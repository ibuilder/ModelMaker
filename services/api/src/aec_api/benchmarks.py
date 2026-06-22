"""Research-grade benchmark defaults (R5) — citable ranges for the assumptions that drive feasibility
(cost/sf, cap rates, soft-cost %, construction productivity, lean PPC). Grounds the app's defaults
and the underwriting guardrails in sources rather than magic numbers. Conceptual ranges; a project's
own Comparables override them.

Sources: CRE underwriting practice (cap-rate bands, soft-cost ratios — Feldman Equities, A.CRE),
Empire State production rates (Skyscraper Museum), VT lean-construction research (Last Planner PPC)."""
from __future__ import annotations

from typing import Any

BENCHMARKS: dict[str, dict[str, Any]] = {
    "hard_cost_psf": {"residential": [200, 350], "commercial": [150, 300], "unit": "$/sf",
                      "note": "Conceptual all-in hard cost; varies by market/finish."},
    "soft_cost_pct": {"range": [0.10, 0.30], "typical": 0.20, "unit": "% of hard",
                      "note": "Residential 10–20%, institutional 25–35%."},
    "contingency_pct": {"hard": [0.05, 0.10], "soft": [0.05, 0.10], "unit": "% of subtotal"},
    "cap_rate": {"stabilized": [0.040, 0.055], "value_add": [0.055, 0.075], "unit": "cap",
                 "note": "Stabilized trades tighter; value-add wider (going-in)."},
    "vacancy": {"range": [0.05, 0.07], "unit": "% of PGI"},
    "mgmt_fee": {"typical": 0.05, "unit": "% of EGI"},
    "reserves_per_unit": {"range": [250, 500], "unit": "$/unit/yr (above NOI)"},
    "equity_irr": {"typical": [0.08, 0.25], "unit": "IRR", "note": "LP threshold ~8%; >35% suspect."},
    "production_rate": {"esb_frame": "≈1 floor/day (Empire State, 1931)",
                        "typical_tower": [1.0, 2.0], "unit": "floors/week"},
    "lean_ppc": {"good": 0.80, "unit": "Plan Percent Complete",
                 "note": "High-performing Last Planner teams sustain ~80%+."},
}


def all_benchmarks() -> dict[str, Any]:
    return {"benchmarks": BENCHMARKS,
            "disclaimer": "Conceptual ranges for grounding defaults — validate against project comps."}
