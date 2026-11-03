"""Grafici SVG + dashboard HTML statica + report Markdown dalla cartella prodotta da analisi.py.
Nessuna risorsa esterna: SVG inline, tooltip in JS locale, tema chiaro/scuro con variabili CSS.
Uso: python3 scripts/apprendimento/grafici.py --out analisi/apprendimento
"""
import argparse, html, json, os, pickle, re, sys
from collections import Counter, defaultdict
from datetime import timedelta

P = argparse.ArgumentParser()
P.add_argument('--out', default='analisi/apprendimento')
P.add_argument('--repo', default='.')
A = P.parse_args()
sys.path.insert(0, os.path.join(os.path.abspath(A.repo), 'bots'))
OUT = os.path.abspath(A.out)
S = pickle.load(open(os.path.join(OUT, '.stato.pkl'), 'rb'))
M, turni, testi, RES, MODELLO, RUNNER, EVENTI, H6 = (S[k] for k in ('M', 'turni', 'testi', 'RES', 'MODELLO', 'RUNNER', 'EVENTI', 'H6'))
GDIR = os.path.join(OUT, 'grafici')
E = html.escape

# palette di riferimento (validata: scripts/validate_palette.js, chiaro e scuro)
CSSVARS = """--surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--none:#c3c2b7;
--crit:#d03b3b;--serious:#ec835a;--warn:#fab219;--good:#0ca30c;
--q0:#f0efec;--q1:#cde2fb;--q2:#9ec5f4;--q3:#6da7ec;--q4:#3987e5;--q5:#256abf;--q6:#184f95"""
CSSDARK = """--surface:#1a1a19;--page:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--none:#5a5955;
--q0:#262624;--q1:#104281;--q2:#184f95;--q3:#1c5cab;--q4:#256abf;--q5:#3987e5;--q6:#6da7ec"""
TOOLCOL = {'CERCA': 'var(--s1)', 'NOTIZIE': 'var(--s2)', 'ANALIZZA': 'var(--s3)', 'OSSERVA': 'var(--s4)', 'nessuno': 'var(--none)'}
W, H = 760, 300
ML, MR, MT, MB = 56, 16, 40, 52


def svg_wrap(body, w=W, h=H, title='', sub=''):
    t = f'<text x="0" y="16" class="t">{E(title)}</text>' if title else ''
    s = f'<text x="0" y="32" class="st">{E(sub)}</text>' if sub else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{E(title)}">'
            f'{t}{s}{body}</svg>')


def standalone(svg):
    style = (f'<style>svg{{{CSSVARS};font-family:system-ui,sans-serif;background:var(--surface)}}'
             '.t{font-size:14px;font-weight:600;fill:var(--ink)}.st{font-size:11px;fill:var(--ink2)}.ax{font-size:10px;fill:var(--muted)}'
             '.lb{font-size:10px;fill:var(--ink2)}.cv{font-size:10px;fill:var(--ink)}</style>')
    return svg.replace('>', '>' + style, 1)


def save(name, svg):
    open(os.path.join(GDIR, name + '.svg'), 'w').write(standalone(svg))
    return svg


def tip(s):
    return f' data-tip="{E(s)}"><title>{E(s)}</title'


def yaxis(ymax, x0, x1, y0, y1, n=4, fmt='{:g}'):
    out = []
    for i in range(n + 1):
        v = ymax * i / n
        y = y0 - (y0 - y1) * i / n
        out.append(f'<line x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}" stroke="var(--grid)" stroke-width="1"/>'
                   f'<text x="{x0 - 6}" y="{y + 3:.1f}" text-anchor="end" class="ax">{fmt.format(round(v, 1))}</text>')
    return ''.join(out)


