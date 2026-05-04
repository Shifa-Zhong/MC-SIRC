#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
论文图表生成脚本
基于排放清单与水质监测的流域水污染全链条定量分析——以南川河流域为例
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
import os

# ============================================================
# 全局设置
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

OUTPUT_DIR = r'D:\shanxi\docs\figures'
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
# 图2: 排放→入河→监测 全链条示意图
# ============================================================
def plot_fig2():
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis('off')

    # --- 三个主框 ---
    boxes = [
        (2.5, 7.0, '排 放 量\nEmission', '#E3F2FD', '#1565C0'),
        (8.0, 7.0, '入 河 量\nRiver Input', '#E8F5E9', '#2E7D32'),
        (13.5, 7.0, '监测负荷\nMonitoring', '#FFF3E0', '#E65100'),
    ]
    bw, bh = 3.4, 1.6
    for (cx, cy, label, fcolor, ecolor) in boxes:
        rect = FancyBboxPatch((cx - bw/2, cy - bh/2), bw, bh,
                              boxstyle="round,pad=0.2",
                              facecolor=fcolor, edgecolor=ecolor, linewidth=2.5)
        ax.add_patch(rect)
        ax.text(cx, cy, label, ha='center', va='center',
                fontsize=15, fontweight='bold', color=ecolor)

    # --- 两个大箭头 ---
    arrow_kw = dict(arrowstyle='->', lw=3, color='#555555',
                    connectionstyle='arc3,rad=0', mutation_scale=25)
    ax.annotate('', xy=(6.3, 7.0), xytext=(4.2, 7.0), arrowprops=arrow_kw)
    ax.annotate('', xy=(11.8, 7.0), xytext=(9.7, 7.0), arrowprops=arrow_kw)

    # 箭头标签
    ax.text(5.25, 7.65, '综合入河系数', ha='center', fontsize=12,
            fontweight='bold', color='#1565C0')
    ax.text(5.25, 7.3, '(0.34 ~ 0.53)', ha='center', fontsize=10, color='#555')
    ax.text(10.75, 7.65, '河道传输系数', ha='center', fontsize=12,
            fontweight='bold', color='#2E7D32')
    ax.text(10.75, 7.3, '(0.16 ~ 1.05)', ha='center', fontsize=10, color='#555')

    # --- 下方数据表格 ---
    pollutants = ['COD', 'NH3-N', 'TN', 'TP']
    emissions  = [1036.52, 19.95, 131.30, 13.96]
    inflows    = [463.89, 6.83, 69.12, 5.32]
    monitors   = [164.26, 5.73, 72.49, 0.84]
    coeff1     = [0.448, 0.342, 0.526, 0.381]
    coeff2     = [0.354, 0.839, 1.049, 0.158]
    overall    = [0.158, 0.287, 0.552, 0.060]
    colors     = ['#D62728', '#1F77B4', '#2CA02C', '#FF7F0E']

    # 表头
    y_header = 5.2
    col_x = [1.0, 2.5, 5.25, 8.0, 10.75, 13.5]
    headers = ['污染物', '排放量\n(吨)', '×入河系数', '入河量\n(吨)', '×传输系数', '监测负荷\n(吨)']
    for x, h in zip(col_x, headers):
        ax.text(x, y_header, h, ha='center', va='center', fontsize=10.5,
                fontweight='bold', color='#333')

    # 分隔线
    ax.plot([0.3, 15.7], [y_header - 0.35, y_header - 0.35],
            '-', color='#BBBBBB', lw=1)

    # 数据行
    row_h = 0.85
    for i, (p, e, inf, m, c1, c2, ov, clr) in enumerate(
            zip(pollutants, emissions, inflows, monitors, coeff1, coeff2, overall, colors)):
        y = y_header - 0.7 - i * row_h

        # 彩色圆点 + 污染物名
        ax.plot(0.65, y, 'o', color=clr, markersize=10, zorder=5)
        ax.text(1.0, y, p, ha='center', va='center', fontsize=12,
                fontweight='bold', color=clr)

        ax.text(2.5, y, f'{e:.2f}', ha='center', va='center', fontsize=11, color='#333')
        ax.text(5.25, y, f'× {c1:.3f}', ha='center', va='center', fontsize=10.5,
                color='#1565C0', fontweight='bold')
        ax.text(8.0, y, f'{inf:.2f}', ha='center', va='center', fontsize=11, color='#333')
        ax.text(10.75, y, f'× {c2:.3f}', ha='center', va='center', fontsize=10.5,
                color='#2E7D32', fontweight='bold')
        ax.text(13.5, y, f'{m:.2f}', ha='center', va='center', fontsize=11, color='#333')

        # 箭头连接
        for (x1, x2) in [(3.5, 4.4), (6.0, 7.0), (9.0, 9.9), (11.6, 12.5)]:
            ax.annotate('', xy=(x2, y), xytext=(x1, y),
                        arrowprops=dict(arrowstyle='->', color='#AAAAAA', lw=1.2))

        # 行分隔
        if i < 3:
            ax.plot([0.3, 15.7], [y - row_h * 0.5, y - row_h * 0.5],
                    '-', color='#EEEEEE', lw=0.5)

    # 底部标注: 全链条效率
    y_bottom = y_header - 0.7 - 4 * row_h - 0.3
    ax.plot([0.3, 15.7], [y_bottom + 0.3, y_bottom + 0.3], '-', color='#BBBBBB', lw=1)
    ax.text(8.0, y_bottom - 0.1,
            '全链条传输效率（监测/排放）: COD 15.8%  |  NH3-N 28.7%  |  TN 55.2%  |  TP 6.0%',
            ha='center', va='center', fontsize=10.5, color='#666',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#F5F5F5',
                      edgecolor='#CCCCCC', alpha=0.9))

    fig.savefig(os.path.join(OUTPUT_DIR, 'fig2_fullchain.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig2_fullchain.png')


# ============================================================
# 图3: 贝叶斯优化修正因子
# ============================================================
def plot_fig3():
    data = {
        'COD': {
            'sources': ['农村生活', '畜禽散养', '水产养殖',
                        '城市面源', '城镇散排', '规模畜禽', '工业源', '集中式设施'],
            'factors': [0.507, 0.975, 0.998, 0.407, 0.891, 0.100, 0.755, 0.558],
            'priors':  [1.0,   1.0,   1.0,   1.0,   1.0,   0.8,   0.9,   0.9],
        },
        'NH3-N': {
            'sources': ['农村生活', '农业种植', '畜禽散养',
                        '城市面源', '城镇散排', '规模畜禽', '工业源', '集中式设施'],
            'factors': [0.911, 0.995, 0.993, 0.988, 0.861, 0.666, 0.877, 0.842],
            'priors':  [1.0,   1.0,   1.0,   1.0,   1.0,   0.8,   0.9,   0.9],
        },
        'TN': {
            'sources': ['农村生活', '农业种植', '畜禽散养',
                        '城市面源', '城镇散排', '规模畜禽', '集中式设施'],
            'factors': [1.003, 1.003, 1.000, 1.004, 1.003, 0.809, 0.941],
            'priors':  [1.0,   1.0,   1.0,   1.0,   1.0,   0.8,   0.9],
        },
        'TP': {
            'sources': ['农村生活', '农业种植', '畜禽散养',
                        '城市面源', '城镇散排', '规模畜禽', '工业源', '集中式设施'],
            'factors': [0.421, 0.863, 0.942, 0.397, 0.659, 0.100, 0.100, 0.100],
            'priors':  [1.0,   1.0,   1.0,   1.0,   1.0,   0.8,   0.9,   0.9],
        },
    }

    poll_color = {'COD': '#D62728', 'NH3-N': '#1F77B4',
                  'TN': '#2CA02C', 'TP': '#FF7F0E'}

    fig, axes = plt.subplots(2, 2, figsize=(15, 11))

    for idx, (poll, d) in enumerate(data.items()):
        ax = axes[idx // 2][idx % 2]
        sources = d['sources']
        factors = np.array(d['factors'])
        priors = np.array(d['priors'])
        n = len(sources)
        y_pos = np.arange(n)
        base_color = poll_color[poll]

        # 颜色区分: 异常(红)、较大偏差(橙)、正常(主色)
        bar_colors = []
        for f in factors:
            if f <= 0.15:
                bar_colors.append('#B71C1C')
            elif f < 0.5:
                bar_colors.append('#E57373')
            else:
                bar_colors.append(base_color)

        bars = ax.barh(y_pos, factors, height=0.6, color=bar_colors,
                       edgecolor='white', linewidth=0.8, alpha=0.88, zorder=3)

        # f=1 参考线
        ax.axvline(x=1.0, color='#444', lw=1.5, ls='--', alpha=0.5,
                   zorder=2, label='f = 1.0（无修正）')

        # 先验均值标记
        ax.scatter(priors, y_pos, marker='D', s=50, color='#333',
                   zorder=5, label='先验均值')

        # 数值标注
        for i, f in enumerate(factors):
            txt = f'{f:.3f}'
            if f <= 0.15:
                txt += ' (!)'
            offset = 0.03
            ax.text(f + offset, i, txt, va='center', fontsize=9,
                    color='#B71C1C' if f <= 0.15 else '#333',
                    fontweight='bold' if f <= 0.15 else 'normal')

        ax.set_yticks(y_pos)
        ax.set_yticklabels(sources, fontsize=10)
        ax.set_xlabel('修正因子 f', fontsize=10.5)
        ax.set_xlim(0, 1.4)
        ax.set_title(f'({chr(97 + idx)}) {poll}', fontsize=13,
                     fontweight='bold', loc='left')
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=0.25, ls=':', zorder=0)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        if idx == 0:
            ax.legend(loc='lower right', fontsize=9, framealpha=0.85)

    plt.tight_layout(h_pad=2.5, w_pad=2.5)
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig3_bayesian_factors.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig3_bayesian_factors.png')


# ============================================================
# 图4: 各污染物半衰距离
# ============================================================
def plot_fig4():
    fig, ax = plt.subplots(figsize=(12, 5.5))

    pollutants = ['TN', 'NH3-N', 'COD', 'TP']
    half_dist  = [11.9, 9.3, 4.8, 3.1]
    k_values   = [0.0582, 0.0742, 0.1430, 0.2205]
    mechanisms = [
        '保守性强，反硝化受限\n各形态氮相互转化',
        '硝化消耗，速率适中\nNH4->NO3 转化',
        '微生物降解活跃\n河道自净能力强',
        '颗粒态沉降迅速\n泥沙吸附显著',
    ]
    colors = ['#2CA02C', '#1F77B4', '#D62728', '#FF7F0E']

    y_pos = np.arange(len(pollutants))
    bars = ax.barh(y_pos, half_dist, height=0.52, color=colors,
                   edgecolor='white', linewidth=1.2, alpha=0.88)

    # 数值标注
    for i, (d, k, m) in enumerate(zip(half_dist, k_values, mechanisms)):
        # 半衰距离数值
        ax.text(d + 0.25, i - 0.08, f'{d} km',
                va='center', fontsize=14, fontweight='bold', color='#333')
        # k 值
        ax.text(d + 0.25, i + 0.22, f'k = {k} km-1',
                va='center', fontsize=9.5, color='#777')
        # 衰减机制（右侧卡片）
        ax.text(15.5, i, m, va='center', ha='center', fontsize=9, color='#444',
                bbox=dict(boxstyle='round,pad=0.4', facecolor='#FAFAFA',
                          edgecolor='#CCCCCC'))

    ax.set_yticks(y_pos)
    ax.set_yticklabels(pollutants, fontsize=14, fontweight='bold')
    ax.set_xlabel('半衰距离 (km)', fontsize=12)
    ax.set_xlim(0, 20)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.25, ls=':')

    # 底部方向标注
    ax.annotate('', xy=(12.5, -0.75), xytext=(0.5, -0.75),
                arrowprops=dict(arrowstyle='->', color='#999', lw=1.5))
    ax.text(6.5, -1.0, '← 衰减越快                          衰减越慢 →',
            ha='center', fontsize=10, color='#888', style='italic')

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig4_half_distances.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig4_half_distances.png')


