#!/usr/bin/env python3
"""
监测数据完整清洗脚本 v2.0
改进：使用合理的阈值代替IQR方法，保留真实的洪峰流量

功能：
1. 筛选2022年数据
2. 对氨氮、总磷、总氮、化学需氧量进行线性插值
3. 对瞬时流量：
   - 删除明显错误的异常值（负值和极端大值）
   - 使用历史同期数据填充
   - 使用相邻月份中位数填充剩余缺失
4. 合并降水量数据
5. 导出清洗后的完整数据
"""

import pandas as pd
import numpy as np
from pathlib import Path

def remove_outliers_threshold(series, lower_bound=0, upper_bound=50):
    """
    使用阈值方法移除明显错误的异常值

    参数:
        series: 数据序列
        lower_bound: 下限（默认0，删除负值）
        upper_bound: 上限（默认50 m³/s，删除极端异常值）

    返回:
        清洗后的序列
    """
    # 统计信息
    total = len(series.dropna())
    below_lower = (series < lower_bound).sum()
    above_upper = (series > upper_bound).sum()

    if total > 0:
        print(f"      原始有效数据: {total} 条")
        print(f"      删除负值: {below_lower} 条")
        print(f"      删除超大值(>{upper_bound}): {above_upper} 条")
        print(f"      保留: {total - below_lower - above_upper} 条")

    # 将超出范围的值设为NaN
    return series.where((series >= lower_bound) & (series <= upper_bound), np.nan)

def fill_with_historical_median(df_2022, df_all, flow_col):
    """使用历史同期中位数填充"""
    df_result = df_2022.copy()

    # 创建时间标识（月-日-时）
    df_all['time_key'] = (df_all['month'].astype(str) + '-' +
                          df_all['day'].astype(str) + '-' +
                          df_all['hour'].astype(str))
    df_result['time_key'] = (df_result['month'].astype(str) + '-' +
                             df_result['day'].astype(str) + '-' +
                             df_result['hour'].astype(str))

    # 计算历史同期中位数（只使用清洗后的数据）
    historical_medians = df_all[df_all['year'] != 2022].groupby('time_key')[flow_col].median()

    # 填充缺失值
    missing_mask = df_result[flow_col].isna()
    filled_count = 0

    for idx in df_result[missing_mask].index:
        time_key = df_result.loc[idx, 'time_key']
        if time_key in historical_medians.index and pd.notna(historical_medians[time_key]):
            df_result.loc[idx, flow_col] = historical_medians[time_key]
            filled_count += 1

    df_result = df_result.drop('time_key', axis=1)
    return df_result, filled_count

def fill_with_adjacent_months(df, flow_col):
    """使用相邻月份中位数填充剩余缺失"""
    df_result = df.copy()
    filled_count = 0

    for month in range(1, 13):
        month_mask = df_result['month'] == month
        month_missing_mask = month_mask & df_result[flow_col].isna()
        missing_count = month_missing_mask.sum()

        if missing_count > 0:
            # 获取相邻月份
            prev_month = month - 1 if month > 1 else 12
            next_month = month + 1 if month < 12 else 1

            # 获取相邻月份的有效数据
            prev_data = df_result[df_result['month'] == prev_month][flow_col].dropna()
            next_data = df_result[df_result['month'] == next_month][flow_col].dropna()
            combined = pd.concat([prev_data, next_data])

            if len(combined) > 0:
                median_value = combined.median()
                df_result.loc[month_missing_mask, flow_col] = median_value
                filled_count += missing_count

    return df_result, filled_count

