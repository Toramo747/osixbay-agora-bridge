"""Tests exercise the original F01 model via the candidate-screening adapter."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from biome_search import experiment, synthetic_map, rank_candidate, VARIANTS
ORIGINAL=Path(__file__).resolve().parents[1]/"genesis/fauna01/sim.py"

class CandidateTests(unittest.TestCase):
    def test_determinism(self):
        a=experiment(ORIGINAL,seeds=(1,2),ticks=30)
        b=experiment(ORIGINAL,seeds=(1,2),ticks=30)
        self.assertEqual(a["replay_digest_sha256"],b["replay_digest_sha256"])
    def test_multiple_candidates(self):
        r=experiment(ORIGINAL,seeds=(3,),ticks=30)
        self.assertEqual(len(r["proposals"]),len(VARIANTS))
        self.assertFalse(r["source_world_mask_imported"])
    def test_mask_irregular(self):
        m,_=synthetic_map(9,VARIANTS[0])
        self.assertTrue(any(not v for row in m for v in row))
        self.assertTrue(any(v for row in m for v in row))
    def test_bounds(self):
        r=experiment(ORIGINAL,seeds=(11,),ticks=50)
        for item in r["proposals"]:
            for t in item["trials"]:
                self.assertGreaterEqual(t["survivors"],0)
                self.assertLessEqual(t["survivors"],t["population_cap"])
                self.assertGreaterEqual(t["final_food"],0)
    def test_invalid_budget(self):
        with self.assertRaises(ValueError):experiment(ORIGINAL,seeds=(),ticks=2)
        with self.assertRaises(ValueError):experiment(ORIGINAL,seeds=(1,),ticks=10001)
    def test_report_not_world_data(self):
        r=experiment(ORIGINAL,seeds=(1,),ticks=5)
        self.assertIn("synthetic",r["status"])
        self.assertTrue(r["caveats"])

if __name__=="__main__":unittest.main()
