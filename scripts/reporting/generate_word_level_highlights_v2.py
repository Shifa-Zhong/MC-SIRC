#!/usr/bin/env python3
"""Generate word-level highlights with order-independent, number-neutral reference matching."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reporting import generate_word_level_highlights as legacy


YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
LEADING_NUMBER_RE = re.compile(r"^\s*\[\d+\]\s*")


def reference_key(text: str):
    stripped = LEADING_NUMBER_RE.sub("", text.strip())
    if not stripped:
        return None
    year = YEAR_RE.search(stripped)
    if year is None:
        return None
    surname = re.split(r"[,\s]", stripped, maxsplit=1)[0].strip().lower()
    return surname, year.group(0)


def heading_index(document, title: str):
    for index, paragraph in enumerate(document.paragraphs):
        if paragraph.text.strip().lower() == title.lower():
            return index
    return None


def align_paragraphs(old_doc, new_doc):
    mapping, details = legacy._SEQUENTIAL_ALIGN(old_doc, new_doc)
    old_heading = heading_index(old_doc, "References")
    new_heading = heading_index(new_doc, "References")
    if old_heading is None or new_heading is None:
        return mapping, details
    old_candidates = {}
    for index in range(old_heading + 1, len(old_doc.paragraphs)):
        paragraph = old_doc.paragraphs[index]
        key = reference_key(paragraph.text)
        if key is not None:
            old_candidates.setdefault(key, []).append(index)
    rematched = set()
    for new_index in range(new_heading + 1, len(new_doc.paragraphs)):
        paragraph = new_doc.paragraphs[new_index]
        key = reference_key(paragraph.text)
        candidates = old_candidates.get(key, [])
        if not candidates:
            mapping.pop(new_index, None)
            continue
        best = max(candidates, key=lambda old_index: legacy.paragraph_similarity(old_doc.paragraphs[old_index], paragraph))
        similarity = legacy.paragraph_similarity(old_doc.paragraphs[best], paragraph)
        mapping[new_index] = best
        rematched.add(new_index)
        details.append({"new": new_index, "old": best, "similarity": similarity, "reference_rematch": True})
    details = [item for item in details if item.get("new") not in rematched or item.get("reference_rematch")]
    details.sort(key=lambda item: item["new"])
    return mapping, details


def main():
    legacy._SEQUENTIAL_ALIGN = legacy.align_paragraphs
    legacy.align_paragraphs = align_paragraphs
    legacy.main()


if __name__ == "__main__":
    main()
