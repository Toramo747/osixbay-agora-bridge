import json,unittest
from scene_contract_p0 import demo,validate_scene,export_scene
from f01_feeding_bridge_p0 import F01Feeding
class ContractTests(unittest.TestCase):
    def test_export(self):
        d=json.loads(demo(ticks=3))
        self.assertEqual(d["schema"],"osixbay.genesis.demo-ecology-scene.v1")
    def test_stable(self):
        self.assertEqual(demo(seed=9,ticks=8),demo(seed=9,ticks=8))
    def test_all_types(self):
        x=F01Feeding();x.tick()
        kinds={e["type"] for e in export_scene(x)["entities"]}
        self.assertTrue({"plant","propagule","microfauna","f01"}.issubset(kinds))
    def test_no_coordinates(self):
        d=json.loads(demo(ticks=2))
        self.assertTrue(all("position" not in e for e in d["entities"]))
    def test_duplicate_rejected(self):
        d=json.loads(demo(ticks=2));d["entities"].append(dict(d["entities"][0]))
        with self.assertRaises(ValueError):validate_scene(d)
    def test_invalid_patch_rejected(self):
        d=json.loads(demo(ticks=2));d["entities"][0]["patch"]="unknown"
        with self.assertRaises(ValueError):validate_scene(d)
if __name__=="__main__":unittest.main()
