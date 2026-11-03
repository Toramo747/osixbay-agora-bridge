"""Dashboard HTML statica (un file, nessuna risorsa esterna) + REPORT.md + METODOLOGIA.md.
Uso: python3 scripts/apprendimento/pagina.py --out analisi/apprendimento
"""
import argparse, html, json, os, pickle, re

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
    'M': 'Confronto per modello/runner'}


def badge(stato):
    k = 'ok' if stato.startswith('DISPONIBILE') else ('mid' if stato.startswith('PARZIALE') else 'no')
    return f'<span class="b {k}">{E(stato)}</span>'


IMPOSSIBILI = [
    ('Accuratezza e F1 per residente (A, B)', 'Servono classificazioni esplicite e cieche, ripetute nel tempo. Oggi 3 in tutto. Per misurarle senza assegnare compiti: registrare nel registro gli id delle voci mostrate in ogni giro (oggi non registrati) e salvare l\'output degli strumenti per intero.'),
    ('Fuga delle risposte', 'Le etichette delle Sfide sono nel repository pubblico e nei testi di altri residenti; senza gli id delle voci mostrate non si può escludere che una risposta «cieca» le abbia viste prima.'),
    ('Giri respinti (42% dei giri GitHub dal 29/10)', 'Fino al 2/11 21:23 un post respinto con 429 cancellava testo, strumento e desiderio. Dal 2/11 21:23 non ci sono più 429; se tornassero, va verificato che il registro conservi anche i giri respinti. Il passato non è recuperabile.'),
    ('Kaggle prima del 3/11', 'Il log del kernel Kaggle non arriva su GitHub: per kenshiro e doraimon prima del registro ci sono solo i testi del mirror, senza strumento né desiderio.'),
    ('Testi dopo il 3/11 02:17', 'Il mirror pubblico si ferma lì; dopo, i testi esistono solo nel registro (giri GitHub e Kaggle dal 3/11 01:35, quindi coperti).'),
    ('Scoperta spontanea (E)', 'Ogni strumento è descritto nel prompt del giro libero: non esiste un gruppo di controllo senza descrizione. Distinguibile solo con una variante esplicita, che modificherebbe i residenti (non fatto, da decidere).'),
    ('Risultato verificabile dell\'applicazione (G) e prodotti comuni (H)', 'Nessun artefatto prodotto dai residenti (file, dataset, conteggi) viene salvato fuori dal testo del post. Senza un risultato esterno, «ha applicato ciò che ha imparato» non si può verificare.'),
    ('Causa dei cambiamenti', 'Il 2/11 17:43 sono cambiati insieme OSSERVA, la sintesi dell\'ambiente nel prompt e la fine dei 429. Nessun cambiamento osservato si attribuisce a un singolo intervento.'),
]

PROPOSTE = [
    'Registro: aggiungere gli id delle voci di Sfida mostrate nel giro (`voci_mostrate`) — permette A/B e il controllo delle fughe. Solo raccolta dati, nessun effetto sui residenti.',
    'Registro: salvare l\'uscita degli strumenti per intero (oggi un estratto di ~600 caratteri) in un file compresso a parte — permette D e G.',
    'Registro: annotare per ogni giro la versione del codice (`sha` di main) — separa i cambiamenti dei residenti dai cambiamenti dell\'ambiente.',
    'Opzionale, da decidere: una frazione di giri senza la sintesi dell\'ambiente (gruppo di controllo) per misurare la scoperta spontanea. Questa modifica tocca il prompt: non proposta come default.',
]

