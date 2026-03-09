from __future__ import annotations

import argparse
import sys
from typing import Any

from mcfind.backends.cubiomes import CubiomesBackend
from mcfind.coords import bearing, chunk_coords, distance_blocks, nether_equivalent, parse_coordinate_pair, region_coords
from mcfind.errors import EmptyResultError, McfindError
from mcfind.models import ResponseEnvelope, ResultRecord
from mcfind.output import render_payload
from mcfind.profiles import add_profile, get_profile, load_profiles, remove_profile
from mcfind.region_versions import add_region_version, load_region_versions, remove_region_version, resolve_region_version
from mcfind.save_import import import_java_save
from mcfind.structures import STRUCTURES, get_structure, parse_structures
from mcfind.versioning import EffectiveVersion, require_supported_structure, resolve_version


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="mcfind", description="Offline Minecraft Java structure lookup.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    query_parent = argparse.ArgumentParser(add_help=False)
    query_parent.add_argument("--seed")
    query_parent.add_argument("--edition", default="java")
    query_parent.add_argument("--version")
    query_parent.add_argument("--chunk-version")
    query_parent.add_argument("--profile")
    query_parent.add_argument("--save")
    query_parent.add_argument("--from", dest="from_coords", nargs="*")
    query_parent.add_argument("--from-x", type=int)
    query_parent.add_argument("--from-z", type=int)
    query_parent.add_argument("--structure", "--structures", dest="structures")
    query_parent.add_argument("--dimension", choices=["overworld", "nether", "end"])
    query_parent.add_argument("--backend", choices=["auto", "cubiomes"], default="auto")
    query_parent.add_argument("--cache-dir")
    query_parent.add_argument("--timeout", type=float)
    query_parent.add_argument("--format", choices=["text", "json", "jsonl", "csv"], default="text")
    query_parent.add_argument("--quiet", action="store_true")
    query_parent.add_argument("--no-colour", action="store_true")
    query_parent.add_argument("--exit-on-empty", action="store_true")
    query_parent.add_argument("--limit", type=int)
    query_parent.add_argument("--top", type=int)
    query_parent.add_argument("--sort", choices=["distance", "x", "z", "structure"], default="distance")
    query_parent.add_argument("--fields")
    query_parent.add_argument("--explain", action="store_true")

    nearest = subparsers.add_parser("nearest", parents=[query_parent])
    nearest.set_defaults(handler=handle_nearest)

    within_radius = subparsers.add_parser("within-radius", parents=[query_parent])
    within_radius.add_argument("--radius", type=int, required=True)
    within_radius.set_defaults(limit=10)
    within_radius.set_defaults(handler=handle_within_radius)

    route = subparsers.add_parser("route", parents=[query_parent])
    route.add_argument("--radius", type=int, default=20000)
    route.set_defaults(limit=5)
    route.set_defaults(handler=handle_route)

    seed_info = subparsers.add_parser("seed-info", parents=[query_parent])
    seed_info.set_defaults(handler=handle_seed_info)

    import_save = subparsers.add_parser("import-save")
    import_save.add_argument("path")
    import_save.add_argument("--format", choices=["text", "json", "jsonl", "csv"], default="text")
    import_save.add_argument("--quiet", action="store_true")
    import_save.add_argument("--fields")
    import_save.set_defaults(handler=handle_import_save)

    profile = subparsers.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    profile_add = profile_sub.add_parser("add")
    profile_add.add_argument("name")
    profile_add.add_argument("--seed", required=True)
    profile_add.add_argument("--version", required=True)
    profile_add.add_argument("--base", nargs=2, metavar=("X", "Z"), required=True)
    profile_add.add_argument("--format", choices=["text", "json"], default="text")
    profile_add.set_defaults(handler=handle_profile_add)
    profile_list = profile_sub.add_parser("list")
    profile_list.add_argument("--format", choices=["text", "json"], default="text")
    profile_list.set_defaults(handler=handle_profile_list)
    profile_remove = profile_sub.add_parser("remove")
    profile_remove.add_argument("name")
    profile_remove.add_argument("--format", choices=["text", "json"], default="text")
    profile_remove.set_defaults(handler=handle_profile_remove)

    region = subparsers.add_parser("region-version")
    region_sub = region.add_subparsers(dest="region_command", required=True)
    region_add = region_sub.add_parser("add")
    region_add.add_argument("--rect", nargs=4, type=int, required=True, metavar=("X1", "Z1", "X2", "Z2"))
    region_add.add_argument("--version", required=True)
    region_add.add_argument("--format", choices=["text", "json"], default="text")
    region_add.set_defaults(handler=handle_region_add)
    region_list = region_sub.add_parser("list")
    region_list.add_argument("--format", choices=["text", "json"], default="text")
    region_list.set_defaults(handler=handle_region_list)
    region_remove = region_sub.add_parser("remove")
    region_remove.add_argument("index", type=int)
    region_remove.add_argument("--format", choices=["text", "json"], default="text")
    region_remove.set_defaults(handler=handle_region_remove)

    namespace = parser.parse_args(argv_list)
    if namespace.command == "nearest" and "--limit" not in argv_list and namespace.top is None:
        namespace.limit = 1
    return namespace


