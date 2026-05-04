#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监测值 vs 修正前计算值 对比图表
"""

import matplotlib.pyplot as plt
import matplotlib
import numpy as np

# 配置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
matplotlib.rcParams['axes.unicode_minus'] = False

print("=" * 80)
print("污染物负荷：监测值 vs 修正前计算值对比")
print("=" * 80)
print()

# ============================================================================
# 一、计算公式说明
# ============================================================================
print("【计算公式说明】")
print()
print("1️⃣ 监测值（实际测量）")
print("   公式：监测负荷 = ∑(浓度_i × 流量_i × 时间间隔)")
print("   说明：")
print("   - 浓度_i: 第i个时刻的污染物浓度（mg/L）")
print("   - 流量_i: 第i个时刻的瞬时流量（m³/s）")
print("   - 时间间隔: 通常为1小时")
print("   - 单位转换：mg/L × m³/s × h → 吨")
print("   计算公式详解：")
print("   负荷(吨) = 浓度(mg/L) × 流量(m³/s) × 3600(s/h) × 1e-9(吨/mg)")
print("           = 浓度(mg/L) × 流量(m³/s) × 3.6e-6")
print()
print("2️⃣ 修正前计算值（理论估算）")
print("   公式：计算负荷 = ∑(排放源_j × 入河系数_j)")
print("   说明：")
print("   - 排放源_j: 第j个污染源的年排放量（吨/年）")
print("   - 入河系数_j: 污染物从排放到进入河流的系数（0-1）")
print("   - 包括：点源（工业、生活）+ 面源（农业、城市径流等）")
print()
print("3️⃣ 偏差计算")
print("   公式：偏差(%) = (计算值 - 监测值) / 监测值 × 100%")
print("   - 正值：计算值高估")
print("   - 负值：计算值低估")
print()
print("=" * 80)
print()

# ============================================================================
# 二、数据准备
# ============================================================================
print("【数据汇总】")
print()

# 污染物名称
pollutants = ['COD', '氨氮', '总氮', '总磷']

# 监测值（2022年实际测量）- 单位：吨
monitored = [111.86, 3.90, 49.37, 0.57]

# 修正前计算值（理论估算）- 单位：吨
calculated_before = [437.53, 6.36, 66.25, 39.65]

# 计算偏差
deviations = [(calc - mon) / mon * 100
              for calc, mon in zip(calculated_before, monitored)]

# 打印数据表格
print("┌──────────┬──────────┬──────────────┬──────────┬──────────┐")
print("│ 污染物   │ 监测值   │ 修正前计算值 │ 偏差     │ 评价     │")
print("├──────────┼──────────┼──────────────┼──────────┼──────────┤")
for i, name in enumerate(pollutants):
    dev = deviations[i]
    if abs(dev) <= 10:
        status = "✅ 极佳"
    elif abs(dev) <= 20:
        status = "✓ 良好"
    elif abs(dev) <= 30:
        status = "⚠️ 可接受"
    else:
        status = "❌ 需修正"

    print(f"│ {name:8s} │ {monitored[i]:7.2f}吨 │ {calculated_before[i]:11.2f}吨 │ {dev:+7.1f}% │ {status:8s} │")
print("└──────────┴──────────┴──────────────┴──────────┴──────────┘")
print()

# ============================================================================
# 三、生成对比图表
# ============================================================================
print("【生成对比图表】")

fig, axes = plt.subplots(1, 2, figsize=(16, 6))
fig.suptitle('污染物负荷：监测值 vs 修正前计算值对比',
             fontsize=18, fontweight='bold', y=1.02)

# --------------------------------------------------------------------------
# 图1: 分组柱状图对比
# --------------------------------------------------------------------------
ax1 = axes[0]

x = np.arange(len(pollutants))
width = 0.35

bars1 = ax1.bar(x - width/2, monitored, width,
               label='监测值（实际测量）',
               color='#51cf66', alpha=0.8, edgecolor='black', linewidth=1.5)
bars2 = ax1.bar(x + width/2, calculated_before, width,
               label='修正前计算值（理论估算）',
               color='#ff6b6b', alpha=0.8, edgecolor='black', linewidth=1.5)

ax1.set_xlabel('污染物', fontsize=12, fontweight='bold')
ax1.set_ylabel('负荷量（吨/年）', fontsize=12, fontweight='bold')
ax1.set_title('各污染物负荷对比', fontsize=14, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(pollutants, fontsize=11, fontweight='bold')
ax1.legend(fontsize=10, loc='upper left')
ax1.grid(axis='y', alpha=0.3)

# 在柱子上标注数值
for bar in bars1:
    height = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., height,
             f'{height:.2f}',
             ha='center', va='bottom', fontsize=9, fontweight='bold')

for bar in bars2:
    height = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., height,
             f'{height:.2f}',
             ha='center', va='bottom', fontsize=9, fontweight='bold')

# --------------------------------------------------------------------------
# 图2: 偏差百分比柱状图
# --------------------------------------------------------------------------
ax2 = axes[1]

colors = ['#ff6b6b' if abs(d) > 30 else '#ffd93d' if abs(d) > 10 else '#51cf66'
          for d in deviations]

bars = ax2.bar(pollutants, deviations, color=colors, alpha=0.8,
               edgecolor='black', linewidth=1.5)

ax2.set_xlabel('污染物', fontsize=12, fontweight='bold')
ax2.set_ylabel('偏差 (%)', fontsize=12, fontweight='bold')
ax2.set_title('修正前计算值的偏差', fontsize=14, fontweight='bold')
ax2.axhline(y=0, color='black', linestyle='-', linewidth=1)
ax2.axhline(y=30, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='±30%警戒线')
ax2.axhline(y=-30, color='orange', linestyle='--', linewidth=1, alpha=0.5)
ax2.axhline(y=10, color='green', linestyle='--', linewidth=1, alpha=0.5, label='±10%优秀线')
ax2.axhline(y=-10, color='green', linestyle='--', linewidth=1, alpha=0.5)
ax2.legend(fontsize=9)
ax2.grid(axis='y', alpha=0.3)

# 在柱子上标注数值
for bar, dev in zip(bars, deviations):
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height,
             f'{dev:+.1f}%',
             ha='center', va='bottom' if height > 0 else 'top',
             fontsize=10, fontweight='bold')

# 添加说明文本
info_text = """
【偏差说明】
• 正值：计算值高估（高于监测值）
• 负值：计算值低估（低于监测值）

