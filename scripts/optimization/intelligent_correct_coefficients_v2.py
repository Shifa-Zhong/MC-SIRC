#!/usr/bin/env python3
"""
智能系数修正脚本 V2
根据用户反馈优化：
1. 面-农村生活污染源的COD使用'排放量'列
2. 面-城市面源修正Cj系数（针对4个功能区）
3. 点-工业源没有总氮（跳过）
"""

import pandas as pd
import numpy as np
from pathlib import Path
import openpyxl

# 监测数据（吨）
MONITOR_VALUES = {
    'COD': 111.861560,
    '氨氮': 3.902692,
    '总氮': 49.368193,
    '总磷': 0.570772
}

# Sheet名称映射
SHEET_NAME_MAPPING = {
    '面-农村生活污染源': '面-农村生活污染源',
    '面-农业面源': '面-农业面源',
    '畜禽散养（点数据，按面源统计）': '畜禽散养（点数据，按面源统计）',
    '面-水产养殖': '面-水产养殖',
    '面-城市面源': '面-城市面源',
    '面-城镇散排': '面-城镇散排',
    '规模畜禽养殖（点数据，按面源统计）': '规模畜禽养殖（点数据，按面源统计）',
    '点-工业源': '点-工业源',
    '点-集中式污染治理设施': '点-集中式污染治理设施'
}


def calculate_correction_factors(df_inflow):
    """
    计算每个污染源对每个污染物的修正因子
    """
    pollutants = ['COD', '氨氮', '总氮', '总磷']
    correction_factors = {}

    for pollutant in pollutants:
        print(f"\n计算 {pollutant} 的修正因子...")
        print("-" * 80)

        df_data = df_inflow[df_inflow['污染源'] != '总计'].copy()
        df_data['贡献值'] = df_data[pollutant]
        total = df_data['贡献值'].sum()

        total_ton = total / 1000
        monitor_ton = MONITOR_VALUES[pollutant]
        global_factor = monitor_ton / total_ton if total_ton > 0 else 1.0

        print(f"计算总量: {total_ton:.2f} 吨")
        print(f"监测值:   {monitor_ton:.2f} 吨")
        print(f"全局修正因子: {global_factor:.4f}")
        print()

        df_data['占比'] = (df_data['贡献值'] / total * 100) if total > 0 else 0

        source_factors = {}

        for idx, row in df_data.iterrows():
            source = row['污染源']
            contribution_ratio = row['占比']

            # 根据贡献度确定修正幅度（V4优化：进一步降低修正强度，提高温和性）
            if contribution_ratio > 80:
                severity_factor = 0.80
            elif contribution_ratio > 60:
                severity_factor = 0.85
            elif contribution_ratio > 40:
                severity_factor = 0.90
            elif contribution_ratio > 20:
                severity_factor = 0.95
            else:
                severity_factor = 1.0

            source_factor = global_factor * severity_factor

            source_factors[source] = {
                '修正因子': source_factor,
                '贡献占比': contribution_ratio,
                '严重程度因子': severity_factor
            }

            print(f"  {source:30s} - 占比:{contribution_ratio:6.2f}% - 严重程度:{severity_factor:.2f} - 修正因子:{source_factor:.4f}")

        correction_factors[pollutant] = source_factors

    return correction_factors


