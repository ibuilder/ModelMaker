"""Takt / line-of-balance planning (R2) — model construction as a vertical assembly line, the way
the Empire State Building was built: each trade flows floor-to-floor at a steady **takt** (a fixed
days-per-floor production rate), trades chase each other up the building, and material is delivered
**just in time** for each floor. Pure functions over a trade list.

Classic LOB recurrence: a trade can't start floor f until it finished floor f-1 *and* the preceding
trade finished floor f. `plan()` returns per-trade per-floor start/finish, total duration, the JIT
delivery plan, and the peak simultaneous crew count."""
from __future__ import annotations

from typing import Any

# default trade sequence with a production rate (days per floor) — a residential tower takt train
DEFAULT_TRADES = [
    {"name": "Structure", "takt_days": 5},
    {"name": "Envelope", "takt_days": 5},
    {"name": "MEP rough-in", "takt_days": 6},
    {"name": "Interiors", "takt_days": 8},
    {"name": "Finishes", "takt_days": 6},
]


def plan(floors: int, trades: list[dict] | None = None, start_day: int = 0,
         jit_lead_days: int = 1) -> dict[str, Any]:
    """Line-of-balance schedule for `floors` floors through the trade train. Returns each trade's
    floor-by-floor start/finish, total duration, a JIT delivery plan (deliver `jit_lead_days` before
    each floor's trade starts), production rate (floors/week), and the peak concurrent crew count."""
    floors = max(1, int(floors))
    trades = trades or DEFAULT_TRADES
    nt = len(trades)
    # finish[i][f] grid; iterate trades (i) then floors (f) honoring both predecessors
    finish: list[list[float]] = [[0.0] * floors for _ in range(nt)]
    start: list[list[float]] = [[0.0] * floors for _ in range(nt)]
    for i, tr in enumerate(trades):
        td = max(1, int(tr.get("takt_days", 5)))
        for f in range(floors):
            prev_floor_done = finish[i][f - 1] if f > 0 else start_day
            prev_trade_done = finish[i - 1][f] if i > 0 else start_day
            s = max(prev_floor_done, prev_trade_done)
            start[i][f] = s
            finish[i][f] = s + td

    duration = max(finish[i][floors - 1] for i in range(nt))
    trade_out, delivery = [], []
    for i, tr in enumerate(trades):
        trade_out.append({
            "name": tr["name"], "takt_days": int(tr.get("takt_days", 5)),
            "start_day": round(start[i][0]), "finish_day": round(finish[i][floors - 1]),
            "floor_starts": [round(start[i][f]) for f in range(floors)],
        })
        for f in range(floors):
            delivery.append({"floor": f + 1, "trade": tr["name"],
                             "deliver_by_day": round(max(0, start[i][f] - jit_lead_days))})
    delivery.sort(key=lambda d: d["deliver_by_day"])
    # floors/week of the lead trade (structure) sets the pace of ascent
    lead_takt = max(1, int(trades[0].get("takt_days", 5)))
    return {
        "floors": floors, "trades": trade_out,
        "duration_days": round(duration),
        "duration_weeks": round(duration / 7, 1),
        "floors_per_week": round(7 / lead_takt, 2),
        "crew_peak": min(floors, nt),               # up to one crew per trade once the train ramps
        "delivery_plan": delivery,
    }
