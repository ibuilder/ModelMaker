"""External-system sync — the other half of interoperability: pull records from a connected
source into the GC-portal module model. v1: Procore RFIs → the `rfi` module (idempotent by the
Procore record id stored in the imported record's data)."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import connectors
from . import modules as me


def sync_procore_rfis(db: Session, project_id: str, token: str, procore_project_id: str,
                      actor: str, party: str | None) -> dict[str, Any]:
    """Import Procore RFIs into the project's `rfi` module. Already-imported RFIs (matched by
    procore_id) are skipped, so re-running is safe."""
    rfis = connectors.procore_rfis(token, procore_project_id)
    existing = me.list_records(db, "rfi", project_id, limit=1_000_000)
    have = {(r.get("data") or {}).get("procore_id") for r in existing}
    imported = 0
    for r in rfis:
        m = connectors.map_procore_rfi(r)
        if m["procore_id"] in have:
            continue
        data = {**m["data"], "procore_id": m["procore_id"]}
        me.create_record(db, "rfi", project_id, {"data": data}, actor, party)
        imported += 1
    return {"source": "procore", "module": "rfi", "fetched": len(rfis),
            "imported": imported, "skipped": len(rfis) - imported}
