"""ECO-LONG-08 isolation and accounting smoke tests."""
import unittest
import plant_lifecycle_p0 as L
from long08_cohort_mortality_audit import SCENARIOS,cohort_settings,run_case
class TestLong08(unittest.TestCase):
    def test_parameter_restoration(self):
        initial=(L.ADULT_AGE,L.BIRTH_FRACTION,L.MIN_BIOMASS)
        with cohort_settings(4,.12,.015):
            self.assertEqual((L.ADULT_AGE,L.BIRTH_FRACTION,L.MIN_BIOMASS),(4,.12,.015))
        self.assertEqual((L.ADULT_AGE,L.BIRTH_FRACTION,L.MIN_BIOMASS),initial)
    def test_exception_restoration(self):
        initial=L.BIRTH_FRACTION
        with self.assertRaises(RuntimeError):
            with cohort_settings(4,.4,.015):raise RuntimeError("fault")
        self.assertEqual(L.BIRTH_FRACTION,initial)
    def test_invalid_threshold_rejected(self):
        with self.assertRaises(ValueError):
            with cohort_settings(1,.7,.015):pass
    def test_reproducible_audit(self):
        a,rows=run_case(11,SCENARIOS[0],ticks=36)
        b,other=run_case(11,SCENARIOS[0],ticks=36)
        self.assertEqual(a,b)
        self.assertEqual(rows,other)
        self.assertEqual(len(rows),36//12*6)
        self.assertTrue(a["conserved"])
        self.assertTrue(a["no_resurrection"])
    def test_deaths_have_audited_reason(self):
        a,_=run_case(11,SCENARIOS[-1],ticks=72)
        self.assertEqual(a["age_deaths"]+a["non_age_deaths"],a["death_events"])
if __name__=="__main__":unittest.main()
