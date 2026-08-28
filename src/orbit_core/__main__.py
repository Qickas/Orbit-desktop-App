"""Command-line entry points for Orbit Core."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from .conversation import ConversationPipeline
from .computer_control import ComputerController
from .desktop_service import OrbitDesktopRuntime, create_desktop_server
from .memory_v2 import MemoryV2
from .ollama_provider import OllamaProvider
from .voice import LocalVoice


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Orbit Core services.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    desktop = subparsers.add_parser("desktop", help="Run the desktop loopback API.")
    desktop.add_argument("--host", default="127.0.0.1")
    desktop.add_argument("--port", type=int, default=8765)
    desktop.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "llama3.2"))
    desktop.add_argument(
        "--base-url",
        default=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    )
    desktop.add_argument(
        "--memory-file",
        type=Path,
        default=Path(os.getenv("ORBIT_MEMORY_FILE", "data/memory.json")),
    )
    desktop.add_argument(
        "--voice-model",
        type=Path,
        default=Path(
            os.getenv("ORBIT_VOICE_MODEL", "assets/voices/sv_SE-nst-medium.onnx")
        ),
    )
    desktop.add_argument(
        "--computer-session-seconds",
        type=int,
        default=int(os.getenv("ORBIT_COMPUTER_SESSION_SECONDS", "600")),
    )
    desktop.add_argument(
        "--web-root",
        type=Path,
        default=Path(os.getenv("ORBIT_WEB_ROOT", "dist")),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "desktop":
        return 2

    provider = OllamaProvider(model=args.model, base_url=args.base_url)
    availability_provider = OllamaProvider(
        model=args.model,
        base_url=args.base_url,
        timeout=2.0,
    )
    conversation = ConversationPipeline(
        provider=provider,
        memory=MemoryV2(args.memory_file),
    )
    runtime = OrbitDesktopRuntime(
        provider=provider,
        conversation=conversation,
        availability_provider=availability_provider,
        voice=LocalVoice(args.voice_model),
        computer=ComputerController(session_seconds=args.computer_session_seconds),
    )
    server = create_desktop_server(
        runtime,
        host=args.host,
        port=args.port,
        web_root=args.web_root,
    )
    print(f"Orbit Core listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
