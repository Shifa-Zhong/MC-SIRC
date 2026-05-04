#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
水文耦合模块

创新点3: 简化水文模型与污染负荷耦合
  - 产汇流过程模拟
  - 污染物迁移转化
  - 面源冲刷模型

主要内容:
1. 简化水文模型（SCS-CN法）
2. 面源冲刷模型
3. 污染物衰减模型
4. 水文-水质耦合模拟
"""

import pandas as pd
import numpy as np
from scipy.optimize import minimize, curve_fit
from scipy.integrate import odeint
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


class HydrologicalCouplingModel:
    """水文耦合模型类"""

    def __init__(self, df):
        """
        初始化模型

        参数:
            df: 包含监测数据的DataFrame
        """
        self.df = df.copy()
        self.prepare_data()

    def prepare_data(self):
        """准备数据"""
        self.df['监测时间'] = pd.to_datetime(self.df['监测时间'])
        self.df = self.df.sort_values('监测时间').reset_index(drop=True)
        self.df['month'] = self.df['监测时间'].dt.month

        # 转换数值列
        for col in ['瞬时流量(m³/s)', '化学需氧量(mg/L)', '氨氮(mg/L)',
                   '总氮(mg/L)', '总磷(mg/L)', '降水量(mm)']:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')

    # ========== 1. SCS-CN产流模型 ==========

    def scs_cn_runoff(self, P, CN, Ia_ratio=0.2):
        """
        SCS曲线数法计算径流

        公式:
        Q = (P - Ia)² / (P - Ia + S)  当 P > Ia
        Q = 0                          当 P ≤ Ia

        其中:
        S = 25400/CN - 254 (最大潜在滞留量, mm)
        Ia = λ × S (初损, 通常λ=0.2)

        参数:
            P: 降雨量 (mm)
            CN: 曲线数 (0-100)
            Ia_ratio: 初损比例 (默认0.2)

        返回:
            径流深 (mm)
        """
        S = 25400 / CN - 254  # 最大潜在滞留量
        Ia = Ia_ratio * S      # 初损

        Q = np.where(
            P > Ia,
            (P - Ia) ** 2 / (P - Ia + S),
            0
        )

        return Q

    def calibrate_cn(self, area_km2=100):
        """
        率定CN值

        使用实测降雨-径流数据反推CN值

        参数:
            area_km2: 流域面积 (km²)

        返回:
            率定的CN值和拟合结果
        """
        # 按日汇总数据
        self.df['date'] = self.df['监测时间'].dt.date
        daily = self.df.groupby('date').agg({
            '降水量(mm)': 'sum',
            '瞬时流量(m³/s)': 'mean'
        }).reset_index()

        # 计算日径流深 (mm)
        # Q_mm = Q_m3s × 86400s × 1000mm / (area_km2 × 10^6 m²)
        daily['Q_mm'] = daily['瞬时流量(m³/s)'] * 86400 * 1000 / (area_km2 * 1e6)

        # 只使用有降雨且有径流的数据
        valid = (daily['降水量(mm)'] > 1) & (daily['Q_mm'] > 0)
        P_obs = daily.loc[valid, '降水量(mm)'].values
        Q_obs = daily.loc[valid, 'Q_mm'].values

        if len(P_obs) < 5:
            return {'error': '有效数据不足'}

        # 目标函数
        def objective(CN):
            Q_pred = self.scs_cn_runoff(P_obs, CN[0])
            return np.sum((Q_obs - Q_pred) ** 2)

        # 优化
        result = minimize(objective, x0=[70], bounds=[(30, 98)], method='L-BFGS-B')
        CN_opt = result.x[0]

        # 计算拟合优度
        Q_pred = self.scs_cn_runoff(P_obs, CN_opt)
        ss_res = np.sum((Q_obs - Q_pred) ** 2)
        ss_tot = np.sum((Q_obs - np.mean(Q_obs)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        # Nash-Sutcliffe效率系数
        nse = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        return {
            'CN': CN_opt,
            'r2': r2,
            'nse': nse,
            'P_obs': P_obs,
            'Q_obs': Q_obs,
            'Q_pred': Q_pred
        }

    # ========== 2. 面源污染冲刷模型 ==========

    def buildup_washoff_model(self, pollutant='COD'):
        """
        面源污染累积-冲刷模型

        累积模型 (Michaelis-Menten型):
        dB/dt = k_a × (B_max - B) - k_d × B

        冲刷模型 (指数型):
        W = B × (1 - exp(-k_w × Q))

        参数:
            pollutant: 污染物名称

        返回:
            模型参数和模拟结果
        """
        col_map = {
            'COD': '化学需氧量(mg/L)',
            '氨氮': '氨氮(mg/L)',
            '总氮': '总氮(mg/L)',
            '总磷': '总磷(mg/L)'
        }

        if pollutant not in col_map:
            return None

        col = col_map[pollutant]
        if col not in self.df.columns:
            return None

        # 计算干期长度（距上次降雨的小时数）
        is_rain = self.df['降水量(mm)'] > 0.1
        dry_hours = []
        count = 0
        for rain in is_rain:
            if rain:
                count = 0
            else:
                count += 1
            dry_hours.append(count)

        self.df['dry_hours'] = dry_hours

        # 计算负荷
        self.df['load'] = self.df[col] * self.df['瞬时流量(m³/s)'] * 3.6

        # 分析降雨事件的冲刷特性
        rain_events = self.df[is_rain].copy()

        if len(rain_events) < 10:
            return {'error': '降雨事件不足'}

        # 拟合累积-冲刷模型参数
        # 简化：使用经验公式
        # 冲刷量 ∝ 干期长度^a × 降雨强度^b

        dry_before_rain = []
        load_during_rain = []
        rain_intensity = []

        for i, (idx, row) in enumerate(rain_events.iterrows()):
            if idx > 0:
                dry_before_rain.append(self.df.loc[idx - 1, 'dry_hours'])
                load_during_rain.append(row['load'])
                rain_intensity.append(row['降水量(mm)'])

        dry_before_rain = np.array(dry_before_rain) + 1  # 避免log(0)
        load_during_rain = np.array(load_during_rain)
        rain_intensity = np.array(rain_intensity) + 0.1

        # 对数线性模型: log(Load) = a + b×log(dry) + c×log(rain)
        try:
            X = np.column_stack([
                np.ones(len(dry_before_rain)),
                np.log(dry_before_rain),
                np.log(rain_intensity)
            ])
            y = np.log(load_during_rain + 0.01)

            beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)

            # 拟合优度
            y_pred = X @ beta
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

            return {
                'intercept': beta[0],
                'dry_period_effect': beta[1],  # 干期累积效应
                'rain_intensity_effect': beta[2],  # 降雨冲刷效应
                'r2': r2,
                'formula': f'log(Load) = {beta[0]:.3f} + {beta[1]:.3f}×log(dry) + {beta[2]:.3f}×log(rain)'
            }

        except Exception as e:
            return {'error': str(e)}

    # ========== 3. 污染物衰减模型 ==========

    def decay_model(self, pollutant='COD'):
        """
        污染物衰减模型

        一级动力学模型:
        dC/dt = -k × C

        解析解:
        C(t) = C_0 × exp(-k × t)

        参数:
            pollutant: 污染物名称

        返回:
            衰减系数k和半衰期
        """
        col_map = {
            'COD': '化学需氧量(mg/L)',
            '氨氮': '氨氮(mg/L)',
            '总氮': '总氮(mg/L)',
            '总磷': '总磷(mg/L)'
        }

        if pollutant not in col_map:
            return None

        col = col_map[pollutant]

        # 选择无降雨且流量稳定的时段
        stable_mask = (
            (self.df['降水量(mm)'] == 0) &
            (self.df['瞬时流量(m³/s)'] > 0.01) &
            (self.df['瞬时流量(m³/s)'] < self.df['瞬时流量(m³/s)'].quantile(0.8))
        )

        stable_data = self.df[stable_mask].copy()

        if len(stable_data) < 100:
            return {'error': '稳定期数据不足'}

        # 计算相邻时刻的浓度变化
        C = stable_data[col].values
        dC = np.diff(C)
        C_mean = (C[:-1] + C[1:]) / 2

        # 线性回归: dC/C = -k × dt
        # 由于dt=1小时, dC/C ≈ -k
        valid = (C_mean > 0) & np.isfinite(dC / C_mean)
        decay_rates = -dC[valid] / C_mean[valid]

        # 使用中位数估计k (更稳健)
        k = np.median(decay_rates)
        k_std = np.std(decay_rates)

        # 半衰期
        half_life = np.log(2) / k if k > 0 else float('inf')

        return {
            'k': k,
            'k_std': k_std,
            'half_life_hours': half_life,
            'n_samples': np.sum(valid)
        }

    # ========== 4. 水文-水质耦合模拟 ==========

    def coupled_simulation(self, area_km2=100):
        """
        水文-水质耦合模拟

        模拟框架:
        1. 降雨 → 产流 (SCS-CN)
        2. 产流 → 面源冲刷
        3. 点源 + 面源 → 入河
        4. 河道衰减

        参数:
            area_km2: 流域面积

        返回:
            模拟结果
        """
        results = {}

        # 1. 率定CN值
        cn_result = self.calibrate_cn(area_km2)
        if 'error' not in cn_result:
            results['cn'] = cn_result['CN']
            results['cn_nse'] = cn_result['nse']

        # 2. 面源冲刷模型
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            bw_result = self.buildup_washoff_model(pollutant)
            if bw_result and 'error' not in bw_result:
                results[f'{pollutant}_buildup_washoff'] = bw_result

        # 3. 衰减模型
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            decay_result = self.decay_model(pollutant)
            if decay_result and 'error' not in decay_result:
                results[f'{pollutant}_decay'] = decay_result

        # 4. 综合模拟
        self._run_coupled_model(results, area_km2)

        return results

    def _run_coupled_model(self, params, area_km2):
        """
        运行耦合模型

        状态变量:
        - B: 地表累积量 (kg/km²)
        - C: 河道浓度 (mg/L)

        状态方程:
        dB/dt = k_b - k_w × Q × B  (累积 - 冲刷)
        dC/dt = (Q_in × C_in - Q_out × C + W) / V - k_d × C  (质量平衡)
        """
        n = len(self.df)
        dt = 1  # 小时

        # 初始化状态
        B = np.zeros((n, 4))  # 4种污染物的累积量
        C_sim = np.zeros((n, 4))  # 模拟浓度

        pollutants = ['COD', '氨氮', '总氮', '总磷']

        # 参数
        k_b = [1.0, 0.05, 0.2, 0.02]  # 累积速率 (kg/km²/h)
        k_w = [0.1, 0.1, 0.1, 0.1]    # 冲刷系数 (1/mm)
        k_d = [0.01, 0.02, 0.01, 0.005]  # 衰减系数 (1/h)

        # 从率定结果更新参数
        for i, p in enumerate(pollutants):
            if f'{p}_decay' in params:
                k_d[i] = max(0.001, params[f'{p}_decay']['k'])

        # 初始条件
        B[0, :] = [100, 5, 20, 1]  # 初始累积量

        # 运行模型
        for t in range(1, n):
            P = self.df.loc[t, '降水量(mm)']
            Q = self.df.loc[t, '瞬时流量(m³/s)']

            for i in range(4):
                # 累积-冲刷
                washoff = B[t-1, i] * (1 - np.exp(-k_w[i] * P)) if P > 0 else 0
                B[t, i] = B[t-1, i] + k_b[i] * dt - washoff

                # 浓度演化 (简化: 假设完全混合)
                if Q > 0:
                    # 冲刷负荷转化为浓度增量
                    C_add = washoff * area_km2 / (Q * 3600)  # mg/L近似
                    C_sim[t, i] = C_sim[t-1, i] * np.exp(-k_d[i] * dt) + C_add * 0.01
                else:
                    C_sim[t, i] = C_sim[t-1, i] * np.exp(-k_d[i] * dt)

        # 保存结果
        for i, p in enumerate(pollutants):
            self.df[f'{p}_sim'] = C_sim[:, i]
            self.df[f'{p}_buildup'] = B[:, i]

        # 计算模拟效果
        col_map = {
            'COD': '化学需氧量(mg/L)',
            '氨氮': '氨氮(mg/L)',
            '总氮': '总氮(mg/L)',
            '总磷': '总磷(mg/L)'
        }

        for p in pollutants:
            if col_map[p] in self.df.columns:
                obs = self.df[col_map[p]].values
                sim = self.df[f'{p}_sim'].values

                # 归一化后计算相关性
                obs_norm = (obs - np.mean(obs)) / (np.std(obs) + 0.001)
                sim_norm = (sim - np.mean(sim)) / (np.std(sim) + 0.001)

                corr = np.corrcoef(obs_norm, sim_norm)[0, 1]
                params[f'{p}_correlation'] = corr

    def sensitivity_analysis(self, param_name='CN', param_range=None):
        """
        敏感性分析

        参数:
            param_name: 参数名称
            param_range: 参数取值范围

        返回:
            敏感性分析结果
        """
        if param_range is None:
            if param_name == 'CN':
                param_range = np.arange(50, 95, 5)
            else:
                param_range = np.linspace(0.5, 2.0, 10)

        results = []

        for value in param_range:
            if param_name == 'CN':
                # 用不同CN值计算径流
                P = self.df['降水量(mm)'].values
                Q_sim = self.scs_cn_runoff(P, value)
                Q_obs = self.df['瞬时流量(m³/s)'].values

                # 计算相关性
                valid = (Q_sim > 0) & (Q_obs > 0)
                if np.sum(valid) > 10:
                    corr = np.corrcoef(Q_sim[valid], Q_obs[valid])[0, 1]
                else:
                    corr = 0

                results.append({
                    'param_value': value,
                    'correlation': corr
                })

        return pd.DataFrame(results)

    def generate_report(self):
        """生成水文耦合分析报告"""
        report = []
        report.append("=" * 80)
        report.append("水文耦合模型分析报告")
        report.append("=" * 80)

        # 运行耦合模拟
        results = self.coupled_simulation()

        # 1. SCS-CN模型
        report.append("\n【1. SCS-CN产流模型】")
        if 'cn' in results:
            report.append(f"  率定CN值: {results['cn']:.1f}")
            report.append(f"  Nash-Sutcliffe效率: {results['cn_nse']:.3f}")

        # 2. 累积-冲刷模型
        report.append("\n【2. 面源累积-冲刷模型】")
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            key = f'{pollutant}_buildup_washoff'
            if key in results:
                bw = results[key]
                report.append(f"\n  {pollutant}:")
                report.append(f"    干期累积效应指数: {bw['dry_period_effect']:.3f}")
                report.append(f"    降雨冲刷效应指数: {bw['rain_intensity_effect']:.3f}")
                report.append(f"    拟合R²: {bw['r2']:.3f}")
                report.append(f"    模型公式: {bw['formula']}")

        # 3. 衰减模型
        report.append("\n【3. 污染物衰减模型】")
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            key = f'{pollutant}_decay'
            if key in results:
                decay = results[key]
                report.append(f"\n  {pollutant}:")
                report.append(f"    衰减系数k: {decay['k']:.4f} /h")
                report.append(f"    半衰期: {decay['half_life_hours']:.1f} 小时")

        # 4. 耦合模拟效果
        report.append("\n【4. 耦合模拟效果】")
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            key = f'{pollutant}_correlation'
            if key in results:
                report.append(f"  {pollutant} 模拟-观测相关系数: {results[key]:.3f}")

        return "\n".join(report)


def main():
    """主函数"""
    base_dir = Path(__file__).parent.parent.parent

    # 读取数据
    data_file = base_dir / 'output' / 'monitor_2022_cleaned_v2.xlsx'
    df = pd.read_excel(data_file)

    # 创建模型
    model = HydrologicalCouplingModel(df)

    # 生成报告
    print("正在运行水文耦合模型...")
    report = model.generate_report()

    output_file = base_dir / 'output' / 'hydrological_coupling_analysis.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\n分析完成！报告已保存到: {output_file}")

    # 敏感性分析
    print("\n正在进行敏感性分析...")
    sensitivity = model.sensitivity_analysis('CN')

    excel_file = base_dir / 'output' / 'hydrological_coupling_results.xlsx'
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        sensitivity.to_excel(writer, sheet_name='CN敏感性分析', index=False)

        # 模拟结果
        sim_cols = ['监测时间', '降水量(mm)', '瞬时流量(m³/s)']
        for p in ['COD', '氨氮', '总氮', '总磷']:
            if f'{p}_sim' in model.df.columns:
                sim_cols.extend([f'{p}_sim', f'{p}_buildup'])

        model.df[sim_cols].to_excel(writer, sheet_name='模拟结果', index=False)

    print(f"详细结果已保存到: {excel_file}")

    return model


if __name__ == "__main__":
    model = main()