# ============================================================
# 图5: 排放量 vs 有效贡献 对比
# ============================================================
def plot_fig5():
    # --- 数据 ---
    # 排放量占比 (%) — 基于 GIS 排放数据
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

    # 有效贡献占比 (%) — 空间衰减模型结果
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

        # 两行堆叠条
        for bar_idx, (label, data_dict) in enumerate(
                [('排放量占比', em), ('有效贡献占比', ef)]):
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
        ax.set_yticklabels(['排放量\n占比', '有效贡献\n占比'], fontsize=10.5)
        ax.set_xlim(0, 103)
        ax.set_xlabel('占比 (%)', fontsize=10)
        ax.set_title(f'({chr(97 + idx)}) {poll}', fontsize=13,
                     fontweight='bold', loc='left')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.invert_yaxis()
        ax.grid(axis='x', alpha=0.15, ls=':')

    # 公共图例
    legend_patches = [mpatches.Patch(facecolor=SOURCE_COLORS[s],
                                     edgecolor='white', label=s)
                      for s in ALL_SOURCES]
    fig.legend(handles=legend_patches, loc='lower center', ncol=5,
               fontsize=10, framealpha=0.9,
               bbox_to_anchor=(0.5, -0.01))

    plt.tight_layout(rect=[0, 0.055, 1, 0.98], h_pad=2.5, w_pad=2.5)
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig5_contribution_comparison.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig5_contribution_comparison.png')


