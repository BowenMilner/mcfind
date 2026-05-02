from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcfind.backends.cubiomes import CubiomesBackend
from mcfind.biomes import get_biome, parse_biomes
from mcfind.coords import bearing, chunk_coords, distance_blocks, nether_equivalent, region_coords
from mcfind.errors import EmptyResultError, McfindError
from mcfind.models import ResponseEnvelope, ResultRecord
from mcfind.profiles import add_profile, get_profile, load_profiles, remove_profile
from mcfind.region_versions import add_region_version, load_region_versions, remove_region_version, resolve_region_version
from mcfind.routing import plan_route
from mcfind.save_import import import_java_save
from mcfind.structures import STRUCTURES, get_structure, parse_structures
from mcfind.versioning import EffectiveVersion, require_supported_feature, require_supported_structure, resolve_version


@dataclass(slots=True)
class QueryRequest:
    seed: int | None = None
    edition: str = "java"
    version: str | None = None
    chunk_version: str | None = None
    profile: str | None = None
    save: str | None = None
    origin: tuple[int, int] | None = None
    use_spawn: bool = False
    dimension: str | None = None
    backend: str = "auto"
    cache_dir: str | None = None
    timeout: float | None = None
    explain: bool = False


@dataclass(slots=True)
class StructureQueryRequest(QueryRequest):
    structures: list[str] | str | None = None
    top: int | None = None
    limit: int | None = None
    sort: str = "distance"
    exit_on_empty: bool = False


@dataclass(slots=True)
class BiomeQueryRequest(QueryRequest):
    biomes: list[str] | str | None = None
    top: int | None = None
    limit: int | None = None
    sort: str = "distance"
    exit_on_empty: bool = False


@dataclass(slots=True)
class RadiusQueryRequest(StructureQueryRequest):
    radius: int = 5000


@dataclass(slots=True)
class RouteQueryRequest(QueryRequest):
    structures: list[str] | str | None = None
    radius: int = 20000
    limit: int = 5
    exit_on_empty: bool = False


@dataclass(slots=True)
class SeedInfoRequest(QueryRequest):
    structures: list[str] | str | None = None


@dataclass(slots=True)
class ProfileAddRequest:
    name: str
    seed: int | str | None
    version: str
    base: tuple[int, int]


@dataclass(slots=True)
class RegionVersionAddRequest:
    rect: tuple[int, int, int, int]
    version: str


@dataclass(slots=True)
class _ResolvedQueryContext:
    backend: CubiomesBackend
    profile: dict[str, Any] | None
    save: dict[str, Any] | None
    seed: int
    origin: tuple[int, int] | None
    effective: EffectiveVersion
    warnings: list[str] = field(default_factory=list)


def parse_seed(value: int | str | None) -> int | None:
    if value is None:
        return None
    try:
        seed = int(value)
    except ValueError as exc:
        raise McfindError("invalid seed", hint="Seeds must be signed 64-bit integers.") from exc
    if seed < -(2**63) or seed > (2**63) - 1:
        raise McfindError("invalid seed", hint="Seeds must be signed 64-bit integers.")
    return seed


