"""Real-estate development finance (Proforma) endpoints: stateless solve + scenario CRUD.
The pure engine (aec_api.proforma) is validated by Pydantic models that double as the
OpenAPI contract. A full proforma + waterfall solves in <100ms — run it in-request."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from sqlalchemy import delete

from .. import cost as cost_engine
from .. import modules as me
from ..db import get_db
from ..models import Scenario
from ..proforma.draws import reforecast
from ..proforma.sensitivity import sensitivity
from ..proforma.solve import solve

router = APIRouter()


# --- input contract (validation + docs) -------------------------------------
class Timing(BaseModel):
    construction_months: int = Field(gt=0)
    leaseup_months: int = 0
    hold_years: float = Field(gt=0)
    start_date: str | None = None


class CostLine(BaseModel):
    category: Literal["land", "hard", "soft", "contingency", "fee"]
    name: str
    amount: float = 0
    curve: Literal["scurve", "linear", "upfront"] = "scurve"
    start_month: int = 0
    end_month: int = 0
    csi_code: str | None = None


class Debt(BaseModel):
    ltc: float = Field(ge=0, le=1)
    rate: float = Field(ge=0)
    points: float = 0.0
    funding: Literal["equity_first", "pari_passu", "loan_first"] = "equity_first"


class Equity(BaseModel):
    lp_pct: float = Field(ge=0, le=1)
    gp_pct: float = Field(ge=0, le=1)


class Ops(BaseModel):
    potential_rent_annual: float
    other_income_annual: float = 0
    opex_annual: float
    stabilized_occ: float = Field(gt=0, le=1)
    credit_loss_pct: float = 0.0


class Exit(BaseModel):
    exit_cap: float = Field(gt=0)
    selling_cost_pct: float = 0.0


class Tier(BaseModel):
    hurdle: float | None = None
    lp: float
    gp: float


class Waterfall(BaseModel):
    pref_rate: float = 0.08
    style: Literal["american", "european"] = "american"
    clawback: bool = False
    tiers: list[Tier]


class Assumptions(BaseModel):
    timing: Timing
    cost_lines: list[CostLine]
    debt: Debt
    equity: Equity
    operations: Ops
    exit: Exit
    waterfall: Waterfall
    discount_rate: float = 0.10


@router.post("/proforma/solve")
def solve_stateless(a: Assumptions):
    """Solve a deal without persisting — full S&U, cash flows, returns, waterfall."""
    return solve(a.model_dump())


class Axis(BaseModel):
    path: str                       # e.g. "exit.exit_cap" or "cost_lines.1.amount"
    values: list[float]


class SensitivityIn(BaseModel):
    assumptions: Assumptions
    x: Axis
    y: Axis
    metric: str = "returns.equity_irr"


@router.post("/proforma/sensitivity")
def run_sensitivity(body: SensitivityIn):
    """Two-variable data table: the metric solved across the x×y grid of two drivers."""
    return sensitivity(body.assumptions.model_dump(), body.x.path, body.x.values,
                       body.y.path, body.y.values, body.metric)


# --- scenarios (persisted, versioned) ---------------------------------------
class ScenarioIn(BaseModel):
    name: str
    project_id: str | None = None
    assumptions: Assumptions


@router.post("/proforma/scenarios", status_code=201)
def create_scenario(body: ScenarioIn, db: Session = Depends(get_db)):
    result = solve(body.assumptions.model_dump())
    s = Scenario(name=body.name, project_id=body.project_id,
                 assumptions=body.assumptions.model_dump(), result=result)
    db.add(s)
    db.commit()
    return {"id": s.id, "name": s.name, "result": result}


@router.get("/proforma/scenarios")
def list_scenarios(project_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Scenario)
    if project_id:
        q = q.filter(Scenario.project_id == project_id)
    return [{"id": s.id, "name": s.name, "project_id": s.project_id,
             "returns": (s.result or {}).get("returns")} for s in q.order_by(Scenario.created_at).all()]


@router.get("/proforma/scenarios/{sid}")
def get_scenario(sid: str, db: Session = Depends(get_db)):
    s = db.get(Scenario, sid)
    if not s:
        raise HTTPException(404, "scenario not found")
    return {"id": s.id, "name": s.name, "assumptions": s.assumptions, "result": s.result}


@router.put("/proforma/scenarios/{sid}")
def update_scenario(sid: str, body: ScenarioIn, db: Session = Depends(get_db)):
    s = db.get(Scenario, sid)
    if not s:
        raise HTTPException(404, "scenario not found")
    if s.is_locked:
        raise HTTPException(409, "scenario is locked")
    s.assumptions = body.assumptions.model_dump()
    s.name = body.name
    s.result = solve(s.assumptions)
    db.commit()
    return {"id": s.id, "name": s.name, "result": s.result}


@router.post("/proforma/scenarios/{sid}/clone", status_code=201)
def clone_scenario(sid: str, name: str = Body(..., embed=True), db: Session = Depends(get_db)):
    s = db.get(Scenario, sid)
    if not s:
        raise HTTPException(404, "scenario not found")
    c = Scenario(name=name, project_id=s.project_id, assumptions=s.assumptions, result=s.result)
    db.add(c)
    db.commit()
    return {"id": c.id, "name": c.name}


class Actual(BaseModel):
    actual_to_date: float = 0
    committed: float = 0
    cost_to_complete: float | None = None


class ForecastIn(BaseModel):
    actuals: list[Actual]
    as_of_month: int = 0


@router.post("/proforma/scenarios/{sid}/forecast")
def forecast_scenario(sid: str, body: ForecastIn, db: Session = Depends(get_db)):
    """Re-forecast the underwritten returns against actuals drawn to date (Phase 5 bridge)."""
    s = db.get(Scenario, sid)
    if not s:
        raise HTTPException(404, "scenario not found")
    return reforecast(s.assumptions, [a.model_dump() for a in body.actuals], body.as_of_month)


@router.post("/proforma/forecast")
def forecast_stateless(assumptions: Assumptions, actuals: list[Actual] = Body(...),
                       as_of_month: int = Body(0)):
    return reforecast(assumptions.model_dump(), [a.model_dump() for a in actuals], as_of_month)


class DrawPackageIn(BaseModel):
    project_id: str                 # the GC portal project to receive the SOV
    actuals: list[Actual]
    as_of_month: int = 0
    retainage_pct: float = 5.0
    app_no: int = 1


@router.post("/proforma/scenarios/{sid}/draw-package")
def draw_package(sid: str, body: DrawPackageIn, db: Session = Depends(get_db)):
    """Bridge underwriting → construction draws: turn the scenario's cost tree + actuals into
    Schedule-of-Values records on a GC project, then produce the AIA G702/G703 pay app —
    so the IRR you underwrote and the lender draw run off the SAME cost tree."""
    s = db.get(Scenario, sid)
    if not s:
        raise HTTPException(404, "scenario not found")
    if "sov" not in me.TABLES:
        raise HTTPException(409, "SOV module not loaded")
    fc = reforecast(s.assumptions, [a.model_dump() for a in body.actuals], body.as_of_month)
    pid = body.project_id
    # replace any prior SOV for this project so re-running is idempotent
    db.execute(delete(me.TABLES["sov"]).where(me.TABLES["sov"].c.project_id == pid))
    db.commit()
    for i, L in enumerate(fc["lines"]):
        me.create_record(db, "sov", pid, {"data": {
            "item_no": f"{i + 1:02d}", "description": L["name"], "cost_code": L["category"],
            "scheduled_value": L["forecast_at_completion"],   # revised contract value
            "completed_this": L["actual_to_date"],
            "retainage_pct": body.retainage_pct,
        }}, "proforma-bridge", "GC")
    g703 = cost_engine.g703(db, pid)
    g702 = cost_engine.g702(db, pid, app_no=body.app_no)
    return {
        "sov_lines_created": len(fc["lines"]),
        "g702": g702, "g703_totals": g703["totals"],
        "g702_pdf": f"/projects/{pid}/cost/g702.pdf?app_no={body.app_no}",
        "forecast_returns": fc["forecast_returns"],
    }


@router.post("/proforma/compare")
def compare(ids: list[str] = Body(...), db: Session = Depends(get_db)):
    """Side-by-side metrics for several scenarios."""
    out = []
    for sid in ids:
        s = db.get(Scenario, sid)
        if s and s.result:
            out.append({"id": s.id, "name": s.name, "returns": s.result.get("returns"),
                        "sources_uses": s.result.get("sources_uses")})
    return out
