"""Checks that Montessori teaching is specific to seme and does not change others."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bots"))
import agora_bots as ab


SEME = {"name": "seme", "persona": "Sei seme, educatrice.", "model": {"label": "test"}}
LUME = {"name": "lume", "persona": "Sei lume, curioso.", "model": {"label": "test"}}


class MontessoriLabTests(unittest.TestCase):
    def test_protocol_requires_small_real_verifiable_experiment(self):
        p = ab.MONTESSORI_SEME
        for term in ("SEME-MONTESSORI-LAB-01", "una sola micro-prova",
                     "input", "confermare o smentire", "senza inventare un risultato",
                     "Non assegnare la stessa micro-prova", "non partecipare"):
            self.assertIn(term, p)

    def test_only_seme_gets_mentor_system_in_normal_turn(self):
        post = {"id": "p1", "author": "fermo", "room": "generale",
                "text": "Non riesco a verificare la notizia", "reply_to": None}
        yes = ab.messages_for(SEME, "", "reply", post, [post])[0]["content"]
        no = ab.messages_for(LUME, "", "reply", post, [post])[0]["content"]
        self.assertIn("SEME-MONTESSORI-LAB-01", yes)
        self.assertNotIn("SEME-MONTESSORI-LAB-01", no)
        self.assertIn("METODO-VERIFICA-01", yes)

    def test_free_turn_has_concrete_exercise_prompt_and_real_peer_context(self):
        cfg = {"free_room_open": True, "free_chance": 1.0, "max_posts_per_day": 6,
               "bots": [SEME, LUME], "private_rooms_accessible": []}
        plan = ab.plan_free(SEME, cfg, [], "", "", 1800000000,
                            rng=random.Random(0))
        self.assertIsNotNone(plan)
        self.assertIn("SEME-MONTESSORI-LAB-01", plan["write"][0]["content"])
        self.assertIn("Per seme: se scegli di aiutare", plan["write"][1]["content"])
        self.assertIn("input preciso", plan["write"][1]["content"])
        other = ab.plan_free(LUME, cfg, [], "", "", 1800000000,
                             rng=random.Random(0))
        self.assertNotIn("SEME-MONTESSORI-LAB-01", other["write"][0]["content"])
        self.assertNotIn("Per seme:", other["write"][1]["content"])

    def test_reflection_keeps_learning_by_feedback_without_affecting_peers(self):
        seme = ab.reflection_messages(SEME, "", "Nessuna prova completata.")
        lume = ab.reflection_messages(LUME, "", "Nessuna prova completata.")
        self.assertIn("SEME-MONTESSORI-LAB-01", seme[0]["content"])
        self.assertNotIn("SEME-MONTESSORI-LAB-01", lume[0]["content"])
        self.assertIn("Nessuna prova completata.", seme[1]["content"])


if __name__ == "__main__":
    unittest.main()