# ============================================================
# 附加图: 数据修正效果对比
# ============================================================
def plot_correction_effect():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6),
                                   gridspec_kw={'width_ratios': [1, 3]})

    # --- 左图: TP修正效果(单独展示，因为量级差异大) ---
    cats = ['修正前\n原始监测', '修正后\n原始监测', '修正后\n补全监测']
    tp_vals = [69.48, 9.32, 6.34]
    tp_colors = ['#EF5350', '#42A5F5', '#66BB6A']

    bars = ax1.bar(range(3), tp_vals, color=tp_colors, width=0.6,
                   edgecolor='white', lw=1.2, alpha=0.88)
    for b, v in zip(bars, tp_vals):
        ax1.text(b.get_x() + b.get_width() / 2, v + 1.5,
                 f'{v:.2f}', ha='center', fontsize=11, fontweight='bold')
    ax1.axhline(y=1.0, color='#333', lw=1.2, ls='--', alpha=0.5)
    ax1.text(2.4, 1.5, '理想值=1', fontsize=8.5, color='#666')
    ax1.set_xticks(range(3))
    ax1.set_xticklabels(cats, fontsize=9.5)
    ax1.set_ylabel('入河量 / 监测负荷', fontsize=11)
    ax1.set_title('(a) 总磷修正效果', fontsize=12, fontweight='bold', loc='left')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.set_ylim(0, 80)

    # 标注箭头
    ax1.annotate('', xy=(1, 9.32), xytext=(0, 69.48),
                 arrowprops=dict(arrowstyle='->', color='#C62828', lw=2))
    ax1.text(0.5, 42, '↓ 86.6%', ha='center', fontsize=11,
             color='#C62828', fontweight='bold', rotation=-70)

    # --- 右图: 四种污染物比较 ---
    polls = ['COD', 'NH3-N', 'TN', 'TP']
    before = [3.92, 1.63, 1.34, 69.48]
    after_raw = [4.15, 1.75, 1.40, 9.32]
    after_comp = [2.82, 1.19, 0.95, 6.34]

    x = np.arange(4)
    w = 0.25

    b1 = ax2.bar(x - w, before, w, label='修正前（原始监测）',
                 color='#EF5350', alpha=0.85, edgecolor='white', lw=0.8)
    b2 = ax2.bar(x, after_raw, w, label='修正后（原始监测）',
                 color='#42A5F5', alpha=0.85, edgecolor='white', lw=0.8)
    b3 = ax2.bar(x + w, after_comp, w, label='修正后（补全监测）',
                 color='#66BB6A', alpha=0.85, edgecolor='white', lw=0.8)

    ax2.axhline(y=1.0, color='#333', lw=1.2, ls='--', alpha=0.5,
                label='理想值 (比值=1)')

    # 数值标注
    for bars_group in [b1, b2, b3]:
        for b in bars_group:
            h = b.get_height()
            label_txt = f'{h:.2f}'
            if h > 12:
                label_txt = f'{h:.1f}'
                ax2.text(b.get_x() + b.get_width() / 2, 11.5, label_txt,
                         ha='center', va='bottom', fontsize=8.5,
                         fontweight='bold', color='#C62828')
                # Broken bar indicator
                ax2.plot([b.get_x() + b.get_width() / 2 - 0.06,
                          b.get_x() + b.get_width() / 2 + 0.06],
                         [11.2, 11.2], color='#C62828', lw=2)
            else:
                ax2.text(b.get_x() + b.get_width() / 2, h + 0.15,
                         label_txt, ha='center', va='bottom', fontsize=8.5)

    ax2.set_xticks(x)
    ax2.set_xticklabels(polls, fontsize=13, fontweight='bold')
    ax2.set_ylabel('入河量 / 监测负荷', fontsize=11)
    ax2.set_title('(b) 各污染物修正效果对比（纵轴截断至12）',
                  fontsize=12, fontweight='bold', loc='left')
    ax2.set_ylim(0, 12)
    ax2.legend(fontsize=9.5, loc='upper right', framealpha=0.85)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(axis='y', alpha=0.2, ls=':')

    plt.tight_layout(w_pad=3)
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig_correction_effect.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig_correction_effect.png')


