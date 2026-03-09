from __future__ import annotations

import re
from dataclasses import dataclass

from mcfind.errors import McfindError


@dataclass(frozen=True, slots=True)
class StructureDefinition:
    canonical_name: str
    backend_name: str
    dimension: str
    min_version: str
    exactness_note: str | None = None


STRUCTURES: dict[str, StructureDefinition] = {
    "stronghold": StructureDefinition(
        canonical_name="stronghold",
        backend_name="stronghold",
        dimension="overworld",
        min_version="b1.8",
        exactness_note="Underground structure. Y is not provided by cubiomes and requires in-game searching.",
    ),
    "trial_chamber": StructureDefinition(
        canonical_name="trial_chamber",
        backend_name="trial_chamber",
        dimension="overworld",
        min_version="1.21.1",
        exactness_note="Underground structure. Coordinates are reliable in X/Z, but Y is unavailable.",
    ),
    "village": StructureDefinition("village", "village", "overworld", "b1.8"),
    "ancient_city": StructureDefinition(
        "ancient_city",
        "ancient_city",
        "overworld",
        "1.19.2",
        exactness_note="Underground structure. Coordinates are reliable in X/Z, but Y is unavailable.",
    ),
    "woodland_mansion": StructureDefinition("woodland_mansion", "mansion", "overworld", "1.11"),
    "ocean_monument": StructureDefinition("ocean_monument", "monument", "overworld", "1.8"),
    "mineshaft": StructureDefinition(
        "mineshaft",
        "mineshaft",
        "overworld",
        "b1.8",
        exactness_note="Mineshafts are distributed densely. Returned coordinates are candidate starts, not a full tunnel map.",
    ),
    "ruined_portal": StructureDefinition("ruined_portal", "ruined_portal", "overworld", "1.16.1"),
    "desert_temple": StructureDefinition("desert_temple", "desert_pyramid", "overworld", "1.3"),
    "jungle_temple": StructureDefinition("jungle_temple", "jungle_temple", "overworld", "1.3"),
    "witch_hut": StructureDefinition("witch_hut", "swamp_hut", "overworld", "1.4"),
    "pillager_outpost": StructureDefinition("pillager_outpost", "outpost", "overworld", "1.14"),
    "bastion_remnant": StructureDefinition("bastion_remnant", "bastion_remnant", "nether", "1.16.1"),
    "nether_fortress": StructureDefinition("nether_fortress", "nether_fortress", "nether", "1.0"),
    "end_city": StructureDefinition("end_city", "end_city", "end", "1.9"),
}

ALIASES: dict[str, str] = {
    "stronghold": "stronghold",
    "trialchamber": "trial_chamber",
    "trialchambers": "trial_chamber",
    "trial_chamber": "trial_chamber",
    "trial chamber": "trial_chamber",
    "trial-chamber": "trial_chamber",
    "village": "village",
    "villages": "village",
    "ancientcity": "ancient_city",
    "ancient_city": "ancient_city",
    "ancient city": "ancient_city",
    "woodlandmansion": "woodland_mansion",
    "woodland_mansion": "woodland_mansion",
    "woodland mansion": "woodland_mansion",
    "mansion": "woodland_mansion",
    "oceanmonument": "ocean_monument",
    "ocean_monument": "ocean_monument",
    "ocean monument": "ocean_monument",
    "monument": "ocean_monument",
    "mineshaft": "mineshaft",
    "ruinedportal": "ruined_portal",
    "ruined_portal": "ruined_portal",
    "ruined portal": "ruined_portal",
    "deserttemple": "desert_temple",
    "desert temple": "desert_temple",
    "desert_temple": "desert_temple",
    "desertpyramid": "desert_temple",
    "jungletemple": "jungle_temple",
    "jungle temple": "jungle_temple",
    "jungle_temple": "jungle_temple",
    "witchhut": "witch_hut",
    "witch hut": "witch_hut",
    "witch_hut": "witch_hut",
    "swamphut": "witch_hut",
    "pillageroutpost": "pillager_outpost",
    "pillager_outpost": "pillager_outpost",
    "pillager outpost": "pillager_outpost",
    "outpost": "pillager_outpost",
    "bastion": "bastion_remnant",
    "bastionremnant": "bastion_remnant",
    "bastion_remnant": "bastion_remnant",
    "bastion remnant": "bastion_remnant",
    "fortress": "nether_fortress",
    "netherfortress": "nether_fortress",
    "nether_fortress": "nether_fortress",
    "nether fortress": "nether_fortress",
    "endcity": "end_city",
    "end_city": "end_city",
    "end city": "end_city",
}


def _normalize_token(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value.strip().lower())


def parse_structures(value: str | list[str]) -> list[str]:
    tokens = [value] if isinstance(value, str) else value
    parsed: list[str] = []
    for token in tokens:
        for part in str(token).split(","):
            candidate = part.strip()
            if not candidate:
                continue
            alias = ALIASES.get(candidate.strip().lower()) or ALIASES.get(_normalize_token(candidate))
            if not alias:
                raise McfindError(
                    f'Unsupported structure "{candidate}".',
                    hint=f"Supported structures: {', '.join(sorted(STRUCTURES))}.",
                )
            if alias not in parsed:
                parsed.append(alias)
    if not parsed:
        raise McfindError("At least one structure must be provided.")
    return parsed


def get_structure(name: str) -> StructureDefinition:
    return STRUCTURES[name]
