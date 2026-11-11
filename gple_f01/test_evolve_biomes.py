import unittest
from pathlib import Path
from evolve_biomes import evolve
ORIGINAL=Path("genesis/fauna01/sim.py")
class EvolutionTests(unittest.TestCase):
    def test_replay(self):
        a=evolve(ORIGINAL,seed=7,generations=2,population=4,ticks=20,trial_seeds=(1,2))
        b=evolve(ORIGINAL,seed=7,generations=2,population=4,ticks=20,trial_seeds=(1,2))
        self.assertEqual(a["replay_digest_sha256"],b["replay_digest_sha256"])
    def test_generated(self):
        out=evolve(ORIGINAL,seed=7,generations=3,population=4,ticks=20,trial_seeds=(1,))
        self.assertEqual(len(out["generations"]),3)
        self.assertTrue(any(x["candidate"]["id"].startswith("evo_") for x in out["generations"][1]["candidates"]))
    def test_bounds(self):
        with self.assertRaises(ValueError):evolve(ORIGINAL,generations=999)
        with self.assertRaises(ValueError):evolve(ORIGINAL,population=1)
    def test_no_real_world_claim(self):
        out=evolve(ORIGINAL,generations=1,population=2,ticks=10,trial_seeds=(3,))
        self.assertEqual(out["status"],"synthetic_selection_not_real_biome_discovery")
if __name__=="__main__":unittest.main()
