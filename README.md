# Orbit Core Foundation

Orbit Core Foundation is the first starter package for the Orbit workspace. It provides the initial Python application skeleton, project conventions, test harness, and automation needed to begin building the core assistant platform in an organized way.

## Package Contents

- `src/orbit_core/`: core Python package and starter engines
- `tests/`: unit tests for the initial foundation modules
- `docs/`: architecture and development notes
- `scripts/`: helper entry points for local development
- `assets/`: placeholder directory for shared static resources
- `.github/workflows/`: continuous integration workflow

## Included Modules

- `BootManager`: coordinates startup and health checks
- `IdentityEngine`: stores core Orbit identity metadata
- `MemoryEngine`: manages simple in-memory records
- `AIRouter`: dispatches requests to configured providers
- `OllamaProvider`: calls a local Ollama model through `/api/chat`
- `ConversationPipeline`: combines memory, history, and provider responses
- `MemoryV2`: searchable JSON-backed conversation memory

## Quick Start

1. Create and activate a Python 3.11 virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Run the test suite with `pytest`.
4. Launch the demo bootstrap with `python scripts/run_boot.py`.
5. Start terminal chat with `python scripts/terminal_chat.py`.

See `INSTALL.md` for setup details.

## Terminal chat

Install and start Ollama, then pull a local model, for example:

```powershell
ollama pull llama3.2
python scripts/terminal_chat.py
```

## Desktop authentication boundary

The Tauri webview never calls the Core API directly. Rust owns the local
credential loaded from the OS keyring and sends authenticated requests to the
loopback Core. The webview communicates only through fixed Tauri commands and
never receives the credential.

`/healthz` is unauthenticated liveness only. Readiness is the authenticated
`/v1/status` request. All other `/v1/*` routes require one exact Bearer header.

The bundled web UI is therefore Desktop/Tauri-only for Core operations. A
future private mobile client needs its own authenticated transport; this
project does not provide an unauthenticated browser compatibility path.

The chat stores local memory in `data/memory.json`. Use `--no-persist` for a
temporary session or `--model qwen3:8b` to choose another installed model.

Useful commands inside the chat are `/status`, `/models`, `/clear`, and
`/quit`. To test one message without opening an interactive session:

```powershell
python scripts/terminal_chat.py --once "Hej Orbit"
```
