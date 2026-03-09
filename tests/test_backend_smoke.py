from __future__ import annotations

import unittest

from mcfind.backends.cubiomes import CubiomesBackend


class BackendSmokeTests(unittest.TestCase):
    def test_stronghold_query_returns_a_result(self) -> None:
        backend = CubiomesBackend()
        results = backend.nearest("stronghold", 28, -461418396194504394, 780, 874, 1)
        self.assertEqual(len(results), 1)
