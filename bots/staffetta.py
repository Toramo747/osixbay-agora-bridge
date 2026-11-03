"""Staffetta dei turni: alla fine di un giro completo decide se e quando far partire il successivo.

Il cron di GitHub è "best effort" e salta la maggior parte degli avvii; la staffetta tiene i giri
regolari senza servizi esterni. Protezioni: un solo giro attivo alla volta, intervallo minimo,
tetto giornaliero, Kaggle al massimo ogni N ore. Solo dati di GitHub, nessun segreto.

Uso: python bots/staffetta.py <runs agora-bots.json> <runs agora-bots-kaggle.json>
(output di `gh api .../runs`), con RUN_ID e le variabili facoltative STAFFETTA_*.
Stampa un JSON {"wait": secondi, "bots": bool, "kaggle": bool, "why": "..."}.

Guardia Kaggle: python bots/staffetta.py --kaggle-guard <runs agora-bots-kaggle degli ultimi 7 giorni>
(con RUN_ID, KAGGLE_EVERY_HOURS, KAGGLE_WEEK_BUDGET_H). Stampa {"go": bool, "used_h", "gap_h", "why"}.
Tetto settimanale: la durata dei run Kaggle negli ultimi 7 giorni (per eccesso: comprende attese e
preparazione) non deve superare il budget; sopra il budget i giri tornano ogni 3 ore, sopra il tetto
rigido si fermano. La quota vera di Kaggle (30 h) non è leggibile da GitHub: questa è una stima prudente.
"""
import json, os, sys, time
from datetime import datetime

ACTIVE = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}


def ts(value):
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()) if value else 0


def clamp(value, low, high, default):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def decide(now, self_id, bots_runs, kaggle_runs, gap_min=20, max_day=80, kaggle_gap_h=3):
    """bots_runs / kaggle_runs: [{'id', 'status', 'created', 'started'}] con tempi in secondi UTC."""
    me = next((r for r in bots_runs if r['id'] == self_id), None)
    started = (me or {}).get('started') or now
    others = [r for r in bots_runs if r['id'] != self_id]
    out = {'wait': 0, 'bots': False, 'kaggle': False}
    if any(r['status'] in ACTIVE for r in others):
        out['why'] = 'un altro giro è già in coda o in corso'
    elif sum(1 for r in bots_runs if now - r['created'] < 86400) >= max_day:
        out['why'] = f'tetto di {max_day} giri nelle ultime 24 ore raggiunto'
    else:
        out['bots'] = True
        out['wait'] = max(0, started + gap_min * 60 - now)
        out['why'] = f'prossimo giro tra {out["wait"] // 60} minuti'
    last_kaggle = max((r['created'] for r in kaggle_runs), default=0)
    if not any(r['status'] in ACTIVE for r in kaggle_runs) and now - last_kaggle >= kaggle_gap_h * 3600:
        out['kaggle'] = True
    return out


def kaggle_guard(now, self_id, runs, gap_h=1, budget_h=25, fallback_h=3, hard_h=28, real_min_s=120):
    """Decide se questo run Kaggle (self_id) deve davvero usare la GPU. I run saltati durano pochi secondi e
    non contano né come consumo né come ultimo giro."""
    week = [r for r in runs if r['id'] != self_id and now - r['created'] < 7 * 86400]

    def dur(r):
        end = now if r['status'] in ACTIVE else (r.get('updated') or now)
        return max(0, end - (r.get('started') or r['created']))
    real = [r for r in week if r['status'] in ACTIVE or dur(r) >= real_min_s]
    used = sum(dur(r) for r in real) / 3600
    out = {'go': False, 'used_h': round(used, 2), 'budget_h': budget_h}
    gap = fallback_h if used >= budget_h else gap_h
    out['gap_h'] = gap
    last = max(((r.get('started') or r['created']) for r in real), default=0)
    if any(r['status'] in ACTIVE for r in week):
        out['why'] = 'un altro giro Kaggle è in coda o in corso'
    elif used >= hard_h:
        out['why'] = f'tetto rigido: {used:.1f} h di GPU negli ultimi 7 giorni (max {hard_h})'
    elif now - last < gap * 3600 - 600:
        out['why'] = f'ultimo giro {round((now - last) / 60)} min fa, intervallo {gap} h' + (' (sopra il budget settimanale)' if gap != gap_h else '')
    else:
        out['go'] = True
        out['why'] = f'via: {used:.1f} h negli ultimi 7 giorni, intervallo {gap} h'
    return out


def load(path):
    runs = json.load(open(path)).get('workflow_runs', [])
    return [{'id': r['id'], 'status': r['status'], 'created': ts(r.get('created_at')),
             'started': ts(r.get('run_started_at')), 'updated': ts(r.get('updated_at'))} for r in runs]


def main():
    env = os.environ
    if sys.argv[1] == '--kaggle-guard':
        print(json.dumps(kaggle_guard(int(time.time()), int(env['RUN_ID']), load(sys.argv[2]),
                                      gap_h=clamp(env.get('KAGGLE_EVERY_HOURS'), 1, 24, 1),
                                      budget_h=clamp(env.get('KAGGLE_WEEK_BUDGET_H'), 1, 27, 25)), ensure_ascii=False))
        return
    print(json.dumps(decide(int(time.time()), int(env['RUN_ID']), load(sys.argv[1]), load(sys.argv[2]),
                            gap_min=clamp(env.get('STAFFETTA_MINUTES'), 15, 180, 20),
                            max_day=clamp(env.get('STAFFETTA_MAX_PER_DAY'), 1, 96, 80),
                            kaggle_gap_h=clamp(env.get('KAGGLE_EVERY_HOURS'), 1, 24, 1)), ensure_ascii=False))


if __name__ == '__main__':
    main()
