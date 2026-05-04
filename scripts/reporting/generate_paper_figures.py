#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文图表生成脚本（图4-图8）
基于排放清单与水质监测的流域水污染全链条定量分析——以南川河流域为例

Generates 5 publication-quality figures:
  fig4 - Bayesian correction factor heatmap
  fig5 - Half-distance decay bar chart
  fig6 - Emission vs effective contribution stacked bars
  fig7 - Monthly load distribution + data completeness
  fig8 - Monte Carlo distribution (2x2 grid)
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import numpy as np
import os

# ============================================================
# 全局设置 (from generate_figures.py)
# ============================================================
plt.rcParams.update({
    'font.sans-serif': ['Microsoft YaHei', 'SimHei'],
    'axes.unicode_minus': False,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.2,
    'axes.linewidth': 0.8,
    'axes.labelsize': 11,
    'axes.titlesize': 13,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9,
    'font.size': 10,
})

OUTPUT_DIR = r'D:\shanxi\output\figures'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================
# 颜色方案
# ============================================================
POLLUTANT_COLORS = {
    'COD': '#D62728', 'NH3-N': '#1F77B4',
    'TN': '#2CA02C', 'TP': '#FF7F0E',
}

SOURCE_COLORS = {
    '集中式设施': '#7B1FA2', '工业源': '#1565C0',
    '农村生活': '#E8836B', '城市面源': '#607D8B',
    '规模畜禽': '#C62828', '城镇散排': '#F9A825',
    '农业种植': '#558B2F', '畜禽散养': '#A1887F',
    '水产养殖': '#4FC3F7',
}

ALL_SOURCES = ['集中式设施', '工业源', '农村生活', '城市面源',
               '规模畜禽', '城镇散排', '农业种植', '畜禽散养', '水产养殖']


# ============================================================
# 图4: 贝叶斯修正因子热力图 (表12)
# ============================================================
def plot_fig4():
    sources = [
        '面-农村生活', '面-农业面源', '畜禽散养', '面-水产养殖',
        '面-城市面源', '面-城镇散排', '规模畜禽养殖', '点-工业源', '点-集中式设施',
    ]
    pollutants = ['COD', 'NH3-N', 'TN', 'TP']

    # Correction factors from Table 12 (NaN = not applicable)
    factors = np.array([
        [0.507, 0.911, 1.003, 0.421],   # 农村生活
        [np.nan, 0.995, 1.003, 0.863],   # 农业面源
        [0.975, 0.993, 1.000, 0.942],    # 畜禽散养
        [0.998, np.nan, np.nan, np.nan],  # 水产养殖
        [0.407, 0.988, 1.004, 0.397],    # 城市面源
        [0.891, 0.861, 1.003, 0.659],    # 城镇散排
        [0.100, 0.666, 0.809, 0.100],    # 规模畜禽
        [0.755, 0.877, np.nan, 0.100],   # 工业源
        [0.558, 0.842, 0.941, 0.100],    # 集中式设施
    ])

    # Z-scores from Table 12
    zscores = np.array([
        [1.64, 0.30, 0.01, 1.93],
        [np.nan, 0.01, 0.01, 0.34],
        [0.06, 0.02, 0.00, 0.14],
        [0.00, np.nan, np.nan, np.nan],
        [1.48, 0.03, 0.01, 1.51],
        [0.22, 0.28, 0.01, 0.68],
        [2.33, 0.45, 0.64, 2.33],
        [0.48, 0.08, np.nan, 2.67],
        [1.14, 0.19, 0.20, 2.67],
    ])

    fig, ax = plt.subplots(figsize=(10, 8))

    # Masked array for NaN handling
    masked = np.ma.masked_invalid(factors)

    # Diverging colormap centered at 1.0
    norm = mcolors.TwoSlopeNorm(vmin=0.0, vcenter=1.0, vmax=1.5)
    cmap = plt.cm.RdYlGn.copy()
    cmap.set_bad(color='#F0F0F0')

    im = ax.imshow(masked, cmap=cmap, norm=norm, aspect='auto')

    # Annotate each cell
    for i in range(len(sources)):
        for j in range(len(pollutants)):
            f_val = factors[i, j]
            z_val = zscores[i, j]
            if np.isnan(f_val):
                ax.text(j, i, '\u2014', ha='center', va='center',
                        fontsize=11, color='#999')
                continue

            txt_color = 'white' if f_val < 0.3 else '#222'
            weight = 'bold' if z_val > 2 else 'normal'
            ax.text(j, i - 0.13, f'{f_val:.3f}', ha='center', va='center',
                    fontsize=11, color=txt_color, fontweight=weight)

            # Z-score sub-label
            if z_val > 2:
                ax.text(j, i + 0.23, f'z={z_val:.2f} \u2605', ha='center',
                        va='center', fontsize=8, color='#B71C1C',
                        fontweight='bold')
            elif z_val > 1.5:
                ax.text(j, i + 0.23, f'z={z_val:.2f}', ha='center',
                        va='center', fontsize=7.5, color='#E65100')

    ax.set_xticks(range(len(pollutants)))
    ax.set_xticklabels(pollutants, fontsize=12, fontweight='bold')
    ax.xaxis.set_ticks_position('top')
    ax.xaxis.set_label_position('top')
    ax.set_yticks(range(len(sources)))
    ax.set_yticklabels(sources, fontsize=10)

    # White grid lines between cells
    for i in range(len(sources) + 1):
        ax.axhline(y=i - 0.5, color='white', linewidth=2)
    for j in range(len(pollutants) + 1):
        ax.axvline(x=j - 0.5, color='white', linewidth=2)

    cbar = fig.colorbar(im, ax=ax, shrink=0.75, pad=0.03)
    cbar.set_label('\u4fee\u6b63\u56e0\u5b50 f', fontsize=11)
    # Mark f=1 on colorbar
    cbar.ax.axhline(y=1.0, color='black', linewidth=1.5, linestyle='--')

    ax.set_title('\u8d1d\u53f6\u65af\u4fee\u6b63\u56e0\u5b50\u70ed\u529b\u56fe'
                 '\uff08\u2605 \u6807\u8bb0 z > 2 \u5f02\u5e38\u6e90\uff09',
                 fontsize=13, fontweight='bold', pad=15)

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig4_bayesian_heatmap.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig4_bayesian_heatmap.png')


