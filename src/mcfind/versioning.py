from __future__ import annotations

from dataclasses import dataclass
import re

from mcfind.errors import McfindError


@dataclass(frozen=True, slots=True)
class EffectiveVersion:
    requested: str
    effective: str
    backend_key: str
    cubiomes_mc: int
    warnings: list[str]
    explanation: str


_ORDER = [
    "b1.7",
    "b1.8",
    "1.0",
    "1.1",
    "1.2",
    "1.3",
    "1.4",
    "1.5",
    "1.6",
    "1.7",
    "1.8",
    "1.9",
    "1.10",
    "1.11",
    "1.12",
    "1.13",
    "1.14",
    "1.15",
    "1.16.1",
    "1.16",
    "1.17",
    "1.18",
    "1.19.2",
    "1.19",
    "1.20",
    "1.21.1",
    "1.21.3",
    "1.21.x",
]

_CUBIOMES_ENUMS = {
    "b1.7": 1,
    "b1.8": 2,
    "1.0": 3,
    "1.1": 4,
    "1.2": 5,
    "1.3": 6,
    "1.4": 7,
    "1.5": 8,
    "1.6": 9,
    "1.7": 10,
    "1.8": 11,
    "1.9": 12,
    "1.10": 13,
    "1.11": 14,
    "1.12": 15,
    "1.13": 16,
    "1.14": 17,
    "1.15": 18,
    "1.16.1": 19,
    "1.16": 20,
    "1.17": 21,
    "1.18": 22,
    "1.19.2": 23,
    "1.19": 24,
    "1.20": 25,
    "1.21.1": 26,
    "1.21.3": 27,
    "1.21.x": 28,
}


def version_rank(version: str) -> int:
    try:
        return _ORDER.index(version)
    except ValueError as exc:
        raise McfindError(f'Unsupported version "{version}".') from exc


def resolve_version(requested: str | None) -> EffectiveVersion:
    if not requested:
        requested = "1.21.11"
    text = requested.strip().lower()
    warnings: list[str] = []
    if text in {"1.21", "1.21.x"}:
        return EffectiveVersion(
            requested=requested,
            effective="1.21.x",
            backend_key="1.21.x",
            cubiomes_mc=_CUBIOMES_ENUMS["1.21.x"],
            warnings=[],
            explanation="Requested 1.21 family input maps to the latest 1.21.x rules exposed by cubiomes.",
        )
    if text in {"1.20", "1.20.x"}:
        return EffectiveVersion(
            requested=requested,
            effective="1.20.x",
            backend_key="1.20",
            cubiomes_mc=_CUBIOMES_ENUMS["1.20"],
            warnings=[],
            explanation="Requested 1.20 family input maps to cubiomes' latest 1.20 release rules.",
        )
    if text.startswith("b1."):
        normalized = text
        if normalized not in _CUBIOMES_ENUMS:
            raise McfindError(
                f'Unsupported version "{requested}".',
                hint="Supported beta inputs currently start at b1.7 or b1.8.",
            )
        return EffectiveVersion(
            requested=requested,
            effective=normalized,
            backend_key=normalized,
            cubiomes_mc=_CUBIOMES_ENUMS[normalized],
            warnings=[],
            explanation=f"Requested version {requested} maps directly to cubiomes beta rules.",
        )
    match = re.fullmatch(r"1\.(\d+)(?:\.(\d+))?", text)
    if not match:
        raise McfindError(
            f'Unsupported version "{requested}".',
            hint="Use a Java version like 1.21.11 or 1.20.4.",
        )
    minor = int(match.group(1))
    patch = int(match.group(2) or "0")
    if minor < 0:
        raise McfindError(f'Unsupported version "{requested}".')
    if minor <= 15:
        key = f"1.{minor}"
    elif minor == 16 and patch == 1:
        key = "1.16.1"
    elif minor in {16, 17, 18}:
        key = f"1.{minor}"
    elif minor == 19 and patch <= 2:
        key = "1.19.2"
    elif minor == 19:
        key = "1.19"
    elif minor == 20:
        key = "1.20"
        if patch not in {0, 6}:
            warnings.append(
                f"Requested version {requested} is normalized to cubiomes 1.20.x rules. Patch-level differences are not modeled."
            )
    elif minor == 21:
        if patch <= 1:
            key = "1.21.1"
        elif patch <= 3:
            key = "1.21.3"
        else:
            key = "1.21.x"
        if text not in {"1.21.1", "1.21.2", "1.21.3", "1.21"}:
            warnings.append(
                f"Requested version {requested} is normalized to cubiomes 1.21.x rules. Patch-level differences are not modeled."
            )
    else:
        raise McfindError(
            f'Unsupported version "{requested}".',
            hint="Current backend support in this build tops out at the 1.21 family.",
        )
    effective = "1.20.x" if key == "1.20" else "1.21.x" if key == "1.21.x" else key
    return EffectiveVersion(
        requested=requested,
        effective=effective,
        backend_key=key,
        cubiomes_mc=_CUBIOMES_ENUMS[key],
        warnings=warnings,
        explanation=f"Requested version {requested} maps to backend key {key}.",
    )


def require_supported_structure(min_version: str, effective: EffectiveVersion, structure_name: str, backend_name: str) -> None:
    if version_rank(effective.backend_key) < version_rank(min_version):
        raise McfindError(
            f'structure "{structure_name}" is not supported by backend "{backend_name}" for effective version "{effective.backend_key}".',
            hint=f"{structure_name.replace('_', ' ')} requires {min_version}+ world generation.",
        )
