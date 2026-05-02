from __future__ import annotations

import argparse
import sys

from mcfind.coords import parse_coordinate_pair
from mcfind.errors import McfindError
from mcfind.models import ResponseEnvelope
from mcfind.output import render_payload
from mcfind.services import (
    BiomeQueryRequest,
    ProfileAddRequest,
    RadiusQueryRequest,
    RegionVersionAddRequest,
    RouteQueryRequest,
    SeedInfoRequest,
    StructureQueryRequest,
    import_save_response,
    nearest_biome_response,
    nearest_response,
    parse_seed,
    profile_add_response,
    profile_list_response,
    profile_remove_response,
    region_add_response,
    region_list_response,
    region_remove_response,
    route_response,
    seed_info_response,
    within_radius_response,
)


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
    query_parent.add_argument("--biome", "--biomes", dest="biomes")
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

    nearest_biome = subparsers.add_parser("nearest-biome", parents=[query_parent])
    nearest_biome.set_defaults(handler=handle_nearest_biome)

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


def _origin_from_args(args: argparse.Namespace) -> tuple[tuple[int, int] | None, bool]:
    raw = getattr(args, "from_coords", None)
    if raw:
        if len(raw) == 1 and str(raw[0]).lower() == "spawn":
            return None, True
        return parse_coordinate_pair(raw), False
    if getattr(args, "from_x", None) is not None and getattr(args, "from_z", None) is not None:
        return (int(args.from_x), int(args.from_z)), False
    return None, False


def _common_query_kwargs(args: argparse.Namespace) -> dict[str, object]:
    origin, use_spawn = _origin_from_args(args)
    return {
        "seed": parse_seed(getattr(args, "seed", None)),
        "edition": getattr(args, "edition", "java"),
        "version": getattr(args, "version", None),
        "chunk_version": getattr(args, "chunk_version", None),
        "profile": getattr(args, "profile", None),
        "save": getattr(args, "save", None),
        "origin": origin,
        "use_spawn": use_spawn,
        "dimension": getattr(args, "dimension", None),
        "backend": getattr(args, "backend", "auto"),
        "cache_dir": getattr(args, "cache_dir", None),
        "timeout": getattr(args, "timeout", None),
        "explain": getattr(args, "explain", False),
    }


def selected_fields(args: argparse.Namespace) -> list[str] | None:
    if not getattr(args, "fields", None):
        return None
    return [field.strip() for field in args.fields.split(",") if field.strip()]


def handle_nearest(args: argparse.Namespace) -> ResponseEnvelope:
    return nearest_response(
        StructureQueryRequest(
            **_common_query_kwargs(args),
            structures=args.structures,
            top=args.top,
            limit=args.limit,
            sort=args.sort,
            exit_on_empty=args.exit_on_empty,
        )
    )


def handle_nearest_biome(args: argparse.Namespace) -> ResponseEnvelope:
    return nearest_biome_response(
        BiomeQueryRequest(
            **_common_query_kwargs(args),
            biomes=args.biomes,
            top=args.top,
            limit=args.limit,
            sort=args.sort,
            exit_on_empty=args.exit_on_empty,
        )
    )


def handle_within_radius(args: argparse.Namespace) -> ResponseEnvelope:
    return within_radius_response(
        RadiusQueryRequest(
            **_common_query_kwargs(args),
            structures=args.structures,
            radius=args.radius,
            limit=args.limit,
            sort=args.sort,
            exit_on_empty=args.exit_on_empty,
        )
    )


def handle_route(args: argparse.Namespace) -> ResponseEnvelope:
    return route_response(
        RouteQueryRequest(
            **_common_query_kwargs(args),
            structures=args.structures,
            radius=args.radius,
            limit=args.limit,
            exit_on_empty=args.exit_on_empty,
        )
    )


def handle_seed_info(args: argparse.Namespace) -> ResponseEnvelope:
    return seed_info_response(SeedInfoRequest(**_common_query_kwargs(args), structures=args.structures))


def handle_import_save(args: argparse.Namespace) -> ResponseEnvelope:
    return import_save_response(args.path)


def handle_profile_add(args: argparse.Namespace) -> ResponseEnvelope:
    return profile_add_response(
        ProfileAddRequest(
            name=args.name,
            seed=args.seed,
            version=args.version,
            base=(int(args.base[0]), int(args.base[1])),
        )
    )


def handle_profile_list(_args: argparse.Namespace) -> ResponseEnvelope:
    return profile_list_response()


def handle_profile_remove(args: argparse.Namespace) -> ResponseEnvelope:
    return profile_remove_response(args.name)


def handle_region_add(args: argparse.Namespace) -> ResponseEnvelope:
    return region_add_response(RegionVersionAddRequest(rect=tuple(args.rect), version=args.version))


def handle_region_list(_args: argparse.Namespace) -> ResponseEnvelope:
    return region_list_response()


def handle_region_remove(args: argparse.Namespace) -> ResponseEnvelope:
    return region_remove_response(args.index)


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
