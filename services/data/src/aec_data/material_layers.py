"""Material layer sets (M3) — Revit-style layered construction assemblies.

Where M1 ([materials.py]) gives each element class a single material + colour, this attaches a real
**IfcMaterialLayerSet** to walls / floors / roofs (e.g. brick · cavity · insulation · CMU · gypsum)
via an IfcMaterialLayerSetUsage, so the model carries genuine assembly data the way Revit's compound
structures do — usable for take-off, thermal (U-value), and schedules.

Pure-ish over an open ifcopenshell model; run as a post-process before writing. Thicknesses are in
metres (project METRE convention). Wall assembly is chosen from Pset_WallCommon.IsExternal; slab vs
roof from the slab PredefinedType.
"""
from __future__ import annotations

from typing import Any

# An assembly = ordered list of (layer name, material name, material category, thickness m).
# Order is exterior/top face → interior/bottom face.
ASSEMBLIES: dict[str, list[tuple[str, str, str, float]]] = {
    "exterior_wall": [
        ("Brick veneer", "Brick", "masonry", 0.090),
        ("Air cavity", "Air", "air", 0.025),
        ("Rigid insulation", "XPS insulation", "insulation", 0.050),
        ("CMU backup", "Concrete masonry", "masonry", 0.190),
        ("Gypsum board", "Gypsum", "gypsum", 0.016),
    ],
    "interior_partition": [
        ("Gypsum board", "Gypsum", "gypsum", 0.016),
        ("Stud cavity", "Mineral wool", "insulation", 0.092),
        ("Gypsum board", "Gypsum", "gypsum", 0.016),
    ],
    "floor_slab": [
        ("Floor finish", "Vinyl", "finish", 0.010),
        ("Screed", "Cement screed", "screed", 0.050),
        ("Structural slab", "Concrete", "concrete", 0.200),
    ],
    "flat_roof": [
        ("Roofing membrane", "Bituminous membrane", "roofing", 0.005),
        ("Rigid insulation", "PIR insulation", "insulation", 0.120),
        ("Vapour barrier", "Polyethylene", "membrane", 0.002),
        ("Structural deck", "Concrete", "concrete", 0.150),
    ],
}


def _pset_bool(el, pset: str, prop: str) -> bool | None:
    import ifcopenshell.util.element
    val = ifcopenshell.util.element.get_psets(el).get(pset, {}).get(prop)
    return bool(val) if isinstance(val, bool) else None


def _assembly_for(el) -> str:
    """Pick the assembly key for an element from its class / Pset / predefined type."""
    cls = el.is_a()
    if cls in ("IfcWall", "IfcWallStandardCase"):
        ext = _pset_bool(el, "Pset_WallCommon", "IsExternal")
        return "exterior_wall" if ext or ext is None else "interior_partition"
    if cls == "IfcRoof":
        return "flat_roof"
    if cls == "IfcSlab":
        return "flat_roof" if str(getattr(el, "PredefinedType", "") or "").upper() == "ROOF" else "floor_slab"
    return "floor_slab"


def apply_layer_sets(model, assemblies: dict | None = None) -> dict[str, Any]:
    """Attach an IfcMaterialLayerSet (built once per assembly + reused) to every wall / slab / roof
    via an IfcMaterialLayerSetUsage. Returns counts. Idempotent enough for a one-shot post-process."""
    import ifcopenshell.api

    lib = assemblies or ASSEMBLIES
    mat_cache: dict[str, Any] = {}
    set_cache: dict[str, Any] = {}

    def material(name: str, category: str):
        if name not in mat_cache:
            mat_cache[name] = ifcopenshell.api.run("material.add_material", model, name=name, category=category)
        return mat_cache[name]

    def layer_set(key: str):
        if key not in set_cache:
            ls = ifcopenshell.api.run("material.add_material_set", model,
                                      name=key.replace("_", " ").title(), set_type="IfcMaterialLayerSet")
            for lname, mname, cat, thick in lib[key]:
                layer = ifcopenshell.api.run("material.add_layer", model, layer_set=ls, material=material(mname, cat))
                ifcopenshell.api.run("material.edit_layer", model, layer=layer,
                                     attributes={"Name": lname, "LayerThickness": float(thick)})
            set_cache[key] = ls
        return set_cache[key]

    assigned = 0
    by_key: dict[str, int] = {}
    targets = model.by_type("IfcWall") + model.by_type("IfcSlab") + model.by_type("IfcRoof")
    for el in targets:
        key = _assembly_for(el)
        try:
            ifcopenshell.api.run("material.assign_material", model, products=[el],
                                 type="IfcMaterialLayerSetUsage", material=layer_set(key))
            assigned += 1
            by_key[key] = by_key.get(key, 0) + 1
        except Exception:                       # noqa: BLE001 — element may not accept a usage
            pass

    return {"assigned": assigned, "layer_sets": len(set_cache), "by_assembly": by_key,
            "total_thickness_m": {k: round(sum(t for *_, t in lib[k]), 3) for k in set_cache}}
