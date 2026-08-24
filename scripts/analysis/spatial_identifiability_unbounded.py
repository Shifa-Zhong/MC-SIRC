#!/usr/bin/env python3
"""Profile spatial attenuation with gamma unbounded above zero.

The published implementation bounded gamma to [0.3, 5].  That bound can make
an otherwise flat k-gamma ridge appear to have an interior optimum.  This audit
profiles gamma analytically without the artificial bounds and compares the
result with the bounded implementation.
"""

from __future__ import annotations

import io
import json
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


ROOT = Path(__file__).resolve().parents[2]


def load_legacy_namespace():
    old_stdout = sys.stdout
    sink = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    try:
        sys.stdout = sink
        return runpy.run_path(str(ROOT / "scripts" / "analysis" / "spatial_model_v3_monthly.py"))
    finally:
        sys.stdout = old_stdout


def metrics(pred, target, weights):
    relative_sse = float(np.sum(weights * ((pred - target) / target) ** 2))
    ss_res = float(np.sum((pred - target) ** 2))
    ss_tot = float(np.sum((target - target.mean()) ** 2))
    return relative_sse, 1 - ss_res / ss_tot


def main():
    ns = load_legacy_namespace()
    k_grid = np.linspace(0.0, 0.30, 301)
    profile_rows = []
    summary_rows = []

    for pollutant in ns["pollutants"]:
        months = [m for m in ns["available_months"] if ns["monthly_loads"][m][pollutant] > 0]
        target = np.array([ns["monthly_loads"][m][pollutant] for m in months], dtype=float)
        weights = np.array([ns["cov_weights"][m] for m in months], dtype=float)
        records = []
        for k in k_grid:
            base = np.array(
                [
                    ns["compute_load_monthly"](
                        k, 1.0, pollutant, m, ns["pt_dist_default"], ns["cu_dist_default"]
                    )
                    for m in months
                ],
                dtype=float,
            )
            ratio = base / target
            gamma_free = float(np.sum(weights * ratio) / np.sum(weights * ratio * ratio))
            gamma_bounded = float(np.clip(gamma_free, 0.3, 5.0))
            sse_free, r2_free = metrics(gamma_free * base, target, weights)
            sse_bounded, r2_bounded = metrics(gamma_bounded * base, target, weights)
            record = {
                "Pollutant": pollutant,
                "k_km-1": float(k),
                "gamma_free": gamma_free,
                "gamma_bounded": gamma_bounded,
                "relative_SSE_free": sse_free,
                "relative_SSE_bounded": sse_bounded,
                "R2_free": r2_free,
                "R2_bounded": r2_bounded,
            }
            records.append(record)
            profile_rows.append(record)

        frame = pd.DataFrame(records)
        free_idx = int(frame.relative_SSE_free.idxmin())
        bounded_idx = int(frame.relative_SSE_bounded.idxmin())
        free_best = frame.iloc[free_idx]
        bounded_best = frame.iloc[bounded_idx]
        k0 = frame.iloc[0]
        summary_rows.append(
            {
                "Pollutant": pollutant,
                "Months": len(months),
                "k_best_free": free_best["k_km-1"],
                "gamma_best_free": free_best["gamma_free"],
                "R2_k0_free": k0["R2_free"],
                "R2_best_free": free_best["R2_free"],
                "Delta_R2_free": free_best["R2_free"] - k0["R2_free"],
                "SSE_ratio_k0_to_best_free": k0["relative_SSE_free"] / free_best["relative_SSE_free"],
                "k_best_bounded": bounded_best["k_km-1"],
                "gamma_best_bounded": bounded_best["gamma_bounded"],
                "R2_k0_bounded": k0["R2_bounded"],
                "R2_best_bounded": bounded_best["R2_bounded"],
                "Delta_R2_bounded": bounded_best["R2_bounded"] - k0["R2_bounded"],
                "gamma_k0_free": k0["gamma_free"],
                "gamma_k0_hits_paper_bound": bool(k0["gamma_free"] < 0.3 or k0["gamma_free"] > 5.0),
            }
        )

    summary = pd.DataFrame(summary_rows)
    profile = pd.DataFrame(profile_rows)
    out_xlsx = ROOT / "output" / "results" / "spatial_identifiability_unbounded.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        profile.to_excel(writer, sheet_name="Profile", index=False)
    out_json = ROOT / "output" / "results" / "spatial_identifiability_unbounded.json"
    out_json.write_text(
        json.dumps(summary.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(out_xlsx)


if __name__ == "__main__":
    main()
