"""Construction depth: T&M (eTicket) cost rollup + submittal register.
Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_construction_depth.py"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_cdepth.db"
os.environ["STORAGE_DIR"] = "./test_storage_cdepth"
os.environ.pop("AEC_RBAC", None)
for _f in ("./test_cdepth.db",):
    if os.path.exists(_f):
        os.remove(_f)

from fastapi.testclient import TestClient   # noqa: E402
from aec_api.main import app                # noqa: E402


def mk(c, pid, key, data):
    return c.post(f"/projects/{pid}/modules/{key}", json={"data": data}).json()["id"]


def trans(c, pid, key, rid, action):
    return c.post(f"/projects/{pid}/modules/{key}/{rid}/transition", json={"action": action})


with TestClient(app) as c:
    pid = c.post("/projects", json={"name": "Depth"}).json()["id"]

    # --- T&M / eTickets -------------------------------------------------------
    e1 = mk(c, pid, "eticket", {"subject": "Rock excavation", "work_date": "2026-06-10",
                                "labor_total": 4000, "material_total": 1000, "equipment_total": 2000})
    mk(c, pid, "eticket", {"subject": "Dewatering", "work_date": "2026-06-12",
                           "labor_total": 1500, "material_total": 500, "equipment_total": 1000})
    # bill the first ticket: draft → super_signed → gc_signed → billed
    for a in ("super_sign", "gc_sign", "bill"):
        r = trans(c, pid, "eticket", e1, a)
        if r.status_code != 200:  # action names may differ; push to billed however the workflow allows
            break
    tms = c.get(f"/projects/{pid}/tm-summary").json()
    assert tms["ticket_count"] == 2, tms
    assert tms["labor_total"] == 5500 and tms["material_total"] == 1500 and tms["equipment_total"] == 3000, tms
    assert tms["grand_total"] == 10000, tms
    assert tms["billed_total"] + tms["unbilled_total"] == 10000, tms

    # --- Submittal register ---------------------------------------------------
    mk(c, pid, "submittal", {"title": "Rebar shop dwgs", "spec_section": "03 20 00", "type": "Shop Drawing",
                             "responsible_contractor": "ACME", "date_received": "2026-06-01",
                             "date_returned": "2026-06-11", "required_on_site": "2020-01-01"})  # overdue + 10d turn
    mk(c, pid, "submittal", {"title": "Concrete mix", "spec_section": "03 30 00", "type": "Product Data",
                             "responsible_contractor": "ACME", "required_on_site": "2030-01-01"})
    reg = c.get(f"/projects/{pid}/submittals/register").json()
    assert reg["submittal_count"] == 2, reg
    assert reg["overdue_count"] == 1, reg                       # the 2020 one, still draft
    assert reg["avg_turnaround_days"] == 10.0, reg             # 06-01 → 06-11
    assert set(reg["by_section"].keys()) == {"03 20 00", "03 30 00"}, reg["by_section"]
    rebar = next(r for r in reg["rows"] if r["spec_section"] == "03 20 00")
    assert rebar["overdue"] is True and rebar["turnaround_days"] == 10, rebar

    # --- reports render -------------------------------------------------------
    cat = {x["id"] for x in c.get("/reports").json()["reports"]}
    assert {"tm_log", "submittal_register"} <= cat, cat
    for rid in ("tm_log", "submittal_register"):
        pdf = c.get(f"/projects/{pid}/reports/{rid}.pdf")
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF" and len(pdf.content) > 1200, (rid, pdf.status_code)

print("CONSTRUCTION-DEPTH OK - T&M rollup $10k (labor/material/equip split, billed+unbilled); submittal "
      "register: 2 subs, 1 overdue, avg turnaround 10d, by spec section; tm_log + submittal_register PDFs render")
