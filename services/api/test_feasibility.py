"""Site feasibility / zoning envelope: the pure envelope math (FAR vs. physical envelope binding,
unit yield, parking, model reconciliation) + the module-backed endpoint + the report.
Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_feasibility.py"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_feasibility.db"
os.environ["STORAGE_DIR"] = "./test_storage_feasibility"
os.environ.pop("AEC_RBAC", None)
for _f in ("./test_feasibility.db",):
    if os.path.exists(_f):
        os.remove(_f)

from aec_api import feasibility as feas      # noqa: E402
from fastapi.testclient import TestClient    # noqa: E402
from aec_api.main import app                 # noqa: E402

# --- pure math ---------------------------------------------------------------
# FAR binds: 20,000 SF site x FAR 3 = 60,000 allowed; envelope (50% cov=10,000 ft x 8 floors=80,000) is looser.
z = {"site_area_sf": 20_000, "far": 3.0, "height_limit_ft": 96, "floor_to_floor_ft": 12,
     "lot_coverage_pct": 50, "efficiency_pct": 85, "avg_unit_sf": 850, "parking_ratio": 1.0, "open_space_pct": 10}
r = feas.compute(z)
assert r["far_gfa_sf"] == 60_000, r
assert r["max_floors"] == 8, r                                 # 96 / 12
assert r["envelope_gfa_sf"] == 80_000, r                       # 10,000 footprint x 8
assert r["allowed_gfa_sf"] == 60_000 and r["binding_constraint"] == "FAR", r
assert r["net_buildable_sf"] == 51_000.0, r                    # 60,000 x 85%
assert r["unit_yield"] == 60, r                                # floor(51,000 / 850)
assert r["parking_required"] == 60, r
assert r["open_space_required_sf"] == 2_000.0, r

# physical envelope binds when FAR is generous
r2 = feas.compute({**z, "far": 10.0})
assert r2["binding_constraint"] == "physical envelope" and r2["allowed_gfa_sf"] == 80_000, r2

# model reconciliation: 45,000 actual vs 60,000 allowed -> 75% used, under, headroom 15,000
rm = feas.compute(z, actual_gfa_sf=45_000)
assert rm["model"]["pct_of_allowed"] == 75.0 and rm["model"]["status"] == "under", rm["model"]
assert rm["model"]["headroom_gfa_sf"] == 15_000.0 and rm["model"]["far_used"] == 2.25, rm["model"]
# over-build is flagged
ro = feas.compute(z, actual_gfa_sf=65_000)
assert ro["model"]["status"] == "over", ro["model"]

# missing site area -> error
assert feas.compute({"far": 3})["error"], "expected error for missing site area"

with TestClient(app) as c:
    pid = c.post("/projects", json={"name": "Feas"}).json()["id"]
    assert "zoning" in {m["key"] for m in c.get("/modules").json()}

    # no zoning record yet -> graceful error
    assert c.get(f"/projects/{pid}/feasibility").json().get("error"), "expected no-zoning error"

    # create a zoning record -> the endpoint computes the envelope
    c.post(f"/projects/{pid}/modules/zoning", json={"data": {
        "site": "Tower parcel", "jurisdiction": "DT-3", "use_type": "Mixed-Use",
        "site_area_sf": 20_000, "far": 3.0, "height_limit_ft": 96, "floor_to_floor_ft": 12,
        "lot_coverage_pct": 50, "efficiency_pct": 85, "avg_unit_sf": 850, "parking_ratio": 1.0, "open_space_pct": 10}})
    f = c.get(f"/projects/{pid}/feasibility").json()
    assert f["allowed_gfa_sf"] == 60_000 and f["binding_constraint"] == "FAR", f
    assert f["unit_yield"] == 60 and f["parking_required"] == 60, f
    assert f["site"] == "Tower parcel" and f.get("ref"), f

    # ?gfa= override drives the model reconciliation
    fg = c.get(f"/projects/{pid}/feasibility?gfa=45000").json()
    assert fg["model"]["pct_of_allowed"] == 75.0 and fg["model"]["status"] == "under", fg["model"]

    # report renders
    assert "site_feasibility" in {x["id"] for x in c.get("/reports").json()["reports"]}
    pdf = c.get(f"/projects/{pid}/reports/site_feasibility.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF", pdf.status_code

print("FEASIBILITY OK - envelope math (FAR vs physical envelope binding, unit yield, parking, open space), "
      "model reconciliation (FAR used / headroom / over-under), zoning-backed endpoint, and the report render")
