"""DM-091: v1 intermodule contract rejects invented state."""
import copy
import unittest
from contract import validate, fixture_snapshot, fixture_event

class ContractTests(unittest.TestCase):
    def test_valid_fixtures(self):
        self.assertTrue(validate(fixture_snapshot()))
        self.assertTrue(validate(fixture_event()))

    def test_no_unverified_coordinates(self):
        s=fixture_snapshot();s["entities"][0]["position_m"]=[0,2,0]
        with self.assertRaises(ValueError):validate(s)
        s=fixture_snapshot();s["transform"]={"source_scene":"S03","scene_hash":"123",
              "horizontal":"XZ","up":"Y","unit":"m","origin_m":[0,0,0],"cell_size_m":1}
        with self.assertRaises(ValueError):validate(s)

    def test_verified_export_transform(self):
        s=fixture_snapshot();s["provenance"]="verified_godot_export"
        s["transform"]={"source_scene":"S03","scene_hash":"sha256-placeholder-fixture",
              "horizontal":"XZ","up":"Y","unit":"m","origin_m":[0.0,0.0,0.0],"cell_size_m":1.0}
        s["entities"][0]["position_m"]=[1.0,2.0,3.0]
        self.assertTrue(validate(s))  # structural check, not proof hash is genuine

    def test_reject_negative_or_nan_stock(self):
        for q in (-1.0, float("nan"), float("inf"), True):
            s=fixture_snapshot();s["stocks"][0]["quantity"]=q
            with self.assertRaises(ValueError):validate(s)

    def test_duplicate_ids_and_stock(self):
        s=fixture_snapshot();s["entities"].append(copy.deepcopy(s["entities"][0]))
        with self.assertRaises(ValueError):validate(s)
        s=fixture_snapshot();s["stocks"].append(copy.deepcopy(s["stocks"][0]))
        with self.assertRaises(ValueError):validate(s)

    def test_wrong_schema_and_unknown_event(self):
        s=fixture_snapshot();s["schema"]="v2"
        with self.assertRaises(ValueError):validate(s)
        e=fixture_event();e["event_type"]="teleport"
        with self.assertRaises(ValueError):validate(e)

    def test_no_client_authoritative_event(self):
        e=fixture_event();e["provenance"]="client_claim"
        with self.assertRaises(ValueError):validate(e)

    def test_event_transfer_invariants(self):
        for quantity in (0,-0.5,float("nan")):
            e=fixture_event();e["payload"]["quantity"]=quantity
            with self.assertRaises(ValueError):validate(e)
        e=fixture_event();e["payload"]["source"]=e["payload"]["target"]
        with self.assertRaises(ValueError):validate(e)

    def test_communication_is_not_shared_truth(self):
        e=fixture_event();e["event_type"]="communicate"
        e["payload"]={"channel":"text","utterance_id":"msg-1","perceived_by":"f01-shore"}
        self.assertTrue(validate(e))
        e["payload"]["omniscient_translation"]="hidden"
        with self.assertRaises(ValueError):validate(e)

    def test_future_extensions_must_be_versioned(self):
        s=fixture_snapshot();s["canonical_biome"]="unknown"
        with self.assertRaises(ValueError):validate(s)

if __name__=="__main__":
    unittest.main()
