#!/usr/bin/env python3
"""Generate the figures used in the 2026-08 revision."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "figures" / "revision3"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "Arial",
        "font.size": 10.5,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
    }
)
plt.rcParams['font.family'] = 'DejaVu Sans'

POLLUTANT_MAP = {"COD": "COD", "氨氮": "NH₃-N", "总氮": "TN", "总磷": "TP"}
SOURCE_MAP = {
    "面-农村生活污染源": "Rural domestic",
    "面-农业面源": "Agricultural NPS",
    "畜禽散养": "Household livestock",
    "面-水产养殖": "Aquaculture",
    "面-城市面源": "Urban NPS",
    "面-城镇散排": "Dispersed urban",
    "规模畜禽养殖": "Large livestock",
    "点-工业源": "Industrial",
    "点-集中式污染治理设施": "Central facility",
}


def panel_label(ax, label):
    ax.text(-0.12, 1.05, label, transform=ax.transAxes, fontsize=13, fontweight="bold", va="top")


def generate_figure2():
    path = ROOT / "output" / "results" / "revision3_identifiability_and_missingness.xlsx"
    detail = pd.read_excel(path, sheet_name="Missing_detail")
    summary = pd.read_excel(path, sheet_name="Missing_summary")
    flags = pd.read_excel(path, sheet_name="Flag_persistence")
    rank = pd.read_excel(path, sheet_name="Annual_rank_nullity")

    default = detail[detail.Scenario == "S2 month-specific (default)"].copy()
    sources = list(SOURCE_MAP)
    pollutants = ["COD", "氨氮", "总氮", "总磷"]
    matrix = np.full((4, len(sources)), np.nan)
    for i, pollutant in enumerate(pollutants):
        for j, source in enumerate(sources):
            match = default[(default.Pollutant == pollutant) & (default.Source == source)]
            if not match.empty:
                matrix[i, j] = match.iloc[0].MAP_factor

    fig, axes = plt.subplots(2, 2, figsize=(14, 10.2), constrained_layout=True)

    ax = axes[0, 0]
    im = ax.imshow(matrix, cmap="Blues_r", vmin=0.1, vmax=1.2, aspect="auto")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            if np.isfinite(matrix[i, j]):
                ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=8,
                        color="white" if matrix[i, j] < 0.45 else "black")
    ax.set_xticks(range(len(sources)), [SOURCE_MAP[s] for s in sources], rotation=48, ha="right")
    ax.set_yticks(range(4), [POLLUTANT_MAP[p] for p in pollutants])
    ax.set_title("Regularized discrepancy factors (default missing-data scenario)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03, label="MAP factor (prior-regularized)")
    panel_label(ax, "a")

    ax = axes[0, 1]
    default_summary = summary[summary.Scenario == "S2 month-specific (default)"].copy()
    x = np.arange(4)
    a = default_summary.Tier_A_count.to_numpy()
    b = default_summary.Tier_B_count.to_numpy()
    c = default_summary.Tier_C_count.to_numpy()
    ax.bar(x, a, color="#b2182b", label="A: strong prior conflict")
    ax.bar(x, b, bottom=a, color="#ef8a62", label="B: moderate prior conflict")
    ax.bar(x, c, bottom=a + b, color="#bdbdbd", label="C: no resolved conflict")
    ax.set_xticks(x, [POLLUTANT_MAP[p] for p in default_summary.Pollutant])
    ax.set_ylabel("Number of source–pollutant pairs")
    ax.set_title("Diagnostic tiers describe prior conflict, not identifiability")
    ax.legend(frameon=False, loc="upper left")
    panel_label(ax, "b")

    ax = axes[1, 0]
    scenarios = [
        "S1 observed-only",
        "S2 month-specific (default)",
        "S3 annual-mean",
        "S4 event-weighted upper",
    ]
    short = ["S1\nobserved", "S2\nmonthly", "S3\nannual mean", "S4\nevent upper"]
    colors = ["#2166ac", "#4393c3", "#d6604d", "#b2182b"]
    markers = ["o", "s", "^", "D"]
    for idx, (_, row) in enumerate(flags.iterrows()):
        values = [row[s + " factor"] for s in scenarios]
        label = f"{POLLUTANT_MAP[row.Pollutant]}—{SOURCE_MAP[row.Source]}"
        ax.plot(range(4), values, marker=markers[idx], ms=7, lw=1.8, color=colors[idx], label=label)
    ax.axhline(0.1, color="black", lw=0.9, ls="--", label="Truncation bound")
    ax.set_xticks(range(4), short)
    ax.set_ylim(0.06, 0.25)
    ax.set_ylabel("Regularized factor")
    ax.set_title("Persistent boundary conflicts across missing-data treatments")
    ax.legend(frameon=False, loc="upper center", ncol=2)
    panel_label(ax, "c")

    ax = axes[1, 1]
    labels = [POLLUTANT_MAP[p] for p in rank.Pollutant]
    params = rank.Active_source_factors + rank.Unknown_source_terms
    ax.bar(np.arange(4) - 0.18, params, width=0.36, color="#7b3294", label="Unknown parameters")
    ax.bar(np.arange(4) + 0.18, rank.Jacobian_rank, width=0.36, color="#008837", label="Jacobian rank")
    for i, nullity in enumerate(rank.Nullity):
        ax.text(i - 0.18, params.iloc[i] + 0.15, f"nullity={int(nullity)}", ha="center", fontsize=8.5)
    ax.set_xticks(range(4), labels)
    ax.set_ylabel("Dimension")
    ax.set_ylim(0, max(params) + 2)
    ax.set_title("One annual observation identifies one aggregate combination")
    ax.legend(frameon=False, loc="upper right")
    panel_label(ax, "d")

    fig.savefig(OUT / "figure2_identifiability_aware_bayesian.png", dpi=400, bbox_inches="tight")
    fig.savefig(OUT / "figure2_identifiability_aware_bayesian.pdf", bbox_inches="tight")
    plt.close(fig)


def generate_figure3():
    files = {
        "COD": "panel_a_mc_samples_COD.csv",
        "NH₃-N": "panel_b_mc_samples_NH3N.csv",
        "TN": "panel_c_mc_samples_TN.csv",
        "TP": "panel_d_mc_samples_TP.csv",
    }
    monitored = {"COD": 140.864, "NH₃-N": 4.785, "TN": 57.774, "TP": 0.758}
    base = ROOT / "output" / "figures" / "figure3_monte_carlo"
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), constrained_layout=True)
    for idx, (ax, (pollutant, filename)) in enumerate(zip(axes.flat, files.items())):
        values = pd.read_csv(base / filename).iloc[:, 0].to_numpy()
        lo, hi = np.percentile(values, [0.5, 99.5])
        ax.hist(values, bins=50, range=(lo, hi), density=True, color="#5b9bd5", alpha=0.75,
                edgecolor="white", linewidth=0.35)
        ax.axvline(monitored[pollutant], color="#c00000", lw=2.2, ls="--", label="Outlet load (S2)")
        ax.axvline(np.mean(values), color="#1f4e79", lw=2.0, label="MC mean")
        p5, p95 = np.percentile(values, [5, 95])
        ax.axvspan(p5, p95, color="#a6a6a6", alpha=0.22, label="5–95% interval")
        ax.set_title(pollutant)
        ax.set_xlabel("Nominal river-entry load (t yr⁻¹)")
        ax.set_ylabel("Probability density")
        ax.legend(frameon=False, loc="upper right")
        panel_label(ax, chr(ord("a") + idx))
    fig.suptitle("Forward uncertainty in nominal river-entry loads (before in-stream transport)", fontsize=14)
    fig.savefig(OUT / "figure3_forward_uncertainty.png", dpi=400, bbox_inches="tight")
    fig.savefig(OUT / "figure3_forward_uncertainty.pdf", bbox_inches="tight")
    plt.close(fig)


def generate_figure4():
    path = ROOT / "output" / "results" / "spatial_identifiability_unbounded.xlsx"
    profile = pd.read_excel(path, sheet_name="Profile")
    summary = pd.read_excel(path, sheet_name="Summary")
    pollutants = ["COD", "氨氮", "总氮", "总磷"]
    fig, axes = plt.subplots(2, 2, figsize=(14, 8.3), constrained_layout=True)
    for idx, (ax, pollutant) in enumerate(zip(axes.flat, pollutants)):
        data = profile[profile.Pollutant == pollutant].copy()
        ratio = data.relative_SSE_free / data.relative_SSE_free.min()
        ax.plot(data["k_km-1"], ratio, color="#2166ac", lw=2.2)
        ax.axvline(0, color="#b2182b", lw=1.5, ls="--", label="k = 0 flow-only null")
        paper_k = {"COD": 0.073, "氨氮": 0.184, "总氮": 0.180, "总磷": 0.300}[pollutant]
        ax.axvline(paper_k, color="#4d4d4d", lw=1.4, ls=":", label="Previously reported k")
        row = summary[summary.Pollutant == pollutant].iloc[0]
        ax.text(0.03, 0.94, f"ΔR² vs k=0 = {row.Delta_R2_free:.4f}", transform=ax.transAxes,
                va="top", bbox=dict(facecolor="white", edgecolor="#cccccc", alpha=0.9))
        ax.set_title(POLLUTANT_MAP[pollutant])
        ax.set_xlabel("Attenuation parameter k (km⁻¹)")
        ax.set_ylabel("Profile relative SSE / minimum")
        ymin, ymax = ratio.min(), ratio.max()
        pad = max((ymax - ymin) * 0.15, 0.00002)
        ax.set_ylim(ymin - pad, ymax + pad)
        ax.ticklabel_format(axis='y', style='plain', useOffset=False)
        ax.legend(frameon=False, loc="lower right")
        panel_label(ax, chr(ord("a") + idx))
    fig.suptitle("Profile audit after analytically removing the k–γ scaling ridge", fontsize=14)
    fig.savefig(OUT / "figure4_spatial_identifiability_profile.png", dpi=400, bbox_inches="tight")
    fig.savefig(OUT / "figure4_spatial_identifiability_profile.pdf", bbox_inches="tight")
    plt.close(fig)


def main():
    generate_figure2()
    generate_figure3()
    generate_figure4()
    print(OUT)


if __name__ == "__main__":
    main()
