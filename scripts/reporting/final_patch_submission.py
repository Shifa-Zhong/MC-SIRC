#!/usr/bin/env python3
"""Apply final terminology synchronization after the revision-5 document build."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

from docx import Document


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reporting import finalize_revision5_submission as finalizer


def replace_everywhere(document, old, new):
    paragraphs = list(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                paragraphs.extend(cell.paragraphs)
    count = 0
    for paragraph in paragraphs:
        if old not in paragraph.text:
            continue
        for run in paragraph.runs:
            if old in run.text:
                count += run.text.count(old)
                run.text = run.text.replace(old, new)
        if old in paragraph.text:
            text = paragraph.text.replace(old, new)
            paragraph.text = text
            count += 1
    return count


def patch_si():
    path = finalizer.PAPER / "SI_Final.docx"
    document = Document(path)
    replacements = {
        "S4 event upper": "S4 enhanced gap (+50%)",
        "S4 event-weighted upper": "S4 enhanced gap (+50%)",
    }
    for old, new in replacements.items():
        replace_everywhere(document, old, new)
    for table in document.tables:
        finalizer.submission.apply_three_line_table(table)
    document.save(path)
    shutil.copy2(path, finalizer.ARCHIVE / path.name)


def main():
    patch_si()
    finalizer.build_exact_response()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "reporting" / "generate_word_level_highlights_v2.py")], check=True)
    for name in [
        "SI_Final.docx", "Response_Letter.docx", "SI_Highlighted_20260824.docx",
        "Manuscript_Highlighted_20260824.docx", "Abstract_Highlighted_20260824.docx",
    ]:
        path = finalizer.PAPER / name
        if path.exists():
            finalizer.prune_docx_media(path)
    print("Final terminology synchronization complete")


if __name__ == "__main__":
    main()
