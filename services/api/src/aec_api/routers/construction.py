"""Construction analytics — T&M (eTicket) cost rollup + the submittal register."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import distribution as dist_engine, submittals as sub_engine, tm as tm_engine
from ..db import get_db
from ..rbac import require_role

router = APIRouter()


@router.get("/projects/{pid}/modules/{key}/{rid}/distribution")
def record_distribution(pid: str, key: str, rid: str, db: Session = Depends(get_db),
                        _: str = Depends(require_role("viewer"))):
    """Resolve a record's distribution (CC) field against the contact directory → recipients + emails."""
    return dist_engine.for_record(db, pid, key, rid)


@router.get("/projects/{pid}/tm-summary")
def tm_summary(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """Time & Material (eTicket) cost rollup — labor/material/equipment, billed vs unbilled."""
    return tm_engine.tm_summary(db, pid)


@router.get("/projects/{pid}/submittals/register")
def submittal_register(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """Spec-section submittal register — turnaround, ball-in-court, overdue flags."""
    return sub_engine.submittal_register(db, pid)
