"""Role-tailored dashboard endpoint (GC portal)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from .. import ai, dashboard, mailer, oauth, rbac, report
from ..db import get_db
from ..models import Project
from ..rbac import require_role

router = APIRouter()


@router.get("/projects/{pid}/dashboard")
def get_dashboard(pid: str, party: str | None = None, db: Session = Depends(get_db),
                  user: str = Depends(require_role("viewer"))):
    """Dashboard tailored to `party` (defaults to the caller's project party role)."""
    party = party or rbac.party_role_for(db, pid, user) or "GC"
    return dashboard.build(db, pid, party)


@router.get("/capabilities")
def capabilities():
    """Which optional integrations are wired (for at-a-glance status badges). Not sensitive —
    just feature flags + the configured SSO provider ids."""
    return {"ai": ai.ai_enabled(), "email": mailer.smtp_configured(),
            "sso": [p["id"] for p in oauth.enabled_providers()]}


@router.get("/projects/{pid}/ai/risk-summary")
def risk_summary(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("reviewer"))):
    """AI/rules risk read over the project dashboard (owner/PM reporting)."""
    d = dashboard.build(db, pid, "GC")
    return {**ai.risk_summary(d.get("kpis", {}), d.get("cost")), "ai_enabled": ai.ai_enabled()}


@router.get("/projects/{pid}/report.pdf")
def status_report(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """One-page project status report (KPIs, cost, open items by module, ball-in-court) as a PDF."""
    proj = db.get(Project, pid)
    pdf = report.project_status_pdf(db, pid, proj.name if proj else pid)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="status-report.pdf"'})
