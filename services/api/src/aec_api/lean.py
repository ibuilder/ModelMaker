"""Lean / Last-Planner analytics (R4) — Plan Percent Complete (PPC) and reasons for non-completion,
the core metrics of the Last Planner System (VT lean-construction research). Pure over weekly-plan
records (status ∈ Planned|Complete|Missed, with a variance_reason on misses)."""
from __future__ import annotations

from collections import Counter
from typing import Any


def ppc(records: list[dict]) -> dict[str, Any]:
    """Plan Percent Complete = completed commitments ÷ total commitments, plus the ranked reasons
    for non-completion (the lever lean teams act on week over week)."""
    rows = [(r.get("data") or r) for r in records]
    total = len(rows)
    complete = sum(1 for r in rows if (r.get("status") or "").lower() == "complete")
    missed = [r for r in rows if (r.get("status") or "").lower() == "missed"]
    reasons = Counter((r.get("variance_reason") or "Unspecified") for r in missed)
    return {
        "commitments": total,
        "completed": complete,
        "ppc": round(complete / total, 3) if total else 0.0,
        "missed": len(missed),
        "top_variance_reasons": [{"reason": k, "count": v} for k, v in reasons.most_common(5)],
        # lean benchmark: high-performing teams sustain ~80%+ PPC
        "rating": ("good" if total and complete / total >= 0.8 else
                   "fair" if total and complete / total >= 0.6 else "needs work"),
    }
