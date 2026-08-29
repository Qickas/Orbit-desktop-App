import json
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from orbit_core import ChatResponse, ConversationPipeline, MemoryV2
from orbit_core.desktop_service import OrbitDesktopRuntime, create_desktop_server
from orbit_core.local_auth import LocalCoreAuthenticator


AUTH_HEADERS = {"Authorization": "Bearer test-token"}


class FakeProvider:
    model = "test-model"

    def __init__(self, *, running: bool = True) -> None:
        self.running = running

    def model_available(self) -> bool:
        return self.running

    def chat(self, messages, *, system=None):
        return ChatResponse(content=f"Svar: {messages[-1].content}", model=self.model)


class FakeComputer:
    def __init__(self) -> None:
        self.active = False

    def status(self) -> dict[str, object]:
        return {"active": self.active, "remainingSeconds": 600, "targetWindow": "Exempel"}

    def start(self) -> dict[str, object]:
        self.active = True
        return self.status()

    def stop(self) -> dict[str, object]:
        self.active = False
        return self.status()

    def inspect(self) -> dict[str, object]:
        return {"windowTitle": "Exempel", "controls": [{"id": "control-1", "name": "Spara", "type": "Button"}]}

    def click(self, identifier: str) -> dict[str, object]:
        return {"action": "click", "control": identifier, "windowTitle": "Exempel"}

    def type_text(self, identifier: str, text: str) -> dict[str, object]:
        return {"action": "type", "control": identifier, "windowTitle": "Exempel"}


class FakeVoice:
    def synthesize(self, text: str) -> bytes:
        return f"WAV:{text}".encode("utf-8")


def make_runtime(
    *,
    running: bool = True,
    with_voice: bool = False,
    with_computer: bool = False,
) -> OrbitDesktopRuntime:
    provider = FakeProvider(running=running)
    conversation = ConversationPipeline(provider=provider, memory=MemoryV2())
    return OrbitDesktopRuntime(
        provider=provider,
        conversation=conversation,
        voice=FakeVoice() if with_voice else None,
        computer=FakeComputer() if with_computer else None,
    )


def start_server(runtime: OrbitDesktopRuntime, *, web_root: Path | None = None):
    server = create_desktop_server(
        runtime,
        port=0,
        web_root=web_root,
        auth=LocalCoreAuthenticator("test-token"),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_status_reports_the_selected_local_model() -> None:
    server, thread = start_server(make_runtime())
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/v1/status", headers=AUTH_HEADERS)
        response = connection.getresponse()
        payload = json.loads(response.read())
    finally:
        server.shutdown()
        thread.join()

    assert response.status == 200
    assert payload == {
        "runtimeState": "ready",
        "localBrain": {"model": "test-model", "running": True},
        "computerMode": {"active": False},
    }


def test_status_is_degraded_when_the_model_is_unavailable() -> None:
    runtime = OrbitDesktopRuntime(
        provider=FakeProvider(running=True),
        conversation=ConversationPipeline(
            provider=FakeProvider(running=True),
            memory=MemoryV2(),
        ),
        availability_provider=FakeProvider(running=False),
    )

    assert runtime.status()["runtimeState"] == "degraded"
    assert runtime.status()["localBrain"]["running"] is False


def test_health_confirms_that_the_core_server_is_reachable() -> None:
    server, thread = start_server(make_runtime())
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/healthz")
        response = connection.getresponse()
        payload = response.read()
    finally:
        server.shutdown()
        thread.join()

    assert response.status == 204
    assert payload == b""


def test_private_mobile_site_serves_the_built_ui_and_rejects_path_escape(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<title>ORBIT</title>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('orbit')", encoding="utf-8")
    server, thread = start_server(make_runtime(), web_root=tmp_path)
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/")
        home = connection.getresponse()
        home_body = home.read()

        connection.request("GET", "/assets/app.js")
        asset = connection.getresponse()
        asset_body = asset.read()

        connection.request("GET", "/%2e%2e/secret.txt")
        escaped = connection.getresponse()
        escaped.read()
    finally:
        server.shutdown()
        thread.join()

    assert home.status == 200
    assert home.getheader("Cache-Control") == "no-store"
    assert home_body == b"<title>ORBIT</title>"
    assert asset.status == 200
    assert asset_body == b"console.log('orbit')"
    assert escaped.status == 403


def test_conversation_returns_orbit_content() -> None:
    server, thread = start_server(make_runtime())
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request(
            "POST",
            "/v1/conversation",
            body=json.dumps({"text": "Hej Orbit"}),
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
    finally:
        server.shutdown()
        thread.join()

    assert response.status == 200
    assert payload == {"content": "Svar: Hej Orbit", "model": "test-model"}


def test_conversation_rejects_empty_text() -> None:
    server, thread = start_server(make_runtime())
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request(
            "POST",
            "/v1/conversation",
            body=json.dumps({"text": "  "}),
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
    finally:
        server.shutdown()
        thread.join()

    assert response.status == 400
    assert payload == {"error": "Text must be a non-empty string."}


def test_speech_returns_wav_audio() -> None:
    server, thread = start_server(make_runtime(with_voice=True))
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request(
            "POST",
            "/v1/speech",
            body=json.dumps({"text": "Hej Orbit"}),
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
        )
        response = connection.getresponse()
        body = response.read()
    finally:
        server.shutdown()
        thread.join()

    assert response.status == 200
    assert response.getheader("Content-Type") == "audio/wav"
    assert body == b"WAV:Hej Orbit"


def test_computer_mode_routes_start_inspect_and_stop() -> None:
    server, thread = start_server(make_runtime(with_computer=True))
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request(
            "POST",
            "/v1/computer/session",
            body=json.dumps({"action": "start"}),
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
        )
        started = json.loads(connection.getresponse().read())

        connection.request("GET", "/v1/computer/context", headers=AUTH_HEADERS)
        context = json.loads(connection.getresponse().read())

        connection.request(
            "POST",
            "/v1/computer/session",
            body=json.dumps({"action": "stop"}),
            headers={**AUTH_HEADERS, "Content-Type": "application/json"},
        )
        stopped = json.loads(connection.getresponse().read())
    finally:
        server.shutdown()
        thread.join()

    assert started["active"] is True
    assert context["controls"][0]["name"] == "Spara"
    assert stopped["active"] is False
