#!/usr/bin/env python3
"""
详细检查总磷数据来源，找出不合理的计算
"""

import pandas as pd
import numpy as np
from pathlib import Path

def main():
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / 'data' / 'data(1).xlsx'
    output_file = base_dir / 'output' / '总磷数据详细检查.txt'

    report = []
    report.append("=" * 100)
    report.append("总磷(TP)数据详细检查报告")
    report.append("=" * 100)
    report.append(f"\n监测值: 570.77 kg (0.57 吨)")
    report.append(f"目标: 找出计算值偏高的原因\n")

    sheets = [
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

    total_tp = 0
    tp_by_source = []

    for sheet_name in sheets:
        report.append("\n" + "=" * 80)
        report.append(f"【{sheet_name}】")
        report.append("=" * 80)

        df = pd.read_excel(input_file, sheet_name=sheet_name)
        report.append(f"数据行数: {len(df)}, 列数: {len(df.columns)}")

        # 找总磷相关的列
        tp_cols = [c for c in df.columns if '总磷' in str(c) or 'TP' in str(c).upper()]
        report.append(f"\n总磷相关列: {tp_cols}")

        # 找入河量列
        inflow_cols = [c for c in df.columns if '入河量' in str(c) and '总磷' in str(c)]

        sheet_tp = 0

        if inflow_cols:
            for col in inflow_cols:
                values = pd.to_numeric(df[col], errors='coerce')
                col_total = values.sum()
                sheet_tp += col_total
                report.append(f"\n入河量列: {col}")
                report.append(f"  总和: {col_total:,.2f} kg")
                report.append(f"  非空行数: {values.notna().sum()}")
                report.append(f"  最大值: {values.max():,.4f}")
                report.append(f"  最小值: {values.min():,.4f}")
                report.append(f"  均值: {values.mean():,.4f}")

                # 检查异常大的值
                large_values = values[values > 100]
                if len(large_values) > 0:
                    report.append(f"  >100kg的记录数: {len(large_values)}")
                    report.append(f"  这些记录的总和: {large_values.sum():,.2f} kg")
        else:
            # 检查是否有其他包含总磷的入河量列
            for col in df.columns:
                if '入河量' in str(col) and '系数' not in str(col):
                    col_str = str(col).lower()
                    if '总磷' in col_str or 'tp' in col_str:
                        values = pd.to_numeric(df[col], errors='coerce')
                        col_total = values.sum()
                        sheet_tp += col_total
                        report.append(f"\n入河量列: {col}")
                        report.append(f"  总和: {col_total:,.2f} kg")

        # 检查排放量列
        emission_cols = [c for c in df.columns if '排放量' in str(c) and '总磷' in str(c)]
        if emission_cols:
            report.append(f"\n排放量列:")
            for col in emission_cols:
                values = pd.to_numeric(df[col], errors='coerce')
                report.append(f"  {col}: {values.sum():,.2f}")

        # 检查产污系数
        coef_cols = [c for c in df.columns if '系数' in str(c) and '总磷' in str(c)]
        if coef_cols:
            report.append(f"\n总磷相关系数列:")
            for col in coef_cols:
                values = pd.to_numeric(df[col], errors='coerce').dropna()
                if len(values) > 0:
                    report.append(f"  {col}: {values.iloc[0] if len(values) > 0 else 'N/A'}")

        total_tp += sheet_tp
        tp_by_source.append({
            'source': sheet_name,
            'tp_kg': sheet_tp,
            'tp_ton': sheet_tp / 1000
        })

        report.append(f"\n本sheet总磷入河量: {sheet_tp:,.2f} kg ({sheet_tp/1000:.2f} 吨)")

    # 汇总
    report.append("\n" + "=" * 100)
    report.append("【汇总】各污染源总磷入河量")
    report.append("=" * 100)

    # 按贡献排序
    tp_by_source.sort(key=lambda x: x['tp_kg'], reverse=True)

    report.append(f"\n{'污染源':<40} {'入河量(kg)':>15} {'入河量(吨)':>12} {'占比':>10}")
    report.append("-" * 80)

    for item in tp_by_source:
        pct = (item['tp_kg'] / total_tp * 100) if total_tp > 0 else 0
        report.append(f"{item['source']:<40} {item['tp_kg']:>15,.2f} {item['tp_ton']:>12.2f} {pct:>9.1f}%")

    report.append("-" * 80)
    report.append(f"{'总计':<40} {total_tp:>15,.2f} {total_tp/1000:>12.2f} {'100.0%':>10}")
    report.append(f"{'监测值':<40} {570.77:>15,.2f} {0.57:>12.2f}")
    report.append(f"{'计算/监测':<40} {total_tp/570.77:>15.1f}倍")

    # 详细检查工业源
    report.append("\n" + "=" * 100)
    report.append("【重点检查】点-工业源 总磷详细数据")
    report.append("=" * 100)

    df_ind = pd.read_excel(input_file, sheet_name='点-工业源')
    report.append(f"\n列名列表:")
    for i, col in enumerate(df_ind.columns):
        report.append(f"  {i}: {col}")

    # 找到总磷入河量列
    tp_col = None
    for col in df_ind.columns:
        if '入河量' in str(col) and '总磷' in str(col):
            tp_col = col
            break

    if tp_col:
        report.append(f"\n总磷入河量列: {tp_col}")
        report.append(f"\n逐行数据:")

        # 找企业名称列
        name_col = None
        for col in df_ind.columns:
            if '企业' in str(col) or '名称' in str(col) or '单位' in str(col):
                name_col = col
                break

        for idx, row in df_ind.iterrows():
            tp_val = pd.to_numeric(row[tp_col], errors='coerce')
            if pd.notna(tp_val) and tp_val > 0:
                name = row[name_col] if name_col else f"行{idx}"
                report.append(f"  {name}: {tp_val:,.2f} kg")

    # 详细检查规模畜禽养殖
    report.append("\n" + "=" * 100)
    report.append("【重点检查】规模畜禽养殖 总磷详细数据")
    report.append("=" * 100)

    df_livestock = pd.read_excel(input_file, sheet_name='规模畜禽养殖（点数据，按面源统计）')

    # 找总磷相关列
    report.append(f"\n所有列名:")
    for i, col in enumerate(df_livestock.columns):
        if '磷' in str(col) or '入河' in str(col) or '排放' in str(col):
            report.append(f"  {i}: {col}")

    tp_col = None
    for col in df_livestock.columns:
        if '入河量' in str(col) and '总磷' in str(col):
            tp_col = col
            break

    if tp_col:
        values = pd.to_numeric(df_livestock[tp_col], errors='coerce')
        report.append(f"\n总磷入河量列: {tp_col}")
        report.append(f"  总和: {values.sum():,.2f} kg")
        report.append(f"  数据行数: {len(values.dropna())}")

        # 检查计算过程
        # 找排放量列
        emission_col = None
        for col in df_livestock.columns:
            if '排放量' in str(col) and '总磷' in str(col):
                emission_col = col
                break

        if emission_col:
            emissions = pd.to_numeric(df_livestock[emission_col], errors='coerce')
            report.append(f"\n排放量列: {emission_col}")
            report.append(f"  排放量总和: {emissions.sum():,.2f} kg")

            # 计算入河系数
            if values.sum() > 0 and emissions.sum() > 0:
                implied_coef = values.sum() / emissions.sum()
                report.append(f"  隐含入河系数: {implied_coef:.4f} ({implied_coef*100:.2f}%)")

    # 详细检查集中式设施
    report.append("\n" + "=" * 100)
    report.append("【重点检查】点-集中式污染治理设施 总磷详细数据")
    report.append("=" * 100)

    df_central = pd.read_excel(input_file, sheet_name='点-集中式污染治理设施')

    report.append(f"\n数据行数: {len(df_central)}")
    report.append(f"\n所有列名:")
    for i, col in enumerate(df_central.columns):
        report.append(f"  {i}: {col}")

    tp_col = None
    for col in df_central.columns:
        if '入河量' in str(col) and '总磷' in str(col):
            tp_col = col
            break

    if tp_col:
        values = pd.to_numeric(df_central[tp_col], errors='coerce')
        report.append(f"\n总磷入河量: {values.sum():,.2f} kg")

        for idx, row in df_central.iterrows():
            tp_val = pd.to_numeric(row[tp_col], errors='coerce')
            if pd.notna(tp_val):
                report.append(f"  行{idx}: {tp_val:,.2f} kg")

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

if __name__ == "__main__":
    main()
