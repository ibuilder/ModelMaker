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


DECISION_OPEN = ("open",)
ASSUMPTION_OPEN = ("open",)


def decision_log(db, pid: str) -> dict[str, Any]:
    """Preconstruction decision log — by status, stakeholder alignment, and open cost/schedule exposure."""
    from . import modules as me
    recs = me.list_records(db, "decision", pid, limit=100000) if "decision" in me.TABLES else []
    by_status, by_alignment, by_category = {}, {}, {}
    open_count = 0
    cost_exposure = sched_exposure = 0.0
    rows = []
    for r in recs:
        d = _d(r)
        st = r.get("workflow_state") or "open"
        by_status[st] = by_status.get(st, 0) + 1
        align = (d.get("alignment") or "Pending").strip() or "Pending"
        by_alignment[align] = by_alignment.get(align, 0) + 1
        cat = (d.get("category") or "(uncategorized)").strip() or "(uncategorized)"
        by_category[cat] = by_category.get(cat, 0) + 1
        is_open = st in DECISION_OPEN
        if is_open:
            open_count += 1
            cost_exposure += _num(d.get("cost_impact"))
            sched_exposure += _num(d.get("schedule_impact_days"))
        rows.append({
            "ref": r.get("ref"), "subject": d.get("subject"), "category": cat, "state": st,
            "alignment": align, "cost_impact": _num(d.get("cost_impact")),
            "schedule_impact_days": _num(d.get("schedule_impact_days")),
            "decided_by": d.get("decided_by"), "due_date": d.get("due_date"),
        })
    return {
        "decision_count": len(rows), "open_count": open_count,
        "decided_count": by_status.get("decided", 0),
        "disputed_count": by_alignment.get("Disputed", 0),
        "open_cost_exposure": round(cost_exposure, 2),
        "open_schedule_exposure_days": round(sched_exposure, 1),
        "by_status": by_status, "by_alignment": by_alignment, "by_category": dict(sorted(by_category.items())),
        "rows": sorted(rows, key=lambda r: (r["state"] != "open", r.get("due_date") or "")),
    }


def assumptions(db, pid: str) -> dict[str, Any]:
    """Assumptions & clarifications register — by status/category + open cost exposure (allowances)."""
    from . import modules as me
    recs = me.list_records(db, "assumption", pid, limit=100000) if "assumption" in me.TABLES else []
    by_status, by_category = {}, {}
    open_cost = 0.0
    rows = []
    for r in recs:
        d = _d(r)
        st = r.get("workflow_state") or "open"
        by_status[st] = by_status.get(st, 0) + 1
        cat = (d.get("category") or "(uncategorized)").strip() or "(uncategorized)"
        by_category[cat] = by_category.get(cat, 0) + 1
        ci = _num(d.get("cost_impact"))
        if st in ASSUMPTION_OPEN:
            open_cost += ci
        rows.append({"ref": r.get("ref"), "subject": d.get("subject"), "category": cat,
                     "state": st, "cost_impact": ci, "owner": d.get("owner")})
    return {
        "assumption_count": len(rows),
        "open_count": sum(v for k, v in by_status.items() if k in ASSUMPTION_OPEN),
        "confirmed_count": by_status.get("confirmed", 0), "voided_count": by_status.get("voided", 0),
        "open_cost_exposure": round(open_cost, 2),
        "by_status": by_status, "by_category": dict(sorted(by_category.items())),
        "rows": sorted(rows, key=lambda r: (r["state"] != "open", -r["cost_impact"])),
    }


