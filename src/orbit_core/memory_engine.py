"""Simple memory abstraction for Orbit."""

from __future__ import annotations


class MemoryEngine:
    """Stores simple key-value records in memory."""

    def __init__(self) -> None:
        self._records: dict[str, str] = {}

    def store(self, key: str, value: str) -> None:
        self._records[key] = value

    def recall(self, key: str) -> str | None:
        return self._records.get(key)

    def has_record(self, key: str) -> bool:
        return key in self._records

    def count(self) -> int:
        return len(self._records)
