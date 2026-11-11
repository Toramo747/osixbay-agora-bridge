"""Tests for experimental F01 ecological adapter using ORIGINAL PR88 classes."""
import unittest
from pathlib import Path
from biome_search import load_f01, VARIANTS
from ecological_adapter import EcoF01, compare, trial

ORIGINAL=Path("genesis/fauna01/sim.py")
class EcologicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f01=load_f01(ORIGINAL)
        cls.variant=VARIANTS[0]

    def create(self,seed=17,**kwargs):
        eco=EcoF01(self.f01,self.variant,seed=seed,**kwargs)
        eco.spawn(8)
        return eco

    def test_deterministic_replay(self):
        a=self.create();b=self.create()
        for _ in range(100):
            a.step();b.step()
        self.assertEqual(a.snapshot(),b.snapshot())

    def test_snapshot_restores_continuation(self):
        a=self.create(seed=21)
        for _ in range(25):a.step()
        b=EcoF01.from_snapshot(self.f01,a.snapshot())
        for _ in range(30):a.step();b.step()
        self.assertEqual(a.snapshot(),b.snapshot())

    def test_no_water_causes_hydration_deaths(self):
        r=trial(ORIGINAL,self.variant,seed=11,ticks=100,water_access=False)
        self.assertEqual(r["alive"],0)
        self.assertGreater(r["hydration_deaths"],0)

    def test_resources_finite_and_nonnegative(self):
        a=self.create()
        for _ in range(250):
            a.step()
            for row in a.env:
                for cell in row:
                    self.assertGreaterEqual(cell.food,0)
                    self.assertLessEqual(cell.food,cell.capacity+1e-8)

    def test_biome_parameters_differ(self):
        a=self.create()
        modes={}
        for row in a.env:
            for c in row:
                if c.playable:modes.setdefault(c.biome,c)
        self.assertGreaterEqual(len(modes),2)
        self.assertGreater(len({v.temperature for v in modes.values()}),1)
        self.assertGreater(len({v.regrowth for v in modes.values()}),1)

    def test_spawn_stays_in_playable_mask(self):
        a=self.create()
        for _ in range(110):
            a.step()
            for unit in a.world.organisms:
                self.assertTrue(a.env[unit.y][unit.x].playable)

    def test_multi_seed_report(self):
        out=compare(ORIGINAL,VARIANTS[:2],seeds=(2,3),ticks=40)
        self.assertEqual(len(out["results"]),2)
        self.assertFalse(out["source_world_mask_imported"])

    def test_corrupt_snapshot_fails(self):
        a=self.create()
        import json
        d=json.loads(a.snapshot());d["hydration"]={}
        with self.assertRaises(ValueError):EcoF01.from_snapshot(self.f01,json.dumps(d))

    def test_zero_regrowth_remains_bounded(self):
        a=self.create()
        for row in a.env:
            for c in row:c.regrowth=0.0
        for _ in range(180):a.step()
        self.assertEqual(a.events["grown"],0.0)

if __name__=="__main__":unittest.main()
