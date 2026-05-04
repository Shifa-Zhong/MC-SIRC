#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
河道衰减分析模块

考虑污染物从排放点到监测点的河道衰减过程：
1. 估计河道滞留时间
2. 建立一阶衰减模型
3. 计算合理的衰减范围
4. 区分"合理衰减"与"系数高估"
5. 重新评估偏差的合理性
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize, differential_evolution
from pathlib import Path


class RiverAttenuationAnalysis:
    """河道衰减分析类"""

    def __init__(self, df, source_data, monitor_values):
        """
        初始化

        Parameters:
        -----------
        df : DataFrame
            监测数据
        source_data : dict
            污染源数据
        monitor_values : dict
            监测值（吨）
        """
        self.df = df.copy()
        self.source_data = source_data
        self.monitor_values = monitor_values
        self.pollutants = ['COD', '氨氮', '总氮', '总磷']

        # 计算理论入河量
        self.theoretical_loads = {}
        for p in self.pollutants:
            if p in source_data:
                self.theoretical_loads[p] = sum(source_data[p].values()) / 1000  # kg -> ton

        # 文献衰减系数 (1/day)
        # 基于河流水质模型文献综述
        self.literature_decay_rates = {
            'COD': {'min': 0.1, 'typical': 0.2, 'max': 0.5},      # BOD/COD衰减
            '氨氮': {'min': 0.05, 'typical': 0.15, 'max': 0.3},   # 硝化作用
            '总氮': {'min': 0.0, 'typical': 0.05, 'max': 0.1},    # 反硝化+沉降
            '总磷': {'min': 0.05, 'typical': 0.15, 'max': 0.3},   # 沉降+吸附
        }

        # 结果存储
        self.attenuation_results = {}
        self.revised_analysis = {}

    def estimate_travel_time(self):
        """
        估计河道滞留时间

        基于流量数据估计平均流速和滞留时间
        """
        # 使用流量数据估计
        flow_col = '瞬时流量(m³/s)'
        Q_mean = self.df[flow_col].mean()  # m³/s
        Q_median = self.df[flow_col].median()

        # 假设河道参数（需根据实际情况调整）
        # 这些是典型中小河流的参数
        river_length = 50  # km，假设平均污染源到监测点距离
        river_width = 20   # m，平均河宽
        river_depth = 1.5  # m，平均水深

        # 计算流速 (m/s)
        cross_section = river_width * river_depth  # m²
        velocity = Q_mean / cross_section if cross_section > 0 else 0.3  # m/s

        # 限制流速在合理范围
        velocity = max(0.1, min(velocity, 2.0))  # 0.1-2.0 m/s

        # 计算滞留时间 (hours)
        travel_time_hours = (river_length * 1000) / velocity / 3600

        self.travel_time = {
            'mean_flow': Q_mean,
            'median_flow': Q_median,
            'assumed_velocity': velocity,
            'river_length_km': river_length,
            'travel_time_hours': travel_time_hours,
            'travel_time_days': travel_time_hours / 24
        }

        # 考虑不同距离的污染源，给出范围
        self.travel_time_range = {
            'min_hours': travel_time_hours * 0.2,  # 近距离源
            'typical_hours': travel_time_hours,     # 典型距离
            'max_hours': travel_time_hours * 2.0,   # 远距离源
        }

        return self.travel_time

    def calculate_attenuation_factor(self, k_per_day, travel_time_hours):
        """
        计算衰减因子

        Parameters:
        -----------
        k_per_day : float
            衰减系数 (1/day)
        travel_time_hours : float
            滞留时间 (hours)

        Returns:
        --------
        float : 衰减因子 (0-1之间，表示剩余比例)
        """
        k_per_hour = k_per_day / 24
        attenuation_factor = np.exp(-k_per_hour * travel_time_hours)
        return attenuation_factor

    def analyze_reasonable_deviation(self):
        """
        分析合理的偏差范围

        对每种污染物，计算考虑河道衰减后的合理偏差范围
        """
        if not hasattr(self, 'travel_time'):
            self.estimate_travel_time()

        results = {}

        for pollutant in self.pollutants:
            if pollutant not in self.theoretical_loads:
                continue

            theoretical = self.theoretical_loads[pollutant]
            monitored = self.monitor_values[pollutant]
            raw_deviation = (theoretical - monitored) / monitored * 100

            decay_rates = self.literature_decay_rates[pollutant]
            travel_time = self.travel_time_range['typical_hours']

            # 计算不同衰减情景下的剩余比例
            scenarios = {}
            for scenario, k in decay_rates.items():
                remaining = self.calculate_attenuation_factor(k, travel_time)
                # 合理的理论/监测比 = 1/remaining
                reasonable_ratio = 1 / remaining
                reasonable_deviation = (reasonable_ratio - 1) * 100
                scenarios[scenario] = {
                    'decay_rate': k,
                    'remaining_fraction': remaining,
                    'attenuation_percent': (1 - remaining) * 100,
                    'reasonable_deviation_percent': reasonable_deviation
                }

            # 判断实际偏差是否在合理范围内
            min_reasonable = scenarios['min']['reasonable_deviation_percent']
            max_reasonable = scenarios['max']['reasonable_deviation_percent']
            typical_reasonable = scenarios['typical']['reasonable_deviation_percent']

            if raw_deviation <= max_reasonable:
                status = 'REASONABLE'
                excess_deviation = 0
            else:
                status = 'EXCESSIVE'
                # 超出合理范围的偏差 = 需要通过系数修正的部分
                excess_deviation = raw_deviation - typical_reasonable

            results[pollutant] = {
                'theoretical_load': theoretical,
                'monitored_load': monitored,
                'raw_deviation_percent': raw_deviation,
                'attenuation_scenarios': scenarios,
                'reasonable_range': {
                    'min_deviation': min_reasonable,
                    'typical_deviation': typical_reasonable,
                    'max_deviation': max_reasonable
                },
                'status': status,
                'excess_deviation_percent': excess_deviation,
                'coefficient_correction_needed': excess_deviation / 100 if excess_deviation > 0 else 0
            }

        self.attenuation_results = results
        return results

    def revised_optimization(self):
        """
        考虑河道衰减的修正优化

        新模型：监测值 = Σ(排放量 × 入河系数 × 修正因子) × 衰减因子
        同时估计修正因子和有效衰减因子
        """
        results = {}

        for pollutant in self.pollutants:
            if pollutant not in self.source_data:
                continue

            sources = self.source_data[pollutant]
            source_names = list(sources.keys())
            source_values = np.array(list(sources.values())) / 1000  # kg -> ton

            monitored = self.monitor_values[pollutant]
            theoretical = sum(source_values)

            decay_rates = self.literature_decay_rates[pollutant]

            def objective(params):
                """目标函数：最小化残差 + 正则化"""
                n_sources = len(source_values)
                factors = params[:n_sources]
                attenuation = params[n_sources]  # 衰减因子 (0-1)

                # 预测值 = Σ(排放量 × 修正因子) × 衰减因子
                predicted = np.sum(source_values * factors) * attenuation

                # 残差
                residual = (predicted - monitored) ** 2

                # 正则化：鼓励因子接近1
                reg_factor = 0.1 * np.sum((factors - 1) ** 2)

                # 正则化：鼓励衰减因子在合理范围
                # 基于文献值计算期望衰减因子
                typical_k = decay_rates['typical']
                travel_time = self.travel_time_range['typical_hours']
                expected_attenuation = self.calculate_attenuation_factor(typical_k, travel_time)
                reg_attenuation = 0.5 * (attenuation - expected_attenuation) ** 2

                return residual + reg_factor + reg_attenuation

            # 约束条件
            n_sources = len(source_values)
            bounds = [(0.3, 1.5)] * n_sources  # 修正因子范围

            # 衰减因子范围（基于文献）
            travel_time = self.travel_time_range['typical_hours']
            min_attenuation = self.calculate_attenuation_factor(decay_rates['max'], travel_time)
            max_attenuation = self.calculate_attenuation_factor(decay_rates['min'], travel_time)
            bounds.append((min_attenuation, max_attenuation))

            # 初始值
            x0 = [1.0] * n_sources + [0.7]

            # 优化
            result = differential_evolution(objective, bounds, seed=42, maxiter=1000)

            opt_factors = result.x[:n_sources]
            opt_attenuation = result.x[n_sources]

            # 计算结果
            corrected_load = np.sum(source_values * opt_factors)
            predicted_monitor = corrected_load * opt_attenuation

            results[pollutant] = {
                'sources': source_names,
                'original_loads': source_values,
                'correction_factors': dict(zip(source_names, opt_factors)),
                'attenuation_factor': opt_attenuation,
                'attenuation_percent': (1 - opt_attenuation) * 100,
                'theoretical_load': theoretical,
                'corrected_load': corrected_load,
                'predicted_monitor': predicted_monitor,
                'actual_monitor': monitored,
                'final_deviation_percent': (predicted_monitor - monitored) / monitored * 100,
                'optimization_success': result.success
            }

        self.revised_analysis = results
        return results

    def generate_report(self):
        """生成分析报告"""
        if not self.attenuation_results:
            self.analyze_reasonable_deviation()
        if not self.revised_analysis:
            self.revised_optimization()

        report = []
        report.append("=" * 80)
        report.append("River Attenuation Analysis Report")
        report.append("=" * 80)

        # 1. 滞留时间估计
        report.append("\n[1] Travel Time Estimation")
        report.append("-" * 40)
        tt = self.travel_time
        report.append(f"  Mean flow: {tt['mean_flow']:.3f} m³/s")
        report.append(f"  Assumed velocity: {tt['assumed_velocity']:.2f} m/s")
        report.append(f"  River length: {tt['river_length_km']} km")
        report.append(f"  Travel time: {tt['travel_time_hours']:.1f} hours ({tt['travel_time_days']:.1f} days)")

        # 2. 合理偏差分析
        report.append("\n[2] Reasonable Deviation Analysis")
        report.append("-" * 40)

        for pollutant, data in self.attenuation_results.items():
            report.append(f"\n  {pollutant}:")
            report.append(f"    Theoretical load: {data['theoretical_load']:.2f} tons")
            report.append(f"    Monitored load: {data['monitored_load']:.2f} tons")
            report.append(f"    Raw deviation: {data['raw_deviation_percent']:+.1f}%")

            report.append(f"    Reasonable deviation range (due to attenuation):")
            rr = data['reasonable_range']
            report.append(f"      Min: {rr['min_deviation']:+.1f}%")
            report.append(f"      Typical: {rr['typical_deviation']:+.1f}%")
            report.append(f"      Max: {rr['max_deviation']:+.1f}%")

            report.append(f"    Status: {data['status']}")
            if data['status'] == 'EXCESSIVE':
                report.append(f"    Excess deviation (coefficient error): {data['excess_deviation_percent']:+.1f}%")

        # 3. 修正优化结果
        report.append("\n[3] Revised Optimization (with Attenuation)")
        report.append("-" * 40)

        for pollutant, data in self.revised_analysis.items():
            report.append(f"\n  {pollutant}:")
            report.append(f"    Attenuation factor: {data['attenuation_factor']:.3f} ({data['attenuation_percent']:.1f}% loss)")
            report.append(f"    Correction factors:")
            for source, factor in data['correction_factors'].items():
                change = (factor - 1) * 100
                report.append(f"      {source}: {factor:.3f} ({change:+.1f}%)")
            report.append(f"    Theoretical load: {data['theoretical_load']:.2f} tons")
            report.append(f"    Corrected load (before attenuation): {data['corrected_load']:.2f} tons")
            report.append(f"    Predicted at monitor: {data['predicted_monitor']:.2f} tons")
            report.append(f"    Actual monitor: {data['actual_monitor']:.2f} tons")
            report.append(f"    Final deviation: {data['final_deviation_percent']:+.1f}%")

        # 4. 结论
        report.append("\n[4] Conclusions")
        report.append("-" * 40)

        report.append("\n  Deviation Source Analysis:")
        for pollutant in self.pollutants:
            if pollutant not in self.attenuation_results:
                continue
            att_data = self.attenuation_results[pollutant]
            rev_data = self.revised_analysis.get(pollutant, {})

            raw_dev = att_data['raw_deviation_percent']
            typical_att = att_data['reasonable_range']['typical_deviation']

            if att_data['status'] == 'REASONABLE':
                report.append(f"\n  {pollutant}: Deviation ({raw_dev:+.1f}%) is within reasonable range")
                report.append(f"    -> Explained by river attenuation, no coefficient correction needed")
            else:
                excess = att_data['excess_deviation_percent']
                att_contrib = typical_att
                coef_contrib = raw_dev - att_contrib
                report.append(f"\n  {pollutant}: Deviation ({raw_dev:+.1f}%) exceeds reasonable range")
                report.append(f"    -> River attenuation contribution: ~{att_contrib:.1f}%")
                report.append(f"    -> Coefficient overestimation: ~{coef_contrib:.1f}%")
                if rev_data:
                    report.append(f"    -> Recommended attenuation factor: {rev_data['attenuation_factor']:.3f}")

        return "\n".join(report)