def ve_log(db, pid: str, target: float | None = None) -> dict[str, Any]:
    """Value-engineering cycle — proposed vs accepted vs rejected savings, by status, and (if a target
    gap is given) how much of it the accepted ideas close."""
    from . import modules as me
    recs = me.list_records(db, "value_engineering", pid, limit=100000) if "value_engineering" in me.TABLES else []
    by_status = {}
    proposed = accepted = rejected = 0.0
    rows = []
    for r in recs:
        d = _d(r)
        st = (r.get("workflow_state") or d.get("status") or "proposed").strip().lower()
        by_status[st] = by_status.get(st, 0) + 1
        sv = _num(d.get("savings"))
        if st == "accepted":
            accepted += sv
        elif st == "rejected":
            rejected += sv
        else:
            proposed += sv
        rows.append({"ref": r.get("ref"), "subject": d.get("subject"), "status": st,
                     "savings": round(sv, 2)})
    out = {
        "ve_count": len(rows), "by_status": by_status,
        "proposed_savings": round(proposed, 2), "accepted_savings": round(accepted, 2),
        "rejected_savings": round(rejected, 2),
        "pipeline_savings": round(proposed + accepted, 2),     # still-available + already-accepted
        "rows": sorted(rows, key=lambda r: -r["savings"]),
    }
    if target is not None:
        gap = _num(target)
        out["target"] = round(gap, 2)
        out["gap_after_accepted"] = round(gap - accepted, 2)   # remaining gap once accepted VE is applied
        out["target_met"] = accepted >= gap
    return out


_RAG = {"green": 100, "amber": 60, "red": 20}


def alignment(db, pid: str) -> dict[str, Any]:
    """Calibrate-style preconstruction alignment: is the latest estimate tracking to budget, are
    decisions/assumptions resolved, and can open VE close any over-budget gap? RAG + score."""
    cont = estimate_continuity(db, pid)
    dec = decision_log(db, pid)
    asm = assumptions(db, pid)
    over = cont["variance_to_budget"] if cont["variance_to_budget"] is not None else 0.0
    ve = ve_log(db, pid, target=over if over > 0 else None)
    domains = []

    def add(key, label, status, headline):
        domains.append({"key": key, "label": label, "status": status, "headline": headline})

    # budget tracking
    if cont["budget"] and cont["variance_to_budget"] is not None:
        v = cont["variance_to_budget"]
        b_status = "green" if v <= 0 else ("amber" if v <= 0.05 * cont["budget"] else "red")
        add("budget", "Estimate vs budget",
            "green" if v <= 0 else b_status,
            f"latest {cont['latest_milestone'] or '—'} {('over' if v > 0 else 'under')} by "
            f"{_fmt_money(abs(v))} vs {_fmt_money(cont['budget'])}")
    else:
        add("budget", "Estimate vs budget", "amber" if cont["set_count"] == 0 else "green",
            f"{cont['set_count']} estimate set(s); no budget baseline" if not cont["budget"] else "tracking")
    # VE coverage of any over-budget gap
    if over > 0:
        add("ve", "VE vs gap",
            "green" if ve.get("target_met") else ("amber" if ve["accepted_savings"] > 0 else "red"),
            f"{_fmt_money(ve['accepted_savings'])} accepted / {_fmt_money(ve['pipeline_savings'])} pipeline "
            f"vs {_fmt_money(over)} gap")
    else:
        add("ve", "Value engineering", "green",
            f"{_fmt_money(ve['accepted_savings'])} accepted, {_fmt_money(ve['proposed_savings'])} proposed")
    # decisions
    add("decisions", "Decisions",
        "red" if dec["disputed_count"] else ("amber" if dec["open_count"] else "green"),
        f"{dec['open_count']} open ({dec['disputed_count']} disputed), "
        f"{_fmt_money(dec['open_cost_exposure'])} cost exposure")
    # assumptions
    add("assumptions", "Assumptions",
        "amber" if asm["open_count"] else "green",
        f"{asm['open_count']} open, {_fmt_money(asm['open_cost_exposure'])} allowance exposure")

    scored = [_RAG[d["status"]] for d in domains]
    score = round(sum(scored) / len(scored)) if scored else None
    overall = "red" if any(d["status"] == "red" for d in domains) else (
        "amber" if any(d["status"] == "amber" for d in domains) else "green")
    return {
        "alignment_score": score, "overall_status": overall,
        "latest_milestone": cont["latest_milestone"], "latest_total": cont["latest_total"],
        "budget": cont["budget"], "variance_to_budget": cont["variance_to_budget"],
        "ve_accepted": ve["accepted_savings"], "ve_pipeline": ve["pipeline_savings"],
        "open_decisions": dec["open_count"], "open_assumptions": asm["open_count"],
        "domains": domains,
    }


def _fmt_money(v: Any) -> str:
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v)
