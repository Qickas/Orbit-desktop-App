"""Provider interfaces for Orbit chat backends."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .chat_models import ChatMessage, ChatResponse


class ChatProvider(Protocol):
    """Common interface implemented by Orbit chat providers."""

    def chat(
        self,
        messages: Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> ChatResponse:
        """Send conversation messages to a provider and return a response."""
        ...