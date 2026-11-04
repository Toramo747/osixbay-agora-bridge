import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import recupero_registro as rr  # noqa: E402


def _w(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _r(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _repo(tmp_path):
    repo = tmp_path / "repo"
    os.makedirs(repo / "bots", exist_ok=True)
    (repo / "bots/bots.json").write_text(json.dumps({"bots": [{"name": "seme"}, {"name": "vaglio"}]}))
    return repo


def test_unisce_senza_duplicati_e_in_ordine(tmp_path):
    repo = _repo(tmp_path)
    base = {"t": "2026-11-03 23:20 UTC", "azione": "free"}
    a = {"t": "2026-11-03 23:45 UTC", "azione": "free"}
    b = {"t": "2026-11-04 02:18 UTC", "azione": "free"}
    c = {"t": "2026-11-04 05:40 UTC", "azione": "free"}
    _w(str(repo / "bots/registro/2026-11-03/seme.jsonl"), [base])
    _w(str(repo / "bots/registro/2026-11-04/seme.jsonl"), [c])  # giro successivo già salvato
    art = tmp_path / "art"
    _w(str(art / "191/memory-seme/registro/2026-11-03/seme.jsonl"), [base, a])
    _w(str(art / "192/memory-seme/registro/2026-11-04/seme.jsonl"), [b])
    _w(str(art / "193/memory-seme/registro/2026-11-04/seme.jsonl"), [b])  # duplicato
    assert rr.recover(str(art), str(repo)) == 2
    assert _r(repo / "bots/registro/2026-11-03/seme.jsonl") == [base, a]
    assert _r(repo / "bots/registro/2026-11-04/seme.jsonl") == [b, c]
    assert rr.recover(str(art), str(repo)) == 0  # idempotente


def test_uscite_e_righe_esistenti_intatte(tmp_path):
    repo = _repo(tmp_path)
    dst = repo / "bots/registro/2026-11-04/uscite/vaglio.jsonl"
    os.makedirs(dst.parent)
    dst.write_text('{"t":"2026-11-04 01:00 UTC","testo":"è"}\n', encoding="utf-8")  # formato originale
    art = tmp_path / "art"
    _w(str(art / "192/memory-vaglio/registro/2026-11-04/uscite/vaglio.jsonl"), [{"t": "2026-11-04 02:20 UTC", "testo": "x"}])
    assert rr.recover(str(art), str(repo)) == 1
    assert dst.read_text(encoding="utf-8").splitlines()[0] == '{"t":"2026-11-04 01:00 UTC","testo":"è"}'


def test_scarta_nomi_date_e_file_non_validi(tmp_path):
    repo = _repo(tmp_path)
    art = tmp_path / "art"
    _w(str(art / "1/memory-intruso/registro/2026-11-04/intruso.jsonl"), [{"t": "x"}])
    _w(str(art / "1/memory-seme/registro/oggi/seme.jsonl"), [{"t": "x"}])
    p = art / "1/memory-vaglio/registro/2026-11-04/vaglio.jsonl"
    os.makedirs(p.parent)
    p.write_text("non json\n")
    assert rr.recover(str(art), str(repo)) == 0
    assert not (repo / "bots/registro").exists()
