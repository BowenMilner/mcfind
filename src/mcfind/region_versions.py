from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcfind.errors import McfindError
from mcfind.runtime import config_home, ensure_dir


def _path() -> Path:
    return ensure_dir(config_home()) / "region_versions.json"


def load_region_versions() -> list[dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_region_versions(entries: list[dict[str, Any]]) -> None:
    _path().write_text(json.dumps(entries, indent=2, sort_keys=True))


def add_region_version(rect: tuple[int, int, int, int], version: str) -> dict[str, Any]:
    entries = load_region_versions()
    record = {
        "x1": min(rect[0], rect[2]),
        "z1": min(rect[1], rect[3]),
        "x2": max(rect[0], rect[2]),
        "z2": max(rect[1], rect[3]),
        "version": version,
    }
    entries.append(record)
    save_region_versions(entries)
    return record


def remove_region_version(index: int) -> None:
    entries = load_region_versions()
    if index < 0 or index >= len(entries):
        raise McfindError("Invalid region-version index.")
    del entries[index]
    save_region_versions(entries)


def resolve_region_version(x: int, z: int) -> dict[str, Any] | None:
    for entry in reversed(load_region_versions()):
        if entry["x1"] <= x <= entry["x2"] and entry["z1"] <= z <= entry["z2"]:
            return entry
    return None
