"""GC portal module endpoints — config-driven CRUD + role-gated workflow + model pins.

One set of routes serves every module (RFIs, Submittals, the change-order chain, …). The
acting user's *party role* gates workflow transitions; the *capability role* gates writes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from .. import modules as mod_engine
from .. import rbac
from ..db import get_db
from ..models import Project
from ..rbac import current_user, require_role

router = APIRouter()


def _party(pid: str, db: Session, user: str) -> str | None:
    return rbac.party_role_for(db, pid, user)


@router.get("/modules")
def list_modules():
    """Module catalog (drives dynamic UI). Returns each module.json."""
    return [
        {"key": m["key"], "name": m["name"], "section": m.get("section"),
         "icon": m.get("icon"), "pinnable": m.get("pinnable", False),
         "fields": m.get("fields", []), "workflow": m.get("workflow", {}),
         "relations": m.get("relations", []), "list_columns": m.get("list_columns")}
        for m in mod_engine.REGISTRY.values()
    ]


@router.get("/projects/{pid}/my-work")
def my_work(pid: str, db: Session = Depends(get_db), user: str = Depends(current_user)):
    """Cross-module work queue for the current user (assigned + ball-in-court)."""
    return mod_engine.my_work(db, pid, user, _party(pid, db, user))


@router.get("/projects/{pid}/notifications")
def notifications(pid: str, db: Session = Depends(get_db), user: str = Depends(current_user)):
    """Recent activity relevant to the caller (assigned / ball-in-court), newest first."""
    return mod_engine.notifications(db, pid, user, _party(pid, db, user))


@router.get("/projects/{pid}/search")
def search(pid: str, q: str, limit: int = 50, db: Session = Depends(get_db),
           _: str = Depends(require_role("viewer"))):
    """Cross-module full-text search (ref / title / field data)."""
    return mod_engine.search_all(db, pid, q, limit)


@router.post("/projects/{pid}/modules/{key}/bulk")
def bulk_action(pid: str, key: str, ids: list[str] = Body(..., embed=True),
                action: str = Body(..., embed=True), value: str | None = Body(None, embed=True),
                db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    """Apply transition / assign / delete to many records at once."""
    return mod_engine.bulk(db, key, pid, ids, action, user, _party(pid, db, user), value)


@router.get("/projects/{pid}/modules/{key}")
def list_records(pid: str, key: str, state: str | None = None, q: str | None = None,
                 limit: int = 200, offset: int = 0, db: Session = Depends(get_db),
                 _: str = Depends(require_role("viewer"))):
    return mod_engine.list_records(db, key, pid, state, q, limit, offset)


@router.post("/projects/{pid}/modules/{key}", status_code=201)
def create_record(pid: str, key: str, body: dict = Body(...), db: Session = Depends(get_db),
                  user: str = Depends(require_role("reviewer"))):
    return mod_engine.create_record(db, key, pid, body, user, _party(pid, db, user))


@router.get("/projects/{pid}/modules/{key}/export.csv")
def export_csv(pid: str, key: str, db: Session = Depends(get_db),
               _: str = Depends(require_role("viewer"))):
    csv_text = mod_engine.to_csv(db, key, pid)
    return Response(csv_text, media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{key}.csv"'})


# NOTE: must precede the /{rid} route so "board" isn't captured as a record id.
@router.get("/projects/{pid}/modules/{key}/board")
def module_board(pid: str, key: str, db: Session = Depends(get_db),
                 _: str = Depends(require_role("viewer"))):
    """Records grouped by workflow state — kanban board."""
    return mod_engine.board(db, key, pid)


@router.get("/projects/{pid}/modules/{key}/{rid}")
def get_record(pid: str, key: str, rid: str, db: Session = Depends(get_db),
               _: str = Depends(require_role("viewer"))):
    rec = mod_engine.get_record(db, key, pid, rid)
    mod = mod_engine.get_module(key)
    rec["available_actions"] = mod_engine.available_actions(
        mod, rec["workflow_state"], _party(pid, db, _))
    return rec


@router.patch("/projects/{pid}/modules/{key}/{rid}")
def update_record(pid: str, key: str, rid: str, data: dict = Body(...),
                  db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    return mod_engine.update_record(db, key, pid, rid, data, user, _party(pid, db, user))


@router.delete("/projects/{pid}/modules/{key}/{rid}")
def delete_record(pid: str, key: str, rid: str, db: Session = Depends(get_db),
                  user: str = Depends(require_role("editor"))):
    """Delete a record (editor+). Removes its activity/comments too."""
    return mod_engine.delete_record(db, key, pid, rid, user, _party(pid, db, user))


@router.get("/projects/{pid}/modules/{key}/{rid}/related")
def related_records(pid: str, key: str, rid: str, db: Session = Depends(get_db),
                    _: str = Depends(require_role("viewer"))):
    """Outgoing references + incoming records that point at this one."""
    return mod_engine.related_records(db, key, pid, rid)


@router.post("/projects/{pid}/modules/{key}/{rid}/transition")
def transition(pid: str, key: str, rid: str, action: str = Body(..., embed=True),
               note: str | None = Body(default=None, embed=True),
               db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    return mod_engine.transition(db, key, pid, rid, action, user, _party(pid, db, user), note)


@router.post("/projects/{pid}/modules/{key}/{rid}/link")
def link_record(pid: str, key: str, rid: str, target: dict = Body(...),
                db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    return mod_engine.link_record(db, key, pid, rid, target, user, _party(pid, db, user))


@router.post("/projects/{pid}/modules/{key}/{rid}/comments", status_code=201)
def add_comment(pid: str, key: str, rid: str, text: str = Body(..., embed=True),
                db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    return mod_engine.add_comment(db, key, pid, rid, text, user)


@router.post("/projects/{pid}/modules/{key}/{rid}/assign")
def assign_record(pid: str, key: str, rid: str, assignee: str | None = Body(None, embed=True),
                  db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    """Set (or clear) the record's assignee — drives the cross-module work queue."""
    return mod_engine.set_assignee(db, key, pid, rid, assignee, user, _party(pid, db, user))


