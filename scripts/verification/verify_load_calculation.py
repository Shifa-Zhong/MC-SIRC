#!/usr/bin/env python3
"""
验证污染负荷计算脚本的正确性
"""

import pandas as pd
import numpy as np
from pathlib import Path

base_dir = Path(__file__).parent.parent
output_file = base_dir / 'output' / '负荷计算验证报告.txt'

report = []
report.append("=" * 100)
report.append("污染负荷计算脚本验证报告")
report.append("=" * 100)

# ============ 1. 公式验证 ============
report.append("\n【1. 公式验证】")
report.append("-" * 80)

report.append("""
脚本使用的公式:
  Load(kg) = Concentration(mg/L) × Flow(m³/s) × 3.6

推导过程:
  质量 = 浓度 × 体积
  体积 = 流量 × 时间 = Q(m³/s) × 3600(s) = Q × 3600 (m³)

  Load = C(mg/L) × Q(m³/s) × 3600(s) × 1000(L/m³) / 1,000,000(mg/kg)
       = C × Q × 3,600,000 / 1,000,000
       = C × Q × 3.6 (kg/h)

结论: 公式正确 ✓
  - 3.6 是单位换算因子，将 mg/L × m³/s × h 转换为 kg
  - 每条记录计算的是该小时内通过断面的污染物质量(kg)
""")

# ============ 2. 检查监测数据时间间隔 ============
report.append("\n【2. 监测数据时间间隔检查】")
report.append("-" * 80)

monitor_file = base_dir / 'output' / 'monitor_2022_cleaned_v2.xlsx'

if monitor_file.exists():
    df = pd.read_excel(monitor_file)
    df['监测时间'] = pd.to_datetime(df['监测时间'])
    df = df.sort_values('监测时间')

    # 计算时间间隔
    time_diffs = df['监测时间'].diff().dropna()

    report.append(f"\n数据基本信息:")
    report.append(f"  总记录数: {len(df)}")
    report.append(f"  起始时间: {df['监测时间'].min()}")
    report.append(f"  结束时间: {df['监测时间'].max()}")

    # 时间跨度
    total_hours = (df['监测时间'].max() - df['监测时间'].min()).total_seconds() / 3600
    report.append(f"  时间跨度: {total_hours:.0f} 小时 ({total_hours/24:.1f} 天)")

    report.append(f"\n时间间隔统计:")
    report.append(f"  最小间隔: {time_diffs.min()}")
    report.append(f"  最大间隔: {time_diffs.max()}")
    report.append(f"  中位数间隔: {time_diffs.median()}")

    # 检查是否为逐小时数据
    hourly_count = (time_diffs == pd.Timedelta(hours=1)).sum()
    report.append(f"  间隔=1小时的记录数: {hourly_count} ({hourly_count/len(time_diffs)*100:.1f}%)")

    # 检查数据连续性
    expected_hours = int(total_hours) + 1
    actual_hours = len(df)
    completeness = actual_hours / expected_hours * 100

    report.append(f"\n数据完整性:")
    report.append(f"  理论应有记录数: {expected_hours}")
    report.append(f"  实际记录数: {actual_hours}")
    report.append(f"  完整率: {completeness:.1f}%")

    if completeness < 95:
        report.append(f"  ⚠️ 数据有缺失，可能影响总负荷计算")
    else:
        report.append(f"  ✓ 数据较完整")

    # ============ 3. 检查关键列 ============
    report.append("\n【3. 关键数据列检查】")
    report.append("-" * 80)

    cols_to_check = ['瞬时流量(m³/s)', '氨氮(mg/L)', '总磷(mg/L)', '总氮(mg/L)', '化学需氧量(mg/L)']

    for col in cols_to_check:
        if col in df.columns:
            values = df[col]
            valid = values.notna().sum()
            missing = values.isna().sum()

            report.append(f"\n{col}:")
            report.append(f"  有效值: {valid} ({valid/len(df)*100:.1f}%)")
            report.append(f"  缺失值: {missing} ({missing/len(df)*100:.1f}%)")
            report.append(f"  最小值: {values.min():.4f}")
            report.append(f"  最大值: {values.max():.4f}")
            report.append(f"  平均值: {values.mean():.4f}")

            # 检查是否有负值或异常值
            if (values < 0).any():
                report.append(f"  ⚠️ 存在负值!")

            if col == '瞬时流量(m³/s)':
                zero_count = (values == 0).sum()
                report.append(f"  零值数量: {zero_count}")

    # ============ 4. 重新计算并验证 ============
    report.append("\n【4. 负荷计算验证】")
    report.append("-" * 80)

    pollutants = {
        'COD': '化学需氧量(mg/L)',
        '氨氮': '氨氮(mg/L)',
        '总氮': '总氮(mg/L)',
        '总磷': '总磷(mg/L)'
    }

    report.append("\n逐小时累加法计算结果:")

    for name, col in pollutants.items():
        # 方法1: 逐小时累加 (脚本使用的方法)
        loads = df[col] * df['瞬时流量(m³/s)'] * 3.6
        total_load = loads.sum()

        # 方法2: 平均浓度 × 平均流量 × 总时间
        avg_conc = df[col].mean()
        avg_flow = df['瞬时流量(m³/s)'].mean()
        total_hours_actual = len(df)
        load_avg_method = avg_conc * avg_flow * 3.6 * total_hours_actual

        report.append(f"\n{name}:")
        report.append(f"  方法1(逐时累加): {total_load:,.2f} kg ({total_load/1000:.2f} 吨)")
        report.append(f"  方法2(平均值法): {load_avg_method:,.2f} kg ({load_avg_method/1000:.2f} 吨)")
        report.append(f"  差异: {abs(total_load - load_avg_method)/total_load*100:.1f}%")

    # ============ 5. 物理意义分析 ============
    report.append("\n\n【5. 物理意义分析】")
    report.append("-" * 80)

    report.append("""
监测断面负荷的物理意义:

  监测负荷 = ∫ C(t) × Q(t) dt

  这代表的是: 通过监测断面的污染物总质量

  与入河量的关系:

  监测负荷 ≠ 入河量
  监测负荷 = Σ(各源入河量) × 河道传输系数 - 河道自净损失

  简化模型:
  监测负荷 = Σ(排放量 × 入河系数 × 河道衰减系数)

  其中河道衰减系数 < 1，表示污染物在河道中的降解、沉降等损失
""")

    # ============ 6. 结论 ============
    report.append("\n【6. 结论】")
    report.append("-" * 80)

    report.append("""
1. 公式正确性: ✓ 正确
   - 单位换算正确
   - 逐小时累加方法合理

2. 数据质量:
   - 需确认数据是否为连续的逐小时记录
   - 缺失数据会导致负荷被低估

3. 物理解释:
   - 计算结果是"断面通量"，不是"入河量"
   - 断面通量 < 入河量 (因为河道自净)
   - 这解释了为什么计算的入河量 > 监测负荷

4. 用于系数优化时的注意事项:
   - 目标函数应考虑河道衰减
   - 即: Σ(排放量 × 入河系数 × 衰减系数) ≈ 监测负荷
   - 而非: Σ(排放量 × 入河系数) = 监测负荷
""")

else:
    report.append(f"\n错误: 监测数据文件不存在 - {monitor_file}")

# 写入报告
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))
