#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
降雨数据缺失值分析脚本
按年份统计降雨数据的缺失情况
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

# 配置中文字体
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
matplotlib.rcParams['axes.unicode_minus'] = False

print("=" * 80)
print("降雨数据缺失值分析")
print("=" * 80)
print()

# 读取降雨数据
print("【1】读取降雨数据...")
df_rain = pd.read_excel('rain.xlsx')

# 查看数据结构
print(f"   数据形状: {df_rain.shape}")
print(f"   列名: {df_rain.columns.tolist()}")
print()

# 显示前几行
print("【2】数据预览:")
print(df_rain.head(10))
print()

# 转换时间列
print("【3】处理时间列...")
# 查找时间相关的列
time_cols = [col for col in df_rain.columns if any(keyword in str(col).lower()
             for keyword in ['时间', 'time', 'date', '日期'])]
print(f"   发现时间列: {time_cols}")

if time_cols:
    time_col = time_cols[0]
    df_rain['时间'] = pd.to_datetime(df_rain[time_col], errors='coerce')
else:
    # 如果没有明确的时间列，尝试第一列
    df_rain['时间'] = pd.to_datetime(df_rain.iloc[:, 0], errors='coerce')

# 提取年份
df_rain['年份'] = df_rain['时间'].dt.year

print(f"   时间范围: {df_rain['时间'].min()} ~ {df_rain['时间'].max()}")
print(f"   年份范围: {df_rain['年份'].min()} ~ {df_rain['年份'].max()}")
print()

# 查找降雨量列
print("【4】识别降雨量列...")
rain_cols = [col for col in df_rain.columns if any(keyword in str(col).lower()
             for keyword in ['降水', '降雨', 'rain', 'precip', 'mm'])]
print(f"   发现降雨量列: {rain_cols}")

if rain_cols:
    rain_col = rain_cols[0]
else:
    # 如果没找到，使用第二列（假设第一列是时间）
    rain_col = df_rain.columns[1]

print(f"   使用列: {rain_col}")
print()

# 转换降雨量为数值
df_rain['降雨量'] = pd.to_numeric(df_rain[rain_col], errors='coerce')

# 按年份统计缺失值
print("【5】按年份统计缺失情况...")
print("=" * 80)

yearly_stats = []

for year in sorted(df_rain['年份'].dropna().unique()):
    year_data = df_rain[df_rain['年份'] == year]

    total = len(year_data)
    missing = year_data['降雨量'].isna().sum()
    valid = total - missing
    missing_pct = (missing / total * 100) if total > 0 else 0

    # 统计降雨量
    if valid > 0:
        rain_sum = year_data['降雨量'].sum()
        rain_mean = year_data['降雨量'].mean()
        rain_max = year_data['降雨量'].max()
        rain_days = (year_data['降雨量'] > 0).sum()
    else:
        rain_sum = rain_mean = rain_max = rain_days = 0

    yearly_stats.append({
        '年份': int(year),
        '总记录数': total,
        '有效记录': valid,
        '缺失记录': missing,
        '缺失率(%)': missing_pct,
        '总降雨量(mm)': rain_sum,
        '平均降雨(mm)': rain_mean,
        '最大降雨(mm)': rain_max,
        '降雨天数': rain_days
    })

    print(f"【年份 {int(year)}】")
    print(f"   总记录数: {total:,}")
    print(f"   有效记录: {valid:,}")
    print(f"   缺失记录: {missing:,}")
    print(f"   缺失率: {missing_pct:.2f}%")
    if valid > 0:
        print(f"   总降雨量: {rain_sum:.2f} mm")
        print(f"   平均降雨: {rain_mean:.4f} mm")
        print(f"   最大降雨: {rain_max:.2f} mm")
        print(f"   降雨天数: {rain_days}")
    print()

# 创建统计表
df_stats = pd.DataFrame(yearly_stats)

# 总体统计
print("=" * 80)
print("【总体统计】")
total_all = len(df_rain)
missing_all = df_rain['降雨量'].isna().sum()
valid_all = total_all - missing_all
missing_pct_all = (missing_all / total_all * 100) if total_all > 0 else 0

print(f"   总记录数: {total_all:,}")
print(f"   有效记录: {valid_all:,}")
print(f"   缺失记录: {missing_all:,}")
print(f"   缺失率: {missing_pct_all:.2f}%")
print()

# 保存统计表
output_file = '降雨数据缺失值统计_按年份.xlsx'
df_stats.to_excel(output_file, index=False)
print(f"✓ 已保存统计表: {output_file}")
print()

# 生成可视化图表
print("【6】生成可视化图表...")

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('降雨数据缺失值分析（按年份）', fontsize=18, fontweight='bold')

# 图1: 缺失率柱状图
ax1 = axes[0, 0]
colors1 = ['#ff6b6b' if x > 5 else '#51cf66' if x < 1 else '#ffd93d'
           for x in df_stats['缺失率(%)']]
