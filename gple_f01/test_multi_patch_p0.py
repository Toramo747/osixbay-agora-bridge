import json
import unittest
from multi_patch_p0 import PatchNetwork, experiment
class MultiPatchTests(unittest.TestCase):
    def test_conserved_and_positive(self):
        w=PatchNetwork(seed=7)
        for _ in range(550):w.tick()
        self.assertAlmostEqual(w.biomass(),w.biomass_initial,places=6)
        self.assertAlmostEqual(sum(w.water.values()),w.water_initial,places=7)
        for node in w.nodes.values():
            self.assertTrue(all(v>=0 for v in node.summary()["stocks"].values()))
    def test_linked_water_moves(self):
        a=PatchNetwork(connections=())
        b=PatchNetwork()
        a.tick();b.tick()
        self.assertEqual(a.water["forest"],18)
        self.assertNotEqual(b.water["forest"],18)
        self.assertGreater(b.flux_events,0)
    def test_isolated_nutrients_do_not_flow(self):
        a=PatchNetwork(connections=())
        b=PatchNetwork()
        for _ in range(4):a.tick();b.tick()
        self.assertNotEqual(a.nodes["forest"].state.nutrients,b.nodes["forest"].state.nutrients)
    def test_replay(self):
        a=PatchNetwork(seed=89);b=PatchNetwork(seed=89)
        for _ in range(31):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_resume(self):
        a=PatchNetwork(seed=8)
        for _ in range(37):a.tick()
        b=PatchNetwork.restore(a.snapshot())
        for _ in range(23):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_corrupt_snapshot(self):
        a=PatchNetwork();d=json.loads(a.snapshot())
        d["water"]["shore"]=-2
        with self.assertRaises(ValueError):PatchNetwork.restore(json.dumps(d))
    def test_no_duplicate_edges(self):
        with self.assertRaises(ValueError):
            PatchNetwork(connections=[("forest","shore"),("shore","forest")])
    def test_seed_variation(self):
        a=PatchNetwork(seed=11);b=PatchNetwork(seed=23)
        a.tick();b.tick()
        self.assertNotEqual(a.nodes["forest"].state.producer_a,b.nodes["forest"].state.producer_a)
    def test_comparison(self):
        e=experiment(seeds=(5,),ticks=20)
        self.assertEqual(len(e["cases"]),2)
        self.assertTrue(all(c["final"]["tick"]==20 for c in e["cases"]))
if __name__=="__main__":unittest.main()
