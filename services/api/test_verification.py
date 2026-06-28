"""Field verification & install coverage: set per-element status, report % coverage vs the model
total, and list deviations. Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_verification.py"""
import json
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_verification.db"
os.environ["STORAGE_DIR"] = "./test_storage_verification"
os.environ.pop("AEC_RBAC", None)
for _f in ("./test_verification.db",):
    if os.path.exists(_f):
        os.remove(_f)

from fastapi.testclient import TestClient   # noqa: E402
from aec_api.main import app                # noqa: E402

PROPS = {"project": {"name": "Plant"}, "elements": [
    {"guid": "g1", "ifc_class": "IfcDuctSegment", "storey": "L1"},
    {"guid": "g2", "ifc_class": "IfcDuctSegment", "storey": "L1"},
    {"guid": "g3", "ifc_class": "IfcPipeSegment", "storey": "L2"},
    {"guid": "g4", "ifc_class": "IfcPipeSegment", "storey": "L2"},
]}

with TestClient(app) as c:
    pid = c.post("/projects", json={"name": "Plant"}).json()["id"]
    c.post(f"/projects/{pid}/properties/index",
           files={"file": ("props.json", json.dumps(PROPS).encode(), "application/json")})

    # invalid status rejected
    assert c.put(f"/projects/{pid}/verification/g1", json={"status": "bogus"}).status_code == 422

    # mark statuses: g1 verified, g2 installed, g3 deviation, g4 untouched (pending)
    v1 = c.put(f"/projects/{pid}/verification/g1", json={"status": "verified"})
    assert v1.status_code == 200 and v1.json()["status"] == "verified", v1.text[:160]
    assert v1.json()["ifc_class"] == "IfcDuctSegment"            # stamped from the index
    c.put(f"/projects/{pid}/verification/g2", json={"status": "installed"})
    c.put(f"/projects/{pid}/verification/g3", json={"status": "deviation", "note": "elbow clashes joist"})

    cov = c.get(f"/projects/{pid}/verification/coverage").json()
    assert cov["total_elements"] == 4, cov
    assert cov["verified"] == 1 and cov["installed"] == 2, cov      # installed = verified + installed
    assert cov["deviations"] == 1, cov
    assert cov["verified_pct"] == 25.0 and cov["installed_pct"] == 50.0, cov
    assert cov["by_status"]["pending"] == 1, cov                    # g4 untracked → pending

    # deviation log
    dev = c.get(f"/projects/{pid}/verification/deviations").json()
    assert len(dev) == 1 and dev[0]["guid"] == "g3" and dev[0]["note"], dev

    # filtered list
    only_verified = c.get(f"/projects/{pid}/verification?status=verified").json()
    assert [v["guid"] for v in only_verified] == ["g1"], only_verified

    # re-verify g1 (upsert, not duplicate) then photo attach
    c.put(f"/projects/{pid}/verification/g1", json={"status": "installed"})
    again = c.get(f"/projects/{pid}/verification?status=verified").json()
    assert again == [], again                                       # status changed, no dup row
    ph = c.post(f"/projects/{pid}/verification/g3/photo",
                files={"file": ("field.jpg", b"\xff\xd8\xff jpeg", "image/jpeg")})
    assert ph.status_code == 200 and ph.json()["has_photo"], ph.text[:160]

print("VERIFICATION OK - per-element status upserts (stamped from index); coverage 25% verified / 50% "
      "installed of 4; 1 deviation logged with note + photo; status filter + pending rollup correct")
