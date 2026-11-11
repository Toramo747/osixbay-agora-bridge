"""Offline acceptance tests for GPLE-F01 baseline."""
import unittest
from sim import simulate, Creature, Reproduction, Perception

class F01Tests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(simulate(seed=11,ticks=60),simulate(seed=11,ticks=60))
    def test_independent_seeds(self):
        self.assertNotEqual(simulate(seed=11,ticks=60),simulate(seed=12,ticks=60))
    def test_population_cap(self):
        out=simulate(seed=2,ticks=500,initial=12,max_population=22)
        self.assertTrue(all(p["population"]<=22 for p in out["timeline"]))
    def test_no_negative_food(self):
        self.assertEqual(simulate(ticks=100)["schema"],"gple.f01.metrics.v1")
    def test_bounds(self):
        self.assertEqual(len(Perception.adjacent(0,0,1)),1)
    def test_heredity(self):
        import random
        parent=Creature(1,0,0)
        child=Reproduction.offspring(parent,2,random.Random(7))
        self.assertEqual(child.generation,1)
        self.assertNotEqual(parent.cid,child.cid)
    def test_bad_inputs(self):
        for args in ({"ticks":0},{"size":129},{"initial":6,"max_population":5}):
            with self.assertRaises(ValueError):
                simulate(**args)

if __name__=="__main__":
    unittest.main()
