from http.client import HTTPConnection
from threading import Thread

from orbit_core.desktop_service import OrbitDesktopRuntime, create_desktop_server
from orbit_core.local_auth import (
    LOCAL_CLIENT_ACCOUNT,
    LOCAL_CLIENT_REVOKED_ACCOUNT,
    LOCAL_CLIENT_SERVICE,
    LocalCoreAuthenticator,
    LocalCoreCredential,
    LocalCredentialError,
    REVOCATION_MARKER,
)
from orbit_core import ChatResponse, ConversationPipeline, MemoryV2


class MemoryBackend:
    def __init__(self, values: dict[tuple[str, str], str | None] | None = None) -> None:
        self.values = values or {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.values.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.values[(service, account)] = value


class FakeProvider:
    model = "test-model"

    def model_available(self) -> bool:
        return True

    def chat(self, messages, *, system=None):
        return ChatResponse(content="ok", model=self.model)


def runtime() -> OrbitDesktopRuntime:
    provider = FakeProvider()
    return OrbitDesktopRuntime(
        provider=provider,
        conversation=ConversationPipeline(provider=provider, memory=MemoryV2()),
    )


def test_first_run_provisions_shared_keyring_namespace_and_reads_back() -> None:
    backend = MemoryBackend()
    token = LocalCoreCredential(backend).load_or_provision()

    assert len(token) >= 40
    assert backend.values[(LOCAL_CLIENT_SERVICE, LOCAL_CLIENT_ACCOUNT)] == token


def test_revoked_marker_fails_closed_without_auto_provision() -> None:
    backend = MemoryBackend({(LOCAL_CLIENT_SERVICE, LOCAL_CLIENT_REVOKED_ACCOUNT): REVOCATION_MARKER})

    try:
        LocalCoreCredential(backend).load_or_provision()
    except LocalCredentialError as error:
        assert str(error) == "Local Core credential is revoked."
    else:
        raise AssertionError("revoked credentials must not auto-provision")


def test_authenticator_is_exact_and_redacted() -> None:
    auth = LocalCoreAuthenticator("secret-token")

    assert auth.accepts(["Bearer secret-token"])
    assert not auth.accepts([])
    assert not auth.accepts(["Bearer wrong", "Bearer secret-token"])
    assert "secret-token" not in repr(auth)


def test_v1_requires_auth_while_healthz_is_liveness_only() -> None:
    server = create_desktop_server(runtime(), port=0, auth=LocalCoreAuthenticator("secret-token"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/healthz")
        health = connection.getresponse()
        assert health.status == 204
        assert health.read() == b""

        connection.request("GET", "/v1/status")
        unauthorized = connection.getresponse()
        assert unauthorized.status == 401
        assert unauthorized.getheader("WWW-Authenticate") == 'Bearer realm="orbit-core"'
        unauthorized.read()

        connection.request("GET", "/v1/status", headers={"Authorization": "Bearer secret-token"})
        authorized = connection.getresponse()
        assert authorized.status == 200
        authorized.read()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_desktop_server_rejects_non_loopback_bind() -> None:
    try:
        create_desktop_server(
            runtime(),
            host="0.0.0.0",
            port=0,
            auth=LocalCoreAuthenticator("secret-token"),
        )
    except ValueError as error:
        assert str(error) == "Orbit Desktop API must bind to loopback only."
    else:
        raise AssertionError("Desktop API must be loopback-only")
