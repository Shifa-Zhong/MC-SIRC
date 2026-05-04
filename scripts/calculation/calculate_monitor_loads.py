#!/usr/bin/env python3
"""
使用监测数据（浓度+流量）计算污染物负荷量
与 data(1).xlsx 的入河量进行对比
"""

import pandas as pd
import numpy as np
from pathlib import Path

def calculate_load(concentration, flow, time_interval_hours=1):
    """
    计算污染物负荷量

    参数:
        concentration: 浓度 (mg/L)
        flow: 流量 (m³/s)
        time_interval_hours: 时间间隔 (小时)

    返回:
        负荷量 (kg)

    公式:
        Load(kg) = Concentration(mg/L) × Flow(m³/s) × 时间(s) × 1000L/m³ / 1,000,000mg/kg
                 = Concentration × Flow × time_interval_hours × 3.6

    其中 3.6 = 3600s/h × 1000L/m³ / 1,000,000mg/kg
    """
    conversion_factor = time_interval_hours * 3600 * 1000 / 1_000_000  # = 3.6
    return concentration * flow * conversion_factor

def main():
    print("=" * 80)
    print("使用监测数据计算污染物负荷量")
    print("=" * 80)

    # 污染物指标
    pollutants = {
        '氨氮': '氨氮(mg/L)',
        '总磷': '总磷(mg/L)',
        '总氮': '总氮(mg/L)',
        'COD': '化学需氧量(mg/L)'
    }

    # ============ 读取监测数据 ============
    print("\n【步骤1】读取监测数据...")

    base_dir = Path(__file__).parent.parent
    file_path = base_dir / 'output' / 'monitor_2022_cleaned_v2.xlsx'

    if not file_path.exists():
        print(f"❌ 错误: 文件不存在 - {file_path}")
        return

    df = pd.read_excel(file_path)
    print(f"  ✓ 读取成功: {len(df)} 条数据")
    print(f"  时间范围: {df['监测时间'].min()} 至 {df['监测时间'].max()}")

    # ============ 检查数据列 ============
    print("\n【步骤2】检查数据列...")

    required_cols = ['瞬时流量(m³/s)'] + list(pollutants.values())
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        print(f"❌ 缺少必要的列: {missing_cols}")
        return

    print("  ✓ 所有必要的列都存在")

    # ============ 计算污染物负荷 ============
    print("\n【步骤3】使用积分方法计算污染物负荷...")

    print(f"\n积分公式: Load(kg) = ∫ Concentration(mg/L) × Flow(m³/s) × dt")
    print(f"离散化: Load(kg) = Σ Concentration × Flow × 3.6")
    print(f"其中 3.6 = 1小时 × 3600s/h × 1000L/m³ / 1,000,000mg/kg\n")

    results = {}

    for name, col in pollutants.items():
        # 计算每个时间点的负荷
        loads = calculate_load(df[col], df['瞬时流量(m³/s)'], time_interval_hours=1)
        total_load = loads.sum()
        results[name] = total_load

        # 统计
        valid_count = df[col].notna().sum()
        mean_conc = df[col].mean()

        print(f"{name}:")
        print(f"  有效数据: {valid_count} 条")
        print(f"  平均浓度: {mean_conc:.4f} mg/L")
        print(f"  总负荷: {total_load:,.2f} kg ({total_load/1000:.2f} 吨)")

    # ============ 流量统计 ============
    print("\n【步骤4】流量统计...")

    flow = df['瞬时流量(m³/s)']

    print(f"\n流量统计:")
    print(f"  最小值: {flow.min():.4f} m³/s")
    print(f"  最大值: {flow.max():.4f} m³/s")
    print(f"  平均值: {flow.mean():.4f} m³/s")
    print(f"  中位数: {flow.median():.4f} m³/s")
    print(f"  >10m³/s 次数: {(flow > 10).sum()}")
    print(f"  >1m³/s 次数: {(flow > 1).sum()}")

    # ============ 降雨期vs非降雨期对比 ============
    print("\n【步骤5】降雨期vs非降雨期负荷对比...")

    # 创建降雨标记
    df['是否降雨'] = df['降水量(mm)'] > 0

    rain_count = df['是否降雨'].sum()
    no_rain_count = (~df['是否降雨']).sum()
    rain_pct = rain_count / len(df) * 100

    print(f"\n时间分布:")
    print(f"  降雨时段: {rain_count} 小时 ({rain_pct:.1f}%)")
    print(f"  非降雨时段: {no_rain_count} 小时 ({100-rain_pct:.1f}%)")

    rain_data = []

    print(f"\n{'污染物':<6} {'总负荷(kg)':>15} {'降雨期(kg)':>15} {'非降雨期(kg)':>15} {'降雨期占比':>12}")
    print("-" * 70)

    for name, col in pollutants.items():
        # 降雨期
        rain_mask = df['是否降雨']
        rain_loads = calculate_load(
            df.loc[rain_mask, col],
            df.loc[rain_mask, '瞬时流量(m³/s)'],
            time_interval_hours=1
        )
        rain_total = rain_loads.sum()

        # 非降雨期
        no_rain_loads = calculate_load(
            df.loc[~rain_mask, col],
            df.loc[~rain_mask, '瞬时流量(m³/s)'],
            time_interval_hours=1
        )
        no_rain_total = no_rain_loads.sum()

        total = rain_total + no_rain_total
        rain_contribution = (rain_total / total * 100) if total > 0 else 0

        print(f"{name:<6} {total:>15,.2f} {rain_total:>15,.2f} {no_rain_total:>15,.2f} {rain_contribution:>11.1f}%")

        rain_data.append({
            '污染物': name,
            '总负荷(kg)': total,
            '降雨期负荷(kg)': rain_total,
            '非降雨期负荷(kg)': no_rain_total,
            '降雨期占比(%)': rain_contribution,
            '降雨时段占比(%)': rain_pct
        })

    # ============ 导出结果 ============
    print("\n【步骤6】导出结果...")

    output_file = base_dir / 'output' / '监测数据污染物负荷统计.xlsx'

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Sheet 1: 总负荷
        total_loads = pd.DataFrame([{
            '污染物': name,
            '总负荷(kg)': results[name],
            '总负荷(吨)': results[name] / 1000
        } for name in ['COD', '氨氮', '总氮', '总磷']])
        total_loads.to_excel(writer, sheet_name='监测数据总负荷', index=False)

        # Sheet 2: 降雨期对比
        df_rain = pd.DataFrame(rain_data)
        df_rain.to_excel(writer, sheet_name='降雨期vs非降雨期', index=False)

        # Sheet 3: 流量统计
        flow_stats = pd.DataFrame([{
            '统计项': '最小值(m³/s)',
            '数值': flow.min()
        }, {
            '统计项': '最大值(m³/s)',
            '数值': flow.max()
        }, {
            '统计项': '平均值(m³/s)',
            '数值': flow.mean()
        }, {
            '统计项': '中位数(m³/s)',
            '数值': flow.median()
        }, {
            '统计项': '>10m³/s次数',
            '数值': (flow > 10).sum()
        }, {
            '统计项': '>1m³/s次数',
            '数值': (flow > 1).sum()
        }])
        flow_stats.to_excel(writer, sheet_name='流量统计', index=False)

        # 调整列宽
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    print(f"\n✓ 已导出: {output_file.name}")

    # ============ 总结 ============
    print("\n" + "=" * 80)
    print("【监测数据污染物负荷总量】")
    print("=" * 80)

    print("\n单位：吨\n")
    for name in ['COD', '氨氮', '总氮', '总磷']:
        value_ton = results[name] / 1000
        print(f"  {name:6s}: {value_ton:>10,.2f} 吨")

    print("\n" + "=" * 80)
    print("计算完成！")
    print("=" * 80)

    # 返回结果供对比使用
    return {name: results[name] / 1000 for name in ['COD', '氨氮', '总氮', '总磷']}

if __name__ == "__main__":
    main()
