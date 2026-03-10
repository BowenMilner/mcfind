from __future__ import annotations

import unittest

from mcfind.biomes import get_biome, parse_biomes


class BiomeTests(unittest.TestCase):
    def test_parses_water_biome_aliases(self) -> None:
        self.assertEqual(parse_biomes("warm ocean"), ["warm_ocean"])
        self.assertEqual(parse_biomes("deep_frozen_ocean"), ["deep_frozen_ocean"])

    def test_parses_nether_and_end_biomes(self) -> None:
        self.assertEqual(parse_biomes("nether wastes"), ["nether_wastes"])
        self.assertEqual(parse_biomes("the end"), ["the_end"])

    def test_dimensions_cover_all_supported_families(self) -> None:
        self.assertEqual(get_biome("warm_ocean").dimension, "overworld")
        self.assertEqual(get_biome("crimson_forest").dimension, "nether")
        self.assertEqual(get_biome("end_barrens").dimension, "end")
