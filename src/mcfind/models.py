from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class ResultRecord:
    structure: str
    x: int
    z: int
    y: int | None
    distance_blocks: float
    bearing: str
    notes: list[str] = field(default_factory=list)
    dimension: str = "overworld"
    chunk_x: int | None = None
    chunk_z: int | None = None
    region_x: int | None = None
    region_z: int | None = None
    nether_equivalent_x: int | None = None
    nether_equivalent_z: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ResponseEnvelope:
    seed: int | None
    edition: str
    version_requested: str | None
    version_effective: str | None
    source_backend: str
    command: str
    warnings: list[str]
    results: list[dict[str, Any]] | None = None
    generated_at: str = field(default_factory=utc_now)
    explain: dict[str, Any] | None = None
    route: dict[str, Any] | None = None
    save: dict[str, Any] | None = None
    profiles: list[dict[str, Any]] | None = None
    region_versions: list[dict[str, Any]] | None = None
    info: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}
