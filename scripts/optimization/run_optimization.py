#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行系数优化（解决Windows编码问题）
"""

import sys
import io
from pathlib import Path

# 设置输出编码
output_file = Path(__file__).parent.parent / 'output' / 'optimization_result.txt'

class OutputRedirector:
    def __init__(self, file_path):
        self.file = open(file_path, 'w', encoding='utf-8')
        self.stdout = sys.stdout

    def write(self, text):
        self.file.write(text)
        # 尝试输出到终端（忽略编码错误）
        try:
            self.stdout.write(text)
        except:
            pass

    def flush(self):
        self.file.flush()
        self.stdout.flush()

    def close(self):
        self.file.close()

# 重定向输出
redirector = OutputRedirector(output_file)
sys.stdout = redirector

# 导入并运行优化模块
import pandas as pd
import numpy as np
from scipy.optimize import differential_evolution

# ============================================================================
# 数据定义
# ============================================================================

MONITOR_VALUES = {
    'COD': 111.861560,
    '氨氮': 3.902692,
    '总氮': 49.368193,
    '总磷': 0.570772
}

SOURCE_DATA = {
    'COD': {
        '面-农村生活污染源': 25490,
        '畜禽散养': 2850,
        '面-城市面源': 68940,
        '面-城镇散排': 5230,
        '规模畜禽养殖': 181300,
        '点-工业源': 80260,
        '点-集中式污染治理设施': 70570,
    },
    '氨氮': {
        '面-农村生活污染源': 380,
        '畜禽散养': 59,
        '面-城市面源': 220,
        '面-城镇散排': 930,
        '规模畜禽养殖': 2490,
        '点-工业源': 1200,
        '点-集中式污染治理设施': 1080,
    },
    '总氮': {
        '面-农村生活污染源': 3040,
        '面-农业面源': 1570,
        '畜禽散养': 270,
        '面-城市面源': 2510,
        '规模畜禽养殖': 10740,
        '点-集中式污染治理设施': 48690,
    },
    '总磷': {
        '面-农村生活污染源': 69,
        '面-农业面源': 240,
        '畜禽散养': 47,
        '面-城市面源': 170,
        '规模畜禽养殖': 2810,
        '点-工业源': 679,  # 排除异常企业后
        '点-集中式污染治理设施': 890,
    }
}


def calculate_total(source_data, factors):
    total = 0
    for source, emission in source_data.items():
        if emission > 0 and source in factors:
            total += emission * factors[source] / 1000
    return total


def objective_function(x, source_data, monitor_value, source_names,
                       lambda_reg=0.1, lambda_unknown=0.01):
    n_sources = len(source_names)
    factors = {source_names[i]: x[i] for i in range(n_sources)}
    unknown_source = x[n_sources]

    calculated = calculate_total(source_data, factors)
    error = (monitor_value - calculated - unknown_source) ** 2

    total_emission = sum(source_data.values())
    reg_factor = 0
    for i, source in enumerate(source_names):
        emission = source_data[source]
        weight = emission / total_emission if total_emission > 0 else 0
        reg_factor += weight * (x[i] - 1) ** 2

    reg_unknown = unknown_source ** 2

    return error + lambda_reg * reg_factor + lambda_unknown * reg_unknown


def optimize_single_pollutant(pollutant, source_data, monitor_value):
    active_sources = {k: v for k, v in source_data.items() if v > 0}
    source_names = list(active_sources.keys())
    n_sources = len(source_names)

    if n_sources == 0:
        return None

    original_total = sum(active_sources.values()) / 1000

    bounds = [(0.3, 1.5)] * n_sources
    max_unknown = max(0, monitor_value * 0.5)
    bounds.append((0, max_unknown))

    result = differential_evolution(
        objective_function,
        bounds=bounds,
        args=(active_sources, monitor_value, source_names, 0.1, 0.01),
        seed=42,
        maxiter=1000,
        tol=1e-8,
        polish=True
    )

    optimal_factors = {source_names[i]: result.x[i] for i in range(n_sources)}
    optimal_unknown = result.x[n_sources]
    corrected_total = calculate_total(active_sources, optimal_factors)

    return {
        '污染物': pollutant,
        '监测值(吨)': monitor_value,
        '原始计算值(吨)': original_total,
        '修正后计算值(吨)': corrected_total,
        '未知源(吨)': optimal_unknown,
        '修正+未知(吨)': corrected_total + optimal_unknown,
        '原始偏差(%)': (original_total - monitor_value) / monitor_value * 100,
        '修正后偏差(%)': (corrected_total + optimal_unknown - monitor_value) / monitor_value * 100,
        '未知源占比(%)': optimal_unknown / monitor_value * 100 if monitor_value > 0 else 0,
        '修正因子': optimal_factors,
        '源数据': active_sources
    }


def main():
    print("=" * 100)
    print("污染物入河系数优化 - 考虑未知源的约束优化方法")
    print("=" * 100)

    print("""