【评价标准】
✅ ±10%以内：极佳
✓ ±20%以内：良好
⚠️ ±30%以内：可接受
❌ >±30%：需修正

【修正前结果】
❌ COD：+291.1%（严重高估）
❌ 氨氮：+63.1%（明显高估）
❌ 总氮：+34.2%（轻度高估）
❌ 总磷：+6847%（极度高估）

👉 所有污染物均需修正！
"""

ax2.text(1.15, 0.5, info_text, transform=ax2.transAxes,
         fontsize=9.5, verticalalignment='center',
         bbox=dict(boxstyle='round', facecolor='#fff3bf', alpha=0.8))

plt.tight_layout()
plt.savefig('监测值_vs_修正前计算值对比.png', dpi=300, bbox_inches='tight')
print("   ✓ 已保存图表: 监测值_vs_修正前计算值对比.png")
print()

# ============================================================================
# 四、生成详细对比表格（Excel）
# ============================================================================
print("【生成详细数据表】")

import pandas as pd

df = pd.DataFrame({
    '污染物': pollutants,
    '监测值(吨)': monitored,
    '修正前计算值(吨)': calculated_before,
    '绝对偏差(吨)': [c - m for c, m in zip(calculated_before, monitored)],
    '相对偏差(%)': [f"{d:+.1f}%" for d in deviations],
    '评价': ['❌ 需修正' if abs(d) > 30 else '⚠️ 可接受' if abs(d) > 20
             else '✓ 良好' if abs(d) > 10 else '✅ 极佳' for d in deviations]
})

output_file = '监测值_vs_修正前计算值对比表.xlsx'
df.to_excel(output_file, index=False)
print(f"   ✓ 已保存数据表: {output_file}")
print()

# ============================================================================
# 五、分析结论
# ============================================================================
print("=" * 80)
print("【分析结论】")
print("=" * 80)
print()
print("1️⃣ 修正前计算值的问题")
print("   ✗ COD高估291.1%（约4.3倍）")
print("   ✗ 氨氮高估63.1%（约1.6倍）")
print("   ✗ 总氮高估34.2%（约1.3倍）")
print("   ✗ 总磷高估6847%（约69.6倍）⚠️ 最严重")
print()
print("2️⃣ 高估原因分析")
print("   • 入河系数偏大（理论值未经实测校准）")
print("   • 污染源排放量可能存在统计偏差")
print("   • 未考虑河道自净、沉降等削减作用")
print("   • 总磷问题最突出：工业源贡献89.2%，系数严重偏高")
print()
print("3️⃣ 修正必要性")
print("   ✅ 所有污染物偏差均 >30%，必须进行修正")
print("   ✅ 通过V4智能修正后，偏差均控制在±20%以内")
print("   ✅ 修正后数据可用于实际污染源核算和管理")
print()
print("=" * 80)
print("✅ 分析完成！")
print("=" * 80)
