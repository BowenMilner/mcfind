from __future__ import annotations

import re
from dataclasses import dataclass

from mcfind.errors import McfindError


@dataclass(frozen=True, slots=True)
class BiomeDefinition:
    canonical_name: str
    biome_id: int
    dimension: str
    min_version: str
    sample_y: int
    exactness_note: str | None = None


BIOMES: dict[str, BiomeDefinition] = {
    "ocean": BiomeDefinition("ocean", 0, "overworld", "b1.8", 64),
    "plains": BiomeDefinition("plains", 1, "overworld", "b1.8", 64),
    "desert": BiomeDefinition("desert", 2, "overworld", "b1.8", 64),
    "forest": BiomeDefinition("forest", 4, "overworld", "b1.8", 64),
    "taiga": BiomeDefinition("taiga", 5, "overworld", "b1.8", 64),
    "swamp": BiomeDefinition("swamp", 6, "overworld", "b1.8", 64),
    "river": BiomeDefinition("river", 7, "overworld", "b1.8", 64),
    "frozen_ocean": BiomeDefinition("frozen_ocean", 10, "overworld", "b1.8", 64),
    "jungle": BiomeDefinition("jungle", 21, "overworld", "1.2", 64),
    "deep_ocean": BiomeDefinition("deep_ocean", 24, "overworld", "1.7", 64),
    "birch_forest": BiomeDefinition("birch_forest", 27, "overworld", "1.7", 64),
    "dark_forest": BiomeDefinition("dark_forest", 29, "overworld", "1.7", 64),
    "badlands": BiomeDefinition("badlands", 37, "overworld", "1.7", 64),
    "small_end_islands": BiomeDefinition("small_end_islands", 40, "end", "1.9", 64),
    "the_end": BiomeDefinition("the_end", 9, "end", "1.0", 64),
    "bamboo_jungle": BiomeDefinition("bamboo_jungle", 168, "overworld", "1.14", 64),
    "meadow": BiomeDefinition("meadow", 177, "overworld", "1.18", 96),
    "grove": BiomeDefinition("grove", 178, "overworld", "1.18", 96),
    "jagged_peaks": BiomeDefinition("jagged_peaks", 180, "overworld", "1.18", 128),
    "frozen_peaks": BiomeDefinition("frozen_peaks", 181, "overworld", "1.18", 128),
    "stony_peaks": BiomeDefinition("stony_peaks", 182, "overworld", "1.18", 128),
    "mushroom_fields": BiomeDefinition("mushroom_fields", 14, "overworld", "b1.8", 64),
    "mangrove_swamp": BiomeDefinition("mangrove_swamp", 184, "overworld", "1.19", 64),
    "cherry_grove": BiomeDefinition("cherry_grove", 185, "overworld", "1.20", 96),
    "pale_garden": BiomeDefinition("pale_garden", 186, "overworld", "1.21.x", 64),
    "warm_ocean": BiomeDefinition("warm_ocean", 44, "overworld", "1.13", 64),
    "lukewarm_ocean": BiomeDefinition("lukewarm_ocean", 45, "overworld", "1.13", 64),
    "cold_ocean": BiomeDefinition("cold_ocean", 46, "overworld", "1.13", 64),
    "deep_warm_ocean": BiomeDefinition("deep_warm_ocean", 47, "overworld", "1.13", 64),
    "deep_lukewarm_ocean": BiomeDefinition("deep_lukewarm_ocean", 48, "overworld", "1.13", 64),
    "deep_cold_ocean": BiomeDefinition("deep_cold_ocean", 49, "overworld", "1.13", 64),
    "deep_frozen_ocean": BiomeDefinition("deep_frozen_ocean", 50, "overworld", "1.13", 64),
    "nether_wastes": BiomeDefinition("nether_wastes", 8, "nether", "1.16.1", 33),
    "soul_sand_valley": BiomeDefinition("soul_sand_valley", 170, "nether", "1.16.1", 33),
    "crimson_forest": BiomeDefinition("crimson_forest", 171, "nether", "1.16.1", 33),
    "warped_forest": BiomeDefinition("warped_forest", 172, "nether", "1.16.1", 33),
    "basalt_deltas": BiomeDefinition("basalt_deltas", 173, "nether", "1.16.1", 33),
    "end_midlands": BiomeDefinition("end_midlands", 41, "end", "1.9", 64),
    "end_highlands": BiomeDefinition("end_highlands", 42, "end", "1.9", 64),
    "end_barrens": BiomeDefinition("end_barrens", 43, "end", "1.9", 64),
}

