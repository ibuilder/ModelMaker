"""GC portal module engine.

Every business process (RFIs, Submittals, PCO Requests, Change Orders, …) is a *module*
described by a single `module.json` and stored in its **own table** (`mod_<key>`), created
automatically. One shared engine renders CRUD and drives a **role-gated workflow state
machine**. Records can be anchored to the model (pins) and linked into chains (the
change-order process). Every transition is written to the record activity timeline.

Implements the patent-described system (provisional 514712205), modernised on FastAPI.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import JSON, Column, DateTime, String, Table, func, insert, select, update
from sqlalchemy.orm import Session

from . import rbac
from .db import Base
from .models import RecordActivity

MODULES_DIR = Path(__file__).resolve().parents[2] / "modules"

REGISTRY: dict[str, dict] = {}
TABLES: dict[str, Table] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _table(key: str) -> Table:
    return Table(
        f"mod_{key}", Base.metadata,
        Column("id", String, primary_key=True),
        Column("project_id", String, index=True),
        Column("ref", String),
        Column("title", String),
        Column("workflow_state", String, index=True),
        Column("party_owner", String, nullable=True),
        Column("assignee", String, nullable=True),
        Column("created_by", String, nullable=True),
        Column("created_at", DateTime(timezone=True)),
        Column("modified_at", DateTime(timezone=True)),
        Column("anchor", JSON, nullable=True),         # {x,y,z} pin on the model
        Column("element_guids", JSON, nullable=True),  # referenced IFC GlobalIds
        Column("links", JSON, nullable=True),          # [{module,id,ref}] change-order chain
        Column("data", JSON),                          # module-defined fields
        extend_existing=True,
    )


def load_registry() -> None:
    """Load every modules/<key>/module.json and register its table. Idempotent."""
    if not MODULES_DIR.exists():
        return
    for mj in sorted(MODULES_DIR.glob("*/module.json")):
        mod = json.loads(mj.read_text(encoding="utf-8"))
        key = mod["key"]
        REGISTRY[key] = mod
        if key not in TABLES:
            TABLES[key] = _table(key)


def get_module(key: str) -> dict:
    mod = REGISTRY.get(key)
    if not mod:
        raise HTTPException(404, f"unknown module {key!r}")
    return mod


# --- workflow ---------------------------------------------------------------
def _transition(mod: dict, frm: str, action: str) -> dict | None:
    for t in mod.get("workflow", {}).get("transitions", []):
        if t["from"] == frm and t["action"] == action:
            return t
    return None


def available_actions(mod: dict, state: str, party: str | None) -> list[dict]:
    out = []
    for t in mod.get("workflow", {}).get("transitions", []):
        if t["from"] == state and rbac.party_allowed(party, t.get("party", [])):
            out.append({"action": t["action"], "to": t["to"], "party": t.get("party", [])})
    return out


# --- CRUD -------------------------------------------------------------------
def _log(db: Session, project_id: str, key: str, rid: str, actor: str,
         party: str | None, action: str, detail: dict | None = None) -> None:
    db.add(RecordActivity(project_id=project_id, module=key, record_id=rid,
                          actor=actor, party=party, action=action, detail=detail))


def _validate_fields(mod: dict, data: dict) -> None:
    missing = [f["name"] for f in mod.get("fields", [])
               if f.get("required") and not data.get(f["name"])]
    if missing:
        raise HTTPException(422, f"missing required field(s): {', '.join(missing)}")


def _next_ref(db: Session, key: str, project_id: str, mod: dict) -> str:
    n = db.execute(select(func.count()).select_from(TABLES[key])
                   .where(TABLES[key].c.project_id == project_id)).scalar() or 0
    return f"{mod.get('ref_prefix', key.upper())}-{n + 1:03d}"


def create_record(db: Session, key: str, project_id: str, body: dict, actor: str,
                  party: str | None) -> dict:
    mod = get_module(key)
    t = TABLES[key]
    data = body.get("data", {})
    _validate_fields(mod, data)
    rid = str(uuid.uuid4())
    title_field = mod.get("title_field") or (mod["fields"][0]["name"] if mod.get("fields") else None)
    row = {
        "id": rid, "project_id": project_id,
        "ref": _next_ref(db, key, project_id, mod),
        "title": data.get(title_field) if title_field else None,
        "workflow_state": mod.get("workflow", {}).get("initial", "open"),
        "party_owner": party, "assignee": body.get("assignee"),
        "created_by": actor, "created_at": _now(), "modified_at": _now(),
        "anchor": body.get("anchor"), "element_guids": body.get("element_guids"),
        "links": body.get("links") or [], "data": data,
    }
    db.execute(insert(t).values(**row))
    _log(db, project_id, key, rid, actor, party, "create", {"ref": row["ref"]})
    db.commit()
    return get_record(db, key, project_id, rid)


def list_records(db: Session, key: str, project_id: str, state: str | None = None,
                 q: str | None = None, limit: int = 200, offset: int = 0) -> list[dict]:
    t = TABLES[key]
    stmt = select(t).where(t.c.project_id == project_id)
    if state:
        stmt = stmt.where(t.c.workflow_state == state)
    stmt = stmt.order_by(t.c.created_at).limit(limit).offset(offset)
    rows = [dict(r._mapping) for r in db.execute(stmt)]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in json.dumps(r.get("data") or {}).lower()
                or ql in (r.get("ref") or "").lower() or ql in (r.get("title") or "").lower()]
    return rows


def get_record(db: Session, key: str, project_id: str, rid: str) -> dict:
    t = TABLES[key]
    r = db.execute(select(t).where(t.c.id == rid, t.c.project_id == project_id)).first()
    if not r:
        raise HTTPException(404, "record not found")
    rec = dict(r._mapping)
    rec["activity"] = [
        {"ts": a.ts.isoformat() if a.ts else None, "actor": a.actor, "party": a.party,
         "action": a.action, "detail": a.detail}
        for a in db.query(RecordActivity).filter(
            RecordActivity.module == key, RecordActivity.record_id == rid)
        .order_by(RecordActivity.ts).all()
    ]
    return rec


def update_record(db: Session, key: str, project_id: str, rid: str, data: dict,
                  actor: str, party: str | None) -> dict:
    t = TABLES[key]
    rec = get_record(db, key, project_id, rid)
    merged = {**(rec.get("data") or {}), **data}
    db.execute(update(t).where(t.c.id == rid).values(data=merged, modified_at=_now()))
    _log(db, project_id, key, rid, actor, party, "update", {"fields": list(data.keys())})
    db.commit()
    return get_record(db, key, project_id, rid)


def transition(db: Session, key: str, project_id: str, rid: str, action: str,
               actor: str, party: str | None, note: str | None = None) -> dict:
    mod = get_module(key)
    t = TABLES[key]
    rec = get_record(db, key, project_id, rid)
    tr = _transition(mod, rec["workflow_state"], action)
    if not tr:
        raise HTTPException(409, f"action {action!r} not allowed from state {rec['workflow_state']!r}")
    if not rbac.party_allowed(party, tr.get("party", [])):
        raise HTTPException(403, f"party {party or 'none'} cannot {action} "
                                 f"(requires {tr.get('party')})")
    db.execute(update(t).where(t.c.id == rid).values(workflow_state=tr["to"], modified_at=_now()))
    _log(db, project_id, key, rid, actor, party, f"transition:{action}",
         {"from": rec["workflow_state"], "to": tr["to"], "note": note})
    db.commit()
    return get_record(db, key, project_id, rid)


def link_record(db: Session, key: str, project_id: str, rid: str, target: dict,
                actor: str, party: str | None) -> dict:
    """Link this record to another (change-order chain). target = {module, id}."""
    t = TABLES[key]
    rec = get_record(db, key, project_id, rid)
    tmod, tid = target["module"], target["id"]
    tref = get_record(db, tmod, project_id, tid)["ref"]
    links = (rec.get("links") or []) + [{"module": tmod, "id": tid, "ref": tref}]
    db.execute(update(t).where(t.c.id == rid).values(links=links, modified_at=_now()))
    _log(db, project_id, key, rid, actor, party, "link", {"to": f"{tmod}:{tref}"})
    db.commit()
    return get_record(db, key, project_id, rid)


def project_pins(db: Session, project_id: str) -> list[dict]:
    """Every anchored module record, as a pin for the 3D viewer overlay."""
    pins = []
    for key, mod in REGISTRY.items():
        if not mod.get("pinnable"):
            continue
        t = TABLES[key]
        rows = db.execute(select(t).where(t.c.project_id == project_id))
        for r in rows:
            m = r._mapping
            if not m["anchor"]:  # JSON-null safe (SQLite stores None as JSON null)
                continue
            pins.append({
                "module": key, "module_name": mod["name"], "icon": mod.get("icon", "•"),
                "id": m["id"], "ref": m["ref"], "title": m["title"],
                "status": m["workflow_state"], "anchor": m["anchor"],
                "element_guids": m["element_guids"],
            })
    return pins
