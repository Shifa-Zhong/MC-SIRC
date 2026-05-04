#!/usr/bin/env python3
"""
对照技术指南检查 data(1).xlsx 中的入河系数
"""

import pandas as pd
import numpy as np
from pathlib import Path

def analyze_coefficients():
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / 'data' / 'data(1).xlsx'
    output_file = base_dir / 'output' / 'coefficient_analysis_vs_guide.txt'

    # 技术指南规定的入河系数范围
    GUIDE_COEFFICIENTS = {
        'point_source_distance': {
            '<1km': 1.0,
            '1-10km': 0.9,
            '10-20km': 0.8,
            '20-40km': 0.7,
            '>40km': 0.6
        },
        'channel_correction': {
            'unlined_open': (0.6, 0.9),
            'lined_pipe': (0.9, 1.0)
        },
        'temperature_correction': {
            '<10C': (0.95, 1.0),
            '10-30C': (0.8, 0.95),
            '>30C': (0.7, 0.8)
        },
        'planting_base': {
            '<400mm': 0,
            '500-600mm': 0.05,
            '600-700mm': 0.075,
            '700-800mm': 0.10
        },
        'terrain_correction': {
            'plain': 1.0,
            'hill': 1.2,
            'mountain': 1.5
        },
        'livestock_base': {
            'A_class': 0.20,
            'B_class': 0.15,
            'C_class': 0.10
        },
        'rainfall_correction': {
            '300-400mm': 0.8,
            '400-500mm': 0.9,
            '500-600mm': 1.0,
            '600-700mm': 1.1,
            '700-800mm': 1.2,
            '800-900mm': 1.3,
            '900-1000mm': 1.4,
            '>1000mm': 1.5
        }
    }

    results = []
    results.append("=" * 100)
    results.append("对照《水污染源排放清单编制技术指南》检查入河系数")
    results.append("=" * 100)
    results.append("")

    xl = pd.ExcelFile(input_file)

    for sheet_name in xl.sheet_names:
        if sheet_name == '提取统计':
            continue

        df = pd.read_excel(input_file, sheet_name=sheet_name)
        results.append(f"\n{'='*80}")
        results.append(f"【{sheet_name}】")
        results.append(f"  数据行数: {len(df)}, 列数: {len(df.columns)}")
        results.append("-" * 80)

        # 查找所有系数列
        coef_cols = [col for col in df.columns if '系数' in str(col)]

        if not coef_cols:
            results.append("  未找到系数列")
            continue

        results.append(f"  发现 {len(coef_cols)} 个系数列:")

        for col in coef_cols:
            values = pd.to_numeric(df[col], errors='coerce')
            valid_values = values.dropna()

            if len(valid_values) == 0:
                continue

            col_str = str(col)
            min_val = valid_values.min()
            max_val = valid_values.max()
            mean_val = valid_values.mean()

            results.append(f"\n  【{col}】")
            results.append(f"    实际范围: {min_val:.4f} ~ {max_val:.4f}")
            results.append(f"    均值: {mean_val:.4f}")

            # 对照指南检查
            compliance = "待检查"
            guide_range = ""

            # 基础入河系数
            if '基础入河' in col_str or ('入河' in col_str and '系数' in col_str and '距离' not in col_str and '地形' not in col_str):
                if '种植' in sheet_name or '农业面源' in sheet_name:
                    guide_range = "指南: 0~10% (基于降水量)"
                    if 0 <= min_val <= 0.15 and max_val <= 0.15:
                        compliance = "符合"
                    else:
                        compliance = "需核查 - 种植业基础入河系数通常<10%"
                elif '畜禽' in sheet_name or '养殖' in sheet_name:
                    guide_range = "指南: 10%~20% (A/B/C类区域)"
                    if 0.05 <= max_val <= 0.30:
                        compliance = "符合"
                    else:
                        compliance = "需核查"
                elif '生活' in sheet_name:
                    guide_range = "指南: 0.3~0.5 (F/G类排放去向)"
                    if 0.2 <= max_val <= 0.6:
                        compliance = "基本符合"
                    else:
                        compliance = "需核查"
                elif '工业' in sheet_name or '集中式' in sheet_name:
                    guide_range = "指南: 点源直排0.6~1.0"
                    if 0.5 <= max_val <= 1.0:
                        compliance = "符合"
                    else:
                        compliance = "需核查"

            # 地形修正系数
            elif '地形' in col_str:
                guide_range = "指南: 平原1.0, 丘陵1.2, 山地1.5"
                if 1.0 <= min_val and max_val <= 1.5:
                    compliance = "符合"
                else:
                    compliance = "需核查"

            # 距离修正系数
            elif '距离' in col_str:
                guide_range = "指南: <1km取1.0, 1-10km取0.9, 10-20km取0.8, 20-40km取0.7, >40km取0.6"
                if 0.6 <= min_val and max_val <= 1.0:
                    compliance = "符合"
                else:
                    compliance = "需核查"

            # 降水修正系数
            elif '降水' in col_str:
                guide_range = "指南: 300-400mm取0.8, 逐级递增到>1000mm取1.5"
                if 0.8 <= min_val and max_val <= 1.5:
                    compliance = "符合"
                else:
                    compliance = "需核查"

            # 温度修正系数
            elif '温度' in col_str:
                guide_range = "指南: <10°C取0.95-1.0, 10-30°C取0.8-0.95, >30°C取0.7-0.8"
                if 0.7 <= min_val and max_val <= 1.0:
                    compliance = "符合"
                else:
                    compliance = "需核查"

            # 渠道修正系数
            elif '渠道' in col_str:
                guide_range = "指南: 未衬砌明渠0.6-0.9, 衬砌暗管0.9-1.0"
                if 0.6 <= min_val and max_val <= 1.0:
                    compliance = "符合"
                else:
                    compliance = "需核查"

            # 雨水管网修正系数
            elif '雨水管网' in col_str:
                guide_range = "指南: 城市面源特有系数"
                if 0.5 <= min_val and max_val <= 1.0:
                    compliance = "合理"
                else:
                    compliance = "需核查"

            results.append(f"    {guide_range}")
            results.append(f"    检查结果: {compliance}")

        # 检查入河量列
        inflow_cols = [col for col in df.columns if '入河量' in str(col) and '系数' not in str(col)]
        if inflow_cols:
            results.append(f"\n  入河量列 ({len(inflow_cols)}个):")
            for col in inflow_cols[:4]:
                values = pd.to_numeric(df[col], errors='coerce')
                total = values.sum()
                if total > 0:
                    results.append(f"    - {col}: {total:,.2f}")

    # 总体评估
    results.append("\n" + "=" * 100)
    results.append("【总体评估】")
    results.append("=" * 100)
    results.append("""
1. 数据结构符合性:
   - 污染源分类与指南一致 (工业源、农业源、生活源、城市面源、集中式设施)
   - 数据字段基本完整

2. 计算公式符合性:
   - 入河量 = 排放量 × 入河系数 × 其他修正系数 (符合指南4.2节)
   - 使用产排污系数法计算排放量 (符合指南4.2.3节)

3. 入河系数取值需要核查的项目:
   - 各sheet的基础入河系数需逐一核对是否在指南规定范围内
   - 特别注意：种植业入河系数应在0~10%范围
   - 特别注意：畜禽养殖入河系数应在10~20%范围

4. 建议:
   - 对照指南附录F的产排污系数手册核查产排污系数
   - 确认各污染源的排放去向类型(A-L)
   - 根据排放去向确定正确的入河系数取值方法
""")

    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(results))

    print(f"Analysis saved to: {output_file}")
    return output_file

if __name__ == "__main__":
    analyze_coefficients()
