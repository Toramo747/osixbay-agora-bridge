import json,unittest
from plant_genetics_p0 import GeneticPlants,GENES,BOUNDS,experiment
class GeneticPlantTests(unittest.TestCase):
    def test_conservation(self):
        m=GeneticPlants(seed=8)
        for _ in range(450):m.tick()
        self.assertAlmostEqual(m.life.hydro.network.biomass(),270,places=5)
        self.assertAlmostEqual(m.life.hydro.total_water(),60,places=6)
    def test_mutation_and_bounds(self):
        m=GeneticPlants(mutation_probability=1)
        for _ in range(40):m.tick()
        self.assertGreater(m.mutations,0)
        self.assertTrue(all(BOUNDS[0]<=x<=BOUNDS[1] for g in m.genes.values() for x in g.values()))
    def test_no_mutation_inheritance(self):
        m=GeneticPlants(mutation_probability=0)
        for _ in range(40):m.tick()
        self.assertEqual(m.mutations,0)
        self.assertTrue(all(all(x==1 for x in g.values()) for g in m.genes.values()))
    def test_parent_lineage(self):
        m=GeneticPlants()
        m.tick()
        self.assertTrue(any(e.get("parent_id") for e in m.life.events if e["event"]=="plant_birth"))
    def test_replay(self):
        a=GeneticPlants(seed=13);b=GeneticPlants(seed=13)
        for _ in range(60):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_restore(self):
        a=GeneticPlants(seed=21)
        for _ in range(38):a.tick()
        b=GeneticPlants.restore(a.snapshot())
        for _ in range(44):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_bad_gene_rejected(self):
        m=GeneticPlants();d=json.loads(m.snapshot())
        key=next(iter(d["genes"]));d["genes"][key]["heat_tolerance"]=9
        with self.assertRaises(ValueError):GeneticPlants.restore(json.dumps(d))
    def test_drought_vs_wet(self):
        r=experiment(seeds=(3,),ticks=70)
        self.assertEqual(len(r["cases"]),3)
        self.assertTrue(all(x["final"]["total_water"]==60 for x in r["cases"]))
    def test_seed_variation(self):
        a=GeneticPlants(seed=1);b=GeneticPlants(seed=2)
        for _ in range(30):a.tick();b.tick()
        self.assertNotEqual(a.snapshot(),b.snapshot())
    def test_no_spontaneous_genes(self):
        m=GeneticPlants()
        for _ in range(130):m.tick()
        self.assertEqual(set(m.genes),{p.identity for p in m.life.individuals})
if __name__=="__main__":unittest.main()
