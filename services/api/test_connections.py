"""Data-source connections (admin). Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_connections.py"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./conn_test.db"
os.environ["STORAGE_DIR"] = "./test_storage"
os.environ.pop("AEC_RBAC", None)
for f in ("./conn_test.db",):
    if os.path.exists(f):
        os.remove(f)

from fastapi.testclient import TestClient  # noqa: E402
from aec_api.main import app  # noqa: E402

BEARER = lambda t: {"Authorization": f"Bearer {t}"}  # noqa: E731

with TestClient(app) as c:
    assert c.get("/connections").status_code == 403                      # admin-gated
    tok = c.post("/auth/register", json={"username": "admin", "password": "supersecret"}).json()
    tok = c.post("/auth/login", json={"username": "admin", "password": "supersecret"}).json()["token"]

    # built-in local DB appears with a live OK status + table count
    lst = c.get("/connections", headers=BEARER(tok)).json()
    assert "procore" in lst["types"] and "supabase" in lst["types"]
    local = next(x for x in lst["connections"] if x["id"] == "local")
    assert local["builtin"] and local["status"]["ok"] and "table" in local["status"]["detail"], local

    # register a Postgres connection — DSN password is masked on read
    pg = c.post("/connections", headers=BEARER(tok),
                json={"name": "Reporting DB", "type": "postgres",
                      "config": {"dsn": "postgresql://user:secretpw@db.example.com:5432/reports"}}).json()
    assert "***" in pg["config"]["dsn"] and "secretpw" not in pg["config"]["dsn"], pg["config"]
    # testing it fails gracefully (host unreachable) — no exception
    t = c.post(f"/connections/{pg['id']}/test", headers=BEARER(tok)).json()
    assert t["status"]["ok"] is False and t["status"]["detail"], t

    # Supabase is a Postgres DSN; Procore is token-based — secret never echoed
    proc = c.post("/connections", headers=BEARER(tok),
                  json={"name": "Procore", "type": "procore", "config": {"access_token": "tok-123"}}).json()
    assert proc["config"].get("access_token_set") is True and "access_token" not in proc["config"], proc["config"]

    # ad-hoc test of the local type (used by the add form)
    assert c.post("/connections/test", headers=BEARER(tok), json={"type": "local", "config": {}}).json()["ok"]

    # update keeps the secret when the form re-sends it blank
    upd = c.put(f"/connections/{proc['id']}", headers=BEARER(tok),
                json={"name": "Procore (prod)", "type": "procore", "config": {"access_token": ""}}).json()
    assert upd["name"] == "Procore (prod)" and upd["config"]["access_token_set"] is True

    # validation: 'local' can't be created; unknown type rejected
    assert c.post("/connections", headers=BEARER(tok), json={"name": "x", "type": "local"}).status_code == 400
    assert c.post("/connections", headers=BEARER(tok), json={"name": "x", "type": "mysql"}).status_code == 400

    # delete
    assert c.delete(f"/connections/{pg['id']}", headers=BEARER(tok)).json()["ok"]
    ids = {x["id"] for x in c.get("/connections", headers=BEARER(tok)).json()["connections"]}
    assert pg["id"] not in ids and proc["id"] in ids

    # --- data plane: read-only browse / query on the local app DB --------------
    tbls = c.get("/connections/local/tables", headers=BEARER(tok)).json()
    assert tbls["kind"] == "sql" and "users" in tbls["tables"], tbls
    # a real SELECT returns rows (we registered users above)
    q = c.post("/connections/local/query", headers=BEARER(tok),
               json={"sql": "SELECT username, role FROM users", "limit": 50}).json()
    assert "username" in q["columns"] and q["row_count"] >= 1, q
    # the LIMIT is enforced even if the query omits it
    q2 = c.post("/connections/local/query", headers=BEARER(tok),
                json={"sql": "SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3", "limit": 2}).json()
    assert q2["row_count"] == 2, q2
    # security: writes / DDL / multiple statements are rejected
    for bad in ("DELETE FROM users", "DROP TABLE users", "UPDATE users SET role='admin'",
                "SELECT 1; DROP TABLE users", "INSERT INTO users VALUES ('x')"):
        r = c.post("/connections/local/query", headers=BEARER(tok), json={"sql": bad}).json()
        assert "error" in r and "rows" not in r, (bad, r)
    assert c.post("/connections/local/query", headers=BEARER(tok),
                  json={"sql": "SELECT 1"}).status_code == 200
    # data-plane is admin-gated too (clear the login cookie so the request is truly unauthenticated)
    c.cookies.clear()
    assert c.get("/connections/local/tables").status_code == 403

    # --- Procore → module sync: RFIs + submittals + change events (idempotent) --
    from aec_api import connectors as _conn
    _conn.procore_rfis = lambda token, ppid: [
        {"id": 101, "number": "1", "subject": "Beam penetration", "questions": [{"body": "OK to core?"}]},
        {"id": 102, "number": "2", "subject": "Slab edge", "body": "Confirm dimension?"}]
    _conn.procore_submittals = lambda token, ppid: [
        {"id": 201, "number": "S-1", "title": "Rebar shop drawings", "specification_section": "03 20 00",
         "type": "Shop Drawing", "status": "Open"}]
    _conn.procore_change_events = lambda token, ppid: [
        {"id": 301, "number": "CE-1", "title": "Added fireproofing",
         "change_event_line_items": [{"amount": 12000}, {"amount": 3000}]}]
    pc = c.post("/connections", headers=BEARER(tok),
                json={"name": "Procore sync", "type": "procore", "config": {"access_token": "tok-xyz"}}).json()
    proj = c.post("/projects", json={"name": "Sync Target"}).json()["id"]
    s1 = c.post(f"/projects/{proj}/sync/procore", headers=BEARER(tok),
                json={"connection_id": pc["id"], "procore_project_id": "9999"}).json()
    assert s1["imported_total"] == 4, s1                                              # 2 rfi + 1 sub + 1 ce
    assert s1["results"]["rfi"]["imported"] == 2 and s1["results"]["submittal"]["imported"] == 1
    assert s1["results"]["change_event"]["imported"] == 1, s1["results"]
    # mappings landed in the right modules
    assert any("core" in (x["data"].get("question") or "") for x in c.get(f"/projects/{proj}/modules/rfi").json())
    subs = c.get(f"/projects/{proj}/modules/submittal").json()
    assert subs[0]["data"]["spec_section"] == "03 20 00" and subs[0]["data"]["procore_id"] == "201", subs
    ces = c.get(f"/projects/{proj}/modules/change_event").json()
    assert ces[0]["data"]["rom"] == 15000.0, ces                                      # summed line items
    # idempotent re-run
    s2 = c.post(f"/projects/{proj}/sync/procore", headers=BEARER(tok),
                json={"connection_id": pc["id"], "procore_project_id": "9999"}).json()
    assert s2["imported_total"] == 0, s2
    # a non-Procore connection can't be used for the Procore sync
    assert c.post(f"/projects/{proj}/sync/procore", headers=BEARER(tok),
                  json={"connection_id": "local", "procore_project_id": "1"}).status_code in (400, 404)

    # --- scheduled / auto-sync ------------------------------------------------
    sch = c.post(f"/projects/{proj}/sync/schedules", headers=BEARER(tok),
                 json={"connection_id": pc["id"], "procore_project_id": "9999", "kinds": ["rfi"],
                       "interval_minutes": 30}).json()
    assert sch["enabled"] and sch["interval_minutes"] == 30 and sch["last_run"] is None
    # run_due imports nothing new (already synced) but stamps last_run + last_result
    from aec_api import sync as _sync
    from aec_api.db import SessionLocal as _SL
    with _SL() as _db:
        ran = _sync.run_due(_db)
    assert any(r["schedule_id"] == sch["id"] for r in ran), ran
    after = next(x for x in c.get(f"/projects/{proj}/sync/schedules", headers=BEARER(tok)).json() if x["id"] == sch["id"])
    assert after["last_run"] is not None and after["last_result"]["imported_total"] == 0, after
    # a second run_due immediately is NOT due (interval not elapsed)
    with _SL() as _db:
        assert _sync.run_due(_db) == []
    # disable + delete
    assert c.put(f"/projects/{proj}/sync/schedules/{sch['id']}", headers=BEARER(tok),
                 json={"enabled": False}).json()["enabled"] is False
    assert c.delete(f"/projects/{proj}/sync/schedules/{sch['id']}", headers=BEARER(tok)).json()["ok"]

    print("CONNECTIONS OK — status, masked secrets, test, CRUD, validation, read-only browse/query, "
          "Procore->rfi/submittal/change_event sync (idempotent), auto-sync schedules + run_due")
