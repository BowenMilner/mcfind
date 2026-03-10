from __future__ import annotations

from typing import Any

from mcfind.cli import parse_args
from mcfind.errors import McfindError


def _append_optional(argv: list[str], flag: str, value: str | int | float | None) -> None:
    if value is None:
        return
    argv.extend([flag, str(value)])


def _structures_arg(structures: list[str] | str | None) -> str | None:
    if structures is None:
        return None
    if isinstance(structures, str):
        return structures
    return ",".join(structures)


def _biomes_arg(biomes: list[str] | str | None) -> str | None:
    if biomes is None:
        return None
    if isinstance(biomes, str):
        return biomes
    return ",".join(biomes)


def run_cli_command(argv: list[str]) -> dict[str, Any]:
    args = parse_args(argv)
    envelope = args.handler(args)
    return envelope.to_dict()


def nearest_payload(
    *,
    seed: int,
    version: str = "1.21.11",
    from_x: int = 0,
    from_z: int = 0,
    structures: list[str] | str = "stronghold",
    edition: str = "java",
    top: int = 1,
    dimension: str | None = None,
    explain: bool = False,
    chunk_version: str | None = None,
    backend: str = "cubiomes",
    timeout: float | None = None,
) -> dict[str, Any]:
    argv = [
        "nearest",
        "--seed",
        str(seed),
        "--edition",
        edition,
        "--version",
        version,
        "--from",
        str(from_x),
        str(from_z),
        "--structure",
        _structures_arg(structures) or "stronghold",
        "--top",
        str(top),
    ]
    _append_optional(argv, "--dimension", dimension)
    _append_optional(argv, "--chunk-version", chunk_version)
    _append_optional(argv, "--backend", backend)
    _append_optional(argv, "--timeout", timeout)
    if explain:
        argv.append("--explain")
    return run_cli_command(argv)


def nearest_biome_payload(
    *,
    seed: int,
    version: str = "1.21.11",
    from_x: int = 0,
    from_z: int = 0,
    biomes: list[str] | str = "cherry_grove",
    edition: str = "java",
    top: int = 1,
    dimension: str | None = None,
    explain: bool = False,
    chunk_version: str | None = None,
    backend: str = "cubiomes",
    timeout: float | None = None,
) -> dict[str, Any]:
    argv = [
        "nearest-biome",
        "--seed",
        str(seed),
        "--edition",
        edition,
        "--version",
        version,
        "--from",
        str(from_x),
        str(from_z),
        "--biome",
        _biomes_arg(biomes) or "cherry_grove",
        "--top",
        str(top),
    ]
    _append_optional(argv, "--dimension", dimension)
    _append_optional(argv, "--chunk-version", chunk_version)
    _append_optional(argv, "--backend", backend)
    _append_optional(argv, "--timeout", timeout)
    if explain:
        argv.append("--explain")
    return run_cli_command(argv)


def within_radius_payload(
    *,
    seed: int,
    version: str = "1.21.11",
    from_x: int = 0,
    from_z: int = 0,
    radius: int = 5000,
    structures: list[str] | str = "village",
    edition: str = "java",
    limit: int = 10,
    sort: str = "distance",
    dimension: str | None = None,
    explain: bool = False,
    chunk_version: str | None = None,
    backend: str = "cubiomes",
    timeout: float | None = None,
) -> dict[str, Any]:
    argv = [
        "within-radius",
        "--seed",
        str(seed),
        "--edition",
        edition,
        "--version",
        version,
        "--from",
        str(from_x),
        str(from_z),
        "--radius",
        str(radius),
        "--structure",
        _structures_arg(structures) or "village",
        "--limit",
        str(limit),
        "--sort",
        sort,
    ]
    _append_optional(argv, "--dimension", dimension)
    _append_optional(argv, "--chunk-version", chunk_version)
    _append_optional(argv, "--backend", backend)
    _append_optional(argv, "--timeout", timeout)
    if explain:
        argv.append("--explain")
    return run_cli_command(argv)


def route_payload(
    *,
    seed: int,
    version: str = "1.21.11",
    from_x: int = 0,
    from_z: int = 0,
    structures: list[str] | str = "village,trial_chamber,stronghold",
    edition: str = "java",
    radius: int = 20000,
    limit: int = 5,
    explain: bool = False,
    chunk_version: str | None = None,
    backend: str = "cubiomes",
    timeout: float | None = None,
) -> dict[str, Any]:
    argv = [
        "route",
        "--seed",
        str(seed),
        "--edition",
        edition,
        "--version",
        version,
        "--from",
        str(from_x),
        str(from_z),
        "--structure",
        _structures_arg(structures) or "village,trial_chamber,stronghold",
        "--radius",
        str(radius),
        "--limit",
        str(limit),
    ]
    _append_optional(argv, "--chunk-version", chunk_version)
    _append_optional(argv, "--backend", backend)
    _append_optional(argv, "--timeout", timeout)
    if explain:
        argv.append("--explain")
    return run_cli_command(argv)


def seed_info_payload(
    *,
    seed: int,
    version: str = "1.21.11",
    structures: list[str] | str | None = None,
    edition: str = "java",
    explain: bool = False,
    backend: str = "cubiomes",
) -> dict[str, Any]:
    argv = [
        "seed-info",
        "--seed",
        str(seed),
        "--edition",
        edition,
        "--version",
        version,
    ]
    if structures:
        argv.extend(["--structure", _structures_arg(structures) or ""])
    _append_optional(argv, "--backend", backend)
    if explain:
        argv.append("--explain")
    return run_cli_command(argv)


def import_save_payload(path: str) -> dict[str, Any]:
    return run_cli_command(["import-save", path])


def make_error_payload(exc: McfindError) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": exc.message}
    if exc.hint:
        payload["hint"] = exc.hint
    payload["exit_code"] = exc.exit_code
    return payload
