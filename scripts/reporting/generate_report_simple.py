#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
项目进展汇报可视化脚本（简化版 - 确保中文显示）
"""

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import os

# ============================================================================
# 设置图表样式（必须在字体设置之前）
# ============================================================================
plt.style.use('default')

# ============================================================================
# 配置中文字体（必须在style之后）
# ============================================================================
print("=" * 80)
print("配置中文字体...")

# 配置matplotlib使用Microsoft YaHei字体（测试已验证可用）
matplotlib.rcParams['font.family'] = ['sans-serif']
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
matplotlib.rcParams['axes.unicode_minus'] = False

# 设置其他样式
matplotlib.rcParams['figure.facecolor'] = 'white'
matplotlib.rcParams['axes.facecolor'] = '#f5f5f5'
matplotlib.rcParams['grid.alpha'] = 0.3

print(f"✓ 字体配置: {matplotlib.rcParams['font.sans-serif']}")
print(f"✓ 配置完成")

print("=" * 80)
print("山西水质监测数据分析项目 - 汇报材料生成工具")
print("=" * 80)
print()

# ============================================================================
# 图1: 数据预处理成果对比
# ============================================================================
print("【1/5】生成数据预处理成果对比图...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('数据预处理方法对比分析（V1.0 vs V2.0）', fontsize=18, fontweight='bold')

# 1.1 最大流量对比
ax = axes[0, 0]
methods = ['V1.0\n(IQR方法)', 'V2.0\n(阈值方法)']
max_flows = [2.14, 30.88]
colors = ['#ff6b6b', '#51cf66']
bars = ax.bar(methods, max_flows, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
ax.set_ylabel('最大流量 (m³/s)', fontsize=12, fontweight='bold')
ax.set_title('最大流量对比', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3)
for bar, val in zip(bars, max_flows):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{val:.2f} m³/s', ha='center', va='bottom', fontsize=11, fontweight='bold')
ax.text(0.5, 25, '提升14倍', ha='center', fontsize=12,
        bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))

# 1.2 大流量事件对比
ax = axes[0, 1]
events = [0, 7]
bars = ax.bar(methods, events, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
ax.set_ylabel('事件数量', fontsize=12, fontweight='bold')
ax.set_title('大流量事件(>10 m³/s)检测', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3)
for bar, val in zip(bars, events):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{val}次', ha='center', va='bottom', fontsize=11, fontweight='bold')

# 1.3 降雨响应率对比
ax = axes[1, 0]
response_rates = [20.5, 79.5]
bars = ax.bar(methods, response_rates, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
ax.set_ylabel('响应率 (%)', fontsize=12, fontweight='bold')
ax.set_title('降雨响应率对比', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, 100)
for bar, val in zip(bars, response_rates):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{val}%', ha='center', va='bottom', fontsize=11, fontweight='bold')
ax.text(0.5, 50, '提升59%', ha='center', fontsize=12,
        bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.5))

# 1.4 方法评价
ax = axes[1, 1]
ax.axis('off')
comparison_text = """
【方法对比总结】

V1.0（IQR方法）：
  ✗ 误删真实洪峰事件
  ✗ 响应率仅20.5%
  ✗ 无法揭示延迟关系
  ✗ 不推荐使用

V2.0（阈值方法）：
  ✓ 保留真实洪峰（7次）
  ✓ 响应率高达79.5%
  ✓ 清晰展示延迟关系
  ✓ 推荐使用

