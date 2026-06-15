"""Data-export endpoints (guide §8) — bridges the API to the IfcOpenShell data service.
Reads the project's registered source IFC and streams XLSX. Keyed by GUID throughout."""
from __future__ import annotations

import io
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import source_ifc_path as _source_ifc

# make the monorepo data package importable in dev (services/data/src)
_DATA_SRC = Path(__file__).resolve().parents[4] / "data" / "src"
if str(_DATA_SRC) not in sys.path:
    sys.path.insert(0, str(_DATA_SRC))

router = APIRouter()


def _xlsx_response(sheets: dict, filename: str) -> Response:
    from aec_data.xlsx import write_sheets  # type: ignore

    buf_path = io.BytesIO()
    # write_sheets writes to a path; use a temp file then read back
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        write_sheets(tmp.name, sheets)
        data = Path(tmp.name).read_bytes()
    Path(tmp.name).unlink(missing_ok=True)
    buf_path.write(data)
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _rows_to_sheet(rows: list[dict]):
    headers = list(rows[0].keys()) if rows else []
    return headers, [[r.get(h) for h in headers] for r in rows]


@router.get("/projects/{pid}/exports/qto.xlsx")
def export_qto(pid: str, db: Session = Depends(get_db)):
    from aec_data import qto  # type: ignore

    rows = qto.takeoff_file(_source_ifc(db, pid))
    return _xlsx_response({"QTO": _rows_to_sheet(rows)}, "qto.xlsx")


@router.get("/projects/{pid}/exports/cobie.xlsx")
def export_cobie(pid: str, db: Session = Depends(get_db)):
    from aec_data import cobie  # type: ignore

    sheets = cobie.cobie_file(_source_ifc(db, pid))
    return _xlsx_response({k: _rows_to_sheet(v) for k, v in sheets.items()}, "cobie.xlsx")


@router.get("/projects/{pid}/exports/spaces.xlsx")
def export_spaces(pid: str, db: Session = Depends(get_db)):
    from aec_data import spaces  # type: ignore

    rows = spaces.space_schedule_file(_source_ifc(db, pid))
    return _xlsx_response({"Spaces": _rows_to_sheet(rows)}, "spaces.xlsx")


@router.get("/projects/{pid}/exports/schedule.xlsx")
def export_schedule(pid: str, db: Session = Depends(get_db)):
    from aec_data import schedule  # type: ignore

    acts = schedule.schedule_file(_source_ifc(db, pid))
    import json as _json

    rows = [{"id": a["id"], "name": a["name"], "start": a["start"], "finish": a["finish"],
             "element_count": len(a["guids"]), "guids": _json.dumps(a["guids"])} for a in acts]
    return _xlsx_response({"Schedule": _rows_to_sheet(rows)}, "schedule.xlsx")
