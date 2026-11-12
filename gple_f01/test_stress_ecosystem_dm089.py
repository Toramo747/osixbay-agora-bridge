"""DM-089 deterministic ECO-P0 stress regression tests (synthetic lab)."""
import copy
import json
import unittest
from stress_ecosystem_dm089 import experiment,run_case,SCHEMA

class StressTests(unittest.TestCase):
    def test_small_matrix_and_ledgers(self):
        r=experiment(seeds=(11,23),ticks=36,scenarios=("baseline","drought_recovery","no_water_extinction"))
        self.assertEqual(r["schema"],SCHEMA)
        self.assertEqual(r["aggregate"]["runs"],6)
        self.assertTrue(r["aggregate"]["all_replay_exact"])
        self.assertTrue(r["aggregate"]["all_conserved"])
        self.assertEqual(len(r["cases"]),6)
    def test_waterless_f01_extinction_without_ghost_feeding(self):
        r=run_case(seed=37,ticks=45,scenario="no_water_extinction")
        self.assertEqual(r["starting"]["water"],0)
        self.assertEqual(r["ending"]["f01_alive"],0)
        self.assertEqual(r["ending"]["f01_deaths"]["thirst"],3)
        self.assertTrue(r["biomass_conserved"] and r["water_conserved"])
        self.assertEqual(r["ending"]["water"],0)
    def test_repeated_seed_deterministic_biology(self):
        a=run_case(seed=19,ticks=48,scenario="drought_recovery")
        b=run_case(seed=19,ticks=48,scenario="drought_recovery")
        self.assertEqual(a["ending"],b["ending"])
        self.assertEqual(a["checkpoints"],b["checkpoints"])
        # Runner timing measurements are allowed to differ.
    def test_no_spontaneous_reappearance_after_extinction(self):
        r=run_case(seed=11,ticks=60,scenario="no_water_extinction")
        self.assertEqual(r["checkpoints"]["40"]["f01_alive"],0)
        self.assertEqual(r["checkpoints"]["60"]["f01_alive"],0)
    def test_phase_order(self):
        r=run_case(seed=23,ticks=60,scenario="drought_recovery")
        self.assertEqual(set(r["checkpoints"]),{"0","1","20","40","60"})
        self.assertEqual(r["ending"]["tick"],60)
    def test_no_false_calibration_claim(self):
        x=experiment(seeds=(11,),ticks=24,scenarios=("baseline",))
        self.assertIn("not the original F01", " ".join(x["limitations"]))
        self.assertNotIn("godot_fps",json.dumps(x).lower())
    def test_reject_unbounded_inputs(self):
        for kwargs in (
            {"seed":True,"ticks":24},
            {"seed":11,"ticks":6},
            {"seed":11,"ticks":1201},
            {"seed":11,"ticks":24,"scenario":"unknown"},
        ):
            with self.assertRaises(ValueError):run_case(**kwargs)
        with self.assertRaises(ValueError):
            experiment(seeds=(11,11),ticks=24)
        with self.assertRaises(ValueError):
            experiment(seeds=(11,),ticks=24,scenarios=("baseline","baseline"))
    def test_timing_not_biology(self):
        r=run_case(seed=11,ticks=24)
        self.assertGreaterEqual(r["tick_ms_mean"],0)
        self.assertGreaterEqual(r["tick_ms_p95"],0)
        self.assertTrue(r["replay_exact"])
if __name__=="__main__":unittest.main()
