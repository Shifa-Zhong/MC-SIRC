#!/usr/bin/env python3
"""
贝叶斯MCMC完整后验分布分析 (修复硬伤3-方案C)

使用emcee进行MCMC采样, 替代MAP点估计, 提供:
  1. 每个修正因子的完整后验边际分布
  2. 参数间相关性分析 (corner plot / 相关矩阵)
  3. 后验不确定性真实量化 (不依赖Laplace近似)
  4. 可识别性诊断: 哪些参数在后验中强相关(tradeoff)

注意: 在1方程9未知数的欠定系统中, MCMC会显示参数间的强相关。
      配合月度约束(v3模型)使用效果更佳。

依赖: pip install emcee corner (可选)
输出: output/reports/贝叶斯MCMC报告.txt
      output/figures/mcmc_*.png
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# ── 路径 ──
ROOT = Path(__file__).resolve().parent
while not (ROOT / 'data').is_dir() and ROOT != ROOT.parent:
    ROOT = ROOT.parent

output_dir = ROOT / 'output'
report_file = output_dir / 'reports' / '贝叶斯MCMC报告.txt'
fig_dir = output_dir / 'figures'
for d in [output_dir / 'reports', fig_dir]:
    d.mkdir(parents=True, exist_ok=True)

report = []
def rpt(s=''):
    report.append(s)
    print(s)

# ============================================================
# 数据定义
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

DEFAULT_PRIORS = {
    '面-农村生活污染源':      {'mu': 1.0, 'sigma': 0.3},
    '面-农业面源':            {'mu': 1.0, 'sigma': 0.4},
    '畜禽散养':               {'mu': 1.0, 'sigma': 0.4},
    '面-水产养殖':            {'mu': 1.0, 'sigma': 0.3},
    '面-城市面源':            {'mu': 1.0, 'sigma': 0.4},
    '面-城镇散排':            {'mu': 1.0, 'sigma': 0.5},
    '规模畜禽养殖':           {'mu': 0.8, 'sigma': 0.3},
    '点-工业源':              {'mu': 0.7, 'sigma': 0.4},
    '点-集中式污染治理设施':  {'mu': 0.9, 'sigma': 0.3},
}

# ============================================================
# MCMC 核心
# ============================================================

def log_posterior(theta, source_names, emissions_per_1000, monitor_value,
                  prior_mus, prior_sigmas, sigma_obs):
    """
    对数后验概率

    theta: [f_1, ..., f_n, u]
      f_i: 第i个源的修正因子
      u:   未知源 (吨)
    """
    n = len(source_names)
    factors = theta[:n]
    unknown = theta[n]

    # 边界检查
    if unknown < 0:
        return -np.inf
    for f in factors:
        if f < 0.05 or f > 2.5:
            return -np.inf

    # 模型预测
    predicted = np.dot(emissions_per_1000, factors) + unknown

    # 对数似然
    ll = -0.5 * ((monitor_value - predicted) / sigma_obs) ** 2

    # 对数先验 (截断正态)
    lp = 0
    for i in range(n):
        lp += -0.5 * ((factors[i] - prior_mus[i]) / prior_sigmas[i]) ** 2

    # 未知源先验 (Gamma)
    alpha_g = 2
    beta_g = 10 / monitor_value
    if unknown > 0:
        lp += (alpha_g - 1) * np.log(unknown) - beta_g * unknown
    else:
        lp += (alpha_g - 1) * np.log(1e-6) - beta_g * 1e-6

    return ll + lp


def run_mcmc(pollutant, n_walkers=32, n_steps=5000, n_burn=1000):
    """对单个污染物运行MCMC"""
    try:
        import emcee
    except ImportError:
        rpt(f"  ✗ emcee未安装。请运行: pip install emcee")
        return None

    source_data = SOURCE_DATA[pollutant]
    monitor_value = MONITOR_VALUES[pollutant]
    sigma_obs = monitor_value * 0.10

    active = {k: v for k, v in source_data.items() if v > 0}
    source_names = list(active.keys())
    n_sources = len(source_names)
    ndim = n_sources + 1  # +1 for unknown source

    emissions = np.array([active[s] / 1000 for s in source_names])
    prior_mus = np.array([DEFAULT_PRIORS.get(s, {'mu': 1.0})['mu'] for s in source_names])
    prior_sigmas = np.array([DEFAULT_PRIORS.get(s, {'sigma': 0.3})['sigma'] for s in source_names])

    args = (source_names, emissions, monitor_value, prior_mus, prior_sigmas, sigma_obs)

    # 初始化walkers (在先验附近)
    p0 = np.zeros((n_walkers, ndim))
    for i in range(n_walkers):
        p0[i, :n_sources] = prior_mus + 0.1 * np.random.randn(n_sources) * prior_sigmas
        p0[i, :n_sources] = np.clip(p0[i, :n_sources], 0.1, 2.0)
        p0[i, n_sources] = monitor_value * (0.05 + 0.1 * np.random.rand())

    # 运行MCMC
    sampler = emcee.EnsembleSampler(n_walkers, ndim, log_posterior, args=args)
    rpt(f"    运行MCMC: {n_walkers} walkers × {n_steps} steps ...")

    sampler.run_mcmc(p0, n_steps, progress=False)

    # 丢弃burn-in
    chain = sampler.get_chain(discard=n_burn, flat=True)
    rpt(f"    有效样本: {chain.shape[0]} (丢弃burn-in {n_burn})")

    # 收敛诊断: 自相关时间
    try:
        tau = sampler.get_autocorr_time(quiet=True)
        rpt(f"    自相关时间: {np.mean(tau):.1f} (平均), 有效样本比={n_steps/np.mean(tau):.0f}")
    except Exception:
        tau = None
        rpt(f"    自相关时间: 无法估计 (链可能不够长)")

    # 后验统计
    results = {
        'source_names': source_names,
        'chain': chain,
        'n_sources': n_sources,
        'ndim': ndim,
        'tau': tau,
    }

    stats = {}
    rpt(f"\n    {'参数':<25s}  {'均值':>8s}  {'中位数':>8s}  {'std':>8s}  {'95%CI':>20s}")
    rpt("    " + "-" * 75)

    for i, name in enumerate(source_names):
        samples = chain[:, i]
        mean = np.mean(samples)
        median = np.median(samples)
        std = np.std(samples)
        ci_low = np.percentile(samples, 2.5)
        ci_high = np.percentile(samples, 97.5)
        stats[name] = {
            'mean': mean, 'median': median, 'std': std,
            'ci_low': ci_low, 'ci_high': ci_high,
        }
        rpt(f"    {name:<25s}  {mean:>8.3f}  {median:>8.3f}  {std:>8.3f}  [{ci_low:.3f}, {ci_high:.3f}]")

    # 未知源
    u_samples = chain[:, n_sources]
    u_mean = np.mean(u_samples)
    u_median = np.median(u_samples)
    u_std = np.std(u_samples)
    u_ci = (np.percentile(u_samples, 2.5), np.percentile(u_samples, 97.5))
    stats['未知源'] = {
        'mean': u_mean, 'median': u_median, 'std': u_std,
        'ci_low': u_ci[0], 'ci_high': u_ci[1],
    }
    rpt(f"    {'未知源(吨)':<25s}  {u_mean:>8.3f}  {u_median:>8.3f}  {u_std:>8.3f}  "
        f"[{u_ci[0]:.3f}, {u_ci[1]:.3f}]")

    results['stats'] = stats

    # 参数间相关矩阵
    param_names = source_names + ['未知源']
    corr = np.corrcoef(chain.T)
    results['corr'] = corr
    results['param_names'] = param_names

    rpt(f"\n    参数间强相关对 (|r| > 0.3):")
    found_corr = False
    for i in range(ndim):
        for j in range(i + 1, ndim):
            r = corr[i, j]
            if abs(r) > 0.3:
                rpt(f"      {param_names[i]} ↔ {param_names[j]}: r = {r:+.3f}")
                found_corr = True
    if not found_corr:
        rpt(f"      无强相关对")

    return results


# ============================================================
# 主程序
# ============================================================

rpt("=" * 100)
rpt("贝叶斯MCMC完整后验分布分析")
rpt("=" * 100)

rpt(f"""
方法: emcee Ensemble Sampler (Foreman-Mackey et al. 2013)
设置: 32 walkers, 5000 steps, burn-in=1000
先验: 与MAP分析一致 (DEFAULT_PRIORS)
似然: N(监测值; 预测值, σ²), σ = 10% × 监测值

