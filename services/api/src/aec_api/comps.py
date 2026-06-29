"""Comparables import — parse a CSV or a RESO Data Dictionary array of sold/leased comps into
`comparable` module records that feed the sales-comparison appraisal approach. Header mapping is
forgiving (case/space/underscore-insensitive) and covers both human CSV headers and RESO field names.
Pure parsing here; the router persists via modules.create_record."""
from __future__ import annotations

import csv
import io
from typing import Any

# normalized comparable field -> the source keys we accept (lower-cased, alnum-only)
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "address": ("address", "unparsedaddress", "streetaddress", "propertyaddress", "location"),
    "asset_type": ("assettype", "propertytype", "propertysubtype", "type"),
    "price": ("price", "saleprice", "closeprice", "soldprice", "lastsaleprice"),
    "price_psf": ("pricepsf", "pricepersf", "pricepersqft", "ppsf", "closepricepersquarefoot"),
    "cap_rate": ("caprate", "capitalizationrate", "caprateatsale"),
    "rent_psf": ("rentpsf", "rentpersf", "rentpersqft", "askingrentpsf"),
    "sale_date": ("saledate", "closedate", "closingdate", "settledate", "clos edate"),
    "notes": ("notes", "remarks", "publicremarks", "comments"),
}
_NUMERIC = ("price", "price_psf", "cap_rate", "rent_psf")


def _norm(key: str) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _num(v: Any) -> Any:
    """Coerce '$1,250,000' / '5.5%' to a float; leave blanks as None."""
    if v is None:
        return None
    s = str(v).strip().replace("$", "").replace(",", "").replace("%", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _map_row(raw: dict) -> dict[str, Any]:
    """Map one source row (dict keyed by arbitrary headers) to a comparable `data` dict."""
    by_norm = {_norm(k): v for k, v in raw.items()}
    out: dict[str, Any] = {}
    for field, aliases in _FIELD_ALIASES.items():
        for a in aliases:
            if a in by_norm and str(by_norm[a]).strip() != "":
                out[field] = by_norm[a]
                break
    for f in _NUMERIC:
        if f in out:
            n = _num(out[f])
            if n is None:
                out.pop(f)
            else:
                out[f] = n
    if out.get("sale_date"):
        out["sale_date"] = str(out["sale_date"])[:10]
    return out


def parse_csv(text: str) -> list[dict[str, Any]]:
    rows = list(csv.DictReader(io.StringIO(text)))
    return [m for m in (_map_row(r) for r in rows) if m.get("address")]


def parse_reso(records: list[dict]) -> list[dict[str, Any]]:
    return [m for m in (_map_row(r) for r in records) if m.get("address")]


def parse(body: dict) -> list[dict[str, Any]]:
    """Accept {csv: "..."} or {reso: [...]} (or {rows: [...]}) -> list of comparable data dicts."""
    if body.get("csv"):
        return parse_csv(str(body["csv"]))
    rows = body.get("reso") or body.get("rows")
    if isinstance(rows, list):
        return parse_reso(rows)
    return []
