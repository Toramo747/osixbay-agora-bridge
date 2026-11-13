"""ECO-LONG-06 parameter isolation and accounting invariants."""
import unittest
import propagules_p0 as P
import plant_lifecycle_p0 as L
from f01_feeding_bridge_p0 import F01Feeding
from long05_detritus_seedbank_audit import seedbank_from_live_parents
from long06_generation_chain_audit import parameters, run_case, SCENARIOS, state

class GenerationsTests(unittest.TestCase):
    def test_overrides_restore_after_success(self):
        original=(P.SEED_LIFETIME,P.GERMINATION_AGE,P.MIN_MOISTURE,
                  P.DISPERSAL_PROBABILITY,L.MAX_AGE)
        with parameters(180,1,.25,.85,240):
            self.assertEqual((P.SEED_LIFETIME,P.GERMINATION_AGE,P.MIN_MOISTURE,
                              P.DISPERSAL_PROBABILITY,L.MAX_AGE),
                             (180,1,.25,.85,240))
        self.assertEqual((P.SEED_LIFETIME,P.GERMINATION_AGE,P.MIN_MOISTURE,
                          P.DISPERSAL_PROBABILITY,L.MAX_AGE),original)
    def test_overrides_restore_after_exception(self):
        original=P.SEED_LIFETIME
        with self.assertRaises(RuntimeError):
            with parameters(180,1,.25,.85,240):
                raise RuntimeError("injected")
        self.assertEqual(P.SEED_LIFETIME,original)
    def test_invalid_rate_rejected(self):
        with self.assertRaises(AssertionError):
            with parameters(10,15,.3,.45,120):pass
    def test_initial_paid_seeds_and_balances(self):
        x=F01Feeding(seed=11)
        initial=state(x)
        seedbank_from_live_parents(x)
        changed=state(x)
        self.assertAlmostEqual(initial["biomass"],changed["biomass"],places=7)
        self.assertAlmostEqual(initial["water"],changed["water"],places=7)
        self.assertEqual(changed["dormant"],6)
        x.audit()
    def test_seeded_generation_replay(self):
        from long05_detritus_seedbank_audit import advance
        x=F01Feeding(seed=23);seedbank_from_live_parents(x)
        with parameters(180,1,.25,.85,240):
            for _ in range(30):advance(x,boosted=True)
            y=F01Feeding.restore(x.snapshot())
            for _ in range(25):
                advance(x,boosted=True);advance(y,boosted=True)
            self.assertEqual(x.snapshot(),y.snapshot())
    def test_scenario_isolation_and_no_respawn(self):
        a,_=run_case(11,SCENARIOS[0])
        b,_=run_case(11,SCENARIOS[0])
        self.assertEqual(a,b)
        self.assertTrue(a["conserved"])
        self.assertTrue(a["no_respawn"])

if __name__=="__main__":unittest.main()