def main():
    """主函数"""
    import sys
    import io

    # 设置输出编码
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    base_dir = Path(__file__).parent.parent.parent

    # 读取数据
    print("Reading data...")
    data_file = base_dir / 'output' / 'monitor_2022_cleaned_v2.xlsx'
    df = pd.read_excel(data_file)

    # 污染源数据 (kg)
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

    # 运行分析
    print("Running river attenuation analysis...")
    analysis = RiverAttenuationAnalysis(df, source_data, monitor_values)
    analysis.estimate_travel_time()
    analysis.analyze_reasonable_deviation()
    analysis.revised_optimization()

    # 生成报告
    report = analysis.generate_report()
    print(report)

    # 保存报告
    output_file = base_dir / 'output' / 'river_attenuation_analysis.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to: {output_file}")

    # 保存详细结果到Excel
    excel_file = base_dir / 'output' / 'river_attenuation_results.xlsx'
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # 合理偏差分析
        deviation_data = []
        for p, data in analysis.attenuation_results.items():
            deviation_data.append({
                'Pollutant': p,
                'Theoretical (ton)': data['theoretical_load'],
                'Monitored (ton)': data['monitored_load'],
                'Raw Deviation (%)': data['raw_deviation_percent'],
                'Min Reasonable (%)': data['reasonable_range']['min_deviation'],
                'Typical Reasonable (%)': data['reasonable_range']['typical_deviation'],
                'Max Reasonable (%)': data['reasonable_range']['max_deviation'],
                'Status': data['status'],
                'Excess Deviation (%)': data['excess_deviation_percent']
            })
        pd.DataFrame(deviation_data).to_excel(writer, sheet_name='Deviation Analysis', index=False)

        # 修正优化结果
        for p, data in analysis.revised_analysis.items():
            factors_df = pd.DataFrame([
                {'Source': s, 'Correction Factor': f, 'Change (%)': (f-1)*100}
                for s, f in data['correction_factors'].items()
            ])
            factors_df.to_excel(writer, sheet_name=f'{p} Factors', index=False)

    print(f"Excel results saved to: {excel_file}")

    return analysis


if __name__ == "__main__":
    main()
