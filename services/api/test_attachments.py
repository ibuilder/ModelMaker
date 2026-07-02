"""Module-record attachment download. Regression for the route-collision bug: bim.py's
/attachments/{id}/download (Attachment table, registered first) shadowed the module-record handler
(RecordAttachment table) and 404'd every portal image thumbnail. The module attachment now lives at a
distinct /module-attachments/{id}/download path.
Run: PYTHONPATH=src ./.venv/Scripts/python.exe test_attachments.py"""
import io
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_attachments.db"
os.environ["STORAGE_DIR"] = "./test_storage_attachments"
os.environ.pop("AEC_RBAC", None)
for _f in ("./test_attachments.db",):
    if os.path.exists(_f):
        os.remove(_f)

from fastapi.testclient import TestClient     # noqa: E402
from aec_api.main import app                  # noqa: E402

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)    # enough bytes to stand in for an image

with TestClient(app) as c:
    pid = c.post("/projects", json={"name": "Att"}).json()["id"]
    rid = c.post(f"/projects/{pid}/modules/rfi",
                 json={"data": {"subject": "Photo test", "question": "see attached"}}).json()["id"]

    up = c.post(f"/projects/{pid}/modules/rfi/{rid}/attachments",
                files={"file": ("site.png", PNG, "image/png")})
    assert up.status_code == 201, up.text[:200]
    aid = up.json()["id"]

    # download at the NEW distinct path -> 200 with the bytes + inline (so <img> renders it)
    dl = c.get(f"/module-attachments/{aid}/download")
    assert dl.status_code == 200, dl.status_code
    assert dl.content == PNG, "bytes round-trip"
    assert dl.headers.get("content-type", "").startswith("image/png"), dl.headers.get("content-type")
    assert "inline" in dl.headers.get("content-disposition", ""), dl.headers.get("content-disposition")
    # CORP header so a COEP-isolated SPA can embed the image cross-origin (else <img> is blocked)
    assert dl.headers.get("cross-origin-resource-policy") == "cross-origin", dict(dl.headers)

    # the OLD shared path routes to bim.py's Attachment-table handler -> 404 for a module attachment id
    # (this is exactly the collision that broke thumbnails; the distinct path above is the fix)
    old = c.get(f"/attachments/{aid}/download")
    assert old.status_code == 404, f"expected the module id to miss bim's Attachment table, got {old.status_code}"

    # the attachment is listed on the record (so the UI knows to render a thumbnail)
    rec = c.get(f"/projects/{pid}/modules/rfi/{rid}").json()
    assert any(a["id"] == aid for a in rec.get("attachments", [])), rec.get("attachments")

print("ATTACHMENTS OK - module-record attachment uploads + downloads at /module-attachments/{id}/download "
      "(200, bytes round-trip, image/png, inline disposition); the old /attachments/{id}/download path "
      "correctly 404s for a module id (bim.py's Attachment-table route no longer shadows thumbnails)")
