"""ECO-LONG-04: regression tests for finite food, starvation, no resurrection."""
import unittest
from f01_feeding_bridge_p0 import F01Feeding
from multi_patch_p0 import NODES

class StarvationRegression(unittest.TestCase):
    def test_living_f01_has_positive_energy_throughout_long_run(self):
        sim=F01Feeding(seed=11)
        before_mass=sim.eco.world.total_biomass()
        before_water=sim.eco.world.genetic.life.hydro.total_water()
        seen_death=False
        for tick in range(1200):
            sim.tick()
            sim.audit()
            self.assertAlmostEqual(sim.eco.world.total_biomass(), before_mass, places=5)
            self.assertAlmostEqual(sim.eco.world.genetic.life.hydro.total_water(), before_water, places=5)
            for actor in sim.f01.values():
                if actor["alive"]:
                    self.assertGreater(actor["energy"], 0.0, "A living F01 cannot have zero metabolic energy")
                else:
                    seen_death=True
        self.assertTrue(seen_death, "The low-food baseline must exercise the starvation pathway")
    def test_no_spontaneous_resurrection(self):
        sim=F01Feeding(seed=37)
        dead=set()
        for _ in range(1200):
            sim.tick()
            for patch,actor in sim.f01.items():
                if patch in dead:
                    self.assertFalse(actor["alive"])
                if not actor["alive"]:
                    dead.add(patch)
        self.assertTrue(dead)
    def test_checkpoint_replay_after_starvation(self):
        a=F01Feeding(seed=23)
        for _ in range(220): a.tick()
        b=F01Feeding.restore(a.snapshot())
        for _ in range(90):
            a.tick();b.tick()
        self.assertEqual(a.snapshot(), b.snapshot())
    def test_death_returns_tissue_water(self):
        sim=F01Feeding(seed=11)
        for _ in range(1200):
            sim.tick()
        hydro=sim.eco.world.genetic.life.hydro
        for patch in NODES:
            if not sim.f01[patch]["alive"]:
                self.assertEqual(hydro.f01_tissue_water[patch],0.0)
if __name__ == "__main__": unittest.main()
