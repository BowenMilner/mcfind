from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import nbtlib

from mcfind.save_import import import_java_save


class SaveImportTests(unittest.TestCase):
    def test_import_java_save_reads_seed_spawn_and_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "region").mkdir()
            data = nbtlib.Compound(
                {
                    "Data": nbtlib.Compound(
                        {
                            "LevelName": nbtlib.String("TestWorld"),
                            "SpawnX": nbtlib.Int(10),
                            "SpawnY": nbtlib.Int(64),
                            "SpawnZ": nbtlib.Int(-20),
                            "Version": nbtlib.Compound(
                                {
                                    "Name": nbtlib.String("1.21.11"),
                                    "Id": nbtlib.Int(4189),
                                }
                            ),
                            "WorldGenSettings": nbtlib.Compound({"seed": nbtlib.Long(123456789)}),
                        }
                    )
                }
            )
            nbtlib.File(data).save(root / "level.dat", gzipped=True)
            imported = import_java_save(root)
            self.assertEqual(imported["seed"], 123456789)
            self.assertEqual(imported["spawn"]["x"], 10)
            self.assertEqual(imported["version_name"], "1.21.11")