def resolve_query_inputs(profile_name: str | None, save_path: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    profile = get_profile(profile_name) if profile_name else None
    save = import_java_save(save_path) if save_path else None
    return profile, save


def resolve_seed(requested_seed: int | None, profile: dict[str, Any] | None, save: dict[str, Any] | None) -> int:
    seed = parse_seed(requested_seed)
    if seed is not None:
        return seed
    if profile and profile.get("seed") is not None:
        return int(profile["seed"])
    if save and save.get("seed") is not None:
        return int(save["seed"])
    raise McfindError("invalid seed", hint="Provide --seed, --profile, or --save.")


def resolve_origin(
    requested_origin: tuple[int, int] | None,
    use_spawn: bool,
    profile: dict[str, Any] | None,
    save: dict[str, Any] | None,
    *,
    require_origin: bool,
    use_save_spawn_default: bool,
) -> tuple[int, int] | None:
    if use_spawn:
        if not save:
            raise McfindError('Cannot use `--from spawn` without `--save`.')
        spawn = save["spawn"]
        return int(spawn["x"]), int(spawn["z"])
    if requested_origin is not None:
        return int(requested_origin[0]), int(requested_origin[1])
    if profile and profile.get("base"):
        return int(profile["base"][0]), int(profile["base"][1])
    if use_save_spawn_default and save:
        spawn = save.get("spawn") or {}
        return int(spawn.get("x", 0)), int(spawn.get("z", 0))
    if require_origin:
        raise McfindError("invalid coordinate pair", hint="Provide --from, --from-x/--from-z, a profile base, or a save.")
    return None


def resolve_effective_version(
    version: str | None,
    chunk_version: str | None,
    origin: tuple[int, int] | None,
    profile: dict[str, Any] | None,
    save: dict[str, Any] | None,
    warnings: list[str],
) -> EffectiveVersion:
    requested = chunk_version or version
    if not requested and profile:
        requested = profile.get("version")
    if not requested and save:
        requested = save.get("version_name")
    if not requested and origin:
        region_match = resolve_region_version(origin[0], origin[1])
        if region_match:
            requested = region_match["version"]
            warnings.append(
                f'Using region-version mapping {region_match["version"]} for origin chunk at ({origin[0]}, {origin[1]}).'
            )
    effective = resolve_version(requested)
    warnings.extend(effective.warnings)
    return effective


def resolve_dimension(structure_names: list[str], explicit_dimension: str | None) -> str:
    dimensions = {get_structure(name).dimension for name in structure_names}
    if len(dimensions) > 1:
        raise McfindError("Mixed-dimension structure queries are not supported.", hint="Query one dimension at a time.")
    inferred = next(iter(dimensions))
    if explicit_dimension is None:
        return inferred
    if "ruined_portal" in structure_names and explicit_dimension in {"overworld", "nether"}:
        return explicit_dimension
    if explicit_dimension != inferred:
        raise McfindError(
            f'Invalid dimension "{explicit_dimension}" for requested structure set.',
            hint=f"These structures generate in {inferred}.",
        )
    return explicit_dimension


def resolve_biome_dimension(biome_names: list[str], explicit_dimension: str | None) -> str:
    dimensions = {get_biome(name).dimension for name in biome_names}
    if len(dimensions) > 1:
        raise McfindError("Mixed-dimension biome queries are not supported.", hint="Query one dimension at a time.")
    inferred = next(iter(dimensions))
    if explicit_dimension is None:
        return inferred
    if explicit_dimension != inferred:
        raise McfindError(
            f'Invalid dimension "{explicit_dimension}" for requested biome set.',
            hint=f"These biomes generate in {inferred}.",
        )
    return explicit_dimension


def resolve_backend_name(structure: str, dimension: str) -> str:
    definition = get_structure(structure)
    if structure == "ruined_portal" and dimension == "nether":
        return "ruined_portal_nether"
    return definition.backend_name


def make_backend(backend_name: str, cache_dir: str | None = None) -> CubiomesBackend:
    if backend_name not in {"auto", "cubiomes"}:
        raise McfindError(f'backend "{backend_name}" is not available.')
    return CubiomesBackend(cache_dir=cache_dir)


def hydrate_result(structure_name: str, dimension: str, from_x: int, from_z: int, x: int, z: int) -> ResultRecord:
    chunk_x, chunk_z = chunk_coords(x, z)
    region_x, region_z = region_coords(x, z)
    nether_x, nether_z = nether_equivalent(x, z, dimension)
    definition = get_structure(structure_name)
    notes = []
    if definition.exactness_note:
        notes.append(definition.exactness_note)
    return ResultRecord(
        structure=structure_name,
        x=x,
        z=z,
        y=None,
        distance_blocks=round(distance_blocks(from_x, from_z, x, z), 1),
        bearing=bearing(from_x, from_z, x, z),
        notes=notes,
        dimension=dimension,
        chunk_x=chunk_x,
        chunk_z=chunk_z,
        region_x=region_x,
        region_z=region_z,
        nether_equivalent_x=nether_x,
        nether_equivalent_z=nether_z,
    )


def hydrate_biome_result(biome_name: str, dimension: str, from_x: int, from_z: int, x: int, z: int) -> dict[str, Any]:
    chunk_x, chunk_z = chunk_coords(x, z)
    region_x, region_z = region_coords(x, z)
    nether_x, nether_z = nether_equivalent(x, z, dimension)
    definition = get_biome(biome_name)
    notes = []
    if definition.exactness_note:
        notes.append(definition.exactness_note)
    notes.append("Biome positions are sampled on cubiomes' 1:4 biome grid, so edges can shift by a few blocks.")
    return {
        "biome": biome_name,
        "x": x,
        "z": z,
        "y": None,
        "distance_blocks": round(distance_blocks(from_x, from_z, x, z), 1),
        "bearing": bearing(from_x, from_z, x, z),
        "notes": notes,
        "dimension": dimension,
        "chunk_x": chunk_x,
        "chunk_z": chunk_z,
        "region_x": region_x,
        "region_z": region_z,
        "nether_equivalent_x": nether_x,
        "nether_equivalent_z": nether_z,
    }


def sort_results(records: list[ResultRecord], sort_key: str) -> list[ResultRecord]:
    key_funcs = {
        "distance": lambda item: (item.distance_blocks, item.structure, item.x, item.z),
        "x": lambda item: (item.x, item.z, item.structure),
        "z": lambda item: (item.z, item.x, item.structure),
        "structure": lambda item: (item.structure, item.distance_blocks, item.x, item.z),
    }
    return sorted(records, key=key_funcs[sort_key])


def sort_payload_results(records: list[dict[str, Any]], sort_key: str) -> list[dict[str, Any]]:
    key_name = "structure" if records and "structure" in records[0] else "biome"
    key_funcs = {
        "distance": lambda item: (item["distance_blocks"], item.get(key_name), item["x"], item["z"]),
        "x": lambda item: (item["x"], item["z"], item.get(key_name)),
        "z": lambda item: (item["z"], item["x"], item.get(key_name)),
        "structure": lambda item: (item.get(key_name), item["distance_blocks"], item["x"], item["z"]),
    }
    return sorted(records, key=key_funcs[sort_key])


def explain_payload(effective: EffectiveVersion, backend_name: str, structures: list[str]) -> dict[str, Any]:
    return {
        "version": effective.explanation,
        "backend": f"{backend_name} computes structure placement locally from cubiomes logic.",
        "results": [get_structure(name).exactness_note for name in structures if get_structure(name).exactness_note],
    }


def biome_explain_payload(effective: EffectiveVersion, backend_name: str, biomes: list[str]) -> dict[str, Any]:
    return {
        "version": effective.explanation,
        "backend": f"{backend_name} samples biome placement locally from cubiomes logic.",
        "results": [
            "Biome searches use cubiomes' 1:4 biome grid and return X/Z only. Underground or vertical biome boundaries are not modeled in this command."
        ]
        + [get_biome(name).exactness_note for name in biomes if get_biome(name).exactness_note],
    }


def _resolve_common_context(
    request: QueryRequest,
    *,
    require_origin: bool,
    use_save_spawn_default: bool,
) -> _ResolvedQueryContext:
    if request.edition != "java":
        raise McfindError('Only `--edition java` is supported in this build.')
    warnings: list[str] = []
    profile, save = resolve_query_inputs(request.profile, request.save)
    origin = resolve_origin(
        request.origin,
        request.use_spawn,
        profile,
        save,
        require_origin=require_origin,
        use_save_spawn_default=use_save_spawn_default,
    )
    effective = resolve_effective_version(request.version, request.chunk_version, origin, profile, save, warnings)
    backend = make_backend(request.backend, request.cache_dir)
    seed = resolve_seed(request.seed, profile, save)
    return _ResolvedQueryContext(
        backend=backend,
        profile=profile,
        save=save,
        seed=seed,
        origin=origin,
        effective=effective,
        warnings=warnings,
    )


def _resolve_structure_context(request: QueryRequest, structures: list[str], command_name: str) -> tuple[_ResolvedQueryContext, str]:
    context = _resolve_common_context(request, require_origin=True, use_save_spawn_default=True)
    assert context.origin is not None
    dimension = resolve_dimension(structures, request.dimension)
    if command_name in {"within-radius", "route"} and resolve_region_version(context.origin[0], context.origin[1]) and not request.chunk_version:
        context.warnings.append(
            "Mixed-version support currently resolves by origin chunk. Queries spanning multiple generation regions should use --chunk-version explicitly."
        )
    return context, dimension


def nearest_response(request: StructureQueryRequest) -> ResponseEnvelope:
    structures = parse_structures(request.structures or [])
    context, dimension = _resolve_structure_context(request, structures, "nearest")
    assert context.origin is not None
    limit = request.top or request.limit or 1
    records: list[ResultRecord] = []
    for structure_name in structures:
        definition = get_structure(structure_name)
        require_supported_structure(definition.min_version, context.effective, structure_name, context.backend.name)
        backend_name = resolve_backend_name(structure_name, dimension)
        results = context.backend.nearest(
            backend_name,
            context.effective.cubiomes_mc,
            context.seed,
            context.origin[0],
            context.origin[1],
            limit,
            timeout=request.timeout,
        )
        records.extend(
            hydrate_result(structure_name, dimension, context.origin[0], context.origin[1], result.x, result.z)
            for result in results
        )
    if not records and request.exit_on_empty:
        raise EmptyResultError(hint="Try increasing --top or checking the version/dimension.")
    records = sort_results(records, request.sort)
    return ResponseEnvelope(
        seed=context.seed,
        edition=request.edition,
        version_requested=context.effective.requested,
        version_effective=context.effective.effective,
        source_backend=context.backend.name,
        command="nearest",
        warnings=context.warnings,
        results=[record.to_dict() for record in records],
        explain=explain_payload(context.effective, context.backend.name, structures) if request.explain else None,
    )


def nearest_biome_response(request: BiomeQueryRequest) -> ResponseEnvelope:
    if not request.biomes:
        raise McfindError("At least one biome must be provided.", hint="Use --biome cherry_grove or --biomes cherry_grove,mushroom_fields.")
    context = _resolve_common_context(request, require_origin=True, use_save_spawn_default=True)
    assert context.origin is not None
    biome_names = parse_biomes(request.biomes)
    dimension = resolve_biome_dimension(biome_names, request.dimension)
    limit = request.top or request.limit or 1
    records: list[dict[str, Any]] = []
    for biome_name in biome_names:
        definition = get_biome(biome_name)
        require_supported_feature("biome", definition.min_version, context.effective, biome_name, context.backend.name)
        results = context.backend.nearest_biome(
            definition.biome_id,
            definition.dimension,
            definition.sample_y,
            context.effective.cubiomes_mc,
            context.seed,
            context.origin[0],
            context.origin[1],
            limit,
            timeout=request.timeout,
        )
        records.extend(
            hydrate_biome_result(biome_name, dimension, context.origin[0], context.origin[1], result.x, result.z)
            for result in results
        )
    if not records and request.exit_on_empty:
        raise EmptyResultError(hint="Try increasing --timeout or confirming the selected version/dimension.")
    records = sort_payload_results(records, request.sort)
    return ResponseEnvelope(
        seed=context.seed,
        edition=request.edition,
        version_requested=context.effective.requested,
        version_effective=context.effective.effective,
        source_backend=context.backend.name,
        command="nearest-biome",
        warnings=context.warnings,
        results=records,
        explain=biome_explain_payload(context.effective, context.backend.name, biome_names) if request.explain else None,
    )


def within_radius_response(request: RadiusQueryRequest) -> ResponseEnvelope:
    structures = parse_structures(request.structures or [])
    context, dimension = _resolve_structure_context(request, structures, "within-radius")
    assert context.origin is not None
    records: list[ResultRecord] = []
    for structure_name in structures:
        definition = get_structure(structure_name)
        require_supported_structure(definition.min_version, context.effective, structure_name, context.backend.name)
        backend_name = resolve_backend_name(structure_name, dimension)
        results = context.backend.within_radius(
            backend_name,
            context.effective.cubiomes_mc,
            context.seed,
            context.origin[0],
            context.origin[1],
            request.radius,
            request.limit or 10,
            timeout=request.timeout,
        )
        records.extend(
            hydrate_result(structure_name, dimension, context.origin[0], context.origin[1], result.x, result.z)
            for result in results
        )
    if not records and request.exit_on_empty:
        raise EmptyResultError(hint="Try increasing --radius or confirming the selected version.")
    records = sort_results(records, request.sort)
    return ResponseEnvelope(
        seed=context.seed,
        edition=request.edition,
        version_requested=context.effective.requested,
        version_effective=context.effective.effective,
        source_backend=context.backend.name,
        command="within-radius",
        warnings=context.warnings,
        results=[record.to_dict() for record in records],
        explain=explain_payload(context.effective, context.backend.name, structures) if request.explain else None,
    )


def route_response(request: RouteQueryRequest) -> ResponseEnvelope:
    structures = parse_structures(request.structures or [])
    context, dimension = _resolve_structure_context(request, structures, "route")
    assert context.origin is not None
    candidates: dict[str, list[ResultRecord]] = {}
    for structure_name in structures:
        definition = get_structure(structure_name)
        require_supported_structure(definition.min_version, context.effective, structure_name, context.backend.name)
        backend_name = resolve_backend_name(structure_name, dimension)
        results = context.backend.within_radius(
            backend_name,
            context.effective.cubiomes_mc,
            context.seed,
            context.origin[0],
            context.origin[1],
            request.radius,
            request.limit,
            timeout=request.timeout,
        )
        candidates[structure_name] = [
            hydrate_result(structure_name, dimension, context.origin[0], context.origin[1], result.x, result.z)
            for result in results
        ]

    missing = sorted(name for name, records in candidates.items() if not records)
    if missing:
        context.warnings.append(f"No candidates found within radius for: {', '.join(missing)}.")

    route = plan_route(context.origin, candidates)
    if not route.results and request.exit_on_empty:
        raise EmptyResultError(hint="Try increasing --radius or --limit.")
    return ResponseEnvelope(
        seed=context.seed,
        edition=request.edition,
        version_requested=context.effective.requested,
        version_effective=context.effective.effective,
        source_backend=context.backend.name,
        command="route",
        warnings=context.warnings,
        results=[record.to_dict() for record in route.results],
        route={"algorithm": route.algorithm, "total_distance_blocks": round(route.total_distance_blocks, 1)},
        explain=explain_payload(context.effective, context.backend.name, structures) if request.explain else None,
    )


def seed_info_response(request: SeedInfoRequest) -> ResponseEnvelope:
    if request.edition != "java":
        raise McfindError('Only `--edition java` is supported in this build.')
    profile, save = resolve_query_inputs(request.profile, request.save)
    warnings: list[str] = []
    seed = resolve_seed(request.seed, profile, save)
    origin = (0, 0)
    if request.origin is not None or request.use_spawn or profile or save:
        try:
            resolved = resolve_origin(
                request.origin,
                request.use_spawn,
                profile,
                save,
                require_origin=False,
                use_save_spawn_default=True,
            )
        except McfindError:
            resolved = None
        if resolved is not None:
            origin = resolved
    effective = resolve_effective_version(request.version, request.chunk_version, origin, profile, save, warnings)
    structures = parse_structures(request.structures) if request.structures else sorted(STRUCTURES.keys())
    dimension = resolve_dimension(structures, request.dimension) if request.structures else "overworld"
    backend = make_backend(request.backend, request.cache_dir)
    supported = []
    for structure_name in structures:
        definition = get_structure(structure_name)
        require_supported_structure(definition.min_version, effective, structure_name, backend.name)
        supported.append(structure_name)
    return ResponseEnvelope(
        seed=seed,
        edition=request.edition,
        version_requested=effective.requested,
        version_effective=effective.effective,
        source_backend=backend.name,
        command="seed-info",
        warnings=warnings,
        info={
            "origin": {"x": origin[0], "z": origin[1]},
            "dimension": dimension,
            "supported_structures": supported,
        },
        explain=explain_payload(effective, backend.name, structures) if request.explain else None,
    )


def import_save_response(path: str) -> ResponseEnvelope:
    save = import_java_save(path)
    return ResponseEnvelope(
        seed=save.get("seed"),
        edition="java",
        version_requested=save.get("version_name"),
        version_effective=resolve_version(save.get("version_name")).effective if save.get("version_name") else None,
        source_backend="local-save",
        command="import-save",
        warnings=[],
        save=save,
    )


def profile_add_response(request: ProfileAddRequest) -> ResponseEnvelope:
    payload = {
        "name": request.name,
        "seed": parse_seed(request.seed),
        "version": request.version,
        "base": [int(request.base[0]), int(request.base[1])],
    }
    add_profile(request.name, payload)
    return ResponseEnvelope(
        seed=payload["seed"],
        edition="java",
        version_requested=payload["version"],
        version_effective=resolve_version(payload["version"]).effective,
        source_backend="local-profile",
        command="profile-add",
        warnings=[],
        profiles=[payload],
    )


def profile_list_response() -> ResponseEnvelope:
    profiles = [{"name": name, **payload} for name, payload in sorted(load_profiles().items())]
    return ResponseEnvelope(
        seed=None,
        edition="java",
        version_requested=None,
        version_effective=None,
        source_backend="local-profile",
        command="profile-list",
        warnings=[],
        profiles=profiles,
    )


def profile_remove_response(name: str) -> ResponseEnvelope:
    remove_profile(name)
    return ResponseEnvelope(
        seed=None,
        edition="java",
        version_requested=None,
        version_effective=None,
        source_backend="local-profile",
        command="profile-remove",
        warnings=[],
        profiles=[{"name": name}],
    )


def region_add_response(request: RegionVersionAddRequest) -> ResponseEnvelope:
    record = add_region_version(request.rect, request.version)
    return ResponseEnvelope(
        seed=None,
        edition="java",
        version_requested=request.version,
        version_effective=resolve_version(request.version).effective,
        source_backend="local-region-map",
        command="region-version-add",
        warnings=[],
        region_versions=[record],
    )


def region_list_response() -> ResponseEnvelope:
    return ResponseEnvelope(
        seed=None,
        edition="java",
        version_requested=None,
        version_effective=None,
        source_backend="local-region-map",
        command="region-version-list",
        warnings=[],
        region_versions=load_region_versions(),
    )


def region_remove_response(index: int) -> ResponseEnvelope:
    remove_region_version(index - 1)
    return ResponseEnvelope(
        seed=None,
        edition="java",
        version_requested=None,
        version_effective=None,
        source_backend="local-region-map",
        command="region-version-remove",
        warnings=[],
        region_versions=load_region_versions(),
    )