ALIASES: dict[str, str] = {
    "ocean": "ocean",
    "plains": "plains",
    "desert": "desert",
    "forest": "forest",
    "taiga": "taiga",
    "swamp": "swamp",
    "river": "river",
    "frozen ocean": "frozen_ocean",
    "frozen_ocean": "frozen_ocean",
    "frozenocean": "frozen_ocean",
    "jungle": "jungle",
    "deep ocean": "deep_ocean",
    "deep_ocean": "deep_ocean",
    "deepocean": "deep_ocean",
    "birch forest": "birch_forest",
    "birch_forest": "birch_forest",
    "birchforest": "birch_forest",
    "dark forest": "dark_forest",
    "dark_forest": "dark_forest",
    "darkforest": "dark_forest",
    "badlands": "badlands",
    "mesa": "badlands",
    "small end islands": "small_end_islands",
    "small_end_islands": "small_end_islands",
    "smallendislands": "small_end_islands",
    "the end": "the_end",
    "the_end": "the_end",
    "theend": "the_end",
    "bamboo jungle": "bamboo_jungle",
    "bamboo_jungle": "bamboo_jungle",
    "bamboojungle": "bamboo_jungle",
    "meadow": "meadow",
    "grove": "grove",
    "jagged peaks": "jagged_peaks",
    "jagged_peaks": "jagged_peaks",
    "jaggedpeaks": "jagged_peaks",
    "frozen peaks": "frozen_peaks",
    "frozen_peaks": "frozen_peaks",
    "frozenpeaks": "frozen_peaks",
    "stony peaks": "stony_peaks",
    "stony_peaks": "stony_peaks",
    "stonypeaks": "stony_peaks",
    "mushroom fields": "mushroom_fields",
    "mushroom_fields": "mushroom_fields",
    "mushroomfields": "mushroom_fields",
    "mangrove swamp": "mangrove_swamp",
    "mangrove_swamp": "mangrove_swamp",
    "mangroveswamp": "mangrove_swamp",
    "cherry grove": "cherry_grove",
    "cherry_grove": "cherry_grove",
    "cherrygrove": "cherry_grove",
    "pale garden": "pale_garden",
    "pale_garden": "pale_garden",
    "palegarden": "pale_garden",
    "warm ocean": "warm_ocean",
    "warm_ocean": "warm_ocean",
    "warmocean": "warm_ocean",
    "lukewarm ocean": "lukewarm_ocean",
    "lukewarm_ocean": "lukewarm_ocean",
    "lukewarmocean": "lukewarm_ocean",
    "cold ocean": "cold_ocean",
    "cold_ocean": "cold_ocean",
    "coldocean": "cold_ocean",
    "deep warm ocean": "deep_warm_ocean",
    "deep_warm_ocean": "deep_warm_ocean",
    "deepwarmocean": "deep_warm_ocean",
    "deep lukewarm ocean": "deep_lukewarm_ocean",
    "deep_lukewarm_ocean": "deep_lukewarm_ocean",
    "deeplukewarmocean": "deep_lukewarm_ocean",
    "deep cold ocean": "deep_cold_ocean",
    "deep_cold_ocean": "deep_cold_ocean",
    "deepcoldocean": "deep_cold_ocean",
    "deep frozen ocean": "deep_frozen_ocean",
    "deep_frozen_ocean": "deep_frozen_ocean",
    "deepfrozenocean": "deep_frozen_ocean",
    "nether wastes": "nether_wastes",
    "nether_wastes": "nether_wastes",
    "netherwastes": "nether_wastes",
    "soul sand valley": "soul_sand_valley",
    "soul_sand_valley": "soul_sand_valley",
    "soulsandvalley": "soul_sand_valley",
    "crimson forest": "crimson_forest",
    "crimson_forest": "crimson_forest",
    "crimsonforest": "crimson_forest",
    "warped forest": "warped_forest",
    "warped_forest": "warped_forest",
    "warpedforest": "warped_forest",
    "basalt deltas": "basalt_deltas",
    "basalt_deltas": "basalt_deltas",
    "basaltdeltas": "basalt_deltas",
    "end midlands": "end_midlands",
    "end_midlands": "end_midlands",
    "endmidlands": "end_midlands",
    "end highlands": "end_highlands",
    "end_highlands": "end_highlands",
    "endhighlands": "end_highlands",
    "end barrens": "end_barrens",
    "end_barrens": "end_barrens",
    "endbarrens": "end_barrens",
}


def _normalize_token(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value.strip().lower())


def parse_biomes(value: str | list[str]) -> list[str]:
    tokens = [value] if isinstance(value, str) else value
    parsed: list[str] = []
    for token in tokens:
        for part in str(token).split(","):
            candidate = part.strip()
            if not candidate:
                continue
            alias = ALIASES.get(candidate.lower()) or ALIASES.get(_normalize_token(candidate))
            if not alias:
                raise McfindError(
                    f'Unsupported biome "{candidate}".',
                    hint=f"Supported biomes: {', '.join(sorted(BIOMES))}.",
                )
            if alias not in parsed:
                parsed.append(alias)
    if not parsed:
        raise McfindError("At least one biome must be provided.")
    return parsed


def get_biome(name: str) -> BiomeDefinition:
    return BIOMES[name]
