"""Submittal register — the spec-section-organized submittal log: turnaround (received→returned),
ball-in-court (workflow state), and overdue flags (required-on-site passed, not yet closed). Pure."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

CLOSED_STATES = ("returned", "closed")


def _parse(s: Any) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)[:10]).date()
    except ValueError:
        return None


def register(submittals: list[dict], as_of: date | None = None) -> dict[str, Any]:
    today = as_of or date.today()
    rows, by_status, by_section = [], {}, {}
    turnarounds, overdue = [], 0
    for s in submittals:
        d = s.get("data") or s
        st = s.get("workflow_state") or "draft"
        by_status[st] = by_status.get(st, 0) + 1
        section = (d.get("spec_section") or "(unassigned)").strip()
        by_section[section] = by_section.get(section, 0) + 1
        rec, ret = _parse(d.get("date_received")), _parse(d.get("date_returned"))
        ros = _parse(d.get("required_on_site"))
        turn = (ret - rec).days if rec and ret else None
        if turn is not None:
            turnarounds.append(turn)
        is_overdue = bool(ros and ros < today and st not in CLOSED_STATES)
        if is_overdue:
            overdue += 1
        rows.append({
            "ref": s.get("ref"), "title": d.get("title"), "spec_section": section,
            "type": d.get("type"), "responsible": d.get("responsible_contractor"),
            "disposition": d.get("disposition"), "status": st,
            "required_on_site": d.get("required_on_site"), "turnaround_days": turn,
            "overdue": is_overdue, "ball_in_court": st,
        })
    avg_turn = round(sum(turnarounds) / len(turnarounds), 1) if turnarounds else None
    return {
        "submittal_count": len(rows),
        "open_count": sum(1 for r in rows if r["status"] not in CLOSED_STATES),
        "overdue_count": overdue,
        "avg_turnaround_days": avg_turn,
        "by_status": by_status,
        "by_section": dict(sorted(by_section.items())),
        "rows": sorted(rows, key=lambda r: (r.get("spec_section") or "", r.get("ref") or "")),
    }


def submittal_register(db, pid: str) -> dict[str, Any]:
    from . import modules as me
    subs = me.list_records(db, "submittal", pid, limit=100000) if "submittal" in me.TABLES else []
    return register(subs)
