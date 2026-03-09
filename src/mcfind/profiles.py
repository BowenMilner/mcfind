from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcfind.errors import McfindError
from mcfind.runtime import config_home, ensure_dir


def _profiles_path() -> Path:
    return ensure_dir(config_home()) / "profiles.json"


def load_profiles() -> dict[str, dict[str, Any]]:
    path = _profiles_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_profiles(profiles: dict[str, dict[str, Any]]) -> None:
    _profiles_path().write_text(json.dumps(profiles, indent=2, sort_keys=True))


def add_profile(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    profiles = load_profiles()
    profiles[name] = payload
    save_profiles(profiles)
    return payload


def remove_profile(name: str) -> None:
    profiles = load_profiles()
    if name not in profiles:
        raise McfindError(f'Profile "{name}" does not exist.')
    del profiles[name]
    save_profiles(profiles)


def get_profile(name: str) -> dict[str, Any]:
    profiles = load_profiles()
    if name not in profiles:
        raise McfindError(f'Profile "{name}" does not exist.')
    return profiles[name]
