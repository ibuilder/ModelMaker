"""GC portal module endpoints — config-driven CRUD + role-gated workflow + model pins.

One set of routes serves every module (RFIs, Submittals, the change-order chain, …). The
acting user's *party role* gates workflow transitions; the *capability role* gates writes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from .. import modules as mod_engine
from .. import rbac
from ..db import get_db
from ..models import Project
from ..rbac import current_user, require_role

router = APIRouter()


def _party(pid: str, db: Session, user: str) -> str | None:
    return rbac.party_role_for(db, pid, user)


@router.get("/modules")
def list_modules():
    """Module catalog (drives dynamic UI). Returns each module.json."""
    return [
        {"key": m["key"], "name": m["name"], "section": m.get("section"),
         "icon": m.get("icon"), "pinnable": m.get("pinnable", False),
         "fields": m.get("fields", []), "workflow": m.get("workflow", {})}
        for m in mod_engine.REGISTRY.values()
    ]


@router.get("/projects/{pid}/modules/{key}")
def list_records(pid: str, key: str, state: str | None = None, q: str | None = None,
                 limit: int = 200, offset: int = 0, db: Session = Depends(get_db),
                 _: str = Depends(require_role("viewer"))):
    return mod_engine.list_records(db, key, pid, state, q, limit, offset)


@router.post("/projects/{pid}/modules/{key}", status_code=201)
def create_record(pid: str, key: str, body: dict = Body(...), db: Session = Depends(get_db),
                  user: str = Depends(require_role("reviewer"))):
    return mod_engine.create_record(db, key, pid, body, user, _party(pid, db, user))


@router.get("/projects/{pid}/modules/{key}/{rid}")
def get_record(pid: str, key: str, rid: str, db: Session = Depends(get_db),
               _: str = Depends(require_role("viewer"))):
    rec = mod_engine.get_record(db, key, pid, rid)
    mod = mod_engine.get_module(key)
    rec["available_actions"] = mod_engine.available_actions(
        mod, rec["workflow_state"], _party(pid, db, _))
    return rec


@router.patch("/projects/{pid}/modules/{key}/{rid}")
def update_record(pid: str, key: str, rid: str, data: dict = Body(...),
                  db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    return mod_engine.update_record(db, key, pid, rid, data, user, _party(pid, db, user))


@router.post("/projects/{pid}/modules/{key}/{rid}/transition")
def transition(pid: str, key: str, rid: str, action: str = Body(..., embed=True),
               note: str | None = Body(default=None, embed=True),
               db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    return mod_engine.transition(db, key, pid, rid, action, user, _party(pid, db, user), note)


@router.post("/projects/{pid}/modules/{key}/{rid}/link")
def link_record(pid: str, key: str, rid: str, target: dict = Body(...),
                db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    return mod_engine.link_record(db, key, pid, rid, target, user, _party(pid, db, user))


@router.get("/projects/{pid}/module-pins")
def module_pins(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """Every anchored GC record across pinnable modules — for the 3D viewer overlay."""
    return mod_engine.project_pins(db, pid)
