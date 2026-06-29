"""Time & Material (eTicket) cost rollup — aggregates `eticket` records (labor/material/equipment)
into a T&M cost summary by status, with billed vs unbilled. Pure over the record dicts."""
from __future__ import annotations

from typing import Any

BILLED = "billed"


def _num(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def summarize(etickets: list[dict]) -> dict[str, Any]:
    rows, by_status = [], {}
    labor = material = equipment = billed_total = 0.0
    for e in etickets:
        d = e.get("data") or e
        lt, mt, et = _num(d.get("labor_total")), _num(d.get("material_total")), _num(d.get("equipment_total"))
        total = lt + mt + et
        labor += lt; material += mt; equipment += et
        st = e.get("workflow_state") or "draft"
        by_status[st] = by_status.get(st, 0.0) + total
        if st == BILLED:
            billed_total += total
        rows.append({"ref": e.get("ref"), "subject": d.get("subject"), "work_date": d.get("work_date"),
                     "labor": round(lt, 2), "material": round(mt, 2), "equipment": round(et, 2),
                     "total": round(total, 2), "status": st})
    grand = labor + material + equipment
    return {
        "ticket_count": len(rows),
        "labor_total": round(labor, 2), "material_total": round(material, 2),
        "equipment_total": round(equipment, 2), "grand_total": round(grand, 2),
        "billed_total": round(billed_total, 2), "unbilled_total": round(grand - billed_total, 2),
        "by_status": {k: round(v, 2) for k, v in by_status.items()},
        "rows": sorted(rows, key=lambda r: (r.get("work_date") or "")),
    }


def tm_summary(db, pid: str) -> dict[str, Any]:
    from . import modules as me
    ets = me.list_records(db, "eticket", pid, limit=100000) if "eticket" in me.TABLES else []
    return summarize(ets)
