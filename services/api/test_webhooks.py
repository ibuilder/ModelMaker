"""Outbound webhooks: a module transition fires a JSON POST to configured URLs (fail-open, opt-in).
Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_webhooks.py"""
import json
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_webhooks.db"
os.environ["STORAGE_DIR"] = "./test_storage_webhooks"
os.environ.pop("AEC_RBAC", None)
os.environ["AEC_WEBHOOK_URLS"] = "http://hook.example/a, http://hook.example/b"
os.environ["AEC_WEBHOOK_SYNC"] = "1"             # deliver synchronously so the test is deterministic
for _f in ("./test_webhooks.db",):
    if os.path.exists(_f):
        os.remove(_f)

from fastapi.testclient import TestClient   # noqa: E402
from aec_api import webhooks                # noqa: E402
from aec_api.main import app               # noqa: E402

# capture deliveries instead of hitting the network
SENT: list[tuple[str, dict]] = []
webhooks._send = lambda url, body: SENT.append((url, json.loads(body)))   # type: ignore

with TestClient(app) as c:
    pid = c.post("/projects", json={"name": "Hooked"}).json()["id"]
    rid = c.post(f"/projects/{pid}/modules/rfi",
                 json={"data": {"subject": "S", "question": "Q"}}).json()["id"]
    SENT.clear()
    r = c.post(f"/projects/{pid}/modules/rfi/{rid}/transition", json={"action": "submit"})
    assert r.status_code == 200 and r.json()["workflow_state"] == "open", r.text[:160]

    # both configured URLs received a record.transition payload
    assert len(SENT) == 2, SENT
    urls = sorted(u for u, _ in SENT)
    assert urls == ["http://hook.example/a", "http://hook.example/b"], urls
    payload = SENT[0][1]
    assert payload["event"] == "record.transition", payload
    assert payload["module"] == "rfi" and payload["action"] == "submit", payload
    assert payload["from"] == "draft" and payload["to"] == "open", payload
    assert payload["project_id"] == pid and payload.get("ref"), payload

    # fail-open: a throwing endpoint must not break the transition
    def boom(url, body):
        raise RuntimeError("endpoint down")
    webhooks._send = boom   # type: ignore
    r2 = c.post(f"/projects/{pid}/modules/rfi/{rid}/transition", json={"action": "void"})
    assert r2.status_code == 200 and r2.json()["workflow_state"] == "void", r2.text[:160]

# no URLs configured -> dispatch is a no-op (returns 0)
os.environ.pop("AEC_WEBHOOK_URLS", None)
assert webhooks.dispatch("x", {"a": 1}) == 0

print("WEBHOOKS OK - transition fired record.transition to both URLs (event/module/action/from/to/ref "
      "present); fail-open on a throwing endpoint; no-op when unconfigured")