# ============================================================
# 图5: 半衰距离水平柱状图 (表15)
# ============================================================
def plot_fig5():
    fig, ax = plt.subplots(figsize=(12, 5.5))

    pollutants = ['TN', 'NH3-N', 'COD', 'TP']
    half_dist = [11.9, 9.3, 4.8, 3.1]
    k_values = [0.0582, 0.0742, 0.1430, 0.2205]
    mechanisms = [
        '\u4fdd\u5b88\u6027\u5f3a\uff0c\u53cd\u785d\u5316\u53d7\u9650\n'
        '\u5404\u5f62\u6001\u6c2e\u76f8\u4e92\u8f6c\u5316',
        '\u785d\u5316\u6d88\u8017\uff0c\u901f\u7387\u9002\u4e2d\n'
        'NH4+ \u2192 NO3- \u8f6c\u5316',
        '\u5fae\u751f\u7269\u964d\u89e3\u6d3b\u8dc3\n'
        '\u6cb3\u9053\u81ea\u51c0\u80fd\u529b\u5f3a',
        '\u9897\u7c92\u6001\u6c89\u964d\u8fc5\u901f\n'
        '\u6ce5\u6c99\u5438\u9644\u663e\u8457',
    ]
    colors = ['#2CA02C', '#1F77B4', '#D62728', '#FF7F0E']

    y_pos = np.arange(len(pollutants))
    ax.barh(y_pos, half_dist, height=0.52, color=colors,
            edgecolor='white', linewidth=1.2, alpha=0.88)

    for i, (d, k, m) in enumerate(zip(half_dist, k_values, mechanisms)):
        ax.text(d + 0.25, i - 0.08, f'{d} km',
                va='center', fontsize=14, fontweight='bold', color='#333')
        ax.text(d + 0.25, i + 0.22, f'k = {k} /km',
                va='center', fontsize=9.5, color='#777')
        ax.text(15.5, i, m, va='center', ha='center', fontsize=9, color='#444',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#FAFAFA',
                          edgecolor='#CCCCCC'))

    ax.set_yticks(y_pos)
    ax.set_yticklabels(pollutants, fontsize=14, fontweight='bold')
    ax.set_xlabel('\u534a\u8870\u8ddd\u79bb (km)', fontsize=12)
    ax.set_xlim(0, 20)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.25, ls=':')

    ax.annotate('', xy=(12.5, -0.75), xytext=(0.5, -0.75),
                arrowprops=dict(arrowstyle='->', color='#999', lw=1.5))
    ax.text(6.5, -1.0,
            '\u2190 \u8870\u51cf\u8d8a\u5feb'
            '                          '
            '\u8870\u51cf\u8d8a\u6162 \u2192',
            ha='center', fontsize=10, color='#888', style='italic')

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig5_half_distances.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig5_half_distances.png')


