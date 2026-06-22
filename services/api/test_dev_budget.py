"""Developer cost budget — engine math + persistence + proforma cost-line mapping.
Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_dev_budget.py"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_devbudget.db"
os.environ["STORAGE_DIR"] = "./test_storage_devbudget"
os.environ.pop("AEC_RBAC", None)
for f in ("./test_devbudget.db",):
    if os.path.exists(f):
        os.remove(f)

from fastapi.testclient import TestClient  # noqa: E402
from aec_api import dev_budget as dvb  # noqa: E402
from aec_api.main import app  # noqa: E402

# --- pure engine: line totals, contingency, category rollups -----------------
budget = {
    "contingency": {"hard": 0.10, "soft": 0.10, "acquisition": 0.0},
    "lines": [
        {"category": "acquisition", "description": "Purchase", "unit_cost": 15_744_700, "quantity": 1},
        {"category": "hard", "description": "Solar panels", "unit_cost": 330, "quantity": 25_000},
        {"category": "hard", "description": "Wind turbines", "unit_cost": 5_000, "quantity": 1_161},
        {"category": "soft", "description": "Architect", "unit_cost": 350_000, "quantity": 1},
        {"category": "soft", "description": "Energy consultant", "unit_cost": 75_000, "quantity": 1},
    ],
}
s = dvb.summarize(budget)
assert s["categories"]["hard"]["subtotal"] == 330 * 25_000 + 5_000 * 1_161, s["categories"]["hard"]
assert s["categories"]["hard"]["contingency"] == round(s["categories"]["hard"]["subtotal"] * 0.10, 2)
assert s["categories"]["soft"]["subtotal"] == 425_000.0
assert s["categories"]["acquisition"]["contingency"] == 0.0
expect_grand = (s["categories"]["acquisition"]["total"] + s["categories"]["hard"]["total"]
                + s["categories"]["soft"]["total"])
assert abs(s["grand_total"] - round(expect_grand, 2)) < 0.01, (s["grand_total"], expect_grand)
assert 0 < s["soft_pct"] < s["hard_pct"] < 1, (s["hard_pct"], s["soft_pct"])   # hard dominates

# --- cost_lines mapping: rolled category line + its contingency as a separate line ---
cl = dvb.to_cost_lines(budget)
cats = [c["category"] for c in cl]
assert "land" in cats and "hard" in cats and "soft" in cats and "contingency" in cats, cats
assert sum(c["amount"] for c in cl) == s["grand_total"], "cost_lines must reconcile to grand total"

# --- persistence round-trip via the API --------------------------------------
with TestClient(app) as c:
    pid = c.post("/projects", json={"name": "Dev Tower"}).json()["id"]
    # starter budget served when none saved
    g0 = c.get(f"/projects/{pid}/dev-budget").json()
    assert g0["budget"]["lines"] and "summary" in g0, g0
    # save + recompute
    r = c.put(f"/projects/{pid}/dev-budget", json={"lines": budget["lines"], "contingency": budget["contingency"]})
    assert r.status_code == 200, r.text
    assert r.json()["summary"]["grand_total"] == s["grand_total"]
    # persisted
    assert c.get(f"/projects/{pid}/dev-budget").json()["summary"]["grand_total"] == s["grand_total"]
    # cost-lines endpoint reconciles
    clr = c.get(f"/projects/{pid}/dev-budget/cost-lines").json()
    assert round(sum(x["amount"] for x in clr["cost_lines"]), 2) == s["grand_total"], clr

print(f"DEV-BUDGET OK - line totals + per-category contingency + grand ${s['grand_total']:,.0f}; "
      f"hard {s['hard_pct']*100:.0f}% / soft {s['soft_pct']*100:.0f}%; cost_lines reconcile; persisted via API")
