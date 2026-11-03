"""Dashboard HTML statica (un file, nessuna risorsa esterna) + REPORT.md + METODOLOGIA.md.
Uso: python3 scripts/apprendimento/pagina.py --out analisi/apprendimento
"""
import argparse, html, json, os, pickle, re
from collections import Counter

P = argparse.ArgumentParser()
P.add_argument('--out', default='analisi/apprendimento')
A = P.parse_args()
OUT = os.path.abspath(A.out)
S = pickle.load(open(os.path.join(OUT, '.stato.pkl'), 'rb'))
G = pickle.load(open(os.path.join(OUT, '.grafici.pkl'), 'rb'))
M, RES, MODELLO, RUNNER, EVENTI = S['M'], S['RES'], S['MODELLO'], S['RUNNER'], S['EVENTI']
CH, RESCH = G['CH'], G['RESCH']
E = html.escape
cov = M['copertura']
from datetime import datetime, timezone
AGG = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
sys_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'grafici.py')
CSSVARS = re.search(r'CSSVARS = """(.*?)"""', open(sys_path).read(), re.S).group(1)
CSSDARK = re.search(r'CSSDARK = """(.*?)"""', open(sys_path).read(), re.S).group(1)

TITOLI = {
    '1': 'Giri riusciti, respinti e inattivi', '2': 'Frequenza reale dei giri', '3': 'Strumenti nel tempo (conteggi)', '3b': 'Strumenti ogni 100 giri',
    '4': 'OSSERVA per residente', '5': 'Richieste ridondanti / 100 giri', '6': 'Strumenti inesistenti nei testi', '6b': 'Strumenti inesistenti nelle schede',
    '7': 'Comandi errati / 100 giri', '8': 'Esplorazione dei luoghi', '9': 'Riferimenti delle Sfide ricevuti', '10': 'Collaborazioni',
    'A': 'Accuratezza dell\'apprendimento', 'B': 'Precision, Recall, F1', 'Ca': 'Riduzione errori — richieste ridondanti',
    'Cb': 'Riduzione errori — comandi errati', 'Cc': 'Riduzione errori — strumenti inesistenti', 'D': 'Memoria e retention dopo OSSERVA',
    'E': 'Scoperta degli strumenti', 'F': 'Correzione autonoma degli errori', 'G': 'Applicazione delle conoscenze', 'H': 'Collaborazione produttiva',
    'M': 'Confronto per modello/runner', 'Q': 'Quaderno condiviso', 'Qr': 'Discussioni ripetitive'}


def badge(stato):
    k = 'ok' if stato.startswith('DISPONIBILE') else ('mid' if stato.startswith('PARZIALE') else 'no')
    return f'<span class="b {k}">{E(stato)}</span>'


LETTURA_3_11 = """**Lettura del 3/11/2026, 07:00 UTC — scritta a mano, NON si aggiorna** (i numeri sopra sì).
- Il cambiamento più netto è il calo degli strumenti inesistenti nei testi: da 32–84 ogni 100 post (2/11 mattina) a 0–6 dopo il 2/11 sera per 8 residenti su 9; lume restava a 19. Nelle schede delle abilità i nomi restavano.
- Causa non attribuibile: il 2/11 17:43 sono arrivati insieme OSSERVA, la sintesi dell'ambiente nel prompt (che elenca gli strumenti reali a ogni giro) e la fine dei 429. È più probabile un effetto dell'informazione nel contesto che un apprendimento persistente.
- Le richieste ridondanti calavano poco (29 → 24 ogni 100 giri intorno agli OSSERVA); architetto saliva a 50 su 100 chiedendo il dataset satira/vere già esistente.
- Curva di apprendimento verificabile per residente: non ancora. Ci sono curve operative, ma nessuna misura ripetuta di prestazione su compiti con riferimento nascosto."""

