#!/usr/bin/env python3
"""检查系数列的数据结构"""

import pandas as pd
from pathlib import Path

base_dir = Path(__file__).parent.parent
input_file = base_dir / 'data' / 'data(1).xlsx'
output_file = base_dir / 'output' / 'coef_structure_check.txt'

results = []

# 检查农村生活污染源
results.append("=" * 80)
results.append("面-农村生活污染源")
results.append("=" * 80)

df = pd.read_excel(input_file, sheet_name='面-农村生活污染源')
coef_cols = [c for c in df.columns if '系数' in str(c)]

for c in coef_cols:
    values = df[c].dropna()
    results.append(f"\n列名: {c}")
    results.append(f"  非空值数量: {len(values)}")
    if len(values) > 0:
        results.append(f"  前5个值: {values.head(5).tolist()}")
        results.append(f"  数据类型: {values.dtype}")

# 检查入河量列
inflow_cols = [c for c in df.columns if '入河量' in str(c) and '系数' not in str(c)]
results.append(f"\n入河量列: {inflow_cols}")

# 检查水产养殖
results.append("\n" + "=" * 80)
results.append("面-水产养殖")
results.append("=" * 80)

df = pd.read_excel(input_file, sheet_name='面-水产养殖')
coef_cols = [c for c in df.columns if '系数' in str(c)]

for c in coef_cols:
    values = df[c].dropna()
    results.append(f"\n列名: {c}")
    results.append(f"  非空值数量: {len(values)}")
    if len(values) > 0:
        results.append(f"  前5个值: {values.head(5).tolist()}")

inflow_cols = [c for c in df.columns if '入河量' in str(c) and '系数' not in str(c)]
results.append(f"\n入河量列: {inflow_cols}")

# 写入文件
with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(results))
