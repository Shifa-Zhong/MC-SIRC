#!/usr/bin/env python3
"""
贝叶斯先验敏感性全面分析 (修复硬伤3)

修复问题:
  1方程9+未知数 → 结果受先验主导
  原分析只测试σ放大, 未测试μ方向的影响

本脚本:
  1. 先验均值敏感性矩阵 (5种情景 × 高贡献源)
  2. σ_obs敏感性 (5%/10%/20%)
  3. 先验→后验偏移量 (数据学习量评估)
  4. 综合可靠性评级

输出: output/reports/贝叶斯先验敏感性报告.txt
      output/results/贝叶斯先验敏感性.xlsx
      output/figures/bayesian_sensitivity_*.png
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from pathlib import Path

# ── 路径 ──
ROOT = Path(__file__).resolve().parent
while not (ROOT / 'data').is_dir() and ROOT != ROOT.parent:
    ROOT = ROOT.parent

output_dir = ROOT / 'output'
report_file = output_dir / 'reports' / '贝叶斯先验敏感性报告.txt'
fig_dir = output_dir / 'figures'
for d in [output_dir / 'reports', fig_dir]:
    d.mkdir(parents=True, exist_ok=True)

report = []
def rpt(s=''):
    report.append(s)
    print(s)

# ============================================================
# 数据定义 (复用自 optimize_coefficients_bayesian.py)
# ============================================================

MONITOR_VALUES = {
    'COD': 111.861560,
    '氨氮': 3.902692,
    '总氮': 49.368193,
    '总磷': 0.570772
}

SOURCE_DATA = {
    'COD': {
        '面-农村生活污染源': 25490, '面-农业面源': 0,
        '畜禽散养': 2850, '面-城市面源': 68940,
        '面-城镇散排': 5230, '规模畜禽养殖': 181300,
        '点-工业源': 80260, '点-集中式污染治理设施': 70570,
    },
    '氨氮': {
        '面-农村生活污染源': 380, '畜禽散养': 59,
        '面-城市面源': 220, '面-城镇散排': 930,
        '规模畜禽养殖': 2490, '点-工业源': 1200,
        '点-集中式污染治理设施': 1080,
    },
    '总氮': {
        '面-农村生活污染源': 3040, '面-农业面源': 1570,
        '畜禽散养': 270, '面-城市面源': 2510,
        '规模畜禽养殖': 10740, '点-集中式污染治理设施': 48690,
    },
    '总磷': {
        '面-农村生活污染源': 69, '面-农业面源': 240,
        '畜禽散养': 47, '面-城市面源': 170,
        '规模畜禽养殖': 2810, '点-工业源': 679,
        '点-集中式污染治理设施': 890,
    }
}

# 默认先验 (与原脚本一致)
DEFAULT_PRIORS = {
    '面-农村生活污染源': {'mu': 1.0, 'sigma': 0.3},
    '面-农业面源':       {'mu': 1.0, 'sigma': 0.4},
    '畜禽散养':          {'mu': 1.0, 'sigma': 0.4},
    '面-水产养殖':       {'mu': 1.0, 'sigma': 0.3},
    '面-城市面源':       {'mu': 1.0, 'sigma': 0.4},
    '面-城镇散排':       {'mu': 1.0, 'sigma': 0.5},
    '规模畜禽养殖':      {'mu': 0.8, 'sigma': 0.3},
    '点-工业源':         {'mu': 0.7, 'sigma': 0.4},
    '点-集中式污染治理设施': {'mu': 0.9, 'sigma': 0.3},
}

# ============================================================
# 核心优化函数
# ============================================================

def neg_log_posterior(params, source_data, monitor_value, source_names,
                      priors, sigma_obs_frac=0.10, include_unknown=True):
    """负对数后验 (可自定义先验和σ_obs)"""
    n_sources = len(source_names)
    factors = {source_names[i]: params[i] for i in range(n_sources)}
    unknown_source = params[n_sources] if include_unknown else 0

    predicted = sum(
        emission * factors[src] / 1000
        for src, emission in source_data.items()
        if emission > 0 and src in factors
    ) + unknown_source

    sigma_obs = monitor_value * sigma_obs_frac
    log_likelihood = -0.5 * ((monitor_value - predicted) / sigma_obs) ** 2

    log_prior = 0
    for i, src in enumerate(source_names):
        f = params[i]
        p = priors.get(src, {'mu': 1.0, 'sigma': 0.3})
        if 0.1 <= f <= 2.0:
            log_prior += -0.5 * ((f - p['mu']) / p['sigma']) ** 2
        else:
            log_prior += -1000

    if include_unknown and unknown_source >= 0:
        alpha_g = 2
        beta_g = 10 / monitor_value
        log_prior += (alpha_g - 1) * np.log(unknown_source + 0.001) - beta_g * unknown_source
    elif include_unknown:
        log_prior += -1000

    return -(log_likelihood + log_prior)


def run_optimization(pollutant, priors, sigma_obs_frac=0.10):
    """运行一次MAP优化"""
    source_data = SOURCE_DATA[pollutant]
    monitor_value = MONITOR_VALUES[pollutant]

    active_sources = {k: v for k, v in source_data.items() if v > 0}
    source_names = list(active_sources.keys())
    n_sources = len(source_names)

    x0 = [priors.get(s, {'mu': 1.0})['mu'] for s in source_names]
    x0.append(monitor_value * 0.1)
    bounds = [(0.1, 2.0)] * n_sources + [(0, monitor_value * 0.5)]

    result = minimize(
        neg_log_posterior, x0,
        args=(active_sources, monitor_value, source_names, priors, sigma_obs_frac, True),
        method='L-BFGS-B', bounds=bounds
    )

    factors = {source_names[i]: result.x[i] for i in range(n_sources)}
    unknown = result.x[n_sources]

    corrected_total = sum(e * factors[s] / 1000 for s, e in active_sources.items()) + unknown
    residual = (corrected_total - monitor_value) / monitor_value * 100

    return {
        'factors': factors,
        'unknown': unknown,
        'corrected_total': corrected_total,
        'residual_pct': residual,
        'success': result.success,
    }


# ============================================================
# 分析1: 先验均值敏感性矩阵
# ============================================================
rpt("=" * 100)
rpt("贝叶斯先验敏感性全面分析")
rpt("=" * 100)

rpt(f"\n第1部分: 先验均值敏感性矩阵")
rpt("-" * 60)

# 先找出每个污染物贡献率最高的3个源
rpt(f"\n  各污染物高贡献源:")
top_sources = {}
for pol in ['COD', '氨氮', '总氮', '总磷']:
    sd = {k: v for k, v in SOURCE_DATA[pol].items() if v > 0}
    total = sum(sd.values())
    sorted_srcs = sorted(sd.items(), key=lambda x: -x[1])
    top3 = [(s, v / total * 100) for s, v in sorted_srcs[:3]]
    top_sources[pol] = [s for s, _ in top3]
    rpt(f"  {pol}: " + ", ".join(f"{s}({pct:.1f}%)" for s, pct in top3))

# 5种先验情景
SCENARIOS = {
    'S1_低估': 0.5,
    'S2_默认': None,  # 使用DEFAULT_PRIORS的μ
    'S3_高估': 1.2,
    'S4_弱先验': None,  # μ=0.8, σ=0.5
    'S5_无信息': None,  # μ=1.0, σ=1.0
}

sensitivity_results = {}  # {pol: {scenario: {source: factor}}}

for pol in ['COD', '氨氮', '总氮', '总磷']:
    rpt(f"\n{'=' * 60}")
    rpt(f"  {pol}")
    rpt(f"{'=' * 60}")

    sensitivity_results[pol] = {}

    for scenario_name in SCENARIOS:
        # 构建该情景的先验
        priors = {}
        for src in DEFAULT_PRIORS:
            dp = DEFAULT_PRIORS[src]
            if scenario_name == 'S1_低估':
                priors[src] = {'mu': 0.5, 'sigma': 0.3}
            elif scenario_name == 'S2_默认':
                priors[src] = {'mu': dp['mu'], 'sigma': dp['sigma']}
            elif scenario_name == 'S3_高估':
                priors[src] = {'mu': 1.2, 'sigma': 0.3}
            elif scenario_name == 'S4_弱先验':
                priors[src] = {'mu': 0.8, 'sigma': 0.5}
            elif scenario_name == 'S5_无信息':
                priors[src] = {'mu': 1.0, 'sigma': 1.0}

        res = run_optimization(pol, priors)
        sensitivity_results[pol][scenario_name] = res

    # 打印对比表
    active_sources = [k for k, v in SOURCE_DATA[pol].items() if v > 0]
    header = f"\n  {'情景':<12s}  "
    for src in active_sources:
        short = src[-4:] if len(src) > 4 else src
        header += f"{short:>8s}  "
    header += f"{'未知源':>8s}  {'偏差%':>8s}"
    rpt(header)
    rpt("  " + "-" * (12 + len(active_sources) * 10 + 20))

    for scenario_name in SCENARIOS:
        res = sensitivity_results[pol][scenario_name]
        line = f"  {scenario_name:<12s}  "
        for src in active_sources:
            f = res['factors'].get(src, float('nan'))
            line += f"{f:>8.3f}  "
        line += f"{res['unknown']:>8.3f}  {res['residual_pct']:>+7.2f}%"
        rpt(line)

# ============================================================
# 分析2: σ_obs敏感性
# ============================================================
rpt(f"\n\n{'=' * 100}")
rpt(f"第2部分: 观测误差σ_obs敏感性")
rpt("=" * 100)
rpt(f"\n  测试σ_obs = 监测值 × {{5%, 10%, 20%}}")
rpt(f"  σ越小 → 似然函数越尖锐 → 数据约束力越强 → 先验影响越小")

sigma_frac_values = [0.05, 0.10, 0.20]
sigma_results = {}

for pol in ['COD', '氨氮', '总氮', '总磷']:
    sigma_results[pol] = {}
    for sf in sigma_frac_values:
        res = run_optimization(pol, DEFAULT_PRIORS, sigma_obs_frac=sf)
        sigma_results[pol][sf] = res

rpt(f"\n  σ_obs敏感性结果 (使用默认先验):")
for pol in ['COD', '氨氮', '总氮', '总磷']:
    rpt(f"\n  {pol}:")
    active = [k for k, v in SOURCE_DATA[pol].items() if v > 0]
    header = f"    {'σ_obs%':>8s}  "
    for src in active:
        short = src[-4:] if len(src) > 4 else src
        header += f"{short:>8s}  "
    header += f"{'未知源':>8s}"
    rpt(header)
    rpt("    " + "-" * (8 + len(active) * 10 + 10))

    for sf in sigma_frac_values:
        res = sigma_results[pol][sf]
        line = f"    {sf*100:>7.0f}%  "
        for src in active:
            f = res['factors'].get(src, float('nan'))
            line += f"{f:>8.3f}  "
        line += f"{res['unknown']:>8.3f}"
        rpt(line)

# ============================================================
# 分析3: 先验→后验偏移量 (数据学习量)
# ============================================================
rpt(f"\n\n{'=' * 100}")
rpt(f"第3部分: 先验→后验偏移量分析")
rpt("=" * 100)
rpt(f"\n  shift_i = |f_MAP - μ_i| / σ_i")
rpt(f"  shift > 1.5: 数据主导 (先验被显著拉动)")
rpt(f"  shift < 0.5: 先验主导 (数据信息不足)")

shift_results = {}

for pol in ['COD', '氨氮', '总氮', '总磷']:
    rpt(f"\n  {pol}:")
    res = sensitivity_results[pol]['S2_默认']
    shift_results[pol] = {}

    rpt(f"    {'污染源':<25s}  {'先验μ':>6s}  {'后验f':>6s}  {'先验σ':>6s}  {'shift':>6s}  {'判断'}")
    rpt("    " + "-" * 70)

    for src in [k for k, v in SOURCE_DATA[pol].items() if v > 0]:
        f_map = res['factors'].get(src, float('nan'))
        p = DEFAULT_PRIORS.get(src, {'mu': 1.0, 'sigma': 0.3})
        shift = abs(f_map - p['mu']) / p['sigma'] if p['sigma'] > 0 else 0

        if shift > 1.5:
            judge = "数据主导 ★"
        elif shift > 0.5:
            judge = "混合"
        else:
            judge = "先验主导 ⚠"

        shift_results[pol][src] = {'shift': shift, 'judge': judge, 'f_map': f_map}
        rpt(f"    {src:<25s}  {p['mu']:>6.2f}  {f_map:>6.3f}  {p['sigma']:>6.2f}  {shift:>6.2f}  {judge}")

# ============================================================
# 分析4: 跨情景一致性检验 (关键结论稳健性)
# ============================================================
rpt(f"\n\n{'=' * 100}")
rpt(f"第4部分: 跨情景一致性检验")
rpt("=" * 100)
rpt(f"\n  检验: 异常检测结论是否在不同先验情景下保持一致")
rpt(f"  如果某源在所有情景下都被压到下限(0.1), 说明异常检测是数据驱动的")

for pol in ['COD', '氨氮', '总氮', '总磷']:
    rpt(f"\n  {pol}:")
    active = [k for k, v in SOURCE_DATA[pol].items() if v > 0]

    for src in active:
        factors_across = [
            sensitivity_results[pol][s]['factors'].get(src, float('nan'))
            for s in SCENARIOS
        ]
        factors_clean = [f for f in factors_across if not np.isnan(f)]
        if not factors_clean:
            continue

        f_min = min(factors_clean)
        f_max = max(factors_clean)
        f_range = f_max - f_min
        f_mean = np.mean(factors_clean)

        # 判断稳定性
        if f_range < 0.1:
            stability = "高稳定 (不受先验影响)"
        elif f_range < 0.3:
            stability = "中等稳定"
        else:
            stability = "不稳定 (先验敏感)"

        # 是否一致被判为异常
        all_low = all(f < 0.3 for f in factors_clean)
        all_high = all(f > 1.5 for f in factors_clean)

        tag = ""
        if all_low:
            tag = " → 铁证: 数据驱动的异常检测"
        elif all_high:
            tag = " → 铁证: 系数需大幅上调"

        if f_range > 0.05 or tag:
            rpt(f"    {src}: [{f_min:.3f}, {f_max:.3f}] (范围{f_range:.3f}) {stability}{tag}")

# ============================================================
# 分析5: 综合可靠性评级
# ============================================================
rpt(f"\n\n{'=' * 100}")
rpt(f"第5部分: 修正因子综合可靠性评级")
rpt("=" * 100)

rpt(f"\n  评级标准:")
rpt(f"    A: 数据主导(shift>1.5) + 跨情景稳定(范围<0.1) → 可直接使用")
rpt(f"    B: 混合(shift 0.5-1.5) + 较稳定(范围<0.3) → 谨慎使用")
rpt(f"    C: 先验主导(shift<0.5) 或 不稳定(范围>0.3) → 不可靠, 需更多数据")

for pol in ['COD', '氨氮', '总氮', '总磷']:
    rpt(f"\n  {pol}:")
    rpt(f"    {'污染源':<25s}  {'shift':>6s}  {'因子范围':>10s}  {'评级':>4s}  {'建议'}")
    rpt("    " + "-" * 70)

    active = [k for k, v in SOURCE_DATA[pol].items() if v > 0]
    for src in active:
        sr = shift_results.get(pol, {}).get(src, {})
        shift = sr.get('shift', 0)

        factors_across = [
            sensitivity_results[pol][s]['factors'].get(src, float('nan'))
            for s in SCENARIOS
        ]
        factors_clean = [f for f in factors_across if not np.isnan(f)]
        f_range = max(factors_clean) - min(factors_clean) if factors_clean else 999

        if shift > 1.5 and f_range < 0.1:
            grade = 'A'
            advice = '可直接使用修正因子'
        elif shift > 0.5 and f_range < 0.3:
            grade = 'B'
            advice = '参考使用, 注意不确定性'
        else:
            grade = 'C'
            advice = '不可靠, 需补充独立验证数据'

        rpt(f"    {src:<25s}  {shift:>6.2f}  [{min(factors_clean):.3f},{max(factors_clean):.3f}]  "
            f"  {grade:>2s}  {advice}")

# ── 保存报告 ──
with open(report_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))
rpt(f"\n✓ 报告已保存: {report_file}")

# ── 生成可视化 ──
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False

    # 图1: 先验-后验对比 (每个污染物)
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    for idx, pol in enumerate(['COD', '氨氮', '总氮', '总磷']):
        ax = axes[idx // 2][idx % 2]
        active = [k for k, v in SOURCE_DATA[pol].items() if v > 0]
        short_names = [s.replace('面-', '').replace('点-', '')[:6] for s in active]

        x = np.arange(len(active))
        # 先验均值
        prior_mu = [DEFAULT_PRIORS.get(s, {'mu': 1.0})['mu'] for s in active]
        prior_sigma = [DEFAULT_PRIORS.get(s, {'sigma': 0.3})['sigma'] for s in active]
        # 后验 (默认情景)
        post_f = [sensitivity_results[pol]['S2_默认']['factors'].get(s, np.nan) for s in active]

        ax.bar(x - 0.15, prior_mu, 0.3, yerr=prior_sigma, label='先验', color='lightgray',
               edgecolor='gray', capsize=3)
        ax.bar(x + 0.15, post_f, 0.3, label='后验(MAP)', color='steelblue')
        ax.axhline(y=1.0, color='green', linestyle='--', alpha=0.3)
        ax.set_xticks(x)
        ax.set_xticklabels(short_names, rotation=45, ha='right', fontsize=8)
        ax.set_ylabel('修正因子')
        ax.set_title(f'{pol}')
        ax.legend(fontsize=8)
        ax.set_ylim(0, 2.2)

    plt.suptitle('先验→后验对比 (灰色=先验±σ, 蓝色=MAP后验)', fontsize=13)
    plt.tight_layout()
    plt.savefig(fig_dir / 'bayesian_sensitivity_prior_posterior.png', dpi=150, bbox_inches='tight')
    plt.close()

    # 图2: 敏感性热力图 (5情景 × 源)
    for pol in ['COD', '氨氮', '总氮', '总磷']:
        active = [k for k, v in SOURCE_DATA[pol].items() if v > 0]
        short_names = [s.replace('面-', '').replace('点-', '')[:6] for s in active]
        scenarios = list(SCENARIOS.keys())

        matrix = np.zeros((len(scenarios), len(active)))
        for i, sc in enumerate(scenarios):
            for j, src in enumerate(active):
                matrix[i, j] = sensitivity_results[pol][sc]['factors'].get(src, np.nan)

        fig, ax = plt.subplots(figsize=(max(8, len(active)), 4))
        im = ax.imshow(matrix, cmap='RdYlBu_r', aspect='auto', vmin=0.1, vmax=2.0)
        ax.set_xticks(range(len(active)))
        ax.set_xticklabels(short_names, rotation=45, ha='right', fontsize=9)
        ax.set_yticks(range(len(scenarios)))
        ax.set_yticklabels(scenarios, fontsize=9)
        # 标注数值
        for i in range(len(scenarios)):
            for j in range(len(active)):
                v = matrix[i, j]
                if not np.isnan(v):
                    ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=8,
                            color='white' if v < 0.4 or v > 1.5 else 'black')
        plt.colorbar(im, label='修正因子')
        ax.set_title(f'{pol} - 先验均值敏感性矩阵')
        plt.tight_layout()
        plt.savefig(fig_dir / f'bayesian_sensitivity_heatmap_{pol}.png', dpi=150, bbox_inches='tight')
        plt.close()

    # 图3: σ_obs敏感性对比
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for idx, pol in enumerate(['COD', '氨氮', '总氮', '总磷']):
        ax = axes[idx // 2][idx % 2]
        active = [k for k, v in SOURCE_DATA[pol].items() if v > 0]
        short_names = [s.replace('面-', '').replace('点-', '')[:6] for s in active]
        x = np.arange(len(active))
        w = 0.25

        for i, sf in enumerate(sigma_frac_values):
            factors = [sigma_results[pol][sf]['factors'].get(s, np.nan) for s in active]
            ax.bar(x + (i - 1) * w, factors, w, label=f'σ={sf*100:.0f}%')

        ax.set_xticks(x)
        ax.set_xticklabels(short_names, rotation=45, ha='right', fontsize=8)
        ax.set_ylabel('修正因子')
        ax.set_title(f'{pol}')
        ax.legend(fontsize=8)
        ax.axhline(y=1.0, color='green', linestyle='--', alpha=0.3)

    plt.suptitle('观测误差σ_obs对修正因子的影响', fontsize=13)
    plt.tight_layout()
    plt.savefig(fig_dir / 'bayesian_sensitivity_sigma_obs.png', dpi=150, bbox_inches='tight')
    plt.close()

    rpt(f"✓ 图表已保存")

except ImportError:
    rpt(f"  注: matplotlib不可用, 跳过图表")
except Exception as e:
    rpt(f"  图表出错: {e}")

# ── 导出Excel ──
excel_file = output_dir / 'results' / '贝叶斯先验敏感性.xlsx'
try:
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # 先验敏感性矩阵
        for pol in ['COD', '氨氮', '总氮', '总磷']:
            rows = []
            active = [k for k, v in SOURCE_DATA[pol].items() if v > 0]
            for sc in SCENARIOS:
                res = sensitivity_results[pol][sc]
                row = {'情景': sc, '未知源': res['unknown'], '偏差%': res['residual_pct']}
                for src in active:
                    row[src] = res['factors'].get(src, np.nan)
                rows.append(row)
            pd.DataFrame(rows).to_excel(writer, sheet_name=f'{pol}_先验敏感性', index=False)

        # σ_obs敏感性
        rows = []
        for pol in ['COD', '氨氮', '总氮', '总磷']:
            active = [k for k, v in SOURCE_DATA[pol].items() if v > 0]
            for sf in sigma_frac_values:
                res = sigma_results[pol][sf]
                row = {'污染物': pol, 'σ_obs%': sf * 100}
                for src in active:
                    row[src] = res['factors'].get(src, np.nan)
                row['未知源'] = res['unknown']
                rows.append(row)
        pd.DataFrame(rows).to_excel(writer, sheet_name='σ_obs敏感性', index=False)

        # 偏移量和评级
        rows = []
        for pol in ['COD', '氨氮', '总氮', '总磷']:
            for src, sr in shift_results.get(pol, {}).items():
                factors_across = [
                    sensitivity_results[pol][s]['factors'].get(src, np.nan)
                    for s in SCENARIOS
                ]
                fc = [f for f in factors_across if not np.isnan(f)]
                f_range = max(fc) - min(fc) if fc else 999
                shift = sr['shift']
                if shift > 1.5 and f_range < 0.1:
                    grade = 'A'
                elif shift > 0.5 and f_range < 0.3:
                    grade = 'B'
                else:
                    grade = 'C'
                rows.append({
                    '污染物': pol, '污染源': src,
                    '先验μ': DEFAULT_PRIORS.get(src, {'mu': 1.0})['mu'],
                    '后验MAP': sr['f_map'],
                    'shift': shift, '因子范围': f_range, '评级': grade,
                })
        pd.DataFrame(rows).to_excel(writer, sheet_name='可靠性评级', index=False)

    rpt(f"✓ Excel已保存: {excel_file.name}")
except Exception as e:
    rpt(f"  Excel保存出错: {e}")

rpt(f"\n{'=' * 100}")
rpt(f"敏感性分析完成")
rpt(f"{'=' * 100}")
