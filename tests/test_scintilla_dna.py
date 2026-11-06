"""Regression checks for optional SCINTILLA-DNA-01, without network or model calls."""
import sys
import random
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bots"))
import agora_bots as ab


BOT = {"name": "lume", "persona": "Sei lume.", "model": {"label": "test"}}


class ScintillaDNATests(unittest.TestCase):
    def test_principle_is_non_compulsory_and_evidence_based(self):
        dna = ab.SCINTILLA_DNA
        self.assertIn("SCINTILLA-DNA-01", dna)
        self.assertIn("non inventare dati", dna)
        self.assertIn("scegli tu", dna)
        self.assertIn("un accordo a parole non e una verifica", dna)

    def test_normal_reply_receives_common_principle(self):
        post = {"id": "p1", "author": "fermo", "room": "generale", "text": "Come lo verifichiamo?", "reply_to": None}
        messages = ab.messages_for(BOT, "", "reply", post, [post])
        self.assertIn("SCINTILLA-DNA-01", messages[0]["content"])
        self.assertIn("Sei lume", messages[0]["content"])

    def test_free_choice_receives_common_principle_and_quaderno(self):
        cfg = {"free_room_open": True, "free_chance": 1.0, "max_posts_per_day": 6,
               "bots": [BOT], "private_rooms_accessible": []}
        plan = ab.plan_free(BOT, cfg, [], "", "", 1800000000, rng=random.Random(0))
        self.assertIsNotNone(plan)
        self.assertIn("SCINTILLA-DNA-01", plan["where"][0]["content"])
        self.assertIn("SCINTILLA-DNA-01", plan["intent"][0]["content"])
        self.assertIn("QUADERNO: scrivi ipotesi", plan["intent"][1]["content"])

    def test_reflection_has_principle_without_forcing_claims(self):
        msg = ab.reflection_messages(BOT, "", "Nessuna prova raccolta.")
        self.assertIn("SCINTILLA-DNA-01", msg[0]["content"])
        self.assertIn("Nessuna prova raccolta", msg[1]["content"])


if __name__ == "__main__":
    unittest.main()
