"""ECO-LONG-11: parent cost, subsequent survival, no synthetic mint regression."""
import unittest
from long11_parent_cost_audit import analyze_case
class ParentCostTests(unittest.TestCase):
    def test_closed_ledger_and_replay(self):
        a,annual,events=analyze_case(11,.24,ticks=96)
        b,annual2,events2=analyze_case(11,.24,ticks=96)
        self.assertEqual(a,b)
        self.assertEqual(annual,annual2)
        self.assertEqual(events,events2)
        self.assertTrue(a["conserved_mass"])
        self.assertTrue(a["conserved_water"])
        self.assertTrue(a["no_resurrection"])
        self.assertEqual(a["founder_plants"],6)
        self.assertEqual(a["initial_paid_propagules"],6)
        self.assertEqual(len(annual),96//12*6)
    def test_parent_mass_split_and_repeat(self):
        a,annual,events=analyze_case(23,.40,ticks=96)
        self.assertEqual(a["births"],len(events))
        self.assertEqual(a["births"],sum(group["births"] for group in a["habitat_groups"]))
        for event in events:
            self.assertGreater(event["paid_child_mass"],0)
            self.assertGreater(event["parent_mass_after_birth"],0)
            self.assertGreater(event["parent_mass_before_birth"],event["parent_mass_after_birth"])
            self.assertIn(event["patch"],("forest","shore","rock"))
            self.assertIn(event["species"],("producer_a","producer_b"))
            if event["parent_next_birth_tick"] is not None:
                self.assertGreater(event["parent_next_birth_tick"],event["tick"])
            if event["parent_death_tick"] is not None:
                self.assertGreater(event["parent_death_tick"],event["tick"])
        self.assertLessEqual(a["parents_with_repeat_births"],a["distinct_parents"])
    def test_noncanonical_fractions_rejected(self):
        with self.assertRaises(ValueError):
            analyze_case(11,.5,ticks=12)
    def test_fraction_observation_window_censored(self):
        a,_,events=analyze_case(37,.48,ticks=48)
        self.assertLessEqual(a["observed_births_24"],a["births"])
        for event in events:
            if event["tick"]+24>48:
                self.assertIsNone(event["survived_24_ticks"])
    def test_small_and_large_fraction_are_comparable(self):
        a,_,_=analyze_case(11,.12,ticks=60)
        b,_,_=analyze_case(11,.48,ticks=60)
        self.assertEqual(a["ticks"],b["ticks"])
        self.assertEqual(a["initial_paid_propagules"],b["initial_paid_propagules"])
if __name__=="__main__":unittest.main()
