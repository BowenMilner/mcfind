from __future__ import annotations

import unittest
from unittest.mock import patch

from mcfind.services import RouteQueryRequest, StructureQueryRequest, nearest_response, route_response


class _BackendResult:
    def __init__(self, x: int, z: int) -> None:
        self.x = x
        self.z = z
        self.exact = True


class _FakeBackend:
    name = "fake-backend"

    def nearest(self, structure: str, version_enum: int, seed: int, from_x: int, from_z: int, limit: int, timeout: float | None = None) -> list[_BackendResult]:
        return [_BackendResult(128, 256)]

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
    ) -> list[_BackendResult]:
        if structure == "village":
            return [_BackendResult(1, 30), _BackendResult(50, 0)]
        if structure == "stronghold":
            return [_BackendResult(51, 0)]
        return []

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
    ) -> list[_BackendResult]:
        return []


class ServiceTests(unittest.TestCase):
    @patch("mcfind.services.make_backend", return_value=_FakeBackend())
    def test_nearest_response_uses_service_layer_without_cli_parsing(self, _make_backend) -> None:
        envelope = nearest_response(
            StructureQueryRequest(
                seed=12345,
                version="1.21.11",
                origin=(0, 0),
                structures=["stronghold"],
                top=1,
            )
        )

        self.assertEqual(envelope.command, "nearest")
        self.assertEqual(envelope.source_backend, "fake-backend")
        self.assertEqual(envelope.results[0]["x"], 128)
        self.assertEqual(envelope.results[0]["z"], 256)

    @patch("mcfind.services.make_backend", return_value=_FakeBackend())
    def test_route_response_returns_exactly_optimized_order(self, _make_backend) -> None:
        envelope = route_response(
            RouteQueryRequest(
                seed=12345,
                version="1.21.11",
                origin=(0, 0),
                structures=["village", "stronghold"],
                radius=1000,
                limit=2,
            )
        )

        self.assertEqual(envelope.route, {"algorithm": "exact", "total_distance_blocks": 51.0})
        self.assertEqual(
            [(record["structure"], record["x"], record["z"]) for record in envelope.results],
            [("village", 50, 0), ("stronghold", 51, 0)],
        )
