"""Clash detection (Navisworks Clash Detective / Bonsai native parity).

Broad-phase AABB clash: bakes world-space geometry once via the IfcOpenShell iterator,
computes an axis-aligned bounding box per element, then finds overlapping boxes between two
element groups (by IFC class). Reports overlap volume as a penetration proxy.

This is the fast broad phase (what most quick-clash passes do). A mesh-triangle narrow
phase (true hard clash) is a follow-up — the per-element vertices are already available here.
"""
from __future__ import annotations

import multiprocessing
from dataclasses import dataclass
from typing import Any

import ifcopenshell
import ifcopenshell.geom as geom
import numpy as np

from .ifc_loader import open_model


@dataclass
class ElementBox:
    guid: str
    ifc_class: str
    name: str | None
    min: np.ndarray  # (3,)
    max: np.ndarray  # (3,)


def _compute_boxes(model: ifcopenshell.file) -> list[ElementBox]:
    settings = geom.settings()
    boxes: list[ElementBox] = []
    it = geom.iterator(settings, model, max(1, multiprocessing.cpu_count() - 1))
    if not it.initialize():
        return boxes
    while True:
        shape = it.get()
        verts = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
        if verts.size:
            el = model.by_guid(shape.guid)
            boxes.append(ElementBox(
                guid=shape.guid,
                ifc_class=el.is_a() if el else shape.type,
                name=getattr(el, "Name", None) if el else None,
                min=verts.min(axis=0),
                max=verts.max(axis=0),
            ))
        if not it.next():
            break
    return boxes


def _overlap_volume(a: ElementBox, b: ElementBox) -> float:
    lo = np.maximum(a.min, b.min)
    hi = np.minimum(a.max, b.max)
    d = hi - lo
    if np.any(d <= 0):
        return 0.0
    return float(d[0] * d[1] * d[2])


def detect(
    model: ifcopenshell.file,
    group_a: list[str] | None = None,
    group_b: list[str] | None = None,
    min_volume: float = 1e-4,
    tolerance: float = 0.0,
) -> list[dict[str, Any]]:
    """Find AABB clashes between two IFC-class groups.

    group_a / group_b: lists of IFC classes; None = everything. tolerance shrinks the boxes
    so only real interpenetration (not mere touching) is reported.
    """
    boxes = _compute_boxes(model)
    if tolerance:
        for bx in boxes:
            bx.min = bx.min + tolerance
            bx.max = bx.max - tolerance

    def pick(group: list[str] | None) -> list[ElementBox]:
        if not group:
            return boxes
        s = {g.lower() for g in group}
        return [b for b in boxes if b.ifc_class.lower() in s]

    A, B = pick(group_a), pick(group_b)
    if not A or not B:
        return []

    mins_a = np.array([b.min for b in A]); maxs_a = np.array([b.max for b in A])
    mins_b = np.array([b.min for b in B]); maxs_b = np.array([b.max for b in B])
    # vectorized broad-phase overlap test
    overlap = (
        (mins_a[:, None, :] <= maxs_b[None, :, :]).all(axis=2)
        & (maxs_a[:, None, :] >= mins_b[None, :, :]).all(axis=2)
    )
    ia, ib = np.where(overlap)

    clashes: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for i, j in zip(ia.tolist(), ib.tolist()):
        a, b = A[i], B[j]
        if a.guid == b.guid:
            continue
        key = tuple(sorted((a.guid, b.guid)))
        if key in seen:
            continue
        seen.add(key)
        vol = _overlap_volume(a, b)
        if vol < min_volume:
            continue
        center = ((np.maximum(a.min, b.min) + np.minimum(a.max, b.max)) / 2).tolist()
        clashes.append({
            "a_guid": a.guid, "a_class": a.ifc_class, "a_name": a.name,
            "b_guid": b.guid, "b_class": b.ifc_class, "b_name": b.name,
            "overlap_volume": round(vol, 6),
            "point": {"x": center[0], "y": center[1], "z": center[2]},
        })
    clashes.sort(key=lambda c: c["overlap_volume"], reverse=True)
    return clashes


def detect_file(ifc_path: str, group_a=None, group_b=None, min_volume=1e-4, tolerance=0.0):
    return detect(open_model(ifc_path), group_a, group_b, min_volume, tolerance)
