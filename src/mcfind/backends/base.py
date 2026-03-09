from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BackendResult:
    x: int
    z: int
    exact: bool


class WorldgenBackend(Protocol):
    name: str

    def nearest(self, structure: str, version_enum: int, seed: int, from_x: int, from_z: int, limit: int, timeout: float | None = None) -> list[BackendResult]:
        ...

    def within_radius(self, structure: str, version_enum: int, seed: int, from_x: int, from_z: int, radius: int, limit: int, timeout: float | None = None) -> list[BackendResult]:
        ...