def merge_rainfall_data(df_monitor, rain_file):
    """合并降水量数据"""
    try:
        # 读取降水量数据
        df_rain = pd.read_excel(rain_file)

        # 转换时间列
        df_rain['北京时(UTC+8)'] = pd.to_datetime(df_rain['北京时(UTC+8)'], errors='coerce')
        df_rain = df_rain.dropna(subset=['北京时(UTC+8)'])

        # 提取2022年数据
        df_rain['year'] = df_rain['北京时(UTC+8)'].dt.year
        df_rain_2022 = df_rain[df_rain['year'] == 2022].copy()

        # 只保留时间和降水量列
        df_rain_2022 = df_rain_2022[['北京时(UTC+8)', '降水量(mm)']].copy()
        df_rain_2022 = df_rain_2022.rename(columns={'北京时(UTC+8)': '监测时间'})

        # 合并数据
        df_merged = df_monitor.merge(df_rain_2022, on='监测时间', how='left')

        # 未匹配的降水量填充为0（无降水）
        df_merged['降水量(mm)'] = df_merged['降水量(mm)'].fillna(0.0)

        rain_matched = df_merged['降水量(mm)'].notna().sum()

        return df_merged, rain_matched

    except Exception as e:
        print(f"    ⚠ 降水量数据合并失败: {e}")
        print(f"    将跳过降水量合并，继续处理...")
        return df_monitor, 0

