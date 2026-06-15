"""Role-tailored dashboard test. Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_dashboard.py"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_dash.db"
os.environ["STORAGE_DIR"] = "./test_storage"
os.environ["AEC_RBAC"] = "1"

for f in ("./test_dash.db",):
    if os.path.exists(f):
        os.remove(f)

from fastapi.testclient import TestClient  # noqa: E402
from aec_api.main import app  # noqa: E402

H = lambda u: {"X-User": u}  # noqa: E731

with TestClient(app) as c:
    pid = c.post("/projects", json={"name": "Tower"}, headers=H("gc")).json()["id"]
    for u, party in [("sub", "Subcontractor"), ("consultant", "Consultant"), ("owner", "Owner")]:
        c.post(f"/projects/{pid}/members", json={"user": u, "role": "reviewer", "party_role": party}, headers=H("gc"))

    rfi = c.post(f"/projects/{pid}/modules/rfi", json={"data": {"subject": "Q", "question": "?"}}, headers=H("gc")).json()
    c.post(f"/projects/{pid}/modules/rfi/{rfi['id']}/transition", json={"action": "submit"}, headers=H("gc"))
    cor = c.post(f"/projects/{pid}/modules/cor", json={"data": {"subject": "CO", "amount": 5000}}, headers=H("gc")).json()
    c.post(f"/projects/{pid}/modules/cor/{cor['id']}/transition", json={"action": "submit"}, headers=H("gc"))

    def items(party):
        return {a["module"] for a in c.get(f"/projects/{pid}/dashboard", params={"party": party}, headers=H("gc")).json()["action_items"]}

    assert items("GC") >= {"rfi", "cor"}                       # GC passes every gate
    assert "rfi" in items("Consultant") and "cor" not in items("Consultant")
    assert "cor" in items("Owner") and "rfi" not in items("Owner")
    assert items("Subcontractor") == set()                     # no sub steps available

    d = c.get(f"/projects/{pid}/dashboard", headers=H("gc")).json()
    assert d["kpis"]["open_rfis"] == 1 and d["kpis"]["pending_change_orders"] == 1

    print("DASHBOARD OK")
    print(f"  GC={sorted(items('GC'))}  Consultant={sorted(items('Consultant'))}  Owner={sorted(items('Owner'))}")
    print(f"  kpis: {{k:v for non-zero}} = {dict((k, v) for k, v in d['kpis'].items() if v)}")
