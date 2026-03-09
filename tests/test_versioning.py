from __future__ import annotations

import unittest

from mcfind.errors import McfindError
from mcfind.versioning import resolve_version


class VersioningTests(unittest.TestCase):
    def test_resolves_12111_to_family(self) -> None:
        resolved = resolve_version("1.21.11")
        self.assertEqual(resolved.effective, "1.21.x")
        self.assertEqual(resolved.backend_key, "1.21.x")
        self.assertTrue(resolved.warnings)

    def test_resolves_1204_to_120_family(self) -> None:
        resolved = resolve_version("1.20.4")
        self.assertEqual(resolved.effective, "1.20.x")
        self.assertEqual(resolved.backend_key, "1.20")

    def test_rejects_unsupported_version(self) -> None:
        with self.assertRaises(McfindError):
            resolve_version("1.22.0")
