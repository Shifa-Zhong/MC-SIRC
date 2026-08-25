#!/usr/bin/env python3
"""Generate the final identifiability-aware MC-SIRC overview figure."""

from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "figures" / "revision3"
OUT.mkdir(parents=True, exist_ok=True)


def box(ax, y, text, color, height=0.115):
    patch = FancyBboxPatch((0.12, y), 0.76, height, boxstyle="round,pad=0.012,rounding_size=0.015",
                           facecolor=color, edgecolor="#444444", linewidth=1.0)
    ax.add_patch(patch)
    ax.text(0.50, y + height / 2, text, ha="center", va="center", fontsize=10.3, fontweight="bold")


def main():
    map_path = ROOT / "output" / "figures" / "figure1a_watershed_standalone" / "figure1a_watershed.png"
    map_image = Image.open(map_path)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.2), gridspec_kw={"width_ratios": [1.55, 1]})
    axes[0].imshow(map_image)
    axes[0].axis("off")
    axes[0].set_title("(a) Nanchuan River Basin: inventory sources and outlet station", loc="left", fontsize=12, fontweight="bold")
    ax = axes[1]
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("(b) Identifiability-aware MC-SIRC workflow", loc="left", fontsize=12, fontweight="bold")
    entries = [
        (0.82, "Inventory + outlet monitoring\n1,588 unique 1-km grid IDs; 100 georeferenced sources; 5,928 observed hours", "#fdd49e"),
        (0.64, "Missing-data scenarios\nmonthly default + lower and enhanced-gap sensitivities", "#c7e9c0"),
        (0.46, "Prior-regularized aggregate reconciliation\nMAP/MCMC allocations within one evidence system", "#c6dbef"),
        (0.28, "Formal identifiability audit\nJacobian rank, null-space solutions, k = 0 profile", "#dadaeb"),
        (0.10, "Supported outputs\naggregate discrepancy, prior-conflict flags, monitoring priorities", "#fcbba1"),
    ]
    for y, text, color in entries:
        box(ax, y, text, color)
    for y1, y2 in zip([0.82, 0.64, 0.46, 0.28], [0.755, 0.575, 0.395, 0.215]):
        ax.add_patch(FancyArrowPatch((0.5, y1), (0.5, y2), arrowstyle="-|>", mutation_scale=13,
                                     linewidth=1.2, color="#444444"))
    ax.text(0.5, 0.035, "Unresolved at the current monitoring resolution: source-specific attenuation,\n"
                        "half-lives, effective outlet shares, and policy re-ranking",
            ha="center", va="center", fontsize=9.5, color="#8b0000")
    fig.tight_layout()
    fig.savefig(OUT / "figure1_revised_framework.png", dpi=400, bbox_inches="tight")
    fig.savefig(OUT / "figure1_revised_framework.pdf", bbox_inches="tight")
    plt.close(fig)
    print(OUT / "figure1_revised_framework.png")


if __name__ == "__main__":
    main()