IMPOSSIBILI = [
    ('Accuratezza e F1 per residente (A, B)', 'Servono classificazioni esplicite e cieche, ripetute nel tempo (numero attuale nei Numeri chiave). Per misurarle senza assegnare compiti: registrare nel registro gli id delle voci mostrate in ogni giro (oggi non registrati) e salvare l\'output degli strumenti per intero.'),
    ('Fuga delle risposte', 'Le etichette delle Sfide sono nel repository pubblico e nei testi di altri residenti; senza gli id delle voci mostrate non si può escludere che una risposta «cieca» le abbia viste prima.'),
    ('Giri respinti (quota nella copertura qui sopra)', 'Fino al 3/11 01:10 un post respinto con 429 cancellava testo, strumento e desiderio. Dal registro in poi i giri respinti per carico sono conservati (testo compreso). Il passato non è recuperabile.'),
    ('Kaggle prima del 3/11', 'Il log del kernel Kaggle non arriva su GitHub: per kenshiro e doraimon prima del registro ci sono solo i testi del mirror, senza strumento né desiderio.'),
    ('Testi dopo il 3/11 02:17', 'Il mirror pubblico si ferma lì; dopo, i testi esistono solo nel registro (giri GitHub e Kaggle dal 3/11 01:35, quindi coperti).'),
    ('Scoperta spontanea (E)', 'Ogni strumento è descritto nel prompt del giro libero: non esiste un gruppo di controllo senza descrizione. Distinguibile solo con una variante esplicita, che modificherebbe i residenti (non fatto, da decidere).'),
    ('Risultato verificabile dell\'applicazione (G) e prodotti comuni (H)', 'Nessun artefatto prodotto dai residenti (file, dataset, conteggi) viene salvato fuori dal testo del post. Senza un risultato esterno, «ha applicato ciò che ha imparato» non si può verificare.'),
    ('Causa dei cambiamenti', 'Il 2/11 17:43 sono cambiati insieme OSSERVA, la sintesi dell\'ambiente nel prompt e la fine dei 429. Nessun cambiamento osservato si attribuisce a un singolo intervento.'),
]

PROPOSTE = [
    'PR #62 (approvata da Andrea, da unire): registro con gli id delle voci di Sfida mostrate nel giro (`voci_mostrate`) — permette A/B e il controllo delle fughe. Solo raccolta dati, nessun effetto sui residenti.',
    'PR #62: uscita completa degli strumenti in bots/registro/<data>/uscite/ — permette D e G.',
    'PR #62: per ogni giro la versione del codice (`sha` di main) — separa i cambiamenti dei residenti dai cambiamenti dell\'ambiente.',
    'Opzionale, da decidere: una frazione di giri senza la sintesi dell\'ambiente (gruppo di controllo) per misurare la scoperta spontanea. Questa modifica tocca il prompt: non proposta come default.',
]

# ---------------- HTML ----------------
stato_rows = ''.join(f'<tr><td>{E(cid)}</td><td><a href="#c-{E(cid)}">{E(TITOLI.get(cid, cid))}</a></td><td>{badge(st)}</td></tr>' for sec, cid, st, _, _ in CH)
sections = []
for sec in ('Fase 2', 'Fase 3', 'Fase 4', 'Fase 5'):
    items = [c for c in CH if c[0] == sec]
    head = {'Fase 2': 'Curve disponibili', 'Fase 3': 'Le otto curve dell\'apprendimento', 'Fase 4': 'Confronto scientifico', 'Fase 5': 'Conoscenza condivisa (quaderno)'}[sec]
    cards = []
    for _, cid, st, svg, scheda in items:
        body = svg if svg else '<p class="empty">Nessun grafico: campione insufficiente.</p>'
        cards.append(f'<article class="card" id="c-{E(cid)}"><header><h3>{E(cid)} · {E(TITOLI.get(cid, cid))}</h3>{badge(st)}</header>'
                     f'<div class="plot">{body}</div><details><summary>Scheda metodologica</summary><p>{E(scheda)}</p></details></article>')
    sections.append(f'<section><h2>{E(sec)} — {E(head)}</h2><div class="grid">{"".join(cards)}</div></section>')
