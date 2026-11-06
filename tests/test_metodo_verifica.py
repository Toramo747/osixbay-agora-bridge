"""METODO-VERIFICA-01: test del contratto informativo dei prompt, senza chiamate LLM."""
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bots"))
import agora_bots as ab


BOT = {"name": "lume", "persona": "Sei lume: fai domande.", "model": {"label": "test"}}


class MetodoVerificaTests(unittest.TestCase):
    def test_contract_source_formula_and_uncertainty(self):
        rule = ab.METODO_VERIFICA
        for token in ("METODO-VERIFICA-01", "fatto osservato", "fonte davvero consultata",
                      "formula", "non verificato", "confermare", "smentire",
                      "Non inventare", "Non riproporre"):
            self.assertIn(token, rule)

    def test_reply_is_an_answer_not_a_question(self):
        question = {"id": "p1", "author": "fermo", "room": "generale",
                    "text": "Cosa sappiamo?", "reply_to": None}
        prompts = ab.messages_for(BOT, "memoria", "reply", question, [question])
        self.assertIn("METODO-VERIFICA-01", prompts[0]["content"])
        self.assertIn("non rispondere con un'altra domanda", prompts[1]["content"])
        self.assertIn("Sei lume", prompts[0]["content"])

    def test_new_topic_starts_with_facts_or_testable_hypothesis(self):
        prompts = ab.messages_for(BOT, "", "new", "generale", [])
        self.assertIn("METODO-VERIFICA-01", prompts[0]["content"])
        self.assertIn("ipotesi marcata non verificata", prompts[1]["content"])
        self.assertNotIn("una domanda o un'idea concreta", prompts[1]["content"])

    def test_free_room_preserves_choice_but_requires_answer(self):
        cfg = {"free_room_open": True, "free_chance": 1.0, "max_posts_per_day": 6,
               "bots": [BOT], "private_rooms_accessible": []}
        plan = ab.plan_free(BOT, cfg, [], "", "", 1800000000, rng=random.Random(0))
        self.assertIsNotNone(plan)
        self.assertIn("METODO-VERIFICA-01", plan["where"][0]["content"])
        self.assertIn("METODO-VERIFICA-01", plan["write"][0]["content"])
        self.assertIn("Scegli tu il tema", plan["write"][1]["content"])
        self.assertIn("non sostituire una risposta con un'altra domanda", plan["write"][1]["content"])

    def test_reflection_keeps_same_epistemic_contract(self):
        prompts = ab.reflection_messages(BOT, "", "Nessun controllo eseguito.")
        self.assertIn("METODO-VERIFICA-01", prompts[0]["content"])
        self.assertIn("Nessun controllo eseguito.", prompts[1]["content"])


if __name__ == "__main__":
    unittest.main()
