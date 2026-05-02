from __future__ import annotations

from typing import Any

from mcfind.errors import McfindError
from mcfind.services import (
    BiomeQueryRequest,
    RadiusQueryRequest,
    RouteQueryRequest,
    SeedInfoRequest,
    StructureQueryRequest,
    import_save_response,
    nearest_biome_response,
    nearest_response,
    route_response,
    seed_info_response,
    within_radius_response,
)


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
    return nearest_response(
        StructureQueryRequest(
            seed=seed,
            edition=edition,
            version=version,
            chunk_version=chunk_version,
            origin=(from_x, from_z),
            structures=structures,
            top=top,
            dimension=dimension,
            backend=backend,
            timeout=timeout,
            explain=explain,
        )
    ).to_dict()


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
    return nearest_biome_response(
        BiomeQueryRequest(
            seed=seed,
            edition=edition,
            version=version,
            chunk_version=chunk_version,
            origin=(from_x, from_z),
            biomes=biomes,
            top=top,
            dimension=dimension,
            backend=backend,
            timeout=timeout,
            explain=explain,
        )
    ).to_dict()


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
    return within_radius_response(
        RadiusQueryRequest(
            seed=seed,
            edition=edition,
            version=version,
            chunk_version=chunk_version,
            origin=(from_x, from_z),
            radius=radius,
            structures=structures,
            limit=limit,
            sort=sort,
            dimension=dimension,
            backend=backend,
            timeout=timeout,
            explain=explain,
        )
    ).to_dict()


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
    return route_response(
        RouteQueryRequest(
            seed=seed,
            edition=edition,
            version=version,
            chunk_version=chunk_version,
            origin=(from_x, from_z),
            structures=structures,
            radius=radius,
            limit=limit,
            backend=backend,
            timeout=timeout,
            explain=explain,
        )
    ).to_dict()


def seed_info_payload(
    *,
    seed: int,
    version: str = "1.21.11",
    structures: list[str] | str | None = None,
    edition: str = "java",
    explain: bool = False,
    backend: str = "cubiomes",
) -> dict[str, Any]:
    return seed_info_response(
        SeedInfoRequest(
            seed=seed,
            edition=edition,
            version=version,
            structures=structures,
            explain=explain,
            backend=backend,
        )
    ).to_dict()


def import_save_payload(path: str) -> dict[str, Any]:
    return import_save_response(path).to_dict()


def make_error_payload(exc: McfindError) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": exc.message}
    if exc.hint:
        payload["hint"] = exc.hint
    payload["exit_code"] = exc.exit_code
    return payload
