"""2D documentation — plan & section generation (Revit-style sheets, openBIM way).

Cuts the model geometry with a plane (trimesh section) and renders the cut polylines to
SVG. Plans are horizontal cuts at a storey height; sections are vertical cuts. Output is
plain SVG so it embeds in the viewer, prints, or drops onto a sheet with a title block.
"""
from __future__ import annotations

import multiprocessing
import warnings
from typing import Any

import ifcopenshell
import ifcopenshell.geom as geom
import ifcopenshell.util.unit as uunit
import numpy as np
import trimesh

from .ifc_loader import open_model

warnings.filterwarnings("ignore")

# (normal, kept-axes) for each view kind
_VIEWS = {
    "plan": (np.array([0.0, 0.0, 1.0]), (0, 1)),   # cut at Z, draw X/Y
    "section-x": (np.array([1.0, 0.0, 0.0]), (1, 2)),  # cut at X, draw Y/Z
    "section-y": (np.array([0.0, 1.0, 0.0]), (0, 2)),  # cut at Y, draw X/Z
}


def storey_elevations(model: ifcopenshell.file) -> list[dict[str, Any]]:
    """Storey elevations in METERS (iterator geometry is SI meters; the IfcBuildingStorey
    Elevation attribute is in the file's length unit, e.g. mm)."""
    scale = uunit.calculate_unit_scale(model)  # file unit -> meters
    out = []
    for s in model.by_type("IfcBuildingStorey"):
        elev = float(getattr(s, "Elevation", 0.0) or 0.0) * scale
        out.append({"name": s.Name, "elevation": elev})
    return sorted(out, key=lambda x: x["elevation"])


def cut(model: ifcopenshell.file, view: str, offset: float,
        classes: list[str] | None = None) -> list[np.ndarray]:
    """Return cut polylines as a list of (n,2) arrays in the view's drawing plane."""
    normal, axes = _VIEWS[view]
    origin = normal * offset
    want = {c.lower() for c in classes} if classes else None

    settings = geom.settings()
    it = geom.iterator(settings, model, max(1, multiprocessing.cpu_count() - 1))
    polylines: list[np.ndarray] = []
    if not it.initialize():
        return polylines
    while True:
        shape = it.get()
        el = model.by_guid(shape.guid)
        if want and (not el or el.is_a().lower() not in want):
            if not it.next():
                break
            continue
        verts = np.asarray(shape.geometry.verts, dtype=float).reshape(-1, 3)
        faces = np.asarray(shape.geometry.faces, dtype=np.int64).reshape(-1, 3)
        if verts.size and faces.size:
            try:
                mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
                sec = mesh.section(plane_origin=origin, plane_normal=normal)
                if sec is not None:
                    for poly in sec.discrete:
                        polylines.append(np.asarray(poly)[:, axes])
            except Exception:
                pass
        if not it.next():
            break
    return polylines


def to_svg(polylines: list[np.ndarray], title: str = "", subtitle: str = "",
           width: int = 1100, pad: int = 40) -> str:
    if not polylines:
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="200">' \
               f'<text x="20" y="40" font-family="sans-serif">No geometry on this cut.</text></svg>'
    allpts = np.vstack(polylines)
    mn, mx = allpts.min(axis=0), allpts.max(axis=0)
    span = np.maximum(mx - mn, 1e-6)
    scale = (width - 2 * pad) / span[0]
    height = int(span[1] * scale + 2 * pad + 60)
    draw_h = span[1] * scale

    def tx(p):
        x = pad + (p[0] - mn[0]) * scale
        y = pad + draw_h - (p[1] - mn[1]) * scale  # flip Y (SVG y-down)
        return x, y

    paths = []
    for poly in polylines:
        pts = " ".join(f"{tx(p)[0]:.1f},{tx(p)[1]:.1f}" for p in poly)
        paths.append(f'<polyline points="{pts}" fill="none" stroke="#111" stroke-width="1"/>')

    ty = height - 30
    titleblock = (
        f'<line x1="{pad}" y1="{ty-12}" x2="{width-pad}" y2="{ty-12}" stroke="#111" stroke-width="1"/>'
        f'<text x="{pad}" y="{ty+8}" font-family="sans-serif" font-size="16" font-weight="700">{title}</text>'
        f'<text x="{width-pad}" y="{ty+8}" font-family="sans-serif" font-size="12" '
        f'text-anchor="end" fill="#555">{subtitle}</text>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}"><rect width="{width}" height="{height}" fill="#fff"/>'
        + "".join(paths) + titleblock + "</svg>"
    )


def plan_svg(model: ifcopenshell.file, elevation: float, cut_height: float = 1.2,
             title: str = "PLAN") -> str:
    polys = cut(model, "plan", elevation + cut_height)
    return to_svg(polys, title=title, subtitle=f"cut @ {elevation + cut_height:.2f} m")


def section_svg(model: ifcopenshell.file, axis: str, offset: float, title: str = "SECTION") -> str:
    view = "section-x" if axis == "x" else "section-y"
    polys = cut(model, view, offset)
    return to_svg(polys, title=title, subtitle=f"{axis.upper()} = {offset:.2f} m")


def plan_file(ifc_path: str, elevation: float, cut_height: float = 1.2, title: str = "PLAN") -> str:
    return plan_svg(open_model(ifc_path), elevation, cut_height, title)
