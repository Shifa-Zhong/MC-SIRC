#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
降雨响应建模模块

创新点1: 建立修正因子与环境因子的定量关系
  修正因子 = f(降雨强度, 前期干旱指数, 季节, 基流比例)

主要内容:
1. 前期干旱指数(API)计算
2. 降雨-径流响应分析
3. 初期冲刷效应量化
4. 面源污染动态系数模型
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class RainfallResponseModel:
    """降雨响应模型类"""

    def __init__(self, df):
        """
        初始化模型

        参数:
            df: 包含监测时间、流量、水质指标、降水量的DataFrame
        """
        self.df = df.copy()
        self.prepare_data()

    def prepare_data(self):
        """准备数据，计算衍生指标"""
        # 确保时间列是datetime类型
        self.df['监测时间'] = pd.to_datetime(self.df['监测时间'])
        self.df = self.df.sort_values('监测时间').reset_index(drop=True)

        # 提取时间特征
        self.df['month'] = self.df['监测时间'].dt.month
        self.df['hour'] = self.df['监测时间'].dt.hour
        self.df['day_of_year'] = self.df['监测时间'].dt.dayofyear

        # 季节划分
        self.df['season'] = self.df['month'].apply(self._get_season)

        # 转换数值列
        numeric_cols = ['瞬时流量(m³/s)', '氨氮(mg/L)', '总磷(mg/L)',
                       '总氮(mg/L)', '化学需氧量(mg/L)', '降水量(mm)']
        for col in numeric_cols:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')

    def _get_season(self, month):
        """季节划分"""
        if month in [3, 4, 5]:
            return 'spring'
        elif month in [6, 7, 8]:
            return 'summer'
        elif month in [9, 10, 11]:
            return 'autumn'
        else:
            return 'winter'

    def calculate_api(self, k=0.85, window=7):
        """
        计算前期干旱指数 (Antecedent Precipitation Index)

        公式: API_t = Σ(P_{t-i} × k^i), i=1 to window

        参数:
            k: 衰减系数 (0.8-0.95, 默认0.85)
            window: 前期天数 (默认7天)

        返回:
            添加API列后的DataFrame
        """
        # 按天汇总降雨量
        self.df['date'] = self.df['监测时间'].dt.date
        daily_rain = self.df.groupby('date')['降水量(mm)'].sum().reset_index()
        daily_rain.columns = ['date', 'daily_rain']

        # 计算API
        api_values = []
        for i, row in daily_rain.iterrows():
            api = 0
            for j in range(1, window + 1):
                if i - j >= 0:
                    api += daily_rain.iloc[i - j]['daily_rain'] * (k ** j)
            api_values.append(api)

        daily_rain['API'] = api_values

        # 合并回原数据
        self.df = self.df.merge(daily_rain[['date', 'API']], on='date', how='left')

        # 计算干旱指数分类
        api_median = self.df['API'].median()
        self.df['drought_level'] = pd.cut(
            self.df['API'],
            bins=[0, api_median * 0.5, api_median, api_median * 2, float('inf')],
            labels=['severe_drought', 'moderate_drought', 'normal', 'wet']
        )

        return self.df

    def calculate_baseflow_separation(self, alpha=0.925):
        """
        基流分割 (数字滤波法)

        公式: Q_b(t) = α × Q_b(t-1) + (1-α)/2 × (Q(t) + Q(t-1))

        参数:
            alpha: 滤波参数 (0.9-0.95)

        返回:
            添加基流和地表径流列
        """
        Q = self.df['瞬时流量(m³/s)'].values
        n = len(Q)

        # 初始化基流
        Qb = np.zeros(n)
        Qb[0] = Q[0] * 0.5  # 初始估计

        # 递归滤波
        for i in range(1, n):
            Qb[i] = alpha * Qb[i-1] + (1 - alpha) / 2 * (Q[i] + Q[i-1])
            # 基流不能超过总流量
            Qb[i] = min(Qb[i], Q[i])

        self.df['baseflow'] = Qb
        self.df['surface_runoff'] = self.df['瞬时流量(m³/s)'] - Qb
        self.df['baseflow_ratio'] = Qb / (self.df['瞬时流量(m³/s)'] + 0.001)

        return self.df

    def identify_storm_events(self, rain_threshold=0.5, gap_hours=6):
        """
        识别降雨事件

        参数:
            rain_threshold: 降雨阈值 (mm/h)
            gap_hours: 事件间隔阈值 (小时)

        返回:
            事件标记列
        """
        is_raining = self.df['降水量(mm)'] > rain_threshold

        # 标记事件
        event_id = 0
        events = []
        in_event = False
        gap_count = 0

        for i, raining in enumerate(is_raining):
            if raining:
                if not in_event:
                    event_id += 1
                    in_event = True
                gap_count = 0
                events.append(event_id)
            else:
                if in_event:
                    gap_count += 1
                    if gap_count >= gap_hours:
                        in_event = False
                        events.append(0)
                    else:
                        events.append(event_id)
                else:
                    events.append(0)

        self.df['storm_event_id'] = events

        return self.df

    def analyze_first_flush(self, pollutant_col='化学需氧量(mg/L)'):
        """
        分析初期冲刷效应 (First Flush Effect)

        计算M(V)曲线和FF系数

        参数:
            pollutant_col: 污染物浓度列名

        返回:
            各事件的初期冲刷分析结果
        """
        if 'storm_event_id' not in self.df.columns:
            self.identify_storm_events()

        events = self.df[self.df['storm_event_id'] > 0]['storm_event_id'].unique()

        ff_results = []

        for event_id in events:
            event_data = self.df[self.df['storm_event_id'] == event_id].copy()

            if len(event_data) < 5:  # 事件太短，跳过
                continue

            # 计算累积流量和累积负荷
            Q = event_data['瞬时流量(m³/s)'].values
            C = event_data[pollutant_col].values
            L = Q * C  # 瞬时负荷

            cum_V = np.cumsum(Q) / np.sum(Q)  # 归一化累积流量
            cum_M = np.cumsum(L) / np.sum(L)  # 归一化累积负荷

            # 计算FF30 (前30%流量携带的负荷比例)
            idx_30 = np.argmin(np.abs(cum_V - 0.3))
            ff30 = cum_M[idx_30] if idx_30 < len(cum_M) else 0.3

            # 计算FF系数 (M(V)曲线下面积与对角线的比值)
            auc = np.trapz(cum_M, cum_V)
            ff_coef = 2 * auc - 1  # >0表示有初期冲刷效应

            # 事件特征
            total_rain = event_data['降水量(mm)'].sum()
            max_rain_intensity = event_data['降水量(mm)'].max()
            duration = len(event_data)

            ff_results.append({
                'event_id': event_id,
                'duration_hours': duration,
                'total_rain_mm': total_rain,
                'max_intensity_mm_h': max_rain_intensity,
                'ff30': ff30,
                'ff_coefficient': ff_coef,
                'has_first_flush': ff_coef > 0.1
            })

        self.ff_results = pd.DataFrame(ff_results)
        return self.ff_results

    def build_dynamic_coefficient_model(self):
        """
        建立动态系数模型

        模型形式:
        α(t) = α_base × f_rain(P) × f_api(API) × f_season(S) × f_baseflow(BFR)

        返回:
            模型参数和拟合结果
        """
        if 'API' not in self.df.columns:
            self.calculate_api()
        if 'baseflow_ratio' not in self.df.columns:
            self.calculate_baseflow_separation()

        results = {}

        for pollutant, col in [('COD', '化学需氧量(mg/L)'),
                                ('氨氮', '氨氮(mg/L)'),
                                ('总氮', '总氮(mg/L)'),
                                ('总磷', '总磷(mg/L)')]:

            if col not in self.df.columns:
                continue

            # 计算瞬时负荷
            self.df[f'{pollutant}_load'] = (
                self.df[col] * self.df['瞬时流量(m³/s)'] * 3.6
            )

            # 按条件分组计算平均负荷强度
            # 1. 降雨强度分组
            rain_groups = pd.cut(
                self.df['降水量(mm)'],
                bins=[-0.001, 0, 1, 5, 10, float('inf')],
                labels=['无雨', '小雨', '中雨', '大雨', '暴雨']
            )
            rain_effect = self.df.groupby(rain_groups)[f'{pollutant}_load'].mean()

            # 归一化为修正因子
            base_load = rain_effect['无雨'] if rain_effect['无雨'] > 0 else rain_effect.mean()
            rain_factors = rain_effect / base_load

            # 2. API分组
            if 'drought_level' in self.df.columns:
                api_effect = self.df.groupby('drought_level')[f'{pollutant}_load'].mean()
                api_factors = api_effect / api_effect.mean()
            else:
                api_factors = None

            # 3. 季节分组
            season_effect = self.df.groupby('season')[f'{pollutant}_load'].mean()
            season_factors = season_effect / season_effect.mean()

            # 4. 基流比例分组
            bf_groups = pd.cut(
                self.df['baseflow_ratio'],
                bins=[0, 0.3, 0.6, 0.9, 1.0],
                labels=['低基流', '中基流', '高基流', '纯基流']
            )
            bf_effect = self.df.groupby(bf_groups)[f'{pollutant}_load'].mean()
            bf_factors = bf_effect / bf_effect.mean()

            results[pollutant] = {
                'rain_factors': rain_factors.to_dict(),
                'api_factors': api_factors.to_dict() if api_factors is not None else None,
                'season_factors': season_factors.to_dict(),
                'baseflow_factors': bf_factors.to_dict(),
                'base_load': base_load
            }

        self.dynamic_model = results
        return results

    def fit_rainfall_response_function(self):
        """
        拟合降雨响应函数

        使用非线性回归拟合:
        Load = a × P^b × (1 + c × API)^d × Q^e

        返回:
            各污染物的拟合参数
        """
        if 'API' not in self.df.columns:
            self.calculate_api()

        # 准备有效数据
        valid_mask = (
            (self.df['降水量(mm)'] > 0) &
            (self.df['瞬时流量(m³/s)'] > 0) &
            (self.df['API'] > 0)
        )

        fit_results = {}

        for pollutant, col in [('COD', '化学需氧量(mg/L)'),
                                ('氨氮', '氨氮(mg/L)'),
                                ('总氮', '总氮(mg/L)'),
                                ('总磷', '总磷(mg/L)')]:

            if col not in self.df.columns:
                continue

            data = self.df[valid_mask].copy()

            if len(data) < 50:
                continue

            # 计算负荷
            P = data['降水量(mm)'].values
            API = data['API'].values
            Q = data['瞬时流量(m³/s)'].values
            C = data[col].values
            Load = C * Q * 3.6

            # 定义响应函数
            def response_func(X, a, b, c, d, e):
                P, API, Q = X
                return a * (P ** b) * ((1 + c * API) ** d) * (Q ** e)

            try:
                # 拟合参数
                popt, pcov = curve_fit(
                    response_func,
                    (P, API, Q),
                    Load,
                    p0=[1, 0.5, 0.1, 0.5, 1],
                    bounds=([0, 0, 0, -2, 0], [100, 2, 1, 2, 2]),
                    maxfev=5000
                )

                # 计算拟合优度
                Load_pred = response_func((P, API, Q), *popt)
                ss_res = np.sum((Load - Load_pred) ** 2)
                ss_tot = np.sum((Load - np.mean(Load)) ** 2)
                r2 = 1 - ss_res / ss_tot

                fit_results[pollutant] = {
                    'params': {
                        'a': popt[0],
                        'b': popt[1],
                        'c': popt[2],
                        'd': popt[3],
                        'e': popt[4]
                    },
                    'r2': r2,
                    'formula': f'Load = {popt[0]:.4f} × P^{popt[1]:.3f} × (1 + {popt[2]:.4f}×API)^{popt[3]:.3f} × Q^{popt[4]:.3f}'
                }

            except Exception as e:
                fit_results[pollutant] = {'error': str(e)}

        self.response_functions = fit_results
        return fit_results

    def calculate_event_mean_concentration(self):
        """
        计算事件平均浓度 (EMC)

        EMC = Σ(C_i × Q_i × Δt) / Σ(Q_i × Δt)

        返回:
            各事件的EMC值
        """
        if 'storm_event_id' not in self.df.columns:
            self.identify_storm_events()

        events = self.df[self.df['storm_event_id'] > 0]['storm_event_id'].unique()

        emc_results = []

        for event_id in events:
            event_data = self.df[self.df['storm_event_id'] == event_id]

            if len(event_data) < 3:
                continue

            Q = event_data['瞬时流量(m³/s)'].values
            total_volume = np.sum(Q)

            if total_volume == 0:
                continue

            result = {
                'event_id': event_id,
                'duration_hours': len(event_data),
                'total_rain_mm': event_data['降水量(mm)'].sum(),
                'mean_flow': Q.mean(),
                'peak_flow': Q.max()
            }

            for pollutant, col in [('COD', '化学需氧量(mg/L)'),
                                    ('氨氮', '氨氮(mg/L)'),
                                    ('总氮', '总氮(mg/L)'),
                                    ('总磷', '总磷(mg/L)')]:
                if col in event_data.columns:
                    C = event_data[col].values
                    emc = np.sum(C * Q) / total_volume
                    result[f'EMC_{pollutant}'] = emc

            emc_results.append(result)

        self.emc_results = pd.DataFrame(emc_results)
        return self.emc_results

    def generate_report(self):
        """生成完整的降雨响应分析报告"""
        report = []
        report.append("=" * 80)
        report.append("降雨响应模型分析报告")
        report.append("=" * 80)

        # 1. 基本统计
        report.append("\n【1. 数据概况】")
        report.append(f"  总记录数: {len(self.df)}")
        report.append(f"  降雨时段: {(self.df['降水量(mm)'] > 0).sum()} 小时")
        report.append(f"  年总降雨量: {self.df['降水量(mm)'].sum():.2f} mm")

        # 2. API统计
        if 'API' in self.df.columns:
            report.append("\n【2. 前期干旱指数(API)统计】")
            report.append(f"  API范围: {self.df['API'].min():.2f} - {self.df['API'].max():.2f}")
            report.append(f"  API均值: {self.df['API'].mean():.2f}")
            report.append(f"  API中位数: {self.df['API'].median():.2f}")

            if 'drought_level' in self.df.columns:
                drought_dist = self.df['drought_level'].value_counts()
                report.append("  干旱等级分布:")
                for level, count in drought_dist.items():
                    report.append(f"    {level}: {count} ({count/len(self.df)*100:.1f}%)")

        # 3. 基流分割结果
        if 'baseflow_ratio' in self.df.columns:
            report.append("\n【3. 基流分割结果】")
            report.append(f"  基流比例范围: {self.df['baseflow_ratio'].min():.3f} - {self.df['baseflow_ratio'].max():.3f}")
            report.append(f"  平均基流比例: {self.df['baseflow_ratio'].mean():.3f}")
            report.append(f"  基流主导时段(BFR>0.8): {(self.df['baseflow_ratio'] > 0.8).sum()} 小时")

        # 4. 降雨事件统计
        if 'storm_event_id' in self.df.columns:
            events = self.df[self.df['storm_event_id'] > 0]['storm_event_id'].unique()
            report.append(f"\n【4. 降雨事件识别】")
            report.append(f"  识别到降雨事件: {len(events)} 场")

        # 5. 初期冲刷效应
        if hasattr(self, 'ff_results') and len(self.ff_results) > 0:
            report.append("\n【5. 初期冲刷效应分析】")
            ff_events = self.ff_results[self.ff_results['has_first_flush']]
            report.append(f"  具有初期冲刷效应的事件: {len(ff_events)}/{len(self.ff_results)} 场")
            report.append(f"  平均FF30系数: {self.ff_results['ff30'].mean():.3f}")
            report.append(f"  (FF30>0.3表示前30%径流携带超30%负荷)")

        # 6. 动态系数模型
        if hasattr(self, 'dynamic_model'):
            report.append("\n【6. 动态系数模型】")
            for pollutant, params in self.dynamic_model.items():
                report.append(f"\n  {pollutant}:")
                report.append(f"    降雨强度因子:")
                for level, factor in params['rain_factors'].items():
                    report.append(f"      {level}: {factor:.3f}")
                report.append(f"    季节因子:")
                for season, factor in params['season_factors'].items():
                    report.append(f"      {season}: {factor:.3f}")

        # 7. 响应函数拟合
        if hasattr(self, 'response_functions'):
            report.append("\n【7. 降雨响应函数】")
            for pollutant, result in self.response_functions.items():
                if 'error' not in result:
                    report.append(f"\n  {pollutant}:")
                    report.append(f"    公式: {result['formula']}")
                    report.append(f"    R² = {result['r2']:.4f}")

        # 8. EMC统计
        if hasattr(self, 'emc_results') and len(self.emc_results) > 0:
            report.append("\n【8. 事件平均浓度(EMC)统计】")
            for col in self.emc_results.columns:
                if col.startswith('EMC_'):
                    pollutant = col.replace('EMC_', '')
                    values = self.emc_results[col].dropna()
                    report.append(f"  {pollutant}:")
                    report.append(f"    EMC范围: {values.min():.3f} - {values.max():.3f} mg/L")
                    report.append(f"    EMC均值: {values.mean():.3f} mg/L")

        return "\n".join(report)


