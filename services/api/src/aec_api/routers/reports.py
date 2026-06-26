"""Report Center endpoints — catalog + per-report PDF / Excel export."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import reports
from ..db import get_db
from ..rbac import current_user, require_role
from .exports import _xlsx_response

router = APIRouter()


@router.get("/reports")
def report_catalog(_: str = Depends(current_user)):
    """The available reports (id, name, group) for the Reports panel."""
    return {"reports": reports.catalog()}


@router.get("/projects/{pid}/reports/{report}.pdf")
def report_pdf(pid: str, report: str, db: Session = Depends(get_db),
               _: str = Depends(require_role("viewer"))):
    try:
        rep = reports.build(db, pid, report)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return Response(reports.to_pdf(rep), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{report}.pdf"'})


@router.get("/projects/{pid}/reports/{report}.xlsx")
def report_xlsx(pid: str, report: str, db: Session = Depends(get_db),
                _: str = Depends(require_role("viewer"))):
    try:
        rep = reports.build(db, pid, report)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return _xlsx_response(reports.to_sheets(rep), f"{report}.xlsx")
