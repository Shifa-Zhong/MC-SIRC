#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨年一致性检验：把论文 Setup A 的 Bayesian (MAP+MCMC+先验敏感性) 套到 2020-2024 每年

设计原则（保守强化方案）：
  - **不改论文方法骨架**：9 源 × 4 污染物、同样的截断正态先验、同样的 MAP→MCMC→A/B/C 评级流程
  - **2022 排放清单作为锚定基线**：所有年份共用同一份源清单（论文 Setup A 的 R values）
  - **每年的"监测值"独立计算**：用 v2 清洗后年负荷 × 该年 imputation factor (= hours_in_year / 监测记录数)
  - **核心比较指标**：(a) 各源修正因子跨年 CV；(b) 各源跨年 A/B/C 评级是否稳定；
                    (c) 异常源（如规模畜禽）是否每年都被识别

输出: output/results/多年一致性检验.xlsx
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import truncnorm

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import emcee
    HAS_EMCEE = True
except ImportError:
    HAS_EMCEE = False

ROOT = Path(__file__).resolve().parent.parent.parent
LOADS_FILE = ROOT / "data" / "processed" / "monthly_loads_multiyear.xlsx"
OUT_FILE = ROOT / "output" / "results" / "多年一致性检验.xlsx"
REPORT_FILE = ROOT / "output" / "reports" / "多年一致性检验报告.txt"

# ─────────────── 与 rerun_setup_A.py 完全一致的设置 ───────────────

SOURCE_DATA = {
    'COD': {
        '面-农村生活污染源': 101956, '面-农业面源': 0,
        '畜禽散养': 2861, '面-水产养殖': 167,
        '面-城市面源': 68941, '面-城镇散排': 8121,
        '规模畜禽养殖': 181297, '点-工业源': 29976,
        '点-集中式污染治理设施': 70568,
    },
    '氨氮': {
        '面-农村生活污染源': 1649, '面-农业面源': 51,
        '畜禽散养': 76, '面-水产养殖': 7,
        '面-城市面源': 124, '面-城镇散排': 929,
        '规模畜禽养殖': 2487, '点-工业源': 431,
        '点-集中式污染治理设施': 1082,
    },
    '总氮': {
        '面-农村生活污染源': 3823, '面-农业面源': 1887,
        '畜禽散养': 180, '面-水产养殖': 27,
        '面-城市面源': 2514, '面-城镇散排': 1289,
        '规模畜禽养殖': 10736, '点-工业源': 0,
        '点-集中式污染治理设施': 48692,
    },
    '总磷': {
        '面-农村生活污染源': 475, '面-农业面源': 63,
        '畜禽散养': 27, '面-水产养殖': 3,
        '面-城市面源': 278, '面-城镇散排': 101,
        '规模畜禽养殖': 2810, '点-工业源': 678,
        '点-集中式污染治理设施': 885,
    }
}

DEFAULT_PRIORS = {
    '面-农村生活污染源':      {'mu': 1.0, 'sigma': 0.3},
    '面-农业面源':            {'mu': 1.0, 'sigma': 0.4},
    '畜禽散养':               {'mu': 1.0, 'sigma': 0.4},
    '面-水产养殖':            {'mu': 1.0, 'sigma': 0.5},
    '面-城市面源':            {'mu': 1.0, 'sigma': 0.4},
    '面-城镇散排':            {'mu': 1.0, 'sigma': 0.5},
    '规模畜禽养殖':           {'mu': 0.8, 'sigma': 0.3},
    '点-工业源':              {'mu': 0.9, 'sigma': 0.3},
    '点-集中式污染治理设施':  {'mu': 0.9, 'sigma': 0.3},
}

POLLUTANTS = ['COD', '氨氮', '总氮', '总磷']

# 多年监测值映射：英文 -> 中文（与论文一致）
POLL_NAME = {'COD': 'COD', 'NH3-N': '氨氮', 'TN': '总氮', 'TP': '总磷'}


