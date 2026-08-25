"""AI routing abstraction for Orbit."""

from __future__ import annotations


class AIRouter:
    """Routes requests to a named provider."""

    def __init__(self, *, default_provider: str) -> None:
        self.default_provider = default_provider

    def validate(self) -> None:
        if not self.default_provider.strip():
            raise ValueError("Default provider must not be empty.")

    def route(self, request_type: str) -> str:
        self.validate()
        return f"{self.default_provider}:{request_type}"
