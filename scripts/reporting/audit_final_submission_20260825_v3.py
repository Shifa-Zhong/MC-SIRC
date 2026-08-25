#!/usr/bin/env python3
"""Run the final audit using the revision-5 figure command in the reproduction guide."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / "output" / "results" / "final_submission_audit_20260825.json"
REPORT = ROOT / "output" / "results" / "final_submission_audit_20260825.md"


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "reporting" / "audit_final_submission_20260825_v2.py")], check=False)
    data = json.loads(RESULT.read_text(encoding="utf-8"))
    guide = (ROOT / "REPRODUCIBILITY.md").read_text(encoding="utf-8")
    expected = ["revision3_diagnostics.py", "spatial_identifiability_unbounded.py", "revision5_mcmc_diagnostics.py", "generate_revision5_figures.py"]
    for item in data["checks"]:
        if item["check"] == "repository instructions cite existing scripts":
            item["status"] = "PASS" if all(name in guide and (ROOT / ("scripts/analysis/" + name if name.startswith(("revision", "spatial")) else "scripts/reporting/" + name)).exists() for name in expected) else "FAIL"
            item["detail"] = str(expected)
    counts = Counter(item["status"] for item in data["checks"])
    data["summary"] = dict(counts)
    RESULT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Final submission audit — 2026-08-25", "", f"Summary: {dict(counts)}", "", "| Status | Check | Detail |", "|---|---|---|"]
    for item in data["checks"]:
        detail = str(item["detail"]).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {item['status']} | {item['check']} | {detail} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(dict(counts))
    for item in data["checks"]:
        if item["status"] == "FAIL":
            print("FAIL", item["check"], item["detail"])
    print(REPORT)
    raise SystemExit(0 if counts["FAIL"] == 0 else 1)


if __name__ == "__main__":
    main()
