"""Data-source connectors — treat external systems as connectable sources alongside the app's
own database. Each type exposes test() (validate credentials/reachability) and info() (a small
status payload). The adapter pattern is the seam for later mapping external data into the app.

Types:
  local      the app's own database (status only)
  postgres   any PostgreSQL DSN
  supabase   a Supabase project's PostgreSQL DSN (Supabase's DB is Postgres)
  procore    Procore REST API via an access token (a data source, not a SQL DB)

Secrets in a connection's config (DSN password, Procore access token) are masked on read."""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

TYPES = ("local", "postgres", "supabase", "procore")


def _mask_dsn(dsn: str) -> str:
    return re.sub(r"(://[^:/@]+:)[^@/]+(@)", r"\1***\2", dsn or "")


def public_config(ctype: str, config: dict | None) -> dict:
    """Config safe to return to the client — secrets redacted."""
    c = dict(config or {})
    if "dsn" in c:
        c["dsn"] = _mask_dsn(c["dsn"])
    if "access_token" in c:
        c["access_token_set"] = bool(c.pop("access_token"))
    return c


def _normalize_dsn(dsn: str) -> str:
    """Use the installed psycopg (v3) driver for plain postgres URLs (incl. Supabase) so a
    pasted `postgresql://…` / `postgres://…` connects without psycopg2."""
    for prefix in ("postgresql://", "postgres://"):
        if dsn.startswith(prefix):
            return "postgresql+psycopg://" + dsn[len(prefix):]
    return dsn


def _test_sql(dsn: str) -> dict[str, Any]:
    from sqlalchemy import create_engine
    if not dsn:
        return {"ok": False, "detail": "no connection string"}
    dsn = _normalize_dsn(dsn)
    args = {"connect_timeout": 6} if "postgresql" in dsn else {}
    eng = None
    try:
        eng = create_engine(dsn, connect_args=args, pool_pre_ping=True)
        with eng.connect() as c:
            ver = c.exec_driver_sql("SELECT version()" if "postgres" in dsn else "SELECT sqlite_version()").scalar()
        return {"ok": True, "detail": str(ver)[:90]}
    except ModuleNotFoundError as e:             # postgres driver not installed in this image
        return {"ok": False, "detail": f"{e} — install the PostgreSQL driver (psycopg) on the server"}
    except Exception as e:                       # noqa: BLE001 — surface any connect failure
        return {"ok": False, "detail": str(e).splitlines()[0][:140]}
    finally:
        if eng is not None:
            eng.dispose()


def _test_local(_config: dict) -> dict[str, Any]:
    from sqlalchemy import inspect, text

    from .db import engine
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        n = len(inspect(engine).get_table_names())
        return {"ok": True, "detail": f"{engine.dialect.name} · {n} tables"}
    except Exception as e:                       # noqa: BLE001
        return {"ok": False, "detail": str(e)[:140]}


def _procore_get(path: str, token: str) -> Any:
    req = urllib.request.Request(f"https://api.procore.com{path}",
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:  # noqa: S310 — fixed Procore host
        return json.loads(r.read().decode())


def _test_procore(config: dict) -> dict[str, Any]:
    token = (config or {}).get("access_token")
    if not token:
        return {"ok": False, "detail": "no access token"}
    try:
        me = _procore_get("/rest/v1.0/me", token)
        who = me.get("login") or me.get("name") or me.get("email_address") or "connected"
        return {"ok": True, "detail": f"Procore · {who}"}
    except Exception as e:                       # noqa: BLE001
        return {"ok": False, "detail": str(e)[:140]}


def test(ctype: str, config: dict | None) -> dict[str, Any]:
    config = config or {}
    if ctype == "local":
        return _test_local(config)
    if ctype in ("postgres", "supabase"):
        return _test_sql(config.get("dsn", ""))
    if ctype == "procore":
        return _test_procore(config)
    return {"ok": False, "detail": f"unknown connection type {ctype!r}"}


def info(ctype: str, config: dict | None) -> dict[str, Any]:
    """A small status payload for the connection card. For Procore, lists a few projects."""
    config = config or {}
    if ctype == "procore" and config.get("access_token"):
        try:
            projects = _procore_get("/rest/v1.0/projects", config["access_token"])
            names = [p.get("name") for p in (projects or [])[:5] if isinstance(p, dict)]
            return {"projects": names, "project_count": len(projects or [])}
        except Exception:                        # noqa: BLE001
            return {}
    return {}