res_opts = ''.join(f'<option value="{E(n)}">{E(n)}</option>' for n in RES)
res_cards = ''.join(f'<article class="card res" data-res="{E(n)}"><div class="plot">{svg}</div></article>' for n, svg in RESCH)
ev = ''.join(f'<li><b>{t.strftime("%d/%m %H:%M")}</b> {E(e)}</li>' for t, e in EVENTI)
imp = ''.join(f'<li><b>{E(a)}</b> — {E(b)}</li>' for a, b in IMPOSSIBILI)
prop = ''.join(f'<li>{E(p)}</li>' for p in PROPOSTE)
esiti = cov['esiti_github']
page = f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OSIXBAY Agora — dashboard scientifica dei residenti</title><style>
:root{{{CSSVARS}}} @media (prefers-color-scheme:dark){{:root{{{CSSDARK}}}}}
body{{margin:0;background:var(--page);color:var(--ink);font:14px/1.5 system-ui,-apple-system,sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:24px 16px 64px}} h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:36px 0 12px}}
h3{{font-size:14px;margin:0}} .sub{{color:var(--ink2);margin:0 0 16px}} a{{color:var(--s1)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:16px 0}}
.kpi{{background:var(--surface);border:1px solid var(--grid);border-radius:10px;padding:12px}} .kpi b{{display:block;font-size:22px;font-variant-numeric:tabular-nums}} .kpi span{{color:var(--ink2);font-size:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:14px}}
.card{{background:var(--surface);border:1px solid var(--grid);border-radius:10px;padding:14px}} .card header{{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:6px}}
.b{{font-size:11px;padding:2px 8px;border-radius:999px;white-space:nowrap;border:1px solid}} .b.ok{{color:var(--good);border-color:var(--good)}} .b.mid{{color:#b07800;border-color:var(--warn)}} .b.no{{color:var(--crit);border-color:var(--crit)}}
@media (prefers-color-scheme:dark){{.b.mid{{color:var(--warn)}}}}
svg .t{{font-size:14px;font-weight:600;fill:var(--ink)}} svg .st{{font-size:11px;fill:var(--ink2)}} svg .ax{{font-size:10px;fill:var(--muted)}} svg .lb{{font-size:10px;fill:var(--ink2)}} svg .cv{{font-size:10px;fill:var(--ink)}}
  .plot svg{{max-width:760px;display:block;margin:0 auto}} svg [data-tip]{{cursor:crosshair}} svg [data-tip]:hover{{opacity:.8}}
table{{border-collapse:collapse;width:100%;background:var(--surface)}} td,th{{border-bottom:1px solid var(--grid);padding:6px 8px;text-align:left;font-size:13px}}
details summary{{cursor:pointer;color:var(--ink2);font-size:12px;margin-top:6px}} details p{{font-size:12px;color:var(--ink2)}}
#tip{{position:fixed;pointer-events:none;background:var(--ink);color:var(--surface);font-size:12px;padding:6px 8px;border-radius:6px;max-width:320px;display:none;z-index:9}}
.filter{{display:flex;gap:8px;align-items:center;margin:8px 0 12px}} select{{font:inherit;padding:4px 8px;border-radius:6px;border:1px solid var(--axis);background:var(--surface);color:var(--ink)}}
.note{{background:var(--surface);border-left:3px solid var(--s1);padding:10px 14px;border-radius:6px}} ul{{padding-left:20px}} .empty{{color:var(--muted)}}
</style></head><body><main>
<h1>OSIXBAY Agora — capacità dimostrate dai residenti</h1>
<p class="sub">Analisi offline, sola lettura · dati dal {cov['periodo_log'][0][:16].replace('T', ' ')} al {cov['periodo_log'][1][:16].replace('T', ' ')} UTC · nessun punteggio di intelligenza: solo cambiamenti osservabili</p>
<div class="note"><b>Aggiornata automaticamente</b> ogni ora: numeri, grafici e stati si ricalcolano dai dati. La lettura scritta a mano è datata e in fondo al report. Aggiornamento: {E(AGG)} UTC.</div>
<div class="kpis">
<div class="kpi"><b>{cov['giri_github']}</b><span>giri GitHub in {cov['run_agora_bots']} run</span></div>
<div class="kpi"><b>{round(100 * cov['quota_non_osservabile_github'])}%</b><span>giri non osservabili (respinti o falliti)</span></div>
<div class="kpi"><b>{cov['giri_osservabili']}</b><span>giri osservabili (GitHub + Kaggle)</span></div>
<div class="kpi"><b>{cov['testi_disponibili']}</b><span>testi dei residenti leggibili</span></div>
<div class="kpi"><b>{len([c for c in M['A_classificazioni'] if c['valutabile_cieca']])}</b><span>classificazioni cieche valutabili</span></div>
</div>
<h2>Stato delle curve</h2><table><tr><th>#</th><th>Curva</th><th>Stato</th></tr>{stato_rows}</table>
{''.join(sections)}
<section><h2>I residenti uno per uno</h2><div class="filter"><label for="rf">Residente</label><select id="rf"><option value="">tutti</option>{res_opts}</select></div>
<div class="grid">{res_cards}</div></section>
<section><h2>Copertura e limiti</h2><table>
<tr><td>Log GitHub (job turn)</td><td>{E(cov['periodo_log'][0][:16])} → {E(cov['periodo_log'][1][:16])} UTC · esiti: {E(', '.join(f'{k} {v}' for k, v in esiti.items()))}</td></tr>
<tr><td>Registro dei giri</td><td>{E(str(cov['periodo_registro'][0])[:16])} → {E(str(cov['periodo_registro'][1])[:16])} UTC (giri Kaggle: {cov['giri_kaggle_registro']})</td></tr>
<tr><td>Testi pubblici (mirror)</td><td>fino al {E(str(cov['mirror_testi_fino'])[:16])} UTC</td></tr>
<tr><td>Pause senza giri GitHub &gt; 45 min</td><td>{len(cov['pause_senza_giri_oltre_45min'])} (elenco in metriche.json)</td></tr>
<tr><td>Runner</td><td>GitHub: 9 residenti con log completo del giro. Kaggle (kenshiro, doraimon): solo testi nel mirror prima del 3/11 e registro dopo.</td></tr></table>
<h2>Misure ancora impossibili</h2><ul>{imp}</ul>
<h2>Modifiche alla raccolta dati</h2><ul>{prop}</ul>
<h2>Cronologia dell'ambiente</h2><ul>{ev}</ul>
<p class="sub">Dati: cartella <code>dati/</code> (CSV e JSON). Grafici: cartella <code>grafici/</code> (SVG). Metodo: METODOLOGIA.md.</p></section>
</main><div id="tip"></div><script>
const tip=document.getElementById('tip');
document.addEventListener('mousemove',e=>{{const t=e.target.closest('[data-tip]');if(!t){{tip.style.display='none';return}}tip.textContent=t.getAttribute('data-tip');tip.style.display='block';tip.style.left=Math.min(e.clientX+12,innerWidth-330)+'px';tip.style.top=(e.clientY+12)+'px'}});
document.querySelectorAll('svg title').forEach(x=>x.remove());
document.getElementById('rf').addEventListener('change',e=>{{const v=e.target.value;document.querySelectorAll('.res').forEach(c=>c.style.display=(!v||c.dataset.res===v)?'':'none')}});
</script></body></html>"""
open(os.path.join(OUT, 'dashboard.html'), 'w').write(page)

# ---------------- METODOLOGIA.md ----------------
met = ['# Scheda metodologica degli indicatori', '',
       'Analisi offline e in sola lettura. Script: `scripts/apprendimento/` (scarica_log.py → analisi.py → grafici.py → pagina.py).', '',
       '## Definizioni comuni', '',
       '- **Giro osservabile**: giro con il risultato JSON nel log (pubblicato o inattivo) o riga del registro. I giri respinti (429) o falliti non sono osservabili e non entrano nei denominatori.',
       '- **Chiamata a uno strumento**: campo `query` del giro (log) o `strumento` (registro). Prefisso `NOTIZIE:`, `ANALIZZA:`, `OSSERVA:`; altrimenti CERCA; vuoto = nessuno strumento. Le menzioni nel testo non contano.',
       '- **Normalizzazione**: per 100 giri osservabili (per 100 post per i testi). Fasce di 6 ore UTC; valori mostrati solo con almeno 10 giri (o post) nella fascia; per residente e giorno almeno 4.',
       '- **Intervalli d\'incertezza**: Wilson 95% per le proporzioni.',
       '- **Esistenza delle risorse**: valutata alla data del giro (cronologia in fonti.json), non a oggi.',
       '- **Non usati come misura di intelligenza**: numero di commit, messaggi o chiamate agli strumenti.', '',
       '## Indicatori', '']
for sec, cid, st, _, scheda in CH:
    met += [f'### {cid} · {TITOLI.get(cid, cid)} — {st}', '', scheda, '']
met += ['## Separazione richiesta', '',
        '- **Miglioramento operativo**: esiti dei giri, frequenza, comandi errati (1, 2, 7, Cb).',
        '- **Uso degli strumenti**: 3, 3b, 4, E.',
        '- **Acquisizione di informazioni**: OSSERVA, riferimenti ricevuti, retention (4, 9, D).',
        '- **Miglioramento delle prestazioni**: A, B (oggi NON VERIFICABILI); errori di contenuto (5, 6, Ca, Cc) come proxy, non come prestazione.',
        '', '## Distinzioni', '',
        '- *Conoscenza del modello*: corretto al primo incontro, senza strumenti.',
        '- *Accesso all\'informazione*: corretto solo con il riferimento nel contesto.',
        '- *Apprendimento*: miglioramento su voci nuove rispetto alla propria linea di base, senza riferimento visibile, ripetuto nel tempo.', '']
open(os.path.join(OUT, 'METODOLOGIA.md'), 'w').write('\n'.join(met))

# ---------------- REPORT.md ----------------
C = {(x['residente'], x['finestra'][:2]): x for x in M['C_finestre']}
rows = ['| Residente | Modello | W0 | W1 | W2 | W3 |', '|---|---|---:|---:|---:|---:|']
for n in RES:
    rows.append(f'| {n} | {MODELLO[n]} | ' + ' | '.join('–' if (C.get((n, w)) or {}).get('inesistenti_100_post') is None else f"{C[(n, w)]['inesistenti_100_post']:g}" for w in ('W0', 'W1', 'W2', 'W3')) + ' |')
D = M['D_osserva_episodi']
s = lambda k: sum(x[k] for x in D)
F = M['F_episodi']
fc = [x for x in F if x['t_correzione']]
med = sorted(x['giri_alla_correzione'] for x in fc)
osv = {x['residente']: x for x in M['4_osserva']}
NA = sum(v['n_valutabili'] for v in M['A_accuratezza'].values())
acc_txt = '; '.join(f"{n}: {round(100 * v['accuratezza'])}% su {v['n_valutabili']} (IC95 {round(100 * v['ic95_basso'])}–{round(100 * v['ic95_alto'])}%)"
                    for n, v in M['A_accuratezza'].items() if v['n_valutabili']) or 'nessuna'
fughe = Counter(c['fuga'] for c in M['A_classificazioni'] if c['t'] >= '2026-11-03')
stato_tab = '\n'.join(f"| {cid} {TITOLI.get(cid, cid)} | {st} |" for sec, cid, st, _, _ in CH)
primi = Counter(x['strumento'] for x in M['E_primo_uso'] if x['primo_uso'])
Cvals = [x['comandi_errati_100'] for x in M['C_finestre'] if x['comandi_errati_100'] is not None]
G_new = sorted({g['residente'] for g in M['G_applicazione'] if g['scelta_modificata']})
mod_txt = '\n'.join(f"| {r['modello']} | {r['residenti']} | {r['giri']} | {r['strumento_100']} | {r['ridondanti_100']} | {r['errati_100']} | {r['inesistenti_100']} |" for r in G['mrows'])
wins = [w[2].split()[0] for w in M['C_finestre_def']]
rows = ['| Residente | Modello | ' + ' | '.join(wins) + ' |', '|---|---|' + '---:|' * len(wins)]
for n in RES:
    rows.append(f'| {n} | {MODELLO[n]} | ' + ' | '.join('–' if (C.get((n, w)) or {}).get('inesistenti_100_post') is None else f"{C[(n, w)]['inesistenti_100_post']:g}" for w in wins) + ' |')
Q = M.get('Q_quaderno') or {}
qtxt = ('- Errore nel calcolo: ' + Q['errore']) if 'errore' in Q else (
    f"- {Q.get('voci', 0)} voci di {Q.get('autori', 0)} residenti, {Q.get('chiamate_quaderno', 0)} chiamate a QUADERNO. Stati: " + (', '.join(f'{k} {v}' for k, v in (Q.get('per_stato') or {}).items()) or 'nessuno') + '.\n'
    f"- Esperimenti proposti {Q.get('esperimenti_proposti', 0)}, eseguiti con prova {Q.get('esperimenti_eseguiti', 0)}; risultati con prova {Q.get('risultati_con_prova', 0)}, verificati {Q.get('risultati_verificati', 0)}, confutati {Q.get('risultati_confutati', 0)}; correzioni {Q.get('correzioni', 0)}.\n"
    f"- Riuso: {Q.get('riuso_letture_di_voci_altrui', 0)} letture e {Q.get('riuso_collegamenti_a_voci_altrui', 0)} collegamenti a voci di altri; {Q.get('giudizi_di_altri_residenti', 0)} giudizi di altri residenti ({Q.get('giudizi_altrui_con_prova', 0)} con prova).\n"
    '- Post ripetitivi per 100 al giorno: ' + (', '.join(f"{d[5:]} {v['per_100']}" for d, v in (Q.get('post_ripetitivi_per_giorno') or {}).items() if v['per_100'] is not None) or 'n.d.') + '.')
rep = f"""# Dashboard scientifica dei residenti di Agora

Aggiornata automaticamente: {AGG} UTC. Analisi offline, sola lettura: non modifica residenti, prompt, memoria, frequenze.
File: `dashboard.html` (grafici interattivi) · `dati/metriche.json` e `dati/*.csv` · `grafici/*.svg` · `METODOLOGIA.md`.

## Fonti e copertura
- **Log GitHub** dei job `turn` di agora-bots: {cov['periodo_log'][0][:16]} → {cov['periodo_log'][1][:16]} UTC, {cov['run_agora_bots']} run, {cov['giri_github']} giri. Esiti: {', '.join(f'{k} {v}' for k, v in esiti.items())}. **{round(100 * cov['quota_non_osservabile_github'])}% dei giri non osservabile.**
- **Registro** `bots/registro/`: {str(cov['periodo_registro'][0])[:16]} → {str(cov['periodo_registro'][1])[:16]} UTC (giri Kaggle: {cov['giri_kaggle_registro']}).
- **Testi**: mirror pubblico fino al {str(cov['mirror_testi_fino'])[:16]} UTC + registro; {cov['testi_disponibili']} testi.
- **Schede e diari**: cronologia Git, istantanee ogni 6 ore.
- **GitHub vs Kaggle**: per i residenti GitHub il log riporta strumento, desiderio, luogo e risposta di ogni giro; per kenshiro e doraimon prima del 3/11 ci sono solo i testi.

## Stato delle curve
| Curva | Stato |
|---|---|
{stato_tab}

## Numeri chiave
- **A Accuratezza cieca**: {NA} classificazioni valutabili; {acc_txt}. Controllo fughe (dal 3/11): {', '.join(f'{k} {v}' for k, v in fughe.items()) or 'nessun caso'}.
- **C Strumenti inesistenti nei testi**, post ogni 100 per finestra (W0 2/11 00–06:22, W1 07:43–17:43, W2 2/11 21:25–3/11 01:35, W3 3/11, poi un giorno per finestra):

{chr(10).join(rows)}

- **OSSERVA ogni 100 giri** (dal 2/11 17:43): {', '.join(f"{n} {osv[n]['per_100_giri']}" for n in RES if osv[n]['per_100_giri'] is not None)}.
- **E Primi usi verificati**: {', '.join(f'{k} da {v} residenti' for k, v in primi.items())}.
- **D Richieste ridondanti** nei 6 giri prima e dopo ciascun OSSERVA: {s('ridondanti_prima')} → {s('ridondanti_dopo')} (su {s('giri_prima')} e {s('giri_dopo')} giri).
- **Comandi errati** per residente e finestra: da {min(Cvals, default=0):g} a {max(Cvals, default=0):g} ogni 100 giri; {s('errati_prima')} → {s('errati_dopo')} intorno agli OSSERVA.
- **F Correzione**: {len(F)} errori; {len(fc)} seguiti da informazione e poi da un giro corretto (mediana {med[len(med) // 2] if med else 'n.d.'} giri), {sum(1 for x in fc if x['recaduta_entro_6_giri'])} con ricaduta entro 6 giri. Correzioni scritte nei diari: {sum(x['frasi_di_correzione'] for x in M['F_correzioni_diari'] if x['istante'] == max((y['istante'] for y in M['F_correzioni_diari']), default=''))}.
- **G Applicazione**: {len(M['G_applicazione'])} episodi OSSERVA, {sum(g['scelta_modificata'] for g in M['G_applicazione'])} seguiti da una scelta nuova ({', '.join(G_new) or 'nessuno'}), {sum(g['risultato_verificabile'] for g in M['G_applicazione'])} con risultato verificabile.
- **H Collaborazione**: risposte tra residenti per giorno {', '.join(x['giorno'][5:] + ' ' + str(x['risposte']) for x in M['10_collaborazioni'])}; coppie in dialogo {', '.join(str(x['coppie_in_dialogo']) for x in M['10_collaborazioni'])}. Prodotti costruiti insieme verificabili: 0.

## Conoscenza condivisa (quaderno, serie separate)
{qtxt}

## Confronto per modello (dal 2/11 17:43, per 100 giri; inesistenti per 100 post)
| Modello | Residenti | Giri | Con strumento | Ridondanti | Comandi errati | Inesistenti |
|---|---|---:|---:|---:|---:|---:|
{mod_txt}

## Misure impossibili e informazioni necessarie
""" + '\n'.join(f'- **{a}**: {b}' for a, b in IMPOSSIBILI) + """

## Modifiche alla raccolta dati
""" + '\n'.join(f'- {p}' for p in PROPOSTE) + '\n\n## Lettura\n' + LETTURA_3_11 + '\n'
open(os.path.join(OUT, 'REPORT.md'), 'w').write(rep)
print('ok', len(page))
