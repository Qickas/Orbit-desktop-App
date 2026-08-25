"""Run a local Orbit terminal chat through Ollama."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from orbit_core import ConversationPipeline, MemoryV2, OllamaError, OllamaProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chat with Orbit through local Ollama.")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "llama3.2"))
    parser.add_argument("--base-url", default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    parser.add_argument(
        "--memory-file",
        type=Path,
        default=Path(os.getenv("ORBIT_MEMORY_FILE", str(PROJECT_ROOT / "data" / "memory.json"))),
    )
    parser.add_argument("--once", help="Send one message and exit.")
    parser.add_argument("--no-persist", action="store_true", help="Keep memory only for this run.")
    return parser


def print_help() -> None:
    print("Kommandon: /help, /status, /models, /clear, /quit")


def run_chat(args: argparse.Namespace) -> int:
    memory = MemoryV2(None if args.no_persist else args.memory_file)
    provider = OllamaProvider(model=args.model, base_url=args.base_url)
    pipeline = ConversationPipeline(provider=provider, memory=memory)

    if args.once:
        try:
            print(pipeline.respond(args.once).content)
        except (OllamaError, ValueError) as exc:
            print(f"Orbit kunde inte svara: {exc}", file=sys.stderr)
            return 1
        return 0

    print(f"Orbit terminalchat | modell: {args.model}")
    print("Skriv /help för kommandon. Skriv /quit för att avsluta.")
    while True:
        try:
            user_text = input("Du> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user_text:
            continue
        if user_text in {"/quit", "/exit"}:
            return 0
        if user_text == "/help":
            print_help()
            continue
        if user_text == "/status":
            print(f"Minnen: {memory.count()} | Historik: {memory.count(kind='conversation')} | Modell: {args.model}")
            continue
        if user_text == "/models":
            try:
                print("\n".join(provider.models()) or "Inga modeller hittades.")
            except OllamaError as exc:
                print(f"Ollama kunde inte kontaktas: {exc}")
            continue
        if user_text == "/clear":
            memory.clear()
            print("Orbit-minnet är rensat.")
            continue

        try:
            print(f"Orbit> {pipeline.respond(user_text).content}")
        except (OllamaError, ValueError) as exc:
            print(f"Orbit kunde inte svara: {exc}")


def main() -> int:
    return run_chat(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
