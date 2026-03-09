from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "mcfind"


def config_home() -> Path:
    override = os.environ.get("MCFIND_HOME")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg).expanduser() / APP_NAME
    return Path.home() / ".config" / APP_NAME


def cache_home(cache_dir: str | None = None) -> Path:
    if cache_dir:
        return Path(cache_dir).expanduser()
    override = os.environ.get("MCFIND_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser() / APP_NAME
    return Path.home() / ".cache" / APP_NAME


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
