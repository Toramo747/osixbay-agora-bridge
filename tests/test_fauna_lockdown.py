"""Test senza rete della modalita' FAUNA-02."""
import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bots"))
import fauna_lockdown


def ts(date):
    return int(datetime.datetime.fromisoformat(date.replace("Z", "+00:00")).timestamp())


ROOT = "2035e772-c619-4c84-bbdf-ecf48df0fb16"
BASE = ts("2026-11-09T12:29:31Z")


def post(id, author, reply_to, time, room="genesis", text="fauna"):
    return {"id": id, "author": author, "reply_to": reply_to,
            "created_at": time, "room": room, "text": text}


class FaunaOnlyTest(unittest.TestCase):
    def setUp(self):
        self.bot = {"name": "lume"}
        self.cfg = {"fauna_only": True, "fauna_room": "genesis",
                    "fauna_thread_id": ROOT, "fauna_max_steps": 10,
                    "fauna_since_utc": "2026-11-09T12:29:31Z",
                    "private_rooms": ["genesis"],
                    "private_rooms_status": {"genesis": "ok"},
                    "bots": [{"name": "lume"}, {"name": "trama"}]}
        self.root = post(ROOT, "Andrea", None, BASE - 100, text="FAUNA-01")

    def test_no_access_no_fallback(self):
        cfg = dict(self.cfg, private_rooms_status={"genesis": "HTTP 500"})
        plan, err = fauna_lockdown.make_plan(self.bot, cfg, [self.root], BASE)
        self.assertIsNone(plan)
        self.assertIn("fail closed", err)

    def test_missing_thread_no_fallback(self):
        plan, err = fauna_lockdown.make_plan(self.bot, self.cfg, [], BASE)
        self.assertIsNone(plan)
        self.assertIn("fail closed", err)

    def test_first_step_private_only(self):
        posts = [self.root, post("public", "trama", None, BASE + 1, "libera")]
        plan, err = fauna_lockdown.make_plan(self.bot, self.cfg, posts, BASE + 100)
        self.assertIsNone(err)
        self.assertEqual(plan["room"], "genesis")
        self.assertEqual(plan["reply_to"], ROOT)
        self.assertEqual(plan["giro"], "fauna-only")
        self.assertIn("genesis", plan["stanze_private"])
        self.assertIn("1/10", plan["messages"][1]["content"])
        self.assertNotIn("public", plan["messages"][1]["content"])

    def test_other_threads_not_counted(self):
        posts = [self.root, post("other", "lume", None, BASE + 5)]
        plan, err = fauna_lockdown.make_plan(self.bot, self.cfg, posts, BASE + 100)
        self.assertIsNone(err)
        self.assertIn("1/10", plan["messages"][1]["content"])

    def test_collective_limit(self):
        posts = [self.root]
        previous = ROOT
        for n in range(10):
            cur = str(n)
            posts.append(post(cur, "lume" if n % 2 else "trama",
                              previous, BASE + n + 1))
            previous = cur
        plan, err = fauna_lockdown.make_plan(self.bot, self.cfg, posts, BASE + 100)
        self.assertIsNone(plan)
        self.assertIn("10 passaggi", err)

    def test_step_10_and_thread_reply(self):
        posts = [self.root]
        previous = ROOT
        for n in range(9):
            cur = str(n)
            posts.append(post(cur, "lume", previous, BASE + n + 1))
            previous = cur
        plan, err = fauna_lockdown.make_plan(self.bot, self.cfg, posts, BASE + 100)
        self.assertIsNone(err)
        self.assertEqual(plan["reply_to"], previous)
        self.assertIn("10/10", plan["messages"][1]["content"])
        self.assertIn("Consegna", plan["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()
