import json,unittest
from propagules_p0 import PropaguleWorld,experiment,GERMINATION_AGE
class PropaguleTests(unittest.TestCase):
    def test_birth_escrows_mass(self):
        w=PropaguleWorld()
        w.tick()
        self.assertGreater(w.created,0)
        self.assertAlmostEqual(w.total_biomass(),270,places=6)
    def test_germination_and_lineage(self):
        w=PropaguleWorld()
        for _ in range(30):w.tick()
        self.assertGreater(w.germinated,0)
        self.assertTrue(all(p.identity in w.genetic.genes for p in w.genetic.life.individuals))
    def test_drought_suppresses_germination(self):
        w=PropaguleWorld()
        w.tick()
        self.assertGreater(w.created,0)
        # A synthetic seed with a very high local moisture threshold must remain dormant.
        from unittest.mock import patch
        with patch("propagules_p0.MIN_MOISTURE",100.0):
            for _ in range(GERMINATION_AGE+1):w.tick(rain_rate=0)
        self.assertGreater(len(w.seeds),0)
        self.assertEqual(w.germinated,0)
    def test_isolated_no_cross_patch(self):
        w=PropaguleWorld(connections=())
        for _ in range(15):w.tick()
        self.assertEqual(w.dispersed,0)
    def test_connected_dispersal(self):
        w=PropaguleWorld(seed=9)
        for _ in range(50):w.tick()
        self.assertGreater(w.dispersed,0)
    def test_conservation_long(self):
        w=PropaguleWorld(seed=17)
        for _ in range(400):w.tick()
        self.assertAlmostEqual(w.total_biomass(),270,places=5)
        self.assertAlmostEqual(w.genetic.life.hydro.total_water(),60,places=6)
    def test_determinism(self):
        a=PropaguleWorld(seed=3);b=PropaguleWorld(seed=3)
        for _ in range(50):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_restore(self):
        a=PropaguleWorld(seed=4)
        for _ in range(30):a.tick()
        b=PropaguleWorld.restore(a.snapshot())
        for _ in range(35):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_tampered_escrow(self):
        a=PropaguleWorld();a.tick()
        d=json.loads(a.snapshot());d["seeds"][0]["biomass"]+=10
        with self.assertRaises(ValueError):PropaguleWorld.restore(json.dumps(d))
    def test_scenarios(self):
        r=experiment(seeds=(5,),ticks=40)
        self.assertEqual(len(r["cases"]),3)
        self.assertTrue(all(x["final"]["total_biomass"]==270 for x in r["cases"]))
if __name__=="__main__":unittest.main()