def apply_correction_to_city_surface(df, correction_factors):
    """
    特殊处理：面-城市面源
    修正Cj系数（针对4个功能区）并重新计算入河量
    """
    df_corrected = df.copy()

    source_name = '面-城市面源'
    corrections_applied = {}

    # 污染物别名映射
    pollutant_mapping = {
        'COD': '化学需氧量',
        '氨氮': '氨氮',
        '总氮': '总氮',
        '总磷': '总磷'
    }

    print(f"  特殊处理：修正Cj系数（4个功能区）并重新计算入河量")

    for pollutant, cj_name in pollutant_mapping.items():
        if pollutant not in correction_factors:
            continue

        if source_name not in correction_factors[pollutant]:
            continue

        factor_info = correction_factors[pollutant][source_name]
        factor = factor_info['修正因子']

        # 查找该污染物的4个Cj列
        cj_cols = {}
        for area in ['商业区', '工业区', '生活区', '交通区']:
            for col in df.columns:
                if f'Cj{cj_name}' in str(col) and area in str(col):
                    cj_cols[area] = col
                    break

        if not cj_cols:
            print(f"  ⚠️  未找到{pollutant}的Cj列")
            continue

        # 为每个功能区创建修正后的Cj列
        for area, cj_col in cj_cols.items():
            corrected_cj_col = f'修正后Cj{cj_name}-{area}'
            # 修正Cj = 原Cj × 修正因子
            original_cj = pd.to_numeric(df[cj_col], errors='coerce').fillna(0)
            df_corrected[corrected_cj_col] = original_cj * factor

        # 重新计算入河量
        # 入河量(kg) = [Σ(A区域 × CF×Ψ×F×0.001 × Cj区域)] × 1000 × 雨水管网系数 × 距离系数

        # 查找面积列
        area_cols = {
            '商业区': 'A商业区面积统计(km2)',
            '工业区': 'A工业区面积统计',
            '生活区': 'A生活区面积统计',
            '交通区': 'A交通区面积统计'
        }

        # CF×Ψ×F×0.001列
        cf_col = 'CF×Ψ×F×0.001'

        # 系数列
        rainwater_coef_col = '雨水管网修正系数（按雨水收集管网覆盖率30-50%之间计算，修正系数取0.8）'
        distance_coef_col = '距离修正系数（按距离在1-10km之间计算，修正系数取0.9）'

        # 检查所有必需的列是否存在
        if cf_col not in df.columns:
            print(f"  ⚠️  未找到 {cf_col} 列")
            continue

        if rainwater_coef_col not in df.columns or distance_coef_col not in df.columns:
            print(f"  ⚠️  未找到系数列")
            continue

        # 计算修正后入河量
        corrected_inflow_col = f'修正后入河量-{pollutant}(千克)'

        # 初始化入河量为0
        inflow = pd.Series(0.0, index=df.index)

        # 累加各功能区的贡献
        for area, area_col in area_cols.items():
            if area_col in df.columns and area in cj_cols:
                corrected_cj_col = f'修正后Cj{cj_name}-{area}'

                # A区域 × CF×Ψ×F×0.001 × 修正后Cj区域
                area_value = pd.to_numeric(df[area_col], errors='coerce').fillna(0)
                cf_value = pd.to_numeric(df[cf_col], errors='coerce').fillna(0)
                cj_value = pd.to_numeric(df_corrected[corrected_cj_col], errors='coerce').fillna(0)

                inflow += area_value * cf_value * cj_value

        # × 1000 (转换为kg)
        inflow = inflow * 1000

        # × 雨水管网系数 × 距离系数
        rainwater_coef = pd.to_numeric(df[rainwater_coef_col], errors='coerce').fillna(1.0)
        distance_coef = pd.to_numeric(df[distance_coef_col], errors='coerce').fillna(1.0)

        inflow = inflow * rainwater_coef * distance_coef

        df_corrected[corrected_inflow_col] = inflow

        corrections_applied[pollutant] = {
            '修正因子': factor,
            '贡献占比': factor_info['贡献占比'],
            'Cj列数': len(cj_cols),
            '修正后入河量列': corrected_inflow_col
        }

        print(f"  {pollutant}: 修正了{len(cj_cols)}个Cj列，修正因子 {factor:.4f}，重新计算入河量")

    return df_corrected, corrections_applied


