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


_RESET_TTL = 3600   # password-reset tokens are short-lived (1 hour)


def create_token(sub: str, ttl: int = _TOKEN_TTL) -> str:
    payload = _b64(json.dumps({"sub": sub, "exp": int(time.time()) + ttl}).encode())
    sig = _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: str) -> str | None:
    """Return the subject (username) if the token is a well-signed, unexpired *auth* token.
    Reset tokens (purpose='reset') are rejected here so they can't be used as bearer tokens."""
    try:
        payload_b64, sig_b64 = token.split(".")
        expected = _b64(hmac.new(_SECRET, payload_b64.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig_b64, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
        if payload.get("exp", 0) < time.time():
            return None
        if payload.get("purpose") not in (None, "auth"):
            return None
        return payload.get("sub")
    except Exception:
        return None


def _pw_fingerprint(pw_hash: str) -> str:
    """A short, secret-keyed fingerprint of the stored password hash. Embedding it in a reset
    token makes the token single-use: once the password changes, the hash (and fingerprint)
    change, so any outstanding reset token stops validating."""
    return _b64(hmac.new(_SECRET, b"reset:" + pw_hash.encode(), hashlib.sha256).digest())[:16]


def create_reset_token(sub: str, pw_hash: str, ttl: int = _RESET_TTL) -> str:
    payload = _b64(json.dumps({"sub": sub, "exp": int(time.time()) + ttl,
                               "purpose": "reset", "fp": _pw_fingerprint(pw_hash)}).encode())
    sig = _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def token_subject(token: str) -> str | None:
    """The 'sub' claim WITHOUT verifying the signature — only to look up the account so its
    current password hash can be checked by verify_reset_token. Never trust this for auth."""
    try:
        return json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "==")).get("sub")
    except Exception:
        return None


def verify_reset_token(token: str, pw_hash: str) -> str | None:
    """Return the subject if `token` is a valid, unexpired, single-use reset token for the
    account whose current password hash is `pw_hash`; else None."""
    try:
        payload_b64, sig_b64 = token.split(".")
        expected = _b64(hmac.new(_SECRET, payload_b64.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig_b64, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
        if payload.get("purpose") != "reset" or payload.get("exp", 0) < time.time():
            return None
        if not hmac.compare_digest(payload.get("fp", ""), _pw_fingerprint(pw_hash)):
            return None
        return payload.get("sub")
    except Exception:
        return None
