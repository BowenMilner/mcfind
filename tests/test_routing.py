from __future__ import annotations

import unittest

from mcfind.models import ResultRecord
from mcfind.routing import plan_route


def _record(structure: str, x: int, z: int) -> ResultRecord:
    return ResultRecord(
        structure=structure,
        x=x,
        z=z,
        y=None,
        distance_blocks=0.0,
        bearing="E",
    )


class RoutingTests(unittest.TestCase):
    def test_exact_route_chooses_globally_best_candidates(self) -> None:
        candidates = {
            "village": [_record("village", 1, 30), _record("village", 50, 0)],
            "stronghold": [_record("stronghold", 51, 0)],
        }

        plan = plan_route((0, 0), candidates)

        self.assertEqual(plan.algorithm, "exact")
        self.assertEqual([(record.structure, record.x, record.z) for record in plan.results], [("village", 50, 0), ("stronghold", 51, 0)])
        self.assertEqual(round(plan.total_distance_blocks, 1), 51.0)
