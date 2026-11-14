import json
import unittest
from hydrology_p0 import Hydrology,experiment
class HydrologyTests(unittest.TestCase):
    def test_conservation_long_horizon(self):
        h=Hydrology(seed=7)
        for _ in range(750):h.tick()
        self.assertAlmostEqual(h.total_water(),h.initial_water,places=7)
        self.assertEqual(h.events["ledger_ticks"],750)
    def test_no_negative_reservoirs(self):
        h=Hydrology()
        for _ in range(300):h.tick()
        self.assertTrue(all(v>=0 for v in h.network.water.values()))
        self.assertTrue(all(v>=0 for v in h.groundwater.values()))
        self.assertGreaterEqual(h.atmosphere,0)
    def test_rain_recirculates_from_atmosphere(self):
        h=Hydrology();h.tick(rain_rate=0)
        self.assertGreater(h.atmosphere,0)
        before=h.atmosphere;h.tick(rain_rate=1,evaporation_rate=0,infiltration_rate=0,discharge_rate=0)
        self.assertEqual(h.atmosphere,0)
        self.assertLessEqual(before,h.events["rainfall"])
    def test_no_hydrology_rates_stable_water_ledger(self):
        h=Hydrology()
        for _ in range(60):h.tick(rain_rate=0,evaporation_rate=0,infiltration_rate=0,discharge_rate=0)
        self.assertEqual(h.atmosphere,0)
        self.assertEqual(sum(h.groundwater.values()),0)
        self.assertAlmostEqual(sum(h.network.water.values()),60)
    def test_drought_reduces_surface_water(self):
        h=Hydrology()
        for _ in range(120):h.tick(rain_rate=0,evaporation_rate=.08)
        self.assertLess(sum(h.network.water.values()),15)
    def test_replay_same_seed(self):
        a=Hydrology(seed=23);b=Hydrology(seed=23)
        for _ in range(75):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_snapshot_resume(self):
        a=Hydrology(seed=19)
        for _ in range(31):a.tick()
        b=Hydrology.restore(a.snapshot())
        for _ in range(80):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_reject_bad_snapshot(self):
        h=Hydrology();d=json.loads(h.snapshot());d["atmosphere"]=-1
        with self.assertRaises(ValueError):Hydrology.restore(json.dumps(d))
    def test_invalid_rate(self):
        for rate in (-0.1,1.1,float("nan")):
            with self.assertRaises(ValueError):Hydrology().tick(rain_rate=rate)
    def test_multi_scenario(self):
        r=experiment(seeds=(7,),ticks=30)
        self.assertEqual(len(r["cases"]),3)
        for case in r["cases"]:
            self.assertEqual(case["summary"]["ledger_ticks"],30)
            self.assertAlmostEqual(case["summary"]["total_water"],60)
if __name__=="__main__":unittest.main()
