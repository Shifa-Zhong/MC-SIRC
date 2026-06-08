#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多年×月度监测负荷提取管线（2019-2024）

输入：data/raw/monitor.xlsx（逐小时浓度+流量，header=1，跳过单位行）

输出（同一个 Excel 多个 sheet）：data/processed/monthly_loads_multiyear.xlsx
  - observed_monthly_loads    : 实测累计（仅浓度+流量同时非空小时，kg）
  - observed_monthly_coverage : 实测累计的有效小时数
  - observed_annual_loads     : 实测累计年总负荷（kg）
  - filled_monthly_loads      : v2 清洗+插值后月负荷（kg）— 与 2022 主清洗一致
  - filled_annual_loads       : v2 清洗+插值后年负荷（kg）
  - data_coverage_summary     : 每年每污染物的覆盖率统计
  - metadata                  : 公式与参数说明

关键修复（基于审计结果）：
  1. 不硬编码年份，自动遍历所有可用年份
  2. 显式区分「实测累计」与「v2 清洗外推」，避免静默 fillna(0)
  3. NaN 处理透明（每个污染物独立计算有效小时）
  4. UTF-8 IO，避免 Windows cp1252 崩溃
  5. 清洗策略与 clean_data_all_v2.py 一致（流量阈值 + 浓度线性插值 + 流量历史同期填充）

负荷公式：
  Load(kg) = Σ_t [ C(mg/L) × Q(m³/s) × 3.6 ]
  其中 3.6 = 3600 s/h × 1000 L/m³ ÷ 1e6 mg/kg
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
RAW_FILE = ROOT / "data" / "raw" / "monitor.xlsx"
OUT_FILE = ROOT / "data" / "processed" / "monthly_loads_multiyear.xlsx"

COL_TIME = "监测时间"
COL_FLOW = "瞬时流量(m³/s)"
POLL_COLS = {
    "COD":   "化学需氧量(mg/L)",
    "NH3-N": "氨氮(mg/L)",
    "TN":    "总氮(mg/L)",
    "TP":    "总磷(mg/L)",
}

FLOW_MIN, FLOW_MAX = 0.0, 50.0
KG_PER_HOUR = 3600 * 1000 / 1_000_000  # = 3.6


# ─────────────────────────────────────────────────────────────────────────
# 加载与基础清洗
# ─────────────────────────────────────────────────────────────────────────

def load_raw(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, header=1, skiprows=[2])
    df = df.rename(columns={c: c.strip() for c in df.columns})
    df[COL_TIME] = pd.to_datetime(df[COL_TIME], errors="coerce")
    df = df.dropna(subset=[COL_TIME]).copy()
    df[COL_FLOW] = pd.to_numeric(df[COL_FLOW], errors="coerce")
    for c in POLL_COLS.values():
        df[c] = pd.to_numeric(df[c], errors="coerce")
    bad = (df[COL_FLOW] < FLOW_MIN) | (df[COL_FLOW] > FLOW_MAX)
    n_bad = int(bad.sum())
    df.loc[bad, COL_FLOW] = np.nan
    if n_bad:
        print(f"  流量阈值 [{FLOW_MIN}, {FLOW_MAX}] m³/s 外的 {n_bad} 条记录置 NaN")
    df = df.sort_values(COL_TIME).reset_index(drop=True)
    df["year"] = df[COL_TIME].dt.year
    df["month"] = df[COL_TIME].dt.month
    return df


# ─────────────────────────────────────────────────────────────────────────
# 路线 1：实测累计（仅浓度+流量同时非空小时）
# ─────────────────────────────────────────────────────────────────────────

def observed_monthly(df: pd.DataFrame, conc_col: str) -> tuple[pd.Series, pd.Series]:
    mask = df[conc_col].notna() & df[COL_FLOW].notna()
    sub = df.loc[mask, [COL_TIME, conc_col, COL_FLOW]].copy()
    sub["load_kg"] = sub[conc_col] * sub[COL_FLOW] * KG_PER_HOUR
    sub["year"] = sub[COL_TIME].dt.year
    sub["month"] = sub[COL_TIME].dt.month
    load = sub.groupby(["year", "month"])["load_kg"].sum()
    cov = sub.groupby(["year", "month"]).size()
    return load, cov


# ─────────────────────────────────────────────────────────────────────────
# 路线 2：v2 清洗+插值（与 clean_data_all_v2.py 一致），输出全年外推月负荷
# ─────────────────────────────────────────────────────────────────────────

