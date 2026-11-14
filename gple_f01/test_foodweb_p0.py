import unittest
from foodweb_p0 import FoodWeb,State,experiment
class FoodWebTests(unittest.TestCase):
    def test_conservation(self):
        world=FoodWeb()
        for _ in range(250):world.tick(consumers=4)
        self.assertAlmostEqual(world.total(),world.initial_total,places=7)
        self.assertTrue(all(v>=0 for v in world.summary()["stocks"].values()))
    def test_no_free_growth(self):
        s=State(nutrients=0,producer_a=0,producer_b=0,fruit_a=0,
                fruit_b=0,biofilm=0,microfauna=0,detritus=0,f01_reserve=0)
        w=FoodWeb(state=s)
        for _ in range(20):w.tick(consumers=10)
        self.assertEqual(w.total(),0)
        self.assertEqual(len(w.events),0)
    def test_fruit_is_real_transfer(self):
        w=FoodWeb()
        before=w.total()
        w.tick(consumers=0)
        self.assertGreater(w.state.fruit_a+w.state.fruit_b,0)
        self.assertAlmostEqual(w.total(),before)
    def test_no_water_stops_growth(self):
        w=FoodWeb()
        w.tick(water=0,consumers=0)
        self.assertFalse(any(e["event"].startswith("growth") for e in w.events))
    def test_seeds_change_productivity(self):
        a=FoodWeb(seed=11);b=FoodWeb(seed=23)
        self.assertNotEqual(a.growth_bias,b.growth_bias)
        a.tick(consumers=0);b.tick(consumers=0)
        self.assertNotEqual(a.state.producer_a,b.state.producer_a)

    def test_replay(self):
        a=FoodWeb(seed=7);b=FoodWeb(seed=7)
        for _ in range(60):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_snapshot_continuation(self):
        a=FoodWeb(seed=37)
        for _ in range(50):a.tick()
        b=FoodWeb.restore(a.snapshot())
        for _ in range(50):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_invalid_amount(self):
        with self.assertRaises(ValueError):FoodWeb().move("nutrients","biofilm",-1,"bad")
    def test_scenarios(self):
        r=experiment(seeds=(1,),ticks=30)
        self.assertEqual(r["runs"],4)
        for item in r["results"]:
            self.assertAlmostEqual(item["result"]["material_total"],90.0,places=5)
if __name__=="__main__":unittest.main()
