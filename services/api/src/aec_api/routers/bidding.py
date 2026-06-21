"""Bidding endpoints (preconstruction): bid leveling — tabulate the bid_submission records by
their bid_package and compute low/high/avg/spread + flag the low bidder."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import modules as me
from ..db import get_db
from ..rbac import require_role

router = APIRouter()


def _amt(rec: dict) -> float | None:
    v = (rec.get("data") or {}).get("amount")
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


@router.get("/projects/{pid}/bids/leveling")
def leveling(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """Bid tabulation by package: each package's submissions, low/high/avg/spread, low-bidder flag."""
    packages = me.list_records(db, "bid_package", pid, limit=1_000_000)
    subs = me.list_records(db, "bid_submission", pid, limit=1_000_000)
    by_pkg: dict[str, list[dict]] = {}
    for s in subs:
        by_pkg.setdefault((s.get("data") or {}).get("package"), []).append(s)

    out = []
    for p in packages:
        sl = by_pkg.get(p["id"], [])
        amts = [a for a in (_amt(x) for x in sl) if a is not None]
        low = min(amts) if amts else None
        bids = [{"ref": x.get("ref"), "bidder": (x.get("data") or {}).get("bidder"),
                 "amount": _amt(x), "status": x.get("workflow_state"),
                 "is_low": low is not None and _amt(x) == low} for x in sl]
        out.append({"package": p.get("title") or p.get("ref"), "package_ref": p.get("ref"),
                    "bid_count": len(sl), "low": low, "high": max(amts) if amts else None,
                    "avg": round(sum(amts) / len(amts), 2) if amts else None,
                    "spread": round(max(amts) - low, 2) if len(amts) > 1 else 0.0,
                    "bids": sorted(bids, key=lambda b: (b["amount"] is None, b["amount"] or 0))})
    return {"packages": out, "package_count": len(packages), "bid_count": len(subs)}
