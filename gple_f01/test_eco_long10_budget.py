"""ECO-LONG-10 regression: parent-paid birth and cohort/fraction invariants."""
import unittest
from long10_offspring_budget_audit import FRACTIONS,run_case

class OffspringBudgetTests(unittest.TestCase):
    def test_fractions_are_monotonic_and_contain_reference(self):
        self.assertEqual(FRACTIONS,(.12,.18,.24,.32,.40,.48))
    def test_replay_24pct(self):
        a,rows,births=run_case(11,.24,ticks=72)
        b,rows2,births2=run_case(11,.24,ticks=72)
        self.assertEqual(a,b)
        self.assertEqual(rows,rows2)
        self.assertEqual(births,births2)
        self.assertTrue(a["biomass_conserved"])
        self.assertTrue(a["water_conserved"])
        self.assertTrue(a["no_respawn"])
        self.assertEqual(a["original_founders"],6)
        self.assertEqual(a["initial_paid_seedbank"],6)
        self.assertEqual(len(rows),72//12*6*4)
    def test_paid_mass_ledger(self):
        a,rows,births=run_case(23,.40,ticks=72)
        self.assertEqual(a["total_births"],len(births))
        self.assertAlmostEqual(a["total_birth_mass"],sum(r["birth_mass"] for r in births),places=7)
        self.assertGreaterEqual(a["highest_generation"],1)
        for record in births:
            self.assertGreater(record["birth_mass"],0)
            self.assertIn(record["patch"],("forest","shore","rock"))
            self.assertIn(record["species"],("producer_a","producer_b"))
        for generation in a["generations"]:
            self.assertLessEqual(generation["reproduced"],generation["matured"])
            self.assertLessEqual(generation["matured"],generation["individuals_known"])
    def test_reject_unsupported_fraction(self):
        with self.assertRaises(ValueError):run_case(11,.99,ticks=12)
    def test_fraction_control_not_coupled_to_adult_threshold(self):
        a,_,_=run_case(37,.12,ticks=60)
        b,_,_=run_case(37,.48,ticks=60)
        self.assertEqual(a["original_founders"],b["original_founders"])
        self.assertEqual(a["initial_paid_seedbank"],b["initial_paid_seedbank"])
        self.assertEqual(a["ticks"],b["ticks"])
if __name__=="__main__":unittest.main()