# ============================================================
# 图6: 排放量 vs 有效贡献 堆叠柱状图 (表17)
# ============================================================
def plot_fig6():
    # Emission percentages (GIS data)
    emit = {
        'COD': {'规模畜禽': 56.6, '农村生活': 15.9, '城市面源': 9.2,
                '集中式设施': 6.8, '城镇散排': 5.1, '工业源': 4.5,
                '畜禽散养': 1.8, '水产养殖': 0.1, '农业种植': 0.0},
        'NH3-N': {'规模畜禽': 40.3, '城镇散排': 30.1, '农村生活': 13.4,
                       '集中式设施': 5.4, '农业种植': 3.9, '工业源': 3.4,
                       '畜禽散养': 2.5, '城市面源': 0.9, '水产养殖': 0.1},
        'TN': {'集中式设施': 37.1, '规模畜禽': 26.5, '农业种植': 21.8,
               '城镇散排': 6.4, '农村生活': 4.7, '城市面源': 2.7,
               '畜禽散养': 0.9, '水产养殖': 0.1, '工业源': 0.0},
        'TP': {'规模畜禽': 65.1, '工业源': 7.4, '农业种植': 6.9,
               '集中式设施': 6.3, '农村生活': 5.5, '城镇散排': 4.7,
               '城市面源': 2.8, '畜禽散养': 1.3, '水产养殖': 0.1},
    }

    # Effective contribution percentages (spatial decay model)
    effect = {
        'COD': {'集中式设施': 26.8, '工业源': 23.6, '农村生活': 22.2,
                '城市面源': 15.1, '规模畜禽': 10.3, '城镇散排': 1.9,
                '水产养殖': 0.0, '畜禽散养': 0.0, '农业种植': 0.0},
        'NH3-N': {'农村生活': 27.6, '集中式设施': 25.1, '规模畜禽': 17.3,
                       '城镇散排': 16.8, '工业源': 10.1, '城市面源': 2.1,
                       '农业种植': 0.8, '畜禽散养': 0.1, '水产养殖': 0.0},
        'TN': {'集中式设施': 81.0, '规模畜禽': 6.8, '农村生活': 4.9,
               '城市面源': 3.3, '农业种植': 2.2, '城镇散排': 1.8,
               '畜禽散养': 0.1, '水产养殖': 0.0, '工业源': 0.0},
        'TP': {'集中式设施': 46.2, '工业源': 21.1, '农村生活': 11.5,
               '规模畜禽': 10.5, '城市面源': 6.6, '城镇散排': 2.5,
               '农业种植': 1.6, '畜禽散养': 0.0, '水产养殖': 0.0},
    }

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    poll_list = ['COD', 'NH3-N', 'TN', 'TP']

    for idx, poll in enumerate(poll_list):
        ax = axes[idx // 2][idx % 2]
        em = emit[poll]
        ef = effect[poll]

        for bar_idx, (label, data_dict) in enumerate(
                [('\u6392\u653e\u91cf\u5360\u6bd4', em),
                 ('\u6709\u6548\u8d21\u732e\u5360\u6bd4', ef)]):
            left = 0
            for src in ALL_SOURCES:
                val = data_dict.get(src, 0)
                if val > 0.05:
                    ax.barh(bar_idx, val, left=left, height=0.55,
                            color=SOURCE_COLORS[src], edgecolor='white', lw=0.6)
                    if val >= 6:
                        ax.text(left + val / 2, bar_idx,
                                f'{src}\n{val:.1f}%',
                                ha='center', va='center', fontsize=7.5,
                                color='white' if val >= 12 else '#222',
                                fontweight='bold' if val >= 12 else 'normal',
                                linespacing=1.15)
                    elif val >= 3:
                        ax.text(left + val / 2, bar_idx,
                                f'{val:.1f}%',
                                ha='center', va='center', fontsize=7,
                                color='#333')
                    left += val

        ax.set_yticks([0, 1])
        ax.set_yticklabels(['\u6392\u653e\u91cf\n\u5360\u6bd4',
                            '\u6709\u6548\u8d21\u732e\n\u5360\u6bd4'],
                           fontsize=10.5)
        ax.set_xlim(0, 103)
        ax.set_xlabel('\u5360\u6bd4 (%)', fontsize=10)
        ax.set_title(f'({chr(97 + idx)}) {poll}', fontsize=13,
                     fontweight='bold', loc='left')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=0.15, ls=':')

    legend_patches = [mpatches.Patch(facecolor=SOURCE_COLORS[s],
                                     edgecolor='white', label=s)
                      for s in ALL_SOURCES]
    fig.legend(handles=legend_patches, loc='lower center', ncol=5,
               fontsize=10, framealpha=0.9,
               bbox_to_anchor=(0.5, -0.01))

    plt.tight_layout(rect=[0, 0.055, 1, 0.98], h_pad=2.5, w_pad=2.5)
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig6_contribution_comparison.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig6_contribution_comparison.png')