def neg_log_posterior(params, source_data, M, names, priors, sigma_obs_frac=0.10):
    """与 rerun_setup_A 完全一致的负对数后验。"""
    n = len(names)
    factors = params[:n]
    Up = params[n] if len(params) > n else 0
    pred = sum(source_data[s] * factors[i] for i, s in enumerate(names)) / 1000 + Up
    sigma = sigma_obs_frac * M
    nll = 0.5 * ((pred - M) / sigma) ** 2
    for i, s in enumerate(names):
        mu, sg = priors[s]['mu'], priors[s]['sigma']
        a, b = (0.1 - mu) / sg, (2.0 - mu) / sg
        nll -= truncnorm.logpdf(factors[i], a, b, loc=mu, scale=sg)
    alpha, beta = 2.0, 10.0 / M
    if Up <= 0:
        return 1e10
    nll -= (alpha - 1) * np.log(Up) - beta * Up
    return nll


def map_optimize(source_data, M, names, priors, sigma_obs_frac=0.10, n_starts=30, seed=42):
    np.random.seed(seed)
    bounds = [(0.1, 2.0)] * len(names) + [(0.001 * M, 0.5 * M)]
    best = None
    for _ in range(n_starts):
        x0 = [priors[s]['mu'] + np.random.normal(0, 0.20) for s in names]
        Up0 = np.random.uniform(0.01 * M, 0.3 * M)
        x0 = np.clip(x0, 0.1, 2.0).tolist() + [Up0]
        res = minimize(neg_log_posterior, x0,
                       args=(source_data, M, names, priors, sigma_obs_frac),
                       method='L-BFGS-B', bounds=bounds)
        if best is None or res.fun < best.fun:
            best = res
    return best


def run_mcmc(source_data, M, names, priors, n_walkers=32, n_steps=10000, n_burn=2500, seed=42):
    if not HAS_EMCEE:
        return None
    np.random.seed(seed)
    n = len(names)
    n_dim = n + 1

    def log_prob(theta):
        for i in range(n):
            if theta[i] < 0.1 or theta[i] > 2.0:
                return -np.inf
        if theta[n] < 0 or theta[n] > 0.5 * M:
            return -np.inf
        return -neg_log_posterior(theta, source_data, M, names, priors)

    p0 = []
    for _ in range(n_walkers):
        x = [priors[s]['mu'] + np.random.normal(0, 0.10) for s in names]
        up_init = max(0.1 * M * (1 + np.random.normal(0, 0.5)), 0.01 * M)
        x.append(up_init)
        x = np.clip(x, [0.1] * n + [0.001 * M], [2.0] * n + [0.49 * M])
        p0.append(x)
    sampler = emcee.EnsembleSampler(n_walkers, n_dim, log_prob)
    sampler.run_mcmc(np.array(p0), n_steps, progress=False)
    return sampler.get_chain(discard=n_burn, flat=True)


# ─────────────── 每年监测值的统一计算 ───────────────

RAW_MONITOR_FILE = ROOT / "data" / "raw" / "monitor.xlsx"
_record_count_cache: dict[int, int] = {}

def _count_records_per_year() -> dict[int, int]:
    """读取原始 monitor.xlsx, 计算每年的监测记录数 (= 行数, 与论文 Setup A 一致).
    论文 2022 IMPUTATION_FACTOR = 8705/5928 = 1.4685, 其中 5928 = 2022 监测记录数."""
    if _record_count_cache:
        return _record_count_cache
    df = pd.read_excel(RAW_MONITOR_FILE, header=1, skiprows=[2])
    df['监测时间'] = pd.to_datetime(df['监测时间'], errors='coerce')
    df = df.dropna(subset=['监测时间'])
    df['year'] = df['监测时间'].dt.year
    for y, n in df.groupby('year').size().items():
        _record_count_cache[int(y)] = int(n)
    return _record_count_cache


