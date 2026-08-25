"""Conversation orchestration for Orbit."""

from __future__ import annotations

from collections.abc import Sequence

from .chat_models import ChatMessage, ChatResponse
from .memory_v2 import MemoryV2
from .providers import ChatProvider


DEFAULT_SYSTEM_PROMPT = (
    "You are Orbit, a trustworthy local-first AI desk companion. "
    "Be helpful, concise, and honest about uncertainty."
)


class ConversationPipeline:
    """Builds provider context, calls the provider, and records the exchange."""

    def __init__(
        self,
        *,
        provider: ChatProvider,
        memory: MemoryV2,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        history_limit: int = 12,
    ) -> None:
        if history_limit < 1:
            raise ValueError("History limit must be positive.")
        self.provider = provider
        self.memory = memory
        self.system_prompt = system_prompt
        self.history_limit = history_limit

    def build_messages(self, user_text: str) -> list[ChatMessage]:
        if not user_text.strip():
            raise ValueError("User message must not be empty.")

        messages = [
            ChatMessage(record.metadata["role"], record.content)
            for record in self.memory.recent(self.history_limit, kind="conversation")
            if record.metadata.get("role") in {"user", "assistant"}
        ]
        messages.append(ChatMessage("user", user_text.strip()))
        return messages

    def respond(self, user_text: str) -> ChatResponse:
        messages = self.build_messages(user_text)
        self.memory.remember(
            user_text.strip(),
            kind="conversation",
            metadata={"role": "user"},
        )
        response = self.provider.chat(messages, system=self.system_prompt)
        self.memory.remember(
            response.content,
            kind="conversation",
            metadata={"role": "assistant", "model": response.model},
        )
        return response
