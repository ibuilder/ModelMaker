"""GC project budget (GMP): direct trades + GC/GR + staffing + overhead/fee/contingency, relational
to cost codes, commitments, bid packages, the prime contract, and the developer proforma hard cost.
Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_project_budget.py"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_project_budget.db"
os.environ["STORAGE_DIR"] = "./test_storage_pb"
os.environ.pop("AEC_RBAC", None)
for f in ("./test_project_budget.db",):
    if os.path.exists(f):
        os.remove(f)

from fastapi.testclient import TestClient  # noqa: E402
from aec_api.main import app  # noqa: E402


def mk(c, pid, key, data):
    return c.post(f"/projects/{pid}/modules/{key}", json={"data": data}).json()


with TestClient(app) as c:
    pid = c.post("/projects", json={"name": "GMP Tower"}).json()["id"]

    # cost codes: one trade (Div 03 Concrete), one general requirement (Div 01)
    cc_conc = mk(c, pid, "cost_code", {"code": "03-3000", "description": "Concrete", "division": "03"})["id"]
    cc_gr = mk(c, pid, "cost_code", {"code": "01-5000", "description": "Temp facilities", "division": "01"})["id"]

    # budget lines per cost code (the PX's GMP allocation)
    mk(c, pid, "budget", {"cost_code": cc_conc, "description": "Concrete", "revised": 2_000_000})
    mk(c, pid, "budget", {"cost_code": cc_gr, "description": "Temp facilities", "revised": 500_000})

    # buyout: an executed commitment against concrete (committed < budget → positive variance)
    com = mk(c, pid, "commitment", {"description": "Concrete sub", "cost_code": cc_conc, "amount": 1_800_000})
    c.post(f"/projects/{pid}/modules/commitment/{com['id']}/transition", json={"action": "execute"})

    # staffing projections: PM under General Conditions, Safety under General Requirements
    mk(c, pid, "staffing", {"role": "Project Manager", "category": "General Conditions", "count": 1,
                            "rate": 25_000, "rate_period": "Month", "start": "2026-01-01", "finish": "2026-12-31"})
    mk(c, pid, "staffing", {"role": "Safety Manager", "category": "General Requirements", "count": 1,
                            "rate": 15_000, "rate_period": "Month", "start": "2026-01-01", "finish": "2026-12-31"})

    # prime contract = the agreed GMP + markup rates the PX set
    mk(c, pid, "prime_contract", {"name": "GMP w/ Owner", "type": "GMP", "value": 10_000_000,
                                  "overhead_pct": 5, "fee_pct": 4, "contingency_pct": 3})

    # a bid package (buyout tracking is relational to every package)
    mk(c, pid, "bid_package", {"name": "Concrete", "trade": "Concrete", "budget": 2_000_000})

    # developer proforma hard cost (the construction line the GMP must reconcile against)
    c.put(f"/projects/{pid}/dev-budget", json={"lines": [
        {"category": "hard", "description": "Hard costs", "unit_cost": 3_200_000, "quantity": 1}]})

    b = c.get(f"/projects/{pid}/budget/gmp").json()
    cats = {c0["key"]: c0 for c0 in b["categories"]}
    assert set(cats) == {"direct", "general_requirements", "general_conditions", "overhead", "fee", "contingency"}, list(cats)

    # direct work: $2.0M budget, $1.8M committed (the executed sub), grouped under Division 03
    assert cats["direct"]["budget"] == 2_000_000 and cats["direct"]["committed"] == 1_800_000, cats["direct"]
    assert cats["direct"]["variance"] == 200_000, cats["direct"]["variance"]
    assert any(g["name"] == "Division 03" for g in cats["direct"]["groups"]), cats["direct"]["groups"]

    # staffing rolls into the right buckets (PM→GC, Safety→GR); ~12 months each
    assert 280_000 < cats["general_conditions"]["budget"] < 320_000, cats["general_conditions"]["budget"]
    assert cats["general_requirements"]["budget"] > 500_000, cats["general_requirements"]["budget"]   # 500k temp + safety

    cow = b["gmp"]["cost_of_work"]
    assert cats["overhead"]["budget"] == round(cow * 0.05, 2), (cats["overhead"]["budget"], cow)
    assert cats["fee"]["budget"] == round((cow + cats["overhead"]["budget"]) * 0.04, 2), cats["fee"]["budget"]
    assert cats["contingency"]["budget"] == round(2_000_000 * 0.03, 2), cats["contingency"]["budget"]

    # GMP reconciliation + proforma tie
    assert b["gmp"]["computed"] == b["totals"]["budget"], (b["gmp"]["computed"], b["totals"]["budget"])
    assert b["gmp"]["contract_value"] == 10_000_000 and b["gmp"]["reconciliation"] is not None
    assert b["proforma"]["hard_cost"] == 3_200_000, b["proforma"]
    assert b["proforma"]["gmp_vs_hard"] == round(b["gmp"]["computed"] - 3_200_000, 2), b["proforma"]
    assert len(b["bid_packages"]) == 1 and b["staffing"]["projected"] > 0, (b["bid_packages"], b["staffing"])

    print(f"PROJECT BUDGET OK - GMP computed ${b['gmp']['computed']:,.0f} (cost of work ${cow:,.0f}); "
          f"direct/GC/GR + OH/fee/contingency; bid packages + staffing + proforma hard-cost reconciled")