def main():
    """主函数"""
    base_dir = Path(__file__).parent.parent.parent

    # 读取清洗后的数据
    data_file = base_dir / 'output' / 'monitor_2022_cleaned_v2.xlsx'
    df = pd.read_excel(data_file)

    # 创建模型
    model = RainfallResponseModel(df)

    # 执行分析
    print("正在计算前期干旱指数...")
    model.calculate_api()

    print("正在进行基流分割...")
    model.calculate_baseflow_separation()

    print("正在识别降雨事件...")
    model.identify_storm_events()

    print("正在分析初期冲刷效应...")
    model.analyze_first_flush()

    print("正在建立动态系数模型...")
    model.build_dynamic_coefficient_model()

    print("正在拟合降雨响应函数...")
    model.fit_rainfall_response_function()

    print("正在计算事件平均浓度...")
    model.calculate_event_mean_concentration()

    # 生成报告
    report = model.generate_report()

    # 保存报告
    output_file = base_dir / 'output' / 'rainfall_response_analysis.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n分析完成！报告已保存到: {output_file}")

    # 保存详细结果到Excel
    excel_file = base_dir / 'output' / 'rainfall_response_results.xlsx'
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # 数据汇总
        summary_cols = ['监测时间', '降水量(mm)', 'API', 'baseflow_ratio',
                       'storm_event_id', 'season']
        summary_cols = [c for c in summary_cols if c in model.df.columns]
        model.df[summary_cols].to_excel(writer, sheet_name='数据汇总', index=False)

        # 初期冲刷结果
        if hasattr(model, 'ff_results'):
            model.ff_results.to_excel(writer, sheet_name='初期冲刷分析', index=False)

        # EMC结果
        if hasattr(model, 'emc_results'):
            model.emc_results.to_excel(writer, sheet_name='事件平均浓度', index=False)

    print(f"详细结果已保存到: {excel_file}")

    return model


if __name__ == "__main__":
    model = main()
