"""Loopback HTTP service used by the Orbit desktop shell."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .chat_models import ChatResponse
from .computer_control import ComputerControlError, ComputerController
from .conversation import ConversationPipeline
from .local_auth import LocalCoreAuthenticator, LocalCoreCredential
from .ollama_provider import OllamaError, OllamaProvider
from .voice import LocalVoice, VoiceSynthesisError


class OrbitDesktopRuntime:
    """Exposes the small API surface required by the desktop frontend."""

    def __init__(
        self,
        *,
        provider: OllamaProvider,
        conversation: ConversationPipeline,
        availability_provider: OllamaProvider | None = None,
        voice: LocalVoice | None = None,
        computer: ComputerController | None = None,
    ) -> None:
        self.provider = provider
        self.conversation = conversation
        self.availability_provider = availability_provider or provider
        self.voice = voice
        self.computer = computer

    def status(self) -> dict[str, Any]:
        try:
            running = self.availability_provider.model_available()
        except OllamaError:
            running = False

        return {
            "runtimeState": "ready" if running else "degraded",
            "localBrain": {
                "model": self.provider.model,
                "running": running,
            },
            "computerMode": self.computer.status() if self.computer else {"active": False},
        }

    def respond(self, text: str) -> ChatResponse:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Text must be a non-empty string.")
        return self.conversation.respond(text)

    def synthesize(self, text: str) -> bytes:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Text must be a non-empty string.")
        if self.voice is None:
            raise VoiceSynthesisError("No local voice is configured.")
        return self.voice.synthesize(text)

    def computer_status(self) -> dict[str, object]:
        return self._computer().status()

    def start_computer_mode(self) -> dict[str, object]:
        return self._computer().start()

    def stop_computer_mode(self) -> dict[str, object]:
        return self._computer().stop()

    def inspect_computer(self) -> dict[str, object]:
        return self._computer().inspect()

    def click_computer_control(self, identifier: str) -> dict[str, object]:
        return self._computer().click(identifier)

    def type_in_computer_control(self, identifier: str, text: str) -> dict[str, object]:
        return self._computer().type_text(identifier, text)

    def _computer(self) -> ComputerController:
        if self.computer is None:
            raise ComputerControlError("Computer mode is not configured.")
        return self.computer


class OrbitDesktopServer(ThreadingHTTPServer):
    """Threaded loopback server carrying the shared Orbit runtime."""

    allow_reuse_address = True

    def __init__(
        self,
        address: tuple[str, int],
        runtime: OrbitDesktopRuntime,
        web_root: Path | None = None,
        auth: LocalCoreAuthenticator | None = None,
    ) -> None:
        if address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("Orbit Desktop API must bind to loopback only.")
        self.runtime = runtime
        self.web_root = web_root.resolve() if web_root and web_root.is_dir() else None
        self.auth = auth or LocalCoreAuthenticator(LocalCoreCredential().load_or_provision())
        super().__init__(address, OrbitDesktopRequestHandler)


class OrbitDesktopRequestHandler(BaseHTTPRequestHandler):
    """Serve status and conversation requests from trusted desktop origins."""

    server: OrbitDesktopServer
    _allowed_origins = {
        "http://127.0.0.1:1420",
        "http://localhost:1420",
        "http://tauri.localhost",
        "tauri://localhost",
    }

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/healthz":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        if path.startswith("/v1/") and not self._authenticated():
            return
        if path == "/v1/status":
            self._write_json(HTTPStatus.OK, self.server.runtime.status())
            return
        if path == "/v1/computer/status":
            self._write_computer_result(self.server.runtime.computer_status)
            return
        if path == "/v1/computer/context":
            self._write_computer_result(self.server.runtime.inspect_computer)
            return
        if path.startswith("/v1/"):
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        self._write_web_asset(path)

    def do_POST(self) -> None:  # noqa: N802
        if not self._authenticated_for_v1():
            return
        if self.path not in {
            "/v1/conversation",
            "/v1/speech",
            "/v1/computer/session",
            "/v1/computer/click",
            "/v1/computer/type",
        }:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        try:
            payload = self._read_json_body()
            if self.path == "/v1/speech":
                self._write_audio(HTTPStatus.OK, self.server.runtime.synthesize(payload.get("text")))
                return
            if self.path == "/v1/computer/session":
                action = payload.get("action")
                if action == "start":
                    self._write_json(HTTPStatus.OK, self.server.runtime.start_computer_mode())
                    return
                if action == "stop":
                    self._write_json(HTTPStatus.OK, self.server.runtime.stop_computer_mode())
                    return
                raise ValueError("Computer session action must be start or stop.")
            if self.path == "/v1/computer/click":
                identifier = payload.get("id")
                if not isinstance(identifier, str):
                    raise ValueError("Computer control id must be a string.")
                self._write_json(
                    HTTPStatus.OK,
                    self.server.runtime.click_computer_control(identifier),
                )
                return
            if self.path == "/v1/computer/type":
                identifier = payload.get("id")
                text = payload.get("text")
                if not isinstance(identifier, str):
                    raise ValueError("Computer control id must be a string.")
                self._write_json(
                    HTTPStatus.OK,
                    self.server.runtime.type_in_computer_control(identifier, text),
                )
                return
            response = self.server.runtime.respond(payload.get("text"))
        except ValueError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except VoiceSynthesisError as exc:
            self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
            return
        except ComputerControlError as exc:
            self._write_json(HTTPStatus.CONFLICT, {"error": str(exc)})
            return
        except OllamaError as exc:
            self._write_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
            return

        self._write_json(
            HTTPStatus.OK,
            {"content": response.content, "model": response.model},
        )

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._write_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self._reject_unsupported_method()

    def do_PUT(self) -> None:  # noqa: N802
        self._reject_unsupported_method()

    def do_PATCH(self) -> None:  # noqa: N802
        self._reject_unsupported_method()

    def do_DELETE(self) -> None:  # noqa: N802
        self._reject_unsupported_method()

    def log_message(self, format: str, *args: object) -> None:
        """Keep the desktop launcher quiet during normal operation."""

    def _read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Content-Length must be an integer.") from exc

        if content_length < 1 or content_length > 65_536:
            raise ValueError("Request body must be between 1 and 65536 bytes.")

        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must be valid JSON.") from exc

        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def _authenticated_for_v1(self) -> bool:
        path = urlparse(self.path).path
        return not path.startswith("/v1/") or self._authenticated()

    def _authenticated(self) -> bool:
        values = self.headers.get_all("Authorization", [])
        if self.server.auth.accepts(values):
            return True
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Bearer realm="orbit-core"')
        self._write_cors_headers()
        body = b'{"error":"Unauthorized."}'
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return False

    def _reject_unsupported_method(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/v1/") and not self._authenticated():
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._write_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_audio(self, status: HTTPStatus, body: bytes) -> None:
        self.send_response(status)
        self._write_cors_headers()
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_web_asset(self, request_path: str) -> None:
        """Serve the built local UI for private mobile access through Tailscale."""

        root = self.server.web_root
        if root is None:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Mobile UI is not built."})
            return

        relative = Path(unquote(request_path).lstrip("/"))
        if relative.is_absolute() or ".." in relative.parts:
            self._write_json(HTTPStatus.FORBIDDEN, {"error": "Invalid web path."})
            return

        candidate = (root / relative).resolve()
        if request_path == "/" or candidate.is_dir():
            candidate = root / "index.html"
        if not candidate.is_file() or root not in candidate.parents and candidate != root:
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        body = candidate.read_bytes()
        content_type = guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "application/json",
        }:
            content_type = f"{content_type}; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _write_computer_result(self, operation: Any) -> None:
        try:
            self._write_json(HTTPStatus.OK, operation())
        except ComputerControlError as exc:
            self._write_json(HTTPStatus.CONFLICT, {"error": str(exc)})

    def _write_cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if origin in self._allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")


def create_desktop_server(
    runtime: OrbitDesktopRuntime,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    web_root: Path | None = None,
    auth: LocalCoreAuthenticator | None = None,
) -> OrbitDesktopServer:
    """Create the loopback server without starting its event loop."""

    return OrbitDesktopServer((host, port), runtime, web_root=web_root, auth=auth)
