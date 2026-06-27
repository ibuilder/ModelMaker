"""Signed, expiring URLs for direct downloads (model.frag / attachments).

A signed URL lets a viewer, a worker fetch, or a shared deep-link retrieve one specific resource for a
short window without carrying a full session — the signature authorizes exactly that path until it
expires. HMAC-SHA256 over (url-path, expiry) with the auth signing secret; constant-time compare.

Only meaningful when RBAC is on (otherwise downloads are already open). The RBAC gate + the download
handlers both accept a valid signature as an alternative to a session identity.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

from . import auth

DEFAULT_TTL = int(os.environ.get("AEC_SIGNED_URL_TTL", "3600"))   # 1 hour


def _mac(path: str, exp: int) -> str:
    digest = hmac.new(auth.signing_key(), f"{path}|{exp}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def sign_path(path: str, ttl: int = DEFAULT_TTL) -> dict[str, object]:
    """Return a signed URL for `path` (an API URL path) valid for `ttl` seconds."""
    exp = int(time.time()) + ttl
    sig = _mac(path, exp)
    return {"url": f"{path}?sig={sig}&exp={exp}", "sig": sig, "exp": exp, "expires_in": ttl}


def verify_path(path: str, sig: str | None, exp: object) -> bool:
    """True iff `sig` is a valid, unexpired signature for `path`."""
    if not sig or exp is None:
        return False
    try:
        exp_i = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_i < int(time.time()):
        return False
    return hmac.compare_digest(_mac(path, exp_i), sig)