核心改进：
• 基于领域知识的阈值（0-50 m³/s）
• 三级智能填充策略
• 保留物理意义的极值
"""
ax.text(0.05, 0.95, comparison_text, transform=ax.transAxes,
        fontsize=11, verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
plt.savefig('图1_数据预处理成果对比.png', dpi=300, bbox_inches='tight')
print("   ✓ 已保存: 图1_数据预处理成果对比.png")
plt.close()

# ============================================================================
# 图2: 系数修正效果对比（核心图表）
# ============================================================================
print("【2/5】生成系数修正效果对比图...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('污染源入河系数修正效果（V4最终版）', fontsize=18, fontweight='bold')

pollutants = ['COD', '氨氮', '总氮', '总磷']
original = [437.53, 6.36, 66.25, 39.65]
v4_corrected = [106.22, 4.29, 44.90, 0.49]
monitored = [111.86, 3.90, 49.37, 0.57]

# 2.1 修正前后总量对比
ax = axes[0, 0]
x = np.arange(len(pollutants))
width = 0.25
bars1 = ax.bar(x - width, original, width, label='修正前', color='#ff6b6b', alpha=0.8)
bars2 = ax.bar(x, v4_corrected, width, label='V4修正后', color='#51cf66', alpha=0.8)
bars3 = ax.bar(x + width, monitored, width, label='监测值', color='#1864ab', alpha=0.8)

ax.set_ylabel('污染物总量 (吨)', fontsize=12, fontweight='bold')
ax.set_title('修正前后污染物总量对比', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(pollutants, fontsize=11, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(axis='y', alpha=0.3)

# 2.2 V4修正效果（偏差率）
ax = axes[0, 1]
bias_v4 = [(v4 - m) / m * 100 for v4, m in zip(v4_corrected, monitored)]
colors_bias = ['#51cf66' if abs(b) <= 10 else '#ffd93d' if abs(b) <= 20 else '#ff6b6b' for b in bias_v4]
bars = ax.bar(pollutants, bias_v4, color=colors_bias, alpha=0.8, edgecolor='black', linewidth=1.5)

ax.set_ylabel('偏差率 (%)', fontsize=12, fontweight='bold')
ax.set_title('V4修正后偏差率（目标: ±10%以内）', fontsize=14, fontweight='bold')
ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
ax.axhline(y=10, color='red', linestyle='--', linewidth=1, alpha=0.5, label='±10%')
ax.axhline(y=-10, color='red', linestyle='--', linewidth=1, alpha=0.5)
ax.axhline(y=20, color='orange', linestyle='--', linewidth=1, alpha=0.3, label='±20%')
ax.axhline(y=-20, color='orange', linestyle='--', linewidth=1, alpha=0.3)
ax.legend(fontsize=9)
ax.grid(axis='y', alpha=0.3)

for bar, bias in zip(bars, bias_v4):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{bias:+.1f}%', ha='center', va='bottom' if height > 0 else 'top',
            fontsize=10, fontweight='bold')

# 2.3 迭代优化过程
ax = axes[1, 0]
versions = ['修正前', 'V2', 'V3', 'V4']
cod_series = [437.53, 91.13, 99.24, 106.22]
tn_series = [66.25, 31.40, 35.19, 44.90]
tp_series = [39.65, 0.33, 0.39, 0.49]

x = np.arange(len(versions))
ax.plot(x, cod_series, marker='o', linewidth=2, markersize=8, label='COD', color='#ff6b6b')
ax.plot(x, tn_series, marker='^', linewidth=2, markersize=8, label='总氮', color='#4dabf7')
ax.plot(x, tp_series, marker='D', linewidth=2, markersize=8, label='总磷', color='#a78bfa')

ax.axhline(y=monitored[0], color='#ff6b6b', linestyle='--', linewidth=1, alpha=0.5)
ax.axhline(y=monitored[2], color='#4dabf7', linestyle='--', linewidth=1, alpha=0.5)
ax.axhline(y=monitored[3], color='#a78bfa', linestyle='--', linewidth=1, alpha=0.5)

ax.set_ylabel('污染物总量 (吨)', fontsize=12, fontweight='bold')
ax.set_title('迭代优化过程（虚线为监测值目标）', fontsize=14, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(versions, fontsize=11, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(axis='both', alpha=0.3)

# 2.4 V4最终效果评价
ax = axes[1, 1]
ax.axis('off')
v4_summary = """
【V4修正最终效果评价】

污染物    修正后    监测值    偏差率    评价
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COD      106.22    111.86     -5.0%   ✅ 极佳
氨氮       4.29      3.90     +9.9%   ✅ 极佳
总氮      44.90     49.37     -9.1%   ✅ 极佳
总磷       0.49      0.57    -13.3%   ✓ 良好
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【关键改进】
V2→V3→V4三轮迭代优化

✓ 总氮：-36.4% → -28.7% → -9.1%
  改进27.3%，从"可接受"到"极佳"

✓ 总磷：-42.2% → -32.2% → -13.3%
  改进28.9%，从"需改进"到"良好"

