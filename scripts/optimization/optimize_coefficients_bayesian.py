#!/usr/bin/env python3
"""
污染物入河系数优化 - 贝叶斯推断方法

特点：
1. 为每个系数设置先验分布（基于领域知识）
2. 通过监测数据更新后验分布
3. 提供不确定性量化（置信区间）
4. 自动识别异常数据源

方法：
使用马尔可夫链蒙特卡洛（MCMC）模拟或变分推断
简化版本使用最大后验估计（MAP）+ 拉普拉斯近似
"""

import pandas as pd
import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm, truncnorm, gamma
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


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
        '面-农业面源': 0,
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
        # 排除异常企业（污水处理厂）后的工业源总磷
        '点-工业源': 679,
        '点-集中式污染治理设施': 890,
    }
}

# 各污染源的先验知识（基于文献和经验）
# prior_mean: 先验均值，prior_std: 先验标准差
# 值越小表示越确定原系数是合理的
SOURCE_PRIORS = {
    '面-农村生活污染源': {'prior_mean': 1.0, 'prior_std': 0.3, 'description': '面源，系数较确定'},
    '面-农业面源': {'prior_mean': 1.0, 'prior_std': 0.4, 'description': '受降雨影响大，不确定性中等'},
    '畜禽散养': {'prior_mean': 1.0, 'prior_std': 0.4, 'description': '分散难统计，不确定性中等'},
    '面-水产养殖': {'prior_mean': 1.0, 'prior_std': 0.3, 'description': '相对集中，系数较确定'},
    '面-城市面源': {'prior_mean': 1.0, 'prior_std': 0.4, 'description': '受管网覆盖影响，不确定性中等'},
    '面-城镇散排': {'prior_mean': 1.0, 'prior_std': 0.5, 'description': '难以监测，不确定性较大'},
    '规模畜禽养殖': {'prior_mean': 0.8, 'prior_std': 0.3, 'description': '可能高估，先验偏低'},
    '点-工业源': {'prior_mean': 0.7, 'prior_std': 0.4, 'description': '可能显著高估，先验偏低'},
    '点-集中式污染治理设施': {'prior_mean': 0.9, 'prior_std': 0.3, 'description': '处理效率可能更高'},
}


def neg_log_posterior(params, source_data, monitor_value, source_names,
                      sigma_obs=None, include_unknown=True):
    """
    计算负对数后验概率（用于最小化）

    贝叶斯框架：
        posterior ∝ likelihood × prior

    似然函数：
        P(监测值|参数) = N(监测值; 计算值, σ²)

    先验分布：
        P(修正因子_i) = TruncatedNormal(μ_i, σ_i², [0.1, 2.0])
        P(未知源) = Exponential(λ) 或 Gamma(α, β)
    """
    n_sources = len(source_names)

    # 解析参数
    factors = {source_names[i]: params[i] for i in range(n_sources)}
    unknown_source = params[n_sources] if include_unknown else 0

    # 计算模型预测值
    predicted = 0
    for source, emission in source_data.items():
        if emission > 0 and source in factors:
            predicted += emission * factors[source] / 1000

    predicted += unknown_source

    # 似然函数（假设观测误差为正态分布）
    if sigma_obs is None:
        sigma_obs = monitor_value * 0.1  # 假设10%的观测误差

    log_likelihood = -0.5 * ((monitor_value - predicted) / sigma_obs) ** 2

    # 先验分布
    log_prior = 0

    # 修正因子的先验（截断正态分布）
    for i, source in enumerate(source_names):
        factor = params[i]
        prior_info = SOURCE_PRIORS.get(source, {'prior_mean': 1.0, 'prior_std': 0.3})
        mu = prior_info['prior_mean']
        sigma = prior_info['prior_std']

        # 截断正态分布的对数概率（简化计算，使用正态近似）
        if 0.1 <= factor <= 2.0:
            log_prior += -0.5 * ((factor - mu) / sigma) ** 2
        else:
            log_prior += -1000  # 超出范围给予很大惩罚

    # 未知源的先验（指数分布，鼓励较小的未知源）
    if include_unknown and unknown_source >= 0:
        # 使用Gamma分布作为先验，鼓励未知源较小
        alpha = 2  # 形状参数
        beta = 10 / monitor_value  # 尺度参数，使得先验期望约为监测值的20%
        log_prior += (alpha - 1) * np.log(unknown_source + 0.001) - beta * unknown_source
    elif include_unknown:
        log_prior += -1000  # 负的未知源给予很大惩罚

    # 负对数后验
    neg_log_post = -(log_likelihood + log_prior)

    return neg_log_post


