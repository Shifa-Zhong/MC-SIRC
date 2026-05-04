#!/usr/bin/env python3
"""
计算 data(1).xlsx 各污染源的入河污染物总量
- 分别统计每个 sheet 的入河量
- 汇总所有污染源的入河量
- 计算各污染源的比例
"""

import pandas as pd
import numpy as np
from pathlib import Path

def identify_inflow_columns(df):
    """
    识别入河量列
    规则：列名包含"入河量"且不包含"系数"
    """
    inflow_cols = []
    for col in df.columns:
        col_str = str(col)
        if '入河量' in col_str and '系数' not in col_str:
            inflow_cols.append(col)
    return inflow_cols

def standardize_pollutant_name(col_name):
    """
    标准化污染物名称
    """
    col_str = str(col_name).lower()

    if 'cod' in col_str or '化学需氧量' in col_str:
        return 'COD'
    elif '氨氮' in col_str or 'nh3' in col_str:
        return '氨氮'
    elif '总氮' in col_str and '氨氮' not in col_str:
        return '总氮'
    elif '总磷' in col_str:
        return '总磷'
    else:
        return col_name

def main():
    print("=" * 80)
    print("计算 data(1).xlsx 各污染源入河污染物总量")
    print("=" * 80)

    # 文件路径
    base_dir = Path(__file__).parent.parent
    file_path = base_dir / 'data' / 'data(1).xlsx'

    # 所有 sheet 名称
    sheet_names = [
        '面-农村生活污染源',
        '面-农业面源',
        '畜禽散养（点数据，按面源统计）',
        '面-水产养殖',
        '面-城市面源',
        '面-城镇散排',
        '规模畜禽养殖（点数据，按面源统计）',
        '点-工业源',
        '点-集中式污染治理设施'
    ]

    # 存储各 sheet 的结果
    all_results = []

    # 统一的污染物类型
    pollutant_types = ['COD', '氨氮', '总氮', '总磷']

    print("\n【步骤1】计算各污染源的入河量...\n")

    for sheet_name in sheet_names:
        print(f"\n处理: {sheet_name}")
        print("-" * 60)

        # 读取数据
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        print(f"  数据行数: {len(df)}")

        # 识别入河量列
        inflow_cols = identify_inflow_columns(df)
        print(f"  识别到 {len(inflow_cols)} 个入河量列:")

        # 计算每个入河量列的总和
        result = {
            '污染源': sheet_name,
            'COD': 0,
            '氨氮': 0,
            '总氮': 0,
            '总磷': 0
        }

        for col in inflow_cols:
            # 标准化污染物名称
            pollutant = standardize_pollutant_name(col)

            # 转换为数值类型并计算总和
            values = pd.to_numeric(df[col], errors='coerce')
            total = values.sum()

            # 跳过无法识别或全为空的列
            if total == 0 or pd.isna(total):
                continue

            print(f"    - {col}")
            print(f"      → {pollutant}: {total:,.2f} 千克")

            # 存储结果
            if pollutant in result:
                result[pollutant] += total
            else:
                # 如果是新的污染物类型，添加到结果中
                if pollutant not in pollutant_types:
                    print(f"      ⚠️  未识别的污染物类型，跳过")

        all_results.append(result)

    # 创建结果 DataFrame
    df_results = pd.DataFrame(all_results)

    # 计算总和
    total_row = {'污染源': '总计'}
    for pollutant in pollutant_types:
        total_row[pollutant] = df_results[pollutant].sum()

    print("\n" + "=" * 80)
    print("【步骤2】各污染源入河量汇总")
    print("=" * 80)
    print("\n单位：千克\n")

    # 显示结果
    for idx, row in df_results.iterrows():
        print(f"{row['污染源']}")
        for pollutant in pollutant_types:
            value = row[pollutant]
            if value > 0:
                print(f"  {pollutant:6s}: {value:>15,.2f} kg")
        print()

    print("-" * 80)
    print(f"{'总计'}")
    for pollutant in pollutant_types:
        value = total_row[pollutant]
        print(f"  {pollutant:6s}: {value:>15,.2f} kg")
    print("-" * 80)

    # 计算比例
    print("\n" + "=" * 80)
    print("【步骤3】各污染源占比分析")
    print("=" * 80)

    percentage_data = []

    for idx, row in df_results.iterrows():
        pct_row = {'污染源': row['污染源']}

        print(f"\n{row['污染源']}")
        for pollutant in pollutant_types:
            value = row[pollutant]
            total = total_row[pollutant]

            if total > 0:
                percentage = (value / total) * 100
                pct_row[f'{pollutant}_占比(%)'] = percentage
                if value > 0:
                    print(f"  {pollutant:6s}: {percentage:>6.2f}%")
            else:
                pct_row[f'{pollutant}_占比(%)'] = 0

        percentage_data.append(pct_row)

    # 创建占比 DataFrame
    df_percentage = pd.DataFrame(percentage_data)

    # 转换单位：千克 → 吨
    print("\n" + "=" * 80)
    print("【步骤4】单位转换：千克 → 吨")
    print("=" * 80)

    df_results_ton = df_results.copy()
    for pollutant in pollutant_types:
        df_results_ton[f'{pollutant}(吨)'] = df_results[pollutant] / 1000
        df_results_ton = df_results_ton.drop(columns=[pollutant])

    total_row_ton = {'污染源': '总计'}
    for pollutant in pollutant_types:
        total_row_ton[f'{pollutant}(吨)'] = total_row[pollutant] / 1000

    print("\n单位：吨\n")
    for idx, row in df_results_ton.iterrows():
        print(f"{row['污染源']}")
        for pollutant in pollutant_types:
            value = row[f'{pollutant}(吨)']
            if value > 0:
                print(f"  {pollutant:6s}: {value:>12,.2f} 吨")
        print()

    print("-" * 80)
    print(f"{'总计'}")
    for pollutant in pollutant_types:
        value = total_row_ton[f'{pollutant}(吨)']
        print(f"  {pollutant:6s}: {value:>12,.2f} 吨")
    print("-" * 80)

    # 导出结果
    print("\n" + "=" * 80)
    print("【步骤5】导出结果到 Excel")
    print("=" * 80)

    output_file = base_dir / 'output' / '入河污染物总量统计.xlsx'

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Sheet 1: 入河量汇总（千克）
        df_results_with_total = pd.concat([df_results, pd.DataFrame([total_row])], ignore_index=True)
        df_results_with_total.to_excel(writer, sheet_name='入河量汇总(千克)', index=False)

        # Sheet 2: 入河量汇总（吨）
        df_results_ton_with_total = pd.concat([df_results_ton, pd.DataFrame([total_row_ton])], ignore_index=True)
        df_results_ton_with_total.to_excel(writer, sheet_name='入河量汇总(吨)', index=False)

        # Sheet 3: 各污染源占比
        df_percentage.to_excel(writer, sheet_name='各污染源占比', index=False)

        # Sheet 4: 各 sheet 详细信息
        sheet_info = []
        for sheet_name in sheet_names:
            df_temp = pd.read_excel(file_path, sheet_name=sheet_name)
            sheet_info.append({
                'Sheet名称': sheet_name,
                '数据行数': len(df_temp),
                '数据列数': len(df_temp.columns)
            })
        df_sheet_info = pd.DataFrame(sheet_info)
        df_sheet_info.to_excel(writer, sheet_name='Sheet信息', index=False)

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

    print(f"\n✓ 结果已导出到: {output_file.name}")
    print("\n包含以下 Sheet:")
    print("  1. 入河量汇总(千克) - 各污染源的入河量（单位：千克）")
    print("  2. 入河量汇总(吨) - 各污染源的入河量（单位：吨）")
    print("  3. 各污染源占比 - 各污染源在总入河量中的占比")
    print("  4. Sheet信息 - 各 sheet 的基本信息")

    # 总结
    print("\n" + "=" * 80)
    print("【分析总结】")
    print("=" * 80)

    print("\n1. 入河污染物总量（吨）:")
    for pollutant in pollutant_types:
        value = total_row_ton[f'{pollutant}(吨)']
        print(f"   • {pollutant:6s}: {value:>10,.2f} 吨")

    print("\n2. 主要污染源（按COD入河量排序）:")
    df_sorted = df_results.sort_values('COD', ascending=False)
    for idx, row in df_sorted.head(5).iterrows():
        cod_value = row['COD'] / 1000
        if cod_value > 0:
            cod_pct = (row['COD'] / total_row['COD']) * 100
            print(f"   • {row['污染源']}: {cod_value:,.2f} 吨 ({cod_pct:.1f}%)")

    print("\n3. 污染源数量:")
    print(f"   • 面源污染: 6 个 sheet")
    print(f"   • 点源污染: 2 个 sheet")
    print(f"   • 总计: {len(sheet_names)} 个污染源类型")

    print("\n" + "=" * 80)
    print("计算完成！")
    print("=" * 80)

if __name__ == "__main__":
    main()
