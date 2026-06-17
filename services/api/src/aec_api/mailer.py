"""Email sending — stdlib smtplib only, no deps. Configured via env; a no-op (logged) when
unconfigured so digests degrade gracefully in dev / unconfigured deployments.

Env:
  AEC_SMTP_HOST            enable sending (unset → disabled, send_email returns "disabled")
  AEC_SMTP_PORT            default 587
  AEC_SMTP_USER / _PASSWORD   optional SMTP auth
  AEC_SMTP_FROM            From address (default no-reply@<host>)
  AEC_SMTP_TLS             "1" (default) → STARTTLS; "0" → plain
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

_log = logging.getLogger("aec.mail")


def smtp_configured() -> bool:
    return bool(os.environ.get("AEC_SMTP_HOST"))


def _from_addr() -> str:
    return os.environ.get("AEC_SMTP_FROM") or f"no-reply@{os.environ.get('AEC_SMTP_HOST', 'localhost')}"


def build_message(to: str, subject: str, body_text: str, body_html: str | None = None) -> EmailMessage:
    """Construct a well-formed (optionally multipart) message — pure, no I/O (testable)."""
    msg = EmailMessage()
    msg["From"] = _from_addr()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body_text)
    if body_html:
        msg.add_alternative(body_html, subtype="html")
    return msg


def send_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> str:
    """Send one message. Returns "sent" | "disabled" | "error". Never raises (so a digest
    run can't be broken by one bad address / transient SMTP failure)."""
    msg = build_message(to, subject, body_text, body_html)
    if not smtp_configured():
        _log.info("email disabled (no AEC_SMTP_HOST) — would send %r to %s", subject, to)
        return "disabled"
    host = os.environ["AEC_SMTP_HOST"]
    port = int(os.environ.get("AEC_SMTP_PORT", "587"))
    try:
        with smtplib.SMTP(host, port, timeout=15) as s:
            if os.environ.get("AEC_SMTP_TLS", "1") == "1":
                s.starttls()
            user, pw = os.environ.get("AEC_SMTP_USER"), os.environ.get("AEC_SMTP_PASSWORD")
            if user and pw:
                s.login(user, pw)
            s.send_message(msg)
        return "sent"
    except Exception as e:           # noqa: BLE001 — one bad send must not abort a batch
        _log.warning("email send failed to %s: %s", to, e)
        return "error"
