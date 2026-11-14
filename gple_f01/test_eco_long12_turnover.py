"""ECO-LONG-12 cohort occupancy invariants and deterministic replay."""
import unittest
from long12_cohort_turnover_audit import run_case,GROUPS
class TurnoverTests(unittest.TestCase):
    def test_patch_species_grid(self):
        self.assertEqual(len(GROUPS),6)
        self.assertEqual(set(p for p,s in GROUPS),{"forest","shore","rock"})
    def test_replay_and_ledgers(self):
        a,rows=run_case(11,.24,ticks=72)
        b,rows_b=run_case(11,.24,ticks=72)
        self.assertEqual(a,b)
        self.assertEqual(rows,rows_b)
        self.assertEqual(len(rows),72//12*6)
        self.assertTrue(a["mass_conserved"])
        self.assertTrue(a["water_conserved"])
        self.assertTrue(a["no_respawn"])
        self.assertEqual(a["initial_paid_seeds"],6)
    def test_births_by_patch_reconcile(self):
        a,_=run_case(23,.48,ticks=84)
        self.assertEqual(sum(x["births"] for x in a["habitats"]),a["births"])
        for x in a["habitats"]:
            self.assertLessEqual(x["adult_plant_ticks"],a["ticks"])
            self.assertLessEqual(x["eligible_plant_ticks"],x["adult_plant_ticks"])
            self.assertLessEqual(x["occupied_plant_ticks"],a["ticks"])
            self.assertLessEqual(x["last_birth_tick"] or 0,a["ticks"])
    def test_unsupported_fraction(self):
        with self.assertRaises(ValueError):run_case(11,.99,ticks=12)
    def test_small_vs_large_fixed_initial_conditions(self):
        a,_=run_case(37,.12,ticks=60)
        b,_=run_case(37,.48,ticks=60)
        self.assertEqual(a["initial_paid_seeds"],b["initial_paid_seeds"])
        self.assertEqual(a["ticks"],b["ticks"])
if __name__=="__main__":unittest.main()
