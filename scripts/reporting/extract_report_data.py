#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取研究报告所需的所有数据
"""

import pandas as pd
import numpy as np
from pathlib import Path

base_dir = Path(__file__).parent.parent
output_file = base_dir / 'output' / 'report_data.txt'

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("=" * 80 + "\n")
    f.write("研究报告数据汇总\n")
    f.write("=" * 80 + "\n\n")

    # 1. 原始数据统计
    f.write("【1. 原始数据统计】\n")
    f.write("-" * 40 + "\n")

    try:
        monitor_file = base_dir / 'data' / 'monitor.xlsx'
        df_raw = pd.read_excel(monitor_file)
        f.write(f"监测数据原始记录数: {len(df_raw)}\n")
        f.write(f"监测数据列数: {len(df_raw.columns)}\n")
    except Exception as e:
        f.write(f"读取原始监测数据失败: {e}\n")

    try:
        rain_file = base_dir / 'data' / 'rain.xlsx'
        df_rain = pd.read_excel(rain_file)
        f.write(f"降雨数据记录数: {len(df_rain)}\n")
    except Exception as e:
        f.write(f"读取降雨数据失败: {e}\n")

    try:
        source_file = base_dir / 'data' / 'data(1).xlsx'
        xl = pd.ExcelFile(source_file)
        f.write(f"污染源数据sheets: {len(xl.sheet_names)}\n")
        for sheet in xl.sheet_names:
            df_sheet = pd.read_excel(source_file, sheet_name=sheet)
            f.write(f"  - {sheet}: {len(df_sheet)} 条\n")
    except Exception as e:
        f.write(f"读取污染源数据失败: {e}\n")

    f.write("\n")

    # 2. 清洗后数据统计
    f.write("【2. 清洗后监测数据统计】\n")
    f.write("-" * 40 + "\n")

    try:
        cleaned_file = base_dir / 'output' / 'monitor_2022_cleaned_v2.xlsx'
        df_cleaned = pd.read_excel(cleaned_file)
        f.write(f"清洗后记录数: {len(df_cleaned)}\n")
        f.write(f"时间范围: {df_cleaned['监测时间'].min()} 至 {df_cleaned['监测时间'].max()}\n")

        # 流量统计
        flow = df_cleaned['瞬时流量(m³/s)']
        f.write(f"\n流量统计:\n")
        f.write(f"  最小值: {flow.min():.4f} m³/s\n")
        f.write(f"  最大值: {flow.max():.4f} m³/s\n")
        f.write(f"  平均值: {flow.mean():.4f} m³/s\n")
        f.write(f"  中位数: {flow.median():.4f} m³/s\n")
        f.write(f"  标准差: {flow.std():.4f} m³/s\n")

        # 水质指标统计
        f.write(f"\n水质指标统计:\n")
        for col in ['氨氮(mg/L)', '总磷(mg/L)', '总氮(mg/L)', '化学需氧量(mg/L)']:
            if col in df_cleaned.columns:
                data = df_cleaned[col]
                f.write(f"  {col}:\n")
                f.write(f"    范围: {data.min():.4f} - {data.max():.4f}\n")
                f.write(f"    均值: {data.mean():.4f}\n")
                f.write(f"    中位数: {data.median():.4f}\n")

        # 降雨统计
        if '降水量(mm)' in df_cleaned.columns:
            rain = df_cleaned['降水量(mm)']
            f.write(f"\n降雨统计:\n")
            f.write(f"  降雨时段: {(rain > 0).sum()} 小时\n")
            f.write(f"  无雨时段: {(rain == 0).sum()} 小时\n")
            f.write(f"  最大小时降雨: {rain.max():.2f} mm\n")
            f.write(f"  年总降雨量: {rain.sum():.2f} mm\n")
    except Exception as e:
        f.write(f"读取清洗后数据失败: {e}\n")

    f.write("\n")

    # 3. 监测负荷结果
    f.write("【3. 监测数据污染物负荷】\n")
    f.write("-" * 40 + "\n")

    try:
        load_file = base_dir / 'output' / '监测数据污染物负荷统计.xlsx'
        df_load = pd.read_excel(load_file, sheet_name='监测数据总负荷')
        for _, row in df_load.iterrows():
            f.write(f"  {row['污染物']}: {row['总负荷(吨)']:.2f} 吨\n")

        # 降雨期对比
        df_rain_load = pd.read_excel(load_file, sheet_name='降雨期vs非降雨期')
        f.write(f"\n降雨期vs非降雨期负荷:\n")
        for _, row in df_rain_load.iterrows():
            f.write(f"  {row['污染物']}: 降雨期 {row['降雨期负荷(kg)']:.2f} kg ({row['降雨期占比(%)']:.1f}%)\n")
    except Exception as e:
        f.write(f"读取监测负荷数据失败: {e}\n")

    f.write("\n")

    # 4. 污染源入河量
    f.write("【4. 污染源入河量统计】\n")
    f.write("-" * 40 + "\n")

    try:
        inflow_file = base_dir / 'output' / '入河污染物总量统计.xlsx'
        df_inflow = pd.read_excel(inflow_file, sheet_name='入河量汇总(吨)')

        f.write("各污染源入河量(吨):\n")
        for _, row in df_inflow.iterrows():
            source = row['污染源']
            f.write(f"\n{source}:\n")
            for col in df_inflow.columns:
                if '吨' in col and col != '污染源':
                    val = row[col]
                    if pd.notna(val) and val > 0:
                        f.write(f"  {col}: {val:.2f}\n")
    except Exception as e:
        f.write(f"读取入河量数据失败: {e}\n")

    f.write("\n")

    # 5. 对比分析
    f.write("【5. 监测负荷vs入河量对比】\n")
    f.write("-" * 40 + "\n")

    try:
        compare_file = base_dir / 'output' / '污染负荷对比分析.xlsx'
        df_compare = pd.read_excel(compare_file, sheet_name='对比汇总')

        for _, row in df_compare.iterrows():
            f.write(f"\n{row['污染物']}:\n")
            f.write(f"  监测负荷: {row['监测数据负荷(吨)']:.2f} 吨\n")
            f.write(f"  入河量: {row['污染源入河量(吨)']:.2f} 吨\n")
            f.write(f"  差值: {row['差值(吨)']:.2f} 吨\n")
            f.write(f"  比值: {row['入河量/监测负荷']:.2f}x\n")
            f.write(f"  差异: {row['差异百分比(%)']:.1f}%\n")
    except Exception as e:
        f.write(f"读取对比分析数据失败: {e}\n")

    f.write("\n")

    # 6. 约束优化结果
    f.write("【6. 约束优化结果】\n")
    f.write("-" * 40 + "\n")

    try:
        opt1_file = base_dir / 'output' / '系数优化结果_考虑未知源.xlsx'
        df_opt1 = pd.read_excel(opt1_file, sheet_name='优化结果汇总')

        for _, row in df_opt1.iterrows():
            f.write(f"\n{row['污染物']}:\n")
            f.write(f"  监测值: {row['监测值(吨)']:.2f} 吨\n")
            f.write(f"  原始计算值: {row['原始计算值(吨)']:.2f} 吨\n")
            f.write(f"  修正后计算值: {row['修正后计算值(吨)']:.2f} 吨\n")
            f.write(f"  未知源: {row['未知源(吨)']:.2f} 吨\n")
            f.write(f"  原始偏差: {row['原始偏差(%)']:.1f}%\n")
            f.write(f"  修正后偏差: {row['修正后偏差(%)']:.1f}%\n")

        # 读取各污染物详情
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            try:
                df_detail = pd.read_excel(opt1_file, sheet_name=f'{pollutant}修正详情')
                f.write(f"\n{pollutant} 各污染源修正因子:\n")
                for _, row in df_detail.iterrows():
                    f.write(f"  {row['污染源']}: {row['修正因子']:.3f} (原{row['原始入河量(kg)']:.0f}kg → 修{row['修正后入河量(kg)']:.0f}kg)\n")
            except:
                pass
    except Exception as e:
        f.write(f"读取约束优化结果失败: {e}\n")

    f.write("\n")

    # 7. 贝叶斯优化结果
    f.write("【7. 贝叶斯优化结果】\n")
    f.write("-" * 40 + "\n")

    try:
        opt2_file = base_dir / 'output' / '系数优化结果_贝叶斯方法.xlsx'
        df_opt2 = pd.read_excel(opt2_file, sheet_name='优化结果汇总')

        for _, row in df_opt2.iterrows():
            f.write(f"\n{row['污染物']}:\n")
            f.write(f"  监测值: {row['监测值(吨)']:.2f} 吨\n")
            f.write(f"  原始计算值: {row['原始计算值(吨)']:.2f} 吨\n")
            f.write(f"  修正后计算值: {row['修正后计算值(吨)']:.2f} 吨\n")
            f.write(f"  未知源: {row['未知源(吨)']:.2f} ± {row['未知源标准差']:.2f} 吨\n")
            f.write(f"  原始偏差: {row['原始偏差(%)']:.1f}%\n")
            f.write(f"  修正后偏差: {row['修正后偏差(%)']:.1f}%\n")

        # 读取各污染物详情
        for pollutant in ['COD', '氨氮', '总氮', '总磷']:
            try:
                df_detail = pd.read_excel(opt2_file, sheet_name=f'{pollutant}详情')
                f.write(f"\n{pollutant} 各污染源修正因子及置信区间:\n")
                for _, row in df_detail.iterrows():
                    f.write(f"  {row['污染源']}: {row['修正因子']:.3f} [{row['95%CI下限']:.3f}, {row['95%CI上限']:.3f}]\n")
            except:
                pass

        # 异常检测
        try:
            df_anomaly = pd.read_excel(opt2_file, sheet_name='异常检测')
            f.write(f"\n异常污染源检测:\n")
            for _, row in df_anomaly.iterrows():
                f.write(f"  {row['污染物']} - {row['污染源']}: z-score={row['z-score']:.2f}, {row['判断']}\n")
        except:
            pass
    except Exception as e:
        f.write(f"读取贝叶斯优化结果失败: {e}\n")

    f.write("\n" + "=" * 80 + "\n")
    f.write("数据提取完成\n")
    f.write("=" * 80 + "\n")

print(f"数据已提取到: {output_file}")
