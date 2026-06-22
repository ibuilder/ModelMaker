"""Production-hardening: the X-User header must NOT be trusted as identity in production (RBAC on,
no AEC_TRUST_XUSER), and the auth signing secret defaults are detectable.
Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_security.py"""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_sec.db"
os.environ["STORAGE_DIR"] = "./test_storage_sec"
os.environ["AEC_RBAC"] = "1"                  # production posture
os.environ.pop("AEC_TRUST_XUSER", None)      # do NOT trust the dev impersonation header
os.environ.pop("AEC_AUTH_SECRET", None)
os.environ.pop("AEC_API_KEY", None)
for f in ("./test_sec.db",):
    if os.path.exists(f):
        os.remove(f)

from fastapi.testclient import TestClient  # noqa: E402
from aec_api import auth  # noqa: E402
from aec_api.main import app  # noqa: E402

BEARER = lambda t: {"Authorization": f"Bearer {t}"}  # noqa: E731

with TestClient(app) as c:
    # the public dev signing secret is detected (production must set AEC_AUTH_SECRET)
    assert auth.secret_is_default() is True, "expected default-secret detection"

    # alice signs up (first account → admin) and logs in for a real signed token
    c.post("/auth/register", json={"username": "alice", "password": "supersecret"})
    tok = c.post("/auth/login", json={"username": "alice", "password": "supersecret"}).json()["token"]
    pid = c.post("/projects", json={"name": "Sec"}, headers=BEARER(tok)).json()["id"]

    # with her token, alice (project admin) can read members
    assert c.get(f"/projects/{pid}/members", headers=BEARER(tok)).status_code == 200

    c.cookies.clear()    # drop alice's login cookie so the next calls carry no real identity
    # an attacker tries to impersonate alice with just the X-User header (no token) →
    # ignored in production → treated as anonymous → 403 (was a spoofing hole before)
    spoof = c.get(f"/projects/{pid}/members", headers={"X-User": "alice"})
    assert spoof.status_code == 403, f"X-User must not be trusted in production, got {spoof.status_code}"

    # and a bare request (no identity at all) is likewise denied
    assert c.get(f"/projects/{pid}/members").status_code == 403

print("SECURITY OK - X-User header not trusted under RBAC (no spoofing); token identity required; "
      "default signing-secret detected")
