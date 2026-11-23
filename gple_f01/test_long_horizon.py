import unittest
from pathlib import Path
from long_horizon import endurance
class EnduranceTests(unittest.TestCase):
    def test_checkpoints_and_ledger(self):
        r=endurance(Path("genesis/fauna01/sim.py"),seeds=(5,),ticks=30,snapshot_every=10)
        self.assertEqual(r["scenarios"],6)
        self.assertEqual(len(r["results"][0]["checkpoints"]),3)
        self.assertTrue(all(x["ledger_checks"]==30 for x in r["results"]))
    def test_bounds(self):
        with self.assertRaises(ValueError):endurance(Path("genesis/fauna01/sim.py"),ticks=10001)
    def test_replay(self):
        a=endurance(Path("genesis/fauna01/sim.py"),seeds=(5,),ticks=12)
        b=endurance(Path("genesis/fauna01/sim.py"),seeds=(5,),ticks=12)
        self.assertEqual(a,b)
if __name__=="__main__":unittest.main()
