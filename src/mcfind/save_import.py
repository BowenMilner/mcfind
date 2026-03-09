from __future__ import annotations

from pathlib import Path
from typing import Any

import nbtlib

from mcfind.errors import McfindError


def _pick(mapping: dict[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def import_java_save(path: str | Path) -> dict[str, Any]:
    root = Path(path).expanduser()
    level_path = root / "level.dat"
    if not level_path.exists():
        raise McfindError(
            f'Could not find level.dat in "{root}".',
            hint="Pass a Java save directory that contains level.dat.",
        )
    try:
        level = nbtlib.load(level_path)
    except Exception as exc:  # pragma: no cover - library-specific failures
        raise McfindError(f'Failed to read "{level_path}".', hint=str(exc)) from exc
    data = level.get("Data", {})
    world_gen = data.get("WorldGenSettings", {})
    version = data.get("Version", {})
    spawn = {
        "x": int(data.get("SpawnX", 0)),
        "y": int(data.get("SpawnY", 0)),
        "z": int(data.get("SpawnZ", 0)),
    }
    dimension_paths = {
        "overworld": str(root / "region"),
        "nether": str(root / "DIM-1" / "region"),
        "end": str(root / "DIM1" / "region"),
    }
    return {
        "path": str(root),
        "seed": int(world_gen.get("seed", 0)) if "seed" in world_gen else None,
        "spawn": spawn,
        "version_name": _pick(data, "Version", "Name"),
        "data_version": int(version["Id"]) if "Id" in version else None,
        "last_played": int(data.get("LastPlayed", 0)) if "LastPlayed" in data else None,
        "level_name": str(data.get("LevelName", root.name)),
        "dimension_paths": dimension_paths,
    }
