"""Startup coordination for Orbit core."""

from __future__ import annotations

from dataclasses import dataclass

from .ai_router import AIRouter
from .identity_engine import IdentityEngine
from .memory_engine import MemoryEngine


@dataclass(slots=True)
class BootSummary:
    identity_name: str
    memory_records: int
    router_provider: str
    status: str


class BootManager:
    """Coordinates the initial startup flow for Orbit."""

    def __init__(
        self,
        *,
        identity: IdentityEngine,
        memory: MemoryEngine,
        router: AIRouter,
    ) -> None:
        self.identity = identity
        self.memory = memory
        self.router = router

    def boot(self) -> BootSummary:
        """Perform lightweight startup validation and return a status summary."""
        self.identity.validate()
        self.router.validate()

        if not self.memory.has_record("system:boot"):
            self.memory.store("system:boot", "initialized")

        return BootSummary(
            identity_name=self.identity.name,
            memory_records=self.memory.count(),
            router_provider=self.router.default_provider,
            status="ready",
        )
