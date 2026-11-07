"""Genesis: il catalogo preparatorio non deve attivare codice né aprire stanze."""
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots"))
import agora_bots as ab  # noqa: E402
import ambiente as amb  # noqa: E402
CATALOGO = ROOT / "bots" / "genesi" / "biblioteca_evolutiva" / "catalogo.json"
SPEC = ROOT / "bots" / "genesi" / "biblioteca_evolutiva" / "README.md"
CONFIG = ROOT / "bots" / "bots.json"
EXPECTED = (
    "fsm", "utility-ai", "steering", "animazione-procedurale",
    "genetica", "memoria-associativa", "apprendimento-leggero", "ecologia"
)


class BibliotecaEvolutivaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
        cls.docs = SPEC.read_text(encoding="utf-8")
        cls.cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_eight_algorithm_families_no_claims_of_verified_code(self):
        rows = self.catalogo["famiglie"]
        self.assertEqual(tuple(x["id"] for x in rows), EXPECTED)
        self.assertEqual(len(set(x["id"] for x in rows)), 8)
        self.assertTrue(all(x.get("titolo") and x.get("obiettivo") and
                            x.get("esempio_test") for x in rows))
        self.assertEqual(self.catalogo["voci"], [])
        self.assertEqual(self.catalogo["versionamento"]["stato_iniziale"], "proposto")
        self.assertFalse(self.catalogo["versionamento"]["esecuzione_automatica"])

    def test_staged_private_room_cannot_be_misreported_as_live(self):
        p = self.catalogo["stanza_proposta"]
        self.assertEqual(p["slug"], "biblioteca-genesis")
        self.assertEqual(p["visibilita"], "privata")
        self.assertEqual(p["stato"], "non_creata_in_questa_PR")
        self.assertIn("stessa allowlist", p["politica_accesso"])
        # Configurazione soltanto in PR: NON attiva finche non viene integrata.
        self.assertEqual(self.cfg.get("private_rooms"), ["genesis", "biblioteca-genesis"])

    def test_evidence_and_biological_constraints_required(self):
        f = set(self.catalogo["contratto_voce"]["obbligatori"])
        for field in ("precondizioni_biologiche", "test_riproducibile",
                      "costo_stimato", "criterio_successo", "evidenze"):
            self.assertIn(field, f)
        self.assertTrue({"proposto", "sperimentale", "verificato",
                         "confutato"}.issubset(
                             self.catalogo["versionamento"]["stati"]))

    def test_privacy_and_room_invariants_documented(self):
        for phrase in ("/feed.json", "stessa", "GET /rooms/biblioteca-genesis.json",
                       "POST", "403/404", "nonce", "noindex",
                       "no", "genesis-godot", "private_rooms"):
            self.assertIn(phrase, self.docs)
        self.assertIn("nessun accesso", " ".join(self.catalogo["guardrail"]).lower())
        self.assertIn("NON EQUIVALE", self.docs.upper())


    def test_private_room_not_selected_for_normal_public_reply(self):
        now = 1800000000
        bot = {"name": "lume", "persona": "Curioso", "rooms": ["generale"],
               "model": {"label": "test"}}
        cfg = {"bots": [bot], "private_rooms": ["genesis", "biblioteca-genesis"],
               "free_room_open": False, "new_post_chance": 1.0,
               "tool_proposal_chance": 0.0}
        private = {"id": "p1", "author": "fermo", "kind": "human",
                   "room": "biblioteca-genesis", "created": now - 60,
                   "text": "DATI_RISERVATI_BIBLIOTECA @lume"}
        plan = ab.plan_turn(bot, cfg, [private], "memoria", now, random.Random(0))
        self.assertEqual((plan["action"], plan["room"]), ("new", "generale"))
        self.assertNotIn("DATI_RISERVATI_BIBLIOTECA", json.dumps(plan))

    def test_private_room_isolation_of_public_diary_and_tools(self):
        now = 1800000000
        plan = {"room": "biblioteca-genesis", "stanze_private": ["genesis", "biblioteca-genesis"],
                "giro": "libero", "action": "free", "diagnostica_private": {
                    "biblioteca-genesis_accessible": True}}
        self.assertTrue(ab.is_private_turn(plan))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            row = amb.journal("lume", plan, now, "pubblicato", root=root,
                              extra={"text": "Uso AuthentiCheckSegreto qui dentro per DATI_RISERVATI_BIBLIOTECA",
                                     "tool_output": "RISULTATO_PRIVATE_NON_PUBBLICABILE",
                                     "query": "ANALIZZA: DATI_RISERVATI_BIBLIOTECA"})
            self.assertEqual(row["strumento"], "ANALIZZA")
            self.assertNotIn("testo", row)
            self.assertIn("testo_omesso", row)
            self.assertNotIn("estratto", row["uscita_strumento"])
            self.assertEqual(row["vincoli"], [])
            all_public = "\\n".join(p.read_text() for p in root.glob("registro/**/*.jsonl"))
            for secret in ("AuthentiCheckSegreto", "DATI_RISERVATI_BIBLIOTECA",
                           "RISULTATO_PRIVATE_NON_PUBBLICABILE"):
                self.assertNotIn(secret, all_public)

    def test_private_read_failure_is_not_seen_as_an_empty_room(self):
        def get(room):
            if room == "genesis":
                return {"posts": []}
            raise PermissionError("denied")
        res = ab.read_private_rooms_status("https://example.invalid",
                                           ["genesis", "biblioteca-genesis"],
                                           "lume", "unused", now=1800000000, get=get)
        self.assertEqual(res["accessible"], ["genesis"])
        self.assertNotIn("biblioteca-genesis", res["accessible"])
        self.assertEqual(res["errors"]["biblioteca-genesis"], "PermissionError")
        self.assertEqual(res["posts"], [])

if __name__ == "__main__":
    unittest.main()
