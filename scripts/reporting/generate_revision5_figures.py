#!/usr/bin/env python3
"""Generate all final scientific figures and the code-generated graphical abstract."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reporting.finalize_revision5_submission import generate_all_figures


if __name__ == "__main__":
    generate_all_figures()
    print(ROOT / "output" / "figures")
