"""Selective long-term learning for Orbit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .memory_v2 import MemoryRecord, MemoryV2


LEARNING_KIND = "learning"


@dataclass(frozen=True, slots=True)
class LearnedItem:
    """A durable piece of knowledge Orbit deliberately learned."""

    id: str
    content: str
    confidence: float
    source: str
    importance: float
    created_at: str


class LearningEngine:
    """Controls what Orbit stores and retrieves as durable learning."""

    def __init__(self, memory: MemoryV2) -> None:
        self.memory = memory

    def learn(
        self,
        content: str,
        *,
        source: str = "user",
        confidence: float = 1.0,
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> LearnedItem:
        text = content.strip()

        if not text:
            raise ValueError("Learning content must not be empty.")

        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0.")

        if not 0.0 <= importance <= 1.0:
            raise ValueError("Importance must be between 0.0 and 1.0.")

        source = source.strip()

        if not source:
            raise ValueError("Learning source must not be empty.")

        record_metadata = dict(metadata or {})
        record_metadata.update(
            {
                "source": source,
                "confidence": confidence,
                "importance": importance,
            }
        )

        record = self.memory.remember(
            text,
            kind=LEARNING_KIND,
            metadata=record_metadata,
        )

        return self._to_learned_item(record)

    def recent(self, limit: int = 20) -> list[LearnedItem]:
        records = self.memory.recent(limit, kind=LEARNING_KIND)
        return [self._to_learned_item(record) for record in records]

    def search(self, query: str, *, limit: int = 5) -> list[LearnedItem]:
        records = self.memory.search(
            query,
            limit=limit,
            kind=LEARNING_KIND,
        )
        return [self._to_learned_item(record) for record in records]

    @staticmethod
    def _to_learned_item(record: MemoryRecord) -> LearnedItem:
        return LearnedItem(
            id=record.id,
            content=record.content,
            confidence=float(record.metadata.get("confidence", 1.0)),
            source=str(record.metadata.get("source", "unknown")),
            importance=float(record.metadata.get("importance", 0.5)),
            created_at=record.created_at,
        )