def v2_clean_one_year(df_all: pd.DataFrame, year: int) -> pd.DataFrame:
    """对单年应用与 clean_data_all_v2 一致的清洗策略，返回该年逐小时清洗后的 DF。"""
    df_y = df_all[df_all["year"] == year].copy().sort_values(COL_TIME).reset_index(drop=True)

    # 浓度：线性插值 + 双向延展
    for col in POLL_COLS.values():
        df_y[col] = df_y[col].interpolate(method="linear", limit_direction="both")

    # 流量 3 级填充：阈值已在 load_raw 完成
    # Level 1: 历史同期（月-日-时）中位数
    df_all_clean = df_all.copy()
    df_all_clean.loc[
        (df_all_clean[COL_FLOW] < FLOW_MIN) | (df_all_clean[COL_FLOW] > FLOW_MAX),
        COL_FLOW,
    ] = np.nan
    df_all_clean["time_key"] = (
        df_all_clean[COL_TIME].dt.month.astype(str) + "-"
        + df_all_clean[COL_TIME].dt.day.astype(str) + "-"
        + df_all_clean[COL_TIME].dt.hour.astype(str)
    )
    df_y["time_key"] = (
        df_y[COL_TIME].dt.month.astype(str) + "-"
        + df_y[COL_TIME].dt.day.astype(str) + "-"
        + df_y[COL_TIME].dt.hour.astype(str)
    )
    hist = df_all_clean[df_all_clean["year"] != year].groupby("time_key")[COL_FLOW].median()
    miss = df_y[COL_FLOW].isna()
    df_y.loc[miss, COL_FLOW] = df_y.loc[miss, "time_key"].map(hist)

    # Level 2: 相邻月份中位数
    for m in range(1, 13):
        m_mask = df_y["month"] == m
        m_miss = m_mask & df_y[COL_FLOW].isna()
        if m_miss.sum() == 0:
            continue
        prev_m = 12 if m == 1 else m - 1
        next_m = 1 if m == 12 else m + 1
        combined = pd.concat([
            df_y.loc[df_y["month"] == prev_m, COL_FLOW].dropna(),
            df_y.loc[df_y["month"] == next_m, COL_FLOW].dropna(),
        ])
        if len(combined) > 0:
            df_y.loc[m_miss, COL_FLOW] = combined.median()

    # Level 3: 线性插值
    df_y[COL_FLOW] = df_y[COL_FLOW].interpolate(method="linear", limit_direction="both")
    df_y.drop(columns="time_key", inplace=True)
    return df_y


def filled_monthly(df_all: pd.DataFrame, years: list[int]) -> dict[str, pd.Series]:
    """对每年做 v2 清洗后，计算每个污染物的月度负荷。返回 {pollutant: Series(index=(year,month))}."""
    rows = []
    for y in years:
        df_y = v2_clean_one_year(df_all, int(y))
        df_y["year"] = df_y[COL_TIME].dt.year
        df_y["month"] = df_y[COL_TIME].dt.month
        for pname, ccol in POLL_COLS.items():
            mask = df_y[ccol].notna() & df_y[COL_FLOW].notna()
            tmp = df_y.loc[mask].copy()
            tmp["load_kg"] = tmp[ccol] * tmp[COL_FLOW] * KG_PER_HOUR
            agg = tmp.groupby("month")["load_kg"].sum()
            for m, v in agg.items():
                rows.append({"year": int(y), "month": int(m), "pollutant": pname, "load_kg": float(v)})

    long_df = pd.DataFrame(rows)
    out: dict[str, pd.Series] = {}
    for p in POLL_COLS:
        s = long_df[long_df["pollutant"] == p].set_index(["year", "month"])["load_kg"]
        out[p] = s
    return out


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def to_wide(frames: dict[str, pd.Series], years: list[int]) -> pd.DataFrame:
    wide = pd.DataFrame(frames)
    idx = pd.MultiIndex.from_product([years, range(1, 13)], names=["year", "month"])
    wide = wide.reindex(idx)
    return wide.reset_index()