def apply_correction_to_normal_sheet(df, sheet_name, correction_factors):
    """
    常规处理：修正基础入河系数
    """
    df_corrected = df.copy()

    if sheet_name not in SHEET_NAME_MAPPING:
        print(f"  ⚠️ 未找到污染源映射，跳过")
        return df_corrected, {}

    source_name = SHEET_NAME_MAPPING[sheet_name]

    # 识别基础入河系数列
    base_coef_col = None
    coef_cols = [col for col in df.columns if '系数' in str(col)]

    for col in coef_cols:
        col_str = str(col)
        if '基础入河' in col_str or '入河/湖系数' in col_str or '入河系数' in col_str:
            if '地形' not in col_str and '降水' not in col_str and '距离' not in col_str and '温度' not in col_str and '渠道' not in col_str and '雨水' not in col_str:
                base_coef_col = col
                break

    # 如果没找到，尝试其他系数
    if not base_coef_col:
        for col in coef_cols:
            col_str = str(col)
            if '渠道修正系数' in col_str or '雨水管网修正系数' in col_str:
                if '（' not in col_str:
                    base_coef_col = col
                    break

    if not base_coef_col and coef_cols:
        for col in coef_cols:
            if '（' not in str(col):
                base_coef_col = col
                break

    if not base_coef_col:
        print(f"  ⚠️ 未找到基础入河系数列，跳过")
        return df_corrected, {}

    print(f"  基础入河系数列: {base_coef_col}")

    # 识别其他系数列
    other_coef_cols = []
    for col in coef_cols:
        if col != base_coef_col:
            col_str = str(col)
            if '（' not in col_str and any(keyword in col_str for keyword in ['地形', '降水', '距离', '温度', '入河/湖系数经验值']):
                other_coef_cols.append(col)

    print(f"  其他系数列: {other_coef_cols}")

    corrections_applied = {}

    # 为每个污染物应用修正
    for pollutant in ['COD', '氨氮', '总氮', '总磷']:
        if pollutant not in correction_factors:
            continue

        if source_name not in correction_factors[pollutant]:
            continue

        factor_info = correction_factors[pollutant][source_name]
        factor = factor_info['修正因子']

        # 创建修正后的系数列
        corrected_coef_col = f'修正后入河系数-{pollutant}'
        base_coef = pd.to_numeric(df[base_coef_col], errors='coerce')
        df_corrected[corrected_coef_col] = base_coef * factor

        corrections_applied[pollutant] = {
            '修正因子': factor,
            '贡献占比': factor_info['贡献占比'],
            '修正后系数列': corrected_coef_col
        }

        print(f"  {pollutant}: 修正因子 {factor:.4f} (占比 {factor_info['贡献占比']:.2f}%)")

    return df_corrected, corrections_applied


def recalculate_inflow(df, sheet_name, corrections_applied):
    """
    重新计算入河量
    """
    if not corrections_applied:
        return df

    df_recalc = df.copy()

    # 识别系数列
    coef_cols = [col for col in df.columns if '系数' in str(col)]
    base_coef_col = None
    for col in coef_cols:
        col_str = str(col)
        if '基础入河' in col_str or '入河/湖系数' in col_str or '入河系数' in col_str:
            if '地形' not in col_str and '降水' not in col_str and '距离' not in col_str:
                base_coef_col = col
                break

    if not base_coef_col:
        for col in coef_cols:
            if '渠道修正系数' in str(col) and '（' not in str(col):
                base_coef_col = col
                break

    other_coef_cols = []
    for col in coef_cols:
        if col != base_coef_col:
            col_str = str(col)
            if '（' not in col_str and any(keyword in col_str for keyword in ['地形', '降水', '距离', '温度', '入河/湖系数经验值']):
                other_coef_cols.append(col)

    # 污染物别名
    pollutant_aliases = {
        'COD': ['COD', '化学需氧量'],
        '氨氮': ['氨氮'],
        '总氮': ['总氮'],
        '总磷': ['总磷']
    }

    for pollutant, info in corrections_applied.items():
        corrected_coef_col = info.get('修正后系数列')
        if not corrected_coef_col:
            continue

        # 查找排放量列
        emission_col = None
        unit_factor = 1.0

        aliases = pollutant_aliases.get(pollutant, [pollutant])

        # 特殊处理：面-农村生活污染源的COD
        if sheet_name == '面-农村生活污染源' and pollutant == 'COD':
            if '排放量' in df.columns:
                emission_col = '排放量'
                unit_factor = 1.0
                print(f"  特殊处理：使用'排放量'列作为COD排放量")

        # 常规查找
        if not emission_col:
            for alias in aliases:
                # 优先千克
                for col in df.columns:
                    col_str = str(col)
                    if '排放量' in col_str and alias in col_str and '千克' in col_str:
                        emission_col = col
                        unit_factor = 1.0
                        break
                if emission_col:
                    break

                # 污染物排放量-污染物格式
                for col in df.columns:
                    col_str = str(col)
                    if '污染物排放量' in col_str and alias in col_str:
                        emission_col = col
                        unit_factor = 1.0
                        break
                if emission_col:
                    break

                # 排放量Qj格式
                for col in df.columns:
                    col_str = str(col)
                    if '排放量Qj' in col_str and alias in col_str:
                        emission_col = col
                        unit_factor = 1.0
                        break
                if emission_col:
                    break

                # 排放量（千克）格式
                for col in df.columns:
                    col_str = str(col)
                    if '排放量（千克）' in col_str and alias in col_str:
                        emission_col = col
                        unit_factor = 1.0
                        break
                if emission_col:
                    break

                # 吨单位
                for col in df.columns:
                    col_str = str(col)
                    if '排放量' in col_str and alias in col_str and '吨' in col_str and '千克' not in col_str:
                        emission_col = col
                        unit_factor = 1000.0
                        break
                if emission_col:
                    break

        if not emission_col:
            print(f"  ⚠️  未找到 {pollutant} 的排放量列")
            continue

        # 计算修正后的入河量
        corrected_inflow_col = f'修正后入河量-{pollutant}(千克)'

        inflow = pd.to_numeric(df_recalc[emission_col], errors='coerce').fillna(0).copy()
        inflow = inflow * unit_factor

        # 应用修正后的系数
        corrected_coef = pd.to_numeric(df_recalc[corrected_coef_col], errors='coerce').fillna(0)
        inflow = inflow * corrected_coef

        # 应用其他系数
        for other_coef_col in other_coef_cols:
            other_coef = pd.to_numeric(df_recalc[other_coef_col], errors='coerce').fillna(1.0)
            inflow = inflow * other_coef

        df_recalc[corrected_inflow_col] = inflow

        print(f"  重新计算: {corrected_inflow_col} (从 {emission_col})")

    return df_recalc


