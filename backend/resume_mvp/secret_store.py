from __future__ import annotations

import hashlib
import sys
from typing import Protocol
from urllib.parse import urlsplit


KEYCHAIN_SERVICE = "cn.resume-evidence-workbench.api"


class SecretStore(Protocol):
    def get(self, account: str) -> str | None: ...

    def set(self, account: str, secret: str) -> None: ...

    def delete(self, account: str) -> None: ...


class MacOSKeychainStore:
    """Store API credentials in the user's login Keychain, never in app files."""

    def __init__(self) -> None:
        if sys.platform != "darwin":
            raise RuntimeError("macOS Keychain is only available on macOS")
        from keyring.backends.macOS import Keyring

        self._backend = Keyring()

    def get(self, account: str) -> str | None:
        return self._backend.get_password(KEYCHAIN_SERVICE, account)

    def set(self, account: str, secret: str) -> None:
        self._backend.set_password(KEYCHAIN_SERVICE, account, secret)

    def delete(self, account: str) -> None:
        # Missing credentials are harmless; denied/locked Keychain access must
        # propagate so the UI never reports deletion when the key remains.
        if self._backend.get_password(KEYCHAIN_SERVICE, account) is None:
            return
        self._backend.delete_password(KEYCHAIN_SERVICE, account)


def provider_key_account(base_url: str) -> str:
    """Return a non-secret, host-scoped Keychain account identifier."""
    parsed = urlsplit(base_url.strip())
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme not in {"http", "https"} or not host:
        raise ValueError("API base URL must be an HTTP(S) URL with a host")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ValueError("API base URL must not contain credentials, query, or fragment")
    port = parsed.port
    if port is None or (scheme == "https" and port == 443) or (scheme == "http" and port == 80):
        origin = f"{scheme}://{host}"
    else:
        origin = f"{scheme}://{host}:{port}"
    digest = hashlib.sha256(origin.encode("utf-8")).hexdigest()
    return f"openai-compatible:{digest}"


def create_platform_secret_store() -> SecretStore | None:
    if sys.platform != "darwin":
        return None
    try:
        return MacOSKeychainStore()
    except Exception:
        # The registry will clearly report memory-only storage to the UI.
        return None
