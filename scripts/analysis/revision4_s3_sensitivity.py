#!/usr/bin/env python3
"""Recompute S3 Bayesian sensitivity outputs with the corrected 8,760-hour year."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.optimization import rerun_setup_A as setup
OUT = ROOT / "output" / "results" / "revision4_s3_corrected_sensitivity.xlsx"
POLLUTANTS = ["COD", "氨氮", "总氮", "总磷"]
S3_LOADS = {name: value * 8760 / 5928 for name, value in setup.RAW_MONITOR.items()}
PRIOR_SCENARIOS = {
    "P1 low means": lambda mu, sigma: (0.5, sigma),
    "P2 default": lambda mu, sigma: (mu, sigma),
    "P3 high means": lambda mu, sigma: (1.2, sigma),
    "P4 weak": lambda mu, sigma: (mu, 0.5),
    "P5 diffuse": lambda mu, sigma: (mu, 1.0),
}


def active_data(pollutant: str):
    data = {name: value for name, value in setup.SOURCE_DATA[pollutant].items() if value > 0}
    return data, list(data)


def summarize_mcmc(pollutant: str):
    data, names = active_data(pollutant)
    monitored = S3_LOADS[pollutant]
    samples = setup.run_mcmc(
        data,
        monitored,
        names,
        setup.DEFAULT_PRIORS,
        n_walkers=32,
        n_steps=20_000,
        n_burn=5_000,
        seed=42,
    )
    if samples is None:
        raise RuntimeError("emcee is required for the corrected S3 sensitivity analysis")
    labels = names + ["Unknown"]
    rows = []
    for index, label in enumerate(labels):
        values = samples[:, index]
        rows.append(
            {
                "Parameter": label,
                "Mean": float(np.mean(values)),
                "Median": float(np.median(values)),
                "Std": float(np.std(values, ddof=1)),
                "CI_2.5": float(np.percentile(values, 2.5)),
                "CI_97.5": float(np.percentile(values, 97.5)),
            }
        )
    correlation = pd.DataFrame(np.corrcoef(samples.T), index=labels, columns=labels)
    return pd.DataFrame(rows), correlation


def prior_sensitivity(pollutant: str):
    data, names = active_data(pollutant)
    monitored = S3_LOADS[pollutant]
    rows = []
    for scenario, transform in PRIOR_SCENARIOS.items():
        priors = {}
        for source, values in setup.DEFAULT_PRIORS.items():
            mu, sigma = transform(values["mu"], values["sigma"])
            priors[source] = {"mu": mu, "sigma": sigma}
        result = setup.map_optimize(data, monitored, names, priors, seed=42)
        factors = dict(zip(names, result.x[:-1]))
        unknown = float(result.x[-1])
        predicted = sum(data[name] * factors[name] for name in names) / 1000 + unknown
        row = {
            "Scenario": scenario,
            "Deviation_pct": (predicted - monitored) / monitored * 100,
            "Unknown_t": unknown,
        }
        row.update(factors)
        rows.append(row)
    return pd.DataFrame(rows)


def observation_error_sensitivity():
    rows = []
    for pollutant in POLLUTANTS:
        data, names = active_data(pollutant)
        monitored = S3_LOADS[pollutant]
        for sigma in (0.05, 0.10, 0.20):
            result = setup.map_optimize(
                data,
                monitored,
                names,
                setup.DEFAULT_PRIORS,
                sigma_obs_frac=sigma,
                seed=42,
            )
            row = {"Pollutant": pollutant, "sigma_obs": f"{int(sigma * 100)}%"}
            row.update(dict(zip(names, result.x[:-1])))
            row["Unknown_t"] = float(result.x[-1])
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    mcmc = {}
    correlations = {}
    priors = {}
    for pollutant in POLLUTANTS:
        print(f"Recomputing corrected S3 outputs for {pollutant}...", flush=True)
        mcmc[pollutant], correlations[pollutant] = summarize_mcmc(pollutant)
        priors[pollutant] = prior_sensitivity(pollutant)
    sigma = observation_error_sensitivity()
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        pd.DataFrame(
            [{"Reference_hours": 8760, "Observed_hours": 5928, "Scale_factor": 8760 / 5928, "Seed": 42}]
        ).to_excel(writer, sheet_name="Metadata", index=False)
        for pollutant in POLLUTANTS:
            key = {"COD": "COD", "氨氮": "NH3N", "总氮": "TN", "总磷": "TP"}[pollutant]
            mcmc[pollutant].to_excel(writer, sheet_name=f"MCMC_{key}", index=False)
            correlations[pollutant].to_excel(writer, sheet_name=f"Corr_{key}")
            priors[pollutant].to_excel(writer, sheet_name=f"Prior_{key}", index=False)
        sigma.to_excel(writer, sheet_name="Sigma", index=False)
    print(OUT)


if __name__ == "__main__":
    main()