注意: 当前系统严重欠定(1方程 vs 7-9参数), MCMC会忠实反映这种
      不确定性——后验分布可能很宽, 参数间可能存在强负相关(tradeoff)。
      这本身就是重要信息: 它说明了哪些参数是可识别的, 哪些不是。
""")

all_results = {}

for pol in ['COD', '氨氮', '总氮', '总磷']:
    rpt(f"\n{'=' * 80}")
    rpt(f"  {pol}")
    rpt(f"{'=' * 80}")

    result = run_mcmc(pol)
    if result:
        all_results[pol] = result

# ============================================================
# 可识别性分析
# ============================================================
if all_results:
    rpt(f"\n\n{'=' * 100}")
    rpt(f"可识别性综合分析")
    rpt("=" * 100)

    rpt(f"\n  判据: 后验std / 先验σ")
    rpt(f"    比值 < 0.5: 参数被数据约束 (可识别)")
    rpt(f"    比值 0.5-0.9: 部分约束")
    rpt(f"    比值 ≈ 1.0: 未被约束 (不可识别, 后验≈先验)")

    for pol in all_results:
        result = all_results[pol]
        stats = result['stats']
        source_names = result['source_names']

        rpt(f"\n  {pol}:")
        rpt(f"    {'参数':<25s}  {'先验σ':>8s}  {'后验std':>8s}  {'比值':>8s}  {'判断'}")
        rpt("    " + "-" * 65)

        for src in source_names:
            prior_sigma = DEFAULT_PRIORS.get(src, {'sigma': 0.3})['sigma']
            post_std = stats[src]['std']
            ratio = post_std / prior_sigma if prior_sigma > 0 else float('inf')

            if ratio < 0.5:
                judge = "可识别 ★"
            elif ratio < 0.9:
                judge = "部分约束"
            else:
                judge = "不可识别 ⚠"

            rpt(f"    {src:<25s}  {prior_sigma:>8.3f}  {post_std:>8.3f}  {ratio:>8.3f}  {judge}")

# ============================================================
# MAP vs MCMC 对比
# ============================================================
if all_results:
    rpt(f"\n\n{'=' * 100}")
    rpt(f"MAP vs MCMC 对比")
    rpt("=" * 100)
    rpt(f"\n  MAP给出点估计, MCMC给出分布。两者差异反映后验偏斜程度。")

    from scipy.optimize import minimize as sp_minimize

    for pol in all_results:
        result = all_results[pol]
        source_names = result['source_names']
        n_sources = result['n_sources']
        stats = result['stats']

        source_data = SOURCE_DATA[pol]
        monitor_value = MONITOR_VALUES[pol]
        active = {k: v for k, v in source_data.items() if v > 0}
        emissions = np.array([active[s] / 1000 for s in source_names])
        prior_mus = np.array([DEFAULT_PRIORS.get(s, {'mu': 1.0})['mu'] for s in source_names])
        prior_sigmas = np.array([DEFAULT_PRIORS.get(s, {'sigma': 0.3})['sigma'] for s in source_names])
        sigma_obs = monitor_value * 0.10

        # MAP (reuse log_posterior with negative sign)
        def neg_lp(theta):
            return -log_posterior(theta, source_names, emissions, monitor_value,
                                  prior_mus, prior_sigmas, sigma_obs)

        x0 = list(prior_mus) + [monitor_value * 0.1]
        bounds = [(0.1, 2.0)] * n_sources + [(0.001, monitor_value * 0.5)]
        map_result = sp_minimize(neg_lp, x0, method='L-BFGS-B', bounds=bounds)

        rpt(f"\n  {pol}:")
        rpt(f"    {'参数':<25s}  {'MAP':>8s}  {'MCMC均值':>10s}  {'MCMC中位':>10s}  {'差异':>8s}")
        rpt("    " + "-" * 65)

        for i, src in enumerate(source_names):
            map_val = map_result.x[i]
            mcmc_mean = stats[src]['mean']
            mcmc_med = stats[src]['median']
            diff = mcmc_mean - map_val
            rpt(f"    {src:<25s}  {map_val:>8.3f}  {mcmc_mean:>10.3f}  {mcmc_med:>10.3f}  {diff:>+7.3f}")

        map_u = map_result.x[n_sources]
        mcmc_u = stats['未知源']['mean']
        rpt(f"    {'未知源':<25s}  {map_u:>8.3f}  {mcmc_u:>10.3f}  {stats['未知源']['median']:>10.3f}  "
            f"{mcmc_u-map_u:>+7.3f}")

# ── 可视化 ──
if all_results:
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False

        for pol in all_results:
            result = all_results[pol]
            chain = result['chain']
            source_names = result['source_names']
            param_names = result['param_names']
            ndim = result['ndim']

            # 图1: 后验边际分布
            n_cols = min(4, ndim)
            n_rows = (ndim + n_cols - 1) // n_cols
            fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 3 * n_rows))
            axes_flat = axes.flatten() if ndim > 1 else [axes]

            for i in range(ndim):
                ax = axes_flat[i]
                samples = chain[:, i]
                ax.hist(samples, bins=50, density=True, alpha=0.7, color='steelblue')

                # 叠加先验
                if i < len(source_names):
                    p = DEFAULT_PRIORS.get(source_names[i], {'mu': 1.0, 'sigma': 0.3})
                    x_range = np.linspace(max(0.05, p['mu'] - 3*p['sigma']),
                                          min(2.5, p['mu'] + 3*p['sigma']), 200)
                    prior_pdf = np.exp(-0.5 * ((x_range - p['mu']) / p['sigma'])**2) / (p['sigma'] * np.sqrt(2*np.pi))
                    ax.plot(x_range, prior_pdf, 'r--', alpha=0.5, label='先验')

                name = param_names[i] if i < len(param_names) else f'θ_{i}'
                short = name.replace('面-', '').replace('点-', '')[:8]
                ax.set_title(short, fontsize=9)
                ax.axvline(np.mean(samples), color='red', linestyle='-', alpha=0.5)
                if i < len(source_names) and i == 0:
                    ax.legend(fontsize=7)

            for i in range(ndim, len(axes_flat)):
                axes_flat[i].set_visible(False)

            plt.suptitle(f'{pol} - MCMC后验分布 (蓝=后验, 红虚线=先验, 红线=均值)', fontsize=11)
            plt.tight_layout()
            plt.savefig(fig_dir / f'mcmc_posterior_{pol}.png', dpi=150, bbox_inches='tight')
            plt.close()

            # 图2: 相关矩阵热力图
            corr = result['corr']
            fig, ax = plt.subplots(figsize=(max(6, ndim * 0.8), max(5, ndim * 0.7)))
            short_names = [n.replace('面-', '').replace('点-', '')[:6] for n in param_names]
            im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1, aspect='equal')
            ax.set_xticks(range(ndim))
            ax.set_xticklabels(short_names, rotation=45, ha='right', fontsize=8)
            ax.set_yticks(range(ndim))
            ax.set_yticklabels(short_names, fontsize=8)
            for i in range(ndim):
                for j in range(ndim):
                    color = 'white' if abs(corr[i, j]) > 0.5 else 'black'
                    ax.text(j, i, f'{corr[i,j]:.2f}', ha='center', va='center',
                            fontsize=7, color=color)
            plt.colorbar(im, label='相关系数')
            ax.set_title(f'{pol} - 参数后验相关矩阵')
            plt.tight_layout()
            plt.savefig(fig_dir / f'mcmc_correlation_{pol}.png', dpi=150, bbox_inches='tight')
            plt.close()

        rpt(f"\n✓ MCMC图表已保存")

    except ImportError:
        rpt(f"  注: matplotlib不可用, 跳过图表")
    except Exception as e:
        rpt(f"  图表出错: {e}")

# ── 导出Excel ──
if all_results:
    excel_file = output_dir / 'results' / '贝叶斯MCMC结果.xlsx'
    try:
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            for pol in all_results:
                result = all_results[pol]
                stats = result['stats']
                rows = []
                for name, s in stats.items():
                    rows.append({
                        '参数': name, '均值': s['mean'], '中位数': s['median'],
                        '标准差': s['std'], '95%CI下限': s['ci_low'], '95%CI上限': s['ci_high'],
                    })
                pd.DataFrame(rows).to_excel(writer, sheet_name=f'{pol}', index=False)

            # 相关矩阵
            for pol in all_results:
                result = all_results[pol]
                corr = result['corr']
                names = result['param_names']
                short = [n.replace('面-', '').replace('点-', '')[:8] for n in names]
                df_corr = pd.DataFrame(corr, index=short, columns=short)
                df_corr.to_excel(writer, sheet_name=f'{pol}_相关矩阵')

        rpt(f"✓ Excel已保存: {excel_file.name}")
    except Exception as e:
        rpt(f"  Excel保存出错: {e}")

# ── 保存报告 ──
with open(report_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))
rpt(f"\n✓ 报告已保存: {report_file}")

rpt(f"\n{'=' * 100}")
rpt(f"MCMC分析完成")
rpt(f"{'=' * 100}")
