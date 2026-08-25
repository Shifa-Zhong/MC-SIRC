#!/usr/bin/env python3
"""Recompute S3 MCMC summaries with convergence diagnostics for the final revision."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.optimization import rerun_setup_A as setup


OUT = ROOT / "output" / "results" / "revision5_mcmc_diagnostics.xlsx"
POLLUTANTS = ["COD", "氨氮", "总氮", "总磷"]
POLLUTANT_KEYS = {"COD": "COD", "氨氮": "NH3N", "总氮": "TN", "总磷": "TP"}
S3_LOADS = {name: value * 8760 / 5928 for name, value in setup.RAW_MONITOR.items()}


def split_rhat(chain: np.ndarray) -> np.ndarray:
    """Return split-Rhat for a chain shaped (steps, walkers, dimensions)."""
    chains = np.transpose(chain, (1, 0, 2))
    half = chains.shape[1] // 2
    split = np.concatenate((chains[:, :half, :], chains[:, -half:, :]), axis=0)
    n = split.shape[1]
    within = np.mean(np.var(split, axis=1, ddof=1), axis=0)
    between = n * np.var(np.mean(split, axis=1), axis=0, ddof=1)
    variance = ((n - 1) / n) * within + between / n
    return np.sqrt(variance / within)


def run_pollutant(pollutant: str):
    try:
        import emcee
    except ImportError as exc:
        raise RuntimeError("emcee is required for the final MCMC diagnostics") from exc

    source_data = {name: value for name, value in setup.SOURCE_DATA[pollutant].items() if value > 0}
    names = list(source_data)
    monitored = S3_LOADS[pollutant]
    n_walkers, n_steps, n_burn = 32, 20_000, 5_000
    np.random.seed(42)
    n_dim = len(names) + 1

    def log_prob(theta):
        if np.any(theta[:-1] < 0.1) or np.any(theta[:-1] > 2.0):
            return -np.inf
        if theta[-1] < 0 or theta[-1] > 0.5 * monitored:
            return -np.inf
        return -setup.neg_log_posterior(theta, source_data, monitored, names, setup.DEFAULT_PRIORS)

    walkers = []
    for _ in range(n_walkers):
        values = [setup.DEFAULT_PRIORS[name]["mu"] + np.random.normal(0, 0.10) for name in names]
        unknown = max(0.1 * monitored * (1 + np.random.normal(0, 0.5)), 0.01 * monitored)
        values.append(unknown)
        walkers.append(np.clip(values, [0.1] * len(names) + [0.001 * monitored],
                               [2.0] * len(names) + [0.49 * monitored]))

    sampler = emcee.EnsembleSampler(n_walkers, n_dim, log_prob)
    sampler.run_mcmc(np.asarray(walkers), n_steps, progress=False)
    chain = sampler.get_chain(discard=n_burn)
    flat = chain.reshape(-1, n_dim)
    labels = names + ["Unknown"]
    rhat = split_rhat(chain)
    try:
        tau = np.asarray(sampler.get_autocorr_time(discard=n_burn, tol=0, quiet=True))
    except Exception:
        tau = np.full(n_dim, np.nan)
    ess = np.where(np.isfinite(tau) & (tau > 0), chain.shape[0] * chain.shape[1] / tau, np.nan)

    rows = []
    for index, label in enumerate(labels):
        values = flat[:, index]
        rows.append({
            "Parameter": label,
            "Mean": float(np.mean(values)),
            "Median": float(np.median(values)),
            "Std": float(np.std(values, ddof=1)),
            "CrI_2.5": float(np.percentile(values, 2.5)),
            "CrI_97.5": float(np.percentile(values, 97.5)),
            "Split_Rhat": float(rhat[index]),
            "ESS": float(ess[index]),
            "Tau": float(tau[index]),
        })
    metadata = {
        "Pollutant": pollutant,
        "Walkers": n_walkers,
        "Steps": n_steps,
        "Burn_in": n_burn,
        "Retained_samples": int(flat.shape[0]),
        "Mean_acceptance_fraction": float(np.mean(sampler.acceptance_fraction)),
        "Max_split_Rhat": float(np.max(rhat)),
        "Min_ESS": float(np.nanmin(ess)),
        "Seed": 42,
        "Scenario": "S3 annual-mean sensitivity",
    }
    correlation = pd.DataFrame(np.corrcoef(flat.T), index=labels, columns=labels)
    return pd.DataFrame(rows), correlation, metadata


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    summaries = {}
    correlations = {}
    metadata = []
    for pollutant in POLLUTANTS:
        print(f"MCMC diagnostics: {pollutant}", flush=True)
        summaries[pollutant], correlations[pollutant], item = run_pollutant(pollutant)
        metadata.append(item)
    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        pd.DataFrame(metadata).to_excel(writer, sheet_name="Metadata", index=False)
        for pollutant in POLLUTANTS:
            key = POLLUTANT_KEYS[pollutant]
            summaries[pollutant].to_excel(writer, sheet_name=f"MCMC_{key}", index=False)
            correlations[pollutant].to_excel(writer, sheet_name=f"Corr_{key}")
    print(OUT)


if __name__ == "__main__":
    main()
