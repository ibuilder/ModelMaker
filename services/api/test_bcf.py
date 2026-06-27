"""BCF 2.1 round-trip (a CLAUDE.md non-negotiable: pins/RFIs follow the BCF model so they round-trip
with other BIM tools). Covers the project-Topic path (export -> import into a fresh project) and the
config-module records path (export_records -> parse_records), incl. viewpoints/components by GUID.
Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_bcf.py"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_bcf.db"
os.environ["STORAGE_DIR"] = "./test_storage_bcf"
os.environ.pop("AEC_RBAC", None)
for f in ("./test_bcf.db",):
    if os.path.exists(f):
        os.remove(f)

import io                                                      # noqa: E402
import zipfile                                                 # noqa: E402

from fastapi.testclient import TestClient                      # noqa: E402
from aec_api.main import app                                   # noqa: E402
from aec_api import bcf_io                                     # noqa: E402

GUID = "3vB2eYHr1ABcDeFgHiJkLm"          # an IFC GlobalId on the topic's viewpoint


with TestClient(app) as c:
    src = c.post("/projects", json={"name": "BCF Source"}).json()["id"]

    # a pinned clash topic (element-tied) + a plain RFI topic
    t1 = c.post(f"/projects/{src}/topics", json={
        "type": "clash", "title": "Beam vs duct", "description": "HVAC main clips the W21",
        "priority": "High", "assignee": "coordinator", "labels": ["CLH-001"],
        "anchor": {"x": 12.5, "y": 3.0, "z": 4.2}, "element_guids": [GUID]})
    assert t1.status_code == 201, t1.text[:200]
    c.post(f"/projects/{src}/topics", json={"type": "rfi", "title": "Slab edge detail"})

    # --- project Topic path: export .bcfzip -> import into a FRESH project ----
    exp = c.get(f"/projects/{src}/bcf/export")
    assert exp.status_code == 200, exp.text[:200]
    blob = exp.content
    # it's a real BCF zip: bcf.version + per-topic markup.bcf + a viewpoint for the pinned one
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = z.namelist()
        assert "bcf.version" in names, names
        assert sum(1 for n in names if n.endswith("markup.bcf")) == 2, names
        assert any(n.endswith(".bcfv") for n in names), names      # pinned topic carries a viewpoint

    dst = c.post("/projects", json={"name": "BCF Target"}).json()["id"]
    imp = c.post(f"/projects/{dst}/bcf/import",
                 files={"file": ("issues.bcfzip", blob, "application/zip")})
    assert imp.status_code == 200, imp.text[:200]
    assert imp.json()["imported"] == 2, imp.json()

    topics = c.get(f"/projects/{dst}/topics").json()
    assert len(topics) == 2, topics
    titles = {t["title"] for t in topics}
    assert {"Beam vs duct", "Slab edge detail"} == titles, titles
    clash = next(t for t in topics if t["title"] == "Beam vs duct")
    assert clash["description"] == "HVAC main clips the W21", clash
    assert clash["priority"] == "High", clash
    # the pin survives: element tie by IFC GlobalId + the 3D anchor (non-negotiable)
    assert clash["element_guids"] == [GUID], clash
    assert clash["anchor"] and abs(clash["anchor"]["x"] - 12.5) < 1e-6, clash

    # --- config-module records path: export_records -> parse_records ----------
    records = [{
        "id": "rec-guid-1", "ref": "CI-001", "title": "Sprinkler vs beam",
        "workflow_state": "open", "assignee": "qa",
        "data": {"subject": "Sprinkler vs beam", "description": "Branch line below structure",
                 "priority": "Critical"},
        "element_guids": [GUID], "anchor": {"x": 1.0, "y": 2.0, "z": 3.0}}]
    z_bytes = bcf_io.export_records_bcfzip(records, topic_type="Clash")
    parsed = bcf_io.parse_records_bcfzip(z_bytes)
    assert len(parsed) == 1, parsed
    p = parsed[0]
    assert p["data"]["subject"] == "Sprinkler vs beam", p
    assert p["data"]["priority"] == "Critical", p
    assert GUID in p["element_guids"], p                        # component round-trips by IFC GUID
    assert p["anchor"] and abs(p["anchor"]["x"] - 1.0) < 1e-6, p
    assert p["status"] == "open", p

    # empty project still exports a valid (topic-less) bcfzip — no crash
    empty = c.post("/projects", json={"name": "Empty"}).json()["id"]
    e = c.get(f"/projects/{empty}/bcf/export")
    assert e.status_code == 200
    with zipfile.ZipFile(io.BytesIO(e.content)) as z:
        assert "bcf.version" in z.namelist()
        assert not [n for n in z.namelist() if n.endswith("markup.bcf")]

print("BCF OK - Topic export/import round-trips into a fresh project (2 topics, fields + priority); "
      "module records export/parse preserve subject/priority/anchor + components by IFC GUID; "
      "empty project exports a valid topic-less bcfzip")
