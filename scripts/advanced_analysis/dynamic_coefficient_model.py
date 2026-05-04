#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态系数模型模块

创新点2: 建立时变入河系数模型
  - 月度/季度变化的时变系数
  - 基于状态空间模型的系数更新
  - 卡尔曼滤波在线估计

主要内容:
1. 月度系数估计
2. 状态空间模型
3. 卡尔曼滤波更新
4. 季节分解
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import minimize
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class DynamicCoefficientModel:
    """动态系数模型类"""

    def __init__(self, df, source_data, monitor_values):
        """
        初始化模型

        参数:
            df: 监测数据DataFrame
            source_data: 各污染源排放数据字典
            monitor_values: 年度监测值字典
        """
        self.df = df.copy()
        self.source_data = source_data
        self.monitor_values = monitor_values
        self.prepare_data()

    def prepare_data(self):
        """准备数据"""
        self.df['监测时间'] = pd.to_datetime(self.df['监测时间'])
        self.df = self.df.sort_values('监测时间').reset_index(drop=True)
        self.df['month'] = self.df['监测时间'].dt.month
        self.df['week'] = self.df['监测时间'].dt.isocalendar().week

        # 转换数值列
        for col in ['瞬时流量(m³/s)', '化学需氧量(mg/L)', '氨氮(mg/L)',
                   '总氮(mg/L)', '总磷(mg/L)']:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')

        # 计算各时间段的负荷
        self._calculate_period_loads()

    def _calculate_period_loads(self):
        """计算月度/周度负荷"""
        pollutant_cols = {
            'COD': '化学需氧量(mg/L)',
            '氨氮': '氨氮(mg/L)',
            '总氮': '总氮(mg/L)',
            '总磷': '总磷(mg/L)'
        }

        # 月度负荷
        monthly_loads = {}
        for name, col in pollutant_cols.items():
            if col in self.df.columns:
                self.df[f'{name}_load'] = (
                    self.df[col] * self.df['瞬时流量(m³/s)'] * 3.6
                )
                monthly = self.df.groupby('month')[f'{name}_load'].sum() / 1000  # 转为吨
                monthly_loads[name] = monthly

        self.monthly_loads = pd.DataFrame(monthly_loads)

        # 周度负荷
        weekly_loads = {}
        for name, col in pollutant_cols.items():
            if col in self.df.columns:
                weekly = self.df.groupby('week')[f'{name}_load'].sum() / 1000
                weekly_loads[name] = weekly

        self.weekly_loads = pd.DataFrame(weekly_loads)

    def estimate_monthly_coefficients(self):
        """
        估计月度入河系数

        假设:
        - 月度监测负荷 = 月度理论入河量 × 月度修正系数
        - 理论入河量在年内均匀分布（可改进）

        返回:
            各污染物的月度系数序列
        """
        monthly_coefficients = {}

        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            if pollutant not in self.monthly_loads.columns:
                continue

            # 月度监测负荷
            monthly_monitor = self.monthly_loads[pollutant]

            # 假设理论入河量均匀分布
            if pollutant in self.source_data:
                annual_source = sum(self.source_data[pollutant].values()) / 1000  # 吨
                monthly_source = annual_source / 12
            else:
                continue

            # 月度系数 = 监测负荷 / 理论入河量
            monthly_coef = monthly_monitor / monthly_source

            monthly_coefficients[pollutant] = monthly_coef

        self.monthly_coefficients = pd.DataFrame(monthly_coefficients)
        return self.monthly_coefficients

    def seasonal_decomposition(self, pollutant='COD'):
        """
        季节分解

        使用加法模型: Y(t) = Trend(t) + Seasonal(t) + Residual(t)

        参数:
            pollutant: 污染物名称

        返回:
            分解结果
        """
        if pollutant not in self.monthly_coefficients.columns:
            return None

        y = self.monthly_coefficients[pollutant].values
        n = len(y)

        # 计算趋势（移动平均）
        window = 3
        trend = np.convolve(y, np.ones(window)/window, mode='same')

        # 去趋势
        detrended = y - trend

        # 季节成分（假设12个月周期）
        seasonal = np.zeros(n)
        for m in range(12):
            if m < n:
                seasonal[m] = detrended[m]

        # 残差
        residual = y - trend - seasonal

        return {
            'original': y,
            'trend': trend,
            'seasonal': seasonal,
            'residual': residual,
            'months': list(range(1, n + 1))
        }

    def state_space_model(self, pollutant='COD'):
        """
        状态空间模型

        状态方程: α(t) = α(t-1) + η(t), η ~ N(0, Q)
        观测方程: y(t) = α(t) × x(t) + ε(t), ε ~ N(0, R)

        其中:
        - α(t): 时变系数
        - y(t): 月度监测负荷
        - x(t): 月度理论入河量

        返回:
            状态估计序列
        """
        if pollutant not in self.monthly_loads.columns:
            return None

        if pollutant not in self.source_data:
            return None

        # 观测值序列
        y = self.monthly_loads[pollutant].values

        # 理论入河量序列（假设均匀分布）
        annual_source = sum(self.source_data[pollutant].values()) / 1000
        x = np.ones(12) * annual_source / 12

        n = len(y)

        # 状态空间模型参数
        Q = 0.01  # 状态噪声方差
        R = 0.1   # 观测噪声方差

        # 初始化
        alpha = np.zeros(n)  # 状态估计
        P = np.zeros(n)      # 状态方差
        alpha[0] = y[0] / x[0] if x[0] > 0 else 1.0
        P[0] = 1.0

        # 卡尔曼滤波
        for t in range(1, n):
            # 预测步
            alpha_pred = alpha[t-1]
            P_pred = P[t-1] + Q

            # 更新步
            K = P_pred * x[t] / (x[t]**2 * P_pred + R)  # 卡尔曼增益
            alpha[t] = alpha_pred + K * (y[t] - alpha_pred * x[t])
            P[t] = (1 - K * x[t]) * P_pred

        return {
            'alpha': alpha,
            'P': P,
            'y': y,
            'x': x,
            'y_fitted': alpha * x
        }

    def kalman_smoother(self, pollutant='COD'):
        """
        卡尔曼平滑器（向后平滑）

        返回更平滑的系数估计
        """
        # 先运行卡尔曼滤波
        kf_result = self.state_space_model(pollutant)
        if kf_result is None:
            return None

        alpha_f = kf_result['alpha']  # 滤波估计
        P_f = kf_result['P']          # 滤波方差
        n = len(alpha_f)

        # 初始化平滑估计
        alpha_s = np.zeros(n)
        P_s = np.zeros(n)
        alpha_s[-1] = alpha_f[-1]
        P_s[-1] = P_f[-1]

        Q = 0.01

        # 向后平滑
        for t in range(n-2, -1, -1):
            P_pred = P_f[t] + Q
            J = P_f[t] / P_pred  # 平滑增益
            alpha_s[t] = alpha_f[t] + J * (alpha_s[t+1] - alpha_f[t])
            P_s[t] = P_f[t] + J**2 * (P_s[t+1] - P_pred)

        return {
            'alpha_filtered': alpha_f,
            'alpha_smoothed': alpha_s,
            'P_filtered': P_f,
            'P_smoothed': P_s,
            'y': kf_result['y'],
            'x': kf_result['x']
        }

    def build_seasonal_coefficient_model(self):
        """
        建立季节性系数模型

        模型形式:
        α(m) = α_base × (1 + β_1×sin(2πm/12) + β_2×cos(2πm/12))

        返回:
            各污染物的季节模型参数
        """
        seasonal_models = {}

        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            if pollutant not in self.monthly_coefficients.columns:
                continue

            y = self.monthly_coefficients[pollutant].values
            months = np.arange(1, 13)

            # 构建设计矩阵
            X = np.column_stack([
                np.ones(12),
                np.sin(2 * np.pi * months / 12),
                np.cos(2 * np.pi * months / 12)
            ])

            # 最小二乘拟合
            try:
                beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)

                # 计算R²
                y_pred = X @ beta
                ss_res = np.sum((y - y_pred) ** 2)
                ss_tot = np.sum((y - np.mean(y)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

                seasonal_models[pollutant] = {
                    'alpha_base': beta[0],
                    'beta_sin': beta[1],
                    'beta_cos': beta[2],
                    'r2': r2,
                    'amplitude': np.sqrt(beta[1]**2 + beta[2]**2),
                    'phase': np.arctan2(beta[2], beta[1]) * 12 / (2 * np.pi),  # 峰值月份
                    'y_observed': y,
                    'y_fitted': y_pred
                }

            except Exception as e:
                seasonal_models[pollutant] = {'error': str(e)}

        self.seasonal_models = seasonal_models
        return seasonal_models

    def adaptive_coefficient_update(self, new_observation, pollutant='COD',
                                    learning_rate=0.1):
        """
        自适应系数更新

        使用指数加权移动平均更新系数:
        α_new = (1 - λ) × α_old + λ × α_observed

        参数:
            new_observation: 新的观测负荷
            pollutant: 污染物名称
            learning_rate: 学习率 λ

        返回:
            更新后的系数
        """
        if not hasattr(self, 'current_coefficients'):
            self.current_coefficients = {}

        if pollutant not in self.source_data:
            return None

        # 理论月入河量
        annual_source = sum(self.source_data[pollutant].values()) / 1000
        monthly_source = annual_source / 12

        # 观测系数
        alpha_observed = new_observation / monthly_source if monthly_source > 0 else 1.0

        # 更新系数
        if pollutant in self.current_coefficients:
            alpha_old = self.current_coefficients[pollutant]
            alpha_new = (1 - learning_rate) * alpha_old + learning_rate * alpha_observed
        else:
            alpha_new = alpha_observed

        self.current_coefficients[pollutant] = alpha_new

        return alpha_new

    def cross_validation(self, n_folds=12):
        """
        交叉验证评估模型性能

        使用留一交叉验证（每月作为一个fold）

        返回:
            各污染物的CV误差
        """
        cv_results = {}

        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            if pollutant not in self.monthly_coefficients.columns:
                continue

            y = self.monthly_coefficients[pollutant].values
            months = np.arange(1, 13)
            n = len(y)

            errors = []

            for i in range(n):
                # 留出第i个月
                train_idx = [j for j in range(n) if j != i]
                test_idx = i

                # 训练数据
                X_train = np.column_stack([
                    np.ones(len(train_idx)),
                    np.sin(2 * np.pi * months[train_idx] / 12),
                    np.cos(2 * np.pi * months[train_idx] / 12)
                ])
                y_train = y[train_idx]

                # 拟合模型
                try:
                    beta, _, _, _ = np.linalg.lstsq(X_train, y_train, rcond=None)

                    # 预测
                    X_test = np.array([
                        1,
                        np.sin(2 * np.pi * months[test_idx] / 12),
                        np.cos(2 * np.pi * months[test_idx] / 12)
                    ])
                    y_pred = X_test @ beta

                    # 计算误差
                    error = (y[test_idx] - y_pred) ** 2
                    errors.append(error)
                except:
                    continue

            cv_results[pollutant] = {
                'mse': np.mean(errors),
                'rmse': np.sqrt(np.mean(errors)),
                'cv_errors': errors
            }

        return cv_results

    def generate_report(self):
        """生成动态系数分析报告"""
        report = []
        report.append("=" * 80)
        report.append("动态系数模型分析报告")
        report.append("=" * 80)

        # 1. 月度系数
        report.append("\n【1. 月度入河系数】")
        if hasattr(self, 'monthly_coefficients'):
            report.append("\n各污染物月度系数:")
            for month in range(1, 13):
                line = f"  {month:2d}月: "
                for pollutant in self.monthly_coefficients.columns:
                    coef = self.monthly_coefficients.loc[month, pollutant]
                    line += f"{pollutant}={coef:.3f}  "
                report.append(line)

            report.append("\n月度系数统计:")
            for pollutant in self.monthly_coefficients.columns:
                coefs = self.monthly_coefficients[pollutant]
                report.append(f"  {pollutant}:")
                report.append(f"    范围: {coefs.min():.3f} - {coefs.max():.3f}")
                report.append(f"    均值: {coefs.mean():.3f}")
                report.append(f"    变异系数: {coefs.std()/coefs.mean():.3f}")

        # 2. 季节模型
        report.append("\n【2. 季节性系数模型】")
        if hasattr(self, 'seasonal_models'):
            for pollutant, model in self.seasonal_models.items():
                if 'error' not in model:
                    report.append(f"\n  {pollutant}:")
                    report.append(f"    基准系数: {model['alpha_base']:.3f}")
                    report.append(f"    季节振幅: {model['amplitude']:.3f}")
                    report.append(f"    峰值月份: {model['phase']:.1f}月")
                    report.append(f"    拟合R²: {model['r2']:.3f}")

        # 3. 卡尔曼滤波结果
        report.append("\n【3. 卡尔曼滤波/平滑结果】")
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            ks_result = self.kalman_smoother(pollutant)
            if ks_result is not None:
                report.append(f"\n  {pollutant}:")
                report.append(f"    滤波系数范围: {ks_result['alpha_filtered'].min():.3f} - {ks_result['alpha_filtered'].max():.3f}")
                report.append(f"    平滑系数范围: {ks_result['alpha_smoothed'].min():.3f} - {ks_result['alpha_smoothed'].max():.3f}")

        # 4. 交叉验证
        report.append("\n【4. 交叉验证结果】")
        cv_results = self.cross_validation()
        for pollutant, result in cv_results.items():
            report.append(f"  {pollutant}: RMSE = {result['rmse']:.4f}")

        return "\n".join(report)


def main():
    """主函数"""
    base_dir = Path(__file__).parent.parent.parent

    # 读取数据
    data_file = base_dir / 'output' / 'monitor_2022_cleaned_v2.xlsx'
    df = pd.read_excel(data_file)

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

    # 创建模型
    model = DynamicCoefficientModel(df, source_data, monitor_values)

    # 执行分析
    print("正在估计月度系数...")
    model.estimate_monthly_coefficients()

    print("正在建立季节性模型...")
    model.build_seasonal_coefficient_model()

    print("正在运行卡尔曼滤波...")
    for pollutant in ['COD', '氨氮', '总氮', '总磷']:
        model.kalman_smoother(pollutant)

    # 生成报告
    report = model.generate_report()

    output_file = base_dir / 'output' / 'dynamic_coefficient_analysis.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n分析完成！报告已保存到: {output_file}")

    # 保存详细结果
    excel_file = base_dir / 'output' / 'dynamic_coefficient_results.xlsx'
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        model.monthly_coefficients.to_excel(writer, sheet_name='月度系数')
        model.monthly_loads.to_excel(writer, sheet_name='月度负荷')

        # 卡尔曼滤波结果
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            ks_result = model.kalman_smoother(pollutant)
            if ks_result is not None:
                ks_df = pd.DataFrame({
                    'month': range(1, 13),
                    'observed_load': ks_result['y'],
                    'theoretical_load': ks_result['x'],
                    'alpha_filtered': ks_result['alpha_filtered'],
                    'alpha_smoothed': ks_result['alpha_smoothed']
                })
                ks_df.to_excel(writer, sheet_name=f'{pollutant}_卡尔曼', index=False)

    print(f"详细结果已保存到: {excel_file}")

    return model


if __name__ == "__main__":
    model = main()
