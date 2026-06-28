"""Disposition & valuation endpoints — auto-fill a listing from the project, the tri-approach
appraisal, the RESO export seam (bridge to WPRealWise / MLS), and a signed, read-only public listing
link for sharing a 3D tour / fact sheet without a session."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .. import marketing, modules as me, rbac, signing
from ..db import get_db
from ..models import Project

router = APIRouter()


@router.get("/projects/{pid}/listings/autofill")
def listing_autofill(pid: str, db: Session = Depends(get_db),
                     _: str = Depends(rbac.require_role("viewer"))):
    """Pre-populated listing fields from the project's proforma + model (the off-plan advantage)."""
    return {"data": marketing.autofill_listing(db, pid)}


@router.get("/projects/{pid}/appraisal")
def get_appraisal(pid: str, request: Request, db: Session = Depends(get_db),
                  _: str = Depends(rbac.require_role("viewer"))):
    """Tri-approach valuation. Saved overrides (project.dev_property.appraisal) merge with any query
    overrides (query wins): depreciation_pct, land_value, replacement_cost_new, stabilized_noi,
    cap_rate, subject_sqft, weight_income, weight_cost, weight_sales."""
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    saved = (p.dev_property or {}).get("appraisal") or {}
    overrides = dict(saved)
    qp = request.query_params
    for k in ("depreciation_pct", "land_value", "replacement_cost_new", "stabilized_noi",
              "cap_rate", "subject_sqft", "subject_units"):
        if qp.get(k) not in (None, ""):
            try:
                overrides[k] = float(qp[k])
            except ValueError:
                pass
    weights = {}
    for wk, qk in (("income", "weight_income"), ("cost", "weight_cost"),
                   ("sales_comparison", "weight_sales")):
        if qp.get(qk) not in (None, ""):
            try:
                weights[wk] = float(qp[qk])
            except ValueError:
                pass
    if weights or saved.get("weights"):
        overrides["weights"] = {**(saved.get("weights") or {}), **weights}
    return marketing.compute_appraisal(db, pid, overrides)


@router.post("/projects/{pid}/appraisal")
def save_appraisal(pid: str, overrides: dict = Body(...), db: Session = Depends(get_db),
                   _: str = Depends(rbac.require_role("editor"))):
    """Persist appraisal overrides (depreciation, land value, weights, …) on the project."""
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    p.dev_property = {**(p.dev_property or {}), "appraisal": overrides}
    db.commit()
    return marketing.compute_appraisal(db, pid, overrides)


@router.get("/projects/{pid}/listings/{lid}/reso")
def listing_reso(pid: str, lid: str, db: Session = Depends(get_db),
                 _: str = Depends(rbac.require_role("viewer"))):
    """The RESO Data Dictionary payload for a listing — the shape a bridge POSTs to WPRealWise / MLS."""
    rec = me.get_record(db, "listing", pid, lid)
    return {"reso": marketing.to_reso(rec)}


@router.post("/projects/{pid}/listings/{lid}/share")
def listing_share(pid: str, lid: str, ttl: int = Query(7 * 24 * 3600, ge=60),
                  db: Session = Depends(get_db), _: str = Depends(rbac.require_role("viewer"))):
    """Mint a signed, expiring URL to the public listing JSON (for a QR / shared link). The signature
    authorizes exactly that path until it expires — no session needed by the recipient."""
    me.get_record(db, "listing", pid, lid)                       # 404 if missing
    path = f"/projects/{pid}/listings/{lid}/public"
    return signing.sign_path(path, ttl=ttl)


@router.get("/projects/{pid}/listings/{lid}/public")
def listing_public(pid: str, lid: str, request: Request, db: Session = Depends(get_db)):
    """Read-only public listing — the only intentionally-anonymous surface. Requires a valid signed
    URL (HMAC) regardless of RBAC; publishes only listing-safe fields (no internal financials beyond
    what the owner put in the public description / asking price)."""
    qp = request.query_params
    if not signing.verify_path(request.url.path, qp.get("sig"), qp.get("exp")):
        raise HTTPException(403, "a valid signed link is required")
    rec = me.get_record(db, "listing", pid, lid)
    d = rec.get("data") or {}
    public_fields = ("address", "asset_type", "list_price", "city", "state", "zip_code",
                     "beds", "baths", "sqft", "num_units", "year_built", "price_psf",
                     "public_description", "virtual_tour_url", "highlights")
    return {
        "ref": rec.get("ref"),
        "status": rec.get("workflow_state"),
        "listing": {k: d.get(k) for k in public_fields if d.get(k) not in (None, "")},
    }
