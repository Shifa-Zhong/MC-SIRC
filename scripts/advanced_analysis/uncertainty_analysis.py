#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
不确定性分析模块

创新点4: 全链路不确定性量化
  - 蒙特卡洛模拟
  - 参数不确定性传递
  - 置信区间估计
  - 敏感性分析

主要内容:
1. 输入数据不确定性
2. 模型参数不确定性
3. 蒙特卡洛传递
4. 全局敏感性分析 (Sobol指数)
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import minimize
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class UncertaintyAnalysis:
    """不确定性分析类"""

    def __init__(self, source_data, monitor_values):
        """
        初始化

        参数:
            source_data: 各污染源排放数据字典
            monitor_values: 监测值字典
        """
        self.source_data = source_data
        self.monitor_values = monitor_values

        # 定义参数的不确定性范围
        self._define_parameter_distributions()

    def _define_parameter_distributions(self):
        """定义各参数的概率分布"""

        # 1. 排放量不确定性 (假设变异系数CV)
        self.emission_cv = {
            '面-农村生活污染源': 0.3,    # 30%不确定性
            '面-农业面源': 0.4,          # 40%
            '畜禽散养': 0.5,             # 50%
            '面-城市面源': 0.3,
            '面-城镇散排': 0.4,
            '规模畜禽养殖': 0.4,
            '点-工业源': 0.2,            # 点源相对准确
            '点-集中式污染治理设施': 0.2
        }

        # 2. 入河系数不确定性
        self.coefficient_distributions = {
            '面-农村生活污染源': {'type': 'normal', 'mean': 1.0, 'std': 0.2},
            '面-农业面源': {'type': 'normal', 'mean': 1.0, 'std': 0.3},
            '畜禽散养': {'type': 'normal', 'mean': 1.0, 'std': 0.3},
            '面-城市面源': {'type': 'normal', 'mean': 1.0, 'std': 0.25},
            '面-城镇散排': {'type': 'normal', 'mean': 1.0, 'std': 0.35},
            '规模畜禽养殖': {'type': 'lognormal', 'mean': 0.8, 'std': 0.3},
            '点-工业源': {'type': 'lognormal', 'mean': 0.7, 'std': 0.25},
            '点-集中式污染治理设施': {'type': 'normal', 'mean': 0.9, 'std': 0.2}
        }

        # 3. 监测值不确定性 (假设10%测量误差)
        self.monitor_cv = 0.10

    def sample_parameters(self, n_samples=1000, seed=None):
        """
        采样参数

        参数:
            n_samples: 采样数量
            seed: 随机种子

        返回:
            采样的参数集合
        """
        if seed is not None:
            np.random.seed(seed)

        samples = {}

        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            if pollutant not in self.source_data:
                continue

            pollutant_samples = {
                'emissions': {},
                'coefficients': {},
                'monitor': []
            }

            # 采样排放量
            for source, value in self.source_data[pollutant].items():
                if value > 0:
                    cv = self.emission_cv.get(source, 0.3)
                    std = value * cv
                    # 使用对数正态分布（保证正值）
                    sigma = np.sqrt(np.log(1 + cv**2))
                    mu = np.log(value) - sigma**2 / 2
                    emission_samples = np.random.lognormal(mu, sigma, n_samples)
                    pollutant_samples['emissions'][source] = emission_samples

            # 采样入河系数
            for source in self.source_data[pollutant].keys():
                if source not in self.coefficient_distributions:
                    continue

                dist_info = self.coefficient_distributions[source]

                if dist_info['type'] == 'normal':
                    coef_samples = np.random.normal(
                        dist_info['mean'],
                        dist_info['std'],
                        n_samples
                    )
                    # 截断到合理范围
                    coef_samples = np.clip(coef_samples, 0.1, 2.0)

                elif dist_info['type'] == 'lognormal':
                    mu = dist_info['mean']
                    std = dist_info['std']
                    sigma = np.sqrt(np.log(1 + (std/mu)**2))
                    mu_ln = np.log(mu) - sigma**2 / 2
                    coef_samples = np.random.lognormal(mu_ln, sigma, n_samples)
                    coef_samples = np.clip(coef_samples, 0.1, 2.0)

                pollutant_samples['coefficients'][source] = coef_samples

            # 采样监测值
            monitor_value = self.monitor_values[pollutant]
            std = monitor_value * self.monitor_cv
            monitor_samples = np.random.normal(monitor_value, std, n_samples)
            monitor_samples = np.maximum(monitor_samples, 0)  # 不能为负
            pollutant_samples['monitor'] = monitor_samples

            samples[pollutant] = pollutant_samples

        self.samples = samples
        return samples

    def monte_carlo_simulation(self, n_samples=10000, seed=42):
        """
        蒙特卡洛模拟

        计算入河量的不确定性分布

        返回:
            各污染物入河量的分布
        """
        samples = self.sample_parameters(n_samples, seed)

        mc_results = {}

        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            if pollutant not in samples:
                continue

            pollutant_samples = samples[pollutant]

            # 计算每次采样的入河量
            total_inflow = np.zeros(n_samples)

            for source in pollutant_samples['emissions'].keys():
                emissions = pollutant_samples['emissions'][source]
                if source in pollutant_samples['coefficients']:
                    coefficients = pollutant_samples['coefficients'][source]
                else:
                    coefficients = np.ones(n_samples)

                source_inflow = emissions * coefficients / 1000  # 转为吨
                total_inflow += source_inflow

            # 统计分布
            mc_results[pollutant] = {
                'mean': np.mean(total_inflow),
                'std': np.std(total_inflow),
                'median': np.median(total_inflow),
                'p5': np.percentile(total_inflow, 5),
                'p25': np.percentile(total_inflow, 25),
                'p75': np.percentile(total_inflow, 75),
                'p95': np.percentile(total_inflow, 95),
                'samples': total_inflow,
                'monitor_mean': np.mean(pollutant_samples['monitor']),
                'monitor_std': np.std(pollutant_samples['monitor'])
            }

            # 计算覆盖监测值的概率
            monitor = pollutant_samples['monitor']
            coverage = np.mean(
                (total_inflow >= np.percentile(monitor, 5)) &
                (total_inflow <= np.percentile(monitor, 95))
            )
            mc_results[pollutant]['coverage_probability'] = coverage

        self.mc_results = mc_results
        return mc_results

    def sobol_sensitivity(self, pollutant='COD', n_samples=2048):
        """
        Sobol全局敏感性分析

        计算一阶和总阶敏感性指数

        参数:
            pollutant: 污染物名称
            n_samples: 采样数量 (应为2的幂次)

        返回:
            各参数的敏感性指数
        """
        if pollutant not in self.source_data:
            return None

        sources = [s for s, v in self.source_data[pollutant].items() if v > 0]
        n_params = len(sources) * 2  # 排放量 + 系数

        # 生成Sobol序列采样矩阵
        # 使用简化的随机采样代替真正的Sobol序列
        np.random.seed(42)

        A = np.random.random((n_samples, n_params))
        B = np.random.random((n_samples, n_params))

        def model_function(params):
            """模型函数：参数 -> 入河量"""
            total = 0
            for i, source in enumerate(sources):
                emission_base = self.source_data[pollutant][source]
                cv = self.emission_cv.get(source, 0.3)

                # 从[0,1]映射到排放量分布
                emission = emission_base * (1 + cv * (params[i] - 0.5) * 2)

                # 从[0,1]映射到系数分布
                coef_info = self.coefficient_distributions.get(
                    source, {'mean': 1.0, 'std': 0.3}
                )
                coef = coef_info['mean'] + coef_info['std'] * (params[i + len(sources)] - 0.5) * 2
                coef = np.clip(coef, 0.1, 2.0)

                total += emission * coef / 1000

            return total

        # 计算模型输出
        f_A = np.array([model_function(A[i]) for i in range(n_samples)])
        f_B = np.array([model_function(B[i]) for i in range(n_samples)])

        # 计算敏感性指数
        sensitivity_indices = {}
        var_total = np.var(np.concatenate([f_A, f_B]))

        for j, source in enumerate(sources):
            # 排放量敏感性
            AB_j = B.copy()
            AB_j[:, j] = A[:, j]
            f_AB_j = np.array([model_function(AB_j[i]) for i in range(n_samples)])

            # 一阶敏感性指数
            S1_emission = np.mean(f_B * (f_AB_j - f_A)) / var_total if var_total > 0 else 0

            sensitivity_indices[f'{source}_排放量'] = {
                'S1': max(0, S1_emission),
                'type': 'emission'
            }

            # 系数敏感性
            j_coef = j + len(sources)
            AB_j_coef = B.copy()
            AB_j_coef[:, j_coef] = A[:, j_coef]
            f_AB_j_coef = np.array([model_function(AB_j_coef[i]) for i in range(n_samples)])

            S1_coef = np.mean(f_B * (f_AB_j_coef - f_A)) / var_total if var_total > 0 else 0

            sensitivity_indices[f'{source}_系数'] = {
                'S1': max(0, S1_coef),
                'type': 'coefficient'
            }

        # 归一化
        total_S1 = sum(v['S1'] for v in sensitivity_indices.values())
        if total_S1 > 0:
            for key in sensitivity_indices:
                sensitivity_indices[key]['S1_normalized'] = (
                    sensitivity_indices[key]['S1'] / total_S1
                )

        return sensitivity_indices

    def local_sensitivity(self, pollutant='COD', delta=0.01):
        """
        局部敏感性分析（偏导数法）

        参数:
            pollutant: 污染物名称
            delta: 扰动比例

        返回:
            各参数的局部敏感性
        """
        if pollutant not in self.source_data:
            return None

        sources = [s for s, v in self.source_data[pollutant].items() if v > 0]

        def calculate_inflow(emissions, coefficients):
            """计算入河量"""
            total = 0
            for source in sources:
                total += emissions[source] * coefficients.get(source, 1.0) / 1000
            return total

        # 基准值
        base_emissions = {s: self.source_data[pollutant][s] for s in sources}
        base_coefficients = {
            s: self.coefficient_distributions.get(s, {'mean': 1.0})['mean']
            for s in sources
        }
        base_inflow = calculate_inflow(base_emissions, base_coefficients)

        sensitivities = {}

        # 排放量敏感性
        for source in sources:
            perturbed = base_emissions.copy()
            perturbed[source] *= (1 + delta)
            perturbed_inflow = calculate_inflow(perturbed, base_coefficients)

            # 弹性系数 = (ΔY/Y) / (ΔX/X)
            elasticity = (perturbed_inflow - base_inflow) / base_inflow / delta

            sensitivities[f'{source}_排放量'] = {
                'elasticity': elasticity,
                'absolute': (perturbed_inflow - base_inflow) / delta,
                'contribution': base_emissions[source] * base_coefficients[source] / 1000 / base_inflow
            }

        # 系数敏感性
        for source in sources:
            perturbed_coef = base_coefficients.copy()
            perturbed_coef[source] *= (1 + delta)
            perturbed_inflow = calculate_inflow(base_emissions, perturbed_coef)

            elasticity = (perturbed_inflow - base_inflow) / base_inflow / delta

            sensitivities[f'{source}_系数'] = {
                'elasticity': elasticity,
                'absolute': (perturbed_inflow - base_inflow) / delta,
                'contribution': base_emissions[source] * base_coefficients[source] / 1000 / base_inflow
            }

        return sensitivities

    def confidence_interval_optimization(self, pollutant='COD', n_bootstrap=1000):
        """
        使用Bootstrap方法估计优化系数的置信区间

        参数:
            pollutant: 污染物名称
            n_bootstrap: Bootstrap次数

        返回:
            各系数的置信区间
        """
        if pollutant not in self.source_data:
            return None

        sources = [s for s, v in self.source_data[pollutant].items() if v > 0]
        monitor_value = self.monitor_values[pollutant]

        bootstrap_results = {source: [] for source in sources}

        for b in range(n_bootstrap):
            # 对排放量和监测值添加随机噪声
            noisy_emissions = {}
            for source in sources:
                base = self.source_data[pollutant][source]
                cv = self.emission_cv.get(source, 0.3)
                noisy_emissions[source] = base * np.random.lognormal(0, cv)

            noisy_monitor = monitor_value * np.random.lognormal(0, self.monitor_cv)

            # 优化系数
            def objective(coefs):
                total = sum(
                    noisy_emissions[s] * coefs[i] / 1000
                    for i, s in enumerate(sources)
                )
                return (total - noisy_monitor) ** 2

            x0 = [1.0] * len(sources)
            bounds = [(0.1, 2.0)] * len(sources)

            try:
                result = minimize(objective, x0, bounds=bounds, method='L-BFGS-B')
                for i, source in enumerate(sources):
                    bootstrap_results[source].append(result.x[i])
            except:
                continue

        # 计算置信区间
        ci_results = {}
        for source in sources:
            coefs = bootstrap_results[source]
            if len(coefs) > 0:
                ci_results[source] = {
                    'mean': np.mean(coefs),
                    'std': np.std(coefs),
                    'ci_lower': np.percentile(coefs, 2.5),
                    'ci_upper': np.percentile(coefs, 97.5),
                    'cv': np.std(coefs) / np.mean(coefs) if np.mean(coefs) > 0 else 0
                }

        return ci_results

    def propagate_uncertainty_to_load(self, n_samples=10000):
        """
        将不确定性传递到污染负荷估计

        返回:
            各污染物负荷的不确定性范围
        """
        mc_results = self.monte_carlo_simulation(n_samples)

        load_uncertainty = {}

        for pollutant, result in mc_results.items():
            samples = result['samples']

            load_uncertainty[pollutant] = {
                'point_estimate': self.monitor_values[pollutant],
                'mc_mean': result['mean'],
                'mc_std': result['std'],
                'ci_90': (result['p5'], result['p95']),
                'ci_50': (result['p25'], result['p75']),
                'relative_uncertainty': result['std'] / result['mean'] if result['mean'] > 0 else 0
            }

        return load_uncertainty

    def generate_report(self):
        """生成不确定性分析报告"""
        report = []
        report.append("=" * 80)
        report.append("不确定性分析报告")
        report.append("=" * 80)

        # 1. 蒙特卡洛模拟
        report.append("\n【1. 蒙特卡洛模拟结果】")
        report.append(f"  采样次数: 10,000")

        mc_results = self.monte_carlo_simulation(10000)

        for pollutant, result in mc_results.items():
            report.append(f"\n  {pollutant}:")
            report.append(f"    均值: {result['mean']:.2f} 吨")
            report.append(f"    标准差: {result['std']:.2f} 吨")
            report.append(f"    90%置信区间: [{result['p5']:.2f}, {result['p95']:.2f}] 吨")
            report.append(f"    监测值: {self.monitor_values[pollutant]:.2f} 吨")
            report.append(f"    相对不确定性: {result['std']/result['mean']*100:.1f}%")

        # 2. Sobol敏感性分析
        report.append("\n【2. 全局敏感性分析 (Sobol)】")
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            sobol = self.sobol_sensitivity(pollutant)
            if sobol is None:
                continue

            report.append(f"\n  {pollutant}:")
            # 排序
            sorted_params = sorted(
                sobol.items(),
                key=lambda x: x[1].get('S1_normalized', 0),
                reverse=True
            )[:5]  # 只显示前5个

            for param, indices in sorted_params:
                if 'S1_normalized' in indices:
                    report.append(f"    {param}: {indices['S1_normalized']*100:.1f}%")

        # 3. 局部敏感性
        report.append("\n【3. 局部敏感性分析 (弹性系数)】")
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            local = self.local_sensitivity(pollutant)
            if local is None:
                continue

            report.append(f"\n  {pollutant} (弹性系数 = ΔY%/ΔX%):")

            # 按贡献度排序
            sorted_params = sorted(
                local.items(),
                key=lambda x: x[1]['contribution'],
                reverse=True
            )[:5]

            for param, indices in sorted_params:
                report.append(f"    {param}:")
                report.append(f"      弹性系数: {indices['elasticity']:.3f}")
                report.append(f"      贡献度: {indices['contribution']*100:.1f}%")

        # 4. Bootstrap置信区间
        report.append("\n【4. 系数Bootstrap置信区间 (95%)】")
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            ci = self.confidence_interval_optimization(pollutant, n_bootstrap=500)
            if ci is None:
                continue

            report.append(f"\n  {pollutant}:")
            for source, result in ci.items():
                report.append(f"    {source}: {result['mean']:.3f} [{result['ci_lower']:.3f}, {result['ci_upper']:.3f}]")

        # 5. 负荷不确定性
        report.append("\n【5. 污染负荷不确定性汇总】")
        load_unc = self.propagate_uncertainty_to_load()

        for pollutant, unc in load_unc.items():
            report.append(f"\n  {pollutant}:")
            report.append(f"    监测值: {unc['point_estimate']:.2f} 吨")
            report.append(f"    蒙特卡洛均值: {unc['mc_mean']:.2f} 吨")
            report.append(f"    90%置信区间: [{unc['ci_90'][0]:.2f}, {unc['ci_90'][1]:.2f}] 吨")
            report.append(f"    相对不确定性: ±{unc['relative_uncertainty']*100:.1f}%")

        return "\n".join(report)


