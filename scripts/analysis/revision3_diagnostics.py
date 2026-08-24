#!/usr/bin/env python3
"""Diagnostics added for the 2026-08 major revision.

This script is intentionally conservative.  It does not treat a regularized
one-observation inversion as source-specific validation, and it explicitly
profiles the distance-decay model against the k=0 flow-only null.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[2]
OUT_RESULTS = ROOT / "output" / "results"
OUT_REPORTS = ROOT / "output" / "reports"
OUT_RESULTS.mkdir(parents=True, exist_ok=True)
OUT_REPORTS.mkdir(parents=True, exist_ok=True)


def load_setup_a_module():
    path = ROOT / "scripts" / "optimization" / "rerun_setup_A.py"
    spec = importlib.util.spec_from_file_location("setup_a_revision3", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def monitored_load_scenarios():
    """Return internally consistent annual-load scenarios in tonnes.

    S1 is the observed-hours lower bound. S2 scales each month by its own
    coverage and is the revised default. S3 reproduces annual-mean scaling but
    uses the correct 8,760-hour denominator. S4 inflates only the S2-imputed
    portion by 50%, rather than multiplying the entire annual load by 1.5.
    """

    raw = {"COD": 111.861560, "氨氮": 3.902692, "总氮": 49.368193, "总磷": 0.570772}
    monthly = {"COD": 140.864, "氨氮": 4.785, "总氮": 57.774, "总磷": 0.758}
    annual_factor = 8760 / 5928
    global_scaled = {p: v * annual_factor for p, v in raw.items()}
    event_upper = {p: raw[p] + 1.5 * (monthly[p] - raw[p]) for p in raw}
    return {
        "S1 observed-only": raw,
        "S2 month-specific (default)": monthly,
        "S3 annual-mean": global_scaled,
        "S4 event-weighted upper": event_upper,
    }


def prior_conflict_tier(z):
    if z > 2:
        return "A"
    if z > 1:
        return "B"
    return "C"


def run_missing_and_rank_diagnostics(setup):
    scenarios = monitored_load_scenarios()
    detail_rows = []
    summary_rows = []
    rank_rows = []
    map_by_scenario = {}

    for scenario_name, loads in scenarios.items():
        map_by_scenario[scenario_name] = {}
        for pollutant, target in loads.items():
            source_data = {k: v for k, v in setup.SOURCE_DATA[pollutant].items() if v > 0}
            names = list(source_data)
            result = setup.map_optimize(
                source_data,
                target,
                names,
                setup.DEFAULT_PRIORS,
                sigma_obs_frac=0.10,
                n_starts=30,
                seed=42,
            )
            factors = {name: float(result.x[i]) for i, name in enumerate(names)}
            unknown = float(result.x[-1])
            predicted = sum(source_data[n] * factors[n] for n in names) / 1000 + unknown
            deviation = (predicted - target) / target * 100
            components = {n: source_data[n] * factors[n] / 1000 for n in names}
            ordering = sorted(components, key=components.get, reverse=True)
            map_by_scenario[scenario_name][pollutant] = {
                "target": target,
                "predicted": predicted,
                "deviation": deviation,
                "unknown": unknown,
                "factors": factors,
                "components": components,
                "ordering": ordering,
            }
            tiers = []
            for name in names:
                prior = setup.DEFAULT_PRIORS[name]
                z = abs(factors[name] - prior["mu"]) / prior["sigma"]
                tier = prior_conflict_tier(z)
                tiers.append(tier)
                detail_rows.append(
                    {
                        "Scenario": scenario_name,
                        "Pollutant": pollutant,
                        "Source": name,
                        "Target_t": target,
                        "MAP_factor": factors[name],
                        "Prior_mu": prior["mu"],
                        "Prior_sigma": prior["sigma"],
                        "z": z,
                        "Prior_conflict_tier": tier,
                        "Regularized_component_t": components[name],
                    }
                )
            summary_rows.append(
                {
                    "Scenario": scenario_name,
                    "Pollutant": pollutant,
                    "Monitored_t": target,
                    "Reconciled_t": predicted,
                    "Deviation_pct": deviation,
                    "Tier_A_count": tiers.count("A"),
                    "Tier_B_count": tiers.count("B"),
                    "Tier_C_count": tiers.count("C"),
                    "Top_regularized_component": ordering[0],
                }
            )

    default_name = "S2 month-specific (default)"
    for scenario_name in scenarios:
        for pollutant in scenarios[scenario_name]:
            default_order = map_by_scenario[default_name][pollutant]["ordering"]
            this_order = map_by_scenario[scenario_name][pollutant]["ordering"]
            union = default_order
            x = [default_order.index(n) for n in union]
            y = [this_order.index(n) for n in union]
            rho = float(spearmanr(x, y).statistic)
            rank_rows.append(
                {
                    "Scenario": scenario_name,
                    "Pollutant": pollutant,
                    "Spearman_vs_default": rho,
                    "Top_source": this_order[0],
                    "Top3": " | ".join(this_order[:3]),
                }
            )

    # Track the four formerly labelled "data-driven" pairs without retaining
    # that interpretation.  Persistence here means persistence of prior conflict.
    flagged_pairs = [
        ("COD", "规模畜禽养殖"),
        ("总磷", "规模畜禽养殖"),
        ("总磷", "点-工业源"),
        ("总磷", "点-集中式污染治理设施"),
    ]
    persistence_rows = []
    detail_df = pd.DataFrame(detail_rows)
    for pollutant, source in flagged_pairs:
        subset = detail_df[(detail_df.Pollutant == pollutant) & (detail_df.Source == source)]
        row = {"Pollutant": pollutant, "Source": source}
        for _, record in subset.iterrows():
            row[record["Scenario"]] = record["Prior_conflict_tier"]
            row[record["Scenario"] + " factor"] = record["MAP_factor"]
        row["Tier_A_scenarios"] = int((subset.Prior_conflict_tier == "A").sum())
        persistence_rows.append(row)

    return {
        "scenario_summary": pd.DataFrame(summary_rows),
        "scenario_detail": detail_df,
        "rank_stability": pd.DataFrame(rank_rows),
        "flag_persistence": pd.DataFrame(persistence_rows),
        "map_by_scenario": map_by_scenario,
    }


def run_annual_identifiability_diagnostics(setup, missing_results):
    default = missing_results["map_by_scenario"]["S2 month-specific (default)"]
    rank_rows = []
    equivalent_rows = []

    for pollutant, result in default.items():
        source_data = {k: v for k, v in setup.SOURCE_DATA[pollutant].items() if v > 0}
        names = list(source_data)
        n_params = len(names) + 1  # source factors plus unknown-source term
        rank_rows.append(
            {
                "Pollutant": pollutant,
                "Annual_observations": 1,
                "Active_source_factors": len(names),
                "Unknown_source_terms": 1,
                "Jacobian_rank": 1,
                "Nullity": n_params - 1,
                "Identifiable_linear_combinations": 1,
            }
        )

        factors = result["factors"]
        best = None
        # Search for a sizeable pairwise null-space move that respects bounds.
        for i, source_i in enumerate(names):
            ai = source_data[source_i] / 1000
            for j, source_j in enumerate(names):
                if i == j:
                    continue
                aj = source_data[source_j] / 1000
                max_delta = min(2.0 - factors[source_i], (factors[source_j] - 0.1) * aj / ai)
                if max_delta <= 0:
                    continue
                score = max_delta * max(1.0, ai / aj)
                if best is None or score > best[0]:
                    best = (score, source_i, source_j, max_delta)
        if best is None:
            continue
        _, source_i, source_j, max_delta = best
        delta = 0.8 * max_delta
        ai = source_data[source_i] / 1000
        aj = source_data[source_j] / 1000
        f2_i = factors[source_i] + delta
        f2_j = factors[source_j] - delta * ai / aj
        load1 = sum(source_data[n] / 1000 * factors[n] for n in names)
        alt = dict(factors)
        alt[source_i] = f2_i
        alt[source_j] = f2_j
        load2 = sum(source_data[n] / 1000 * alt[n] for n in names)
        equivalent_rows.append(
            {
                "Pollutant": pollutant,
                "Source_increased": source_i,
                "f_original_i": factors[source_i],
                "f_alternative_i": f2_i,
                "Source_decreased": source_j,
                "f_original_j": factors[source_j],
                "f_alternative_j": f2_j,
                "Regularized_source_sum_1_t": load1,
                "Regularized_source_sum_2_t": load2,
                "Absolute_load_difference_kg": abs(load2 - load1) * 1000,
            }
        )

    return pd.DataFrame(rank_rows), pd.DataFrame(equivalent_rows)


def run_spatial_profile_diagnostics():
    spatial_script = ROOT / "scripts" / "analysis" / "spatial_model_v3_monthly.py"
    # The legacy script prints a long report and regenerates its own outputs.
    # The legacy script expects sys.stdout.buffer, so use a binary-backed sink.
    old_stdout = sys.stdout
    sink = io.TextIOWrapper(io.BytesIO(), encoding='utf-8')
    try:
        sys.stdout = sink
        ns = runpy.run_path(str(spatial_script))
    finally:
        sys.stdout = old_stdout

    rows = []
    profile_rows = []
    k_grid = np.linspace(0.0, 0.30, 301)
    for pollutant in ns["pollutants"]:
        months = [m for m in ns["available_months"] if ns["monthly_loads"][m][pollutant] > 0]
        target = np.array([ns["monthly_loads"][m][pollutant] for m in months], dtype=float)
        weights = np.array([ns["cov_weights"][m] for m in months], dtype=float)
        r2_values = []
        objective_values = []
        gamma_values = []
        for k in k_grid:
            base = np.array(
                [
                    ns["compute_load_monthly"](
                        k,
                        1.0,
                        pollutant,
                        m,
                        ns["pt_dist_default"],
                        ns["cu_dist_default"],
                    )
                    for m in months
                ],
                dtype=float,
            )
            ratio = base / target
            gamma = float(np.sum(weights * ratio) / np.sum(weights * ratio * ratio))
            pred = gamma * base
            objective = float(np.sum(weights * ((pred - target) / target) ** 2))
            ss_res = float(np.sum((pred - target) ** 2))
            ss_tot = float(np.sum((target - target.mean()) ** 2))
            r2 = 1 - ss_res / ss_tot
            r2_values.append(r2)
            objective_values.append(objective)
            gamma_values.append(gamma)
            profile_rows.append(
                {
                    "Pollutant": pollutant,
                    "k_km-1": k,
                    "gamma_profiled": gamma,
                    "relative_SSE": objective,
                    "R2": r2,
                }
            )

        r2_values = np.asarray(r2_values)
        objective_values = np.asarray(objective_values)
        best_idx = int(np.argmin(objective_values))
        rows.append(
            {
                "Pollutant": pollutant,
                "Months": len(months),
                "k_at_profile_min": float(k_grid[best_idx]),
                "gamma_at_profile_min": float(gamma_values[best_idx]),
                "R2_k0_flow_only": float(r2_values[0]),
                "R2_profile_min": float(r2_values[best_idx]),
                "Delta_R2_vs_k0": float(r2_values[best_idx] - r2_values[0]),
                "R2_range_across_k": float(r2_values.max() - r2_values.min()),
                "Relative_SSE_k0": float(objective_values[0]),
                "Relative_SSE_min": float(objective_values[best_idx]),
                "SSE_ratio_k0_to_min": float(objective_values[0] / objective_values[best_idx]),
                "Interpretation": "k not estimable from shared/near-shared monthly allocation",
            }
        )

    return pd.DataFrame(rows), pd.DataFrame(profile_rows)


def to_jsonable_frame(frame):
    return frame.replace({np.nan: None}).to_dict(orient="records")


def main():
    setup = load_setup_a_module()
    missing = run_missing_and_rank_diagnostics(setup)
    annual_rank, equivalent = run_annual_identifiability_diagnostics(setup, missing)
    spatial_summary, spatial_profile = run_spatial_profile_diagnostics()

    excel_path = OUT_RESULTS / "revision3_identifiability_and_missingness.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        missing["scenario_summary"].to_excel(writer, sheet_name="Missing_summary", index=False)
        missing["scenario_detail"].to_excel(writer, sheet_name="Missing_detail", index=False)
        missing["rank_stability"].to_excel(writer, sheet_name="Rank_stability", index=False)
        missing["flag_persistence"].to_excel(writer, sheet_name="Flag_persistence", index=False)
        annual_rank.to_excel(writer, sheet_name="Annual_rank_nullity", index=False)
        equivalent.to_excel(writer, sheet_name="Equivalent_solutions", index=False)
        spatial_summary.to_excel(writer, sheet_name="Spatial_null_test", index=False)
        spatial_profile.to_excel(writer, sheet_name="Spatial_profile", index=False)

    payload = {
        "hours": {"observed": 5928, "expected": 8760, "missing": 2832},
        "missing_summary": to_jsonable_frame(missing["scenario_summary"]),
        "rank_stability": to_jsonable_frame(missing["rank_stability"]),
        "flag_persistence": to_jsonable_frame(missing["flag_persistence"]),
        "annual_rank_nullity": to_jsonable_frame(annual_rank),
        "equivalent_solutions": to_jsonable_frame(equivalent),
        "spatial_null_test": to_jsonable_frame(spatial_summary),
    }
    json_path = OUT_RESULTS / "revision3_diagnostics.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "Revision-3 identifiability and missingness diagnostics",
        "",
        "Missing-data scenario summary:",
        missing["scenario_summary"].to_string(index=False),
        "",
        "Former Rating-A pair persistence as prior-conflict flags:",
        missing["flag_persistence"].to_string(index=False),
        "",
        "Annual rank/nullity:",
        annual_rank.to_string(index=False),
        "",
        "Exactly equivalent source-factor allocations:",
        equivalent.to_string(index=False),
        "",
        "Spatial k=0 null comparison:",
        spatial_summary.to_string(index=False),
    ]
    report_path = OUT_REPORTS / "revision3_diagnostics.txt"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(report_path)
    print(excel_path)
    print(json_path)
    print(spatial_summary.to_string(index=False))


if __name__ == "__main__":
    main()
