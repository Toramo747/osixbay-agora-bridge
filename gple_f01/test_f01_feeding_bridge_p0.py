import json,unittest
from f01_feeding_bridge_p0 import F01Feeding
class FeedingTests(unittest.TestCase):
    def test_ledger(self):
        x=F01Feeding()
        for _ in range(70):x.tick()
        self.assertAlmostEqual(x.eco.world.total_biomass(),270,places=5)
    def test_food_from_events(self):
        x=F01Feeding()
        result=x.tick()
        self.assertTrue(all(set(meal["food"])=={"fruit_a","fruit_b","biofilm","microfauna"} for meal in result["meals"].values()))
    def test_no_double_feeding(self):
        x=F01Feeding()
        x.tick()
        self.assertEqual(x.eco.world.genetic.life.hydro.network.ticks,1)
    def test_energy_bounds(self):
        x=F01Feeding()
        for _ in range(100):x.tick()
        self.assertTrue(all(0<=a["energy"]<=1 for a in x.f01.values()))
    def test_determinism(self):
        a=F01Feeding(seed=4);b=F01Feeding(seed=4)
        for _ in range(25):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_resume(self):
        a=F01Feeding()
        for _ in range(20):a.tick()
        b=F01Feeding.restore(a.snapshot())
        for _ in range(20):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_tamper(self):
        x=F01Feeding();d=json.loads(x.snapshot());d["f01"]["forest"]["energy"]=3
        with self.assertRaises(ValueError):F01Feeding.restore(json.dumps(d))
    def test_no_spontaneous_mass(self):
        x=F01Feeding();before=x.eco.world.total_biomass()
        for _ in range(20):x.tick()
        self.assertAlmostEqual(x.eco.world.total_biomass(),before,places=6)
if __name__=="__main__":unittest.main()
