"""FAUNA-02 simulator checks: run python3 -m unittest discover -s genesis/fauna01/tests -v"""
import unittest
from genesis.fauna01.sim import World, Parameters, demonstration

class TestFaunaReference(unittest.TestCase):
    def setUp(self):
        self.habitat = [[True] * 7 for _ in range(7)]

    def world(self, seed=99, params=None):
        w = World(self.habitat, seed=seed, parameters=params)
        w.add_organism(3, 3)
        w.add_organism(4, 3)
        return w

    def test_repeatability_same_seed(self):
        a, b = self.world(), self.world()
        for _ in range(90):
            self.assertEqual(a.step(), b.step())
        self.assertEqual(a.snapshot(), b.snapshot())

    def test_different_seeds_change_inherited_traits(self):
        p = Parameters(birth_threshold=9.0, cooldown=1)
        a, b = self.world(1, p), self.world(2, p)
        for _ in range(10):
            a.step()
            b.step()
        self.assertNotEqual(a.snapshot(), b.snapshot())

    def test_snapshot_replay(self):
        a = self.world()
        for _ in range(23):
            a.step()
        b = World.from_snapshot(a.snapshot())
        for _ in range(44):
            self.assertEqual(a.step(), b.step())
        self.assertEqual(a.snapshot(), b.snapshot())

    def test_reproduction_and_mutation_bounds(self):
        p = Parameters(birth_threshold=9.0, cooldown=1, max_population=12)
        w = self.world(seed=42, params=p)
        initial = len(w.organisms)
        for _ in range(25):
            w.step()
        self.assertGreater(w.next_id, initial + 1)
        self.assertTrue(all(2 <= a.threshold <= 18 and 0.5 <= a.efficiency <= 1.5
                            for a in w.organisms))

    def test_danger_causes_flee(self):
        w = World([[True, True, True]], seed=2)
        a = w.add_organism(1, 0)
        w.cells[0][1].danger = 1.0
        w.step()
        self.assertNotEqual(a.x, 1)
        self.assertEqual(a.last_action, "flee")

    def test_energy_and_resources_bounded(self):
        w = self.world()
        p = w.parameters
        for _ in range(250):
            w.step()
            for a in w.organisms:
                self.assertGreater(a.energy, 0)
                self.assertLessEqual(a.energy, p.energy_cap)
            for row in w.cells:
                for c in row:
                    self.assertGreaterEqual(c.food, 0)
                    self.assertLessEqual(c.food, p.capacity)

    def test_unsuitable_habitat_rejects_birth(self):
        w = World([[False, True]], seed=3)
        with self.assertRaises(ValueError):
            w.add_organism(0, 0)
        w.add_organism(1, 0)
        w.cells[0][1].suitable = False
        result = w.step()
        self.assertEqual(result["alive"], 0)
        self.assertEqual(result["died"], 1)
        self.assertEqual(w.cells[0][1].food, 0)

    def test_population_cap(self):
        w = self.world(params=Parameters(max_population=4, birth_threshold=9.0, cooldown=0))
        for _ in range(200):
            w.step()
            self.assertLessEqual(len(w.organisms), 4)

    def test_no_food_creates_no_energy(self):
        p = Parameters(regrowth=0, basal_cost=0.5, birth_threshold=19)
        w = World([[True]], seed=3, parameters=p)
        w.add_organism(0, 0, energy=5)
        w.cells[0][0].food = 0
        for _ in range(5):
            w.step()
        if w.organisms:
            self.assertLess(w.organisms[0].energy, 5)

    def test_nonnegative_food_after_many_consumers(self):
        w = World([[True]], parameters=Parameters(max_population=20, regrowth=0))
        for _ in range(15):
            w.add_organism(0, 0)
        for _ in range(35):
            w.step()
            self.assertGreaterEqual(w.cells[0][0].food, 0)

    def test_lifetime_death(self):
        w = World([[True]], parameters=Parameters(max_age=2, birth_threshold=19))
        w.add_organism(0, 0)
        w.step()
        self.assertEqual(w.step()["alive"], 0)

    def test_no_external_state_required(self):
        self.assertEqual(demonstration(seed=42, ticks=15), demonstration(seed=42, ticks=15))

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            Parameters(capacity=-1)
        with self.assertRaises(ValueError):
            World([[True, False], [True]])

if __name__ == "__main__":
    unittest.main()
