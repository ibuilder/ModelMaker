"""Sources & Uses — the capital plan that sits between the cost budget and the proforma.

USES come from the developer cost budget (acquisition + hard + soft + contingency) plus a financing
line (construction-loan interest, estimated on the average outstanding balance). SOURCES size senior
debt (LTC, with optional LTV / DSCR / debt-yield caps when operating figures are supplied) and fill
the rest with LP/GP equity. Pure over the budget summary so it's testable without a DB."""
from __future__ import annotations

from typing import Any


def build(budget_summary: dict[str, Any], params: dict[str, Any] | None = None) -> dict[str, Any]:
    """budget_summary: dev_budget.summarize() output. params: ltc, rate, construction_months,
    lp_pct, and optional sizing caps (max_ltv + stabilized_value, min_dscr / min_debt_yield + noi)."""
    p = params or {}
    cats = budget_summary["categories"]
    acq = cats["acquisition"]["subtotal"]
    hard = cats["hard"]["subtotal"]
    soft = cats["soft"]["subtotal"]
    contingency = round(sum(cats[c]["contingency"] for c in cats), 2)
    cost_excl_fin = round(acq + hard + soft + contingency, 2)   # == grand_total

    ltc = float(p.get("ltc", 0.65))
    rate = float(p.get("rate", 0.075))
    months = float(p.get("construction_months", 18))
    # construction-loan interest on ~55% average outstanding balance over the build (one pass)
    interest = round(ltc * cost_excl_fin * rate * (months / 12) * 0.55)
    # USES total is the sum of the displayed (rounded) line items, so the statement always reconciles
    # to the penny — no drift between the lines a user sees and the stated total (WPLedger invariant).
    use_amounts = [round(acq), round(hard), round(soft), round(contingency), interest]
    total_uses = float(sum(use_amounts))

    # debt sizing: LTC, capped by LTV / DSCR / debt-yield when operating inputs are provided
    debt = ltc * total_uses
    binding = "LTC"
    noi = p.get("noi"); value = p.get("stabilized_value")
    if p.get("max_ltv") and value:
        cap = float(p["max_ltv"]) * float(value)
        if cap < debt:
            debt, binding = cap, "LTV"
    if p.get("min_debt_yield") and noi:
        cap = float(noi) / float(p["min_debt_yield"])
        if cap < debt:
            debt, binding = cap, "debt yield"
    if p.get("min_dscr") and noi and rate:
        cap = float(noi) / (float(p["min_dscr"]) * rate)   # interest-only proxy
        if cap < debt:
            debt, binding = cap, "DSCR"
    debt = round(debt)
    equity = round(total_uses - debt)           # equity plugs the gap so SOURCES == USES exactly
    lp = float(p.get("lp_pct", 0.9))
    lp_equity = round(equity * lp)
    gp_equity = equity - lp_equity              # GP absorbs the rounding remainder (no $1 drift)

    uses = [
        {"label": "Acquisition", "amount": round(acq)},
        {"label": "Hard costs", "amount": round(hard)},
        {"label": "Soft costs", "amount": round(soft)},
        {"label": "Contingency", "amount": round(contingency)},
        {"label": "Financing (construction interest)", "amount": interest},
    ]
    sources = [
        {"label": f"Senior debt ({ltc * 100:.0f}% LTC, bound by {binding})", "amount": debt},
        {"label": "LP equity", "amount": lp_equity},
        {"label": "GP equity", "amount": gp_equity},
    ]
    total_sources = sum(s["amount"] for s in sources)   # == debt + equity == total_uses
    return {
        "uses": [u for u in uses if u["amount"]],
        "sources": [s for s in sources if s["amount"]],
        "total_uses": total_uses,
        "total_sources": total_sources,
        "ltc": round(debt / total_uses, 4) if total_uses else 0,
        "debt": debt, "equity": equity, "binding_constraint": binding,
        # the displayed lines reconcile to the totals, and sources tie to uses, to the dollar
        "balanced": (sum(u["amount"] for u in uses) == total_uses == total_sources),
    }
