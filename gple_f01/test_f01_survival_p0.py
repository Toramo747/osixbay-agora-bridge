"""DM-088: no-water, lifecycle and conservation regression (synthetic only)."""
import json
import unittest
from f01_feeding_bridge_p0 import F01Feeding
from multi_patch_p0 import NODES

def drain_all_water(sim):
    hydro = sim.eco.world.genetic.life.hydro
    for p in NODES:
        hydro.network.water[p] = 0.0
        hydro.groundwater[p] = 0.0
        hydro.f01_tissue_water[p] = 0.0
        for kind in hydro.producer_water[p]:
            hydro.producer_water[p][kind] = 0.0
    hydro.atmosphere = 0.0
    hydro.initial_water = 0.0
    hydro.network.water_initial = 0.0
    hydro.audit()

class F01SurvivalTests(unittest.TestCase):
    def test_initial_water_conservation(self):
        sim = F01Feeding()
        hydro = sim.eco.world.genetic.life.hydro
        expected = hydro.initial_water
        for _ in range(120):
            sim.tick()
            self.assertAlmostEqual(hydro.total_water(), expected, places=6)
            self.assertAlmostEqual(sim.eco.world.total_biomass(), 270, places=5)

    def test_real_drinking_draws_surface_stock(self):
        sim = F01Feeding()
        hydro = sim.eco.world.genetic.life.hydro
        result = sim.tick(rain_rate=0, evaporation_rate=0,
                          infiltration_rate=0, discharge_rate=0)
        self.assertGreater(result["meals"]["forest"]["water"], 0.0)
        self.assertGreater(hydro.f01_tissue_water["forest"], 0.0)
        self.assertAlmostEqual(hydro.total_water(), hydro.initial_water, places=6)

    def test_no_water_causes_death_and_stops_food(self):
        sim = F01Feeding()
        drain_all_water(sim)
        last = None
        for _ in range(25):
            last = sim.tick(rain_rate=0, evaporation_rate=0,
                            infiltration_rate=0, discharge_rate=0)
        for p in NODES:
            self.assertFalse(sim.f01[p]["alive"])
            self.assertEqual(sim.f01[p]["death_reason"], "thirst")
            self.assertEqual(last["meals"][p]["consumed"], 0)
        self.assertAlmostEqual(sim.eco.world.genetic.life.hydro.total_water(), 0, places=7)

    def test_snapshot_and_replay(self):
        sim = F01Feeding(seed=23)
        for _ in range(23): sim.tick()
        restored = F01Feeding.restore(sim.snapshot())
        for _ in range(21):
            sim.tick(); restored.tick()
        self.assertEqual(sim.snapshot(), restored.snapshot())

    def test_reject_fabricated_hydration(self):
        sim = F01Feeding(); sim.tick()
        snapshot = json.loads(sim.snapshot())
        snapshot["f01"]["forest"]["hydration"] = 2.0
        with self.assertRaises(ValueError):
            F01Feeding.restore(json.dumps(snapshot))

    def test_dead_actor_cannot_feed_after_snapshot_resume(self):
        sim = F01Feeding()
        drain_all_water(sim)
        for _ in range(22):
            sim.tick(rain_rate=0, evaporation_rate=0,
                     infiltration_rate=0, discharge_rate=0)
        restored = F01Feeding.restore(sim.snapshot())
        for _ in range(4):
            result = restored.tick(rain_rate=0, evaporation_rate=0,
                                   infiltration_rate=0, discharge_rate=0)
            for patch in NODES:
                self.assertFalse(result["meals"][patch]["alive"])
                self.assertEqual(result["meals"][patch]["consumed"], 0)
        self.assertTrue(all(not a["alive"] for a in restored.f01.values()))

if __name__ == "__main__":
    unittest.main()
