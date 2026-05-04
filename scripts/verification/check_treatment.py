#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查集中式污染治理设施sheet"""

import pandas as pd
from pathlib import Path

data_file = Path(__file__).parent.parent / 'data' / 'data(1).xlsx'
output_file = Path(__file__).parent.parent / 'output' / 'treatment_check.txt'

df = pd.read_excel(data_file, sheet_name='点-集中式污染治理设施')

lines = []
lines.append("=" * 80)
lines.append("点-集中式污染治理设施 Sheet")
lines.append("=" * 80)

lines.append(f"\n数据行数: {len(df)}")
lines.append(f"\n所有列名:")
for i, col in enumerate(df.columns, 1):
    lines.append(f"  {i:2d}. {col}")

lines.append("\n" + "=" * 80)
lines.append("企业列表")
lines.append("=" * 80)

# 查找企业名称列
name_col = None
for col in df.columns:
    if '名称' in str(col) or '企业' in str(col):
        name_col = col
        break

if name_col:
    for idx, row in df.iterrows():
        lines.append(f"行{idx}: {row[name_col]}")

# 查找总磷相关列
lines.append("\n" + "=" * 80)
lines.append("总磷数据")
lines.append("=" * 80)

tp_cols = [col for col in df.columns if '总磷' in str(col) or '磷' in str(col)]
for col in tp_cols:
    values = pd.to_numeric(df[col], errors='coerce')
    lines.append(f"\n【{col}】")
    lines.append(f"  总和: {values.sum():,.2f}")
    lines.append(f"  总和(吨): {values.sum()/1000:.4f}")

with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"Results saved to: {output_file}")
