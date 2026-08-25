#!/usr/bin/env python3
"""Generate the final identifiability-aware MC-SIRC overview figure."""

from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output" / "figures" / "revision3"
OUT.mkdir(parents=True, exist_ok=True)


def box(ax, y, text, color, height=0.13, fontsize=17.5, edgecolor="#444444"):
    patch = FancyBboxPatch((0.04, y), 0.92, height, boxstyle="round,pad=0.010,rounding_size=0.015",
                           facecolor=color, edgecolor=edgecolor, linewidth=1.35)
    ax.add_patch(patch)
    label = ax.text(
        0.50, y + height / 2, text,
        ha="center", va="center", fontsize=fontsize, fontweight="bold", linespacing=1.08,
    )
    return patch, label


def main():
    map_path = ROOT / "output" / "figures" / "figure1a_watershed_standalone" / "figure1a_watershed.png"
    map_image = Image.open(map_path)
    fig, axes = plt.subplots(1, 2, figsize=(18, 8.5), gridspec_kw={"width_ratios": [1.30, 1.20]})
    axes[0].imshow(map_image)
    axes[0].axis("off")
    axes[0].set_title("(a) Nanchuan River Basin: inventory sources and outlet station", loc="left", fontsize=18, fontweight="bold")
    ax = axes[1]
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("(b) Identifiability-aware MC-SIRC workflow", loc="left", fontsize=18, fontweight="bold")
    entries = [
        (0.815, "Inventory and outlet monitoring\n1,588 unique 1-km grid IDs\n100 sources | 5,928 observed hours", "#fdd49e"),
        (0.650, "Missing-data scenarios\nMonthly default and lower-bound\nEnhanced-gap sensitivity", "#c7e9c0"),
        (0.485, "Prior-regularized reconciliation\nMAP/MCMC source allocations\nwithin a common evidence system", "#c6dbef"),
        (0.320, "Formal identifiability audit\nJacobian rank | null-space solutions\nk = 0 profile", "#dadaeb"),
        (0.155, "Supported outputs\nAggregate discrepancy | prior-conflict flags\nMonitoring priorities", "#fcbba1"),
    ]
    framed_text = []
    for y, text, color in entries:
        framed_text.append(box(ax, y, text, color))
    for current, following in zip(entries[:-1], entries[1:]):
        ax.add_patch(FancyArrowPatch(
            (0.5, current[0]), (0.5, following[0] + 0.13), arrowstyle="-|>", mutation_scale=18,
            linewidth=1.5, color="#444444",
        ))
    framed_text.append(box(
        ax, 0.010,
        "Not resolved at current monitoring resolution\n"
        "Source-specific attenuation and half-lives\n"
        "Effective outlet shares and policy re-ranking",
        "#fff5f0", height=0.11, fontsize=15.0, edgecolor="#8b0000",
    ))
    fig.tight_layout(pad=0.8)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for patch, label in framed_text:
        frame = patch.get_window_extent(renderer)
        text_extent = label.get_window_extent(renderer)
        if not (
            text_extent.x0 >= frame.x0 + 4
            and text_extent.x1 <= frame.x1 - 4
            and text_extent.y0 >= frame.y0 + 3
            and text_extent.y1 <= frame.y1 - 3
        ):
            raise RuntimeError(f"Panel 1b text exceeds its frame: {label.get_text()!r}")
    fig.savefig(OUT / "figure1_revised_framework.png", dpi=400, bbox_inches="tight")
    fig.savefig(OUT / "figure1_revised_framework.pdf", bbox_inches="tight")
    plt.close(fig)
    print(OUT / "figure1_revised_framework.png")


if __name__ == "__main__":
    main()
