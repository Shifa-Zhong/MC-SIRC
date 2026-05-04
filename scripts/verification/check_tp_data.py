#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查点-工业源的总磷数据
"""

import pandas as pd
from pathlib import Path

def main():
    data_file = Path(__file__).parent.parent / 'data' / 'data(1).xlsx'
    output_file = Path(__file__).parent.parent / 'output' / 'tp_check_result.txt'

    lines = []
    lines.append("=" * 80)
    lines.append("检查 点-工业源 的总磷数据")
    lines.append("=" * 80)

    # 读取工业源sheet
    df = pd.read_excel(data_file, sheet_name='点-工业源')

    lines.append(f"\n数据行数: {len(df)}")
    lines.append(f"数据列数: {len(df.columns)}")

    # 打印所有列名
    lines.append("\n所有列名:")
    for i, col in enumerate(df.columns, 1):
        lines.append(f"  {i:2d}. {col}")

    # 查找总磷相关的列
    lines.append("\n" + "=" * 80)
    lines.append("总磷相关列详情")
    lines.append("=" * 80)

    tp_cols = [col for col in df.columns if '总磷' in str(col) or '磷' in str(col)]

    for col in tp_cols:
        lines.append(f"\n【{col}】")
        values = pd.to_numeric(df[col], errors='coerce')
        valid_count = values.notna().sum()
        total = values.sum()

        lines.append(f"  非空值数量: {valid_count}")
        lines.append(f"  总和: {total:,.2f}")

        if valid_count > 0:
            lines.append(f"  最大值: {values.max():,.2f}")
            lines.append(f"  最小值: {values.min():,.4f}")
            lines.append(f"  平均值: {values.mean():,.4f}")

            # 显示最大的几个值
            top5 = values.nlargest(5)
            lines.append(f"\n  最大的5个值:")
            for idx, val in top5.items():
                lines.append(f"    行{idx}: {val:,.2f}")

    # 查找入河量相关的列
    lines.append("\n" + "=" * 80)
    lines.append("入河量相关列详情")
    lines.append("=" * 80)

    inflow_cols = [col for col in df.columns if '入河量' in str(col)]

    for col in inflow_cols:
        lines.append(f"\n【{col}】")
        values = pd.to_numeric(df[col], errors='coerce')
        valid_count = values.notna().sum()
        total = values.sum()

        lines.append(f"  非空值数量: {valid_count}")
        lines.append(f"  总和: {total:,.2f}")

        if valid_count > 0 and total > 0:
            # 转换单位显示
            lines.append(f"  总和(吨): {total/1000:,.4f}")
            lines.append(f"  最大值: {values.max():,.2f}")

            # 显示最大的几个值
            top5 = values.nlargest(5)
            lines.append(f"\n  最大的5个值:")
            for idx, val in top5.items():
                lines.append(f"    行{idx}: {val:,.2f}")

    # 检查系数列
    lines.append("\n" + "=" * 80)
    lines.append("入河系数相关列")
    lines.append("=" * 80)

    coef_cols = [col for col in df.columns if '系数' in str(col)]
    for col in coef_cols:
        values = pd.to_numeric(df[col], errors='coerce')
        if values.notna().sum() > 0:
            lines.append(f"\n【{col}】")
            lines.append(f"  范围: {values.min():.4f} ~ {values.max():.4f}")
            lines.append(f"  平均: {values.mean():.4f}")

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Results saved to: {output_file}")

if __name__ == "__main__":
    main()