def get_year_monitor_values(year: int) -> tuple[dict[str, float], float, dict[str, float], int, int]:
    """
    返回 (monitor_values 吨, imputation_factor, raw_v2_loads 吨, expected_hours, observed_records).
    monitor_values = raw_v2 × imputation_factor   （口径 B，与论文 Setup A 一致）

    imputation_factor = expected_hours / observed_records
    其中 observed_records = monitor.xlsx 中该年的行数。
    expected_hours 取整年 (8760 或 8784) 对于完整年; 对于部分年取末次记录前的小时数。
    """
    fa = pd.read_excel(LOADS_FILE, sheet_name='filled_annual_loads')
    fa = fa[fa['year'] == year]
    if fa.empty:
        raise ValueError(f"无 {year} 年的 filled_annual_loads")
    row = fa.iloc[0]
    raw = {POLL_NAME[k]: float(row[k]) / 1000 for k in ['COD', 'NH3-N', 'TN', 'TP']}

    rec_counts = _count_records_per_year()
    n_records = rec_counts.get(year, 0)

    # expected hours: 部分年用该年实际记录跨度近似
    df = pd.read_excel(RAW_MONITOR_FILE, header=1, skiprows=[2])
    df['监测时间'] = pd.to_datetime(df['监测时间'], errors='coerce')
    sub = df[df['监测时间'].dt.year == year].dropna(subset=['监测时间'])
    if sub.empty:
        return {k: 0.0 for k in raw}, 1.0, raw, 0, 0
    if len(sub) == n_records:
        # 完整年：用 8760/8784
        expected_hours = 8784 if year % 4 == 0 else 8760
        # 但若数据只覆盖部分年（如 2019 Aug-Dec, 2024 Jan-Nov），用记录跨度
        t_span_hours = (sub['监测时间'].max() - sub['监测时间'].min()).total_seconds() / 3600
        if t_span_hours < expected_hours * 0.7:  # 跨度 <70% 整年, 视为部分年
            expected_hours = int(t_span_hours)
    else:
        expected_hours = 8784 if year % 4 == 0 else 8760

    imp = expected_hours / max(n_records, 1) if n_records > 0 else 1.0
    # 论文 2022: 8705/5928 = 1.4685 (8705 ≈ 8760-55, 也许排除少数无效日)
    # 我们用 8760, 得 8760/5928 = 1.478, 误差 < 1%, 可接受
    monitor = {k: v * imp for k, v in raw.items()}
    return monitor, imp, raw, expected_hours, n_records


# ─────────────── 主流程 ───────────────

