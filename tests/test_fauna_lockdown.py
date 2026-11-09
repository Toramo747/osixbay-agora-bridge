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


    def test_run_bot_fauna_only_never_calls_public_routes(self):
        import base64
        import agora_bots as ab
        bot = dict(self.bot, model={"label": "test"}, persona="test")
        seen = []
        result = ab.run_bot(
            bot, self.cfg, "https://example.invalid",
            base64.b64encode(b"x" * 32).decode(), None, None, now=BASE + 100,
            read=lambda: [self.root],
            send=lambda p: seen.append(p) or {"id": "test"},
            ask=lambda msgs, **kwargs: "Proposta tecnica verificabile per una singola specie: scegliere habitat, bilancio energetico e parametri.")
        self.assertEqual(result["room"], "genesis")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["room"], "genesis")
        self.assertEqual(seen[0]["reply_to"], ROOT)

    def test_run_bot_fauna_only_does_not_send_on_http500(self):
        import base64
        import agora_bots as ab
        cfg = dict(self.cfg, private_rooms_status={"genesis": "HTTP 500"})
        calls = []
        result = ab.run_bot(
            dict(self.bot, model={"label": "test"}, persona="test"),
            cfg, "https://example.invalid", base64.b64encode(b"x" * 32).decode(),
            None, None, now=BASE + 100, read=lambda: [self.root],
            send=lambda p: calls.append(p),
            ask=lambda *args, **kwargs: self.fail("Model should not be called"))
        self.assertEqual(result["action"], "idle")
        self.assertEqual(calls, [])


    def test_kaggle_fauna_only_never_exports_private_posts(self):
        import tempfile
        from unittest import mock
        import kaggle_turn
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(kaggle_turn, "KERNEL_DIR", Path(folder)):
                jobs = kaggle_turn.prepare(
                    dict(self.cfg, bots=[{"name": "lume", "runner": "kaggle",
                                           "model": {"hf": "unused"}}]),
                    [], BASE + 100, username="test",
                    private={"lume": {"posts": [self.root],
                                      "accessible": ["genesis"], "errors": {}}})
            self.assertEqual(jobs, [])
            self.assertFalse(any(Path(folder).iterdir()))

    def test_kaggle_fauna_only_discards_results(self):
        import kaggle_turn
        reports = kaggle_turn.finish(
            self.cfg,
            [{"bot": "lume", "action": "reply", "room": "genesis", "giro": "fauna-only"}],
            [{"bot": "lume", "text": "testo privato"}],
            None,
            lambda p: self.fail("Kaggle must not publish in FAUNA ONLY"),
            BASE + 100,
        )
        self.assertEqual(len(reports), 1)
        self.assertIn("sospesa", reports[0][1])


if __name__ == "__main__":
    unittest.main()
