"""Counterfactual generation-screen regression tests."""
import unittest
import foodweb_p0 as F
import plant_lifecycle_p0 as L
from long07_generational_renewal import CASES,tuning,run_case
from f01_feeding_bridge_p0 import F01Feeding
class Long07Tests(unittest.TestCase):
    def test_defaults_restored(self):
        old=(F.PRODUCER_GROWTH_MULTIPLIER,F.FRUITING_FRACTION,
             F.PRODUCER_TURNOVER_FRACTION,L.BIRTH_BIOMASS,L.REPRO_COOLDOWN,L.MAX_AGE)
        with tuning(CASES[-1]):
            self.assertEqual(F.PRODUCER_GROWTH_MULTIPLIER,2.0)
            self.assertEqual(L.BIRTH_BIOMASS,2.0)
        self.assertEqual(old,(F.PRODUCER_GROWTH_MULTIPLIER,F.FRUITING_FRACTION,
             F.PRODUCER_TURNOVER_FRACTION,L.BIRTH_BIOMASS,L.REPRO_COOLDOWN,L.MAX_AGE))
    def test_restores_on_exception(self):
        before=F.FRUITING_FRACTION
        with self.assertRaises(RuntimeError):
            with tuning(CASES[4]):raise RuntimeError("fault injection")
        self.assertEqual(before,F.FRUITING_FRACTION)
    def test_no_generational_mass_mint(self):
        case,rows=run_case(11,CASES[0],ticks=120)
        self.assertTrue(case["all_material_conserved"])
        self.assertTrue(case["all_water_conserved"])
        self.assertTrue(case["no_respawn"])
        self.assertTrue(case["no_untracked_birth"])
        self.assertEqual(len(rows),10)
    def test_reproducible_single_scenario(self):
        x,_=run_case(11,CASES[2],ticks=72)
        y,_=run_case(11,CASES[2],ticks=72)
        self.assertEqual(x,y)
    def test_default_parameters_unchanged_for_legacy(self):
        self.assertEqual(F.PRODUCER_GROWTH_MULTIPLIER,1.0)
        self.assertEqual(F.FRUITING_FRACTION,.055)
        self.assertEqual(F.PRODUCER_TURNOVER_FRACTION,.012)
        self.assertEqual(L.BIRTH_BIOMASS,3.5)
        self.assertEqual(L.REPRO_COOLDOWN,20)
if __name__=="__main__": unittest.main()
