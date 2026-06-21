"""Schedule visual endpoints (GC portal): Gantt + Line-of-Balance SVG."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from .. import modules as me
from .. import schedule_cpm, schedule_viz
from ..db import get_db
from ..rbac import require_role

router = APIRouter()


def _svg(s: str) -> Response:
    return Response(s.encode("utf-8"), media_type="image/svg+xml")


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