# ============================================================
# 附加图: 全链条瀑布图
# ============================================================
def plot_chain_waterfall():
    fig, axes = plt.subplots(1, 4, figsize=(16, 5.5), sharey=False)

    polls = ['COD', 'NH3-N', 'TN', 'TP']
    emissions = [1036.52, 19.95, 131.30, 13.96]
    inflows   = [463.89, 6.83, 69.12, 5.32]
    monitors  = [164.26, 5.73, 72.49, 0.84]
    colors    = ['#D62728', '#1F77B4', '#2CA02C', '#FF7F0E']

    for i, (ax, poll, em, inf, mon, clr) in enumerate(
            zip(axes, polls, emissions, inflows, monitors, colors)):

        stages = ['排放量', '入河量', '监测负荷']
        values = [em, inf, mon]

        # 柱状图
        x = [0, 1, 2]
        alphas = [0.45, 0.7, 1.0]
        for xi, (vi, ai) in enumerate(zip(values, alphas)):
            ax.bar(xi, vi, width=0.6, color=clr, alpha=ai,
                   edgecolor='white', lw=1.5)
        bars = ax.containers[0] if ax.containers else None

        # 连接线+降幅标注
        for j in range(2):
            mid_x = x[j] + 0.5
            ax.plot([x[j] + 0.3, x[j + 1] - 0.3],
                    [values[j], values[j + 1]],
                    '--', color='#888', lw=1.2)

            pct = (1 - values[j + 1] / values[j]) * 100
            if pct > 0:
                label = f'↓{pct:.0f}%'
            else:
                label = f'↑{abs(pct):.0f}%'
            mid_y = (values[j] + values[j + 1]) / 2
            ax.text(mid_x, mid_y, label, ha='center', va='center',
                    fontsize=9.5, color='#C62828' if pct > 0 else '#2E7D32',
                    fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                              edgecolor='#DDD', alpha=0.9))

        # 数值标注
        for xi, v in enumerate(values):
            fmt = f'{v:.2f}' if v >= 1 else f'{v:.3f}'
            ax.text(xi, v + max(values) * 0.03,
                    f'{fmt} t', ha='center', fontsize=9.5, fontweight='bold')

        ax.set_xticks(x)
        ax.set_xticklabels(stages, fontsize=10)
        ax.set_title(f'{poll}', fontsize=13, fontweight='bold', color=clr)
        ax.set_ylim(0, max(values) * 1.18)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.2, ls=':')
        if i == 0:
            ax.set_ylabel('负荷量（吨）', fontsize=11)

    plt.tight_layout(w_pad=1.5)
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig_chain_waterfall.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig_chain_waterfall.png')


