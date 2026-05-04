#!/usr/bin/env python3
"""
污染物入河系数优化 - 考虑未知源的约束优化方法

改进点：
1. 引入"未知源"项，不假设所有污染源都已知
2. 使用约束优化，确保系数在物理合理范围内
3. 最小化修正幅度，避免过度修正
4. 提供不确定性估计

模型：
    监测值 = Σ(排放量_i × 系数_i × 修正因子_i) + 未知源

约束：
    - 修正因子在 [0.3, 1.5] 范围内（不允许过度修正）
    - 未知源 >= 0（只允许遗漏，不允许负贡献）
    - 优先修正贡献大的源（修正幅度与贡献度相关）
"""

import pandas as pd
import numpy as np
from scipy.optimize import minimize, differential_evolution
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# 数据定义
# ============================================================================

# 监测数据（吨）- 作为优化目标
MONITOR_VALUES = {
    'COD': 111.861560,
    '氨氮': 3.902692,
    '总氮': 49.368193,
    '总磷': 0.570772
}

# 各污染源的原始入河量（千克）- 来自 入河污染物总量统计.xlsx
# 这里需要根据实际数据填写
SOURCE_DATA = {
    'COD': {
        '面-农村生活污染源': 25490,
        '面-农业面源': 0,
        '畜禽散养': 2850,
        '面-水产养殖': 0,
        '面-城市面源': 68940,
        '面-城镇散排': 5230,
        '规模畜禽养殖': 181300,
        '点-工业源': 80260,
        '点-集中式污染治理设施': 70570,
    },
    '氨氮': {
        '面-农村生活污染源': 380,
        '面-农业面源': 0,
        '畜禽散养': 59,
        '面-水产养殖': 0,
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
        '面-水产养殖': 0,
        '面-城市面源': 2510,
        '面-城镇散排': 0,
        '规模畜禽养殖': 10740,
        '点-工业源': 0,  # 工业源没有总氮数据
        '点-集中式污染治理设施': 48690,
    },
    '总磷': {
        '面-农村生活污染源': 69,
        '面-农业面源': 240,
        '畜禽散养': 47,
        '面-水产养殖': 0,
        '面-城市面源': 170,
        '面-城镇散排': 0,
        '规模畜禽养殖': 2810,
        # 点-工业源原值35370kg有严重问题（污水处理厂数据异常）
        # 排除异常企业后，工业源总磷约679kg
        '点-工业源': 679,
        '点-集中式污染治理设施': 890,
    }
}


def calculate_total(source_data, factors):
    """计算修正后的总入河量（吨）"""
    total = 0
    for source, emission in source_data.items():
        if emission > 0 and source in factors:
            total += emission * factors[source] / 1000  # 千克转吨
    return total


def objective_function(x, source_data, monitor_value, source_names,
                       lambda_reg=0.1, lambda_unknown=0.01):
    """
    目标函数：最小化误差 + 正则化项

    参数：
        x: [修正因子1, 修正因子2, ..., 未知源]
        source_data: 各污染源的原始入河量
        monitor_value: 监测值
        source_names: 污染源名称列表
        lambda_reg: 修正因子正则化系数（惩罚偏离1的程度）
        lambda_unknown: 未知源正则化系数（惩罚未知源过大）

    目标：
        min |监测值 - (计算值 + 未知源)|²
            + λ1 * Σ(修正因子_i - 1)² * 贡献度_i
            + λ2 * 未知源²
    """
    n_sources = len(source_names)
    factors = {source_names[i]: x[i] for i in range(n_sources)}
    unknown_source = x[n_sources]  # 最后一个变量是未知源

    # 计算修正后的总量
    calculated = calculate_total(source_data, factors)

    # 误差项：(监测值 - 计算值 - 未知源)²
    error = (monitor_value - calculated - unknown_source) ** 2

    # 正则化项1：惩罚修正因子偏离1（按贡献度加权）
    total_emission = sum(source_data.values())
    reg_factor = 0
    for i, source in enumerate(source_names):
        emission = source_data[source]
        weight = emission / total_emission if total_emission > 0 else 0
        reg_factor += weight * (x[i] - 1) ** 2

    # 正则化项2：惩罚未知源过大
    reg_unknown = unknown_source ** 2

    return error + lambda_reg * reg_factor + lambda_unknown * reg_unknown


