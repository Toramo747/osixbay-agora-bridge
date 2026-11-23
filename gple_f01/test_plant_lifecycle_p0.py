import json
import unittest
from plant_lifecycle_p0 import PlantLifecycle,experiment,PRODUCERS,NODES,MAX_INDIVIDUALS_PER_PATCH
class PlantLifeTests(unittest.TestCase):
    def test_birth_does_not_create_biomass(self):
        p=PlantLifecycle()
        before=p.hydro.network.biomass()
        p.tick()
        self.assertGreater(p.counts["births"],0)
        self.assertAlmostEqual(before,p.hydro.network.biomass(),places=6)
    def test_individual_pools_reconciled(self):
        p=PlantLifecycle(seed=5)
        for _ in range(160):p.tick()
        p.audit()
        for patch in NODES:
            for species in PRODUCERS:
                self.assertAlmostEqual(sum(q.biomass for q in p.individuals if q.patch==patch and q.species==species),p.pool(patch,species))
    def test_no_spontaneous_repopulation(self):
        p=PlantLifecycle()
        target=[q for q in p.individuals if q.patch=="forest" and q.species=="producer_a"]
        for q in target:q.age=119
        p.tick()
        self.assertEqual(sum(q.patch=="forest" and q.species=="producer_a" for q in p.individuals),0)
        for _ in range(10):p.tick()
        self.assertEqual(sum(q.patch=="forest" and q.species=="producer_a" for q in p.individuals),0)
    def test_death_creates_detritus(self):
        p=PlantLifecycle()
        p.individuals[0].age=119
        target=p.individuals[0]
        original=p.hydro.network.nodes[target.patch].state.detritus
        p.tick()
        self.assertGreater(p.counts["deaths"],0)
        self.assertFalse(any(q.identity==target.identity for q in p.individuals))
        self.assertGreater(p.hydro.network.nodes[target.patch].state.detritus,original)
    def test_long_horizon(self):
        p=PlantLifecycle(seed=17)
        for _ in range(500):p.tick()
        self.assertAlmostEqual(p.hydro.network.biomass(),270.0,places=5)
        self.assertAlmostEqual(p.hydro.total_water(),60.0,places=6)
        self.assertLessEqual(len(p.individuals),len(NODES)*len(PRODUCERS)*MAX_INDIVIDUALS_PER_PATCH)
    def test_replay(self):
        a=PlantLifecycle(seed=23);b=PlantLifecycle(seed=23)
        for _ in range(50):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_resume(self):
        a=PlantLifecycle(seed=33)
        for _ in range(37):a.tick()
        b=PlantLifecycle.restore(a.snapshot())
        for _ in range(43):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_bad_snapshot_rejected(self):
        a=PlantLifecycle();d=json.loads(a.snapshot());d["individuals"][0]["biomass"]=-1
        with self.assertRaises(ValueError):PlantLifecycle.restore(json.dumps(d))
    def test_multi_scenario(self):
        x=experiment(seeds=(11,),ticks=40)
        self.assertEqual(len(x["cases"]),3)
        self.assertTrue(all(r["final"]["tick"]==40 for r in x["cases"]))
    def test_drought_no_material_magic(self):
        a=PlantLifecycle(dry_start=True)
        for _ in range(50):a.tick()
        self.assertAlmostEqual(a.hydro.total_water(),0,places=7)
        self.assertAlmostEqual(a.hydro.network.biomass(),270,places=5)
if __name__=="__main__":unittest.main()
