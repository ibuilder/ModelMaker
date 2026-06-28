"""Serves the Phase 1 properties index (geometry stays in .frag, data comes from here).
Selection in the viewer raycasts to a GUID, then fetches Psets from these endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Body, Depends, HTTPException, UploadFile, File

from .. import ai, storage
from ..rbac import require_role

router = APIRouter()

# project_id -> { guid -> element record }  (loaded from uploaded props.json)
_INDEX: dict[str, dict[str, dict]] = {}
_META: dict[str, dict] = {}


def _load(pid: str, payload: dict) -> int:
    _META[pid] = {k: payload.get(k) for k in ("schema", "project", "counts", "facets")}
    _INDEX[pid] = {e["guid"]: e for e in payload.get("elements", [])}
    return len(_INDEX[pid])


@router.post("/projects/{pid}/properties/index")
async def upload_index(pid: str, file: UploadFile = File(...), _: str = Depends(require_role("editor"))):
    """Upload the props.json produced by the data service (`aec_data.cli index`)."""
    payload = json.loads(await file.read())
    storage.put(f"{pid}/props.json", json.dumps(payload).encode("utf-8"))
    n = _load(pid, payload)
    return {"loaded": n, "meta": _META[pid]}


def _ensure_loaded(pid: str) -> None:
    if pid in _INDEX:
        return
    key = f"{pid}/props.json"
    if storage.exists(key):
        _load(pid, json.loads(storage.get(key)))


@router.get("/projects/{pid}/properties/meta")
def meta(pid: str, _: str = Depends(require_role("viewer"))):
    _ensure_loaded(pid)
    if pid not in _META:
        raise HTTPException(404, "no properties index for project")
    return _META[pid]


@router.get("/projects/{pid}/elements")
def list_elements(pid: str, ifc_class: str | None = None, storey: str | None = None, limit: int = 500,
                  _: str = Depends(require_role("viewer"))):
    _ensure_loaded(pid)
    if pid not in _INDEX:
        raise HTTPException(404, "no properties index for project")
    out = []
    for e in _INDEX[pid].values():
        if ifc_class and e["ifc_class"] != ifc_class:
            continue
        if storey and e["storey"] != storey:
            continue
        out.append(e)
        if len(out) >= limit:
            break
    return out


@router.get("/projects/{pid}/elements/{guid}")
def element(pid: str, guid: str, _: str = Depends(require_role("viewer"))):
    _ensure_loaded(pid)
    rec = _INDEX.get(pid, {}).get(guid)
    if not rec:
        raise HTTPException(404, "element not found")
    return rec


def _model_snapshot(pid: str) -> dict:
    """A compact, grounded summary of the model's data for the AI assistant (or for direct display
    when AI is off): element total, counts by class + storey, the property sets present, and the
    indexer's precomputed counts/facets."""
    idx = _INDEX.get(pid, {})
    by_class: dict[str, int] = {}
    by_storey: dict[str, int] = {}
    pset_keys: set[str] = set()
    for e in idx.values():
        by_class[e.get("ifc_class", "?")] = by_class.get(e.get("ifc_class", "?"), 0) + 1
        st = e.get("storey") or "(unassigned)"
        by_storey[st] = by_storey.get(st, 0) + 1
        psets = e.get("psets") or e.get("properties") or {}
        if isinstance(psets, dict):
            pset_keys.update(psets.keys())
    meta = _META.get(pid, {})
    return {
        "project": meta.get("project"),
        "total_elements": len(idx),
        "counts_by_class": dict(sorted(by_class.items(), key=lambda x: -x[1])[:40]),
        "counts_by_storey": by_storey,
        "property_sets": sorted(pset_keys)[:60],
        "indexer_counts": meta.get("counts"),
        "facets": meta.get("facets"),
    }


@router.post("/projects/{pid}/ask")
def ask_model(pid: str, body: dict = Body(...), _: str = Depends(require_role("viewer"))):
    """Ask a plain-English question about the model. Grounds the answer in a snapshot of the property
    index (counts by class/storey, Psets, facets); uses the configured AI provider, and degrades to
    returning the snapshot itself when no AI key is set (so the data is still useful offline)."""
    _ensure_loaded(pid)
    if pid not in _INDEX:
        raise HTTPException(404, "no properties index for project — upload one first")
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(422, "question required")
    return ai.ask(question, _model_snapshot(pid))
