"""Persistent, searchable memory for Orbit conversations."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One durable memory record."""

    id: str
    content: str
    kind: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryV2:
    """A small JSON-backed memory store with recent-history and search APIs."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else None
        self._records: list[MemoryRecord] = []
        if self.path is not None and self.path.exists():
            self._load()

    def remember(
        self,
        content: str,
        *,
        kind: str = "note",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        if not content.strip():
            raise ValueError("Memory content must not be empty.")
        if not kind.strip():
            raise ValueError("Memory kind must not be empty.")

        record = MemoryRecord(
            id=uuid.uuid4().hex,
            content=content.strip(),
            kind=kind.strip(),
            created_at=datetime.now(UTC).isoformat(),
            metadata=dict(metadata or {}),
        )
        self._records.append(record)
        self._save()
        return record

    def recent(self, limit: int = 20, *, kind: str | None = None) -> list[MemoryRecord]:
        if limit < 1:
            return []
        records = self._filter(kind)
        return list(records[-limit:])

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        kind: str | None = None,
    ) -> list[MemoryRecord]:
        if not query.strip() or limit < 1:
            return []
        needle = query.casefold()
        matches = []
        for record in reversed(self._filter(kind)):
            haystack = " ".join(
                [record.content, record.kind, *(str(value) for value in record.metadata.values())]
            ).casefold()
            if needle in haystack:
                matches.append(record)
                if len(matches) >= limit:
                    break
        return matches

    def count(self, *, kind: str | None = None) -> int:
        return len(self._filter(kind))

    def clear(self) -> None:
        self._records.clear()
        self._save()

    def _filter(self, kind: str | None) -> list[MemoryRecord]:
        if kind is None:
            return list(self._records)
        return [record for record in self._records if record.kind == kind]

    def _load(self) -> None:
        if self.path is None:
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            records = raw.get("records", [])
            self._records = [MemoryRecord(**item) for item in records]
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ValueError(f"Could not load memory file: {self.path}") from exc

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 2, "records": [asdict(record) for record in self._records]}
        fd, temp_name = tempfile.mkstemp(prefix="orbit-memory-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=True, indent=2)
                handle.write("\n")
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