def main():
    """主函数"""
    base_dir = Path(__file__).parent.parent.parent

    # 污染源数据
    source_data = {
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
            '点-工业源': 679,
            '点-集中式污染治理设施': 890,
        }
    }

    monitor_values = {
        'COD': 111.861560,
        '氨氮': 3.902692,
        '总氮': 49.368193,
        '总磷': 0.570772
    }

    # 创建分析对象
    ua = UncertaintyAnalysis(source_data, monitor_values)

    # 生成报告
    print("正在进行不确定性分析...")
    report = ua.generate_report()

    output_file = base_dir / 'output' / 'uncertainty_analysis.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n分析完成！报告已保存到: {output_file}")

    # 保存详细结果
    excel_file = base_dir / 'output' / 'uncertainty_analysis_results.xlsx'

    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # 蒙特卡洛结果
        mc_summary = []
        for pollutant, result in ua.mc_results.items():
            mc_summary.append({
                '污染物': pollutant,
                '均值(吨)': result['mean'],
                '标准差(吨)': result['std'],
                '中位数(吨)': result['median'],
                'P5(吨)': result['p5'],
                'P95(吨)': result['p95'],
                '监测值(吨)': ua.monitor_values[pollutant],
                '相对不确定性(%)': result['std'] / result['mean'] * 100
            })
        pd.DataFrame(mc_summary).to_excel(writer, sheet_name='蒙特卡洛结果', index=False)

        # Sobol敏感性
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            sobol = ua.sobol_sensitivity(pollutant)
            if sobol:
                sobol_df = pd.DataFrame([
                    {'参数': k, '敏感性指数': v.get('S1_normalized', 0) * 100}
                    for k, v in sobol.items()
                ]).sort_values('敏感性指数', ascending=False)
                sobol_df.to_excel(writer, sheet_name=f'{pollutant}_敏感性', index=False)

        # Bootstrap结果
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            ci = ua.confidence_interval_optimization(pollutant, n_bootstrap=500)
            if ci:
                ci_df = pd.DataFrame([
                    {
                        '污染源': source,
                        '均值': result['mean'],
                        '标准差': result['std'],
                        '95%CI下限': result['ci_lower'],
                        '95%CI上限': result['ci_upper']
                    }
                    for source, result in ci.items()
                ])
                ci_df.to_excel(writer, sheet_name=f'{pollutant}_Bootstrap', index=False)

    print(f"详细结果已保存到: {excel_file}")

    return ua


if __name__ == "__main__":
    ua = main()
