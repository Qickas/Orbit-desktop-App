"""Small dependency-free client for Ollama's local chat API."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .chat_models import ChatMessage, ChatResponse


class OllamaError(RuntimeError):
    """Raised when Ollama cannot answer a request."""


class OllamaProvider:
    """Calls Ollama's local ``/api/chat`` endpoint."""

    def __init__(
        self,
        *,
        model: str = "qwen3.5:9b",
        base_url: str = "http://localhost:11434",
        timeout: float = 180.0,
        num_ctx: int = 4096,
        think: bool = False,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not model.strip():
            raise ValueError("Ollama model must not be empty.")
        if timeout <= 0:
            raise ValueError("Ollama timeout must be positive.")
        if num_ctx <= 0:
            raise ValueError("Ollama context size must be positive.")

        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.num_ctx = num_ctx
        self.think = think
        self._opener = opener or urlopen

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/api/chat"

    @property
    def tags_url(self) -> str:
        return f"{self.base_url}/api/tags"

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> ChatResponse:
        if not messages:
            raise ValueError("At least one chat message is required.")

        payload_messages: list[dict[str, str]] = []

        if system and system.strip():
            payload_messages.append(
                {
                    "role": "system",
                    "content": system.strip(),
                }
            )

        payload_messages.extend(message.to_dict() for message in messages)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "stream": False,
            "think": self.think,
            "options": {
                "num_ctx": self.num_ctx,
            },
        }

        data = self._post_json(self.chat_url, payload)

        message = data.get("message")

        if not isinstance(message, dict):
            raise OllamaError("Ollama returned no assistant message.")

        content = message.get("content")

        if not isinstance(content, str):
            raise OllamaError("Ollama returned no assistant message content.")

        content = content.strip()

        if not content:
            raise OllamaError("Ollama returned an empty assistant message.")

        try:
            return ChatResponse(
                content=content,
                model=str(data.get("model") or self.model),
                raw=data,
            )
        except ValueError as exc:
            raise OllamaError(
                "Could not convert Ollama response into ChatResponse."
            ) from exc

    def models(self) -> list[str]:
        """Return locally available Ollama model names."""

        data = self._get_json(self.tags_url)

        models = data.get("models", [])

        if not isinstance(models, list):
            raise OllamaError("Ollama returned an invalid model list.")

        return [
            str(item["name"])
            for item in models
            if isinstance(item, dict) and item.get("name")
        ]

    def model_available(self, model: str | None = None) -> bool:
        """Return True when the requested model exists locally."""

        target = (model or self.model).strip()

        if not target:
            return False

        return target in self.models()

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        return self._read_json(request, "chat")

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
            },
            method="GET",
        )

        return self._read_json(request, "model list")

    def _read_json(
        self,
        request: Request,
        operation: str,
    ) -> dict[str, Any]:
        try:
            with self._opener(
                request,
                timeout=self.timeout,
            ) as response:
                raw_body = response.read()

        except HTTPError as exc:
            detail = exc.read().decode(
                "utf-8",
                errors="replace",
            ).strip()

            message = (
                f"Ollama {operation} failed "
                f"with HTTP {exc.code}."
            )

            raise OllamaError(
                f"{message} {detail}".strip()
            ) from exc

        except (URLError, TimeoutError, OSError) as exc:
            raise OllamaError(
                "Could not reach Ollama at "
                f"{self.base_url}. "
                "Start Ollama and check the URL."
            ) from exc

        try:
            decoded = raw_body.decode("utf-8")
            data = json.loads(decoded)

        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaError(
                "Ollama returned invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise OllamaError(
                "Ollama returned an invalid JSON object."
            )

        return data