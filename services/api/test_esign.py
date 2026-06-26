"""PDF e-signatures — PAdES digital signing + status gating + the digital-sign endpoint.
Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_esign.py"""
import io
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_esign.db"
os.environ["STORAGE_DIR"] = "./test_storage_esign"
os.environ.pop("AEC_RBAC", None)
os.environ.pop("ESIGN_PROVIDER", None)
for f in ("./test_esign.db",):
    if os.path.exists(f):
        os.remove(f)

import pypdf                                                 # noqa: E402
from fastapi.testclient import TestClient                    # noqa: E402
from aec_api.main import app                                 # noqa: E402
from aec_api import esign, esign_bridge                      # noqa: E402


def _sig_fields(pdf: bytes):
    f = pypdf.PdfReader(io.BytesIO(pdf)).get_fields() or {}
    return [k for k, v in f.items() if getattr(v, "get", lambda *_: None)("/FT") == "/Sig"]


# --- unit: PAdES signing + status -------------------------------------------
from reportlab.lib.pagesizes import letter                   # noqa: E402
from reportlab.pdfgen import canvas                          # noqa: E402
_b = io.BytesIO(); _c = canvas.Canvas(_b, pagesize=letter); _c.drawString(72, 720, "Agreement"); _c.save()
plain = _b.getvalue()
signed = esign.digitally_sign(plain, reason="Executed", name="Pat GC")
assert signed[:4] == b"%PDF" and len(signed) > len(plain), "signed PDF should be valid + larger"
assert _sig_fields(signed) == ["AECSignature"], "expected an embedded PAdES signature field"
assert not _sig_fields(plain), "plain PDF has no signature"
fp = esign.signer_fingerprint()
assert len(fp) == 32 and fp == esign.signer_fingerprint(), "fingerprint stable"
assert esign.status()["available"] is True and esign.status()["kind"] == "self-signed"
assert esign_bridge.is_enabled() is False and esign_bridge.status()["enabled"] is False

# --- integration: endpoints --------------------------------------------------
with TestClient(app) as c:
    st = c.get("/esign/status").json()
    assert st["pades"]["available"] is True and st["bridge"]["enabled"] is False, st

    pid = c.post("/projects", json={"name": "Sign Tower"}).json()["id"]
    sc = c.post(f"/projects/{pid}/modules/subcontract",
                json={"data": {"vendor": "ACME Concrete", "trade": "Concrete", "value": 1_800_000}}).json()["id"]

    r = c.post(f"/projects/{pid}/contracts/subcontract/{sc}/digital-sign", json={})
    assert r.status_code == 200, r.text[:200]
    out = r.json()
    assert out["signed"] is True and len(out["fingerprint"]) == 32 and out["kind"] == "self-signed", out

    rec = c.get(f"/projects/{pid}/modules/subcontract/{sc}").json()
    atts = rec.get("attachments", [])
    assert any(a.get("filename", "").startswith("agreement-signed-") for a in atts), atts
    ds = (rec.get("data") or {}).get("digital_signatures") or []
    assert len(ds) == 1 and ds[0]["fingerprint"] == out["fingerprint"] and ds[0]["doc"] == "agreement", ds

print("ESIGN OK - PAdES signature embedded + detected; stable cert fingerprint; status gating "
      "(self-signed available, 3rd-party bridge off); digital-sign attaches signed PDF + records signer")
