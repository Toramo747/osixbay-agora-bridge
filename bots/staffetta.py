"""Staffetta dei turni: alla fine di un giro completo decide se e quando far partire il successivo.

Il cron di GitHub è "best effort" e salta la maggior parte degli avvii; la staffetta tiene i giri
regolari senza servizi esterni. Protezioni: un solo giro attivo alla volta, intervallo minimo,
tetto giornaliero, Kaggle al massimo ogni N ore. Solo dati di GitHub, nessun segreto.

Uso: python bots/staffetta.py <runs agora-bots.json> <runs agora-bots-kaggle.json>
(output di `gh api .../runs`), con RUN_ID e le variabili facoltative STAFFETTA_*.
Stampa un JSON {"wait": secondi, "bots": bool, "kaggle": bool, "why": "..."}.
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


def load(path):
    runs = json.load(open(path)).get('workflow_runs', [])
    return [{'id': r['id'], 'status': r['status'], 'created': ts(r.get('created_at')),
             'started': ts(r.get('run_started_at'))} for r in runs]


def main():
    env = os.environ
    print(json.dumps(decide(int(time.time()), int(env['RUN_ID']), load(sys.argv[1]), load(sys.argv[2]),
                            gap_min=clamp(env.get('STAFFETTA_MINUTES'), 15, 180, 20),
                            max_day=clamp(env.get('STAFFETTA_MAX_PER_DAY'), 1, 96, 80),
                            kaggle_gap_h=clamp(env.get('KAGGLE_EVERY_HOURS'), 3, 24, 3)), ensure_ascii=False))


if __name__ == '__main__':
    main()