【核心策略】
差异化修正：根据污染源贡献度
  • 高贡献源(>80%): 因子0.80
  • 中贡献源(40-80%): 因子0.85-0.90
  • 低贡献源(<40%): 因子0.95-1.00
"""
ax.text(0.05, 0.95, v4_summary, transform=ax.transAxes,
        fontsize=10, verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

plt.tight_layout()
plt.savefig('图2_系数修正效果对比.png', dpi=300, bbox_inches='tight')
print("   ✓ 已保存: 图2_系数修正效果对比.png")
plt.close()

# ============================================================================
# 图3: 降雨-流量延迟关系
# ============================================================================
print("【3/5】生成降雨-流量延迟关系分析图...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('降雨-流量延迟关系分析', fontsize=18, fontweight='bold')

# 3.1 按降雨等级的响应率
ax = axes[0, 0]
rainfall_levels = ['小雨\n0-0.5mm', '中雨\n0.5-1mm', '大雨\n1-2mm', '暴雨\n>2mm']
response_rates = [71.8, 76.9, 89.5, 88.2]
event_counts = [39, 13, 19, 17]
colors_rain = ['#74c0fc', '#4dabf7', '#1c7ed6', '#1864ab']
bars = ax.bar(rainfall_levels, response_rates, color=colors_rain, alpha=0.8, edgecolor='black', linewidth=1.5)
ax.set_ylabel('响应率 (%)', fontsize=12, fontweight='bold')
ax.set_title('不同降雨等级的流量响应率', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, 100)
for i, (bar, rate, count) in enumerate(zip(bars, response_rates, event_counts)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 2,
            f'{rate}%\n({count}次)', ha='center', va='bottom', fontsize=10, fontweight='bold')

# 3.2 按降雨等级的平均延迟
ax = axes[0, 1]
avg_delays = [25.2, 21.1, 26.5, 17.7]
bars = ax.bar(rainfall_levels, avg_delays, color=colors_rain, alpha=0.8, edgecolor='black', linewidth=1.5)
ax.set_ylabel('平均延迟 (小时)', fontsize=12, fontweight='bold')
ax.set_title('不同降雨等级的平均延迟时间', fontsize=14, fontweight='bold')
ax.grid(axis='y', alpha=0.3)
ax.axhline(y=23.3, color='red', linestyle='--', linewidth=2, label='总体平均延迟')
ax.legend(fontsize=10)
for bar, delay in zip(bars, avg_delays):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{delay:.1f}h', ha='center', va='bottom', fontsize=10, fontweight='bold')

# 3.3 延迟时间分布
ax = axes[1, 0]
delay_counts = [5, 12, 31, 18, 3, 1]
x_pos = np.arange(len(delay_counts))
bars = ax.bar(x_pos, delay_counts, color='#845ef7', alpha=0.8, edgecolor='black', linewidth=1.5)
ax.set_xlabel('延迟时间 (小时)', fontsize=12, fontweight='bold')
ax.set_ylabel('事件数量', fontsize=12, fontweight='bold')
ax.set_title('延迟时间分布（70个响应事件）', fontsize=14, fontweight='bold')
ax.set_xticks(x_pos)
ax.set_xticklabels(['0-10', '10-20', '20-30', '30-40', '40-50', '>50'])
ax.grid(axis='y', alpha=0.3)
ax.axvline(x=2, color='red', linestyle='--', linewidth=2, label='典型延迟(21-25h)')
ax.legend(fontsize=10)
for bar, count in zip(bars, delay_counts):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{count}', ha='center', va='bottom', fontsize=10, fontweight='bold')

# 3.4 核心发现
ax = axes[1, 1]
ax.axis('off')
findings = """
【降雨-流量延迟关系核心发现】

✓ 存在明显延迟关系
  • 典型延迟：21-25小时（约1天）
  • 平均延迟：23.3小时
  • 延迟范围：0-61小时

✓ 响应率分析（88个降雨事件）
  • 总响应率：79.5% (70/88)
  • 非冻土期：88.6% (70/79)
  • 冬季(1-2月)：0% (0/9)

✓ 降雨量影响规律
  • 降雨越大，响应率越高
  • 降雨越大，延迟越短
  • 暴雨(>2mm)：17.7h，88.2%响应