# ============================================================
# 附加图: 控制单元有效贡献
# ============================================================
def plot_control_unit():
    fig, ax = plt.subplots(figsize=(12, 6))

    polls = ['COD', 'NH3-N', 'TN', 'TP']
    # 数据: [南川河交口, 枣林乡, 枝柯镇, 武家庄镇, 点源合计]
    data = {
        'COD':   [32.8, 5.4, 0.8, 0.2, 60.8],
        'NH3-N': [41.6, 3.9, 1.1, 0.8, 52.7],
        'TN':    [9.9,  1.3, 0.5, 0.4, 87.9],
        'TP':    [17.8, 4.1, 0.2, 0.0, 77.9],
    }

    cats = ['南川河交口镇\n(面源)', '枣林乡\n(面源)', '枝柯镇\n(面源)',
            '武家庄镇\n(面源)', '点源合计']
    cat_colors = ['#66BB6A', '#A5D6A7', '#C8E6C9', '#E8F5E9', '#1565C0']

    x = np.arange(len(polls))
    n_cats = len(cats)
    bar_width = 0.7

    # 堆叠柱状图
    bottoms = np.zeros(len(polls))
    bars_all = []
    for j, (cat, clr) in enumerate(zip(cats, cat_colors)):
        vals = [data[p][j] for p in polls]
        b = ax.bar(x, vals, bar_width, bottom=bottoms, color=clr,
                   edgecolor='white', lw=0.8, label=cat, alpha=0.88)
        bars_all.append(b)

        # 数值标注 (只标注 >= 3%)
        for k, v in enumerate(vals):
            if v >= 3:
                ax.text(x[k], bottoms[k] + v / 2,
                        f'{v:.1f}%', ha='center', va='center',
                        fontsize=9, fontweight='bold',
                        color='white' if clr == '#1565C0' else '#333')
        bottoms += np.array(vals)

    # 100% 参考线
    ax.axhline(y=100, color='#CCC', lw=0.8, ls='-')

    ax.set_xticks(x)
    ax.set_xticklabels(polls, fontsize=14, fontweight='bold')
    ax.set_ylabel('有效贡献占比 (%)', fontsize=12)
    ax.set_ylim(0, 108)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=10, loc='upper right', framealpha=0.85)
    ax.grid(axis='y', alpha=0.2, ls=':')

    # 面源/点源分界标注
    for k, p in enumerate(polls):
        face_total = sum(data[p][:4])
        point_total = data[p][4]
        ax.annotate(f'点源{point_total:.0f}%',
                    xy=(k, face_total + point_total / 2),
                    fontsize=8.5, ha='center', va='center',
                    color='white', fontweight='bold')

    plt.tight_layout()
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig_control_unit.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig_control_unit.png')