def optimize_single_pollutant(pollutant, source_data, monitor_value,
                              factor_bounds=(0.3, 1.5),
                              unknown_bounds=(0, None),
                              lambda_reg=0.1,
                              lambda_unknown=0.01):
    """
    优化单个污染物的系数

    参数：
        pollutant: 污染物名称
        source_data: 各污染源的入河量字典
        monitor_value: 监测值（吨）
        factor_bounds: 修正因子的范围
        unknown_bounds: 未知源的范围
        lambda_reg: 修正因子正则化系数
        lambda_unknown: 未知源正则化系数

    返回：
        优化结果字典
    """
    # 筛选有效的污染源（入河量>0）
    active_sources = {k: v for k, v in source_data.items() if v > 0}
    source_names = list(active_sources.keys())
    n_sources = len(source_names)

    if n_sources == 0:
        return None

    # 计算原始总量
    original_total = sum(active_sources.values()) / 1000  # 吨

    # 设置边界
    # 修正因子边界
    bounds = [factor_bounds] * n_sources
    # 未知源边界（最大不超过监测值的50%）
    max_unknown = max(0, monitor_value * 0.5)
    bounds.append((0, max_unknown))

    # 初始值：修正因子=1，未知源=0
    x0 = [1.0] * n_sources + [0.0]

    # 使用差分进化算法（全局优化）
    result = differential_evolution(
        objective_function,
        bounds=bounds,
        args=(active_sources, monitor_value, source_names, lambda_reg, lambda_unknown),
        seed=42,
        maxiter=1000,
        tol=1e-8,
        polish=True
    )

    # 解析结果
    optimal_factors = {source_names[i]: result.x[i] for i in range(n_sources)}
    optimal_unknown = result.x[n_sources]

    # 计算修正后的总量
    corrected_total = calculate_total(active_sources, optimal_factors)

    # 计算各项统计
    stats = {
        '污染物': pollutant,
        '监测值(吨)': monitor_value,
        '原始计算值(吨)': original_total,
        '修正后计算值(吨)': corrected_total,
        '未知源(吨)': optimal_unknown,
        '修正+未知(吨)': corrected_total + optimal_unknown,
        '原始偏差(%)': (original_total - monitor_value) / monitor_value * 100,
        '修正后偏差(%)': (corrected_total + optimal_unknown - monitor_value) / monitor_value * 100,
        '未知源占比(%)': optimal_unknown / monitor_value * 100 if monitor_value > 0 else 0,
        '优化成功': result.success,
        '修正因子': optimal_factors
    }

    return stats


def analyze_sensitivity(pollutant, source_data, monitor_value, optimal_factors):
    """
    敏感性分析：分析各污染源对结果的影响
    """
    active_sources = {k: v for k, v in source_data.items() if v > 0}
    total_emission = sum(active_sources.values())

    sensitivity = {}
    for source, emission in active_sources.items():
        # 计算该源对总量的贡献
        contribution = emission / total_emission if total_emission > 0 else 0

        # 计算修正幅度
        factor = optimal_factors.get(source, 1.0)
        correction = (factor - 1) * 100

        sensitivity[source] = {
            '原始入河量(kg)': emission,
            '贡献度(%)': contribution * 100,
            '修正因子': factor,
            '修正幅度(%)': correction,
            '修正后入河量(kg)': emission * factor
        }

    return sensitivity


