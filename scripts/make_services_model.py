"""Generate a small MEP/services IFC (horizontal ducts) that crosses the structural model
at floor-slab levels — a federated cross-discipline clash demo. Run with the data venv:
   PYTHONPATH=services/data/src services/data/.venv/Scripts/python.exe scripts/make_services_model.py
"""
import warnings

warnings.filterwarnings("ignore")
import ifcopenshell
import ifcopenshell.api

OUT = "samples/school_mep.ifc"

# Positioned against the REAL structure (footprint X -16..57, Y -24..31):
# ground framing is dense at Z~0.25; upper beams at ~3.3; columns span Z 0..3.5.
# axis: 'x' runs along X at plan-Y=a; 'y' runs along Y at plan-X=a; 'z' is a vertical riser.
# (axis, along0, along1, a, z_center, w, h)
DUCTS = [
    ("x", -12, 50, 0.0, 0.25, 0.5, 0.5),    # main duct across ground framing
    ("x", -12, 50, 12.0, 0.25, 0.5, 0.5),   # parallel run
    ("y", -20, 28, 8.0, 0.25, 0.5, 0.5),    # cross run over ground framing
    ("x", -12, 2, 5.0, 3.30, 0.5, 0.5),     # duct through upper-floor beams (z~3.3)
    ("z", -1.0, 4.0, None, None, 0.5, 0.5),  # vertical riser through a column (x=-9.2,y=6.85)
]
RISER_XY = (-9.2, 6.85)


def box(x0, y0, z0, x1, y1, z1):
    """Watertight, consistently-wound (outward CCW) cube — manifold-clean for booleans."""
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 2, 1), (0, 3, 2),   # bottom -Z
         (4, 5, 6), (4, 6, 7),   # top +Z
         (0, 1, 5), (0, 5, 4),   # front -Y
         (3, 7, 6), (3, 6, 2),   # back +Y
         (0, 4, 7), (0, 7, 3),   # left -X
         (1, 2, 6), (1, 6, 5)]   # right +X
    return v, f


def main():
    m = ifcopenshell.api.run("project.create_file", version="IFC4")
    ifcopenshell.api.run("root.create_entity", m, ifc_class="IfcProject", name="School — Services")
    ifcopenshell.api.run("unit.assign_unit", m)
    ctx = ifcopenshell.api.run("context.add_context", m, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", m, context_type="Model",
                                context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)
    for i, (axis, a0, a1, a, zc, w, h) in enumerate(DUCTS, 1):
        el = ifcopenshell.api.run("root.create_entity", m, ifc_class="IfcBuildingElementProxy",
                                  name=f"Duct-{i}")
        if axis == "x":
            v, f = box(a0, a - w / 2, zc - h / 2, a1, a + w / 2, zc + h / 2)
        elif axis == "y":
            v, f = box(a - w / 2, a0, zc - h / 2, a + w / 2, a1, zc + h / 2)
        else:  # vertical riser
            rx, ry = RISER_XY
            v, f = box(rx - w / 2, ry - w / 2, a0, rx + w / 2, ry + w / 2, a1)
        rep = ifcopenshell.api.run("geometry.add_mesh_representation", m, context=body,
                                   vertices=[v], faces=[f])
        ifcopenshell.api.run("geometry.assign_representation", m, product=el, representation=rep)
    m.write(OUT)
    print(f"wrote {OUT} with {len(DUCTS)} ducts")


if __name__ == "__main__":
    main()
