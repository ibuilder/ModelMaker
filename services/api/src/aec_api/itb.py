"""Invitation-to-bid (ITB) tracking — rolls up bid packages vs the submissions received: who was
invited, who responded, who provided a bid bond, the low bid, and coverage gaps (packages with no
bids). Complements bid leveling (the compare) with the outbound/solicitation side. Pure over dicts."""
from __future__ import annotations

from typing import Any


def _num(v: Any) -> float | None:
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "y", "provided")


def summarize(packages: list[dict], submissions: list[dict]) -> dict[str, Any]:
    """packages: bid_package records; submissions: bid_submission records. Matches submissions to a
    package by the submission's `package` field == the package name or ref."""
    subs_by_pkg: dict[str, list[dict]] = {}
    for s in submissions:
        d = s.get("data") or s
        key = str(d.get("package") or "").strip().lower()
        subs_by_pkg.setdefault(key, []).append(d)
    rows = []
    total_invited = total_responses = total_bonded = no_bid_pkgs = 0
    for p in packages:
        d = p.get("data") or p
        name = d.get("name") or p.get("ref") or ""
        invited_list = d.get("invited_companies") or []
        invited = len(invited_list) if invited_list else int(_num(d.get("bidders_invited")) or 0)
        subs = subs_by_pkg.get(name.strip().lower(), []) + subs_by_pkg.get(str(p.get("ref") or "").lower(), [])
        responses = len(subs)
        bonded = sum(1 for s in subs if _truthy(s.get("bond_provided")))
        amts = [a for s in subs if (a := _num(s.get("amount") or s.get("base_bid"))) is not None]
        low = min(amts) if amts else None
        total_invited += invited
        total_responses += responses
        total_bonded += bonded
        if responses == 0:
            no_bid_pkgs += 1
        rows.append({
            "ref": p.get("ref"), "package": name, "trade": d.get("trade"),
            "budget": _num(d.get("budget")), "invited": invited, "responses": responses,
            "bonded": bonded, "low_bid": low, "due_date": d.get("due_date"),
            "response_rate": round(100 * responses / invited, 1) if invited else 0.0,
            "coverage": "no bids" if responses == 0 else ("covered" if responses >= 3 else "thin"),
        })
    return {
        "package_count": len(packages),
        "total_invited": total_invited,
        "total_responses": total_responses,
        "total_bonded": total_bonded,
        "packages_without_bids": no_bid_pkgs,
        "overall_response_rate": round(100 * total_responses / total_invited, 1) if total_invited else 0.0,
        "rows": sorted(rows, key=lambda r: (r["coverage"] != "no bids", r["package"])),
    }


def itb(db, pid: str) -> dict[str, Any]:
    from . import modules as me
    pkgs = me.list_records(db, "bid_package", pid, limit=100000) if "bid_package" in me.TABLES else []
    subs = me.list_records(db, "bid_submission", pid, limit=100000) if "bid_submission" in me.TABLES else []
    return summarize(pkgs, subs)
