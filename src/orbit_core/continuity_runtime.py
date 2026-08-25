"""Continuity orchestration for Orbit."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .identity_engine import IdentityEngine
from .learning_engine import LearnedItem, LearningEngine
from .memory_v2 import MemoryV2


@dataclass(slots=True)
class ContinuityRuntime:
    """Owns Orbit's durable identity and long-term learning interfaces."""

    identity: IdentityEngine
    memory: MemoryV2
    learning: LearningEngine

    @classmethod
    def create(
        cls,
        *,
        memory_path: str | Path,
        identity: IdentityEngine | None = None,
    ) -> "ContinuityRuntime":
        active_identity = identity or IdentityEngine.default_identity()
        active_identity.validate()

        memory = MemoryV2(memory_path)
        learning = LearningEngine(memory)

        return cls(
            identity=active_identity,
            memory=memory,
            learning=learning,
        )

    def learn(
        self,
        content: str,
        *,
        source: str = "user",
        confidence: float = 1.0,
        importance: float = 0.5,
    ) -> LearnedItem:
        return self.learning.learn(
            content,
            source=source,
            confidence=confidence,
            importance=importance,
        )

    def recall_learning(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[LearnedItem]:
        return self.learning.search(query, limit=limit)

    def continuity_summary(self) -> str:
        return (
            f"{self.identity.name} {self.identity.version} | "
            f"mission={self.identity.mission} | "
            f"learned={self.memory.count(kind='learning')}"
        )