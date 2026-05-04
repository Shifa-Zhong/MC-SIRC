#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成单个图表测试
"""

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# 第1步：设置样式
plt.style.use('default')

# 第2步：配置中文字体（与测试脚本完全相同）
matplotlib.rcParams['font.family'] = ['sans-serif']
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
matplotlib.rcParams['axes.unicode_minus'] = False

# 第3步：设置背景颜色
matplotlib.rcParams['figure.facecolor'] = 'white'
matplotlib.rcParams['axes.facecolor'] = '#f5f5f5'
matplotlib.rcParams['grid.alpha'] = 0.3

print("=" * 80)
print("生成单个测试图表")
print(f"字体配置: {matplotlib.rcParams['font.sans-serif']}")
print("=" * 80)

# 生成图表
fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('数据预处理方法对比分析（V1.0 vs V2.0）', fontsize=18, fontweight='bold')

# 左上角：最大流量对比
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

# 右上角：大流量事件
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

# 左下角：响应率
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

# 右下角：文字总结
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
        fontsize=11, verticalalignment='top', family='monospace',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
plt.savefig('测试_单个图表.png', dpi=300, bbox_inches='tight')
print("✓ 已保存: 测试_单个图表.png")
print("=" * 80)
plt.close()
