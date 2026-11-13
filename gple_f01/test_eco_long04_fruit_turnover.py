"""ECO-LONG-04 conservative fruit turnover; no replenishment or respawn."""
import unittest
from foodweb_p0 import FoodWeb, State
class FruitTurnoverTests(unittest.TestCase):
    def test_orphan_fruit_is_recycled_not_frozen(self):
        state=State(nutrients=0.0,producer_a=0.0,producer_b=0.0,
                    fruit_a=5.0,fruit_b=7.0,biofilm=0.0,microfauna=0.0,
                    detritus=0.0,f01_reserve=0.0)
        sim=FoodWeb(seed=11,state=state)
        mass=sim.total()
        initial_fruit=state.fruit_a+state.fruit_b
        sim.tick(water=0,light=0,consumers=0)
        after_fruit=state.fruit_a+state.fruit_b
        self.assertLess(after_fruit,initial_fruit)
        self.assertGreater(state.detritus,0)
        self.assertGreater(state.nutrients,0)
        self.assertAlmostEqual(sim.total(),mass,places=8)
    def test_spoilage_replay_and_conservation(self):
        a=FoodWeb(seed=37)
        for _ in range(30):a.tick(consumers=0)
        b=FoodWeb.restore(a.snapshot())
        for _ in range(50):a.tick(consumers=0);b.tick(consumers=0)
        self.assertEqual(a.snapshot(),b.snapshot())
        self.assertAlmostEqual(a.total(),90.0,places=7)
if __name__=="__main__": unittest.main()
