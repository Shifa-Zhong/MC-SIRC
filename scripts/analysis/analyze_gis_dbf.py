# -*- coding: utf-8 -*-
"""
分析GIS shapefile的属性表（通过读取.dbf文件）
输出每个文件的列名、类型、记录数、前5行样例数据、数值列基本统计
"""

import sys
import os
from dbfread import DBF
from collections import OrderedDict
import statistics

def analyze_dbf(dbf_path, out):
    """分析单个DBF文件并输出结果"""
    fname = os.path.basename(dbf_path)
    out.write("=" * 80 + "\n")
    out.write(f"文件: {fname}\n")
    out.write(f"路径: {dbf_path}\n")
    out.write("=" * 80 + "\n\n")

    try:
        table = DBF(dbf_path, encoding='utf-8')
    except Exception:
        try:
            table = DBF(dbf_path, encoding='gbk')
        except Exception:
            table = DBF(dbf_path, encoding='cp936')

    # Read all records into list
    records = list(table)
    num_records = len(records)

    out.write(f"记录数 (Number of records): {num_records}\n\n")

    # --- 1. Column names and types ---
    out.write("--- 列名与类型 (Column Names and Types) ---\n")
    out.write(f"{'序号':<6}{'字段名':<30}{'类型':<12}{'长度':<8}{'小数位':<8}\n")
    out.write("-" * 64 + "\n")

    field_names = []
    numeric_fields = []
    for i, field in enumerate(table.fields, 1):
        type_map = {
            'C': 'Character',
            'N': 'Numeric',
            'F': 'Float',
            'D': 'Date',
            'L': 'Logical',
            'M': 'Memo',
            'I': 'Integer',
            'B': 'Double',
            'O': 'Double',
        }
        type_str = type_map.get(field.type, field.type)
        out.write(f"{i:<6}{field.name:<30}{type_str:<12}{field.length:<8}{field.decimal_count:<8}\n")
        field_names.append(field.name)
        if field.type in ('N', 'F', 'I', 'B', 'O'):
            numeric_fields.append(field.name)
    out.write("\n")

    # --- 2. First 5 rows ---
    out.write("--- 前5行样例数据 (First 5 Rows) ---\n")
    sample = records[:5]
    if sample:
        # Build column widths based on content
        col_widths = {}
        for fn in field_names:
            vals = [str(r.get(fn, '')) for r in sample]
            max_val_len = max((len(v) for v in vals), default=0)
            col_widths[fn] = max(len(fn), max_val_len, 6) + 2

        # Header
        header = "行号  "
        for fn in field_names:
            header += f"{fn:<{col_widths[fn]}}"
        out.write(header.rstrip() + "\n")
        out.write("-" * min(len(header), 200) + "\n")

        # Rows
        for idx, rec in enumerate(sample, 1):
            row_str = f"{idx:<6}"
            for fn in field_names:
                val = rec.get(fn, '')
                val_str = str(val) if val is not None else 'NULL'
                row_str += f"{val_str:<{col_widths[fn]}}"
            out.write(row_str.rstrip() + "\n")
    else:
        out.write("(无数据)\n")
    out.write("\n")

    # --- 3. Basic statistics for numeric columns ---
    out.write("--- 数值列基本统计 (Basic Statistics for Numeric Columns) ---\n")
    if not numeric_fields:
        out.write("(无数值列)\n")
    else:
        stat_header = f"{'字段名':<25}{'非空数':<10}{'最小值':<18}{'最大值':<18}{'均值':<18}{'中位数':<18}{'标准差':<18}\n"
        out.write(stat_header)
        out.write("-" * 125 + "\n")

        for fn in numeric_fields:
            values = []
            null_count = 0
            for rec in records:
                v = rec.get(fn)
                if v is not None:
                    try:
                        values.append(float(v))
                    except (ValueError, TypeError):
                        null_count += 1
                else:
                    null_count += 1

            non_null = len(values)
            if non_null == 0:
                out.write(f"{fn:<25}{non_null:<10}{'N/A':<18}{'N/A':<18}{'N/A':<18}{'N/A':<18}{'N/A':<18}\n")
                continue

            min_val = min(values)
            max_val = max(values)
            mean_val = statistics.mean(values)
            median_val = statistics.median(values)
            stdev_val = statistics.stdev(values) if non_null > 1 else 0.0

            out.write(
                f"{fn:<25}"
                f"{non_null:<10}"
                f"{min_val:<18.6f}"
                f"{max_val:<18.6f}"
                f"{mean_val:<18.6f}"
                f"{median_val:<18.6f}"
                f"{stdev_val:<18.6f}\n"
            )

    out.write("\n\n")


def main():
    dbf_files = [
        r"D:\shanxi\gis\4项污染物面源单位面积排放量.dbf",
        r"D:\shanxi\gis\点源排放数据.dbf",
        r"D:\shanxi\gis\网格土地利用类型t.dbf",
    ]

    output_path = r"D:\shanxi\output\gis_属性分析.txt"

    with open(output_path, 'w', encoding='utf-8') as out:
        out.write("GIS Shapefile 属性表分析报告\n")
        out.write(f"分析文件数: {len(dbf_files)}\n")
        out.write("=" * 80 + "\n\n")

        for dbf_path in dbf_files:
            if not os.path.exists(dbf_path):
                out.write(f"[ERROR] 文件不存在: {dbf_path}\n\n")
                continue
            try:
                analyze_dbf(dbf_path, out)
                print(f"[OK] 已分析: {os.path.basename(dbf_path)}")
            except Exception as e:
                msg = f"[ERROR] 分析失败 {os.path.basename(dbf_path)}: {e}"
                out.write(msg + "\n\n")
                print(msg)

        out.write("=" * 80 + "\n")
        out.write("分析完成。\n")

    print(f"\n结果已保存至: {output_path}")


if __name__ == '__main__':
    main()
