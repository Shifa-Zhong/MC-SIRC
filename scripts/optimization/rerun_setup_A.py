#!/usr/bin/env python3
"""
Setup A 一致性重跑：贝叶斯 MAP + MCMC + 先验敏感性 + 可靠性评级 + σ_obs 敏感性

Setup A 参数:
  - 入河量: Manuscript Table 2 R values (修正后入河量)
  - 监测目标: 缩放后 (× 1.4685, S2 imputation)
  - 工业源先验: μ=0.9, σ=0.3 (与 SI Table S3 一致)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import truncnorm
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────── Setup A 数据 ───────────────────────────

# Manuscript Table 2 R values (kg) — 修正后入河量
SOURCE_DATA = {
    'COD': {
        '面-农村生活污染源': 101956, '面-农业面源': 0,
        '畜禽散养':         2861,    '面-水产养殖': 167,
        '面-城市面源':      68941,   '面-城镇散排': 8121,
        '规模畜禽养殖':     181297,  '点-工业源':   29976,
        '点-集中式污染治理设施': 70568,
    },
    '氨氮': {
        '面-农村生活污染源': 1649, '面-农业面源': 51,
        '畜禽散养':         76,    '面-水产养殖': 7,
        '面-城市面源':      124,   '面-城镇散排': 929,
        '规模畜禽养殖':     2487,  '点-工业源':   431,
        '点-集中式污染治理设施': 1082,
    },
    '总氮': {
        '面-农村生活污染源': 3823, '面-农业面源': 1887,
        '畜禽散养':         180,   '面-水产养殖': 27,
        '面-城市面源':      2514,  '面-城镇散排': 1289,
        '规模畜禽养殖':     10736, '点-工业源':   0,    # — (industrial TN missing)
        '点-集中式污染治理设施': 48692,
    },
    '总磷': {
        '面-农村生活污染源': 475, '面-农业面源': 63,
        '畜禽散养':         27,    '面-水产养殖': 3,
        '面-城市面源':      278,   '面-城镇散排': 101,
        '规模畜禽养殖':     2810,  '点-工业源':   678,
        '点-集中式污染治理设施': 885,
    }
}

# 缩放后监测值 (吨) — 原始监测 × 1.4685 (S2 imputation: 8705/5928)
RAW_MONITOR = {
    'COD': 111.861560, '氨氮': 3.902692, '总氮': 49.368193, '总磷': 0.570772
}
IMPUTATION_FACTOR = 8705 / 5928  # = 1.4685
MONITOR_VALUES = {p: v * IMPUTATION_FACTOR for p, v in RAW_MONITOR.items()}

# 先验 — Industrial 0.9/0.3 与 SI Table S3 一致
DEFAULT_PRIORS = {
    '面-农村生活污染源':      {'mu': 1.0, 'sigma': 0.3},
    '面-农业面源':            {'mu': 1.0, 'sigma': 0.4},
    '畜禽散养':               {'mu': 1.0, 'sigma': 0.4},
    '面-水产养殖':            {'mu': 1.0, 'sigma': 0.5},  # 注意:Table S3=0.5
    '面-城市面源':            {'mu': 1.0, 'sigma': 0.4},
    '面-城镇散排':            {'mu': 1.0, 'sigma': 0.5},
    '规模畜禽养殖':           {'mu': 0.8, 'sigma': 0.3},
    '点-工业源':              {'mu': 0.9, 'sigma': 0.3},  # ← Setup A 修正
    '点-集中式污染治理设施':  {'mu': 0.9, 'sigma': 0.3},
}

# ─────────────────────────── 核心函数 ───────────────────────────

def neg_log_posterior(params, source_data, M, names, priors, sigma_obs_frac=0.10):
    """负对数后验"""
    n = len(names)
    factors = params[:n]
    Up = params[n] if len(params) > n else 0
    pred = sum(source_data[s]*factors[i] for i,s in enumerate(names))/1000 + Up
    sigma = sigma_obs_frac * M
    nll = 0.5 * ((pred - M)/sigma)**2
    for i, s in enumerate(names):
        mu, sg = priors[s]['mu'], priors[s]['sigma']
        a, b = (0.1 - mu)/sg, (2.0 - mu)/sg
        nll -= truncnorm.logpdf(factors[i], a, b, loc=mu, scale=sg)
    alpha, beta = 2.0, 10.0/M
    if Up <= 0:
        return 1e10
    nll -= (alpha-1)*np.log(Up) - beta*Up
    return nll

def map_optimize(source_data, M, names, priors, sigma_obs_frac=0.10, n_starts=30, seed=42):
    """MAP 优化, 多起点"""
    np.random.seed(seed)
    # 修: Up 下界为 0.001*M 避免 log(0) 的边界数值问题
    bounds = [(0.1, 2.0)]*len(names) + [(0.001*M, 0.5*M)]
    best = None
    for k in range(n_starts):
        x0 = [priors[s]['mu'] + np.random.normal(0, 0.20) for s in names]
        Up0 = np.random.uniform(0.01*M, 0.3*M)
        x0 = np.clip(x0, 0.1, 2.0).tolist() + [Up0]
        res = minimize(neg_log_posterior, x0,
                       args=(source_data, M, names, priors, sigma_obs_frac),
                       method='L-BFGS-B', bounds=bounds)
        if best is None or res.fun < best.fun:
            best = res
    return best

def run_mcmc(source_data, M, names, priors, n_walkers=32, n_steps=20000, n_burn=5000, seed=42):
    """MCMC posterior sampling"""
    try:
        import emcee
    except ImportError:
        print("  pip install emcee 才能运行 MCMC, 跳过")
        return None

    np.random.seed(seed)
    n = len(names)
    n_dim = n + 1  # +1 for unknown source

    def log_prob(theta):
        # bounds
        for i in range(n):
            if theta[i] < 0.1 or theta[i] > 2.0:
                return -np.inf
        if theta[n] < 0 or theta[n] > 0.5*M:
            return -np.inf
        return -neg_log_posterior(theta, source_data, M, names, priors)

    # initial walkers — 给每个 walker 在每个维度都加扰动 (避免 ensemble move 退化)
    p0 = []
    for _ in range(n_walkers):
        x = [priors[s]['mu'] + np.random.normal(0, 0.10) for s in names]
        up_init = 0.1*M * (1 + np.random.normal(0, 0.5))  # 给 Up 维度扰动
        up_init = max(up_init, 0.01*M)
        x.append(up_init)
        x = np.clip(x, [0.1]*n+[0.001*M], [2.0]*n+[0.49*M])
        p0.append(x)
    p0 = np.array(p0)

    sampler = emcee.EnsembleSampler(n_walkers, n_dim, log_prob)
    sampler.run_mcmc(p0, n_steps, progress=False)
    samples = sampler.get_chain(discard=n_burn, flat=True)
    return samples

# ─────────────────────────── 主流程 ───────────────────────────

def main():
    print("=" * 80)
    print("Setup A 重跑：MAP + MCMC + 先验敏感性 + 可靠性评级 + σ_obs 敏感性")
    print("=" * 80)
    print(f"\n监测值 (缩放, t):  ", {p: round(v,2) for p,v in MONITOR_VALUES.items()})
    print(f"工业源先验:          μ=0.9, σ=0.3 (Setup A)")

    pollutants = ['COD', '氨氮', '总氮', '总磷']
    output_dir = Path('D:/shanxi/output/results')
    output_dir.mkdir(parents=True, exist_ok=True)

    # ============ 1. MAP 优化 ============
    print("\n" + "─"*80)
    print("【1】MAP 优化（默认 σ_obs=10%）")
    print("─"*80)

    map_results = {}
    for p in pollutants:
        sd = {k: v for k, v in SOURCE_DATA[p].items() if v > 0}
        names = list(sd.keys())
        M = MONITOR_VALUES[p]
        res = map_optimize(sd, M, names, DEFAULT_PRIORS)
        factors = {names[i]: res.x[i] for i in range(len(names))}
        Up = res.x[-1]
        pred = sum(sd[s]*factors[s] for s in names)/1000 + Up
        dev = (pred - M) / M * 100
        map_results[p] = {
            'factors': factors, 'Up': Up, 'pred': pred, 'M': M, 'dev': dev,
            'names': names
        }
        print(f"\n  {p}: M={M*1000:.0f} kg, Pred={pred*1000:.0f} kg, Dev={dev:+.2f}%, Up={Up*1000:.0f} kg ({Up/M*100:.1f}%)")
        for n in names:
            mu, sg = DEFAULT_PRIORS[n]['mu'], DEFAULT_PRIORS[n]['sigma']
            z = abs(factors[n]-mu)/sg
            flag = '★' if z > 2 else ''
            print(f"    {n:<25s}  f={factors[n]:.3f}  z={z:.2f}  {flag}")

    # ============ 2. MCMC ============
    print("\n" + "─"*80)
    print("【2】MCMC 采样（32 walkers, 20000 steps, 5000 burn-in）")
    print("─"*80)

    mcmc_results = {}
    for p in pollutants:
        sd = {k: v for k, v in SOURCE_DATA[p].items() if v > 0}
        names = list(sd.keys())
        M = MONITOR_VALUES[p]
        samples = run_mcmc(sd, M, names, DEFAULT_PRIORS)
        if samples is None:
            print(f"  {p}: MCMC 跳过")
            continue
        # 统计
        stats = {}
        for i, n in enumerate(names + ['Unknown']):
            s = samples[:, i]
            stats[n] = {
                'mean': np.mean(s), 'median': np.median(s), 'std': np.std(s),
                'ci_lo': np.percentile(s, 2.5), 'ci_hi': np.percentile(s, 97.5)
            }
        mcmc_results[p] = {'samples': samples, 'stats': stats, 'names': names}
        print(f"\n  {p}: 样本数 {samples.shape[0]}")
        for n in names:
            st = stats[n]
            print(f"    {n:<25s}  mean={st['mean']:.3f}  CI=[{st['ci_lo']:.3f},{st['ci_hi']:.3f}]")
        st = stats['Unknown']
        print(f"    {'Unknown (t)':<25s}  mean={st['mean']:.3f}  CI=[{st['ci_lo']:.3f},{st['ci_hi']:.3f}]")

    # ============ 3. 先验敏感性 5 情景 ============
    print("\n" + "─"*80)
    print("【3】先验敏感性 5 情景")
    print("─"*80)

    scenarios = {
        'S1 Low':      lambda mu,sg: (0.5, sg),
        'S2 Default':  lambda mu,sg: (mu, sg),
        'S3 High':     lambda mu,sg: (1.2, sg),
        'S4 Weak':     lambda mu,sg: (mu, 0.5),
        'S5 Uninf.':   lambda mu,sg: (mu, 1.0),
    }

    sens_results = {}
    for p in pollutants:
        sd = {k: v for k, v in SOURCE_DATA[p].items() if v > 0}
        names = list(sd.keys())
        M = MONITOR_VALUES[p]
        sens_results[p] = {}
        for sc_name, sc_fn in scenarios.items():
            scenario_priors = {}
            for s in DEFAULT_PRIORS:
                mu, sg = DEFAULT_PRIORS[s]['mu'], DEFAULT_PRIORS[s]['sigma']
                new_mu, new_sg = sc_fn(mu, sg)
                scenario_priors[s] = {'mu': new_mu, 'sigma': new_sg}
            res = map_optimize(sd, M, names, scenario_priors)
            factors = {names[i]: res.x[i] for i in range(len(names))}
            Up = res.x[-1]
            pred = sum(sd[s]*factors[s] for s in names)/1000 + Up
            dev = (pred - M) / M * 100
            sens_results[p][sc_name] = {
                'factors': factors, 'Up': Up, 'pred': pred, 'dev': dev
            }

    # ============ 4. σ_obs 敏感性 ============
    print("\n" + "─"*80)
    print("【4】σ_obs 敏感性 (5%/10%/20%)")
    print("─"*80)

    sigma_results = {}
    for p in pollutants:
        sd = {k: v for k, v in SOURCE_DATA[p].items() if v > 0}
        names = list(sd.keys())
        M = MONITOR_VALUES[p]
        sigma_results[p] = {}
        for sigma in [0.05, 0.10, 0.20]:
            res = map_optimize(sd, M, names, DEFAULT_PRIORS, sigma_obs_frac=sigma)
            factors = {names[i]: res.x[i] for i in range(len(names))}
            Up = res.x[-1]
            sigma_results[p][f'{int(sigma*100)}%'] = {'factors': factors, 'Up': Up}

    # ============ 5. 可靠性评级 ============
    print("\n" + "─"*80)
    print("【5】可靠性评级")
    print("─"*80)

    rating_rows = []
    for p in pollutants:
        sd = {k: v for k, v in SOURCE_DATA[p].items() if v > 0}
        names = list(sd.keys())
        for n in names:
            mu = DEFAULT_PRIORS[n]['mu']
            sg = DEFAULT_PRIORS[n]['sigma']
            f_map = map_results[p]['factors'][n]
            shift = abs(f_map - mu) / sg
            # 跨情景因子范围
            f_across = [sens_results[p][sc]['factors'][n] for sc in scenarios.keys()]
            f_range = max(f_across) - min(f_across)
            # 评级 (与原脚本一致: shift>1.5 AND range<0.1 → A)
            if shift > 1.5 and f_range < 0.1:
                rating = 'A'
            elif shift > 0.5 and f_range < 0.3:
                rating = 'B'
            else:
                rating = 'C'
            rating_rows.append({
                '污染物': p, '污染源': n, '先验μ': mu,
                'MAP f': f_map, 'shift': shift, '因子范围': f_range, '评级': rating
            })
    df_rating = pd.DataFrame(rating_rows)
    print("\n  数量统计:")
    counts = df_rating['评级'].value_counts()
    print(f"    A: {counts.get('A',0)}, B: {counts.get('B',0)}, C: {counts.get('C',0)}")

    # ============ 输出 Excel ============
    out_file = output_dir / 'setup_A_完整结果.xlsx'
    with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
        # MAP 总表
        map_summary_rows = []
        for p in pollutants:
            r = map_results[p]
            map_summary_rows.append({
                '污染物': p, '监测值(kg)': r['M']*1000,
                '预测值(kg)': r['pred']*1000, '偏差%': r['dev'],
                '未知源(kg)': r['Up']*1000, '未知源%': r['Up']/r['M']*100
            })
        pd.DataFrame(map_summary_rows).to_excel(writer, sheet_name='MAP汇总', index=False)

        # MAP 详情
        map_detail_rows = []
        for p in pollutants:
            for n, f in map_results[p]['factors'].items():
                mu = DEFAULT_PRIORS[n]['mu']
                sg = DEFAULT_PRIORS[n]['sigma']
                z = abs(f-mu)/sg
                map_detail_rows.append({
                    '污染物': p, '污染源': n, '入河量(kg)': SOURCE_DATA[p][n],
                    'MAP f': f, '先验μ': mu, '先验σ': sg, 'z-score': z
                })
        pd.DataFrame(map_detail_rows).to_excel(writer, sheet_name='MAP详情', index=False)

        # MCMC 详情
        for p in pollutants:
            if p not in mcmc_results:
                continue
            rows = []
            stats = mcmc_results[p]['stats']
            for n, st in stats.items():
                rows.append({
                    '参数': n, '均值': st['mean'], '中位数': st['median'],
                    '标准差': st['std'], '95%CI下限': st['ci_lo'], '95%CI上限': st['ci_hi']
                })
            pd.DataFrame(rows).to_excel(writer, sheet_name=f'MCMC_{p}', index=False)

        # 相关矩阵
        for p in pollutants:
            if p not in mcmc_results:
                continue
            samples = mcmc_results[p]['samples']
            names = mcmc_results[p]['names'] + ['Unknown']
            corr = np.corrcoef(samples.T)
            df_corr = pd.DataFrame(corr, index=names, columns=names)
            df_corr.to_excel(writer, sheet_name=f'MCMC_corr_{p}')

        # 先验敏感性
        for p in pollutants:
            sd = {k: v for k, v in SOURCE_DATA[p].items() if v > 0}
            names = list(sd.keys())
            rows = []
            for sc in scenarios.keys():
                row = {'情景': sc, '偏差%': sens_results[p][sc]['dev'],
                       '未知源(t)': sens_results[p][sc]['Up']}
                for n in names:
                    row[n] = sens_results[p][sc]['factors'][n]
                rows.append(row)
            pd.DataFrame(rows).to_excel(writer, sheet_name=f'先验敏感性_{p}', index=False)

        # σ_obs 敏感性
        sigma_rows = []
        for p in pollutants:
            sd = {k: v for k, v in SOURCE_DATA[p].items() if v > 0}
            names = list(sd.keys())
            for sg_name in ['5%', '10%', '20%']:
                row = {'污染物': p, 'σ_obs': sg_name}
                for n in names:
                    row[n] = sigma_results[p][sg_name]['factors'][n]
                row['未知源(t)'] = sigma_results[p][sg_name]['Up']
                sigma_rows.append(row)
        pd.DataFrame(sigma_rows).to_excel(writer, sheet_name='σ_obs敏感性', index=False)

        # 可靠性评级
        df_rating.to_excel(writer, sheet_name='可靠性评级', index=False)

    print(f"\n✓ 已输出: {out_file}")
    return map_results, mcmc_results, sens_results, sigma_results, df_rating

if __name__ == '__main__':
    main()
