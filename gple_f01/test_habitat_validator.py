import unittest
from habitat_validator import validate

def fixture():
    return {"schema":"osixbay.genesis.gple.f01.habitat-export.v1",
            "zone_id":"synthetic-test","world_version":"test-only",
            "source_scene":"TEST_ONLY","source_commit":"TEST_ONLY",
            "grid_resolution_m":1.0,"origin_world":[0,0],
            "cells":[[{"playable":True,"suitable_for_f01":True,"traversable":True,
                       "biome":"alien_forest","substrate":"soil","water_depth_m":0,
                       "resources":{"organic_biofilm":0},"resource_capacity":{"organic_biofilm":3},
                       "resource_regrowth":{"organic_biofilm":0.1},"danger":0,"shelter":True,
                       "temperature":20,"humidity":0.5}]]}

class HabitatTest(unittest.TestCase):
    def test_valid_zero_food(self):self.assertEqual(validate(fixture())["viable_cells"],1)
    def test_invalid_mask(self):
        a=fixture();del a["cells"][0][0]["playable"]
        with self.assertRaises(ValueError):validate(a)
    def test_outside_rejected(self):
        a=fixture();a["cells"][0][0]["playable"]=False
        with self.assertRaises(ValueError):validate(a)
    def test_unknown_biome(self):
        a=fixture();a["cells"][0][0]["biome"]="ocean"
        with self.assertRaises(ValueError):validate(a)
    def test_invalid_resources(self):
        a=fixture();a["cells"][0][0]["resources"]["organic_biofilm"]=4
        with self.assertRaises(ValueError):validate(a)
    def test_no_source(self):
        a=fixture();a["source_scene"]=""
        with self.assertRaises(ValueError):validate(a)

if __name__=="__main__":unittest.main()