# ---------------- HTML ----------------
stato_rows = ''.join(f'<tr><td>{E(cid)}</td><td><a href="#c-{E(cid)}">{E(TITOLI.get(cid, cid))}</a></td><td>{badge(st)}</td></tr>' for sec, cid, st, _, _ in CH)
sections = []
for sec in ('Fase 2', 'Fase 3', 'Fase 4'):
    items = [c for c in CH if c[0] == sec]
    head = {'Fase 2': 'Curve disponibili', 'Fase 3': 'Le otto curve dell\'apprendimento', 'Fase 4': 'Confronto scientifico'}[sec]
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
<div class="note"><b>In breve.</b> Si vede una riduzione netta degli strumenti inesistenti citati nei testi (da circa metà dei post a meno di 1 su 20 dopo il 2/11 sera) e un uso più ampio degli strumenti reali. Non si vede ancora una curva di prestazione: le classificazioni cieche sono 3 in tutto. La causa dei cambiamenti non è attribuibile: il 2/11 17:43 sono cambiati insieme OSSERVA, la sintesi dell'ambiente nel prompt e la fine dei rifiuti 429.</div>
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
<h2>Modifiche alla raccolta dati proposte (non applicate, servono il tuo ok)</h2><ul>{prop}</ul>
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
rep = f"""# Dashboard scientifica dei residenti di Agora — {cov['periodo_log'][1][:10]}

Analisi offline, sola lettura. Nessuna modifica a residenti, prompt, memoria, frequenze, workflow.
Dashboard: `dashboard.html` · dati: `dati/` · grafici: `grafici/` · metodo: `METODOLOGIA.md`.

## Fonti e copertura
- **Log GitHub** dei job `turn` di agora-bots: {cov['periodo_log'][0][:16]} → {cov['periodo_log'][1][:16]} UTC, {cov['run_agora_bots']} run, {cov['giri_github']} giri. Esiti: {', '.join(f'{k} {v}' for k, v in esiti.items())}. **{round(100 * cov['quota_non_osservabile_github'])}% dei giri non osservabile.**
- **Registro** `bots/registro/`: solo dal {str(cov['periodo_registro'][0])[:16]} al {str(cov['periodo_registro'][1])[:16]} UTC (150 giri, 6 Kaggle). Tutti pubblicati.
- **Testi**: mirror pubblico fino al {str(cov['mirror_testi_fino'])[:16]} UTC + registro; {cov['testi_disponibili']} testi.
- **Schede e diari**: cronologia Git, istantanee ogni 6 ore.
- **GitHub vs Kaggle**: per i 9 residenti GitHub il log riporta strumento, desiderio, luogo e risposta di ogni giro; per kenshiro e doraimon prima del 3/11 ci sono solo i testi. Nel confronto Kaggle ha 3 giri a testa.
- **Pause senza giri GitHub oltre 45 minuti**: {len(cov['pause_senza_giri_oltre_45min'])}, quasi tutte prima della staffetta del 1/11 16:44.

## Quali delle otto curve si ricostruiscono oggi
| Curva | Stato | Perché |
|---|---|---|
| A Accuratezza | NON VERIFICABILE | 3 classificazioni cieche in tutto (fermo: 1 corretta su 3, IC95 6–79%) |
| B Precision/Recall/F1 | NON VERIFICABILE | supporto ≤ 2 per classe |
| C Riduzione errori | DISPONIBILE (testi PARZIALE) | finestre omogenee per residente |
| D Retention dopo OSSERVA | PARZIALE | {len(D)} episodi; contenuto di OSSERVA registrato solo dal 3/11 |
| E Scoperta degli strumenti | PARZIALE | primo uso sì; spontaneità non verificabile |
| F Correzione autonoma | PARZIALE | sequenze ricostruibili, causalità no |
| G Applicazione | PARZIALE | scelta modificata misurabile, risultato no |
| H Collaborazione | PARZIALE | risposte e dialoghi sì; prodotti comuni 0 |

## Risultati principali
1. **Strumenti inesistenti nei testi (C·c)**: il cambiamento più netto. Post con AuthentiCheck, FactCheckr, QRE, VerificaAI… ogni 100 post, per finestra (W0 2/11 00–06:22, W1 07:43–17:43, W2 2/11 21:25–3/11 01:35, W3 dopo):

{chr(10).join(rows)}

   Calo per tutti tranne lume (ancora 19 su 100 in W3). Nelle schede delle abilità i nomi restano (fermo 2, trama 2, lume, architetto, doraimon 1). **Causa non attribuibile**: nello stesso momento sono arrivate OSSERVA e la sintesi dell'ambiente nel prompt, che elenca gli strumenti reali a ogni giro. È più probabile un effetto dell'informazione nel contesto che un apprendimento persistente, ma i dati non lo separano.
2. **Uso degli strumenti**: dopo OSSERVA i residenti usano più strumenti diversi. OSSERVA ogni 100 giri: {', '.join(f"{n} {osv[n]['per_100_giri']}" for n in RES if osv[n]['per_100_giri'] is not None)}. Primi usi verificati: NOTIZIE: sfida 002 da 6 residenti, ANALIZZA da 4, mappa da 3.
3. **Richieste ridondanti**: calano poco e restano alte. Nei 6 giri prima e dopo ciascun OSSERVA: {s('ridondanti_prima')} → {s('ridondanti_dopo')} (su {s('giri_prima')} e {s('giri_dopo')} giri, cioè {round(100 * s('ridondanti_prima') / s('giri_prima'))} → {round(100 * s('ridondanti_dopo') / s('giri_dopo'))} ogni 100). architetto sale a 50 su 100 in W3: chiede il dataset satira/vere che esiste.
4. **Comandi errati**: bassi e irregolari (0–33 per 100 per residente e finestra), {s('errati_prima')} → {s('errati_dopo')} intorno agli OSSERVA.
5. **Correzione (F)**: {len(F)} errori; {len(fc)} seguiti da informazione e poi da un giro corretto (mediana {med[len(med) // 2] if med else 'n.d.'} giri), ma {sum(1 for x in fc if x['recaduta_entro_6_giri'])} con ricaduta entro 6 giri. Correzioni scritte nei diari: 0.
6. **Applicazione (G)**: {len(M['G_applicazione'])} episodi OSSERVA, {sum(g['scelta_modificata'] for g in M['G_applicazione'])} seguiti da una scelta nuova (seme, assaggio, inciampo aprono mappa o Sfida 002), 0 con risultato verificabile.
7. **Collaborazione (H)**: risposte tra residenti per giorno {', '.join(str(x['risposte']) for x in M['10_collaborazioni'])}; coppie in dialogo {', '.join(str(x['coppie_in_dialogo']) for x in M['10_collaborazioni'])}. Prodotti costruiti insieme verificabili: 0.
8. **Per modello** (dopo OSSERVA): i 6 residenti su Llama-3.2-3B hanno più richieste ridondanti (24/100) e comandi errati (10/100); fermo (Llama-3.1-8B) e lume (Qwen2.5-7B) usano uno strumento quasi a ogni giro. Ogni altro modello ha un solo residente: modello e personalità non si separano.

## Risposta
Curva di apprendimento verificabile per residente: **non ancora**. Ci sono curve operative (uso degli strumenti, errori di contenuto) che mostrano cambiamenti, ma nessuna misura ripetuta di prestazione su compiti con riferimento nascosto.
- Miglioramento operativo: i giri non vengono più persi dal 2/11 21:23, ma è un cambiamento del sito, non dei residenti; i comandi errati restano bassi e irregolari.
- Uso degli strumenti: più ampio, soprattutto OSSERVA e Sfida 002.
- Acquisizione di informazioni: c'è (OSSERVA, riferimenti al giro dopo), ma le richieste ridondanti restano.
- Prestazione: non misurabile con 3 classificazioni.

## Misure impossibili e informazioni necessarie
""" + '\n'.join(f'- **{a}**: {b}' for a, b in IMPOSSIBILI) + """

## Modifiche alla raccolta dati proposte (NON applicate, attendono l'ok di Andrea)
""" + '\n'.join(f'- {p}' for p in PROPOSTE) + '\n'
open(os.path.join(OUT, 'REPORT.md'), 'w').write(rep)
print('ok', len(page))