模型: 监测值 = Σ(排放量 × 修正因子) + 未知源
约束: 0.3 ≤ 修正因子 ≤ 1.5, 未知源 ≥ 0
""")

    all_results = []

    for pollutant in ['COD', '氨氮', '总氮', '总磷']:
        print(f"\n{'='*80}")
        print(f"优化 {pollutant}")
        print(f"{'='*80}")

        source_data = SOURCE_DATA[pollutant]
        monitor_value = MONITOR_VALUES[pollutant]

        total_calc = sum(source_data.values()) / 1000
        print(f"\n原始数据:")
        print(f"  监测值: {monitor_value:.2f} 吨")
        print(f"  计算值: {total_calc:.2f} 吨")
        print(f"  原始偏差: {(total_calc - monitor_value) / monitor_value * 100:+.1f}%")

        result = optimize_single_pollutant(pollutant, source_data, monitor_value)

        if result:
            all_results.append(result)

            print(f"\n优化结果:")
            print(f"  修正后计算值: {result['修正后计算值(吨)']:.2f} 吨")
            print(f"  未知源估计: {result['未知源(吨)']:.2f} 吨 ({result['未知源占比(%)']:.1f}%)")
            print(f"  总计: {result['修正+未知(吨)']:.2f} 吨")
            print(f"  修正后偏差: {result['修正后偏差(%)']:+.1f}%")

            print(f"\n各污染源修正因子:")
            print(f"  {'污染源':<25} {'原始(kg)':>12} {'修正因子':>10} {'修正后(kg)':>12} {'修正幅度':>10}")
            print(f"  {'-'*75}")

            for source, factor in result['修正因子'].items():
                orig = source_data[source]
                corrected = orig * factor
                change = (factor - 1) * 100
                print(f"  {source:<25} {orig:>12,.0f} {factor:>10.3f} {corrected:>12,.0f} {change:>+9.1f}%")

    # 总结
    print("\n" + "=" * 100)
    print("优化结果总结")
    print("=" * 100)

    print(f"\n{'污染物':<8} {'监测值':>10} {'原始计算':>10} {'修正后':>10} {'未知源':>10} {'原始偏差':>12} {'修正后偏差':>12}")
    print(f"{'-'*86}")

    for result in all_results:
        print(f"{result['污染物']:<8} "
              f"{result['监测值(吨)']:>10.2f} "
              f"{result['原始计算值(吨)']:>10.2f} "
              f"{result['修正后计算值(吨)']:>10.2f} "
              f"{result['未知源(吨)']:>10.2f} "
              f"{result['原始偏差(%)']:>+11.1f}% "
              f"{result['修正后偏差(%)']:>+11.1f}%")

    # 未知源分析
    print("\n" + "=" * 100)
    print("未知源分析")
    print("=" * 100)

    for result in all_results:
        pollutant = result['污染物']
        unknown_pct = result['未知源占比(%)']

        if unknown_pct > 20:
            status = "建议深入调查未统计污染源"
        elif unknown_pct > 10:
            status = "建议核查数据完整性"
        elif unknown_pct > 0:
            status = "在合理范围内"
        else:
            status = "无未知源，原有污染源可能高估"

        print(f"  {pollutant}: 未知源占比 {unknown_pct:.1f}% - {status}")

    # 导出Excel
    print("\n" + "=" * 100)
    print("导出结果")
    print("=" * 100)

    excel_output = Path(__file__).parent.parent / 'output' / '系数优化结果_考虑未知源.xlsx'

    with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
        # 汇总
        df_summary = pd.DataFrame([{
            '污染物': r['污染物'],
            '监测值(吨)': r['监测值(吨)'],
            '原始计算值(吨)': r['原始计算值(吨)'],
            '修正后计算值(吨)': r['修正后计算值(吨)'],
            '未知源(吨)': r['未知源(吨)'],
            '修正+未知(吨)': r['修正+未知(吨)'],
            '原始偏差(%)': r['原始偏差(%)'],
            '修正后偏差(%)': r['修正后偏差(%)'],
            '未知源占比(%)': r['未知源占比(%)']
        } for r in all_results])
        df_summary.to_excel(writer, sheet_name='优化结果汇总', index=False)

        # 各污染物详情
        for result in all_results:
            pollutant = result['污染物']
            data = []
            for source, factor in result['修正因子'].items():
                orig = result['源数据'][source]
                data.append({
                    '污染源': source,
                    '原始入河量(kg)': orig,
                    '修正因子': factor,
                    '修正后入河量(kg)': orig * factor,
                    '修正幅度(%)': (factor - 1) * 100
                })
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name=f'{pollutant}修正详情', index=False)

    print(f"\n已导出: {excel_output.name}")
    print("\n" + "=" * 100)
    print("优化完成!")
    print("=" * 100)


if __name__ == "__main__":
    main()
    redirector.close()
    print(f"\nResults saved to: {output_file}")
