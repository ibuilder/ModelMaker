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
    members = c.get(f"/projects/{pid}/members", headers=BEARER(tok))
    assert members.status_code == 200
    # hardening response headers are present on every response
    h = members.headers
    assert h.get("X-Content-Type-Options") == "nosniff", h
    assert h.get("X-Frame-Options") == "DENY" and "frame-ancestors" in h.get("Content-Security-Policy", ""), h

    c.cookies.clear()    # drop alice's login cookie so the next calls carry no real identity
    # an attacker tries to impersonate alice with just the X-User header (no token) → ignored in
    # production → no valid identity → denied (401 from the RBAC gate, was a spoofing hole before)
    spoof = c.get(f"/projects/{pid}/members", headers={"X-User": "alice"})
    assert spoof.status_code in (401, 403), f"X-User must not be trusted, got {spoof.status_code}"
    assert c.get(f"/projects/{pid}/members").status_code in (401, 403)   # bare request denied too

    # RBAC defense-in-depth gate: the (otherwise un-guarded) finance + properties surfaces are NOT
    # reachable anonymously when RBAC is on — previously these had no auth dependency at all.
    assert c.get(f"/projects/{pid}/dev-budget").status_code == 401, "finance must require auth under RBAC"
    assert c.get(f"/projects/{pid}/financials").status_code == 401
    assert c.post(f"/projects/{pid}/properties/index", files={"file": ("p.json", b"{}", "application/json")}).status_code == 401
    # …but with a valid token the owner reaches them (gate passes; 200 or a clean 404 when no data)
    assert c.get(f"/projects/{pid}/dev-budget", headers=BEARER(tok)).status_code == 200

    # oversized uploads are rejected by the body-size cap (Content-Length check → 413)
    big = c.post(f"/projects/{pid}/properties/index", headers={**BEARER(tok), "Content-Length": str(99 * 1024**3)},
                 files={"file": ("p.json", b"{}", "application/json")})
    assert big.status_code == 413, f"oversized upload should be 413, got {big.status_code}"

print("SECURITY OK - X-User not trusted under RBAC; hardening headers present; RBAC gate blocks "
      "anonymous finance/properties (401); oversized upload -> 413; default signing-secret detected")
