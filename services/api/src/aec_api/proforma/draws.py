"""Actuals / draws bridge (Phase 5) — the differentiator.

Carries the underwriting cost tree forward into committed + actual on the SAME tree, so the
IRR you underwrote is continuously re-forecast against what's actually getting drawn:
  underwritten budget  →  committed (POs/subcontracts)  →  actual (drawn to date)
Re-forecast = actual-to-date + cost-to-complete per line, re-solved through the full engine."""
from __future__ import annotations

import copy

import numpy as np

from .schedule import spread_line
from .solve import solve


def budget_to_date(cost_lines: list[dict], as_of_month: int, total_months: int) -> list[float]:
    """Budgeted cumulative spend per line through as_of_month (from its S-curve)."""
    out = []
    for ln in cost_lines:
        sched = spread_line(float(ln.get("amount", 0)), int(ln.get("start_month", 0)),
                            int(ln.get("end_month", total_months - 1)),
                            ln.get("curve", "scurve"), total_months)
        out.append(float(np.sum(sched[:as_of_month + 1])))
    return out


def reforecast(assumptions: dict, actuals: list[dict], as_of_month: int) -> dict:
    """actuals: per cost line (aligned by index) — {actual_to_date, committed?, cost_to_complete?}.
    forecast_total = actual_to_date + cost_to_complete (or the remaining budget if not given).
    Returns the underwritten vs re-forecast returns and a budget-vs-actual variance table."""
    cost_lines = assumptions["cost_lines"]
    C = int(assumptions["timing"]["construction_months"])
    btd = budget_to_date(cost_lines, as_of_month, C)
    baseline = solve(assumptions)

    fc = copy.deepcopy(assumptions)
    lines_out = []
    for i, ln in enumerate(cost_lines):
        budget = float(ln.get("amount", 0))
        act = actuals[i] if i < len(actuals) else {}
        actual = float(act.get("actual_to_date", 0) or 0)
        committed = float(act.get("committed", 0) or 0)
        ctc = act.get("cost_to_complete")
        forecast = actual + float(ctc) if ctc is not None else max(budget, actual)
        fc["cost_lines"][i]["amount"] = forecast
        lines_out.append({
            "name": ln.get("name"), "category": ln.get("category"),
            "budget": round(budget, 2), "committed": round(committed, 2),
            "actual_to_date": round(actual, 2), "budget_to_date": round(btd[i], 2),
            "forecast_at_completion": round(forecast, 2),
            "variance_to_budget": round(forecast - budget, 2),
            "pct_drawn": round(actual / budget * 100, 1) if budget else 0.0,
        })

    forecast_res = solve(fc)
    tot_budget = sum(L["budget"] for L in lines_out)
    tot_forecast = sum(L["forecast_at_completion"] for L in lines_out)
    base_irr = baseline["returns"]["equity_irr"]
    fc_irr = forecast_res["returns"]["equity_irr"]
    return {
        "as_of_month": as_of_month,
        "lines": lines_out,
        "totals": {
            "budget": round(tot_budget, 2),
            "committed": round(sum(L["committed"] for L in lines_out), 2),
            "actual_to_date": round(sum(L["actual_to_date"] for L in lines_out), 2),
            "forecast_at_completion": round(tot_forecast, 2),
            "variance_to_budget": round(tot_forecast - tot_budget, 2),
        },
        "underwritten_returns": baseline["returns"],
        "forecast_returns": forecast_res["returns"],
        "irr_delta": (None if base_irr is None or fc_irr is None
                      else round(fc_irr - base_irr, 4)),
    }
