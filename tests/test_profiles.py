from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from mcfind.profiles import add_profile, get_profile, load_profiles, remove_profile


class ProfileTests(unittest.TestCase):
    def test_profile_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["MCFIND_HOME"] = tmp
            add_profile("home", {"name": "home", "seed": 42, "version": "1.21.11", "base": [1, 2]})
            self.assertIn("home", load_profiles())
            self.assertEqual(get_profile("home")["seed"], 42)
            remove_profile("home")
            self.assertEqual(load_profiles(), {})
            del os.environ["MCFIND_HOME"]
