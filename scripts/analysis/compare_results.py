#!/usr/bin/env python3
"""
对比监测数据计算的负荷与污染源入河量
分析两者的差异及可能原因
"""

import pandas as pd
import numpy as np
from pathlib import Path

def main():
    print("=" * 80)
    print("监测数据负荷 vs 污染源入河量对比分析")
    print("=" * 80)

    # ============ 读取两个结果 ============
    print("\n【步骤1】读取计算结果...")

    base_dir = Path(__file__).parent.parent

    # 监测数据结果
    monitor_file = base_dir / 'output' / '监测数据污染物负荷统计.xlsx'
    df_monitor = pd.read_excel(monitor_file, sheet_name='监测数据总负荷')

    # 污染源数据结果
    source_file = base_dir / 'output' / '入河污染物总量统计.xlsx'
    df_source = pd.read_excel(source_file, sheet_name='入河量汇总(吨)')

    # 提取总计行（最后一行）
    source_totals = df_source[df_source['污染源'] == '总计'].iloc[0]

    print("✓ 数据读取成功\n")

    # ============ 创建对比表 ============
    print("【步骤2】数据对比...")

    pollutants = ['COD', '氨氮', '总氮', '总磷']

    comparison_data = []

    print(f"\n{'污染物':<8} {'监测数据负荷':>15} {'污染源入河量':>15} {'差值':>15} {'入河量/监测':>12}")
    print("-" * 70)

    for pollutant in pollutants:
        # 监测数据负荷（吨）
        monitor_value = df_monitor[df_monitor['污染物'] == pollutant]['总负荷(吨)'].values[0]

        # 污染源入河量（吨）
        source_col = f'{pollutant}(吨)'
        source_value = source_totals[source_col] if source_col in source_totals else 0

        # 计算差值和比例
        diff = source_value - monitor_value
        ratio = source_value / monitor_value if monitor_value > 0 else 0

        print(f"{pollutant:<8} {monitor_value:>14.2f}吨 {source_value:>14.2f}吨 {diff:>14.2f}吨 {ratio:>11.2f}x")

        comparison_data.append({
            '污染物': pollutant,
            '监测数据负荷(吨)': monitor_value,
            '污染源入河量(吨)': source_value,
            '差值(吨)': diff,
            '入河量/监测负荷': ratio,
            '差异百分比(%)': (diff / monitor_value * 100) if monitor_value > 0 else 0
        })

    df_comparison = pd.DataFrame(comparison_data)

    # ============ 分析差异原因 ============
    print("\n" + "=" * 80)
    print("【步骤3】差异分析")
    print("=" * 80)

    print("\n1. 数据差异概览:\n")

    for idx, row in df_comparison.iterrows():
        pollutant = row['污染物']
        ratio = row['入河量/监测负荷']
        diff_pct = row['差异百分比(%)']

        if ratio > 1:
            status = f"污染源入河量是监测负荷的 {ratio:.2f} 倍 (+{diff_pct:.1f}%)"
        elif ratio < 1:
            status = f"污染源入河量仅为监测负荷的 {ratio:.2f} 倍 ({diff_pct:.1f}%)"
        else:
            status = "完全吻合"

        print(f"   {pollutant:6s}: {status}")

    print("\n2. 可能的差异原因:\n")

    reasons = []

    # 分析各污染物
    for idx, row in df_comparison.iterrows():
        pollutant = row['污染物']
        ratio = row['入河量/监测负荷']

        if ratio > 2:
            reason = f"   • {pollutant}: 污染源入河量显著高于监测负荷（{ratio:.1f}倍）"
            reasons.append(reason)
            print(reason)
            print(f"     可能原因:")
            print(f"       - 入河系数可能被高估")
            print(f"       - 污染物在迁移过程中发生降解或沉降")
            print(f"       - 监测点位于污染源下游，污染物已部分降解")
            print(f"       - 监测数据可能存在偏差或缺失")
            print()

        elif ratio < 0.5:
            reason = f"   • {pollutant}: 污染源入河量显著低于监测负荷（仅{ratio:.1f}倍）"
            reasons.append(reason)
            print(reason)
            print(f"     可能原因:")
            print(f"       - 入河系数可能被低估")
            print(f"       - 存在未纳入统计的污染源")
            print(f"       - 监测点可能受上游其他污染源影响")
            print(f"       - 污染源排放量估算可能偏低")
            print()

        elif 0.8 <= ratio <= 1.2:
            reason = f"   • {pollutant}: 两者基本吻合（{ratio:.2f}倍）"
            reasons.append(reason)
            print(reason)
            print(f"     说明: 污染源清单和入河系数较为准确")
            print()

        else:
            reason = f"   • {pollutant}: 存在一定差异（{ratio:.2f}倍）"
            reasons.append(reason)
            print(reason)
            print(f"     建议: 进一步核实污染源清单和入河系数")
            print()

    print("\n3. 综合分析:\n")

    # 统计差异情况
    large_diff = df_comparison[df_comparison['入河量/监测负荷'] > 2]
    small_diff = df_comparison[df_comparison['入河量/监测负荷'] < 0.5]
    good_match = df_comparison[(df_comparison['入河量/监测负荷'] >= 0.8) &
                                (df_comparison['入河量/监测负荷'] <= 1.2)]

    print(f"   • 污染源入河量远高于监测负荷: {len(large_diff)} 个指标")
    if len(large_diff) > 0:
        print(f"     ({', '.join(large_diff['污染物'].tolist())})")

    print(f"   • 污染源入河量远低于监测负荷: {len(small_diff)} 个指标")
    if len(small_diff) > 0:
        print(f"     ({', '.join(small_diff['污染物'].tolist())})")

    print(f"   • 两者基本吻合: {len(good_match)} 个指标")
    if len(good_match) > 0:
        print(f"     ({', '.join(good_match['污染物'].tolist())})")

    print("\n4. 特殊说明:\n")
    print("   • 监测数据: 2022年全年监测断面的实际污染物负荷")
    print("   • 污染源数据: 基于排放量和入河系数计算的理论入河量")
    print("   • 两者差异反映了:")
    print("     1) 入河系数的准确性")
    print("     2) 污染源清单的完整性")
    print("     3) 污染物在迁移过程中的衰减情况")
    print("     4) 监测数据的代表性")

    # ============ 导出对比结果 ============
    print("\n" + "=" * 80)
    print("【步骤4】导出对比结果...")
    print("=" * 80)

    output_file = base_dir / 'output' / '污染负荷对比分析.xlsx'

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Sheet 1: 对比汇总
        df_comparison.to_excel(writer, sheet_name='对比汇总', index=False)

        # Sheet 2: 监测数据详情
        df_monitor.to_excel(writer, sheet_name='监测数据负荷', index=False)

        # Sheet 3: 污染源数据详情
        df_source.to_excel(writer, sheet_name='污染源入河量', index=False)

        # Sheet 4: 分析说明
        analysis_text = []
        analysis_text.append(['分析项', '说明'])
        analysis_text.append(['数据来源', ''])
        analysis_text.append(['监测数据', '2022年监测断面浓度×流量积分'])
        analysis_text.append(['污染源数据', 'data(1).xlsx各污染源排放量×入河系数'])
        analysis_text.append(['', ''])
        analysis_text.append(['差异原因', ''])

        for idx, row in df_comparison.iterrows():
            analysis_text.append([
                row['污染物'],
                f"入河量是监测负荷的{row['入河量/监测负荷']:.2f}倍"
            ])

        df_analysis = pd.DataFrame(analysis_text[1:], columns=analysis_text[0])
        df_analysis.to_excel(writer, sheet_name='分析说明', index=False)

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

    print(f"\n✓ 对比结果已导出到: {output_file.name}")
    print("\n包含以下 Sheet:")
    print("  1. 对比汇总 - 监测数据vs污染源数据对比")
    print("  2. 监测数据负荷 - 监测数据计算的负荷")
    print("  3. 污染源入河量 - 污染源数据计算的入河量")
    print("  4. 分析说明 - 差异原因分析")

    # ============ 总结 ============
    print("\n" + "=" * 80)
    print("【总结】")
    print("=" * 80)

    print("\n监测数据负荷 与 污染源入河量 存在较大差异:")
    print()

    for idx, row in df_comparison.iterrows():
        pollutant = row['污染物']
        ratio = row['入河量/监测负荷']
        monitor_val = row['监测数据负荷(吨)']
        source_val = row['污染源入河量(吨)']

        print(f"{pollutant}:")
        print(f"  监测负荷: {monitor_val:>8.2f} 吨")
        print(f"  入河量:   {source_val:>8.2f} 吨")
        print(f"  比值:     {ratio:>8.2f}x")
        print()

    print("建议:")
    print("  1. 核查入河系数是否合理")
    print("  2. 检查污染源清单是否完整")
    print("  3. 考虑污染物迁移过程中的降解系数")
    print("  4. 验证监测数据的代表性和准确性")

    print("\n" + "=" * 80)
    print("对比分析完成！")
    print("=" * 80)

if __name__ == "__main__":
    main()
