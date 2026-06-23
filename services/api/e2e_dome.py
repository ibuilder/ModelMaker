"""End-to-end earth-dome house: a monolithic/earth dome from model → budget → construction →
furnish → turnover. Exercises the dome generator + the developer/GC/turnover stack over HTTP and
reports PASS/FAIL per step (a failing step never aborts). Run: python services/api/e2e_dome.py"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://localhost:8000")
ap.add_argument("--user", default="gc")
opts = ap.parse_args()
results: list[tuple[str, str, str, str]] = []
_phase = "0"


def call(method, path, body=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(opts.url + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "X-User": opts.user})
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read()
        return b if raw else json.loads(b or "{}")


def run(name, fn):
    try:
        out = fn()
        results.append((_phase, name, "PASS", out if isinstance(out, str) else ""))
        print(f"  PASS  {name}" + (f"  ->  {out}" if isinstance(out, str) else ""))
        return out
    except urllib.error.HTTPError as e:
        det = f"{e.code}: {e.read().decode()[:160]}"; results.append((_phase, name, "FAIL", det)); print(f"  FAIL  {name}  ({det})")
    except Exception as e:                       # noqa: BLE001
        results.append((_phase, name, "FAIL", str(e)[:180])); print(f"  FAIL  {name}  ({str(e)[:180]})")
    return None


def phase(n, t):
    global _phase
    _phase = n; print(f"\n=== PHASE {n} - {t} ===")


pid = None


def new(mod, data, assignee=None):
    body = {"data": data}
    if assignee:
        body["assignee"] = assignee
    return call("POST", f"/projects/{pid}/modules/{mod}", body)["id"]


def act(mod, rid, action):
    call("POST", f"/projects/{pid}/modules/{mod}/{rid}/transition", {"action": action})


def edit(recipe, params, publish=False):
    return call("POST", f"/projects/{pid}/edit", {"recipe": recipe, "params": params, "publish": publish})


def upload(mod, rid, fname, content):
    boundary = "----e2edome"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\n"
            f"Content-Type: text/plain\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(opts.url + f"/projects/{pid}/modules/{mod}/{rid}/attachments", data=body,
                                 method="POST", headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-User": opts.user})
    urllib.request.urlopen(req, timeout=120).read(); return True


def wait_publish():
    for _ in range(60):
        s = call("GET", f"/projects/{pid}/publish/status").get("state")
        if s in ("done", "error"):
            return s
        time.sleep(1)
    return "timeout"


def _furniture_count():
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "data", "src"))
    from aec_data.ifc_loader import open_model  # type: ignore
    m = open_model(call("GET", f"/projects/{pid}")["source_ifc"])
    n = (len(m.by_type("IfcFurniture")) + len(m.by_type("IfcSanitaryTerminal"))
         + len(m.by_type("IfcElectricAppliance")) + len(m.by_type("IfcGeographicElement")))
    return f"{n} furniture/fixture/appliance/plant occurrences"


# ============================================================================
phase("0", "Model — generate the earth dome")
pid = run("create project", lambda: call("POST", "/projects", {"name": "Earth Dome House"})["id"])
if not pid:
    raise SystemExit("no project")
g = run("generate dome (shape=dome, r=8m)", lambda: call("POST", f"/projects/{pid}/generate/massing",
        {"name": "Earth Dome House", "shape": "dome", "dome_radius": 8.0, "use_type": "residential"}))
if g:
    run("  program", lambda: f"{g['metrics']['buildable_gfa_sf']} sf · system: {g['metrics']['structure']['system']}")
    run("  publish model", wait_publish)
run("model published (source IFC set)", lambda: f"source set: {bool(call('GET', f'/projects/{pid}')['source_ifc'])}")
run("model takeoff -> estimate", lambda: f"${call('GET', f'/projects/{pid}/estimate/from-model').get('total', 0):,.0f}")
run("drawings: plan", lambda: f"{len(call('GET', f'/projects/{pid}/drawings/plan.svg?elevation=1.2', raw=True)):,} bytes")
run("energy analysis", lambda: f"EUI {call('GET', f'/projects/{pid}/energy').get('eui_kwh_m2_yr', '?')}" if True else "")

# ============================================================================
phase("1", "Budget + underwrite")
run("property & tax", lambda: f"taxes ${call('PUT', f'/projects/{pid}/property', {'purchase_price': 60_000, 'building_sf': 2164, 'land_sf': 8000, 'taxes': {'county': 3_200, 'town': 1_800}})['summary']['total_taxes']:,.0f}")
run("cost budget (earth dome)", lambda: f"grand ${call('PUT', f'/projects/{pid}/dev-budget', {'contingency': {'hard': 0.1, 'soft': 0.1}, 'lines': [{'category': 'acquisition', 'description': 'Land', 'unit_cost': 60_000, 'quantity': 1}, {'category': 'hard', 'description': 'Foundation / footing', 'unit_cost': 28_000, 'quantity': 1}, {'category': 'hard', 'description': 'Airform + shotcrete shell ($/sf)', 'unit_cost': 95, 'quantity': 2164}, {'category': 'hard', 'description': 'Rebar + insulation', 'unit_cost': 42_000, 'quantity': 1}, {'category': 'hard', 'description': 'Interior fit-out', 'unit_cost': 80_000, 'quantity': 1}, {'category': 'soft', 'description': 'Design + permits', 'unit_cost': 35_000, 'quantity': 1}]})['summary']['grand_total']:,.0f}")
run("sources & uses", lambda: (lambda su: f"uses ${su['total_uses']:,.0f} ({'balanced' if su['balanced'] else 'UNBALANCED'})")(call("GET", f"/projects/{pid}/sources-uses")))
cl = run("budget -> cost lines", lambda: call("GET", f"/projects/{pid}/dev-budget/cost-lines")["cost_lines"])
if cl:
    a = {"timing": {"construction_months": 9, "hold_years": 10}, "cost_lines": cl, "debt": {"ltc": 0.6, "rate": 0.07},
         "equity": {"lp_pct": 0.8, "gp_pct": 0.2}, "operations": {"potential_rent_annual": 42_000, "opex_annual": 9_000, "stabilized_occ": 0.95, "reserves_annual": 1_500},
         "exit": {"exit_cap": 0.06}, "waterfall": {"pref_rate": 0.08, "tiers": [{"hurdle": None, "lp": 0.8, "gp": 0.2}]}}
    run("solve proforma", lambda: (lambda s: f"IRR {(s['result']['returns'].get('equity_irr') or 0)*100:.1f}% · guardrails {len(s['result'].get('guardrails', {}).get('flags', []))}")(call("POST", "/proforma/scenarios", {"name": "Dome Base", "project_id": pid, "assumptions": a})))
run("investment memo (PDF)", lambda: f"{len(call('GET', f'/projects/{pid}/investment-memo.pdf', raw=True)):,} bytes")

# ============================================================================
phase("2", "Construction")
rfi = run("RFI (submit->respond)", lambda: new("rfi", {"subject": "Airform anchor spacing", "question": "Confirm base anchor spacing.", "discipline": "Structural"}, "consultant"))
if rfi:
    run("  submit", lambda: act("rfi", rfi, "submit") or "open"); run("  respond", lambda: act("rfi", rfi, "respond") or "answered")
run("submittal (shotcrete mix)", lambda: new("submittal", {"title": "Shotcrete mix design", "spec_section": "03 37 00"}, "sub"))
run("daily report", lambda: new("daily_report", {"report_date": "2026-09-01", "weather": "Clear"}))
insp = run("inspection (fail->NCR)", lambda: new("inspection", {"subject": "Shell thickness", "date": "2026-09-10", "result": "Fail"}, "qa"))
if insp:
    run("  fail", lambda: act("inspection", insp, "fail") or "failed")
    run("  NCR", lambda: new("ncr", {"subject": "Thin spot at crown", "description": "Shell under spec at apex", "severity": "Major", "inspection": insp}, "sub"))
run("safety incident", lambda: new("incident", {"subject": "Near miss - spray rig", "date": "2026-09-11", "classification": "Near Miss", "severity": "Near Miss"}, "safety"))
run("SOV + G703", lambda: (new("sov", {"item_no": "01", "description": "Shell", "scheduled_value": 205_000, "completed_this": 100_000, "retainage_pct": 5}), f"${call('GET', f'/projects/{pid}/cost/g703')['totals']['scheduled']:,.0f}")[1])

# ============================================================================
phase("3", "Furnish the home")
fams = ["sofa", "bed", "table", "chair", "fridge", "range", "sink", "toilet", "tree"]
placed = []
for i, fam in enumerate(fams):
    ang = i / len(fams) * 6.28
    pos = [round(4 * (1 if i % 2 else -1) * (i / len(fams)), 1), round(2.0 + i * 0.4, 1)]
    r = run(f"place {fam}", lambda fam=fam, pos=pos: edit("add_family", {"family": fam, "storey": "Ground floor", "position": pos}).get("changed"))
    if r:
        placed.append(fam)
run("publish furnished model", lambda: (edit("add_family", {"family": "planter", "position": [0, 0]}, publish=True), wait_publish())[1])
run("verify furniture in model", lambda: _furniture_count())

# ============================================================================
phase("4", "Turnover")
pl = run("punchlist (open->verify)", lambda: new("punchlist", {"description": "Seal skylight ring", "location": "Apex", "severity": "Minor"}))
if pl:
    run("  ready", lambda: act("punchlist", pl, "ready_to_inspect") or "ready")
    run("  evidence", lambda: upload("punchlist", pl, "done.txt", b"sealed") and "attached")
    run("  verify", lambda: act("punchlist", pl, "verify") or "verified")
run("COBie export", lambda: f"{len(call('GET', f'/projects/{pid}/exports/cobie.xlsx', raw=True)):,} bytes")
run("QTO export", lambda: f"{len(call('GET', f'/projects/{pid}/exports/qto.xlsx', raw=True)):,} bytes")


# ============================================================================
print("\n" + "=" * 70)
by = {}
for ph, _, st, _ in results:
    b = by.setdefault(ph, [0, 0]); b[0 if st == "PASS" else 1] += 1
tp = sum(b[0] for b in by.values()); tf = sum(b[1] for b in by.values())
print(f"E2E EARTH DOME - {tp} passed, {tf} failed across {len(by)} phases")
for ph in sorted(by):
    p, f = by[ph]; print(f"  phase {ph}: {p} pass / {f} fail")
if tf:
    print("\nFAILURES:")
    for ph, name, st, det in results:
        if st == "FAIL":
            print(f"  [{ph}] {name}: {det}")
try:
    print(f"\nproject: {pid}\nsource_ifc: {call('GET', f'/projects/{pid}')['source_ifc']}")
except Exception:
    pass
