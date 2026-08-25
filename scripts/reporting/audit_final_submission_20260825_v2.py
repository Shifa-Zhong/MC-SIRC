#!/usr/bin/env python3
"""Finalize the submission audit with exact XML-tag and reference-rematch checks."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import re
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "paper"
RESULT = ROOT / "output" / "results" / "final_submission_audit_20260825.json"
REPORT = ROOT / "output" / "results" / "final_submission_audit_20260825.md"
TRACK_TAG_RE = re.compile(rb"<w:(?:ins|del)(?:\s|>)")


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts" / "reporting" / "audit_final_submission_20260825.py")], check=False)
    data = json.loads(RESULT.read_text(encoding="utf-8"))
    for item in data["checks"]:
        if item["check"].startswith("no tracked insertions/deletions:"):
            name = item["check"].split(": ", 1)[1]
            with zipfile.ZipFile(PAPER / name) as archive:
                xml = archive.read("word/document.xml")
            matches = [match.group(0).decode("ascii") for match in TRACK_TAG_RE.finditer(xml)]
            item["status"] = "PASS" if not matches else "FAIL"
            item["detail"] = f"tracked_change_tags={matches}"
        elif item["check"] == "references matched independent of order for word-level diff":
            highlight = json.loads((ROOT / "output" / "results" / "word_level_highlight_report.json").read_text(encoding="utf-8"))
            manuscript = next(entry for entry in highlight if entry["scope"] == "MS")
            count = sum(bool(mapping.get("reference_rematch")) for mapping in manuscript["paragraph_mapping"])
            item["status"] = "PASS" if count >= 20 else "FAIL"
            item["detail"] = f"reference_rematches={count}"
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
