import copy
import unittest
from asset_contract_p0 import manifest,validate_manifest,validate_event
class AssetContractTests(unittest.TestCase):
    def test_candidate_manifest_is_explicitly_missing(self):
        m=manifest()
        self.assertTrue(validate_manifest(m))
        self.assertFalse(m["actual_godot_build_verified"])
        self.assertTrue(all(s["glb_path"] is None and s["source_blend_path"] is None for s in m["species"]))
    def test_no_accidental_approval(self):
        m=manifest();m["species"][0]["approval"]="approved"
        with self.assertRaises(ValueError):validate_manifest(m)
    def test_missing_lod_fails(self):
        m=manifest();m["species"][0]["lod_assets"]={}
        with self.assertRaises(ValueError):validate_manifest(m)
    def test_consumption_event(self):
        e={"event":"fruit_consumed","entity_id":"p01","species_id":"PROD-A",
           "tick":3,"cell_id":"zone:12:4","world_version":"v1","quantity_before":2,"quantity_after":1.4}
        self.assertEqual(validate_event(e,"v1")["visual_delta"],-0.6)
    def test_reject_stale_version(self):
        e={"event":"fruit_consumed","entity_id":"p01","species_id":"PROD-A",
           "tick":3,"cell_id":"zone:12:4","world_version":"v0","quantity_before":2,"quantity_after":1}
        with self.assertRaises(ValueError):validate_event(e,"v1")
    def test_no_free_food_event(self):
        e={"event":"fruit_consumed","entity_id":"p01","species_id":"PROD-A",
           "tick":3,"cell_id":"zone:12:4","world_version":"v1","quantity_before":0,"quantity_after":1}
        with self.assertRaises(ValueError):validate_event(e,"v1")
if __name__=="__main__":unittest.main()
