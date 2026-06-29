"""Project assistant endpoint — plain-English Q&A across the whole project (modules, schedule,
budget, risk, rent roll)."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import assistant
from ..db import get_db
from ..rbac import require_role

router = APIRouter()


@router.post("/projects/{pid}/assistant")
def project_assistant(pid: str, body: dict = Body(...), db: Session = Depends(get_db),
                      _: str = Depends(require_role("viewer"))):
    """Ask about the project in plain English ('how many open RFIs?', 'what's the SPI?', 'occupancy?').
    Grounded in a live project snapshot; returns the snapshot when no AI key is configured."""
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(422, "question required")
    return assistant.ask(db, pid, question)


@router.get("/projects/{pid}/assistant/snapshot")
def assistant_snapshot(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """The grounded project snapshot the assistant uses (module tallies, schedule, budget, risk)."""
    return assistant.project_snapshot(db, pid)
