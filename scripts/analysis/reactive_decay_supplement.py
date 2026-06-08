#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NH3-N + TP 反应衰减补充实验
（任务 14: 回应审稿人对单指数衰减失败 R²=0.36 / 0.43 的诊断）

实验对比 3 个衰减模型（拟合 2022 月度负荷）：

  Model A — 单指数 (论文 v3 baseline)
      L_m = γ × Σ_i E_i α_i exp(-k d_i) × π(m)
      2 参数: k, γ

  Model B — 双速率两池
      L_m = γ × Σ_i E_i α_i [ p exp(-k_fast d_i) + (1-p) exp(-k_slow d_i) ] × π(m)
      4 参数: γ, p, k_fast, k_slow
      物理含义: TP 颗粒沉降 vs 溶解保守; NH3-N 硝化损失 vs 守恒部分

  Model C — 距离阈值 (TP only)
      L_m = γ × Σ_i E_i α_i × decay(d_i) × π(m)
      其中 decay = exp(-k_near d) if d ≤ d_cut
            else exp(-k_near d_cut - k_far (d - d_cut))
      4 参数: γ, k_near, k_far, d_cut
      物理含义: 近源段快速沉降 (5-10 km 内 70-80% 损失), 之后接近守恒

数据简化：用 SI Table S8 入河量 + 代表距离（各类别均值），不做点源逐点处理。
这适合「测试衰减函数形式」的目的；具体空间分布留给 v3。