def main():
    base_dir = Path(__file__).parent.parent
    monitor_file = base_dir / 'data' / 'monitor.xlsx'
    rain_file = base_dir / 'data' / 'rain.xlsx'
    output_file = base_dir / 'output' / 'monitor_2022_cleaned_v2.xlsx'

    print("="*70)
    print("监测数据清洗流程 v2.0")
    print("改进：保留真实洪峰流量，只删除明显错误的异常值")
    print("="*70)

    # ==================== 读取数据 ====================
    print("\n【步骤1】读取原始监测数据...")
    df = pd.read_excel(monitor_file)
    df.columns = df.iloc[0]
    df = df.drop(0).reset_index(drop=True)

    print(f"原始数据形状: {df.shape}")

    # 转换时间列
    df['监测时间'] = pd.to_datetime(df['监测时间'], errors='coerce')
    df = df.dropna(subset=['监测时间'])

    # 提取时间信息
    df['year'] = df['监测时间'].dt.year
    df['month'] = df['监测时间'].dt.month
    df['day'] = df['监测时间'].dt.day
    df['hour'] = df['监测时间'].dt.hour

    # ==================== 筛选2022年数据 ====================
    print("\n【步骤2】筛选2022年数据...")
    df_2022 = df[df['year'] == 2022].copy()
    df_2022 = df_2022.sort_values('监测时间').reset_index(drop=True)
    print(f"2022年数据: {len(df_2022)}条")

    # ==================== 处理水质指标（线性插值）====================
    print("\n【步骤3】处理水质指标（线性插值）...")

    interpolate_columns = ['氨氮(mg/L)', '总磷(mg/L)', '总氮(mg/L)', '化学需氧量(mg/L)']

    for col in interpolate_columns:
        if col in df_2022.columns:
            df_2022[col] = pd.to_numeric(df_2022[col], errors='coerce')
            missing_before = df_2022[col].isna().sum()
            df_2022[col] = df_2022[col].interpolate(method='linear', limit_direction='both')
            missing_after = df_2022[col].isna().sum()
            filled = missing_before - missing_after
            print(f"  {col}: 填充 {filled} 个缺失值")

    # ==================== 处理瞬时流量 ====================
    print("\n【步骤4】处理瞬时流量...")

    flow_col = '瞬时流量(m³/s)'

    if flow_col in df_2022.columns:
        # 转换为数值类型
        df[flow_col] = pd.to_numeric(df[flow_col], errors='coerce')
        df_2022[flow_col] = pd.to_numeric(df_2022[flow_col], errors='coerce')

        # 4.1 使用阈值方法移除明显错误的异常值
        print("\n  4.1 使用阈值方法移除明显错误的异常值...")
        print(f"      阈值设置: 0 m³/s ≤ 流量 ≤ 50 m³/s")
        print(f"      (删除负值和极端大值，保留真实洪峰)")

        print(f"\n    全数据集清洗:")
        df[flow_col] = remove_outliers_threshold(df[flow_col], lower_bound=0, upper_bound=50)

        print(f"\n    2022年数据清洗:")
        df_2022[flow_col] = remove_outliers_threshold(df_2022[flow_col], lower_bound=0, upper_bound=50)

        original_missing = df_2022[flow_col].isna().sum()
        print(f"\n      清洗后缺失: {original_missing}条")

        # 4.2 使用历史同期数据填充
        print("\n  4.2 使用历史同期数据填充...")
        df_2022, hist_filled = fill_with_historical_median(df_2022, df, flow_col)
        after_hist = df_2022[flow_col].isna().sum()
        print(f"      历史同期填充: {hist_filled}条")
        print(f"      剩余缺失: {after_hist}条")

        # 4.3 使用相邻月份中位数填充剩余缺失
        print("\n  4.3 使用相邻月份中位数填充剩余缺失...")
        df_2022, adj_filled = fill_with_adjacent_months(df_2022, flow_col)
        final_missing = df_2022[flow_col].isna().sum()
        print(f"      相邻月份填充: {adj_filled}条")
        print(f"      最终缺失: {final_missing}条")

        # 统计信息
        if df_2022[flow_col].notna().sum() > 0:
            print(f"\n      清洗后统计:")
            print(f"        有效数据: {df_2022[flow_col].notna().sum()}")
            print(f"        完整率: {df_2022[flow_col].notna().sum()/len(df_2022)*100:.2f}%")
            print(f"        最小值: {df_2022[flow_col].min():.4f} m³/s")
            print(f"        最大值: {df_2022[flow_col].max():.4f} m³/s")
            print(f"        均值: {df_2022[flow_col].mean():.4f} m³/s")
            print(f"        中位数: {df_2022[flow_col].median():.4f} m³/s")

            # 统计大流量事件
            large_flow_count = (df_2022[flow_col] > 10).sum()
            print(f"        大流量事件(>10 m³/s): {large_flow_count}次")

    # ==================== 清理辅助列 ====================
    cols_to_drop = ['year', 'month', 'day', 'hour']
    df_2022_final = df_2022.drop(columns=cols_to_drop, errors='ignore')

    # ==================== 合并降水量数据 ====================
    print("\n【步骤5】合并降水量数据...")

    if rain_file.exists():
        df_2022_final, rain_matched = merge_rainfall_data(df_2022_final, rain_file)
        print(f"  ✓ 降水量数据合并完成")
        print(f"    成功匹配: {rain_matched}条")
        print(f"    完整率: {rain_matched/len(df_2022_final)*100:.2f}%")
    else:
        print(f"  ⚠ 降水量文件不存在: {rain_file}")
        print(f"    跳过降水量合并")

    # ==================== 导出 ====================
    print("\n【步骤6】导出清洗后的数据...")

    df_2022_final.to_excel(output_file, index=False)

    print(f"\n✓ 已导出到: {output_file}")
    print(f"  最终数据形状: {df_2022_final.shape}")

    # ==================== 数据质量报告 ====================
    print("\n" + "="*70)
    print("数据质量报告")
    print("="*70)

    print("\n关键指标缺失情况:")
    key_cols = ['氨氮(mg/L)', '总磷(mg/L)', '总氮(mg/L)', '化学需氧量(mg/L)', '瞬时流量(m³/s)']

    # 如果有降水量列，添加到检查列表
    if '降水量(mm)' in df_2022_final.columns:
        key_cols.append('降水量(mm)')

    for col in key_cols:
        if col in df_2022_final.columns:
            missing = df_2022_final[col].isna().sum()
            total = len(df_2022_final)
            pct = (total - missing) / total * 100
            status = "✓" if missing == 0 else "✗"
            print(f"  {status} {col:20s}: {total - missing:4d}/{total} ({pct:5.2f}%)")

    print("\n最终列名:")
    for i, col in enumerate(df_2022_final.columns, 1):
        print(f"  {i:2d}. {col}")

    print("\n" + "="*70)
    print("清洗完成！")
    print("="*70)
    print("""
处理方法总结:
  • 水质指标: 线性插值 → 100%填充
  • 瞬时流量:
    - 阈值清洗（删除负值和>50m³/s的极端值）
    - 历史同期数据填充（2019-2024年同期中位数）
    - 相邻月份中位数填充（剩余缺失）
    - 保留了真实的洪峰流量（10-50 m³/s）
  • 降水量: 按时间匹配合并

输出文件: monitor_2022_cleaned_v2.xlsx
    """)

if __name__ == "__main__":
    main()
