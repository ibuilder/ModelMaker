"""External-system sync — the other half of interoperability: pull records from a connected
source into the GC-portal module model. Procore RFIs / submittals / change events → the matching
modules, idempotent by the Procore record id stored in each imported record's data."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import connectors
from . import modules as me

# kind -> (module key, connectors fetch attr, connectors mapper attr)
KINDS: dict[str, tuple[str, str, str]] = {
    "rfi": ("rfi", "procore_rfis", "map_procore_rfi"),
    "submittal": ("submittal", "procore_submittals", "map_procore_submittal"),
    "change_event": ("change_event", "procore_change_events", "map_procore_change_event"),
}


def _sync_kind(db: Session, project_id: str, kind: str, token: str, procore_project_id: str,
               actor: str, party: str | None) -> dict[str, Any]:
    module_key, fetch_attr, map_attr = KINDS[kind]
    items = getattr(connectors, fetch_attr)(token, procore_project_id)
    mapper = getattr(connectors, map_attr)
    existing = me.list_records(db, module_key, project_id, limit=1_000_000)
    have = {(r.get("data") or {}).get("procore_id") for r in existing}
    imported = 0
    for it in items:
        m = mapper(it)
        if not m["procore_id"] or m["procore_id"] in have:
            continue
        me.create_record(db, module_key, project_id,
                         {"data": {**m["data"], "procore_id": m["procore_id"]}}, actor, party)
        have.add(m["procore_id"])
        imported += 1
    return {"module": module_key, "fetched": len(items), "imported": imported,
            "skipped": len(items) - imported}


def sync_procore(db: Session, project_id: str, token: str, procore_project_id: str,
                 kinds: list[str], actor: str, party: str | None) -> dict[str, Any]:
    """Import the requested Procore record kinds into their modules (idempotent). Re-running only
    imports records not already present (matched by procore_id)."""
    results = {k: _sync_kind(db, project_id, k, token, procore_project_id, actor, party)
               for k in kinds if k in KINDS}
    return {"source": "procore", "results": results,
            "imported_total": sum(r["imported"] for r in results.values())}


# --- scheduled / auto-sync -----------------------------------------------------
def _aware(dt):
    from datetime import timezone
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def run_schedule(db: Session, sched, actor: str = "procore-sync") -> dict[str, Any]:
    """Run one schedule now (used by run-now + the background loop)."""
    from .models import Connection
    c = db.get(Connection, sched.connection_id)
    if not c or c.type != "procore" or not (c.config or {}).get("access_token"):
        return {"error": "connection missing or not a configured Procore connection"}
    kinds = sched.kinds or list(KINDS)
    return sync_procore(db, sched.project_id, c.config["access_token"],
                        str(sched.procore_project_id), kinds, actor, None)


def run_due(db: Session, now=None) -> list[dict[str, Any]]:
    """Run every enabled schedule whose interval has elapsed; record last_run/last_result."""
    from datetime import datetime, timedelta, timezone

    from .models import SyncSchedule
    now = now or datetime.now(timezone.utc)
    ran = []
    for s in db.query(SyncSchedule).filter(SyncSchedule.enabled.isnot(False)).all():
        if s.last_run is not None and (now - _aware(s.last_run)) < timedelta(minutes=s.interval_minutes or 60):
            continue
        try:
            res = run_schedule(db, s)
        except Exception as e:                   # noqa: BLE001 — one bad schedule mustn't stop the rest
            res = {"error": str(e)[:160]}
        s.last_run = now
        s.last_result = res
        db.commit()
        ran.append({"schedule_id": s.id, "result": res})
    return ran