def parse_seed(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise McfindError("invalid seed", hint="Seeds must be signed 64-bit integers.") from exc


def selected_fields(args: argparse.Namespace) -> list[str] | None:
    if not getattr(args, "fields", None):
        return None
    return [field.strip() for field in args.fields.split(",") if field.strip()]


def resolve_query_inputs(args: argparse.Namespace) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    profile = get_profile(args.profile) if getattr(args, "profile", None) else None
    save = import_java_save(args.save) if getattr(args, "save", None) else None
    return profile, save


def resolve_seed(args: argparse.Namespace, profile: dict[str, Any] | None, save: dict[str, Any] | None) -> int:
    seed = parse_seed(getattr(args, "seed", None))
    if seed is not None:
        return seed
    if profile and profile.get("seed") is not None:
        return int(profile["seed"])
    if save and save.get("seed") is not None:
        return int(save["seed"])
    raise McfindError("invalid seed", hint="Provide --seed, --profile, or --save.")


def resolve_origin(args: argparse.Namespace, profile: dict[str, Any] | None, save: dict[str, Any] | None) -> tuple[int, int]:
    raw = getattr(args, "from_coords", None)
    if raw:
        if len(raw) == 1 and str(raw[0]).lower() == "spawn":
            if not save:
                raise McfindError('Cannot use `--from spawn` without `--save`.')
            spawn = save["spawn"]
            return int(spawn["x"]), int(spawn["z"])
        return parse_coordinate_pair(raw)
    if getattr(args, "from_x", None) is not None and getattr(args, "from_z", None) is not None:
        return int(args.from_x), int(args.from_z)
    if profile and profile.get("base"):
        return int(profile["base"][0]), int(profile["base"][1])
    if save and getattr(args, "command", None) != "seed-info":
        spawn = save.get("spawn") or {}
        return int(spawn.get("x", 0)), int(spawn.get("z", 0))
    raise McfindError("invalid coordinate pair", hint="Provide --from, --from-x/--from-z, a profile base, or a save.")


def resolve_effective_version(
    args: argparse.Namespace,
    origin: tuple[int, int] | None,
    profile: dict[str, Any] | None,
    save: dict[str, Any] | None,
    warnings: list[str],
) -> EffectiveVersion:
    requested = getattr(args, "chunk_version", None) or getattr(args, "version", None)
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


def resolve_backend_name(structure: str, dimension: str) -> str:
    definition = get_structure(structure)
    if structure == "ruined_portal" and dimension == "nether":
        return "ruined_portal_nether"
    return definition.backend_name


def make_backend(args: argparse.Namespace) -> CubiomesBackend:
    if args.backend not in {"auto", "cubiomes"}:
        raise McfindError(f'backend "{args.backend}" is not available.')
    return CubiomesBackend(cache_dir=args.cache_dir)


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


def sort_results(records: list[ResultRecord], sort_key: str) -> list[ResultRecord]:
    key_funcs = {
        "distance": lambda item: (item.distance_blocks, item.structure, item.x, item.z),
        "x": lambda item: (item.x, item.z, item.structure),
        "z": lambda item: (item.z, item.x, item.structure),
        "structure": lambda item: (item.structure, item.distance_blocks, item.x, item.z),
    }
    return sorted(records, key=key_funcs[sort_key])


def build_query_context(args: argparse.Namespace) -> tuple[CubiomesBackend, list[str], dict[str, Any] | None, dict[str, Any] | None, int, tuple[int, int], EffectiveVersion, str, list[str]]:
    if args.edition != "java":
        raise McfindError('Only `--edition java` is supported in this build.')
    structures = parse_structures(args.structures)
    warnings: list[str] = []
    profile, save = resolve_query_inputs(args)
    origin = resolve_origin(args, profile, save)
    effective = resolve_effective_version(args, origin, profile, save, warnings)
    dimension = resolve_dimension(structures, args.dimension)
    backend = make_backend(args)
    seed = resolve_seed(args, profile, save)
    if args.command in {"within-radius", "route"} and resolve_region_version(origin[0], origin[1]) and not args.chunk_version:
        warnings.append("Mixed-version support currently resolves by origin chunk. Queries spanning multiple generation regions should use --chunk-version explicitly.")
    return backend, structures, profile, save, seed, origin, effective, dimension, warnings


def explain_payload(effective: EffectiveVersion, backend_name: str, structures: list[str]) -> dict[str, Any]:
    return {
        "version": effective.explanation,
        "backend": f"{backend_name} computes structure placement locally from cubiomes logic.",
        "results": [get_structure(name).exactness_note for name in structures if get_structure(name).exactness_note],
    }


def handle_nearest(args: argparse.Namespace) -> ResponseEnvelope:
    backend, structures, _profile, _save, seed, origin, effective, dimension, warnings = build_query_context(args)
    limit = args.top or args.limit or 1
    records: list[ResultRecord] = []
    for structure_name in structures:
        definition = get_structure(structure_name)
        require_supported_structure(definition.min_version, effective, structure_name, backend.name)
        backend_name = resolve_backend_name(structure_name, dimension)
        results = backend.nearest(
            backend_name,
            effective.cubiomes_mc,
            seed,
            origin[0],
            origin[1],
            limit,
            timeout=args.timeout,
        )
        records.extend(
            hydrate_result(structure_name, dimension, origin[0], origin[1], result.x, result.z)
            for result in results
        )
    if not records and args.exit_on_empty:
        raise EmptyResultError(hint="Try increasing --top or checking the version/dimension.")
    records = sort_results(records, args.sort)
    return ResponseEnvelope(
        seed=seed,
        edition=args.edition,
        version_requested=effective.requested,
        version_effective=effective.effective,
        source_backend=backend.name,
        command="nearest",
        warnings=warnings,
        results=[record.to_dict() for record in records],
        explain=explain_payload(effective, backend.name, structures) if args.explain else None,
    )


def handle_within_radius(args: argparse.Namespace) -> ResponseEnvelope:
    backend, structures, _profile, _save, seed, origin, effective, dimension, warnings = build_query_context(args)
    limit = args.limit
    records: list[ResultRecord] = []
    for structure_name in structures:
        definition = get_structure(structure_name)
        require_supported_structure(definition.min_version, effective, structure_name, backend.name)
        backend_name = resolve_backend_name(structure_name, dimension)
        results = backend.within_radius(
            backend_name,
            effective.cubiomes_mc,
            seed,
            origin[0],
            origin[1],
            args.radius,
            limit,
            timeout=args.timeout,
        )
        records.extend(
            hydrate_result(structure_name, dimension, origin[0], origin[1], result.x, result.z)
            for result in results
        )
    if not records and args.exit_on_empty:
        raise EmptyResultError(hint="Try increasing --radius or confirming the selected version.")
    records = sort_results(records, args.sort)
    return ResponseEnvelope(
        seed=seed,
        edition=args.edition,
        version_requested=effective.requested,
        version_effective=effective.effective,
        source_backend=backend.name,
        command="within-radius",
        warnings=warnings,
        results=[record.to_dict() for record in records],
        explain=explain_payload(effective, backend.name, structures) if args.explain else None,
    )


def handle_route(args: argparse.Namespace) -> ResponseEnvelope:
    backend, structures, _profile, _save, seed, origin, effective, dimension, warnings = build_query_context(args)
    per_structure_limit = args.limit
    candidates: dict[str, list[ResultRecord]] = {}
    for structure_name in structures:
        definition = get_structure(structure_name)
        require_supported_structure(definition.min_version, effective, structure_name, backend.name)
        backend_name = resolve_backend_name(structure_name, dimension)
        results = backend.within_radius(
            backend_name,
            effective.cubiomes_mc,
            seed,
            origin[0],
            origin[1],
            args.radius,
            per_structure_limit,
            timeout=args.timeout,
        )
        candidates[structure_name] = [
            hydrate_result(structure_name, dimension, origin[0], origin[1], result.x, result.z)
            for result in results
        ]
    current = origin
    remaining = set(structures)
    ordered: list[ResultRecord] = []
    total = 0.0
    while remaining:
        best: tuple[str, ResultRecord, float] | None = None
        for structure_name in list(remaining):
            for candidate in candidates.get(structure_name, []):
                step_distance = distance_blocks(current[0], current[1], candidate.x, candidate.z)
                if best is None or step_distance < best[2]:
                    best = (structure_name, candidate, step_distance)
        if best is None:
            break
        remaining.remove(best[0])
        ordered.append(best[1])
        total += best[2]
        current = (best[1].x, best[1].z)
    if not ordered and args.exit_on_empty:
        raise EmptyResultError(hint="Try increasing --radius or --limit.")
    return ResponseEnvelope(
        seed=seed,
        edition=args.edition,
        version_requested=effective.requested,
        version_effective=effective.effective,
        source_backend=backend.name,
        command="route",
        warnings=warnings,
        results=[record.to_dict() for record in ordered],
        route={"algorithm": "greedy", "total_distance_blocks": round(total, 1)},
        explain=explain_payload(effective, backend.name, structures) if args.explain else None,
    )


def handle_seed_info(args: argparse.Namespace) -> ResponseEnvelope:
    if args.edition != "java":
        raise McfindError('Only `--edition java` is supported in this build.')
    profile, save = resolve_query_inputs(args)
    warnings: list[str] = []
    seed = resolve_seed(args, profile, save)
    origin = (0, 0)
    if args.from_coords or (args.from_x is not None and args.from_z is not None) or profile or save:
        try:
            origin = resolve_origin(args, profile, save)
        except McfindError:
            origin = (0, 0)
    effective = resolve_effective_version(args, origin, profile, save, warnings)
    structures = parse_structures(args.structures) if args.structures else sorted(STRUCTURES.keys())
    dimension = resolve_dimension(structures, args.dimension) if args.structures else "overworld"
    backend = make_backend(args)
    supported = []
    for structure_name in structures:
        definition = get_structure(structure_name)
        require_supported_structure(definition.min_version, effective, structure_name, backend.name)
        supported.append(structure_name)
    return ResponseEnvelope(
        seed=seed,
        edition=args.edition,
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
        explain=explain_payload(effective, backend.name, structures) if args.explain else None,
    )


def handle_import_save(args: argparse.Namespace) -> ResponseEnvelope:
    save = import_java_save(args.path)
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


def handle_profile_add(args: argparse.Namespace) -> ResponseEnvelope:
    payload = {
        "name": args.name,
        "seed": parse_seed(args.seed),
        "version": args.version,
        "base": [int(args.base[0]), int(args.base[1])],
    }
    add_profile(args.name, payload)
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


def handle_profile_list(args: argparse.Namespace) -> ResponseEnvelope:
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


def handle_profile_remove(args: argparse.Namespace) -> ResponseEnvelope:
    remove_profile(args.name)
    return ResponseEnvelope(
        seed=None,
        edition="java",
        version_requested=None,
        version_effective=None,
        source_backend="local-profile",
        command="profile-remove",
        warnings=[],
        profiles=[{"name": args.name}],
    )


def handle_region_add(args: argparse.Namespace) -> ResponseEnvelope:
    record = add_region_version(tuple(args.rect), args.version)
    return ResponseEnvelope(
        seed=None,
        edition="java",
        version_requested=args.version,
        version_effective=resolve_version(args.version).effective,
        source_backend="local-region-map",
        command="region-version-add",
        warnings=[],
        region_versions=[record],
    )


def handle_region_list(args: argparse.Namespace) -> ResponseEnvelope:
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


def handle_region_remove(args: argparse.Namespace) -> ResponseEnvelope:
    remove_region_version(args.index - 1)
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


def emit_response(envelope: ResponseEnvelope, args: argparse.Namespace) -> int:
    payload = envelope.to_dict()
    print(render_payload(payload, args.format, fields=selected_fields(args), quiet=getattr(args, "quiet", False)))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        envelope = args.handler(args)
        return emit_response(envelope, args)
    except McfindError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        if exc.hint:
            print(f"Hint: {exc.hint}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
