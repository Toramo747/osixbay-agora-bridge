import json,unittest
from microfauna_p0 import MicroWorld
class MicroTests(unittest.TestCase):
    def test_ledger(self):
        w=MicroWorld(seed=7)
        for _ in range(250):w.tick()
        self.assertAlmostEqual(w.world.total_biomass(),270,places=5)
        self.assertAlmostEqual(w.world.genetic.life.hydro.total_water(),60,places=6)
    def test_births(self):
        w=MicroWorld()
        for _ in range(40):w.tick()
        self.assertGreater(w.births,0)
    def test_movement_linked(self):
        w=MicroWorld(seed=9)
        for _ in range(120):w.tick()
        self.assertGreater(w.moves,0)
    def test_no_movement_isolated(self):
        w=MicroWorld(connections=())
        for _ in range(100):w.tick()
        self.assertEqual(w.moves,0)
    def test_death(self):
        w=MicroWorld()
        w.micro[0].age=109
        w.tick()
        self.assertGreater(w.deaths,0)
    def test_determinism(self):
        a=MicroWorld(seed=8);b=MicroWorld(seed=8)
        for _ in range(50):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_resume(self):
        a=MicroWorld(seed=11)
        for _ in range(31):a.tick()
        b=MicroWorld.restore(a.snapshot())
        for _ in range(30):a.tick();b.tick()
        self.assertEqual(a.snapshot(),b.snapshot())
    def test_corrupt_snapshot(self):
        w=MicroWorld();d=json.loads(w.snapshot());d["micro"][0]["mass"]=-1
        with self.assertRaises(ValueError):MicroWorld.restore(json.dumps(d))
    def test_no_movement_to_unlinked(self):
        w=MicroWorld(connections=())
        with self.assertRaises(ValueError):w._move(w.micro[0],"rock")
    def test_no_free_biomass(self):
        w=MicroWorld()
        before=w.world.total_biomass()
        for _ in range(25):w.tick()
        self.assertAlmostEqual(before,w.world.total_biomass(),places=6)
if __name__=="__main__":unittest.main()
