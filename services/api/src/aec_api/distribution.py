"""Distribution lists — resolve a record's `distribution` field (comma/semicolon/newline-separated
names or emails) against the Company/Contact directory into recipients with emails. Used to CC the
right people when an RFI/submittal transitions, and to address a transmittal. Pure resolver + a
DB-backed convenience."""
from __future__ import annotations

import re
from typing import Any


def resolve(contacts: list[dict], raw: Any) -> list[dict]:
    """Parse `raw` into recipients; match name tokens to directory contacts (by name) for their email.
    Returns [{name, email, resolved}] de-duplicated, order-preserving."""
    by_name: dict[str, str] = {}
    for c in contacts:
        d = c.get("data") or c
        nm = (d.get("name") or "").strip().lower()
        if nm and d.get("email"):
            by_name[nm] = d["email"]
    out, seen = [], set()
    for tok in re.split(r"[,;\n]+", str(raw or "")):
        t = tok.strip()
        if not t:
            continue
        if "@" in t:
            name, email = t, t
        else:
            name, email = t, by_name.get(t.lower())
        key = (name.lower(), (email or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "email": email, "resolved": bool(email)})
    return out


def emails(recipients: list[dict]) -> list[str]:
    return [r["email"] for r in recipients if r.get("email")]


def for_record(db, pid: str, key: str, rid: str) -> dict[str, Any]:
    from . import modules as me
    rec = me.get_record(db, key, pid, rid)
    raw = (rec.get("data") or {}).get("distribution")
    contacts = me.list_records(db, "contact", pid, limit=100000) if "contact" in me.TABLES else []
    recipients = resolve(contacts, raw)
    return {"ref": rec.get("ref"), "recipients": recipients, "emails": emails(recipients)}


def record_emails(db, pid: str, key: str, data: dict | None) -> list[str]:
    """Resolved distribution emails for a record's data dict (no extra fetch of the record)."""
    from . import modules as me
    raw = (data or {}).get("distribution")
    if not raw:
        return []
    contacts = me.list_records(db, "contact", pid, limit=100000) if "contact" in me.TABLES else []
    return emails(resolve(contacts, raw))
