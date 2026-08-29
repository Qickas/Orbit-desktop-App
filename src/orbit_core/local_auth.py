"""Local Core credential access for the Desktop host.

The Desktop host shares the credential namespace with the canonical Core.
Credentials are loaded lazily from the OS keyring and are never returned in
errors or representations.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Protocol


LOCAL_CLIENT_SERVICE = "orbit-core.local-client-auth"
LOCAL_CLIENT_ACCOUNT = "loopback-core"
LOCAL_CLIENT_REVOKED_ACCOUNT = "loopback-core.revoked"
REVOCATION_MARKER = "revoked"


class LocalCredentialError(RuntimeError):
    """A token-free credential-store or authentication failure."""


class CredentialBackend(Protocol):
    def get_password(self, service: str, account: str) -> str | None: ...

    def set_password(self, service: str, account: str, value: str) -> None: ...


class KeyringBackend:
    """Lazy OS-keyring adapter; importing this module never touches keyring."""

    def __init__(self) -> None:
        try:
            import keyring
            from keyring.backends.fail import Keyring as FailKeyring

            backend = keyring.get_keyring()
        except Exception:
            raise LocalCredentialError("OS credential store is unavailable.") from None
        if isinstance(backend, FailKeyring):
            raise LocalCredentialError("OS credential store is unavailable.")
        self._backend = keyring

    def get_password(self, service: str, account: str) -> str | None:
        try:
            return self._backend.get_password(service, account)
        except Exception:
            raise LocalCredentialError("OS credential store is unavailable.") from None

    def set_password(self, service: str, account: str, value: str) -> None:
        try:
            self._backend.set_password(service, account, value)
        except Exception:
            raise LocalCredentialError("OS credential store is unavailable.") from None


class LocalCoreCredential:
    """Load or provision the shared local Core credential."""

    def __init__(self, backend: CredentialBackend | None = None) -> None:
        self._backend = backend or KeyringBackend()

    def load_or_provision(self) -> str:
        if self._read(LOCAL_CLIENT_REVOKED_ACCOUNT) == REVOCATION_MARKER:
            raise LocalCredentialError("Local Core credential is revoked.")

        current = self._read(LOCAL_CLIENT_ACCOUNT)
        if current:
            return current

        token = secrets.token_urlsafe(32)
        self._write(LOCAL_CLIENT_ACCOUNT, token)
        read_back = self._read(LOCAL_CLIENT_ACCOUNT)
        if not read_back or not hmac.compare_digest(read_back, token):
            raise LocalCredentialError("Credential read-back verification failed.")
        return token

    def _read(self, account: str) -> str | None:
        return self._backend.get_password(LOCAL_CLIENT_SERVICE, account)

    def _write(self, account: str, value: str) -> None:
        if not value:
            raise LocalCredentialError("Credential value must not be empty.")
        self._backend.set_password(LOCAL_CLIENT_SERVICE, account, value)


class LocalCoreAuthenticator:
    """Validate exactly one Bearer header in constant time."""

    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("Local Core credential must not be empty.")
        self._token = token

    def accepts(self, values: list[str]) -> bool:
        if len(values) != 1:
            return False
        scheme, separator, candidate = values[0].partition(" ")
        return (
            scheme == "Bearer"
            and separator == " "
            and bool(candidate)
            and not any(character.isspace() for character in candidate)
            and hmac.compare_digest(candidate, self._token)
        )

    def __repr__(self) -> str:
        return "LocalCoreAuthenticator(<redacted>)"