@router.post("/projects/{pid}/modules/{key}/{rid}/attachments", status_code=201)
async def upload_attachment(pid: str, key: str, rid: str, file: UploadFile = File(...),
                            db: Session = Depends(get_db), user: str = Depends(require_role("reviewer"))):
    """Attach a file to a record (stored in object storage / MinIO)."""
    data = await file.read()
    return mod_engine.add_attachment(db, key, pid, rid, file.filename or "file",
                                     file.content_type, data, user)


@router.get("/attachments/{att_id}/download")
def download_attachment(att_id: str, db: Session = Depends(get_db),
                        _: str = Depends(require_role("viewer"))):
    att, data = mod_engine.get_attachment(db, att_id)
    return Response(data, media_type=att.content_type or "application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{att.filename}"'})


@router.get("/projects/{pid}/modules/{key}/{rid}/pdf")
def record_pdf(pid: str, key: str, rid: str, db: Session = Depends(get_db),
               _: str = Depends(require_role("viewer"))):
    import io

    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    mod = mod_engine.get_module(key)
    r = mod_engine.get_record(db, key, pid, rid)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, h - 50, f"{mod['name']} — {r['ref']}")
    c.setFont("Helvetica", 10)
    c.drawString(40, h - 68, f"Status: {r['workflow_state']}    Party: {r['party_owner'] or '-'}    By: {r['created_by'] or '-'}")
    y = h - 100
    for f in mod.get("fields", []):
        v = r["data"].get(f["name"])
        if v in (None, ""):
            continue
        c.setFont("Helvetica-Bold", 10); c.drawString(40, y, f"{f['label']}:")
        c.setFont("Helvetica", 10)
        for i, line in enumerate(str(v)[:600].split("\n")):
            c.drawString(170, y - i * 13, line[:70])
            y -= 13 if i else 0
        y -= 16
        if y < 80:
            c.showPage(); y = h - 60
    if r.get("activity"):
        c.setFont("Helvetica-Bold", 11); c.drawString(40, y - 6, "Activity"); y -= 22
        c.setFont("Helvetica", 9)
        for a in r["activity"]:
            c.drawString(50, y, f"{(a['ts'] or '')[:16]}  {a['actor'] or ''}  {a['action']}")
            y -= 12
            if y < 60:
                c.showPage(); y = h - 60
    c.showPage(); c.save()
    return Response(buf.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{r["ref"]}.pdf"'})


@router.get("/projects/{pid}/module-pins")
def module_pins(pid: str, db: Session = Depends(get_db), _: str = Depends(require_role("viewer"))):
    """Every anchored GC record across pinnable modules — for the 3D viewer overlay."""
    return mod_engine.project_pins(db, pid)