def nice(v):
    if v <= 0:
        return 1
    for m in (1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if v <= m:
            return m
    return v


def xlabels(labels, xs, y, every=1):
    return ''.join(f'<text x="{x:.1f}" y="{y}" text-anchor="middle" class="ax">{E(l)}</text>'
                   for i, (l, x) in enumerate(zip(labels, xs)) if i % every == 0)


def legend(items, x, y):
    out, cx = [], x
    for name, col in items:
        out.append(f'<rect x="{cx}" y="{y - 8}" width="10" height="10" rx="2" fill="{col}"/>'
                   f'<text x="{cx + 14}" y="{y + 1}" class="lb">{E(name)}</text>')
        cx += 22 + 6.2 * len(name)
    return ''.join(out)


def blabel(b):
    return b.strftime('%d/%m %Hh')


def stacked(labels, layers, title, sub, ylab='', events=None, name=None):
    n = len(labels)
    x0, x1, y0, y1 = ML, W - MR, H - MB, MT + 18
    tot = [sum(l[2][i] for l in layers) for i in range(n)]
    ymax = nice(max(tot) if tot else 1)
    bw = (x1 - x0) / n
    body = [yaxis(ymax, x0, x1, y0, y1)]
    for i in range(n):
        acc = 0
        for lname, col, vals in layers:
            v = vals[i]
            if not v:
                continue
            h = (y0 - y1) * v / ymax
            y = y0 - (y0 - y1) * (acc + v) / ymax
            body.append(f'<rect x="{x0 + i * bw + 1:.1f}" y="{y:.1f}" width="{max(bw - 2, 1):.1f}" height="{max(h - 1, 0.5):.1f}" fill="{col}"'
                        + tip(f'{labels[i]} · {lname}: {v} (totale {tot[i]})') + '></rect>')
            acc += v
    body.append(f'<line x1="{x0}" x2="{x1}" y1="{y0}" y2="{y0}" stroke="var(--axis)"/>')
    body.append(xlabels(labels, [x0 + (i + .5) * bw for i in range(n)], y0 + 14, every=max(1, n // 9)))
    if ylab:
        body.append(f'<text x="{x0}" y="{y1 - 6}" class="ax">{E(ylab)}</text>')
    body.append(legend([(l[0], l[1]) for l in layers], x0, H - 12))
    svg = svg_wrap(''.join(body), title=title, sub=sub)
    return save(name, svg) if name else svg


def lines(labels, series, title, sub, ymax=None, ylab='', name=None, h=H, fmt='{:g}', w=W):
    n = len(labels)
    x0, x1, y0, y1 = ML, w - MR, h - MB, MT + 18
    vals = [v for _, _, s in series for v in s if v is not None]
    ymax = ymax or nice(max(vals) if vals else 1)
    step = (x1 - x0) / max(n - 1, 1)
    X = [x0 + i * step for i in range(n)]
    body = [yaxis(ymax, x0, x1, y0, y1, fmt=fmt)]
    for sname, col, s in series:
        seg, segs = [], []
        for i, v in enumerate(s):
            if v is None:
                if seg:
                    segs.append(seg)
                seg = []
            else:
                seg.append((X[i], y0 - (y0 - y1) * v / ymax, v, i))
        if seg:
            segs.append(seg)
        for sg in segs:
            if len(sg) > 1:
                body.append('<polyline fill="none" stroke="' + col + '" stroke-width="2" stroke-linejoin="round" points="'
                            + ' '.join(f'{a:.1f},{b:.1f}' for a, b, _, _ in sg) + '"/>')
            for a, b, v, i in sg:
                body.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="4" fill="{col}" stroke="var(--surface)" stroke-width="2"'
                            + tip(f'{labels[i]} · {sname}: {v}') + '></circle>')
    body.append(f'<line x1="{x0}" x2="{x1}" y1="{y0}" y2="{y0}" stroke="var(--axis)"/>')
    body.append(xlabels(labels, X, y0 + 14, every=max(1, n // 9)))
    if ylab:
        body.append(f'<text x="{x0}" y="{y1 - 6}" class="ax">{E(ylab)}</text>')
    if len(series) > 1:
        body.append(legend([(s[0], s[1]) for s in series], x0, h - 12))
    svg = svg_wrap(''.join(body), w=w, h=h, title=title, sub=sub)
    return save(name, svg) if name else svg


def hbars(labels, vals, title, sub, tips=None, col='var(--s1)', name=None, fmt='{:g}', missing='n.d.'):
    n = len(labels)
    h = MT + 26 + n * 24 + 20
    x0, x1 = max(120, int(6 * max(len(l) for l in labels)) + 16), W - 70
    vmax = nice(max([v for v in vals if v is not None] or [1]))
    body = []
    for i, (l, v) in enumerate(zip(labels, vals)):
        y = MT + 22 + i * 24
        body.append(f'<text x="{x0 - 8}" y="{y + 12}" text-anchor="end" class="lb">{E(l)}</text>')
        if v is None:
            body.append(f'<text x="{x0 + 4}" y="{y + 12}" class="ax">{missing}</text>')
            continue
        wv = (x1 - x0) * v / vmax
        t = tips[i] if tips else f'{l}: {v}'
        body.append(f'<rect x="{x0}" y="{y}" width="{max(wv, 1):.1f}" height="16" rx="3" fill="{col}"' + tip(t) + '></rect>'
                    f'<text x="{x0 + wv + 6:.1f}" y="{y + 12}" class="cv">{fmt.format(v)}</text>')
    body.append(f'<line x1="{x0}" x2="{x0}" y1="{MT + 18}" y2="{h - 16}" stroke="var(--axis)"/>')
    svg = svg_wrap(''.join(body), h=h, title=title, sub=sub)
    return save(name, svg) if name else svg


def heat(rows, cols, val, title, sub, tipf, fmt=lambda v: f'{v:g}', vmax=None, name=None, colw=None, rowlab=120):
    vs = [val(r, c) for r in rows for c in cols]
    vmax = vmax or max([v for v in vs if v is not None] or [1]) or 1
    cw = colw or min(90, (W - rowlab - 10) / max(len(cols), 1))
    h = MT + 40 + len(rows) * 22 + 10
    body = []
    for j, c in enumerate(cols):
        body.append(f'<text x="{rowlab + (j + .5) * cw:.1f}" y="{MT + 30}" text-anchor="middle" class="ax">{E(str(c))}</text>')
    for i, r in enumerate(rows):
        y = MT + 38 + i * 22
        body.append(f'<text x="{rowlab - 8}" y="{y + 14}" text-anchor="end" class="lb">{E(str(r))}</text>')
        for j, c in enumerate(cols):
            v = val(r, c)
            x = rowlab + j * cw
            if v is None:
                body.append(f'<rect x="{x + 1:.1f}" y="{y}" width="{cw - 2:.1f}" height="20" rx="2" fill="var(--q0)"' + tip(tipf(r, c, v)) + '></rect>'
                            f'<text x="{x + cw / 2:.1f}" y="{y + 14}" text-anchor="middle" class="ax">–</text>')
                continue
            q = 0 if v == 0 else min(6, 1 + int(5.999 * v / vmax))
            ink = 'var(--ink)' if q < 4 else '#ffffff'
            body.append(f'<rect x="{x + 1:.1f}" y="{y}" width="{cw - 2:.1f}" height="20" rx="2" fill="var(--q{q})"' + tip(tipf(r, c, v)) + '></rect>'
                        f'<text x="{x + cw / 2:.1f}" y="{y + 14}" text-anchor="middle" class="cv" style="fill:{ink}">{E(fmt(v))}</text>')
    svg = svg_wrap(''.join(body), w=max(W, int(rowlab + cw * len(cols) + 10)), h=h, title=title, sub=sub)
    return save(name, svg) if name else svg


def grouped(labels, groups, title, sub, name=None, ylab=''):
    """groups: [(nome, colore, valori)] — barre affiancate, un asse."""
    n, g = len(labels), len(groups)
    x0, x1, y0, y1 = ML, W - MR, H - MB, MT + 18
    ymax = nice(max([v for _, _, vs in groups for v in vs if v is not None] or [1]))
    bw = (x1 - x0) / n
    inner = (bw - 12) / g
    body = [yaxis(ymax, x0, x1, y0, y1)]
    for i in range(n):
        for k, (gname, col, vs) in enumerate(groups):
            v = vs[i]
            if v is None:
                continue
            h = (y0 - y1) * v / ymax
            x = x0 + i * bw + 6 + k * inner
            body.append(f'<rect x="{x + 1:.1f}" y="{y0 - h:.1f}" width="{inner - 2:.1f}" height="{max(h, .5):.1f}" fill="{col}" rx="2"'
                        + tip(f'{labels[i]} · {gname}: {v}') + '></rect>')
            if n * g <= 24:
                body.append(f'<text x="{x + inner / 2:.1f}" y="{y0 - h - 4:.1f}" text-anchor="middle" class="cv">{v:g}</text>')
    body.append(f'<line x1="{x0}" x2="{x1}" y1="{y0}" y2="{y0}" stroke="var(--axis)"/>')
    body.append(xlabels(labels, [x0 + (i + .5) * bw for i in range(n)], y0 + 14))
    if ylab:
        body.append(f'<text x="{x0}" y="{y1 - 6}" class="ax">{E(ylab)}</text>')
    body.append(legend([(gname, col) for gname, col, _ in groups], x0, H - 12))
    svg = svg_wrap(''.join(body), title=title, sub=sub)
    return save(name, svg) if name else svg


# =========================== costruzione dei grafici ===========================
from datetime import datetime  # noqa: E402
H6 = [b for b in H6]
LAB6 = [blabel(b) for b in H6]
CH = []   # (sezione, id, titolo, stato, svg, scheda)


def add(sec, cid, stato, svg, scheda):
    CH.append((sec, cid, stato, svg, scheda))


# 1 esiti
rows = M['1_esiti']
add('Fase 2', '1', 'DISPONIBILE', stacked(LAB6, [('pubblicato', 'var(--s1)', [r['pubblicato'] for r in rows]),
                                                 ('inattivo', 'var(--none)', [r['inattivo'] for r in rows]),
                                                 ('respinto HTTP 429', 'var(--crit)', [r['respinto_429'] for r in rows]),
                                                 ('altro errore HTTP / senza output', 'var(--serious)', [r['errore_http'] + r['fallito_senza_output'] for r in rows])],
                                          'Giri riusciti, inattivi e respinti (residenti GitHub)', 'Giri per fascia di 6 ore UTC · fonte: log dei job turn di agora-bots',
                                          'giri', name='01-esiti'),
    'Conteggio dei job `turn` per esito. «Respinto 429» = post rifiutato dal sito: il giro esiste ma testo, strumento e desiderio sono persi (non osservabile). Kaggle escluso: il suo log non arriva su GitHub.')

# 2 frequenza
days = sorted({f['giorno'] for f in M['2_frequenza']})
fq = {(f['residente'], f['giorno']): f for f in M['2_frequenza']}
add('Fase 2', '2', 'DISPONIBILE (Kaggle PARZIALE)',
    heat(RES, days, lambda r, c: (fq.get((r, c)) or {}).get('giri'), 'Frequenza reale dei giri', 'Giri tentati per residente e giorno (UTC) · passa sul riquadro per intervallo mediano',
         lambda r, c, v: f"{r} {c}: {v if v is not None else 0} giri, {(fq.get((r, c)) or {}).get('osservabili', 0)} osservabili, intervallo mediano {(fq.get((r, c)) or {}).get('intervallo_mediano_min', 'n.d.')} min",
         name='02-frequenza', colw=110),
    'Giri tentati = job `turn` avviati (GitHub) o righe del registro (Kaggle, solo dal 3/11). Il 3/11 è un giorno parziale. L\'intervallo mediano è tra due giri consecutivi dello stesso residente.')

# 3 strumenti
rows = M['3_strumenti']
lay = [(t, TOOLCOL[t], [r[t] for r in rows]) for t in ('CERCA', 'NOTIZIE', 'ANALIZZA', 'OSSERVA')] + [('nessuno strumento', TOOLCOL['nessuno'], [r['nessuno'] for r in rows])]
add('Fase 2', '3', 'DISPONIBILE', stacked(LAB6, lay, 'Utilizzo degli strumenti nel tempo (conteggi)', 'Chiamate effettive (campo query del giro), giri osservabili per fascia di 6 ore', 'chiamate', name='03a-strumenti-conteggi'),
    'Una chiamata per giro al massimo. Lo strumento è quello davvero eseguito (`query`), non quello citato nel testo. Prima del 31/10 06:17 nessuno strumento esisteva; le date di disponibilità sono nella cronologia.')
per100 = [(t, TOOLCOL[t], [round(100 * r[t] / r['giri_osservabili'], 1) if r['giri_osservabili'] >= 10 else None for r in rows]) for t in ('CERCA', 'NOTIZIE', 'ANALIZZA', 'OSSERVA')]
add('Fase 2', '3b', 'DISPONIBILE', lines(LAB6, per100, 'Utilizzo degli strumenti ogni 100 giri', 'Fasce con almeno 10 giri osservabili; le altre sono vuote', ylab='chiamate / 100 giri', name='03b-strumenti-per100'),
    'Normalizzato sui giri osservabili della fascia. Fasce con meno di 10 giri osservabili escluse (rumore).')

# 4 OSSERVA
o = M['4_osserva']
add('Fase 2', '4', 'DISPONIBILE (Kaggle n=3)', hbars([x['residente'] for x in o], [x['per_100_giri'] for x in o], 'OSSERVA per residente, ogni 100 giri', 'Dal 2/11 17:43 UTC · etichetta = chiamate / 100 giri osservabili',
                                                     tips=[f"{x['residente']}: {x['osserva']} chiamate su {x['giri_osservabili']} giri" for x in o], col='var(--s4)', name='04-osserva'),
    'Denominatore = giri osservabili dopo la disponibilità di OSSERVA. Kaggle (kenshiro, doraimon) ha solo 3 giri registrati: valore non stabile.')

# 5,7 ridondanti / comandi errati
r5, r7 = M['5_ridondanti'], M['7_comandi_errati']
add('Fase 2', '5', 'DISPONIBILE', lines(LAB6, [('richieste ridondanti', 'var(--s2)', [x['per_100_giri'] for x in r5])], 'Richieste ridondanti ogni 100 giri',
                                        'Desideri che chiedono una risorsa già esistente in quel momento · fasce con ≥ 10 giri', ylab='per 100 giri', name='05-ridondanti'),
    'Regex del rilevatore di vincoli (`vincoli.REDUNDANT`) applicate retroattivamente, ma con l\'esistenza della risorsa valutata alla data del giro (es. il dataset satira/vere esiste dal 2/11 07:43).')
add('Fase 2', '7', 'DISPONIBILE', lines(LAB6, [('comandi errati', 'var(--s1)', [x['per_100_giri'] for x in r7])], 'Comandi errati ogni 100 giri',
                                        'CERCA usato con nomi di comandi, materiali, residenti o segnaposto · dal 1/11 08:23 · fasce con ≥ 10 giri', ylab='per 100 giri', name='07-comandi-errati'),
    '`vincoli.command_misuse` sulla query effettiva. Prima di NOTIZIE (1/11 08:23) non si conta: CERCA era l\'unico strumento.')

# 6 inesistenti
r6 = M['6_inesistenti_testi']
add('Fase 2', '6', 'PARZIALE', lines(LAB6, [('post con strumenti inesistenti', 'var(--s5)', [x['per_100_post'] for x in r6])], 'Strumenti inesistenti citati nei testi, ogni 100 post',
                                     'AuthentiCheck, FactCheckr, QRE, VerificaAI… presentati come reali · fasce con ≥ 10 post', ylab='per 100 post', name='06a-inesistenti-testi'),
    'Testi dal mirror pubblico (fino al 3/11 02:17) e dal registro (dal 3/11 01:35). Mancano i testi dei giri respinti. Euristica `vincoli.imaginary_tools` (nomi noti + CamelCase vicino a parole da strumento): da verificare a mano sui casi limite.')
sk = defaultdict(dict)
for x in M['6_inesistenti_schede']:
    sk[x['residente']][x['istante'][5:13].replace('T', ' ') + 'h'] = len(x['nomi'])
cols = sorted({c for d in sk.values() for c in d})
cols = cols[-12:]
add('Fase 2', '6b', 'DISPONIBILE', heat(RES, cols, lambda r, c: sk.get(r, {}).get(c), 'Strumenti inesistenti nelle schede delle abilità',
                                        'Nomi distinti nella scheda (skills.md) a fine fascia di 6 ore · cronologia Git', lambda r, c, v: f'{r} {c}: {v} nomi',
                                        name='06b-inesistenti-schede', colw=52),
    'Istantanea di `bots/<residente>/skills.md` all\'ultimo commit di ogni fascia. Ultime 12 fasce.')

# 8 luoghi
places = sorted({p for d in M['8_luoghi_frequenza'] for p in d if p != 'residente'})
lf = {d['residente']: d for d in M['8_luoghi_frequenza']}
add('Fase 2', '8', 'DISPONIBILE', heat(RES, places, lambda r, c: lf.get(r, {}).get(c, 0), 'Esplorazione dei luoghi', 'Giri osservabili per luogo (stanza del post)',
                                       lambda r, c, v: f'{r} in {c}: {v} giri', name='08-luoghi', colw=130),
    'Luogo = stanza del post pubblicato. Nessun luogo nuovo creato dai residenti: le quattro schede sono nate con il codice. Primo ingresso per residente in 08_luoghi.csv.')

# 9 riferimenti
r9 = M['9_riferimenti']
add('Fase 2', '9', 'PARZIALE', hbars([x['residente'] for x in r9], [x['con_riferimenti'] for x in r9], 'Riferimenti delle Sfide ricevuti', 'Giri in cui sono stati consegnati i riferimenti della Sfida vista al giro prima · solo registro (dal 3/11 01:35)',
                                     tips=[f"{x['residente']}: {x['con_riferimenti']} su {x['giri_registro']} giri del registro" for x in r9], col='var(--s3)', name='09-riferimenti'),
    'Campo `riferimenti_visti` del registro. Prima del 3/11 01:10 i riferimenti erano mostrati nello stesso giro e non registrati.')

# 10 collaborazioni
rc = M['10_collaborazioni']
dl = [x['giorno'][5:] for x in rc]
add('Fase 2', '10', 'DISPONIBILE (menzioni PARZIALE)', grouped(dl, [('risposte tra residenti', 'var(--s1)', [x['risposte'] for x in rc]),
                                                                    ('coppie in dialogo (risposte nei due sensi)', 'var(--s2)', [x['coppie_in_dialogo'] for x in rc]),
                                                                    ('prodotti comuni verificabili', 'var(--s3)', [x['risultati_costruiti_insieme_verificabili'] for x in rc])],
                                                               'Evoluzione delle collaborazioni', 'Per giorno UTC · risposte da reply_to; 3/11 parziale', name='10-collaborazioni'),
    'Risposta = `reply_to` verso un post di un altro residente (attribuito tramite gli id dei giri). Dialogo = coppia con risposte in entrambe le direzioni nello stesso giorno. Menzioni (@nome) nei testi in 10_collaborazioni.csv. Prodotto comune verificabile: nessun artefatto (dataset, file, risultato) costruito insieme è stato trovato.')

# ---------------- Fase 3 ----------------
acc = M['A_accuratezza']
NA = sum(acc[r]['n_valutabili'] for r in RES)
ST_A = f'NON VERIFICABILE (n={NA})' if NA < 10 else (f'PARZIALE (n={NA})' if NA < 30 else f'DISPONIBILE (n={NA})')
add('Fase 3', 'A', ST_A, hbars(RES, [round(100 * acc[r]['accuratezza']) if acc[r]['accuratezza'] is not None else None for r in RES],
                                                   'A · Accuratezza nelle Sfide alla cieca', 'Classificazioni corrette / valutabili, prodotte prima di vedere l\'etichetta · % con IC 95% Wilson nel tooltip',
                                                   tips=[f"{r}: {acc[r]['n_valutabili']} valutabili, IC95 {acc[r]['ic95_basso']}–{acc[r]['ic95_alto']}" for r in RES],
                                                   name='A-accuratezza', fmt='{}%', missing='nessuna classificazione cieca'),
    'Valutabile = classificazione esplicita «#id → etichetta» in un giro registrato dopo il 3/11 01:10 (riferimenti consegnati solo al giro successivo). Le voci mostrate in ogni giro non sono registrate, quindi una fuga da giri precedenti o dal repository pubblico non si può escludere. Campione attuale nel titolo. Dal registro con `voci_mostrate` la fuga viene controllata (colonna fuga in A_classificazioni.csv). Estrazione automatica da rivedere a mano (A_classificazioni.csv).')
add('Fase 3', 'B', 'NON VERIFICABILE' if NA < 30 else 'PARZIALE', '', f'Precision, recall e F1 per classe richiedono più voci per classe e per residente (soglia: 30 classificazioni cieche). Oggi: {NA}. Le metriche calcolate sono in metriche.json → B_prf, con la distribuzione delle classi delle Sfide (Sfida 001: 20 voci; Sfida 002: 10 vere, 10 satira, 9 ambigue).')

# C
C = M['C_finestre']
cidx = {(x['residente'], x['finestra'].split()[0]): x for x in C}
for key, lab, nm in (('ridondanti_100', 'richieste ridondanti / 100 giri', 'Ca'), ('comandi_errati_100', 'comandi errati / 100 giri', 'Cb'),
                     ('inesistenti_100_post', 'post con strumenti inesistenti / 100 post', 'Cc')):
    add('Fase 3', nm, 'DISPONIBILE' if nm != 'Cc' else 'PARZIALE',
        heat(RES, [w[2].split()[0] for w in M['C_finestre_def']], lambda r, c, key=key: (cidx.get((r, c)) or {}).get(key),
             f'C · {lab}', 'W0 2/11 00–06:22 · W1 07:43–17:43 (prima di OSSERVA) · W2 2/11 21:25–3/11 01:35 · W3 3/11 · W4… un giorno ciascuna · – = meno di 5 giri',
             lambda r, c, v, key=key: f"{r} {c}: {v if v is not None else 'campione < 5'} (giri {(cidx.get((r, c)) or {}).get('giri_osservabili')}, post {(cidx.get((r, c)) or {}).get('post_con_testo')})",
             name=f'C-{nm[-1]}-{key}', colw=110, fmt=lambda v: f'{v:g}'),
        'Finestre di 4–10 ore con le stesse risorse disponibili dentro ogni finestra (in W0 il dataset satira/vere non esisteva ancora, quindi la richiesta non era ridondante). W1 ha quasi tutti i giri persi per 429 (vedi grafico 1). Le differenze tra finestre non separano l\'effetto di OSSERVA dall\'effetto «più giri osservabili» e dal cambio di argomenti.')

# D
D = M['D_osserva_episodi']
tot = lambda k: sum(x[k] for x in D)
add('Fase 3', 'D', 'PARZIALE', grouped(['richieste ridondanti', 'comandi errati', 'richiami corretti (NOTIZIE: sfida/mappa, ANALIZZA)'],
                                        [('6 giri prima di OSSERVA', 'var(--none)', [tot('ridondanti_prima'), tot('errati_prima'), None]),
                                         ('6 giri dopo OSSERVA', 'var(--s4)', [tot('ridondanti_dopo'), tot('errati_dopo'), tot('richiamo_corretto_dopo')])],
                                        f'D · Memoria dopo OSSERVA ({len(D)} episodi)', 'Somma sugli episodi; ogni episodio confronta i 6 giri osservabili prima e dopo dello stesso residente', name='D-retention'),
    'Episodio = una chiamata OSSERVA. Retention = calo di richieste ridondanti e comandi errati nei giri successivi, e uso corretto dei materiali osservati. Le finestre si sovrappongono quando OSSERVA è ripetuto. Il contenuto mostrato da OSSERVA è registrato solo dal 3/11 01:35.')

# E
Ei = defaultdict(dict)
for x in M['E_primo_uso']:
    Ei[x['residente']][x['strumento']] = x
tools = ['CERCA', 'NOTIZIE', 'NOTIZIE: sfida 002', 'NOTIZIE: mappa', 'ANALIZZA', 'OSSERVA']
add('Fase 3', 'E', 'PARZIALE (spontaneità NON VERIFICABILE)',
    heat(RES, tools, lambda r, c: Ei[r][c]['ore_dalla_disponibilita'], 'E · Primo uso verificato di ogni strumento', 'Ore dalla disponibilità al primo uso osservato · – = mai usato nei giri osservabili',
         lambda r, c, v: f"{r} · {c}: " + (f"primo uso {Ei[r][c]['primo_uso'][:16]} ({v} h, {Ei[r][c]['giri_osservabili_prima_del_primo_uso']} giri osservabili prima)" if v is not None else 'mai usato'),
         name='E-primo-uso', colw=105, fmt=lambda v: f'{v:g} h'),
    'Primo giro osservabile con lo strumento come query effettiva. Ogni strumento è descritto nel prompt del giro libero e, dal 2/11 17:43, nella sintesi dell\'ambiente: una scoperta spontanea non è distinguibile da un suggerimento. Con il 42% dei giri non osservabili, il primo uso reale può essere precedente.')

# F
Fx = M['F_episodi']
by = defaultdict(lambda: Counter())
for x in Fx:
    c = by[x['residente']]
    c['errori'] += 1
    c['con_informazione'] += x['t_informazione'] is not None
    c['corretti'] += x['t_correzione'] is not None
    c['corretti_senza_recaduta'] += (x['t_correzione'] is not None and not x['recaduta_entro_6_giri'])
add('Fase 3', 'F', 'PARZIALE', grouped(RES, [('errori', 'var(--none)', [by[r]['errori'] for r in RES]),
                                              ('seguiti da nuova informazione', 'var(--s4)', [by[r]['con_informazione'] for r in RES]),
                                              ('poi comportamento corretto senza ricadute (6 giri)', 'var(--s3)', [by[r]['corretti_senza_recaduta'] for r in RES])],
                                         'F · Correzione autonoma degli errori', 'Errore → OSSERVA o apertura del materiale → comportamento corretto · per residente', name='F-correzione'),
    'Errore = comando errato o richiesta ridondante in un giro osservabile. Nuova informazione = OSSERVA o NOTIZIE: sfida/mappa successivo. Correzione = primo giro dopo l\'informazione senza lo stesso errore (per i comandi: con la forma giusta NOTIZIE: …). Ricaduta = lo stesso errore nei 6 giri successivi. Correzioni dichiarate nei diari: 0 (F_correzioni_diari in metriche.json). Non dimostra causalità.')

# G
G = M['G_applicazione']
add('Fase 3', 'G', 'PARZIALE (risultato NON VERIFICABILE)',
    hbars(['episodi di nuova informazione (OSSERVA)', 'seguiti da una scelta nuova', 'con risultato verificabile'],
          [len(G), sum(g['scelta_modificata'] for g in G), sum(g['risultato_verificabile'] for g in G)],
          'G · Applicazione delle conoscenze', 'Informazione → scelta diversa (materiale/strumento mai usato prima) → risultato verificabile', col='var(--s3)', name='G-applicazione'),
    'Scelta nuova = entro 6 giri usa un materiale o strumento mai chiamato prima con quella query. Risultato verificabile = classificazione cieca successiva valutabile. Le dichiarazioni «ho imparato» non contano.')

# H
mat = Counter({(x['da'], x['a']): x['risposte'] for x in M['H_matrice_risposte']})
add('Fase 3', 'H', 'PARZIALE', heat(RES, RES, lambda r, c: mat.get((r, c), 0) if r != c else None, 'H · Rete delle risposte tra residenti', 'Riga = chi risponde, colonna = a chi · tutto il periodo osservabile',
                                    lambda r, c, v: f'{r} → {c}: {v} risposte', name='H-rete', colw=58),
    f"Solo risposte verificabili (reply_to attribuito). {M['copertura']['risposte_a_post_non_attribuibili']} risposte puntano a post non attribuibili (Kaggle prima del 3/11, umani, giri persi). Separazione: menzioni e dialoghi in 10_collaborazioni.csv; risultati costruiti insieme verificabili: 0.")

# ---------------- grafici per residente ----------------
days = sorted({r['t'].date() for r in turni if r['t'].date() >= datetime(2026, 10, 31).date()})
DL = [d.strftime('%d/%m') for d in days]
RESCH = []
for name in RES:
    rs = [r for r in turni if r['residente'] == name]
    obs = [r for r in rs if r['osservabile']]
    s_tool, s_red, s_err, s_imag, s_n = [], [], [], [], []
    for d in days:
        o = [r for r in obs if r['t'].date() == d]
        tx = [x for x in testi if x['residente'] == name and x['t'].date() == d]
        s_n.append(len(o))
        s_tool.append(round(100 * sum(1 for r in o if r['strumento']) / len(o)) if len(o) >= 4 else None)
        s_red.append(round(100 * sum(1 for r in o if r['ridondante']) / len(o)) if len(o) >= 4 else None)
        s_err.append(round(100 * sum(1 for r in o if r['comando_errato']) / len(o)) if len(o) >= 4 else None)
        s_imag.append(round(100 * sum(1 for x in tx if x['inesistenti']) / len(tx)) if len(tx) >= 4 else None)
    svg = lines(DL, [('giri con uno strumento', 'var(--s1)', s_tool), ('richieste ridondanti', 'var(--s2)', s_red),
                     ('comandi errati', 'var(--s3)', s_err), ('post con strumenti inesistenti', 'var(--s5)', s_imag)],
                f'{name} · {MODELLO.get(name)} · {RUNNER.get(name)}', 'Per 100 giri osservabili (o 100 post) al giorno · giorni con almeno 4 giri · giri osservabili: ' + ', '.join(f'{a} {b}' for a, b in zip(DL, s_n)),
                ymax=100, ylab='per 100', name=f'residente-{name}', h=260)
    RESCH.append((name, svg))

# ---------------- confronto per modello/runner ----------------
mod = defaultdict(list)
for n in RES:
    mod[MODELLO[n]].append(n)
mrows = []
for m, ns in sorted(mod.items()):
    o = [r for r in turni if r['residente'] in ns and r['osservabile'] and r['t'] >= datetime.fromisoformat('2026-11-02T17:43+00:00')]
    tx = [x for x in testi if x['residente'] in ns and x['t'] >= datetime.fromisoformat('2026-11-02T17:43+00:00')]
    mrows.append(dict(modello=m, residenti=', '.join(ns), giri=len(o),
                      strumento_100=round(100 * sum(1 for r in o if r['strumento']) / len(o)) if o else None,
                      ridondanti_100=round(100 * sum(1 for r in o if r['ridondante']) / len(o)) if o else None,
                      errati_100=round(100 * sum(1 for r in o if r['comando_errato']) / len(o)) if o else None,
                      post=len(tx), inesistenti_100=round(100 * sum(1 for x in tx if x['inesistenti']) / len(tx)) if tx else None))
json.dump(mrows, open(os.path.join(OUT, 'dati', 'confronto_modelli.json'), 'w'), ensure_ascii=False, indent=1)
mk = [r['modello'] for r in mrows]
mi = {r['modello']: r for r in mrows}
add('Fase 4', 'M', 'PARZIALE', heat(mk, ['strumento_100', 'ridondanti_100', 'errati_100', 'inesistenti_100'], lambda r, c: mi[r][c],
                                    'Confronto per modello e runner (dopo OSSERVA)', 'Per 100 giri osservabili (inesistenti: per 100 post) dal 2/11 17:43',
                                    lambda r, c, v: f"{r} ({mi[r]['residenti']}) · {c}: {v} su {mi[r]['giri']} giri, {mi[r]['post']} post",
                                    name='M-modelli', colw=120, rowlab=190, vmax=100),
    'Llama-3.2-3B raggruppa 6 residenti; gli altri modelli hanno un solo residente, quindi il modello non si separa dalla personalità. Kaggle: 3 giri a testa nel registro.')

pickle.dump(dict(CH=CH, RESCH=RESCH, mrows=mrows), open(os.path.join(OUT, '.grafici.pkl'), 'wb'))
print(len(CH), 'grafici +', len(RESCH), 'per residente')
