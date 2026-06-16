"""Authentication: password hashing + signed bearer tokens (stdlib only — no extra deps).

Identity layer under the existing project RBAC: a token says *who* you are (replacing the
dev `X-User` header); per-project authorization still comes from `ProjectMember`. Passwords
are PBKDF2-HMAC-SHA256 salted hashes; tokens are HMAC-SHA256 signed `payload.sig` (JWT-ish,
but dependency-free)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

_PBKDF2_ROUNDS = 200_000
# token signing secret — set AEC_AUTH_SECRET (or AEC_API_KEY) in prod; dev default is insecure
_SECRET = (os.environ.get("AEC_AUTH_SECRET") or os.environ.get("AEC_API_KEY")
           or "dev-insecure-secret").encode()
_TOKEN_TTL = 7 * 24 * 3600   # 7 days


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, salt_hex, dk_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), _PBKDF2_ROUNDS)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def create_token(sub: str, ttl: int = _TOKEN_TTL) -> str:
    payload = _b64(json.dumps({"sub": sub, "exp": int(time.time()) + ttl}).encode())
    sig = _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: str) -> str | None:
    """Return the subject (username) if the token is well-signed and unexpired, else None."""
    try:
        payload_b64, sig_b64 = token.split(".")
        expected = _b64(hmac.new(_SECRET, payload_b64.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig_b64, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
        if payload.get("exp", 0) < time.time():
            return None
        return payload.get("sub")
    except Exception:
        return None
