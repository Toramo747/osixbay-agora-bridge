"""Recupero una tantum del registro dei giri da artefatti memory-* di run il cui salvataggio è fallito.

Uso: python scripts/recupero_registro.py <cartella_artefatti> [<repo>]
  <cartella_artefatti>/<run_id>/memory-<nome>/...   (come scaricati da `gh run download`)

Recupera solo bots/registro/<data>/<nome>.jsonl e bots/registro/<data>/uscite/<nome>.jsonl.
Memoria, stato, quaderno e luoghi NON si toccano: i giri successivi li hanno già superati.
Ogni riga si aggiunge una sola volta (confronto sul JSON canonico) e il file resta in ordine di "t".
Stesse regole del job remember: nome in bots.json, data valida, righe JSON, dimensione limitata.
"""
import glob
import json
import os
import re
import sys

MAX_BYTES = 450000
DAY = re.compile(r"^20\d\d-[01]\d-[0-3]\d$")


def _rows(path):
    """Coppie (oggetto, riga originale): le righe già salvate si riscrivono byte per byte."""
    with open(path, encoding="utf-8") as f:
        return [(json.loads(l), l.rstrip("\n")) for l in f if l.strip()]


def _key(row):
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


def merge(existing, extra):
    """Righe esistenti + righe nuove non già presenti, in ordine stabile di "t" se tutte lo hanno."""
    seen = {_key(o) for o, _ in existing}
    out = list(existing)
    for o, raw in extra:
        k = _key(o)
        if k not in seen:
            seen.add(k)
            out.append((o, raw))
    if all(isinstance(o, dict) and isinstance(o.get("t"), str) for o, _ in out):
        out.sort(key=lambda r: r[0]["t"])
    return out


def recover(art_dir, repo="."):
    names = {b["name"] for b in json.load(open(os.path.join(repo, "bots/bots.json")))["bots"]}
    added = 0
    for d in sorted(glob.glob(os.path.join(art_dir, "*", "memory-*"))):
        name = d.rsplit("memory-", 1)[1]
        if name not in names or not re.fullmatch(r"[a-z0-9-]+", name):
            continue
        sources = [(f, os.path.basename(os.path.dirname(f)), False) for f in glob.glob(os.path.join(d, "registro", "*", name + ".jsonl"))]
        sources += [(f, os.path.basename(os.path.dirname(os.path.dirname(f))), True) for f in glob.glob(os.path.join(d, "registro", "*", "uscite", name + ".jsonl"))]
        for src, day, uscite in sources:
            if not DAY.match(day) or os.path.getsize(src) > MAX_BYTES:
                continue
            try:
                extra = _rows(src)
            except (ValueError, UnicodeDecodeError):
                continue
            dst_dir = os.path.join(repo, "bots/registro", day, "uscite" if uscite else "")
            dst = os.path.join(dst_dir, name + ".jsonl")
            existing = _rows(dst) if os.path.exists(dst) else []
            merged = merge(existing, extra)
            if len(merged) == len(existing):
                continue
            body = "".join(raw + "\n" for _, raw in merged)
            if len(body.encode("utf-8")) > MAX_BYTES:
                print(f"saltato (troppo grande): {dst}")
                continue
            os.makedirs(dst_dir, exist_ok=True)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(body)
            n = len(merged) - len(existing)
            added += n
            print(f"{dst}: +{n} righe")
    print(f"totale righe recuperate: {added}")
    return added


if __name__ == "__main__":
    recover(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ".")