✓ 实际应用
  • 洪水预警：降雨后20-25小时监测
  • 主要产流期：3-11月
  • 冬季可不预警（冻土无响应）
"""
ax.text(0.05, 0.95, findings, transform=ax.transAxes,
        fontsize=10.5, verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

plt.tight_layout()
plt.savefig('图3_降雨流量延迟关系分析.png', dpi=300, bbox_inches='tight')
print("   ✓ 已保存: 图3_降雨流量延迟关系分析.png")
plt.close()

# ============================================================================
# 图4: 项目成果总览
# ============================================================================
print("【4/5】生成项目成果总览图...")

fig = plt.figure(figsize=(18, 10))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
fig.suptitle('山西水质监测数据分析项目 - 成果总览', fontsize=20, fontweight='bold')

# 时间线
ax1 = fig.add_subplot(gs[0, :])
ax1.axis('off')
timeline = """
【项目时间线】
2025-10-20: ✓ 数据预处理V1.0（IQR） → ✓ V2.0（阈值，重大改进） → ✓ 降雨-流量延迟分析
2025-10-21: ✓ 系数修正V1.0 → ✓ 技术文档 → ✓ V2/V3/V4迭代优化 → ✓ 项目总结
"""
ax1.text(0.05, 0.5, timeline, transform=ax1.transAxes, fontsize=12,
         verticalalignment='center',
         bbox=dict(boxstyle='round', facecolor='#e3f2fd', alpha=0.8))

# 数据规模
ax2 = fig.add_subplot(gs[1, 0])
categories = ['原始数据\n2019-2024', '2022年\n数据', '降雨\n事件', '响应\n事件']
values = [30000, 5928, 88, 70]
colors_stat = ['#ff6b6b', '#ffd93d', '#51cf66', '#4dabf7']
bars = ax2.bar(categories, values, color=colors_stat, alpha=0.8, edgecolor='black', linewidth=1.5)
ax2.set_ylabel('数量', fontsize=11, fontweight='bold')
ax2.set_title('数据规模统计', fontsize=13, fontweight='bold')
ax2.set_yscale('log')
ax2.grid(axis='y', alpha=0.3)

# 完整率
ax3 = fig.add_subplot(gs[1, 1])
indicators = ['氨氮', '总磷', '总氮', 'COD', '流量', '降水']
completeness = [100] * 6
bars = ax3.barh(indicators, completeness, color='#51cf66', alpha=0.8, edgecolor='black', linewidth=1.5)
ax3.set_xlabel('完整率 (%)', fontsize=11, fontweight='bold')
ax3.set_title('核心指标完整率', fontsize=13, fontweight='bold')
ax3.set_xlim(0, 110)
ax3.grid(axis='x', alpha=0.3)

# 文件产出
ax4 = fig.add_subplot(gs[1, 2])
file_types = ['Python\n脚本', 'Excel\n数据', '分析\n报告', '技术\n文档']
file_counts = [8, 6, 3, 4]
colors_files = ['#a78bfa', '#ffd93d', '#ff6b6b', '#51cf66']
bars = ax4.bar(file_types, file_counts, color=colors_files, alpha=0.8, edgecolor='black', linewidth=1.5)
ax4.set_ylabel('文件数量', fontsize=11, fontweight='bold')
ax4.set_title('项目产出统计', fontsize=13, fontweight='bold')
ax4.grid(axis='y', alpha=0.3)

# 核心成果
ax5 = fig.add_subplot(gs[2, :])
ax5.axis('off')
achievements = """
【核心成果】
一、数据预处理（V2.0阈值方法）
  ✓ 完整率100%  ✓ 保留7次洪峰  ✓ 最大流量30.88m³/s(提升14倍)  ✓ 响应率79.5%(提升59%)

二、降雨-流量延迟关系
  ✓ 典型延迟21-25小时  ✓ 响应率79.5%  ✓ 发现季节性规律（冬季无响应，非冻土期88.6%）

三、污染源入河系数修正（V4最终版）
  ✅ COD：偏差-5.0%(极佳)  ✅ 氨氮：偏差+9.9%(极佳)  ✅ 总氮：偏差-9.1%(极佳)  ✓ 总磷：偏差-13.3%(良好)