# ============================================================
# 图7: 月度负荷分布 + 数据完整率 (表7 + 表3)
# ============================================================
def plot_fig7():
    months = ['1\u6708', '2\u6708', '3\u6708', '4\u6708',
              '5\u6708', '6\u6708', '7\u6708', '8\u6708',
              '9\u6708', '10\u6708', '11\u6708', '12\u6708']

    # Table 7: monthly loads (tons)
    cod  = [6.18, 3.54, 4.12, 30.68, 34.00, 16.58,
            2.40, 0.94, 3.39,  0.65,  0.86,  8.53]
    nh3n = [0.25, 0.28, 0.12, 0.60, 1.43, 0.58,
            0.22, 0.03, 0.10, 0.02, 0.02, 0.23]
    tn   = [3.55, 2.89, 2.40, 13.86, 11.44, 8.63,
            0.56, 0.28, 0.94,  0.17,  0.19, 4.46]
    tp   = [0.051, 0.015, 0.015, 0.142, 0.173, 0.051,
            0.019, 0.009, 0.015, 0.006, 0.006, 0.069]

    # Table 3: completeness (%)
    completeness = [100.0, 99.9, 96.8, 96.7, 97.3, 96.1,
                    62.8, 28.1, 27.1, 18.4, 9.3, 81.5]

    fig, ax1 = plt.subplots(figsize=(14, 7))

    x = np.arange(12)
    w = 0.18

    # Scale NH3-N ×10 and TP ×100 so all pollutants are visible together
    ax1.bar(x - 1.5 * w, cod, w, label='COD (t)',
            color='#D62728', alpha=0.85, edgecolor='white', lw=0.8)
    ax1.bar(x - 0.5 * w, tn, w, label='TN (t)',
            color='#2CA02C', alpha=0.85, edgecolor='white', lw=0.8)
    ax1.bar(x + 0.5 * w, [v * 10 for v in nh3n], w,
            label='NH3-N (t, \u00d710)',
            color='#1F77B4', alpha=0.85, edgecolor='white', lw=0.8)
    ax1.bar(x + 1.5 * w, [v * 100 for v in tp], w,
            label='TP (t, \u00d7100)',
            color='#FF7F0E', alpha=0.85, edgecolor='white', lw=0.8)

    ax1.set_xlabel('\u6708\u4efd', fontsize=12)
    ax1.set_ylabel('\u8d1f\u8377\u91cf\uff08\u5428\uff1b'
                   'NH3-N \u00d710, TP \u00d7100\uff09', fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(months, fontsize=10)
    ax1.spines['top'].set_visible(False)
    ax1.grid(axis='y', alpha=0.2, ls=':')
    ax1.legend(loc='upper left', fontsize=9.5, framealpha=0.85)

    # Secondary axis: data completeness
    ax2 = ax1.twinx()
    ax2.plot(x, completeness, '--o', markersize=6, linewidth=2,
             label='\u6570\u636e\u5b8c\u6574\u7387 (%)', color='#555',
             zorder=5)
    ax2.set_ylabel('\u6570\u636e\u5b8c\u6574\u7387 (%)', fontsize=11,
                   color='#555')
    ax2.set_ylim(0, 115)
    ax2.tick_params(axis='y', colors='#555')
    ax2.spines['top'].set_visible(False)
    ax2.legend(loc='upper right', fontsize=9.5, framealpha=0.85)

    # Shade low-completeness months
    for i, c in enumerate(completeness):
        if c < 70:
            ax1.axvspan(i - 0.45, i + 0.45, alpha=0.08, color='red', zorder=0)

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig7_monthly_loads.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig7_monthly_loads.png')


# ============================================================
# 图8: 蒙特卡洛模拟分布图 (表13, 10000次)
# ============================================================
def plot_fig8():
    np.random.seed(42)

    # Parameters from Table 13
    mc_params = {
        'COD':    {'mean': 465.38, 'std': 82.74,
                   'q5': 337.79, 'q95': 610.96,
                   'monitor': 164.26, 'p_gt': 100.0},
        'NH3-N': {'mean': 6.84, 'std': 1.18,
                       'q5': 4.98, 'q95': 8.90,
                       'monitor': 5.73, 'p_gt': 82.4},
        'TN':     {'mean': 68.76, 'std': 17.74,
                   'q5': 42.94, 'q95': 100.64,
                   'monitor': 72.49, 'p_gt': 39.1},
        'TP':     {'mean': 5.34, 'std': 1.11,
                   'q5': 3.67, 'q95': 7.30,
                   'monitor': 0.84, 'p_gt': 100.0},
    }

    poll_colors = {'COD': '#D62728', 'NH3-N': '#1F77B4',
                   'TN': '#2CA02C', 'TP': '#FF7F0E'}

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    for idx, (poll, p) in enumerate(mc_params.items()):
        ax = axes[idx // 2][idx % 2]
        clr = poll_colors[poll]

        # Generate 10,000 samples matching reported mean & std
        samples = np.random.normal(p['mean'], p['std'], 10000)

        ax.hist(samples, bins=60, color=clr, alpha=0.7,
                edgecolor='white', linewidth=0.5, density=True)

        # Monitored value
        ax.axvline(x=p['monitor'], color='#222', linewidth=2.5, linestyle='-',
                   label=f'\u76d1\u6d4b\u503c {p["monitor"]:.2f} t')

        # 90% CI bounds
        ax.axvline(x=p['q5'], color='#888', linewidth=1.2, linestyle='--',
                   label=f'5% = {p["q5"]:.2f} t')
        ax.axvline(x=p['q95'], color='#888', linewidth=1.2, linestyle=':',
                   label=f'95% = {p["q95"]:.2f} t')

        # Shade 90% CI
        ax.axvspan(p['q5'], p['q95'], alpha=0.10, color=clr)

        # Text box with stats
        ax.text(0.97, 0.95,
                f'P(\u5165\u6cb3\u91cf>\u76d1\u6d4b\u503c) = {p["p_gt"]:.1f}%\n'
                f'\u5747\u503c = {p["mean"]:.2f} t\n'
                f'90% CI: [{p["q5"]:.2f}, {p["q95"]:.2f}]',
                transform=ax.transAxes, fontsize=9,
                va='top', ha='right',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                          edgecolor='#CCC', alpha=0.9))

        ax.set_xlabel('\u5165\u6cb3\u603b\u91cf\uff08\u5428\uff09', fontsize=10)
        ax.set_ylabel('\u6982\u7387\u5bc6\u5ea6', fontsize=10)
        ax.set_title(f'({chr(97 + idx)}) {poll}', fontsize=13,
                     fontweight='bold', loc='left')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.legend(fontsize=8.5, framealpha=0.85,
                  loc='upper left' if poll != 'TN' else 'upper right')

    plt.tight_layout(h_pad=2.5, w_pad=2.5)
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig8_monte_carlo.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig8_monte_carlo.png')


# ============================================================
# 主函数
# ============================================================
if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    funcs = [
        ('\u56fe4 \u8d1d\u53f6\u65af\u4fee\u6b63\u56e0\u5b50\u70ed\u529b\u56fe',
         plot_fig4),
        ('\u56fe5 \u534a\u8870\u8ddd\u79bb', plot_fig5),
        ('\u56fe6 \u6392\u653evs\u6709\u6548\u8d21\u732e', plot_fig6),
        ('\u56fe7 \u6708\u5ea6\u8d1f\u8377\u5206\u5e03', plot_fig7),
        ('\u56fe8 \u8499\u7279\u5361\u6d1b\u5206\u5e03', plot_fig8),
    ]

    success = 0
    for name, func in funcs:
        try:
            func()
            success += 1
        except Exception as e:
            print(f'[FAIL] {name}: {e}')
            import traceback
            traceback.print_exc()

    print(f'\n===== Done: {success}/{len(funcs)} figures =====')
    print(f'Output: {OUTPUT_DIR}')