def main() -> None:
    print("=" * 80)
    print("多年×月度监测负荷提取 v1.1")
    print(f"读取: {RAW_FILE}")
    print("=" * 80)

    if not RAW_FILE.exists():
        print(f"❌ 原始数据不存在: {RAW_FILE}")
        sys.exit(1)

    df = load_raw(RAW_FILE)
    years = sorted(int(y) for y in df["year"].unique())
    print(f"\n总记录: {len(df):,} 条；时间范围 {df[COL_TIME].min()} → {df[COL_TIME].max()}")
    print(f"可用年份: {years}")

    # 路线 1：实测累计
    print("\n=== 路线 1：实测累计（仅浓度+流量同时非空） ===")
    obs_load: dict[str, pd.Series] = {}
    obs_cov: dict[str, pd.Series] = {}
    for pname, ccol in POLL_COLS.items():
        load_s, cov_s = observed_monthly(df, ccol)
        obs_load[pname] = load_s
        obs_cov[pname] = cov_s
        annual_load = load_s.groupby(level=0).sum()
        annual_cov = cov_s.groupby(level=0).sum()
        print(f"\n[{pname}]")
        for y in years:
            v = annual_load.get(y, 0.0)
            c = annual_cov.get(y, 0)
            hours = 8784 if y % 4 == 0 else 8760
            print(f"  {y}: {v:>10,.1f} kg  (有效 {int(c):>4d}/{hours} h = {c/hours*100:5.1f}%)")

    # 路线 2：v2 清洗+插值
    print("\n=== 路线 2：v2 清洗+插值后年负荷（与单年 clean_data_all_v2 一致） ===")
    filled = filled_monthly(df, years)
    for pname, s in filled.items():
        annual = s.groupby(level=0).sum()
        print(f"\n[{pname}]")
        for y in years:
            v = annual.get(y, 0.0)
            print(f"  {y}: {v:>12,.1f} kg")

    # ── 整理输出 ──
    obs_loads_wide = to_wide(obs_load, years)
    obs_cov_wide = to_wide({k: v.astype(float) for k, v in obs_cov.items()}, years).fillna(0)
    for c in POLL_COLS:
        obs_cov_wide[c] = obs_cov_wide[c].astype(int)

    obs_annual = obs_loads_wide.groupby("year")[list(POLL_COLS)].sum(min_count=1)

    filled_loads_wide = to_wide(filled, years)
    filled_annual = filled_loads_wide.groupby("year")[list(POLL_COLS)].sum(min_count=1)

    # 覆盖率汇总
    cov_summary_rows = []
    for y in years:
        hours = 8784 if y % 4 == 0 else 8760
        row = {"year": y, "hours_in_year": hours}
        for p in POLL_COLS:
            c = int(obs_cov[p].xs(y, level=0).sum()) if y in obs_cov[p].index.get_level_values(0) else 0
            row[f"{p}_valid_hours"] = c
            row[f"{p}_coverage_pct"] = round(c / hours * 100, 2)
        cov_summary_rows.append(row)
    cov_summary = pd.DataFrame(cov_summary_rows)

    metadata = pd.DataFrame({
        "key": [
            "extraction_time", "raw_source", "load_formula", "kg_per_hour_factor",
            "flow_threshold_min_m3s", "flow_threshold_max_m3s",
            "observed_strategy", "filled_strategy",
        ],
        "value": [
            datetime.now().isoformat(timespec="seconds"),
            str(RAW_FILE),
            "Load(kg) = Σ_t [C(mg/L) × Q(m³/s) × 3.6]",
            f"{KG_PER_HOUR:.6f}",
            f"{FLOW_MIN}", f"{FLOW_MAX}",
            "仅累计浓度+流量同时非空的小时；缺月保留 NaN",
            "浓度线性插值 + 流量 3 级填充 (历史同期/相邻月/线性)，与 clean_data_all_v2 一致",
        ],
    })

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_FILE, engine="openpyxl") as w:
        obs_loads_wide.to_excel(w, sheet_name="observed_monthly_loads", index=False)
        obs_cov_wide.to_excel(w, sheet_name="observed_monthly_coverage", index=False)
        obs_annual.reset_index().to_excel(w, sheet_name="observed_annual_loads", index=False)
        filled_loads_wide.to_excel(w, sheet_name="filled_monthly_loads", index=False)
        filled_annual.reset_index().to_excel(w, sheet_name="filled_annual_loads", index=False)
        cov_summary.to_excel(w, sheet_name="data_coverage_summary", index=False)
        metadata.to_excel(w, sheet_name="metadata", index=False)

    print(f"\n✓ 输出: {OUT_FILE}")
    print("  Sheets: observed_*, filled_*, data_coverage_summary, metadata")


if __name__ == "__main__":
    main()