bars1 = ax1.bar(df_stats['年份'].astype(str), df_stats['缺失率(%)'],
                color=colors1, alpha=0.8, edgecolor='black', linewidth=1.5)
ax1.set_xlabel('年份', fontsize=12, fontweight='bold')
ax1.set_ylabel('缺失率 (%)', fontsize=12, fontweight='bold')
ax1.set_title('各年份降雨数据缺失率', fontsize=14, fontweight='bold')
ax1.grid(axis='y', alpha=0.3)
ax1.axhline(y=5, color='red', linestyle='--', linewidth=1, alpha=0.5, label='5%警戒线')
ax1.legend()

# 在柱子上标注数值
for bar, val in zip(bars1, df_stats['缺失率(%)']):
    height = bar.get_height()
    ax1.text(bar.get_x() + bar.get_width()/2., height,
             f'{val:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

# 图2: 有效记录数堆叠图
ax2 = axes[0, 1]
x = np.arange(len(df_stats))
width = 0.6
bars2a = ax2.bar(x, df_stats['有效记录'], width, label='有效记录',
                 color='#51cf66', alpha=0.8, edgecolor='black', linewidth=1.5)
bars2b = ax2.bar(x, df_stats['缺失记录'], width, bottom=df_stats['有效记录'],
                 label='缺失记录', color='#ff6b6b', alpha=0.8, edgecolor='black', linewidth=1.5)
ax2.set_xlabel('年份', fontsize=12, fontweight='bold')
ax2.set_ylabel('记录数', fontsize=12, fontweight='bold')
ax2.set_title('各年份数据完整性', fontsize=14, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(df_stats['年份'].astype(str))
ax2.legend()
ax2.grid(axis='y', alpha=0.3)

# 图3: 总降雨量趋势
ax3 = axes[1, 0]
ax3.plot(df_stats['年份'], df_stats['总降雨量(mm)'], marker='o',
         linewidth=2, markersize=8, color='#4dabf7', label='总降雨量')
ax3.fill_between(df_stats['年份'], 0, df_stats['总降雨量(mm)'], alpha=0.3, color='#4dabf7')
ax3.set_xlabel('年份', fontsize=12, fontweight='bold')
ax3.set_ylabel('总降雨量 (mm)', fontsize=12, fontweight='bold')
ax3.set_title('各年份总降雨量', fontsize=14, fontweight='bold')
ax3.grid(axis='both', alpha=0.3)
ax3.legend()

# 在点上标注数值
for year, rain in zip(df_stats['年份'], df_stats['总降雨量(mm)']):
    ax3.text(year, rain, f'{rain:.0f}', ha='center', va='bottom', fontsize=9)

# 图4: 统计摘要表
ax4 = axes[1, 1]
ax4.axis('off')

# 创建摘要文本
summary_text = f"""
【降雨数据缺失值分析摘要】

一、数据范围
  • 时间跨度: {df_rain['时间'].min().strftime('%Y-%m-%d')} ~ {df_rain['时间'].max().strftime('%Y-%m-%d')}
  • 年份范围: {int(df_rain['年份'].min())} - {int(df_rain['年份'].max())}
  • 总记录数: {total_all:,} 条

二、缺失情况
  • 有效记录: {valid_all:,} 条
  • 缺失记录: {missing_all:,} 条
  • 总体缺失率: {missing_pct_all:.2f}%

三、各年份缺失率排名
"""

# 添加缺失率排名
df_sorted = df_stats.sort_values('缺失率(%)', ascending=False)
for i, row in df_sorted.head(5).iterrows():
    summary_text += f"  {row['年份']:.0f}年: {row['缺失率(%)']:.2f}%\n"

summary_text += f"""
四、数据质量评价
  • 缺失率 <1%: ✅ 优秀
  • 缺失率 1-5%: ✓ 良好
  • 缺失率 >5%: ⚠ 需注意

五、建议
"""

if missing_pct_all < 1:
    summary_text += "  ✅ 数据质量优秀，可直接使用\n"
elif missing_pct_all < 5:
    summary_text += "  ✓ 数据质量良好，建议填充缺失值\n"
else:
    summary_text += "  ⚠ 缺失率较高，建议检查数据源\n"

ax4.text(0.05, 0.95, summary_text, transform=ax4.transAxes,
         fontsize=10.5, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='#e3f2fd', alpha=0.8))

plt.tight_layout()
plt.savefig('降雨数据缺失值分析图表.png', dpi=300, bbox_inches='tight')
print("   ✓ 已保存图表: 降雨数据缺失值分析图表.png")
print()

print("=" * 80)
print("✅ 分析完成！")
print("=" * 80)
print()
print("【生成文件】")
print("  1. 降雨数据缺失值统计_按年份.xlsx - 详细统计表")
print("  2. 降雨数据缺失值分析图表.png - 可视化图表")
print()
