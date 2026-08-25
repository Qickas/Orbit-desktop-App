# Orbit Core Architecture

Orbit Core starts as a lightweight Python package that can grow into a larger multi-service platform later without forcing an early rewrite.

## Layers

- `BootManager`: startup coordination
- `IdentityEngine`: identity and configuration defaults
- `MemoryEngine`: compatibility layer for the original in-memory records
- `MemoryV2`: durable, searchable memory records
- `AIRouter`: model/provider routing logic
- `OllamaProvider`: local model provider over Ollama's HTTP API
- `ConversationPipeline`: conversation history and provider orchestration

## Conversation flow

```text
terminal_chat -> ConversationPipeline -> MemoryV2 (history)
                               -> OllamaProvider -> Ollama /api/chat
                               -> MemoryV2 (user + assistant messages)
```

## Design Notes

- Keep module boundaries explicit from day one
- Prefer testable classes over hidden global state
- Start simple, but make later persistence and provider expansion straightforward
- Keep Ollama optional at import time so tests do not require a running model
