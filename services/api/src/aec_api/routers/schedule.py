"""Schedule visual + planning endpoints (GC portal): Gantt + Line-of-Balance SVG, CPM, and the
short-interval **lookahead** + **milestone** schedules the field and PM run from."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from .. import modules as me
from .. import schedule_cpm, schedule_viz
from ..db import get_db
from ..rbac import require_role

router = APIRouter()


def _svg(s: str) -> Response:
    return Response(s.encode("utf-8"), media_type="image/svg+xml")


def _d(v) -> date | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v)[:10]).date()
    except ValueError:
        return None


def _activity_status(start: date | None, finish: date | None, pct: float, today: date) -> str:
    """Field status of an activity from its dates + % complete."""
    if pct >= 100:
        return "complete"
    if finish and finish < today:
        return "late"                                # past its finish but not done
    if start and start <= today:
        return "in_progress"
    return "not_started"


@router.get("/projects/{pid}/schedule/cpm")
def cpm(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """Critical Path Method analysis of the schedule_activity records — early/late dates, total +
    free float, and the critical path (FS dependencies via each activity's `predecessors`)."""
    acts = me.list_records(db, "schedule_activity", pid, limit=1_000_000)
    return schedule_cpm.compute(acts)


@router.get("/projects/{pid}/schedule/gantt.svg")
def gantt(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    return _svg(schedule_viz.gantt_svg(db, pid))


@router.get("/projects/{pid}/schedule/lob.svg")
def lob(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    return _svg(schedule_viz.lob_svg(db, pid))


@router.get("/projects/{pid}/schedule/lookahead")
def lookahead(pid: str, weeks: int = 3, start: str | None = None, db: Session = Depends(get_db),
              _: str = Depends(require_role("viewer"))):
    """Short-interval **lookahead** (the field's 3- / 6-week plan): activities active in the window
    [`start`, `start`+`weeks`), grouped by ISO week. An activity is in-window if it overlaps it
    (starts before the end and finishes on/after the start). Each carries trade, %-complete, and a
    field status (not_started / in_progress / late / complete). Defaults to a 3-week window today."""
    weeks = max(1, min(12, weeks))
    d0 = _d(start) or date.today()
    d1 = d0 + timedelta(weeks=weeks)
    rows = me.list_records(db, "schedule_activity", pid, limit=1_000_000)
    buckets: dict[str, list] = {}
    for r in rows:
        data = r.get("data") or {}
        s, f = _d(data.get("start")) or _d(data.get("actual_start")), _d(data.get("finish")) or _d(data.get("actual_finish"))
        if not (s or f):
            continue
        s = s or f; f = f or s
        if s >= d1 or f < d0:                         # no overlap with the window
            continue
        pct = float(data.get("percent") or 0)
        wk = (max(s, d0) - d0).days // 7             # 0-based week index within the window
        label = f"Week {wk + 1} ({(d0 + timedelta(weeks=wk)).isoformat()})"
        buckets.setdefault(label, []).append({
            "ref": r.get("ref"), "name": r.get("title") or data.get("name"),
            "trade": data.get("trade"), "start": data.get("start"), "finish": data.get("finish"),
            "percent": pct, "status": _activity_status(s, f, pct, date.today())})
    for v in buckets.values():
        v.sort(key=lambda a: (a["start"] or "", a["name"] or ""))
    total = sum(len(v) for v in buckets.values())
    return {"start": d0.isoformat(), "finish": d1.isoformat(), "weeks": weeks,
            "count": total, "weeks_detail": [{"week": k, "activities": buckets[k]} for k in sorted(buckets)]}


@router.get("/projects/{pid}/schedule/earned-value")
def earned_value(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """Schedule **earned value** over the activities that carry a budgeted cost. For each:
    BAC = Σ budget; **EV (BCWP)** = Σ %·budget (work earned); **PV (BCWS)** = Σ planned-fraction·budget
    (where today sits in [start, finish]). **SPI** = EV/PV and the schedule variance **SV** = EV−PV
    tell you, in dollars, whether the job is ahead of or behind plan. AC/CPI need cost actuals and are
    left to the cost engine."""
    today = date.today()
    rows = me.list_records(db, "schedule_activity", pid, limit=1_000_000)
    bac = ev = pv = 0.0
    lines = []
    for r in rows:
        data = r.get("data") or {}
        budget = float(data.get("budget") or 0)
        if budget <= 0:
            continue
        pct = max(0.0, min(100.0, float(data.get("percent") or 0))) / 100.0
        s, f = _d(data.get("start")) or _d(data.get("actual_start")), _d(data.get("finish")) or _d(data.get("actual_finish"))
        if s and f and f > s:
            planned = max(0.0, min(1.0, (today - s).days / (f - s).days))
        elif f:
            planned = 1.0 if today >= f else 0.0
        else:
            planned = 0.0
        a_ev, a_pv = pct * budget, planned * budget
        bac += budget; ev += a_ev; pv += a_pv
        lines.append({"ref": r.get("ref"), "name": r.get("title") or data.get("name"),
                      "budget": round(budget, 2), "percent": round(pct * 100, 1),
                      "ev": round(a_ev, 2), "pv": round(a_pv, 2), "sv": round(a_ev - a_pv, 2)})
    spi = round(ev / pv, 3) if pv else None
    status = "no_data" if not lines else (
        "ahead" if spi and spi > 1.05 else "behind" if spi and spi < 0.95 else "on_track")
    lines.sort(key=lambda x: x["sv"])               # worst schedule variance first
    return {"bac": round(bac, 2), "ev": round(ev, 2), "pv": round(pv, 2),
            "sv": round(ev - pv, 2), "spi": spi, "percent_complete": round(ev / bac * 100, 1) if bac else 0.0,
            "status": status, "activity_count": len(lines), "activities": lines}


@router.get("/projects/{pid}/schedule/milestones")
def milestones(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """**Milestone schedule**: the key dates — activities typed `Milestone` (or zero-duration),
    sorted by date, each with a status (met / due_soon / upcoming / late). `met` = 100% complete;
    `late` = past its date and not complete; `due_soon` = within 14 days."""
    today = date.today()
    rows = me.list_records(db, "schedule_activity", pid, limit=1_000_000)
    out = []
    for r in rows:
        data = r.get("data") or {}
        s, f = _d(data.get("start")), _d(data.get("finish"))
        is_ms = (data.get("activity_type") == "Milestone") or (s and f and s == f)
        if not is_ms:
            continue
        when = f or s
        pct = float(data.get("percent") or 0)
        if pct >= 100:
            status = "met"
        elif when and when < today:
            status = "late"
        elif when and when <= today + timedelta(days=14):
            status = "due_soon"
        else:
            status = "upcoming"
        out.append({"ref": r.get("ref"), "name": r.get("title") or data.get("name"),
                    "date": (when.isoformat() if when else None),
                    "days_out": ((when - today).days if when else None),
                    "percent": pct, "status": status})
    out.sort(key=lambda m: (m["date"] or "9999"))
    summary = {k: sum(1 for m in out if m["status"] == k) for k in ("met", "late", "due_soon", "upcoming")}
    return {"count": len(out), "summary": summary, "milestones": out}
