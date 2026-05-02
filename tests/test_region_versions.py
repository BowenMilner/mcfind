from __future__ import annotations

import os
import tempfile
import unittest

from mcfind.region_versions import add_region_version, load_region_versions, remove_region_version, resolve_region_version


class RegionVersionTests(unittest.TestCase):
    def test_region_version_roundtrip_and_resolution(self) -> None:
        previous_home = os.environ.get("MCFIND_HOME")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["MCFIND_HOME"] = tmp
            try:
                add_region_version((10, 10, -5, -5), "1.20.4")
                self.assertEqual(load_region_versions()[0]["x1"], -5)
                self.assertEqual(resolve_region_version(0, 0)["version"], "1.20.4")
                remove_region_version(0)
                self.assertEqual(load_region_versions(), [])
            finally:
                if previous_home is None:
                    del os.environ["MCFIND_HOME"]
                else:
                    os.environ["MCFIND_HOME"] = previous_home
