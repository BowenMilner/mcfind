from __future__ import annotations

import math
from typing import Iterable

from mcfind.errors import McfindError


BEARINGS = (
    "N",
    "NE",
    "E",
    "SE",
    "S",
    "SW",
    "W",
    "NW",
)


def parse_coordinate_pair(values: Iterable[str] | str) -> tuple[int, int]:
    if isinstance(values, str):
        cleaned = values.replace(",", " ")
        parts = [part for part in cleaned.split() if part]
    else:
        parts = [str(part) for part in values]
    if len(parts) != 2:
        raise McfindError(
            "Invalid coordinate pair.",
            hint='Use `--from 780 874`, `--from "780,874"`, or `--from-x/--from-z`.',
        )
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise McfindError("Invalid coordinate pair.", hint="Coordinates must be integers.") from exc


def distance_blocks(from_x: int, from_z: int, to_x: int, to_z: int) -> float:
    return math.hypot(to_x - from_x, to_z - from_z)


def bearing(from_x: int, from_z: int, to_x: int, to_z: int) -> str:
    dx = to_x - from_x
    dz = to_z - from_z
    if dx == 0 and dz == 0:
        return "HERE"
    angle = (math.degrees(math.atan2(dx, -dz)) + 360.0) % 360.0
    index = int((angle + 22.5) // 45) % len(BEARINGS)
    return BEARINGS[index]


def chunk_coords(x: int, z: int) -> tuple[int, int]:
    return math.floor(x / 16), math.floor(z / 16)


def region_coords(x: int, z: int) -> tuple[int, int]:
    return math.floor(x / 512), math.floor(z / 512)


def nether_equivalent(x: int, z: int, dimension: str) -> tuple[int | None, int | None]:
    if dimension == "overworld":
        return math.floor(x / 8), math.floor(z / 8)
    if dimension == "nether":
        return x * 8, z * 8
    return None, None
