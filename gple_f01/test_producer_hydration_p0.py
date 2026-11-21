import json
import unittest
from producer_hydration_p0 import ProducerHydrology,experiment

class ProducerWaterTests(unittest.TestCase):
    def test_500_tick_mass_balance(self):
        h=ProducerHydrology(seed=7)
        for _ in range(500):h.tick()
        self.assertAlmostEqual(h.total_water(),60.0,places=7)
        self.assertGreater(h.uptake_total,0)
        self.assertGreater(h.transpiration_total,0)
    def test_dry_start_blocks_growth(self):
        h=ProducerHydrology(dry_start=True)
        before={n:(h.network.nodes[n].state.producer_a,
                   h.network.nodes[n].state.producer_b) for n in h.network.nodes}
        h.tick()
        for n,(a,b) in before.items():
            self.assertLessEqual(h.network.nodes[n].state.producer_a,a)
            self.assertLessEqual(h.network.nodes[n].state.producer_b,b)
        self.assertEqual(h.uptake_total,0)
    def test_water_is_not_created(self):
        h=ProducerHydrology()
        for _ in range(60):h.tick(rain_rate=0,evaporation_rate=0)
        self.assertAlmostEqual(h.total_water(),60,places=8)
    def test_snapshots(self):
        a=ProducerHydrology(seed=19)
        for _ in range(43):a.tick()
        b=ProducerHydrology.restore(a.snapshot())
        for _ in range(40):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_deterministic(self):
        a=ProducerHydrology(seed=13);b=ProducerHydrology(seed=13)
        for _ in range(60):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_corruption_rejected(self):
        h=ProducerHydrology()
        d=json.loads(h.snapshot());d["producer_water"]["forest"]["producer_a"]=-1
        with self.assertRaises(ValueError):ProducerHydrology.restore(json.dumps(d))
    def test_invalid_rates(self):
        with self.assertRaises(ValueError):ProducerHydrology().tick(rain_rate=-1)
    def test_drought_vs_wet(self):
        e=experiment(seeds=(7,),ticks=100)
        self.assertEqual(len(e["cases"]),3)
        for x in e["cases"]:self.assertAlmostEqual(x["final"]["total_water"],60)
    def test_nonnegative_stores(self):
        h=ProducerHydrology(seed=4)
        for _ in range(150):h.tick()
        self.assertTrue(all(x>=0 for row in h.producer_water.values() for x in row.values()))
        self.assertTrue(all(x>=0 for x in h.network.water.values()))
    def test_existing_hydro_model_unchanged(self):
        from hydrology_p0 import Hydrology
        h=Hydrology(seed=7)
        for _ in range(60):h.tick()
        self.assertAlmostEqual(h.total_water(),60)
if __name__=="__main__":unittest.main()
