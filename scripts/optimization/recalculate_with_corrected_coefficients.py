#!/usr/bin/env python3
"""
根据技术指南修正系数后重新核算入河污染物总量

修正内容:
1. 面-农村生活污染源: 基础入河系数 0.1 → 0.4 (指南F/G类: 0.3~0.5)
2. 面-水产养殖: 入河系数 1.0 → 0.15 (指南A/B/C类: 10%~20%)
3. 点-工业源: 总磷数据需核查（当前值异常偏高）
"""

import pandas as pd
import numpy as np
from pathlib import Path

def get_pollutant_type(col_name):
    """识别污染物类型"""
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

def get_inflow_sum(df, pollutants_init=None):
    """获取各污染物入河量总和"""
    if pollutants_init is None:
        pollutants_init = {'COD': 0, '氨氮': 0, '总氮': 0, '总磷': 0}
    result = pollutants_init.copy()

    for col in df.columns:
        if '入河量' in str(col) and '系数' not in str(col):
            values = pd.to_numeric(df[col], errors='coerce')
            total = values.sum()
            pollutant = get_pollutant_type(col)
            if pollutant and total > 0:
                result[pollutant] += total
    return result

def main():
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / 'data' / 'data(1).xlsx'
    output_file = base_dir / 'output' / '入河污染物总量_修正后.xlsx'
    report_file = base_dir / 'output' / '系数修正核算报告.txt'

    pollutants = ['COD', '氨氮', '总氮', '总磷']

    results_before = []
    results_after = []
    correction_details = []

    report = []
    report.append("=" * 100)
    report.append("根据《水污染源排放清单编制技术指南》修正系数后重新核算")
    report.append("=" * 100)

    # ========== 1. 面-农村生活污染源 ==========
    report.append("\n" + "=" * 80)
    report.append("【修正1】面-农村生活污染源 - 基础入河系数")
    report.append("=" * 80)

    df_rural = pd.read_excel(input_file, sheet_name='面-农村生活污染源')
    report.append(f"数据行数: {len(df_rural)}")

    # 找到基础入河系数列
    coef_col = '基础入河/湖系数（干流、湖库流经0.2，一级支流0.15，二级及以下支流0.1）'

    if coef_col in df_rural.columns:
        # 获取实际系数值（取众数）
        coef_values = pd.to_numeric(df_rural[coef_col], errors='coerce').dropna()
        old_coef = coef_values.mode().iloc[0] if len(coef_values) > 0 else 0.1
        new_coef = 0.4  # 指南F/G类中值

        report.append(f"\n修正前系数: {old_coef}")
        report.append(f"修正后系数: {new_coef}")
        report.append(f"修正依据: 指南4.4节 F/G类排放去向入河系数0.3~0.5，取中值0.4")

        # 计算修正比例
        correction_ratio = new_coef / old_coef if old_coef > 0 else 1.0

        # 获取修正前入河量
        rural_before = {'污染源': '面-农村生活污染源'}
        rural_before.update(get_inflow_sum(df_rural))

        # 计算修正后入河量
        rural_after = {'污染源': '面-农村生活污染源'}
        for p in pollutants:
            rural_after[p] = rural_before[p] * correction_ratio

        report.append(f"\n入河量变化 (修正比例: {correction_ratio:.1f}x):")
        for p in pollutants:
            if rural_before[p] > 0:
                report.append(f"  {p}: {rural_before[p]:,.2f} kg -> {rural_after[p]:,.2f} kg")

        results_before.append(rural_before)
        results_after.append(rural_after)
        correction_details.append({
            '污染源': '面-农村生活污染源',
            '修正项': '基础入河系数',
            '修正前': old_coef,
            '修正后': new_coef,
            '修正比例': correction_ratio,
            '依据': '指南4.4节 F/G类0.3~0.5'
        })
    else:
        report.append(f"警告: 未找到基础入河系数列")

    # ========== 2. 面-农业面源 (不修正) ==========
    df_agri = pd.read_excel(input_file, sheet_name='面-农业面源')
    agri_result = {'污染源': '面-农业面源'}
    agri_result.update(get_inflow_sum(df_agri))
    results_before.append(agri_result.copy())
    results_after.append(agri_result.copy())

    # ========== 3. 畜禽散养 (不修正) ==========
    df_livestock_free = pd.read_excel(input_file, sheet_name='畜禽散养（点数据，按面源统计）')
    livestock_free_result = {'污染源': '畜禽散养'}
    livestock_free_result.update(get_inflow_sum(df_livestock_free))
    results_before.append(livestock_free_result.copy())
    results_after.append(livestock_free_result.copy())

    # ========== 4. 面-水产养殖 ==========
    report.append("\n" + "=" * 80)
    report.append("【修正2】面-水产养殖 - 入河系数")
    report.append("=" * 80)

    df_aqua = pd.read_excel(input_file, sheet_name='面-水产养殖')
    report.append(f"数据行数: {len(df_aqua)}")

    # 找到入河系数列
    coef_col = '入河系数'

    if coef_col in df_aqua.columns:
        coef_values = pd.to_numeric(df_aqua[coef_col], errors='coerce').dropna()
        old_coef = coef_values.mode().iloc[0] if len(coef_values) > 0 else 1.0
        new_coef = 0.15  # 指南A/B/C类中值

        report.append(f"\n修正前系数: {old_coef}")
        report.append(f"修正后系数: {new_coef}")
        report.append(f"修正依据: 指南4.4节 A/B/C类排放去向入河系数10%~20%，取中值15%")

        correction_ratio = new_coef / old_coef if old_coef > 0 else 1.0

        # 获取修正前入河量
        aqua_before = {'污染源': '面-水产养殖'}
        aqua_before.update(get_inflow_sum(df_aqua))

        # 水产养殖只有一个入河量列，按COD计
        inflow_col = '入河量（千克）'
        if inflow_col in df_aqua.columns:
            inflow_val = pd.to_numeric(df_aqua[inflow_col], errors='coerce').sum()
            aqua_before['COD'] = inflow_val

        # 计算修正后入河量
        aqua_after = {'污染源': '面-水产养殖'}
        for p in pollutants:
            aqua_after[p] = aqua_before.get(p, 0) * correction_ratio

        report.append(f"\n入河量变化 (修正比例: {correction_ratio:.2f}x):")
        for p in pollutants:
            if aqua_before.get(p, 0) > 0:
                report.append(f"  {p}: {aqua_before[p]:,.2f} kg -> {aqua_after[p]:,.2f} kg")

        results_before.append(aqua_before)
        results_after.append(aqua_after)
        correction_details.append({
            '污染源': '面-水产养殖',
            '修正项': '入河系数',
            '修正前': old_coef,
            '修正后': new_coef,
            '修正比例': correction_ratio,
            '依据': '指南4.4节 A/B/C类10%~20%'
        })

    # ========== 5. 面-城市面源 (不修正) ==========
    df_urban = pd.read_excel(input_file, sheet_name='面-城市面源')
    urban_result = {'污染源': '面-城市面源'}
    urban_result.update(get_inflow_sum(df_urban))
    results_before.append(urban_result.copy())
    results_after.append(urban_result.copy())

    # ========== 6. 面-城镇散排 (不修正) ==========
    df_township = pd.read_excel(input_file, sheet_name='面-城镇散排')
    township_result = {'污染源': '面-城镇散排'}
    township_result.update(get_inflow_sum(df_township))
    results_before.append(township_result.copy())
    results_after.append(township_result.copy())

    # ========== 7. 规模畜禽养殖 (不修正) ==========
    df_livestock_large = pd.read_excel(input_file, sheet_name='规模畜禽养殖（点数据，按面源统计）')
    livestock_large_result = {'污染源': '规模畜禽养殖'}
    livestock_large_result.update(get_inflow_sum(df_livestock_large))
    results_before.append(livestock_large_result.copy())
    results_after.append(livestock_large_result.copy())

    # ========== 8. 点-工业源 ==========
    report.append("\n" + "=" * 80)
    report.append("【核查】点-工业源 - 总磷数据异常")
    report.append("=" * 80)

    df_industrial = pd.read_excel(input_file, sheet_name='点-工业源')
    report.append(f"数据行数: {len(df_industrial)}")

    industrial_before = {'污染源': '点-工业源'}
    industrial_before.update(get_inflow_sum(df_industrial))

    industrial_after = industrial_before.copy()

    report.append("\n原始入河量数据:")
    for p in pollutants:
        if industrial_before.get(p, 0) > 0:
            report.append(f"  {p}: {industrial_before[p]:,.2f} kg")

    # 检查总磷异常
    tp_value = industrial_before.get('总磷', 0)
    if tp_value > 1000:  # 明显异常
        corrected_tp = tp_value / 1000  # 假设单位错误
        report.append(f"\n总磷数据异常分析:")
        report.append(f"  原值: {tp_value:,.2f} kg")
        report.append(f"  监测值: 570.77 kg")
        report.append(f"  比值: {tp_value/570.77:.1f} 倍")
        report.append(f"  假设单位错误(吨->千克)，修正为: {corrected_tp:,.2f} kg")
        industrial_after['总磷'] = corrected_tp

        correction_details.append({
            '污染源': '点-工业源',
            '修正项': '总磷入河量(单位)',
            '修正前': tp_value,
            '修正后': corrected_tp,
            '修正比例': 0.001,
            '依据': '假设单位录入错误(吨->千克)'
        })

    results_before.append(industrial_before)
    results_after.append(industrial_after)

    # ========== 9. 点-集中式污染治理设施 (不修正) ==========
    df_centralized = pd.read_excel(input_file, sheet_name='点-集中式污染治理设施')
    centralized_result = {'污染源': '点-集中式污染治理设施'}
    centralized_result.update(get_inflow_sum(df_centralized))
    results_before.append(centralized_result.copy())
    results_after.append(centralized_result.copy())

    # ========== 汇总计算 ==========
    report.append("\n" + "=" * 100)
    report.append("【汇总】修正前后入河污染物总量对比")
    report.append("=" * 100)

    df_before = pd.DataFrame(results_before)
    df_after = pd.DataFrame(results_after)

    # 确保所有列都是数值型
    for p in pollutants:
        df_before[p] = pd.to_numeric(df_before[p], errors='coerce').fillna(0)
        df_after[p] = pd.to_numeric(df_after[p], errors='coerce').fillna(0)

    # 计算总量
    total_before = {p: df_before[p].sum() for p in pollutants}
    total_after = {p: df_after[p].sum() for p in pollutants}

    # 监测值
    monitor_values = {
        'COD': 111861.56,
        '氨氮': 3902.69,
        '总氮': 49368.19,
        '总磷': 570.77
    }

    report.append("\n单位: 千克 (kg)")
    report.append("\n" + "-" * 100)
    report.append(f"{'污染物':<10} {'修正前':>15} {'修正后':>15} {'变化':>15} {'监测值':>15} {'修正后/监测':>12}")
    report.append("-" * 100)

    for p in pollutants:
        before = total_before[p]
        after = total_after[p]
        change = after - before
        monitor = monitor_values[p]
        ratio = after / monitor if monitor > 0 else 0

        change_str = f"+{change:,.0f}" if change > 0 else f"{change:,.0f}"
        report.append(f"{p:<10} {before:>15,.2f} {after:>15,.2f} {change_str:>15} {monitor:>15,.2f} {ratio:>12.2f}")

    report.append("-" * 100)

    # 转换为吨
    report.append("\n单位: 吨 (t)")
    report.append("\n" + "-" * 100)
    report.append(f"{'污染物':<10} {'修正前':>15} {'修正后':>15} {'监测值':>15} {'修正后/监测':>12}")
    report.append("-" * 100)

    for p in pollutants:
        before = total_before[p] / 1000
        after = total_after[p] / 1000
        monitor = monitor_values[p] / 1000
        ratio = (after / monitor) if monitor > 0 else 0
        report.append(f"{p:<10} {before:>15.2f} {after:>15.2f} {monitor:>15.2f} {ratio:>12.2f}")

    report.append("-" * 100)

    # ========== 各污染源详细对比 ==========
    report.append("\n" + "=" * 100)
    report.append("【详细】各污染源入河量 (修正后)")
    report.append("=" * 100)

    report.append("\n单位: 千克 (kg)")
    report.append("-" * 110)
    report.append(f"{'污染源':<35} {'COD':>15} {'氨氮':>15} {'总氮':>15} {'总磷':>15}")
    report.append("-" * 110)

    for idx, row in df_after.iterrows():
        source = row['污染源']
        report.append(f"{source:<35} {row['COD']:>15,.2f} {row['氨氮']:>15,.2f} {row['总氮']:>15,.2f} {row['总磷']:>15,.2f}")

    report.append("-" * 110)
    report.append(f"{'总计':<35} {total_after['COD']:>15,.2f} {total_after['氨氮']:>15,.2f} {total_after['总氮']:>15,.2f} {total_after['总磷']:>15,.2f}")
    report.append(f"{'监测值':<35} {monitor_values['COD']:>15,.2f} {monitor_values['氨氮']:>15,.2f} {monitor_values['总氮']:>15,.2f} {monitor_values['总磷']:>15,.2f}")
    report.append("-" * 110)

    # ========== 占比分析 ==========
    report.append("\n" + "=" * 100)
    report.append("【占比】各污染源贡献率 (修正后)")
    report.append("=" * 100)

    report.append("\n" + "-" * 90)
    report.append(f"{'污染源':<35} {'COD%':>12} {'氨氮%':>12} {'总氮%':>12} {'总磷%':>12}")
    report.append("-" * 90)

    for idx, row in df_after.iterrows():
        source = row['污染源']
        pct_cod = (row['COD'] / total_after['COD'] * 100) if total_after['COD'] > 0 else 0
        pct_nh3 = (row['氨氮'] / total_after['氨氮'] * 100) if total_after['氨氮'] > 0 else 0
        pct_tn = (row['总氮'] / total_after['总氮'] * 100) if total_after['总氮'] > 0 else 0
        pct_tp = (row['总磷'] / total_after['总磷'] * 100) if total_after['总磷'] > 0 else 0
        report.append(f"{source:<35} {pct_cod:>12.1f} {pct_nh3:>12.1f} {pct_tn:>12.1f} {pct_tp:>12.1f}")

    report.append("-" * 90)

    # ========== 结论 ==========
    report.append("\n" + "=" * 100)
    report.append("【结论】")
    report.append("=" * 100)

    report.append("\n1. 修正内容:")
    for detail in correction_details:
        report.append(f"   - {detail['污染源']}: {detail['修正项']} {detail['修正前']} -> {detail['修正后']} ({detail['依据']})")

    report.append("\n2. 修正效果:")
    for p in pollutants:
        before = total_before[p] / 1000
        after = total_after[p] / 1000
        monitor = monitor_values[p] / 1000
        ratio_before = total_before[p] / monitor_values[p] if monitor_values[p] > 0 else 0
        ratio_after = total_after[p] / monitor_values[p] if monitor_values[p] > 0 else 0
        report.append(f"   {p}: {before:.2f}吨 -> {after:.2f}吨 (监测值{monitor:.2f}吨)")
        report.append(f"        计算/监测比值: {ratio_before:.2f} -> {ratio_after:.2f}")

    report.append("\n3. 评价:")
    for p in pollutants:
        ratio = total_after[p] / monitor_values[p] if monitor_values[p] > 0 else 0
        if 0.8 <= ratio <= 1.5:
            report.append(f"   - {p}: 修正后计算值与监测值接近，较为合理 (比值={ratio:.2f})")
        elif ratio < 0.8:
            report.append(f"   - {p}: 修正后计算值偏低 (比值={ratio:.2f})")
        else:
            report.append(f"   - {p}: 修正后计算值仍偏高 (比值={ratio:.2f})，需进一步核查")

    report.append("\n4. 后续建议:")
    report.append("   - 核实工业源总磷原始数据的单位和计算过程")
    report.append("   - 核实农村生活污水的实际排放去向类型(F或G)")
    report.append("   - 如COD计算值仍偏高，可能存在其他系数需要调整")

    # 写入报告文件
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    # 导出Excel
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Sheet 1: 修正前
        df_before_total = pd.concat([df_before, pd.DataFrame([{'污染源': '总计', **total_before}])], ignore_index=True)
        df_before_total.to_excel(writer, sheet_name='修正前入河量(kg)', index=False)

        # Sheet 2: 修正后
        df_after_total = pd.concat([df_after, pd.DataFrame([{'污染源': '总计', **total_after}])], ignore_index=True)
        df_after_total.to_excel(writer, sheet_name='修正后入河量(kg)', index=False)

        # Sheet 3: 对比
        comparison = []
        for p in pollutants:
            comparison.append({
                '污染物': p,
                '修正前(kg)': total_before[p],
                '修正后(kg)': total_after[p],
                '监测值(kg)': monitor_values[p],
                '修正前/监测': total_before[p] / monitor_values[p] if monitor_values[p] > 0 else 0,
                '修正后/监测': total_after[p] / monitor_values[p] if monitor_values[p] > 0 else 0
            })
        pd.DataFrame(comparison).to_excel(writer, sheet_name='修正前后对比', index=False)

        # Sheet 4: 修正明细
        pd.DataFrame(correction_details).to_excel(writer, sheet_name='修正明细', index=False)

    return report_file, output_file

if __name__ == "__main__":
    main()
