"""Preconstruction analytics — estimate continuity across design milestones
(Concept -> SD -> DD -> CD -> IFC -> GMP -> Award): per-milestone total + $/SF, the milestone-to-
milestone cost **drift**, and the gap between the latest estimate and the project budget/GMP. Pure
read-side aggregation over the `estimate_set` module; no writes. Mirrors the other analytics engines.

This is the "are we still tracking to budget as the design evolves?" view — the preconstruction
discipline Concntric centers on, built on Massing's existing estimate/budget primitives."""
from __future__ import annotations

from typing import Any

MILESTONE_ORDER = ["Concept", "SD", "DD", "CD", "IFC", "GMP", "Award"]
_RANK = {m: i for i, m in enumerate(MILESTONE_ORDER)}


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _d(r: dict) -> dict:
    return r.get("data") or r


def _budget_baseline(db, pid: str) -> float | None:
    """The project's GMP budget total (the line we measure the latest estimate against)."""
    try:
        from . import project_budget
        b = project_budget.gmp_budget(db, pid)["totals"]["budget"]
        return round(b, 2) if b else None
    except Exception:                                 # noqa: BLE001 — best-effort baseline
        return None


def estimate_continuity(db, pid: str, budget: float | None = None) -> dict[str, Any]:
    from . import modules as me
    sets = me.list_records(db, "estimate_set", pid, limit=100000) if "estimate_set" in me.TABLES else []
    rows = []
    for s in sets:
        d = _d(s)
        total = round(_num(d.get("total")), 2)
        gsf = _num(d.get("gsf"))
        ms = (d.get("milestone") or "").strip()
        rows.append({
            "ref": s.get("ref"), "title": d.get("title"), "milestone": ms,
            "rank": _RANK.get(ms, 99), "total": total, "gsf": gsf,
            "psf": round(total / gsf, 2) if gsf else None,
            "basis": d.get("basis"), "estimate_date": d.get("estimate_date"),
            "state": s.get("workflow_state"),
        })
    # order along the design timeline (milestone rank, then date)
    rows.sort(key=lambda r: (r["rank"], r.get("estimate_date") or ""))
    # milestone-to-milestone drift
    prev = None
    for r in rows:
        if prev is not None:
            r["delta_total"] = round(r["total"] - prev["total"], 2)
            r["delta_pct"] = round(100 * (r["total"] - prev["total"]) / prev["total"], 1) if prev["total"] else None
        else:
            r["delta_total"] = None
            r["delta_pct"] = None
        prev = r

    first = rows[0] if rows else None
    latest = rows[-1] if rows else None
    if budget is None:
        budget = _budget_baseline(db, pid)
    variance = round(latest["total"] - budget, 2) if (latest and budget) else None
    drift = round(latest["total"] - first["total"], 2) if (latest and first) else 0.0
    drift_pct = (round(100 * drift / first["total"], 1) if (first and first["total"]) else None)
    return {
        "set_count": len(rows),
        "milestones": [r["milestone"] for r in rows],
        "first_milestone": first["milestone"] if first else None,
        "first_total": first["total"] if first else 0.0,
        "latest_milestone": latest["milestone"] if latest else None,
        "latest_total": latest["total"] if latest else 0.0,
        "latest_psf": latest["psf"] if latest else None,
        "total_drift": drift,
        "total_drift_pct": drift_pct,
        "budget": round(budget, 2) if budget else None,
        "variance_to_budget": variance,        # positive = latest estimate is OVER budget
        "over_budget": (variance is not None and variance > 0),
        "rows": rows,
    }
