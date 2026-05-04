#!/usr/bin/env python3
"""
核查污水处理厂数据并修正后重新核算
"""

import pandas as pd
import numpy as np
from pathlib import Path

def main():
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / 'data' / 'data(1).xlsx'
    output_file = base_dir / 'output' / '入河污染物总量_修正后v2.xlsx'
    report_file = base_dir / 'output' / '污水厂数据核查与修正报告.txt'

    report = []
    report.append("=" * 100)
    report.append("污水处理厂数据核查与修正报告")
    report.append("=" * 100)

    # ==================== 第一部分：核查数据 ====================
    report.append("\n" + "=" * 80)
    report.append("【第一部分】数据核查")
    report.append("=" * 80)

    # 1. 检查点-工业源中的污水处理厂
    report.append("\n>>> 点-工业源 中的数据:")
    df_ind = pd.read_excel(input_file, sheet_name='点-工业源')

    # 找到污水处理厂的行
    wwtp_rows = []
    for idx, row in df_ind.iterrows():
        name = str(row.get('企业名称', ''))
        if '污水' in name or '水处理' in name:
            wwtp_rows.append(idx)
            report.append(f"\n发现污水处理相关企业 (行{idx}):")
            report.append(f"  企业名称: {name}")

            # 显示所有数值列
            for col in df_ind.columns:
                val = row[col]
                if pd.notna(val) and col != '企业名称':
                    report.append(f"  {col}: {val}")

    # 2. 检查点-集中式污染治理设施
    report.append("\n\n>>> 点-集中式污染治理设施 中的数据:")
    df_central = pd.read_excel(input_file, sheet_name='点-集中式污染治理设施')

    for idx, row in df_central.iterrows():
        name = str(row.get('单位名称', ''))
        report.append(f"\n设施 (行{idx}):")
        report.append(f"  单位名称: {name}")

        for col in df_central.columns:
            val = row[col]
            if pd.notna(val) and col != '单位名称':
                report.append(f"  {col}: {val}")

    # ==================== 第二部分：问题分析 ====================
    report.append("\n\n" + "=" * 80)
    report.append("【第二部分】问题分析")
    report.append("=" * 80)

    # 获取工业源中污水厂的详细数据
    if wwtp_rows:
        wwtp_idx = wwtp_rows[0]
        wwtp_data = df_ind.iloc[wwtp_idx]

        # 获取关键数据
        tp_ton = pd.to_numeric(wwtp_data.get('总磷\n（吨）', 0), errors='coerce')
        tp_emission_kg = pd.to_numeric(wwtp_data.get('排放量-总磷（千克）', 0), errors='coerce')
        tp_inflow_kg = pd.to_numeric(wwtp_data.get('入河量-总磷（千克）', 0), errors='coerce')

        report.append(f"\n工业源中'中阳县宝洁城市污水处理有限公司'数据:")
        report.append(f"  总磷（吨）列: {tp_ton}")
        report.append(f"  排放量-总磷（千克）: {tp_emission_kg}")
        report.append(f"  入河量-总磷（千克）: {tp_inflow_kg}")

        # 检查单位一致性
        report.append(f"\n单位检查:")
        report.append(f"  如果'总磷（吨）'={tp_ton}吨，换算为千克应该是 {tp_ton*1000} kg")
        report.append(f"  实际排放量列值: {tp_emission_kg} kg")

        if abs(tp_ton * 1000 - tp_emission_kg) < 1:
            report.append(f"  → 单位换算正确（吨→千克）")
        else:
            report.append(f"  → 单位可能存在问题！差异: {abs(tp_ton*1000 - tp_emission_kg)}")

        # 检查是否与集中式设施重复
        report.append(f"\n重复检查:")
        central_name = df_central.iloc[0].get('单位名称', '') if len(df_central) > 0 else ''
        ind_name = wwtp_data.get('企业名称', '')

        report.append(f"  工业源中名称: {ind_name}")
        report.append(f"  集中式设施名称: {central_name}")

        if '宝洁' in str(central_name) or central_name == ind_name:
            report.append(f"  → 可能是同一设施，存在重复计算！")
        else:
            report.append(f"  → 不是同一设施，但分类错误（污水厂不应在工业源中）")

    # ==================== 第三部分：问题确认 ====================
    report.append("\n\n" + "=" * 80)
    report.append("【第三部分】确认的问题")
    report.append("=" * 80)

    report.append("""
问题1: 分类错误
  - "中阳县宝洁城市污水处理有限公司"是城市污水处理厂
  - 被错误分类到"点-工业源"
  - 应属于"点-集中式污染治理设施"

问题2: 数据异常
  - 该污水厂总磷入河量: 34,692.82 kg (34.69吨)
  - 对比: 集中式设施中的污水厂总磷排放量仅 0.89 吨
  - 该值异常偏高，可能是:
    a) 数据录入错误
    b) 与集中式设施中的数据重复
    c) 计算公式错误

修正方案:
  - 将该污水厂从工业源入河量计算中剔除
  - 理由: 污水厂属于集中式设施，不应计入工业源
""")

    # ==================== 第四部分：修正后重新核算 ====================
    report.append("\n" + "=" * 80)
    report.append("【第四部分】修正后重新核算")
    report.append("=" * 80)

    pollutants = ['COD', '氨氮', '总氮', '总磷']

    def get_pollutant_type(col_name):
        col_str = str(col_name).lower()
        if 'cod' in col_str or '化学需氧量' in col_str:
            return 'COD'
        elif '氨氮' in col_str:
            return '氨氮'
        elif '总氮' in col_str:
            return '总氮'
        elif '总磷' in col_str:
            return '总磷'
        return None

    def get_inflow_sum(df):
        result = {'COD': 0, '氨氮': 0, '总氮': 0, '总磷': 0}
        for col in df.columns:
            if '入河量' in str(col) and '系数' not in str(col):
                values = pd.to_numeric(df[col], errors='coerce')
                total = values.sum()
                pollutant = get_pollutant_type(col)
                if pollutant and total > 0:
                    result[pollutant] += total
        return result

    results = []

    # 1. 面-农村生活污染源 (修正系数 0.1 -> 0.4)
    df = pd.read_excel(input_file, sheet_name='面-农村生活污染源')
    inflow = get_inflow_sum(df)
    corrected = {p: v * 4.0 for p, v in inflow.items()}  # 系数从0.1改为0.4
    results.append({'污染源': '面-农村生活污染源', **corrected, '修正说明': '基础入河系数0.1→0.4'})

    # 2. 面-农业面源 (不修正)
    df = pd.read_excel(input_file, sheet_name='面-农业面源')
    inflow = get_inflow_sum(df)
    results.append({'污染源': '面-农业面源', **inflow, '修正说明': '无修正'})

    # 3. 畜禽散养 (不修正)
    df = pd.read_excel(input_file, sheet_name='畜禽散养（点数据，按面源统计）')
    inflow = get_inflow_sum(df)
    results.append({'污染源': '畜禽散养', **inflow, '修正说明': '无修正'})

    # 4. 面-水产养殖 (修正系数 1.0 -> 0.15)
    df = pd.read_excel(input_file, sheet_name='面-水产养殖')
    inflow = get_inflow_sum(df)
    # 水产养殖只有一个入河量列
    for col in df.columns:
        if '入河量' in str(col) and '系数' not in str(col):
            val = pd.to_numeric(df[col], errors='coerce').sum()
            inflow['COD'] = val * 0.15  # 系数从1.0改为0.15
    results.append({'污染源': '面-水产养殖', **inflow, '修正说明': '入河系数1.0→0.15'})

    # 5. 面-城市面源 (不修正)
    df = pd.read_excel(input_file, sheet_name='面-城市面源')
    inflow = get_inflow_sum(df)
    results.append({'污染源': '面-城市面源', **inflow, '修正说明': '无修正'})

    # 6. 面-城镇散排 (不修正)
    df = pd.read_excel(input_file, sheet_name='面-城镇散排')
    inflow = get_inflow_sum(df)
    results.append({'污染源': '面-城镇散排', **inflow, '修正说明': '无修正'})

    # 7. 规模畜禽养殖 (不修正)
    df = pd.read_excel(input_file, sheet_name='规模畜禽养殖（点数据，按面源统计）')
    inflow = get_inflow_sum(df)
    results.append({'污染源': '规模畜禽养殖', **inflow, '修正说明': '无修正'})

    # 8. 点-工业源 (剔除污水处理厂)
    df = pd.read_excel(input_file, sheet_name='点-工业源')

    # 找到污水处理厂并剔除
    wwtp_mask = df['企业名称'].str.contains('污水|水处理', na=False)
    df_ind_corrected = df[~wwtp_mask].copy()

    # 记录被剔除的数据
    df_wwtp = df[wwtp_mask]
    wwtp_inflow = get_inflow_sum(df_wwtp)

    report.append(f"\n工业源修正:")
    report.append(f"  原数据行数: {len(df)}")
    report.append(f"  剔除污水厂后: {len(df_ind_corrected)}")
    report.append(f"  剔除的污水厂入河量:")
    for p in pollutants:
        report.append(f"    {p}: {wwtp_inflow[p]:,.2f} kg")

    inflow = get_inflow_sum(df_ind_corrected)
    results.append({'污染源': '点-工业源(剔除污水厂)', **inflow, '修正说明': '剔除"中阳县宝洁城市污水处理有限公司"'})

    # 9. 点-集中式污染治理设施 (不修正)
    df = pd.read_excel(input_file, sheet_name='点-集中式污染治理设施')
    inflow = get_inflow_sum(df)
    results.append({'污染源': '点-集中式污染治理设施', **inflow, '修正说明': '无修正'})

    # 汇总
    df_results = pd.DataFrame(results)

    for p in pollutants:
        df_results[p] = pd.to_numeric(df_results[p], errors='coerce').fillna(0)

    total = {p: df_results[p].sum() for p in pollutants}

    # 监测值
    monitor = {'COD': 111861.56, '氨氮': 3902.69, '总氮': 49368.19, '总磷': 570.77}

    # 输出汇总表
    report.append("\n\n修正后各污染源入河量 (kg):")
    report.append("-" * 110)
    report.append(f"{'污染源':<35} {'COD':>15} {'氨氮':>12} {'总氮':>12} {'总磷':>12}")
    report.append("-" * 110)

    for idx, row in df_results.iterrows():
        report.append(f"{row['污染源']:<35} {row['COD']:>15,.2f} {row['氨氮']:>12,.2f} {row['总氮']:>12,.2f} {row['总磷']:>12,.2f}")

    report.append("-" * 110)
    report.append(f"{'总计':<35} {total['COD']:>15,.2f} {total['氨氮']:>12,.2f} {total['总氮']:>12,.2f} {total['总磷']:>12,.2f}")
    report.append(f"{'监测值':<35} {monitor['COD']:>15,.2f} {monitor['氨氮']:>12,.2f} {monitor['总氮']:>12,.2f} {monitor['总磷']:>12,.2f}")
    report.append("-" * 110)

    # 计算比值
    report.append("\n\n修正后计算值与监测值对比:")
    report.append("-" * 80)
    report.append(f"{'污染物':<10} {'修正后(kg)':>15} {'修正后(吨)':>12} {'监测值(吨)':>12} {'计算/监测':>12}")
    report.append("-" * 80)

    for p in pollutants:
        calc_kg = total[p]
        calc_ton = calc_kg / 1000
        mon_ton = monitor[p] / 1000
        ratio = calc_kg / monitor[p] if monitor[p] > 0 else 0
        report.append(f"{p:<10} {calc_kg:>15,.2f} {calc_ton:>12.2f} {mon_ton:>12.2f} {ratio:>12.2f}")

    report.append("-" * 80)

    # 对比修正前后
    report.append("\n\n" + "=" * 80)
    report.append("【第五部分】修正效果对比")
    report.append("=" * 80)

    # 原始计算值（未修正）
    original = {'COD': 438648.60, '氨氮': 6364.17, '总氮': 66252.92, '总磷': 39654.59}

    report.append("\n修正前后对比 (单位: 吨):")
    report.append("-" * 90)
    report.append(f"{'污染物':<10} {'原始值':>12} {'修正后':>12} {'监测值':>12} {'原/监测':>10} {'修正/监测':>10}")
    report.append("-" * 90)

    for p in pollutants:
        orig = original[p] / 1000
        corr = total[p] / 1000
        mon = monitor[p] / 1000
        ratio_orig = original[p] / monitor[p]
        ratio_corr = total[p] / monitor[p]
        report.append(f"{p:<10} {orig:>12.2f} {corr:>12.2f} {mon:>12.2f} {ratio_orig:>10.2f} {ratio_corr:>10.2f}")

    report.append("-" * 90)

    # 各污染源占比
    report.append("\n\n修正后各污染源贡献占比 (%):")
    report.append("-" * 90)
    report.append(f"{'污染源':<35} {'COD%':>12} {'氨氮%':>12} {'总氮%':>12} {'总磷%':>12}")
    report.append("-" * 90)

    for idx, row in df_results.iterrows():
        pct = {p: (row[p] / total[p] * 100) if total[p] > 0 else 0 for p in pollutants}
        report.append(f"{row['污染源']:<35} {pct['COD']:>12.1f} {pct['氨氮']:>12.1f} {pct['总氮']:>12.1f} {pct['总磷']:>12.1f}")

    report.append("-" * 90)

    # 结论
    report.append("\n\n" + "=" * 80)
    report.append("【结论】")
    report.append("=" * 80)

    report.append("""
1. 核查发现的问题:
   - "中阳县宝洁城市污水处理有限公司"被错误分类到"点-工业源"
   - 该污水厂贡献了工业源98%的总磷入河量(34,693 kg)
   - 污水处理厂应属于"集中式污染治理设施"，不应计入工业源

2. 修正措施:
   - 从"点-工业源"中剔除该污水处理厂
   - 农村生活污染源入河系数: 0.1 → 0.4
   - 水产养殖入河系数: 1.0 → 0.15

3. 修正效果:
""")

    for p in pollutants:
        ratio_orig = original[p] / monitor[p]
        ratio_corr = total[p] / monitor[p]
        improvement = "改善" if ratio_corr < ratio_orig else "未改善"
        report.append(f"   {p}: {ratio_orig:.2f}倍 → {ratio_corr:.2f}倍 ({improvement})")

    report.append("""
4. 后续建议:
   - 核实"中阳县宝洁城市污水处理有限公司"与"点-集中式设施"中的设施是否重复
   - 如果是同一设施，确认哪份数据正确
   - 规模畜禽养殖仍是总磷主要来源，建议进一步核查其产排污系数
""")

    # 写入报告
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    # 导出Excel
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # 修正后汇总
        df_results_total = pd.concat([
            df_results,
            pd.DataFrame([{'污染源': '总计', **total, '修正说明': ''}])
        ], ignore_index=True)
        df_results_total.to_excel(writer, sheet_name='修正后入河量(kg)', index=False)

        # 对比表
        comparison = []
        for p in pollutants:
            comparison.append({
                '污染物': p,
                '原始值(kg)': original[p],
                '修正后(kg)': total[p],
                '监测值(kg)': monitor[p],
                '原始/监测': original[p] / monitor[p],
                '修正/监测': total[p] / monitor[p]
            })
        pd.DataFrame(comparison).to_excel(writer, sheet_name='修正前后对比', index=False)

        # 修正明细
        corrections = [
            {'修正项': '面-农村生活污染源', '修正内容': '基础入河系数', '修正前': 0.1, '修正后': 0.4, '依据': '指南4.4节F/G类'},
            {'修正项': '面-水产养殖', '修正内容': '入河系数', '修正前': 1.0, '修正后': 0.15, '依据': '指南4.4节A/B/C类'},
            {'修正项': '点-工业源', '修正内容': '剔除污水处理厂', '修正前': '包含', '修正后': '剔除', '依据': '分类错误，污水厂应属集中式设施'},
        ]
        pd.DataFrame(corrections).to_excel(writer, sheet_name='修正明细', index=False)

if __name__ == "__main__":
    main()
