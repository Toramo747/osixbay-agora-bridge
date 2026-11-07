"""Genesis: il catalogo preparatorio non deve attivare codice né aprire stanze."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
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
        # Il bridge non deve tentare la lettura della nuova stanza prima
        # che il server Sites applichi e collaudi le ACL.
        self.assertNotIn("biblioteca-genesis", self.cfg.get("private_rooms", []))

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
        self.assertIn("NON equivale", self.docs.upper())


if __name__ == "__main__":
    unittest.main()
