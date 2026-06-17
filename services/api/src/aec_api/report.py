"""Project status report (PDF) — a one-document executive snapshot aggregating the cross-module
dashboard (KPIs, cost, open items by module, ball-in-court). Built with reportlab (already a dep)."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session


def _money(v: Any) -> str:
    try:
        return f"${float(v):,.0f}"
    except (TypeError, ValueError):
        return "-"


def project_status_pdf(db: Session, pid: str, project_name: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    from . import dashboard

    d = dashboard.build(db, pid, "GC")          # GC party = whole-project view
    kp = d.get("kpis", {})
    cost = d.get("cost")
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter
    margin = 40
    y = h - 50

    def newpage():
        nonlocal y
        c.showPage()
        y = h - 50

    def heading(text: str):
        nonlocal y
        if y < 90:
            newpage()
        c.setFont("Helvetica-Bold", 13)
        c.drawString(margin, y, text)
        y -= 6
        c.setStrokeColor(colors.grey); c.line(margin, y, w - margin, y); c.setStrokeColor(colors.black)
        y -= 16

    def row(label: str, value: str, indent: int = 0):
        nonlocal y
        if y < 60:
            newpage()
        c.setFont("Helvetica", 10)
        c.drawString(margin + indent, y, label)
        c.drawRightString(w - margin, y, value)
        y -= 15

    # --- title block ---
    c.setFont("Helvetica-Bold", 18); c.drawString(margin, y, "Project Status Report"); y -= 22
    c.setFont("Helvetica", 11); c.drawString(margin, y, project_name or pid)
    c.drawRightString(w - margin, y, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")); y -= 8
    c.setStrokeColor(colors.black); c.line(margin, y, w - margin, y); y -= 24

    # --- KPIs ---
    heading("Summary")
    row("Total records", str(kp.get("total_records", 0)))
    row("Overdue items", str(kp.get("overdue", 0)))
    row("Open RFIs", str(kp.get("open_rfis", 0)))
    row("Pending change orders", str(kp.get("pending_change_orders", 0)))
    row("Open coordination/issues", str(kp.get("open_issues", 0)))
    row("Open quality (NCR/deficiency/insp.)", str(kp.get("open_quality", 0)))
    row("Open safety", str(kp.get("open_safety", 0)))
    row("Open punchlist", str(kp.get("open_punchlist", 0)))
    y -= 10

    # --- cost snapshot ---
    if cost:
        heading("Cost snapshot")
        row("Revised budget", _money(cost.get("budget")))
        row("Committed", _money(cost.get("committed")))
        row("Actual to date", _money(cost.get("actual")))
        row("Forecast at completion", _money(cost.get("forecast")))
        if cost.get("projected_over_under") is not None:
            row("Projected over / (under)", _money(cost.get("projected_over_under")))
        y -= 10

    # --- open items by module ---
    heading("Open items by module")
    by_module = [m for m in d.get("by_module", []) if m.get("count")]
    for m in by_module[:30]:
        states = m.get("by_state", {})
        detail = ", ".join(f"{n} {s}" for s, n in sorted(states.items(), key=lambda kv: -kv[1])[:4])
        row(f"{m['name']} ({m['count']})", detail or "-")
    y -= 10

    # --- ball-in-court action items ---
    actions = d.get("action_items", [])
    heading(f"Action items — ball in court ({len(actions)})")
    if not actions:
        row("None outstanding", "")
    for a in actions[:25]:
        row(f"{a['ref']} — {(a.get('title') or '')[:48]}", a.get("state", ""), indent=8)

    c.setFont("Helvetica-Oblique", 8)
    c.drawString(margin, 30, "AEC BIM Platform — generated from live project data")
    c.showPage()
    c.save()
    return buf.getvalue()
