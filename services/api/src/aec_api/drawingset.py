"""Drawing-set register — derives the controlled current set from the `drawing` module records:
for each sheet number the highest revision is *current*, earlier ones *superseded*. Produces a sheet
index, revision history and discipline rollup (Procore/ACC "Drawings" parity). Pure over the dicts."""
from __future__ import annotations

import re
from typing import Any


def _rev_key(rev: Any) -> tuple:
    """Sortable revision key. Numeric revs sort numerically; alpha revs (A<B<C) after; blank lowest.
    Handles 'P1'/'C2' style by (number, letters)."""
    s = str(rev or "").strip()
    if not s:
        return (0, 0, "")
    nums = re.findall(r"\d+", s)
    letters = re.sub(r"[^A-Za-z]", "", s).upper()
    n = int(nums[-1]) if nums else 0
    # alpha-only revs (A,B,C) rank by letter; numeric revs by number
    return (1 if (letters and not nums) else 2, n, letters)


def register(drawings: list[dict]) -> dict[str, Any]:
    """drawings: each `drawing` record's data + ref/workflow_state. Returns the controlled set."""
    by_sheet: dict[str, list[dict]] = {}
    for d in drawings:
        data = d.get("data") or d
        sheet = (data.get("sheet_number") or data.get("number") or d.get("ref") or "?").strip()
        by_sheet.setdefault(sheet, []).append({
            "ref": d.get("ref"), "sheet_number": sheet,
            "title": data.get("title"), "discipline": data.get("discipline"),
            "revision": data.get("revision"), "status": d.get("workflow_state"),
            "_k": _rev_key(data.get("revision")),
        })
    current_set, superseded, index = [], [], []
    by_discipline: dict[str, int] = {}
    for sheet, revs in sorted(by_sheet.items()):
        revs.sort(key=lambda r: r["_k"])
        cur = revs[-1]
        for r in revs[:-1]:
            r2 = {k: v for k, v in r.items() if k != "_k"}
            r2["superseded_by"] = cur["revision"]
            superseded.append(r2)
        cur_clean = {k: v for k, v in cur.items() if k != "_k"}
        current_set.append(cur_clean)
        disc = cur.get("discipline") or "Uncategorized"
        by_discipline[disc] = by_discipline.get(disc, 0) + 1
        index.append({"sheet_number": sheet, "title": cur.get("title"), "discipline": disc,
                      "current_revision": cur.get("revision"), "revisions": len(revs)})
    return {
        "sheet_count": len(by_sheet),
        "current_count": len(current_set),
        "superseded_count": len(superseded),
        "by_discipline": dict(sorted(by_discipline.items())),
        "sheet_index": index,
        "current_set": current_set,
        "superseded": superseded,
    }


def drawing_set(db, pid: str) -> dict[str, Any]:
    from . import modules as me
    drawings = me.list_records(db, "drawing", pid, limit=100000) if "drawing" in me.TABLES else []
    return register(drawings)
