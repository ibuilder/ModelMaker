"""GC project budget (GMP) — the relational on-budget view a project executive lives in.

Assembles the agreed-upon GMP from its parts and tracks each against reality:

  Direct trade work (cost codes, grouped by CSI division, tied to bid packages)
  + General Requirements (CSI Division 01 cost codes + GR staffing)
  + General Conditions (project-team staffing projections)
  + Overhead  (overhead_pct of cost)
  + Fee / Profit (fee_pct of cost)
  + GC Contingency (contingency_pct of direct)
  = GMP

Every line carries budget vs committed (buyout) vs actual vs forecast vs variance, keyed off the same
cost codes / commitments / subcontracts / direct costs the rest of the portal uses. Reconciles to the
prime-contract value and to the developer proforma's construction hard-cost line, so the GC budget and
the developer's underwriting are one relational number.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from . import modules as me


def _n(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _pdate(v: Any):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _records(db: Session, key: str, pid: str) -> list[dict]:
    if key not in me.TABLES:
        return []
    return me.list_records(db, key, pid, limit=1_000_000)


def staffing_cost(data: dict) -> float:
    """Projected cost of a staffing line = headcount × rate × periods(on-site → off-site)."""
    count = _n(data.get("count")) or 1
    rate = _n(data.get("rate"))
    if not rate:
        return 0.0
    s, f = _pdate(data.get("start")), _pdate(data.get("finish"))
    period = (data.get("rate_period") or "Month").lower()
    if s and f and f > s:
        days = (f - s).days
        units = days / 30.4 if period == "month" else days / 7 if period == "week" else days * 8
    else:
        units = 1.0
    return round(count * rate * units, 2)


def _line(name: str, budget: float, committed: float = 0.0, actual: float = 0.0,
          **extra: Any) -> dict:
    forecast = round(max(committed, actual, 0.0) or budget, 2)
    return {"name": name, "budget": round(budget, 2), "committed": round(committed, 2),
            "actual": round(actual, 2), "forecast": forecast,
            "variance": round(budget - forecast, 2), **extra}


def _category(key: str, name: str, lines: list[dict], **extra: Any) -> dict:
    agg = {k: round(sum(_n(l[k]) for l in lines), 2) for k in ("budget", "committed", "actual", "forecast")}
    agg["variance"] = round(agg["budget"] - agg["forecast"], 2)
    return {"key": key, "name": name, "lines": lines, **agg, **extra}


def gmp_budget(db: Session, pid: str, proforma_hard: float | None = None) -> dict:
    """Build the full GMP budget. `proforma_hard` is the developer proforma's hard-cost total for the
    reconciliation line (the caller passes it from the project's dev_budget)."""
    # --- maps keyed by the referenced cost_code record id -----------------------
    budget_by_cc: dict[str, float] = {}
    for r in _records(db, "budget", pid):
        d = r.get("data") or {}
        cc = d.get("cost_code")
        amt = _n(d.get("revised")) or _n(d.get("original")) or _n(d.get("budget"))
        if cc:
            budget_by_cc[cc] = budget_by_cc.get(cc, 0.0) + amt

    committed_by_cc: dict[str, float] = {}
    for r in _records(db, "commitment", pid):
        d = r.get("data") or {}
        if r.get("workflow_state") in ("executed", "closed") and d.get("cost_code"):
            committed_by_cc[d["cost_code"]] = committed_by_cc.get(d["cost_code"], 0.0) + _n(d.get("amount"))
    for r in _records(db, "subcontract", pid):
        d = r.get("data") or {}
        if r.get("workflow_state") == "executed" and d.get("cost_code"):
            committed_by_cc[d["cost_code"]] = committed_by_cc.get(d["cost_code"], 0.0) + _n(d.get("value"))

    actual_by_cc: dict[str, float] = {}
    for r in _records(db, "direct_cost", pid):
        d = r.get("data") or {}
        if d.get("cost_code"):
            actual_by_cc[d["cost_code"]] = actual_by_cc.get(d["cost_code"], 0.0) + _n(d.get("amount"))

    # --- classify cost codes: Division 01/00 → General Requirements; else direct trade work ----
    direct_groups: dict[str, list[dict]] = {}
    gr_costcode_lines: list[dict] = []
    for r in _records(db, "cost_code", pid):
        d = r.get("data") or {}
        cid = r.get("id")
        div = str(d.get("division") or "").strip()
        code = d.get("code") or r.get("ref") or ""
        line = _line(f"{code} {d.get('description') or ''}".strip(),
                     budget_by_cc.get(cid, 0.0), committed_by_cc.get(cid, 0.0),
                     actual_by_cc.get(cid, 0.0), code=code, division=div, ref=r.get("ref"))
        if div[:2] in ("00", "01"):
            gr_costcode_lines.append(line)
        else:
            direct_groups.setdefault(div or "—", []).append(line)

    # --- staffing projections split into General Conditions / General Requirements ----
    gc_staff, gr_staff = [], []
    for r in _records(db, "staffing", pid):
        d = r.get("data") or {}
        cost = staffing_cost(d)
        line = _line(f"{d.get('role') or 'Staff'} ×{int(_n(d.get('count')) or 1)}", cost, cost, 0.0,
                     role=d.get("role"), ref=r.get("ref"))
        (gr_staff if d.get("category") == "General Requirements" else gc_staff).append(line)

    # --- assemble categories ----------------------------------------------------
    direct_group_cats = [
        _category(f"div-{div}", f"Division {div}" if div != "—" else "Uncoded",
                  sorted(lines, key=lambda l: l["name"]))
        for div, lines in sorted(direct_groups.items())
    ]
    direct = _category("direct", "Direct Work (Trades)",
                       [{**g, "is_group": True} for g in direct_group_cats], groups=direct_group_cats)
    general_conditions = _category("general_conditions", "General Conditions", gc_staff)
    general_requirements = _category("general_requirements", "General Requirements",
                                     gr_costcode_lines + gr_staff)

    cost_of_work = direct["budget"] + general_conditions["budget"] + general_requirements["budget"]

    # --- markups from the prime contract (PX sets the rates) ---------------------
    pc = next(iter(_records(db, "prime_contract", pid)), None)
    pcd = (pc or {}).get("data") or {}
    oh_pct, fee_pct, cont_pct = _n(pcd.get("overhead_pct")), _n(pcd.get("fee_pct")), _n(pcd.get("contingency_pct"))
    gmp_value = _n(pcd.get("value"))

    overhead_amt = round(cost_of_work * oh_pct / 100, 2)
    fee_amt = round((cost_of_work + overhead_amt) * fee_pct / 100, 2)
    contingency_amt = round(direct["budget"] * cont_pct / 100, 2)
    overhead = _category("overhead", f"Overhead ({oh_pct}%)", [_line("Home-office overhead", overhead_amt)])
    fee = _category("fee", f"Fee / Profit ({fee_pct}%)", [_line("Fee", fee_amt)])
    contingency = _category("contingency", f"GC Contingency ({cont_pct}%)", [_line("Contingency", contingency_amt)])

    categories = [direct, general_requirements, general_conditions, overhead, fee, contingency]
    totals = {k: round(sum(_n(c[k]) for c in categories), 2)
              for k in ("budget", "committed", "actual", "forecast")}
    totals["variance"] = round(totals["budget"] - totals["forecast"], 2)
    gmp_computed = totals["budget"]

    # --- bid-package buyout tracking (relational to every package) ---------------
    bid_packages = []
    for r in _records(db, "bid_package", pid):
        d = r.get("data") or {}
        bud = _n(d.get("budget")) or _n(d.get("estimate"))
        bid_packages.append({"ref": r.get("ref"), "name": r.get("title") or d.get("name"),
                             "trade": d.get("trade"), "budget": round(bud, 2),
                             "submissions": _n(d.get("submission_count"))})

    return {
        "gmp": {"contract_value": round(gmp_value, 2), "computed": round(gmp_computed, 2),
                "reconciliation": round(gmp_value - gmp_computed, 2) if gmp_value else None,
                "cost_of_work": round(cost_of_work, 2),
                "markups": {"overhead_pct": oh_pct, "fee_pct": fee_pct, "contingency_pct": cont_pct}},
        "categories": categories,
        "totals": totals,
        "bid_packages": bid_packages,
        "staffing": {"projected": round(general_conditions["budget"] + sum(_n(l["budget"]) for l in gr_staff), 2),
                     "headcount_roles": len(gc_staff) + len(gr_staff)},
        "proforma": ({"hard_cost": round(_n(proforma_hard), 2),
                      "gmp_vs_hard": round(gmp_computed - _n(proforma_hard), 2)}
                     if proforma_hard is not None else None),
    }