def optimize_bayesian(pollutant, source_data, monitor_value, include_unknown=True):
    """
    使用贝叶斯方法优化单个污染物
    """
    # 筛选有效污染源
    active_sources = {k: v for k, v in source_data.items() if v > 0}
    source_names = list(active_sources.keys())
    n_sources = len(source_names)

    if n_sources == 0:
        return None

    # 设置初始值和边界
    x0 = []
    bounds = []

    for source in source_names:
        prior_info = SOURCE_PRIORS.get(source, {'prior_mean': 1.0})
        x0.append(prior_info['prior_mean'])
        bounds.append((0.1, 2.0))

    if include_unknown:
        x0.append(monitor_value * 0.1)  # 初始未知源为监测值的10%
        bounds.append((0, monitor_value * 0.5))

    # 优化
    result = minimize(
        neg_log_posterior,
        x0,
        args=(active_sources, monitor_value, source_names, None, include_unknown),
        method='L-BFGS-B',
        bounds=bounds
    )

    # 计算Hessian矩阵用于不确定性估计（拉普拉斯近似）
    # 这里使用简化方法，通过数值微分估计
    eps = 1e-5
    n_params = len(result.x)
    hessian = np.zeros((n_params, n_params))

    for i in range(n_params):
        for j in range(n_params):
            x_pp = result.x.copy()
            x_pm = result.x.copy()
            x_mp = result.x.copy()
            x_mm = result.x.copy()

            x_pp[i] += eps
            x_pp[j] += eps
            x_pm[i] += eps
            x_pm[j] -= eps
            x_mp[i] -= eps
            x_mp[j] += eps
            x_mm[i] -= eps
            x_mm[j] -= eps

            f_pp = neg_log_posterior(x_pp, active_sources, monitor_value, source_names, None, include_unknown)
            f_pm = neg_log_posterior(x_pm, active_sources, monitor_value, source_names, None, include_unknown)
            f_mp = neg_log_posterior(x_mp, active_sources, monitor_value, source_names, None, include_unknown)
            f_mm = neg_log_posterior(x_mm, active_sources, monitor_value, source_names, None, include_unknown)

            hessian[i, j] = (f_pp - f_pm - f_mp + f_mm) / (4 * eps ** 2)

    # 计算协方差矩阵（Hessian的逆）
    try:
        cov_matrix = np.linalg.inv(hessian)
        std_errors = np.sqrt(np.diag(cov_matrix))
    except:
        std_errors = np.zeros(n_params)

    # 解析结果
    optimal_factors = {}
    factor_uncertainties = {}

    for i, source in enumerate(source_names):
        optimal_factors[source] = result.x[i]
        factor_uncertainties[source] = std_errors[i] if i < len(std_errors) else 0

    if include_unknown:
        unknown_source = result.x[n_sources]
        unknown_std = std_errors[n_sources] if n_sources < len(std_errors) else 0
    else:
        unknown_source = 0
        unknown_std = 0

    # 计算总量
    original_total = sum(active_sources.values()) / 1000
    corrected_total = sum(
        emission * optimal_factors[source] / 1000
        for source, emission in active_sources.items()
    )

    return {
        '污染物': pollutant,
        '监测值(吨)': monitor_value,
        '原始计算值(吨)': original_total,
        '修正后计算值(吨)': corrected_total,
        '未知源(吨)': unknown_source,
        '未知源标准差': unknown_std,
        '修正+未知(吨)': corrected_total + unknown_source,
        '原始偏差(%)': (original_total - monitor_value) / monitor_value * 100,
        '修正后偏差(%)': (corrected_total + unknown_source - monitor_value) / monitor_value * 100,
        '修正因子': optimal_factors,
        '修正因子不确定性': factor_uncertainties,
        '优化成功': result.success
    }


