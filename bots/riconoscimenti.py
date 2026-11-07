"""Riconoscimenti di competenza derivati da prove del quaderno, non da messaggi o approvazioni.

Nessuna classifica pubblica, chiamata AI, modifica dei pesi o file di premi.
I punti sono un feedback formativo privato nel prompt; non dichiarano verita scientifica:
l'impronta valida dimostra l'esecuzione di uno strumento, non la pertinenza della sua uscita.
"""
from collections import defaultdict
from pathlib import Path

import quaderno


PESI = {
    'esperimenti_documentati': 3,
    'risultati_confermati': 3,
    'verifiche_indipendenti': 2,
    'correzioni_documentate': 2,
    'riusi_documentati': 3,
}
LIMIT_EVENTI = 2


def quadro(root=None):
    """Calcola riconoscimenti riproducibili, scartando impronte inventate e duplicati."""
    root = Path(root or quaderno.ROOT)
    events = quaderno.load_events(root)
    by_id = quaderno.entries(events)
    proofs = {}
    for name in {e['autore'] for e in events}:
        proofs[name] = set(quaderno.tool_proofs(name, root))
    def valid(e):
        owned = proofs.get(e.get('autore'), set())
        return {p.get('sha') for p in e.get('prove') or []
                if p.get('valida') and p.get('sha') in owned}

    # Una medesima uscita di uno strumento non genera infinite micro-ricompense.
    used_proofs = defaultdict(set)
    counted = defaultdict(set)
    result_sources = set()
    scores = defaultdict(lambda: {'punti': 0, **{key: 0 for key in PESI}, 'tracce': []})

    def award(name, typ, key, shas=(), consume=True):
        token = (typ, key)
        if token in counted[name]:
            return False
        eligible = sorted(set(shas) - used_proofs[name]) if consume else sorted(shas)
        if consume and not eligible:
            return False
        if consume:
            used_proofs[name].add(eligible[0])
        counted[name].add(token)
        row = scores[name]
        row[typ] += 1
        row['punti'] += PESI[typ]
        row['tracce'].append((typ, key))
        return True

    for e in events:
        who, eid, kind = e['autore'], e['id'], e.get('evento')
        own_proofs = valid(e)
        if kind == 'nuova' and e.get('tipo') == 'esperimento_eseguito':
            award(who, 'esperimenti_documentati', eid, own_proofs)
        if kind == 'nuova' and e.get('tipo') in ('esperimento_eseguito', 'risultato'):
            # La conoscenza viene riusata solo se il risultato altrui e' stato confermato
            # e se l'azione nuova ha una prova propria non gia' premiata.
            links = e.get('collegamenti') or []
            for ref in links:
                original = by_id.get(ref)
                if original and original['autore'] != who and original['t'] < e.get('t', ''):
                    if _confirmed(original, valid, before=e.get('t', '')):
                        if award(who, 'riusi_documentati', eid, own_proofs):
                            break
        if kind == 'correggi' and own_proofs:
            target = by_id.get(e.get('riferimento'))
            if target and target['autore'] == who:
                award(who, 'correzioni_documentate', e['riferimento'], own_proofs)
        if kind in ('verifica', 'contesta') and own_proofs:
            target = by_id.get(e.get('riferimento'))
            if not target or target['autore'] == who:
                continue
            # Una verifica senza una prova dell'autore non convalida un risultato.
            source = any(valid(version) for version in target['versioni']
                         if version.get('t', '') <= e.get('t', ''))
            if not source:
                continue
            if kind == 'verifica' and e.get('esito') == 'conferma':
                award(who, 'verifiche_indipendenti', e['riferimento'], own_proofs)
            elif kind == 'contesta' or e.get('esito') == 'smentita':
                award(who, 'correzioni_documentate', e['riferimento'], own_proofs)

    # La scoperta acquista un riconoscimento proprio solo dopo conferma indipendente
    # ancora valida; la medesima prova originaria non finanzia molte scoperte.
    for entry in sorted(by_id.values(), key=lambda v: (v['t'], v['id'])):
        if entry.get('tipo') != 'risultato' or not _confirmed(entry, valid):
            continue
        src = sorted({p for e in entry['versioni'] for p in valid(e)})
        unseen = [p for p in src if (entry['autore'], p) not in result_sources]
        if unseen:
            result_sources.add((entry['autore'], unseen[0]))
            award(entry['autore'], 'risultati_confermati', entry['id'], src, consume=False)

    return {n: v for n, v in scores.items()}


def _confirmed(entry, valid, before=None):
    if entry.get('tipo') != 'risultato':
        return False
    versions = [e for e in entry['versioni'] if before is None or e.get('t', '') <= before]
    if not any(valid(e) for e in versions):
        return False
    judgements = [g for g in entry['giudizi']
                  if (before is None or g.get('t', '') <= before)
                  and g['autore'] != entry['autore'] and valid(g)]
    if not judgements:
        return False
    last = judgements[-1]
    return last['evento'] == 'verifica' and last.get('esito') == 'conferma'


def feedback(name, root=None):
    """Testo breve per la memoria di lavoro; non altera mai il diario dell'agente."""
    row = quadro(root).get(name)
    if not row:
        return ("Riconoscimenti basati sul quaderno: nessuna competenza ancora documentata "
                "con le prove richieste. Non e' un giudizio su di te. "
                "Puoi scegliere una micro-prova, registrare l'uscita reale di uno strumento "
                "e chiedere una replica indipendente. Non inventare esiti.")
    metrics = (
        ('esperimenti_documentati', 'esperimenti con traccia'),
        ('risultati_confermati', 'risultati confermati'),
        ('verifiche_indipendenti', 'verifiche indipendenti'),
        ('correzioni_documentate', 'correzioni o contestazioni con traccia'),
        ('riusi_documentati', 'riusi documentati'),
    )
    detail = '; '.join(f"{label}: {row[key]}" for key, label in metrics if row[key])
    recent = ', '.join(str(key) for _, key in row['tracce'][-LIMIT_EVENTI:])
    return (f"Riconoscimenti documentati nel quaderno: {row['punti']} punti formativi "
            f"({detail}). Tracce: {recent}. Non e' una classifica ne' un premio per post, "
            "domande o accordi. Le impronte attestano l'uso di strumenti, "
            "non provano da sole la verita delle conclusioni.")
