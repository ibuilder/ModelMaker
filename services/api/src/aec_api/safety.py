"""Safety analytics — OSHA incident rates (TRIR / DART / LTIFR / severity rate), the safety-observation
leading-indicator mix (safe vs at-risk, close-out), toolbox-talk coverage, and the safety-violation
log. Pure read-side aggregation over the incident / observation / toolbox_talk / safety_violation
modules; no writes. Hours-worked is taken as given, else estimated from daily-report manpower x 8h."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

OSHA_BASE = 200_000  # 100 full-time workers x 2,000 h/yr — the OSHA rate base
RECORDABLE_CLASS = ("Recordable", "Lost Time", "Fatality")
HOURS_PER_MANDAY = 8.0
INC_CLOSED = ("closed",)
OBS_CLOSED = ("closed",)
VIOL_CLOSED = ("closed",)


def _parse(s: Any) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)[:10]).date()
    except ValueError:
        return None


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _d(r: dict) -> dict:
    return r.get("data") or r


def _rate(count: float, hours: float) -> float | None:
    if not hours:
        return None
    return round(count * OSHA_BASE / hours, 2)


def incident_rates(incidents: list[dict], hours: float) -> dict[str, Any]:
    by_class, by_severity = {}, {}
    recordable = dart = lost_time = first_aid = near_miss = 0
    lost_days = restricted_days = 0.0
    by_state = {}
    rows = []
    for i in incidents:
        d = _d(i)
        st = i.get("workflow_state") or "open"
        by_state[st] = by_state.get(st, 0) + 1
        cls = (d.get("classification") or "(unclassified)").strip() or "(unclassified)"
        by_class[cls] = by_class.get(cls, 0) + 1
        sev = (d.get("severity") or "(unrated)").strip() or "(unrated)"
        by_severity[sev] = by_severity.get(sev, 0) + 1
        ld = _num(d.get("lost_days"))
        rd = _num(d.get("restricted_days"))
        lost_days += ld
        restricted_days += rd
        is_recordable = cls in RECORDABLE_CLASS or (d.get("osha_recordable") == "Yes")
        is_dart = is_recordable and (ld > 0 or rd > 0 or cls == "Lost Time")
        is_lost_time = cls == "Lost Time" or ld > 0
        if is_recordable:
            recordable += 1
        if is_dart:
            dart += 1
        if is_lost_time:
            lost_time += 1
        if cls == "First Aid":
            first_aid += 1
        if cls == "Near Miss":
            near_miss += 1
        rows.append({
            "ref": i.get("ref"), "subject": d.get("subject"), "date": d.get("date"),
            "classification": cls, "severity": sev, "recordable": is_recordable,
            "dart": is_dart, "lost_days": ld, "restricted_days": rd, "state": st,
        })
    return {
        "incident_count": len(rows),
        "recordable_count": recordable, "dart_count": dart, "lost_time_count": lost_time,
        "first_aid_count": first_aid, "near_miss_count": near_miss,
        "total_lost_days": round(lost_days, 1), "total_restricted_days": round(restricted_days, 1),
        "open_count": sum(v for k, v in by_state.items() if k not in INC_CLOSED),
        "hours_worked": round(hours, 0) if hours else 0,
        "trir": _rate(recordable, hours),
        "dart_rate": _rate(dart, hours),
        "ltifr": _rate(lost_time, hours),
        "severity_rate": _rate(lost_days + restricted_days, hours),
        "by_classification": by_class, "by_severity": by_severity, "by_state": by_state,
        "rows": sorted(rows, key=lambda r: (r.get("date") or ""), reverse=True),
    }


def observation_rollup(obs: list[dict]) -> dict[str, Any]:
    by_category, by_state = {}, {}
    safe = at_risk = closed = 0
    for o in obs:
        d = _d(o)
        st = o.get("workflow_state") or "open"
        by_state[st] = by_state.get(st, 0) + 1
        cat = (d.get("category") or d.get("type") or "(uncategorized)").strip() or "(uncategorized)"
        by_category[cat] = by_category.get(cat, 0) + 1
        typ = d.get("type")
        if typ == "Safe" or cat in ("Safe", "Positive"):
            safe += 1
        elif typ == "At-Risk" or cat in ("At-Risk", "Hazard"):
            at_risk += 1
        if st in OBS_CLOSED:
            closed += 1
    n = len(obs)
    return {
        "observation_count": n, "safe_count": safe, "at_risk_count": at_risk,
        "closed_count": closed, "open_count": n - closed,
        "closed_pct": round(100 * closed / n, 1) if n else None,
        # leading indicator: a healthy program logs many safe observations per at-risk one
        "safe_to_at_risk": round(safe / at_risk, 2) if at_risk else None,
        "by_category": dict(sorted(by_category.items())), "by_state": by_state,
    }


def toolbox_rollup(talks: list[dict]) -> dict[str, Any]:
    total_attendees = 0.0
    for t in talks:
        total_attendees += _num(_d(t).get("attendees"))
    n = len(talks)
    return {
        "talk_count": n, "total_attendees": int(total_attendees),
        "avg_attendees": round(total_attendees / n, 1) if n else None,
    }


def violation_rollup(viols: list[dict], as_of: date | None = None) -> dict[str, Any]:
    today = as_of or date.today()
    by_severity, by_state = {}, {}
    overdue = 0
    for v in viols:
        d = _d(v)
        st = v.get("workflow_state") or "open"
        by_state[st] = by_state.get(st, 0) + 1
        sev = (d.get("severity") or "(unrated)").strip() or "(unrated)"
        by_severity[sev] = by_severity.get(sev, 0) + 1
        due = _parse(d.get("due_date"))
        if due and due < today and st not in VIOL_CLOSED:
            overdue += 1
    n = len(viols)
    return {
        "violation_count": n,
        "open_count": sum(v for k, v in by_state.items() if k not in VIOL_CLOSED),
        "overdue_count": overdue, "by_severity": by_severity, "by_state": by_state,
    }


def estimate_hours(db, pid: str) -> float:
    """Fallback hours-worked estimate from daily-report manpower (man-days x 8h)."""
    from . import dailylog
    s = dailylog.field_log_summary(db, pid)
    return s.get("total_manpower", 0) * HOURS_PER_MANDAY


def safety_summary(db, pid: str, hours: float | None = None) -> dict[str, Any]:
    from . import modules as me
    inc = me.list_records(db, "incident", pid, limit=100000) if "incident" in me.TABLES else []
    obs = me.list_records(db, "observation", pid, limit=100000) if "observation" in me.TABLES else []
    tbt = me.list_records(db, "toolbox_talk", pid, limit=100000) if "toolbox_talk" in me.TABLES else []
    viol = me.list_records(db, "safety_violation", pid, limit=100000) if "safety_violation" in me.TABLES else []
    h = hours if hours is not None else estimate_hours(db, pid)
    return {
        "hours_estimated": hours is None,
        "incidents": incident_rates(inc, h),
        "observations": observation_rollup(obs),
        "toolbox_talks": toolbox_rollup(tbt),
        "violations": violation_rollup(viol),
    }
