"""Identity model for Orbit."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class IdentityEngine:
    """Represents the core identity configuration for Orbit."""

    name: str
    version: str
    mission: str
    traits: list[str] = field(default_factory=list)

    @classmethod
    def default_identity(cls) -> "IdentityEngine":
        return cls(
            name="Orbit",
            version="0.1.0",
            mission="Build a trustworthy assistant foundation.",
            traits=["private", "local-first", "modular"],
        )

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Identity name must not be empty.")
        if not self.version.strip():
            raise ValueError("Identity version must not be empty.")
