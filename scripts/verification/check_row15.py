#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查第15行企业详情"""

import pandas as pd
from pathlib import Path

data_file = Path(__file__).parent.parent / 'data' / 'data(1).xlsx'
output_file = Path(__file__).parent.parent / 'output' / 'row15_detail.txt'

df = pd.read_excel(data_file, sheet_name='点-工业源')

lines = []
lines.append("=" * 80)
lines.append("第15行企业详情 (总磷入河量最大)")
lines.append("=" * 80)

row = df.iloc[15]
for col in df.columns:
    lines.append(f"{col}: {row[col]}")

lines.append("\n" + "=" * 80)
lines.append("所有企业总磷排放量对比")
lines.append("=" * 80)

df['排放量-总磷（千克）'] = pd.to_numeric(df['排放量-总磷（千克）'], errors='coerce')
df_sorted = df.sort_values('排放量-总磷（千克）', ascending=False)

for idx, row in df_sorted.iterrows():
    name = row['企业名称']
    tp = row['排放量-总磷（千克）']
    lines.append(f"行{idx}: {name} - {tp:,.2f} 千克 ({tp/1000:.2f} 吨)")

with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f"Results saved to: {output_file}")
