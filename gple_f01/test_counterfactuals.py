import unittest
from pathlib import Path
from counterfactuals import experiment, INTERVENTIONS
class CounterfactualTests(unittest.TestCase):
    def test_bounded_and_attributed(self):
        r=experiment(Path("genesis/fauna01/sim.py"),seeds=(7,),ticks=50)
        self.assertEqual(len(r["cases"]),6*len(INTERVENTIONS))
        for c in r["cases"]:
            self.assertEqual(c["deaths"],c["hydration_deaths"]+c["energy_deaths"]+c["age_deaths"])
            self.assertEqual(c["ledger_checks"],50)
            self.assertEqual(c["births"],0 if c["intervention"]=="no_births" else c["births"])
    def test_no_water(self):
        r=experiment(Path("genesis/fauna01/sim.py"),seeds=(7,),ticks=100)
        no_water=[c for c in r["cases"] if c["intervention"]=="no_water"]
        self.assertTrue(all(c["hydration_deaths"]>0 for c in no_water))
    def test_replay(self):
        kw={"seeds":(3,),"ticks":24}
        self.assertEqual(experiment(Path("genesis/fauna01/sim.py"),**kw),
                         experiment(Path("genesis/fauna01/sim.py"),**kw))
    def test_limits(self):
        with self.assertRaises(ValueError):
            experiment(Path("genesis/fauna01/sim.py"),ticks=10001)
if __name__=="__main__":unittest.main()
