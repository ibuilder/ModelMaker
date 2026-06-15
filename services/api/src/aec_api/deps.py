"""Shared FastAPI dependencies / helpers used across routers (DRY)."""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Project


def get_project(db: Session, pid: str) -> Project:
    p = db.get(Project, pid)
    if not p:
        raise HTTPException(404, "project not found")
    return p


def source_ifc_path(db: Session, pid: str) -> str:
    """Path to the project's source IFC, or 409 if not set/accessible."""
    p = get_project(db, pid)
    if not p.source_ifc or not Path(p.source_ifc).exists():
        raise HTTPException(409, "project has no accessible source IFC (set project.source_ifc)")
    return p.source_ifc
