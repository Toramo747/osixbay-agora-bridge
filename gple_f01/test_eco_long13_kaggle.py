"""ECO-LONG-13: audit reproducibility and offline Kaggle guardrails."""
import tempfile
import unittest
from pathlib import Path
from eco_long13_kaggle_batch import evaluate,main,FRACTIONS,GROUPS

class KaggleBatchTests(unittest.TestCase):
    def test_small_run_and_replay(self):
        a,annual,events=evaluate(11,.24,24)
        b,annual_b,events_b=evaluate(11,.24,24)
        self.assertEqual(a,b)
        self.assertEqual(annual,annual_b)
        self.assertEqual(events,events_b)
        self.assertEqual(len(annual),12)
        self.assertTrue(a["mass_conserved"])
        self.assertTrue(a["water_conserved"])
        self.assertTrue(a["no_respawn"])
        self.assertEqual(a["initial_founders"],6)
        self.assertEqual(a["initial_paid_seeds"],6)
    def test_boundaries(self):
        for args in ((-1,.24,12),(11,.99,12),(11,.24,0),(11,.24,2401)):
            with self.assertRaises(ValueError):evaluate(*args)
    def test_output_and_same_fixed_fractions(self):
        with tempfile.TemporaryDirectory() as td:
            r=main(["--seeds","11","--ticks","12","--outdir",td])
            self.assertEqual(len(r["cases"]),6)
            self.assertEqual(r["annual_rows"],36)
            self.assertEqual(set(r["fractions"]),set(FRACTIONS))
            self.assertTrue((Path(td)/"cohorts.csv").is_file())
            self.assertTrue((Path(td)/"events.csv").is_file())
            self.assertTrue((Path(td)/"summary.json").is_file())
    def test_reject_duplicate_and_oversized_seed_batch(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):main(["--seeds","11,11","--ticks","12","--outdir",td])
            with self.assertRaises(ValueError):main(["--seeds",",".join(map(str,range(51))),"--ticks","12","--outdir",td])
if __name__=="__main__":unittest.main()
