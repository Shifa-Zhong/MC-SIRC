#!/usr/bin/env python3
"""
验证数据录入错误
"""

import pandas as pd
from pathlib import Path

base_dir = Path(__file__).parent.parent
input_file = base_dir / 'data' / 'data(1).xlsx'
output_file = base_dir / 'output' / '数据错误验证.txt'

report = []
report.append("=" * 100)
report.append("数据错误验证报告")
report.append("=" * 100)

# 读取两个sheet的数据
df_ind = pd.read_excel(input_file, sheet_name='点-工业源')
df_central = pd.read_excel(input_file, sheet_name='点-集中式污染治理设施')

# 找到工业源中的污水厂
wwtp_ind = df_ind[df_ind['企业名称'].str.contains('污水|水处理', na=False)].iloc[0]

# 找到包含换行符的列名
cod_col = [c for c in df_ind.columns if '化学需氧量' in str(c) and '吨' in str(c) and '排放量' not in str(c)][0]
nh3_col = [c for c in df_ind.columns if '氨氮' in str(c) and '吨' in str(c) and '排放量' not in str(c)][0]
tp_col = [c for c in df_ind.columns if '总磷' in str(c) and '吨' in str(c) and '排放量' not in str(c)][0]

report.append("\n【工业源】中阳县宝洁城市污水处理有限公司:")
report.append("  化学需氧量（吨）: " + str(wwtp_ind.get(cod_col, 'N/A')))
report.append("  氨氮（吨）: " + str(wwtp_ind.get(nh3_col, 'N/A')))
report.append("  总磷（吨）: " + str(wwtp_ind.get(tp_col, 'N/A')))
report.append("  排放量-化学需氧量（千克）: " + str(wwtp_ind.get('排放量-化学需氧量（千克）', 'N/A')))
report.append("  排放量-氨氮（千克）: " + str(wwtp_ind.get('排放量-氨氮（千克）', 'N/A')))
report.append("  排放量-总磷（千克）: " + str(wwtp_ind.get('排放量-总磷（千克）', 'N/A')))

report.append("\n【集中式设施】中阳县污水处理厂:")
wwtp_central = df_central.iloc[0]
report.append("  化学需氧量排放量（吨）: " + str(wwtp_central.get('化学需氧量排放量（吨）', 'N/A')))
report.append("  氨氮排放量（吨）: " + str(wwtp_central.get('氨氮排放量（吨）', 'N/A')))
report.append("  总氮排放量（吨）: " + str(wwtp_central.get('总氮排放量（吨）', 'N/A')))
report.append("  总磷排放量（吨）: " + str(wwtp_central.get('总磷排放量（吨）', 'N/A')))
report.append("  排放量-化学需氧量（千克）: " + str(wwtp_central.get('排放量-化学需氧量（千克）', 'N/A')))
report.append("  排放量-氨氮（千克）: " + str(wwtp_central.get('排放量-氨氮（千克）', 'N/A')))
report.append("  排放量-总氮（千克）: " + str(wwtp_central.get('排放量-总氮（千克）', 'N/A')))
report.append("  排放量-总磷（千克）: " + str(wwtp_central.get('排放量-总磷（千克）', 'N/A')))

report.append("\n" + "=" * 80)
report.append("【关键发现】")
report.append("=" * 80)

# 比较数据
ind_cod = wwtp_ind.get(cod_col, 0)
central_cod = wwtp_central.get('化学需氧量排放量（吨）', 0)

ind_nh3 = wwtp_ind.get(nh3_col, 0)
central_nh3 = wwtp_central.get('氨氮排放量（吨）', 0)

ind_tp = wwtp_ind.get(tp_col, 0)
central_tp = wwtp_central.get('总磷排放量（吨）', 0)
central_tn = wwtp_central.get('总氮排放量（吨）', 0)

report.append("\n1. COD对比:")
report.append("   工业源: " + str(ind_cod) + " 吨")
report.append("   集中式: " + str(central_cod) + " 吨")
cod_match = abs(float(ind_cod or 0) - float(central_cod or 0)) < 0.01
report.append("   是否一致: " + ('是 ✓' if cod_match else '否'))

report.append("\n2. 氨氮对比:")
report.append("   工业源: " + str(ind_nh3) + " 吨")
report.append("   集中式: " + str(central_nh3) + " 吨")
nh3_match = abs(float(ind_nh3 or 0) - float(central_nh3 or 0)) < 0.01
report.append("   是否一致: " + ('是 ✓' if nh3_match else '否'))

report.append("\n3. 总磷对比:")
report.append("   工业源'总磷': " + str(ind_tp) + " 吨  ← 异常！")
report.append("   集中式'总磷': " + str(central_tp) + " 吨")
report.append("   集中式'总氮': " + str(central_tn) + " 吨")

tp_tn_match = abs(float(ind_tp or 0) - float(central_tn or 0)) < 0.01
report.append("\n4. 关键发现:")
report.append("   工业源'总磷（吨）' = " + str(ind_tp))
report.append("   集中式'总氮（吨）' = " + str(central_tn))
report.append("   两者是否相等: " + ('是！数据列错位！' if tp_tn_match else '否'))

report.append("\n" + "=" * 80)
report.append("【结论】")
report.append("=" * 80)
report.append("""
1. 这是同一个污水处理厂:
   - "中阳县宝洁城市污水处理有限公司"（工业源）
   - "中阳县污水处理厂"（集中式设施）
   - COD、氨氮数据完全一致，证明是同一设施

2. 工业源表中存在严重数据录入错误:
   - "总磷（吨）"列的值48.69168，实际上是"总氮"的值
   - 正确的总磷值应该是0.885276吨（与集中式设施表一致）
   - 这是一个列错位/数据填错的问题

3. 同一污水厂被重复录入到两个sheet中:
   - 点-工业源（数据有误）
   - 点-集中式污染治理设施（数据正确）

4. 问题影响:
   - 总磷被高估: 48.69吨（错误）vs 0.885吨（正确），相差55倍！
   - 这解释了为什么计算值是监测值的69倍

5. 修正方案:
   从"点-工业源"中删除该污水处理厂
   理由:
   a) 污水处理厂本就不应出现在工业源中
   b) 该数据已在"集中式设施"中正确录入
   c) 保留会造成重复计算
""")

with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))