四、方法论创新
  ✓ 阈值方法优于IQR  ✓ 三级智能填充  ✓ 事件驱动分析  ✓ 差异化系数修正(V2→V3→V4迭代)
"""
ax5.text(0.02, 0.98, achievements, transform=ax5.transAxes, fontsize=10.5,
         verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='#fff9c4', alpha=0.8))

plt.savefig('图4_项目成果总览.png', dpi=300, bbox_inches='tight')
print("   ✓ 已保存: 图4_项目成果总览.png")
plt.close()

# ============================================================================
# 生成Excel数据表格
# ============================================================================
print("【5/5】生成详细数据表格...")

with pd.ExcelWriter('项目汇报数据表格.xlsx', engine='openpyxl') as writer:

    # 表1: 数据预处理对比
    df1 = pd.DataFrame({
        '对比项': ['异常值检测', '最大流量(m³/s)', '大流量事件', '响应率(%)', '推荐'],
        'V1.0(IQR)': ['Q3+1.5×IQR', '2.14', '0次', '20.5%', '❌'],
        'V2.0(阈值)': ['0-50 m³/s', '30.88', '7次', '79.5%', '✅'],
        '改进': ['更合理', '↑14倍', '+7次', '↑59%', '重大提升']
    })
    df1.to_excel(writer, sheet_name='数据预处理对比', index=False)

    # 表2: 降雨延迟关系
    df2 = pd.DataFrame({
        '降雨等级': ['小雨(0-0.5mm)', '中雨(0.5-1mm)', '大雨(1-2mm)', '暴雨(>2mm)', '总计'],
        '事件数': [39, 13, 19, 17, 88],
        '响应数': [28, 10, 17, 15, 70],
        '响应率(%)': [71.8, 76.9, 89.5, 88.2, 79.5],
        '平均延迟(h)': [25.2, 21.1, 26.5, 17.7, 23.3]
    })
    df2.to_excel(writer, sheet_name='降雨延迟关系', index=False)

    # 表3: 系数修正效果
    df3 = pd.DataFrame({
        '污染物': ['COD', '氨氮', '总氮', '总磷'],
        '修正前(吨)': [437.53, 6.36, 66.25, 39.65],
        'V4修正(吨)': [106.22, 4.29, 44.90, 0.49],
        '监测值(吨)': [111.86, 3.90, 49.37, 0.57],
        '修正前偏差': ['+291.1%', '+63.1%', '+34.2%', '+6846.8%'],
        'V4偏差': ['-5.0%', '+9.9%', '-9.1%', '-13.3%'],
        'V4评价': ['✅极佳', '✅极佳', '✅极佳', '✓良好']
    })
    df3.to_excel(writer, sheet_name='系数修正效果', index=False)

    # 表4: 项目统计
    df4 = pd.DataFrame({
        '统计项': ['原始数据量', '2022数据量', '降雨事件', '响应事件', '大流量事件',
                  'Python脚本', 'Excel文件', '分析报告', '技术文档', 'Git提交'],
        '数值': ['30,000+条', '5,928条', '88个', '70个', '7个',
               '8个', '6个', '3个', '4个', '4次']
    })
    df4.to_excel(writer, sheet_name='项目统计', index=False)

print("   ✓ 已保存: 项目汇报数据表格.xlsx")

print()
print("=" * 80)
print("✅ 所有汇报材料生成完成！")
print("=" * 80)
print()
print("【生成文件】")
print("  1. 图1_数据预处理成果对比.png")
print("  2. 图2_系数修正效果对比.png")
print("  3. 图3_降雨流量延迟关系分析.png")
print("  4. 图4_项目成果总览.png")
print("  5. 项目汇报数据表格.xlsx")
print()
print("【使用建议】")
print("  • PPT汇报：直接插入PNG图片")
print("  • 书面报告：引用Excel表格数据")
print("  • 答辩演示：按图1→2→3→4顺序")
print()
print("【关键亮点】")
print("  ✓ 数据预处理创新（阈值法vs IQR法）")
print("  ✓ 降雨-流量延迟关系（21-25小时）")
print("  ✓ 系数修正极佳效果（3个污染物±10%内）")
print("  ✓ 完整技术文档体系")
print("=" * 80)
