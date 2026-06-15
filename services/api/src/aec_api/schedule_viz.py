"""Schedule visuals (GC portal): Gantt chart for the activity schedule and an Empire State
Building-style Line-of-Balance (location/takt) chart. Reads `schedule_activity` records and
renders SVG."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from . import modules as me


def _d(v: Any) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _activities(db: Session, pid: str) -> list[dict]:
    out = []
    for r in me.list_records(db, "schedule_activity", pid, limit=100000) if "schedule_activity" in me.TABLES else []:
        d = r["data"]
        s, f = _d(d.get("start")), _d(d.get("finish"))
        if not s or not f or f < s:
            continue
        out.append({"name": d.get("name") or r["ref"], "wbs": d.get("wbs"),
                    "location": d.get("location"), "start": s, "finish": f,
                    "percent": float(d.get("percent") or 0)})
    return out


def _axis(d0: date, d1: date, x0: float, x1: float):
    span = max((d1 - d0).days, 1)
    return lambda d: x0 + (d - d0).days / span * (x1 - x0)


def _empty(msg: str, width=900) -> str:
    return (f'<?xml version="1.0" encoding="UTF-8"?><svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="120"><rect width="{width}" height="120" fill="#fff"/>'
            f'<text x="20" y="60" font-family="sans-serif" font-size="14">{msg}</text></svg>')


def _month_grid(out, d0, d1, X, top, bottom):
    cur = date(d0.year, d0.month, 1)
    while cur <= d1:
        x = X(cur)
        out.append(f'<line x1="{x:.0f}" y1="{top}" x2="{x:.0f}" y2="{bottom}" stroke="#eee" stroke-width="1"/>')
        out.append(f'<text x="{x+3:.0f}" y="{top-4}" font-family="sans-serif" font-size="9" '
                   f'fill="#999">{cur.strftime("%b %y")}</text>')
        cur = date(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1)


def gantt_svg(db: Session, pid: str, width: int = 1000) -> str:
    acts = sorted(_activities(db, pid), key=lambda a: a["start"])
    if not acts:
        return _empty("No schedule activities. Add them in the Schedule module.")
    d0 = min(a["start"] for a in acts)
    d1 = max(a["finish"] for a in acts)
    label_w, pad, row_h, top = 220, 20, 22, 40
    X = _axis(d0, d1, label_w, width - pad)
    height = top + len(acts) * row_h + 30
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
           f'<rect width="{width}" height="{height}" fill="#fff"/>',
           f'<text x="{pad}" y="22" font-family="sans-serif" font-size="15" font-weight="700">SCHEDULE — GANTT</text>']
    _month_grid(out, d0, d1, X, top, height - 24)
    today = date.today()
    if d0 <= today <= d1:
        tx = X(today)
        out.append(f'<line x1="{tx:.0f}" y1="{top}" x2="{tx:.0f}" y2="{height-24}" stroke="#e0457b" stroke-width="1" stroke-dasharray="4 3"/>')
    for i, a in enumerate(acts):
        y = top + i * row_h
        x1, x2 = X(a["start"]), X(a["finish"])
        out.append(f'<text x="{pad}" y="{y+15:.0f}" font-family="sans-serif" font-size="11">{(a["name"] or "")[:34]}</text>')
        out.append(f'<rect x="{x1:.0f}" y="{y+4:.0f}" width="{max(x2-x1,2):.0f}" height="13" rx="2" fill="#cdd6e4"/>')
        if a["percent"] > 0:
            out.append(f'<rect x="{x1:.0f}" y="{y+4:.0f}" width="{max((x2-x1)*a["percent"]/100,1):.0f}" height="13" rx="2" fill="#4a8cff"/>')
        out.append(f'<text x="{x2+4:.0f}" y="{y+15:.0f}" font-family="sans-serif" font-size="9" fill="#888">{a["percent"]:.0f}%</text>')
    out.append("</svg>")
    return "".join(out)


def lob_svg(db: Session, pid: str, width: int = 1000) -> str:
    """Line-of-Balance: x=time, y=location; one production line per task across locations."""
    acts = _activities(db, pid)
    located = [a for a in acts if a["location"]]
    if not located:
        return _empty("No located activities. Set a Location on schedule activities for LoB.")
    locations = sorted({a["location"] for a in located})
    loc_idx = {loc: i for i, loc in enumerate(locations)}
    d0 = min(a["start"] for a in located)
    d1 = max(a["finish"] for a in located)
    pad_l, pad, top = 160, 20, 40
    plot_top, plot_bottom = top, top + len(locations) * 40
    X = _axis(d0, d1, pad_l, width - pad)
    height = plot_bottom + 60

    def Y(loc):
        return plot_bottom - (loc_idx[loc] + 0.5) / len(locations) * (plot_bottom - plot_top)

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
           f'<rect width="{width}" height="{height}" fill="#fff"/>',
           f'<text x="{pad}" y="22" font-family="sans-serif" font-size="15" font-weight="700">LINE OF BALANCE</text>']
    _month_grid(out, d0, d1, X, plot_top, plot_bottom)
    for loc in locations:
        y = Y(loc)
        out.append(f'<line x1="{pad_l}" y1="{y:.0f}" x2="{width-pad}" y2="{y:.0f}" stroke="#f0f0f0"/>')
        out.append(f'<text x="{pad}" y="{y+3:.0f}" font-family="sans-serif" font-size="10">{loc[:22]}</text>')
    palette = ["#4a8cff", "#e0457b", "#0a8f5b", "#ff8c00", "#8e44ad", "#16a3b8"]
    tasks: dict[str, list[dict]] = {}
    for a in located:
        tasks.setdefault(a["name"], []).append(a)
    for ti, (name, items) in enumerate(sorted(tasks.items())):
        items = sorted(items, key=lambda a: loc_idx[a["location"]])
        col = palette[ti % len(palette)]
        starts = " ".join(f"{X(a['start']):.0f},{Y(a['location']):.0f}" for a in items)
        finishes = " ".join(f"{X(a['finish']):.0f},{Y(a['location']):.0f}" for a in items)
        out.append(f'<polyline points="{starts}" fill="none" stroke="{col}" stroke-width="2"/>')
        out.append(f'<polyline points="{finishes}" fill="none" stroke="{col}" stroke-width="2" stroke-dasharray="4 3"/>')
        first = items[0]
        out.append(f'<text x="{X(first["start"]):.0f}" y="{Y(first["location"])-6:.0f}" '
                   f'font-family="sans-serif" font-size="10" fill="{col}" font-weight="600">{name[:18]}</text>')
    out.append("</svg>")
    return "".join(out)