def main():
    print("=" * 100)
    print("污染物入河系数优化 - 考虑未知源的约束优化方法")
    print("=" * 100)

    print("""
【方法说明】

传统方法的问题：
  ✗ 假设所有污染源都已知
  ✗ 简单按比例分配修正因子
  ✗ 可能导致修正过度或不足

本方法的改进：
  ✓ 引入"未知源"项，允许存在未识别的污染来源
  ✓ 使用约束优化，确保修正因子在物理合理范围内 [0.3, 1.5]
  ✓ 正则化项惩罚过度修正，优先保持原系数
  ✓ 按贡献度加权，贡献大的源允许更大修正

数学模型：
  目标：min |监测值 - Σ(排放量 × 修正因子) - 未知源|²
           + λ1 × Σ(修正因子 - 1)² × 贡献度
           + λ2 × 未知源²

  约束：0.3 ≤ 修正因子 ≤ 1.5
        0 ≤ 未知源 ≤ 监测值 × 50%
""")

    all_results = []
    all_sensitivity = {}

    for pollutant in ['COD', '氨氮', '总氮', '总磷']:
        print(f"\n{'='*80}")
        print(f"优化 {pollutant}")
        print(f"{'='*80}")

        source_data = SOURCE_DATA[pollutant]
        monitor_value = MONITOR_VALUES[pollutant]

        # 显示原始数据
        print(f"\n原始数据：")
        print(f"  监测值: {monitor_value:.2f} 吨")
        total_calc = sum(source_data.values()) / 1000
        print(f"  计算值: {total_calc:.2f} 吨")
        print(f"  原始偏差: {(total_calc - monitor_value) / monitor_value * 100:+.1f}%")

        # 执行优化
        result = optimize_single_pollutant(
            pollutant, source_data, monitor_value,
            factor_bounds=(0.3, 1.5),
            lambda_reg=0.1,
            lambda_unknown=0.01
        )

        if result:
            all_results.append(result)

            print(f"\n优化结果：")
            print(f"  修正后计算值: {result['修正后计算值(吨)']:.2f} 吨")
            print(f"  未知源估计: {result['未知源(吨)']:.2f} 吨 ({result['未知源占比(%)']:.1f}%)")
            print(f"  总计: {result['修正+未知(吨)']:.2f} 吨")
            print(f"  修正后偏差: {result['修正后偏差(%)']:+.1f}%")

            print(f"\n各污染源修正因子：")
            print(f"  {'污染源':<25} {'原始(kg)':>12} {'修正因子':>10} {'修正后(kg)':>12} {'修正幅度':>10}")
            print(f"  {'-'*75}")

            for source, factor in result['修正因子'].items():
                orig = source_data[source]
                corrected = orig * factor
                change = (factor - 1) * 100
                print(f"  {source:<25} {orig:>12,.0f} {factor:>10.3f} {corrected:>12,.0f} {change:>+9.1f}%")

            # 敏感性分析
            sensitivity = analyze_sensitivity(pollutant, source_data, monitor_value, result['修正因子'])
            all_sensitivity[pollutant] = sensitivity

    # 总结报告
    print("\n" + "=" * 100)
    print("优化结果总结")
    print("=" * 100)

    print(f"\n{'污染物':<8} {'监测值':>10} {'原始计算':>10} {'修正后':>10} {'未知源':>10} {'原始偏差':>10} {'修正后偏差':>12}")
    print(f"{'-'*82}")

    for result in all_results:
        print(f"{result['污染物']:<8} "
              f"{result['监测值(吨)']:>10.2f} "
              f"{result['原始计算值(吨)']:>10.2f} "
              f"{result['修正后计算值(吨)']:>10.2f} "
              f"{result['未知源(吨)']:>10.2f} "
              f"{result['原始偏差(%)']:>+9.1f}% "
              f"{result['修正后偏差(%)']:>+11.1f}%")

    # 未知源分析
    print("\n" + "=" * 100)
    print("未知源分析")
    print("=" * 100)

    print("""
【未知源的可能来源】

1. 大气沉降
   - 干沉降、湿沉降带来的污染物
   - 对总氮、总磷有较大贡献

2. 地下水入渗
   - 受污染的地下水补给河流
   - 可能携带农业面源的残留污染

3. 河道底泥释放
   - 历史沉积污染物的二次释放
   - 在特定条件下（厌氧、高温）释放增强

4. 未统计的小型污染源
   - 小型养殖场、小作坊
   - 农村散户排放

5. 数据统计遗漏
   - 部分污染源未被完整统计
   - 排放量估算偏低

【建议】
""")

    for result in all_results:
        pollutant = result['污染物']
        unknown_pct = result['未知源占比(%)']

        if unknown_pct > 20:
            print(f"  {pollutant}: 未知源占比 {unknown_pct:.1f}%，建议深入调查未统计污染源")
        elif unknown_pct > 10:
            print(f"  {pollutant}: 未知源占比 {unknown_pct:.1f}%，建议核查数据完整性")
        elif unknown_pct > 0:
            print(f"  {pollutant}: 未知源占比 {unknown_pct:.1f}%，在合理范围内")
        else:
            print(f"  {pollutant}: 无未知源，原有污染源可能高估")

    # 导出结果
    print("\n" + "=" * 100)
    print("导出结果")
    print("=" * 100)

    output_file = Path(__file__).parent.parent / 'output' / '系数优化结果_考虑未知源.xlsx'

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Sheet 1: 优化结果汇总
        df_summary = pd.DataFrame(all_results)
        df_summary = df_summary.drop(columns=['修正因子'])
        df_summary.to_excel(writer, sheet_name='优化结果汇总', index=False)

        # Sheet 2-5: 各污染物的详细修正因子
        for pollutant, sensitivity in all_sensitivity.items():
            df_detail = pd.DataFrame.from_dict(sensitivity, orient='index')
            df_detail.index.name = '污染源'
            df_detail = df_detail.reset_index()
            df_detail.to_excel(writer, sheet_name=f'{pollutant}修正详情', index=False)

    print(f"\n✓ 已导出: {output_file.name}")

    print("\n" + "=" * 100)
    print("优化完成！")
    print("=" * 100)


if __name__ == "__main__":
    main()
