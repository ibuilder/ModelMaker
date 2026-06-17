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

    print("CONNECTIONS OK — local status, masked secrets, test (graceful), CRUD, validation")