输出: output/results/反应衰减补充.xlsx
"""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
LOADS_FILE = ROOT / "data" / "processed" / "monitor_2022_cleaned_v2.xlsx"
OUT_FILE = ROOT / "output" / "results" / "反应衰减补充.xlsx"
REPORT_FILE = ROOT / "output" / "reports" / "反应衰减补充报告.txt"

# SI Table S8 入河量 R (kg, = E × α, 即原始模型中 E_i α_i)
R_VALUES_2022 = {
    '氨氮': {
        '面-农村生活污染源': 1649,
        '面-农业面源': 51,
        '畜禽散养': 76,
        '面-水产养殖': 7,
        '面-城市面源': 124,
        '面-城镇散排': 929,
        '规模畜禽养殖': 2487,
        '点-工业源': 431,
        '点-集中式污染治理设施': 1082,
    },
    '总磷': {
        '面-农村生活污染源': 475,
        '面-农业面源': 63,
        '畜禽散养': 27,
        '面-水产养殖': 3,
        '面-城市面源': 278,
        '面-城镇散排': 101,
        '规模畜禽养殖': 2810,
        '点-工业源': 678,
        '点-集中式污染治理设施': 885,
    },
}

# 各源类别代表距离 (km, 河道距离含弯曲系数 1.4)
# 来源:
#   - SI S4: NPS 控制单元代表距离 8/12/22/30 km
#   - SI Table S12: 点源距离分布
#   - 论文 §3.3: 集中式处理设施 ~7 km, 大型畜禽 ~30-50 km
REPRESENTATIVE_DISTANCE_KM = {
    '面-农村生活污染源': 15.0,        # 控制单元跨度
    '面-农业面源': 22.0,              # CU3
    '畜禽散养': 18.0,                 # CU2-CU3
    '面-水产养殖': 22.0,
    '面-城市面源': 8.0,               # CU1 (近 outlet)
    '面-城镇散排': 10.0,
    '规模畜禽养殖': 40.0,             # 论文称远距
    '点-工业源': 36.0,                # SI S4 median
    '点-集中式污染治理设施': 7.0,     # 论文 §3.3 提到
}

POLLUTANTS_FOCUS = ['氨氮', '总磷']
POLL_COL = {'氨氮': '氨氮(mg/L)', '总磷': '总磷(mg/L)'}


# ─────────────── 数据加载 ───────────────

def load_monthly_targets() -> tuple[dict, dict, dict, dict]:
    """读取 v2 清洗后 2022 数据 → 月度负荷 + 覆盖率 + 流量分配 + 月均水温."""
    df = pd.read_excel(LOADS_FILE)
    df['监测时间'] = pd.to_datetime(df['监测时间'])
    df['month'] = df['监测时间'].dt.month
    df['flow'] = pd.to_numeric(df['瞬时流量(m³/s)'], errors='coerce')
    # 水温列名（清洗后保留）
    temp_col = next((c for c in df.columns if '水温' in c), None)
    if temp_col is not None:
        df[temp_col] = pd.to_numeric(df[temp_col], errors='coerce')

    monthly_loads = {p: {} for p in POLLUTANTS_FOCUS}
    monthly_cov = {p: {} for p in POLLUTANTS_FOCUS}
    for p in POLLUTANTS_FOCUS:
        col = POLL_COL[p]
        df[col] = pd.to_numeric(df[col], errors='coerce')
        for m in range(1, 13):
            sub = df[df['month'] == m]
            valid = sub.dropna(subset=[col, 'flow'])
            monthly_loads[p][m] = float((valid[col] * valid['flow'] * 3.6).sum())
            monthly_cov[p][m] = len(valid) / max(len(sub), 1)

    total_flow = df['flow'].sum()
    flow_fraction = {m: float(df[df['month'] == m]['flow'].sum() / total_flow) if total_flow > 0 else 1/12
                     for m in range(1, 13)}

    monthly_temp = {}
    if temp_col is not None:
        for m in range(1, 13):
            t = df[df['month'] == m][temp_col].mean()
            monthly_temp[m] = float(t) if pd.notna(t) else 15.0  # fallback
    else:
        monthly_temp = {m: 15.0 for m in range(1, 13)}

    return monthly_loads, monthly_cov, flow_fraction, monthly_temp


# ─────────────── 衰减模型 ───────────────

def predict_A(params: tuple, R: dict, dist: dict, pi_m: float) -> float:
    """单指数: L = γ Σ R exp(-k d) × π(m)."""
    k, gamma = params
    total = sum(R[s] * np.exp(-k * dist[s]) for s in R)
    return gamma * total * pi_m


def predict_B(params: tuple, R: dict, dist: dict, pi_m: float) -> float:
    """双速率两池: L = γ Σ R [p exp(-k_fast d) + (1-p) exp(-k_slow d)] × π(m)."""
    k_fast, k_slow, p, gamma = params
    if k_fast < k_slow:
        k_fast, k_slow = k_slow, k_fast  # 强制 fast > slow
    total = 0.0
    for s in R:
        d = dist[s]
        decay = p * np.exp(-k_fast * d) + (1 - p) * np.exp(-k_slow * d)
        total += R[s] * decay
    return gamma * total * pi_m


def predict_C(params: tuple, R: dict, dist: dict, pi_m: float) -> float:
    """距离阈值: 前 d_cut km 快速衰减, 之后慢速."""
    k_near, k_far, d_cut, gamma = params
    if k_near < k_far:
        k_near, k_far = k_far, k_near  # 近段应该更快
    total = 0.0
    for s in R:
        d = dist[s]
        if d <= d_cut:
            decay = np.exp(-k_near * d)
        else:
            decay = np.exp(-k_near * d_cut - k_far * (d - d_cut))
        total += R[s] * decay
    return gamma * total * pi_m


def predict_D(params: tuple, R: dict, dist: dict, pi_m: float, T: float) -> float:
    """Model D: 温度修正衰减 k(T) = k_20 × θ^(T-20).
    生化过程的标准 Arrhenius 形式; θ=1.04-1.08 典型 (Chapra 1997, Birgand 2007)."""
    k_20, theta, gamma = params
    k_T = k_20 * (theta ** (T - 20.0))
    total = sum(R[s] * np.exp(-k_T * dist[s]) for s in R)
    return gamma * total * pi_m


def fit_model_D(R_p: dict, monthly_targets: dict, monthly_cov: dict,
                flow_fraction: dict, monthly_temp: dict, cov_min: float = 0.5):
    """Model D 拟合: 月度负荷需传月均温度."""
    valid_m = [m for m, t in monthly_targets.items() if t > 0 and monthly_cov[m] >= cov_min]

    def obj(params):
        sse = 0.0
        for m in valid_m:
            pred = predict_D(tuple(params), R_p, REPRESENTATIVE_DISTANCE_KM,
                             flow_fraction[m], monthly_temp[m])
            t = monthly_targets[m]
            w = monthly_cov[m]
            sse += w * ((pred - t) / t) ** 2
        return sse

    # 边界: k_20 ∈ [0.001, 0.5], θ ∈ [1.00, 1.15] (生化典型范围), γ ∈ [0.3, 8.0]
    bounds = [(0.001, 0.5), (1.0, 1.15), (0.3, 8.0)]
    res = differential_evolution(obj, bounds=bounds, seed=42, maxiter=500, tol=1e-12, popsize=30)
    obs = np.array([monthly_targets[m] for m in valid_m])
    prd = np.array([predict_D(tuple(res.x), R_p, REPRESENTATIVE_DISTANCE_KM,
                              flow_fraction[m], monthly_temp[m]) for m in valid_m])
    rmse = float(np.sqrt(np.mean((prd - obs) ** 2)))
    ss_res = float(np.sum((prd - obs) ** 2))
    ss_tot = float(np.sum((obs - obs.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float('nan')
    nrmse = rmse / obs.mean() * 100 if obs.mean() > 0 else float('nan')
    bias = (prd.sum() - obs.sum()) / obs.sum() * 100
    return {
        'params': res.x.tolist(),
        'r2': r2, 'rmse': rmse, 'nrmse_pct': nrmse, 'total_bias_pct': bias,
        'n_months': len(valid_m), 'months': valid_m,
        'obs': obs.tolist(), 'pred': prd.tolist(),
    }


# ─────────────── 拟合 ───────────────

def fit_model(predict_fn, bounds, R_p: dict, monthly_targets: dict, monthly_cov: dict,
              flow_fraction: dict, cov_min: float = 0.5):
    """覆盖率加权月度相对误差平方和 (与论文 v3 一致, 仅保留 ≥50% 覆盖月)."""
    valid_m = [m for m, t in monthly_targets.items() if t > 0 and monthly_cov[m] >= cov_min]

    def obj(params):
        sse = 0.0
        for m in valid_m:
            pred = predict_fn(tuple(params), R_p, REPRESENTATIVE_DISTANCE_KM, flow_fraction[m])
            t = monthly_targets[m]
            w = monthly_cov[m]
            sse += w * ((pred - t) / t) ** 2
        return sse

    res = differential_evolution(obj, bounds=bounds, seed=42, maxiter=500, tol=1e-12, popsize=30)
    obs = np.array([monthly_targets[m] for m in valid_m])
    prd = np.array([predict_fn(tuple(res.x), R_p, REPRESENTATIVE_DISTANCE_KM, flow_fraction[m]) for m in valid_m])
    rmse = float(np.sqrt(np.mean((prd - obs) ** 2)))
    ss_res = float(np.sum((prd - obs) ** 2))
    ss_tot = float(np.sum((obs - obs.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float('nan')
    nrmse = rmse / obs.mean() * 100 if obs.mean() > 0 else float('nan')
    bias = (prd.sum() - obs.sum()) / obs.sum() * 100

    return {
        'params': res.x.tolist(),
        'r2': r2, 'rmse': rmse, 'nrmse_pct': nrmse, 'total_bias_pct': bias,
        'n_months': len(valid_m), 'months': valid_m,
        'obs': obs.tolist(), 'pred': prd.tolist(),
    }


# ─────────────── 主流程 ───────────────

def main():
    log = []
    def rpt(s):
        print(s, flush=True); log.append(s)

    rpt("=" * 80)
    rpt(f"NH3-N + TP 反应衰减补充实验  {datetime.now().isoformat(timespec='seconds')}")
    rpt("=" * 80)

    monthly_loads, monthly_cov, flow_fraction, monthly_temp = load_monthly_targets()

    rpt("\n月度流量分配 (与 v3 一致):")
    rpt("  " + " ".join(f"{m}={flow_fraction[m]*100:.1f}%" for m in range(1, 13)))
    rpt("\n月均水温 (°C, 2022 v2 清洗后):")
    rpt("  " + " ".join(f"{m}={monthly_temp[m]:.1f}" for m in range(1, 13)))

    results_all = {}
    for p in POLLUTANTS_FOCUS:
        rpt(f"\n{'='*70}\n{p}\n{'='*70}")
        R_p = R_VALUES_2022[p]
        rpt(f"  入河量 (kg): " + ", ".join(f"{s}={v}" for s, v in R_p.items()))
        rpt(f"  代表距离 (km): " + ", ".join(f"{s}={REPRESENTATIVE_DISTANCE_KM[s]}" for s in R_p))

        targets = monthly_loads[p]
        cov = monthly_cov[p]
        valid_m = [m for m, t in targets.items() if t > 0 and cov[m] >= 0.5]
        rpt(f"\n  有效月份 (cov ≥ 50%): {valid_m} (共 {len(valid_m)})")
        rpt(f"  月度负荷 (kg): " + ", ".join(f"{m}:{targets[m]:.1f}" for m in valid_m))

        results_all[p] = {}

        # --- Model D 温度修正 (使用宽松 setup, 12 月) ---
        rpt(f"\n  ### Model D: 温度修正衰减 k(T) = k_20 × θ^(T-20)  (12 月) ###")
        rD = fit_model_D(R_p, targets, cov, flow_fraction, monthly_temp)
        results_all[p]['D_temp_modulated'] = rD
        rpt(f"    k_20={rD['params'][0]:.4f}, θ={rD['params'][1]:.4f} "
            f"({'升温↑衰减加快' if rD['params'][1] > 1.0 else '升温↓衰减减慢'}), "
            f"γ={rD['params'][2]:.3f}")
        rpt(f"    R²={rD['r2']:+.3f}, NRMSE={rD['nrmse_pct']:.1f}%, "
            f"总偏差={rD['total_bias_pct']:+.1f}%")

        # --- 配置 1: 严格论文 setup (8 月, γ ≤ 5.0) ---
        rpt(f"\n  ### 配置 1: 论文 setup (8 月 Apr-July+Dec/Jan, γ ≤ 5.0) ###")
        # 论文剔除 Aug-Nov 等低覆盖月; 留 Jan-Jul + Dec = 8 个月
        valid_months_paper = [1, 2, 3, 4, 5, 6, 7, 12]
        cov_paper = {m: (cov[m] if m in valid_months_paper else 0.0) for m in cov}

        # Model A (论文 setup)
        rA1 = fit_model(predict_A, [(0.0001, 0.5), (0.3, 5.0)], R_p, targets, cov_paper, flow_fraction)
        results_all[p]['A1_paper_setup'] = rA1
        rpt(f"    Model A: k={rA1['params'][0]:.4f}, γ={rA1['params'][1]:.3f}, "
            f"R²={rA1['r2']:+.3f}, NRMSE={rA1['nrmse_pct']:.1f}%")

        # Model B (论文 setup)
        rB1 = fit_model(predict_B,
                        [(0.05, 1.0), (0.0001, 0.05), (0.0, 1.0), (0.3, 5.0)],
                        R_p, targets, cov_paper, flow_fraction)
        results_all[p]['B1_paper_setup'] = rB1
        rpt(f"    Model B: k_fast={rB1['params'][0]:.4f}, k_slow={rB1['params'][1]:.4f}, "
            f"p={rB1['params'][2]:.3f}, γ={rB1['params'][3]:.3f}, "
            f"R²={rB1['r2']:+.3f}, NRMSE={rB1['nrmse_pct']:.1f}%")

        if p == '总磷':
            rC1 = fit_model(predict_C,
                            [(0.1, 2.0), (0.0001, 0.05), (3.0, 15.0), (0.3, 5.0)],
                            R_p, targets, cov_paper, flow_fraction)
            results_all[p]['C1_paper_setup'] = rC1
            rpt(f"    Model C: k_near={rC1['params'][0]:.4f}, k_far={rC1['params'][1]:.4f}, "
                f"d_cut={rC1['params'][2]:.1f} km, γ={rC1['params'][3]:.3f}, "
                f"R²={rC1['r2']:+.3f}, NRMSE={rC1['nrmse_pct']:.1f}%")

        # --- 配置 2: 宽松 setup (全 12 月, γ ≤ 8.0) ---
        rpt(f"\n  ### 配置 2: 宽松 setup (12 月, γ ≤ 8.0) ###")
        rA2 = fit_model(predict_A, [(0.0001, 0.5), (0.3, 8.0)], R_p, targets, cov, flow_fraction)
        results_all[p]['A2_relaxed'] = rA2
        rpt(f"    Model A: k={rA2['params'][0]:.4f}, γ={rA2['params'][1]:.3f}, "
            f"R²={rA2['r2']:+.3f}, NRMSE={rA2['nrmse_pct']:.1f}%")

        rB2 = fit_model(predict_B,
                        [(0.05, 1.0), (0.0001, 0.05), (0.0, 1.0), (0.3, 8.0)],
                        R_p, targets, cov, flow_fraction)
        results_all[p]['B2_relaxed'] = rB2
        rpt(f"    Model B: k_fast={rB2['params'][0]:.4f}, k_slow={rB2['params'][1]:.4f}, "
            f"p={rB2['params'][2]:.3f}, γ={rB2['params'][3]:.3f}, "
            f"R²={rB2['r2']:+.3f}, NRMSE={rB2['nrmse_pct']:.1f}%")

        if p == '总磷':
            rC2 = fit_model(predict_C,
                            [(0.1, 2.0), (0.0001, 0.05), (3.0, 15.0), (0.3, 8.0)],
                            R_p, targets, cov, flow_fraction)
            results_all[p]['C2_relaxed'] = rC2
            rpt(f"    Model C: k_near={rC2['params'][0]:.4f}, k_far={rC2['params'][1]:.4f}, "
                f"d_cut={rC2['params'][2]:.1f} km, γ={rC2['params'][3]:.3f}, "
                f"R²={rC2['r2']:+.3f}, NRMSE={rC2['nrmse_pct']:.1f}%")

    # ── 模型对比 ──
    rpt("\n" + "=" * 80)
    rpt("汇总：B/C/D 模型相对 A 单指数的改进")
    rpt("=" * 80)
    for p in POLLUTANTS_FOCUS:
        rpt(f"\n  {p}:")
        # Model D vs A2 (宽松 setup, 同 12 月)
        if 'D_temp_modulated' in results_all[p] and 'A2_relaxed' in results_all[p]:
            rA2 = results_all[p]['A2_relaxed']
            rD = results_all[p]['D_temp_modulated']
            dR2 = rD['r2'] - rA2['r2']
            verdict = ("↑↑ 显著改进" if dR2 > 0.15 else
                       "↑ 中等改进"   if dR2 > 0.05 else
                       "≈ 边际改进"   if dR2 > 0.01 else
                       "→ 无改进")
            rpt(f"    --- Model D (温度修正, 12 月 baseline) ---")
            rpt(f"    A baseline:        R²={rA2['r2']:+.3f}, NRMSE={rA2['nrmse_pct']:.1f}%")
            rpt(f"    Model D:           R²={rD['r2']:+.3f} (Δ={dR2:+.3f}), "
                f"NRMSE={rD['nrmse_pct']:.1f}%, θ={rD['params'][1]:.3f}  → {verdict}")

        for cfg in ['1_paper_setup', '2_relaxed']:
            rA_key = f'A{cfg}'
            if rA_key not in results_all[p]:
                continue
            rA = results_all[p][rA_key]
            rpt(f"    --- 配置 {cfg.split('_')[0]} ({cfg.split('_', 1)[1]}) ---")
            rpt(f"    A baseline:        R²={rA['r2']:+.3f}, NRMSE={rA['nrmse_pct']:.1f}%, 总偏差={rA['total_bias_pct']:+.1f}%")
            for lbl in ['B', 'C']:
                key = f'{lbl}{cfg}'
                if key not in results_all[p]:
                    continue
                r = results_all[p][key]
                dR2 = r['r2'] - rA['r2']
                dNRMSE = r['nrmse_pct'] - rA['nrmse_pct']
                verdict = ("↑↑ 显著改进" if dR2 > 0.15 else
                           "↑ 中等改进"   if dR2 > 0.05 else
                           "≈ 边际改进"   if dR2 > 0.01 else
                           "→ 无改进")
                rpt(f"    Model {lbl}:           R²={r['r2']:+.3f} (Δ={dR2:+.3f}), "
                    f"NRMSE={r['nrmse_pct']:.1f}% (Δ={dNRMSE:+.1f}pp)  → {verdict}")

    # ── 写 Excel ──
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows_summary = []
    rows_monthly = []
    for p in POLLUTANTS_FOCUS:
        for lbl, r in results_all[p].items():
            rows_summary.append({
                '污染物': p, '模型': lbl, 'n_months': r['n_months'],
                'R²': r['r2'], 'NRMSE_%': r['nrmse_pct'], '总偏差_%': r['total_bias_pct'],
                '参数': str([round(v, 4) for v in r['params']]),
            })
            for i, m in enumerate(r['months']):
                rows_monthly.append({
                    '污染物': p, '模型': lbl, '月份': m,
                    '观测_kg': round(r['obs'][i], 1),
                    '预测_kg': round(r['pred'][i], 1),
                    '相对误差_%': round((r['pred'][i] - r['obs'][i]) / r['obs'][i] * 100, 1),
                })
    with pd.ExcelWriter(OUT_FILE, engine='openpyxl') as w:
        pd.DataFrame(rows_summary).to_excel(w, sheet_name='模型对比汇总', index=False)
        pd.DataFrame(rows_monthly).to_excel(w, sheet_name='逐月对比', index=False)
        pd.DataFrame([{
            '源': s, '入河量_NH3N_kg': R_VALUES_2022['氨氮'][s],
            '入河量_TP_kg': R_VALUES_2022['总磷'][s], '代表距离_km': REPRESENTATIVE_DISTANCE_KM[s],
        } for s in R_VALUES_2022['氨氮']]).to_excel(w, sheet_name='输入数据', index=False)

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(log), encoding='utf-8')
    rpt(f"\n✓ 输出: {OUT_FILE}")
    rpt(f"  报告: {REPORT_FILE}")


if __name__ == '__main__':
    main()
