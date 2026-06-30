"""Preconstruction estimate continuity — per-milestone totals + $/SF, milestone-to-milestone drift,
and the gap to the project budget/GMP. Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_precon.py"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_precon.db"
os.environ["STORAGE_DIR"] = "./test_storage_precon"
os.environ.pop("AEC_RBAC", None)
for _f in ("./test_precon.db",):
    if os.path.exists(_f):
        os.remove(_f)

from fastapi.testclient import TestClient   # noqa: E402
from aec_api.main import app                # noqa: E402


def mk(c, pid, key, data):
    return c.post(f"/projects/{pid}/modules/{key}", json={"data": data}).json()["id"]


with TestClient(app) as c:
    pid = c.post("/projects", json={"name": "Precon"}).json()["id"]

    # the module is registered + catalogued
    assert "estimate_set" in {m["key"] for m in c.get("/modules").json()}

    # create estimate sets OUT of milestone order (engine must order along the design timeline)
    mk(c, pid, "estimate_set", {"title": "DD set", "milestone": "DD", "total": 12_500_000, "gsf": 50000,
                                "basis": "Budget", "estimate_date": "2026-03-01"})
    mk(c, pid, "estimate_set", {"title": "Concept set", "milestone": "Concept", "total": 10_000_000,
                                "gsf": 50000, "basis": "ROM", "estimate_date": "2026-01-01"})
    mk(c, pid, "estimate_set", {"title": "SD set", "milestone": "SD", "total": 11_000_000, "gsf": 50000,
                                "basis": "ROM", "estimate_date": "2026-02-01"})

    s = c.get(f"/projects/{pid}/precon/estimate-continuity?budget=12000000").json()
    assert s["set_count"] == 3, s
    assert s["milestones"] == ["Concept", "SD", "DD"], s["milestones"]      # ordered by milestone rank
    assert s["first_total"] == 10_000_000 and s["first_milestone"] == "Concept", s
    assert s["latest_total"] == 12_500_000 and s["latest_milestone"] == "DD", s
    assert s["latest_psf"] == 250.0, s["latest_psf"]                        # 12.5M / 50k SF
    assert s["total_drift"] == 2_500_000 and s["total_drift_pct"] == 25.0, s
    assert s["budget"] == 12_000_000, s
    assert s["variance_to_budget"] == 500_000 and s["over_budget"] is True, s   # latest 12.5M vs 12M budget
    dd = next(r for r in s["rows"] if r["milestone"] == "DD")
    assert dd["delta_total"] == 1_500_000 and dd["delta_pct"] == round(100 * 1.5 / 11, 1), dd  # SD->DD

    # report renders (PDF + xlsx) and is catalogued
    assert "estimate_continuity" in {x["id"] for x in c.get("/reports").json()["reports"]}
    pdf = c.get(f"/projects/{pid}/reports/estimate_continuity.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF", pdf.status_code
    xls = c.get(f"/projects/{pid}/reports/estimate_continuity.xlsx")
    assert xls.status_code == 200 and len(xls.content) > 100, xls.status_code

    # empty project -> clean zeroed structure (no crash)
    pid2 = c.post("/projects", json={"name": "Empty precon"}).json()["id"]
    e = c.get(f"/projects/{pid2}/precon/estimate-continuity").json()
    assert e["set_count"] == 0 and e["latest_total"] == 0.0 and e["variance_to_budget"] is None, e

print("PRECON OK - estimate sets ordered Concept->SD->DD; $/SF (250 at DD); milestone drift (SD->DD "
      "+1.5M) + first->latest +2.5M/25%; variance vs $12M budget = +500k OVER; report renders PDF+xlsx; "
      "empty project zeroed")