def main():
    print("=" * 100)
    print("智能系数修正脚本 V2")
    print("=" * 100)

    base_dir = Path(__file__).parent.parent
    input_file = base_dir / 'data' / 'data(1).xlsx'
    output_file = base_dir / 'output' / 'data_corrected_intelligent_v2.xlsx'
    inflow_stats_file = base_dir / 'output' / '入河污染物总量统计.xlsx'

    # 步骤1：计算修正因子
    print("\n【步骤1】计算修正因子")
    print("=" * 100)

    df_inflow_stats = pd.read_excel(inflow_stats_file)
    correction_factors = calculate_correction_factors(df_inflow_stats)

    # 步骤2：应用修正
    print("\n" + "=" * 100)
    print("【步骤2】应用修正因子到各个sheet")
    print("=" * 100)

    xl = pd.ExcelFile(input_file)
    sheet_names = [name for name in xl.sheet_names if name != '提取统计']

    all_stats = []

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for i, sheet_name in enumerate(sheet_names, 1):
            print(f"\n{i}. 处理: {sheet_name}")
            print("-" * 80)

            df = pd.read_excel(input_file, sheet_name=sheet_name, header=0)

            # 特殊处理面-城市面源
            if sheet_name == '面-城市面源':
                df_corrected, corrections = apply_correction_to_city_surface(df, correction_factors)
                df_final = df_corrected  # 城市面源已在函数内重新计算入河量
            else:
                df_corrected, corrections = apply_correction_to_normal_sheet(df, sheet_name, correction_factors)
                if corrections:
                    df_final = recalculate_inflow(df_corrected, sheet_name, corrections)
                else:
                    df_final = df_corrected

            df_final.to_excel(writer, sheet_name=sheet_name, index=False)

            all_stats.append({
                'Sheet名称': sheet_name,
                '原始列数': len(df.columns),
                '修正后列数': len(df_final.columns),
                '新增列数': len(df_final.columns) - len(df.columns),
                '修正的污染物': ', '.join(corrections.keys()) if corrections else '无'
            })

        # 添加统计
        print("\n添加统计sheet...")
        df_stats = pd.DataFrame(all_stats)
        df_stats.to_excel(writer, sheet_name='修正统计', index=False)

        # 添加修正因子说明
        factor_data = []
        factor_data.append(['污染源', '污染物', '修正因子', '贡献占比(%)', '说明'])

        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            for source, info in correction_factors[pollutant].items():
                factor = info['修正因子']
                ratio = info['贡献占比']
                if ratio > 50:
                    note = '贡献过大，重点修正'
                elif ratio > 30:
                    note = '贡献较大，较多修正'
                elif ratio > 15:
                    note = '贡献适中，适度修正'
                else:
                    note = '贡献合理，轻微修正'

                factor_data.append([source, pollutant, f'{factor:.4f}', f'{ratio:.2f}', note])

        df_factors = pd.DataFrame(factor_data[1:], columns=factor_data[0])
        df_factors.to_excel(writer, sheet_name='修正因子详情', index=False)

    print("\n" + "=" * 100)
    print("✓ 智能修正完成！")
    print("=" * 100)
    print(f"\n输出文件: {output_file.name}")
    print(f"包含 {len(sheet_names)} 个修正数据sheet + 2 个说明sheet")


if __name__ == "__main__":
    main()
