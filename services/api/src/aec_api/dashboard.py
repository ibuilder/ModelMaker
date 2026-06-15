"""Role-tailored dashboard (GC portal). Aggregates records across all modules into a
per-party view: KPIs, "ball-in-your-court" action items (records the acting party can move
through the workflow right now), per-module status counts, and a cost snapshot."""
from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from . import cost
from . import modules as me


def _overdue(rec: dict) -> bool:
    due = rec["data"].get("due_date")
    try:
        return bool(due) and date.fromisoformat(str(due)[:10]) < date.today() \
            and rec["workflow_state"] not in ("closed", "answered", "verified", "done")
    except (TypeError, ValueError):
        return False


def build(db: Session, pid: str, party: str | None) -> dict[str, Any]:
    by_module: list[dict] = []
    action_items: list[dict] = []
    overdue = 0
    open_states = {"open", "submitted", "draft", "issued", "scheduled", "investigating",
                   "applied", "agenda", "proposed", "pending"}
    counts = Counter()

    for key, mod in me.REGISTRY.items():
        recs = me.list_records(db, key, pid, limit=100000)
        if not recs:
            continue
        states = Counter(r["workflow_state"] for r in recs)
        by_module.append({"key": key, "name": mod["name"], "section": mod.get("section"),
                          "count": len(recs), "by_state": dict(states)})
        counts["total"] += len(recs)
        counts[f"open:{key}"] += sum(states[s] for s in states if s in open_states)
        for r in recs:
            if _overdue(r):
                overdue += 1
            acts = me.available_actions(mod, r["workflow_state"], party)
            # only count records that have an actionable, non-trivial next step for this party
            if acts and r["workflow_state"] in open_states:
                action_items.append({
                    "module": key, "module_name": mod["name"], "id": r["id"], "ref": r["ref"],
                    "title": r["title"], "state": r["workflow_state"],
                    "actions": [a["action"] for a in acts],
                })

    def open_count(key):
        return counts.get(f"open:{key}", 0)

    kpis = {
        "total_records": counts["total"],
        "my_action_items": len(action_items),
        "overdue": overdue,
        "open_rfis": open_count("rfi"),
        "pending_change_orders": open_count("cor"),
        "open_issues": open_count("issue") + open_count("coordination_issue"),
        "open_quality": open_count("ncr") + open_count("deficiency") + open_count("inspection"),
        "open_safety": open_count("incident") + open_count("observation"),
        "open_punchlist": open_count("punchlist"),
    }

    try:
        cost_snapshot = cost.summary(db, pid)
    except Exception:
        cost_snapshot = None

    by_module.sort(key=lambda m: (-m["count"], m["name"]))
    action_items.sort(key=lambda a: a["module"])
    return {"party": party or "GC", "kpis": kpis, "cost": cost_snapshot,
            "action_items": action_items[:100], "by_module": by_module}
