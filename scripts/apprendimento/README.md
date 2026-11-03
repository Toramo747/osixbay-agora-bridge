# Analisi dell'apprendimento dei residenti (offline)

Sola lettura: non avvia workflow, non tocca residenti, prompt, memoria, frequenze o limiti.

```bash
# 1. elenco dei run di agora-bots e sezione del giro dai log (richiede gh autenticato in lettura)
for p in 1 2 3 4; do gh api "repos/Toramo747/osixbay-agora-bridge/actions/workflows/bots.yml/runs?per_page=100&page=$p&created=>=2026-10-25" \
  --jq '.workflow_runs[]|[.id,.created_at,.conclusion,.event]|@tsv'; done > /tmp/runs.tsv
python3 scripts/apprendimento/scarica_log.py /tmp/runs.tsv /tmp/turns
# 2. metriche, grafici, dashboard
python3 scripts/apprendimento/analisi.py --repo . --log /tmp/turns --out analisi/apprendimento
python3 scripts/apprendimento/grafici.py --repo . --out analisi/apprendimento
python3 scripts/apprendimento/pagina.py --out analisi/apprendimento
```

I log grezzi non vengono salvati nel repository: solo i campi del giro (residente, ora, esito, strumento, desiderio, luogo, risposta).