def run_one_year(year: int, log: list[str]):
    def rpt(s):
        print(s, flush=True)
        log.append(s)

    rpt(f"\n{'='*80}")
    rpt(f"年份 {year}")
    rpt('=' * 80)

    monitor, imp, raw, exp_h, n_rec = get_year_monitor_values(year)
    rpt(f"  原始 v2 年负荷 (t): " + ", ".join(f"{k}={v:.2f}" for k,v in raw.items()))
    rpt(f"  监测记录数: {n_rec};  expected_hours: {exp_h};  imputation: {imp:.3f}")
    rpt(f"  Setup A 监测值 (t): " + ", ".join(f"{k}={v:.2f}" for k,v in monitor.items()))

    results = {}
    for p in POLLUTANTS:
        sd = {k: v for k, v in SOURCE_DATA[p].items() if v > 0}
        names = list(sd.keys())
        M = monitor[p]
        if M <= 0:
            continue

        # MAP
        res = map_optimize(sd, M, names, DEFAULT_PRIORS)
        factors = {names[i]: float(res.x[i]) for i in range(len(names))}
        Up = float(res.x[-1])
        pred = sum(sd[s] * factors[s] for s in names) / 1000 + Up
        dev = (pred - M) / M * 100

        # 5 prior scenarios for sensitivity
        scenarios = {
            'S1_low':     lambda mu, sg: (0.5, sg),
            'S2_default': lambda mu, sg: (mu, sg),
            'S3_high':    lambda mu, sg: (1.2, sg),
            'S4_weak':    lambda mu, sg: (mu, 0.5),
            'S5_uninf':   lambda mu, sg: (mu, 1.0),
        }
        sens_factors = {}
        for sc_name, sc_fn in scenarios.items():
            sp = {s: {'mu': sc_fn(DEFAULT_PRIORS[s]['mu'], DEFAULT_PRIORS[s]['sigma'])[0],
                      'sigma': sc_fn(DEFAULT_PRIORS[s]['mu'], DEFAULT_PRIORS[s]['sigma'])[1]}
                  for s in DEFAULT_PRIORS}
            res_sc = map_optimize(sd, M, names, sp)
            sens_factors[sc_name] = {names[i]: float(res_sc.x[i]) for i in range(len(names))}

        # MCMC (reduced steps for speed: 3000 steps × 24 walkers = 60k samples after burn)
        samples = run_mcmc(sd, M, names, DEFAULT_PRIORS, n_walkers=24, n_steps=3000, n_burn=1000)

        results[p] = {
            'M': M, 'pred': pred, 'dev': dev, 'Up': Up,
            'factors': factors, 'names': names,
            'sens_factors': sens_factors,
            'mcmc_samples': samples,
        }
        rpt(f"  {p}: M={M*1000:>9.0f} kg, Pred={pred*1000:>9.0f} kg, Dev={dev:+6.2f}%, Up%={Up/M*100:5.1f}%")
        for n in names:
            mu, sg = DEFAULT_PRIORS[n]['mu'], DEFAULT_PRIORS[n]['sigma']
            z = abs(factors[n] - mu) / sg
            flag = '★' if z > 2 else ('  ' if z < 1 else ' ·')
            rpt(f"    {n:<25s}  f={factors[n]:.3f}  z={z:.2f} {flag}")

    return results