# ============================================================
# 附加图: 入河系数推算结果
# ============================================================
def plot_inflow_coefficients():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # 点源
    pt_sources = ['集中式设施', '工业源', '规模畜禽', '畜禽散养']
    pt_cod   = [1.000, 0.640, 0.309, 0.155]
    pt_nh3   = [1.000, 0.643, 0.309, 0.154]
    pt_tn    = [1.000, 0.000, 0.309, 0.155]
    pt_tp    = [1.000, 0.654, 0.309, 0.155]

    x = np.arange(len(pt_sources))
    w = 0.2
    ax1.bar(x - 1.5 * w, pt_cod, w, label='COD', color='#D62728', alpha=0.85, edgecolor='white')
    ax1.bar(x - 0.5 * w, pt_nh3, w, label='NH3-N', color='#1F77B4', alpha=0.85, edgecolor='white')
    ax1.bar(x + 0.5 * w, pt_tn, w, label='TN', color='#2CA02C', alpha=0.85, edgecolor='white')
    ax1.bar(x + 1.5 * w, pt_tp, w, label='TP', color='#FF7F0E', alpha=0.85, edgecolor='white')

    ax1.set_xticks(x)
    ax1.set_xticklabels(pt_sources, fontsize=10)
    ax1.set_ylabel('入河系数 (入河量/排放量)', fontsize=11)
    ax1.set_title('(a) 点源入河系数', fontsize=12, fontweight='bold', loc='left')
    ax1.set_ylim(0, 1.15)
    ax1.legend(fontsize=9)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.grid(axis='y', alpha=0.2, ls=':')

    # 面源
    nps_sources = ['农村生活', '城市面源', '水产养殖', '城镇散排', '农业种植']
    nps_cod = [0.618, 0.720, 0.299, 0.154, 0.000]
    nps_nh3 = [0.618, 0.718, 0.000, 0.154, 0.065]
    nps_tn  = [0.618, 0.720, 0.000, 0.155, 0.066]
    nps_tp  = [0.618, 0.719, 0.000, 0.155, 0.066]

    x2 = np.arange(len(nps_sources))
    ax2.bar(x2 - 1.5 * w, nps_cod, w, label='COD', color='#D62728', alpha=0.85, edgecolor='white')
    ax2.bar(x2 - 0.5 * w, nps_nh3, w, label='NH3-N', color='#1F77B4', alpha=0.85, edgecolor='white')
    ax2.bar(x2 + 0.5 * w, nps_tn, w, label='TN', color='#2CA02C', alpha=0.85, edgecolor='white')
    ax2.bar(x2 + 1.5 * w, nps_tp, w, label='TP', color='#FF7F0E', alpha=0.85, edgecolor='white')

    ax2.set_xticks(x2)
    ax2.set_xticklabels(nps_sources, fontsize=10)
    ax2.set_ylabel('入河系数 (入河量/排放量)', fontsize=11)
    ax2.set_title('(b) 面源入河系数', fontsize=12, fontweight='bold', loc='left')
    ax2.set_ylim(0, 0.85)
    ax2.legend(fontsize=9)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(axis='y', alpha=0.2, ls=':')

    plt.tight_layout(w_pad=3)
    fig.savefig(os.path.join(OUTPUT_DIR, 'fig_inflow_coefficients.png'),
                dpi=300, facecolor='white', edgecolor='none')
    plt.close(fig)
    print('[OK] fig_inflow_coefficients.png')


# ============================================================
# 主函数
# ============================================================
if __name__ == '__main__':
    funcs = [
        ('图2 全链条示意图', plot_fig2),
        ('图3 贝叶斯修正因子', plot_fig3),
        ('图4 半衰距离', plot_fig4),
        ('图5 贡献对比', plot_fig5),
        ('附 数据修正效果', plot_correction_effect),
        ('附 全链条瀑布图', plot_chain_waterfall),
        ('附 控制单元贡献', plot_control_unit),
        ('附 入河系数推算', plot_inflow_coefficients),
    ]

    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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