def detect_anomalies(pollutant, source_data, optimal_factors, factor_uncertainties):
    """
    检测异常污染源（修正幅度显著偏离先验）
    """
    anomalies = []

    for source, factor in optimal_factors.items():
        prior_info = SOURCE_PRIORS.get(source, {'prior_mean': 1.0, 'prior_std': 0.3})
        prior_mean = prior_info['prior_mean']
        prior_std = prior_info['prior_std']

        # 计算z-score（偏离先验的程度）
        z_score = abs(factor - prior_mean) / prior_std

        # 如果z-score > 2，认为是异常
        if z_score > 2:
            anomalies.append({
                '污染源': source,
                '优化后因子': factor,
                '先验均值': prior_mean,
                'z-score': z_score,
                '判断': '可能存在数据问题' if factor < 0.5 else '系数需要大幅调整'
            })

    return anomalies


def main():
    print("=" * 100)
    print("污染物入河系数优化 - 贝叶斯推断方法")
    print("=" * 100)

    print("""
【贝叶斯方法的优势】

1. 先验知识融合
   - 可以融入专家经验和历史数据
   - 对数据质量差的源给予更大的调整空间

2. 不确定性量化
   - 提供修正因子的置信区间
   - 识别哪些源的系数最不确定

3. 异常检测
   - 自动识别与先验严重偏离的源
   - 提示可能存在数据质量问题

4. 稳健估计
   - 先验起到正则化作用，避免过拟合
   - 对于稀疏数据更稳定

【先验设置】
""")

    print(f"  {'污染源':<25} {'先验均值':>10} {'先验标准差':>12} {'说明'}")
    print(f"  {'-'*80}")
    for source, info in SOURCE_PRIORS.items():
        print(f"  {source:<25} {info['prior_mean']:>10.2f} {info['prior_std']:>12.2f} {info['description']}")

    all_results = []
    all_anomalies = {}

    for pollutant in ['COD', '氨氮', '总氮', '总磷']:
        print(f"\n{'='*80}")
        print(f"优化 {pollutant}")
        print(f"{'='*80}")

        source_data = SOURCE_DATA[pollutant]
        monitor_value = MONITOR_VALUES[pollutant]

        # 执行贝叶斯优化
        result = optimize_bayesian(pollutant, source_data, monitor_value, include_unknown=True)

        if result:
            all_results.append(result)

            print(f"\n【优化结果】")
            print(f"  监测值: {result['监测值(吨)']:.2f} 吨")
            print(f"  原始计算值: {result['原始计算值(吨)']:.2f} 吨 (偏差: {result['原始偏差(%)']:+.1f}%)")
            print(f"  修正后计算值: {result['修正后计算值(吨)']:.2f} 吨")
            print(f"  未知源: {result['未知源(吨)']:.2f} ± {result['未知源标准差']:.2f} 吨")
            print(f"  总计: {result['修正+未知(吨)']:.2f} 吨 (偏差: {result['修正后偏差(%)']:+.1f}%)")

            print(f"\n【各污染源修正因子及置信区间】")
            print(f"  {'污染源':<25} {'因子':>8} {'95%CI':>18} {'先验':>8} {'变化':>10}")
            print(f"  {'-'*75}")

            for source in result['修正因子']:
                factor = result['修正因子'][source]
                std = result['修正因子不确定性'].get(source, 0)
                prior_mean = SOURCE_PRIORS.get(source, {'prior_mean': 1.0})['prior_mean']

                ci_low = max(0.1, factor - 1.96 * std)
                ci_high = min(2.0, factor + 1.96 * std)
                change = (factor - prior_mean) / prior_mean * 100

                print(f"  {source:<25} {factor:>8.3f} [{ci_low:.3f}, {ci_high:.3f}] {prior_mean:>8.2f} {change:>+9.1f}%")

            # 异常检测
            anomalies = detect_anomalies(
                pollutant, source_data,
                result['修正因子'],
                result['修正因子不确定性']
            )

            if anomalies:
                all_anomalies[pollutant] = anomalies
                print(f"\n  ⚠️ 检测到异常污染源：")
                for anom in anomalies:
                    print(f"    - {anom['污染源']}: 因子={anom['优化后因子']:.3f}, "
                          f"z-score={anom['z-score']:.2f}, {anom['判断']}")

    # 总结
    print("\n" + "=" * 100)
    print("优化结果总结")
    print("=" * 100)

    print(f"\n{'污染物':<8} {'监测值':>10} {'原始值':>10} {'修正后':>10} {'未知源':>10} {'偏差改善':>12}")
    print(f"{'-'*72}")

    for result in all_results:
        improvement = abs(result['原始偏差(%)']) - abs(result['修正后偏差(%)'])
        print(f"{result['污染物']:<8} "
              f"{result['监测值(吨)']:>10.2f} "
              f"{result['原始计算值(吨)']:>10.2f} "
              f"{result['修正后计算值(吨)']:>10.2f} "
              f"{result['未知源(吨)']:>10.2f} "
              f"{improvement:>+11.1f}%")

    # 异常源汇总
    if all_anomalies:
        print("\n" + "=" * 100)
        print("异常污染源汇总（建议重点核查）")
        print("=" * 100)

        for pollutant, anomalies in all_anomalies.items():
            print(f"\n{pollutant}:")
            for anom in anomalies:
                print(f"  - {anom['污染源']}: {anom['判断']}")

    # 建议
    print("\n" + "=" * 100)
    print("优化建议")
    print("=" * 100)

    print("""
1. 数据核查优先级
   - 首先核查标记为"异常"的污染源数据
   - 检查单位是否统一（千克 vs 吨）
   - 验证排放量计算公式是否正确

2. 未知源调查
   - 如果某污染物的未知源占比>20%，建议调查：
     * 是否有遗漏的污染源
     * 大气沉降贡献
     * 地下水入渗
     * 河道底泥释放

3. 系数更新策略
   - 对于置信区间较窄的因子，可以直接使用
   - 对于置信区间较宽的因子，建议进一步收集数据

4. 迭代优化
   - 修正后重新运行分析
   - 使用多年数据验证修正效果
   - 根据实际监测反馈调整先验
""")

    # 导出
    output_file = Path(__file__).parent.parent / 'output' / '系数优化结果_贝叶斯方法.xlsx'

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # 汇总
        df_summary = pd.DataFrame([{
            '污染物': r['污染物'],
            '监测值(吨)': r['监测值(吨)'],
            '原始计算值(吨)': r['原始计算值(吨)'],
            '修正后计算值(吨)': r['修正后计算值(吨)'],
            '未知源(吨)': r['未知源(吨)'],
            '未知源标准差': r['未知源标准差'],
            '原始偏差(%)': r['原始偏差(%)'],
            '修正后偏差(%)': r['修正后偏差(%)']
        } for r in all_results])
        df_summary.to_excel(writer, sheet_name='优化结果汇总', index=False)

        # 各污染物详情
        for result in all_results:
            pollutant = result['污染物']
            data = []
            for source in result['修正因子']:
                factor = result['修正因子'][source]
                std = result['修正因子不确定性'].get(source, 0)
                prior = SOURCE_PRIORS.get(source, {'prior_mean': 1.0, 'prior_std': 0.3})

                data.append({
                    '污染源': source,
                    '修正因子': factor,
                    '标准差': std,
                    '95%CI下限': max(0.1, factor - 1.96 * std),
                    '95%CI上限': min(2.0, factor + 1.96 * std),
                    '先验均值': prior['prior_mean'],
                    '先验标准差': prior['prior_std'],
                    '变化(%)': (factor - prior['prior_mean']) / prior['prior_mean'] * 100
                })

            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name=f'{pollutant}详情', index=False)

        # 异常检测
        if all_anomalies:
            anomaly_data = []
            for pollutant, anomalies in all_anomalies.items():
                for anom in anomalies:
                    anomaly_data.append({
                        '污染物': pollutant,
                        **anom
                    })
            df_anomaly = pd.DataFrame(anomaly_data)
            df_anomaly.to_excel(writer, sheet_name='异常检测', index=False)

    print(f"\n✓ 已导出: {output_file.name}")


if __name__ == "__main__":
    main()
