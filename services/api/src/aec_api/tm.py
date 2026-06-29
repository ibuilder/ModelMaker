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


def by_change_event(db, pid: str) -> dict[str, Any]:
    """Roll up eTicket T&M by the change event each ticket is linked to — ties field T&M to the
    change-management → cost chain. eTickets with no link land in an 'unassigned' bucket."""
    from . import modules as me
    ets = me.list_records(db, "eticket", pid, limit=100000) if "eticket" in me.TABLES else []
    ce = {r["id"]: r for r in (me.list_records(db, "change_event", pid, limit=100000)
                               if "change_event" in me.TABLES else [])}
    groups: dict[str, dict] = {}
    for e in ets:
        d = e.get("data") or e
        total = _num(d.get("labor_total")) + _num(d.get("material_total")) + _num(d.get("equipment_total"))
        cid = d.get("change_event")
        rec = ce.get(cid)
        gkey = cid if (cid and rec) else "__unassigned__"
        g = groups.setdefault(gkey, {
            "change_event_id": cid if rec else None,
            "ref": rec.get("ref") if rec else None,
            "subject": ((rec.get("data") or {}).get("subject") if rec else "Unassigned"),
            "ticket_count": 0, "total": 0.0})
        g["ticket_count"] += 1
        g["total"] = round(g["total"] + total, 2)
    rows = sorted(groups.values(), key=lambda r: (r["ref"] is None, r["ref"] or ""))
    return {"groups": rows, "linked_total": round(sum(g["total"] for g in rows if g["change_event_id"]), 2),
            "unassigned_total": round(sum(g["total"] for g in rows if not g["change_event_id"]), 2)}
