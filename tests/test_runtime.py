from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from mcfind.runtime import write_text_atomic


class RuntimeTests(unittest.TestCase):
    def test_write_text_atomic_replaces_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "profiles.json"
            write_text_atomic(path, "one")
            write_text_atomic(path, "two")

            self.assertEqual(path.read_text(), "two")
            leftovers = [entry.name for entry in path.parent.iterdir() if entry.name != path.name]
            self.assertEqual(leftovers, [])