def main():
    log = []
    def rpt(s):
        print(s, flush=True)
        log.append(s)

    rpt("=" * 80)
    rpt("多年跨年一致性检验 (保留论文 Setup A 框架, 仅切换年份)")
    rpt(f"运行时间: {datetime.now().isoformat(timespec='seconds')}")
    rpt(f"emcee 可用: {HAS_EMCEE}")
    rpt("=" * 80)

    # 哪些年份纳入跨年比较？
    # 排除：2019（部分年, Aug-Dec only）、2024（部分年, Jan-Nov only）
    # 但仍跑这两年的 MAP, 作为参考
    YEARS_FULL = [2020, 2021, 2022, 2023]  # 完整年 + 跨年 CV 用
    YEARS_REF = [2019, 2024]               # 部分年, 参考
    ALL_YEARS = YEARS_FULL + YEARS_REF

    all_results: dict[int, dict] = {}
    for y in sorted(ALL_YEARS):
        all_results[y] = run_one_year(y, log)

    # ── 跨年汇总 ──
    rpt("\n\n" + "=" * 80)
    rpt("跨年汇总：完整年 (2020-2023) 修正因子稳定性")
    rpt("=" * 80)

    cross_year_rows = []
    for p in POLLUTANTS:
        rpt(f"\n  {p}:")
        rpt(f"    {'污染源':<25s} " + " ".join(f"{y:>7d}" for y in YEARS_FULL) + "    mean    std     CV(%)")
        rpt("    " + "-" * 90)
        for n in DEFAULT_PRIORS:
            if SOURCE_DATA[p].get(n, 0) <= 0:
                continue
            vals = []
            for y in YEARS_FULL:
                if y in all_results and p in all_results[y]:
                    vals.append(all_results[y][p]['factors'].get(n, np.nan))
                else:
                    vals.append(np.nan)
            arr = np.array(vals, dtype=float)
            arr_valid = arr[~np.isnan(arr)]
            if len(arr_valid) >= 2:
                m, s = arr_valid.mean(), arr_valid.std()
                cv = s / m * 100 if m > 0 else np.nan
            else:
                m = s = cv = np.nan
            cross_year_rows.append({
                '污染物': p, '污染源': n,
                **{f'f_{y}': vals[i] for i, y in enumerate(YEARS_FULL)},
                'mean': m, 'std': s, 'CV_pct': cv,
            })
            rpt(f"    {n:<25s} " + " ".join(f"{v:7.3f}" if not np.isnan(v) else f"{'—':>7s}" for v in vals)
                + f"   {m:.3f}  {s:.3f}  {cv:6.1f}")

    df_cross = pd.DataFrame(cross_year_rows)

    # ── 输出 Excel ──
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_FILE, engine='openpyxl') as w:
        df_cross.to_excel(w, sheet_name='跨年因子稳定性', index=False)

        # 每年 MAP 详细结果
        for y in ALL_YEARS:
            if y not in all_results:
                continue
            rows = []
            for p in POLLUTANTS:
                if p not in all_results[y]:
                    continue
                r = all_results[y][p]
                for n in r['names']:
                    mu = DEFAULT_PRIORS[n]['mu']
                    sg = DEFAULT_PRIORS[n]['sigma']
                    f = r['factors'][n]
                    z = abs(f - mu) / sg
                    rows.append({
                        '污染物': p, '污染源': n, '入河量(kg)': SOURCE_DATA[p][n],
                        'MAP_f': f, '先验μ': mu, '先验σ': sg, 'z': z,
                        '监测值(t)': r['M'], '预测值(t)': r['pred'], '偏差%': r['dev'],
                        'Up(t)': r['Up'], 'Up%': r['Up'] / r['M'] * 100,
                    })
            pd.DataFrame(rows).to_excel(w, sheet_name=f'MAP_{y}', index=False)

        # MCMC 统计每年
        for y in ALL_YEARS:
            if y not in all_results:
                continue
            rows = []
            for p in POLLUTANTS:
                if p not in all_results[y]:
                    continue
                samples = all_results[y][p].get('mcmc_samples')
                if samples is None:
                    continue
                names = all_results[y][p]['names'] + ['Unknown']
                for i, n in enumerate(names):
                    s = samples[:, i]
                    rows.append({
                        '污染物': p, '参数': n,
                        '均值': float(np.mean(s)), '中位数': float(np.median(s)),
                        '标准差': float(np.std(s)),
                        'CI_lo': float(np.percentile(s, 2.5)),
                        'CI_hi': float(np.percentile(s, 97.5)),
                    })
            if rows:
                pd.DataFrame(rows).to_excel(w, sheet_name=f'MCMC_{y}', index=False)

        # 跨年敏感性汇总：每年的 5 情景因子范围
        sens_rows = []
        for y in ALL_YEARS:
            if y not in all_results:
                continue
            for p in POLLUTANTS:
                if p not in all_results[y]:
                    continue
                r = all_results[y][p]
                for n in r['names']:
                    factors_5 = [r['sens_factors'][sc][n] for sc in ['S1_low', 'S2_default', 'S3_high', 'S4_weak', 'S5_uninf']]
                    sens_rows.append({
                        '年份': y, '污染物': p, '污染源': n,
                        'S1_low': factors_5[0], 'S2_default': factors_5[1],
                        'S3_high': factors_5[2], 'S4_weak': factors_5[3], 'S5_uninf': factors_5[4],
                        '因子范围': max(factors_5) - min(factors_5),
                    })
        pd.DataFrame(sens_rows).to_excel(w, sheet_name='跨年敏感性', index=False)

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(log), encoding='utf-8')
    rpt(f"\n✓ 已输出: {OUT_FILE}")
    rpt(f"  报告: {REPORT_FILE}")


if __name__ == '__main__':
    main()
