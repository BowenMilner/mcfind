from __future__ import annotations

import os
import tempfile
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


def write_text_atomic(path: Path, contents: str) -> None:
    ensure_dir(path.parent)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
