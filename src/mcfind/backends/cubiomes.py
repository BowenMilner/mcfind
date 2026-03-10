from __future__ import annotations

from ctypes import byref, c_char, c_int

from mcfind.backends.base import BackendResult, WorldgenBackend
from mcfind.backends.cubiomes_native import NativeResult, load_native_library
from mcfind.errors import McfindError


STRUCTURE_ENUMS = {
    "stronghold": -1,
    "desert_pyramid": 1,
    "jungle_temple": 2,
    "swamp_hut": 3,
    "igloo": 4,
    "village": 5,
    "ocean_ruin": 6,
    "shipwreck": 7,
    "monument": 8,
    "mansion": 9,
    "outpost": 10,
    "ruined_portal": 11,
    "ruined_portal_nether": 12,
    "ancient_city": 13,
    "treasure": 14,
    "mineshaft": 15,
    "desert_well": 16,
    "geode": 17,
    "nether_fortress": 18,
    "bastion_remnant": 19,
    "end_city": 20,
    "trail_ruins": 23,
    "trial_chamber": 24,
}


class CubiomesBackend(WorldgenBackend):
    name = "cubiomes"

    def __init__(self, cache_dir: str | None = None) -> None:
        self._lib = load_native_library(cache_dir)

    def _run_query(
        self,
        *,
        structure: str,
        version_enum: int,
        seed: int,
        from_x: int,
        from_z: int,
        radius: int,
        limit: int,
        timeout: float | None,
    ) -> list[BackendResult]:
        native_type = STRUCTURE_ENUMS[structure]
        results = (NativeResult * limit)()
        count = c_int(0)
        error = (c_char * 512)()
        timeout_ms = int(timeout * 1000) if timeout else 0
        ok = self._lib.mcfind_query_structure(
            native_type,
            version_enum,
            seed,
            from_x,
            from_z,
            radius,
            limit,
            timeout_ms,
            results,
            byref(count),
            error,
            len(error),
        )
        if not ok:
            message = bytes(error).split(b"\x00", 1)[0].decode() or "Unknown cubiomes error."
            raise McfindError(message)
        return [
            BackendResult(x=results[index].x, z=results[index].z, exact=bool(results[index].exact))
            for index in range(count.value)
            if results[index].valid
        ]

    def nearest(
        self,
        structure: str,
        version_enum: int,
        seed: int,
        from_x: int,
        from_z: int,
        limit: int,
        timeout: float | None = None,
    ) -> list[BackendResult]:
        return self._run_query(
            structure=structure,
            version_enum=version_enum,
            seed=seed,
            from_x=from_x,
            from_z=from_z,
            radius=0,
            limit=limit,
            timeout=timeout,
        )

    def within_radius(
        self,
        structure: str,
        version_enum: int,
        seed: int,
        from_x: int,
        from_z: int,
        radius: int,
        limit: int,
        timeout: float | None = None,
    ) -> list[BackendResult]:
        return self._run_query(
            structure=structure,
            version_enum=version_enum,
            seed=seed,
            from_x=from_x,
            from_z=from_z,
            radius=radius,
            limit=limit,
            timeout=timeout,
        )

    def nearest_biome(
        self,
        biome_id: int,
        dimension: str,
        sample_y: int,
        version_enum: int,
        seed: int,
        from_x: int,
        from_z: int,
        limit: int,
        timeout: float | None = None,
    ) -> list[BackendResult]:
        dimension_enum = {"overworld": 0, "nether": -1, "end": 1}[dimension]
        results = (NativeResult * limit)()
        count = c_int(0)
        error = (c_char * 512)()
        timeout_ms = int(timeout * 1000) if timeout else 0
        ok = self._lib.mcfind_query_biome(
            biome_id,
            dimension_enum,
            sample_y,
            version_enum,
            seed,
            from_x,
            from_z,
            limit,
            timeout_ms,
            results,
            byref(count),
            error,
            len(error),
        )
        if not ok:
            message = bytes(error).split(b"\x00", 1)[0].decode() or "Unknown cubiomes error."
            raise McfindError(message)
        return [
            BackendResult(x=results[index].x, z=results[index].z, exact=bool(results[index].exact))
            for index in range(count.value)
            if results[index].valid
        ]
