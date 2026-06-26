"""3rd-party e-signature bridge — OPTIONAL, feature-flagged (off unless ESIGN_PROVIDER + creds set).

Self-hosted PAdES (esign.py) already covers tamper-evident execution at no cost / fully offline. This
bridge is for *legally-binding, multi-party* signing workflows when a project requires them, via a
SaaS (DocuSign / Adobe Acrobat Sign / Dropbox Sign) or a self-hosted open-source platform
(DocuSeal / Documenso / OpenSign). Like aps.py: gates are testable without credentials and the actual
send raises an actionable error until a provider is provisioned. See docs/esign-options.md.
"""
from __future__ import annotations

import os
from typing import Any

_PROVIDERS = {
    "docusign": "DocuSign",
    "adobe": "Adobe Acrobat Sign",
    "dropbox": "Dropbox Sign",
    "docuseal": "DocuSeal (self-hosted)",
    "documenso": "Documenso (self-hosted)",
    "opensign": "OpenSign (self-hosted)",
}


def provider() -> str | None:
    p = os.environ.get("ESIGN_PROVIDER", "").strip().lower()
    return p or None


def is_enabled() -> bool:
    """A provider is configured with at least an API key or a self-hosted base URL."""
    return bool(provider() in _PROVIDERS and (os.environ.get("ESIGN_API_KEY") or os.environ.get("ESIGN_BASE_URL")))


def status() -> dict[str, Any]:
    p = provider()
    return {
        "enabled": is_enabled(),
        "provider": _PROVIDERS.get(p or "", None),
        "providers_supported": list(_PROVIDERS.values()),
        "message": (f"{_PROVIDERS[p]} bridge configured." if is_enabled() else
                    "3rd-party e-signature bridge not configured. Self-hosted PAdES digital signatures "
                    "are available now; set ESIGN_PROVIDER (+ ESIGN_API_KEY / ESIGN_BASE_URL) to route "
                    "legally-binding multi-party signing through DocuSign / Dropbox Sign / DocuSeal / etc."),
    }


def send_for_signature(pdf: bytes, signers: list[dict], subject: str) -> dict[str, Any]:
    """Send a document for signature through the configured provider. Not wired until provisioned —
    the provider's REST flow (create envelope/submission → add signers → send → webhook on completion)
    is implemented per deployment so we don't ship dead provider SDKs."""
    if not is_enabled():
        raise RuntimeError("No e-signature provider configured (set ESIGN_PROVIDER + credentials).")
    raise NotImplementedError(
        f"The {_PROVIDERS[provider()]} signing flow runs in a credentialed deployment; wire its "
        "envelope/submission API here. Until then, use the built-in PAdES digital signature.")
