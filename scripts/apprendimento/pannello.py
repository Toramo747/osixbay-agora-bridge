"""Porta la dashboard di apprendimento nel pannello /admin del sito (tema Agora).

Scrive solo dentro theme/: SVG in theme/assets/apprendimento/ e la sezione di admin.mustache tra i marcatori
<!--apprendimento--> e <!--/apprendimento-->. Niente script, niente risorse esterne: immagini SVG dello stesso sito.
Uso: python3 scripts/apprendimento/pannello.py --out <cartella di analisi.py/grafici.py> --theme theme
"""
import argparse, html, os, pickle, re, shutil
from datetime import datetime, timezone

P = argparse.ArgumentParser()
P.add_argument('--out', required=True)
P.add_argument('--theme', default='theme')
A = P.parse_args()
E = html.escape
OUT, TH = os.path.abspath(A.out), os.path.abspath(A.theme)
G = pickle.load(open(os.path.join(OUT, '.grafici.pkl'), 'rb'))
S = pickle.load(open(os.path.join(OUT, '.stato.pkl'), 'rb'))
CH, RESCH, RES = G['CH'], G['RESCH'], S['RES']
DEST = os.path.join(TH, 'assets', 'apprendimento')
shutil.rmtree(DEST, ignore_errors=True)
os.makedirs(DEST)
NOW = datetime.now(timezone.utc)


def clean(svg):
    """Immagine statica: via tooltip e attributi data-* (nel pannello sono <img>), sfondo chiaro fisso."""
    svg = re.sub(r'\sdata-tip="[^"]*"', '', svg)
    svg = re.sub(r'<title>.*?</title>', '', svg, flags=re.S)
    return svg


files = {}
for f in sorted(os.listdir(os.path.join(OUT, 'grafici'))):
    if f.endswith('.svg') and re.fullmatch(r'[A-Za-z0-9_.-]+', f):
        files[f[:-4]] = clean(open(os.path.join(OUT, 'grafici', f)).read())
        open(os.path.join(DEST, f), 'w').write(files[f[:-4]])

# riquadro di stato: aggiornamento, copertura, stato delle curve
cov = S['M']['copertura']
COL = {'ok': '#0ca30c', 'mid': '#b07800', 'no': '#d03b3b'}
titoli = {}
for _, cid, st, svg, _ in CH:
    m = re.search(r'aria-label="([^"]*)"', svg or '')
    titoli[cid] = html.unescape(m.group(1)) if m else cid
rows = []
for i, (_, cid, st, _, _) in enumerate(CH):
    k = 'ok' if st.startswith('DISPONIBILE') else ('mid' if st.startswith('PARZIALE') else 'no')
    y = 104 + i * 20
    rows.append(f'<text x="16" y="{y}" class="cv">{E(cid)}</text><text x="52" y="{y}" class="lb">{E(titoli[cid][:62])}</text>'
                f'<text x="744" y="{y}" text-anchor="end" style="fill:{COL[k]};font-weight:600" class="lb">{E(st)}</text>')
h = 120 + len(CH) * 20
stato = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 {h}" width="100%" role="img" aria-label="Stato delle curve">'
         '<style>svg{font-family:system-ui,sans-serif;background:#fcfcfb}.t{font-size:15px;font-weight:600;fill:#0b0b0b}.st{font-size:11px;fill:#52514e}'
         '.lb{font-size:11px;fill:#52514e}.cv{font-size:11px;fill:#0b0b0b;font-weight:600}</style>'
         f'<text x="16" y="24" class="t">Stato delle curve · aggiornato {NOW:%d/%m %H:%M} UTC</text>'
         f'<text x="16" y="44" class="st">Giri GitHub {cov["giri_github"]} ({round(100 * cov["quota_non_osservabile_github"])}% non osservabili) · '
         f'giri osservabili {cov["giri_osservabili"]} · testi {cov["testi_disponibili"]}</text>'
         f'<text x="16" y="62" class="st">Log {cov["periodo_log"][0][:10]} → {cov["periodo_log"][1][:16].replace("T", " ")} · registro dal {str(cov["periodo_registro"][0])[:16].replace("T", " ")}</text>'
         '<line x1="16" x2="744" y1="80" y2="80" stroke="#e1e0d9"/>' + ''.join(rows) + '</svg>')
open(os.path.join(DEST, 'stato.svg'), 'w').write(stato)

# sezione del pannello (deterministica, tranne il parametro di versione delle immagini)
v = NOW.strftime('%Y%m%d%H')


def img(name, alt):
    return f'<img src="/theme/assets/apprendimento/{name}.svg?v={v}" alt="{E(alt)}" loading="lazy">'


fase = {'Fase 2': 'Curve disponibili', 'Fase 3': 'Le otto curve dell\'apprendimento', 'Fase 4': 'Confronto per modello', 'Fase 5': 'Conoscenza condivisa'}
parts = ['<!--apprendimento--><h2>Evoluzione dei residenti</h2>',
         '<p>Dashboard scientifica, aggiornata ogni ora dai registri dei giri. Misura cambiamenti osservabili, non punteggi di intelligenza. '
         'Ogni curva è DISPONIBILE, PARZIALE o NON VERIFICABILE; il metodo è in scripts/apprendimento/ del repository.</p>',
         f'<div class="learn-status">{img("stato", "Stato delle curve")}</div>']
for sec in ('Fase 2', 'Fase 3', 'Fase 4', 'Fase 5'):
    items = []
    for sez, cid, st, svg, _scheda in CH:
        if sez != sec or not svg:
            continue
        name = {'1': '01-esiti', '2': '02-frequenza', '3': '03a-strumenti-conteggi', '3b': '03b-strumenti-per100', '4': '04-osserva',
                '5': '05-ridondanti', '6': '06a-inesistenti-testi', '6b': '06b-inesistenti-schede', '7': '07-comandi-errati',
                '8': '08-luoghi', '9': '09-riferimenti', '10': '10-collaborazioni', 'A': 'A-accuratezza', 'Ca': 'C-a-ridondanti_100',
                'Cb': 'C-b-comandi_errati_100', 'Cc': 'C-c-inesistenti_100_post', 'D': 'D-retention', 'E': 'E-primo-uso',
                'F': 'F-correzione', 'G': 'G-applicazione', 'H': 'H-rete', 'M': 'M-modelli', 'Q': 'Q-quaderno', 'Qr': 'Q-ripetitivi'}.get(cid)
        if name in files:
            items.append(f'<figure>{img(name, titoli[cid])}<figcaption>{E(cid)} · {E(st)}</figcaption></figure>')
    parts.append(f'<details class="learn-block"{" open" if sec == "Fase 3" else ""}><summary>{E(sec)} · {E(fase[sec])}</summary>'
                 f'<div class="learn-grid">{"".join(items)}</div></details>')
res_items = ''.join(f'<figure>{img("residente-" + n, n)}<figcaption>{E(n)}</figcaption></figure>' for n, _ in RESCH if 'residente-' + n in files)
parts.append(f'<details class="learn-block"><summary>I residenti uno per uno</summary><div class="learn-grid">{res_items}</div></details><!--/apprendimento-->')
block = ''.join(parts)

adm_path = os.path.join(TH, 'admin.mustache')
adm = open(adm_path).read()
if '<!--apprendimento-->' in adm:
    adm = re.sub(r'<!--apprendimento-->.*?<!--/apprendimento-->', lambda m: block, adm, flags=re.S)
else:
    adm = adm.replace('<h1>{{title}}</h1>', '<h1>{{title}}</h1>' + block, 1)
open(adm_path, 'w').write(adm)

css_path = os.path.join(TH, 'css', 'agora.css')
css = open(css_path).read()
RULES = ('/* apprendimento */.learn-status img,.learn-grid img{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:8px;background:#fcfcfb}'
         '.learn-block{margin:14px 0}.learn-block summary{cursor:pointer;font-weight:600;padding:8px 0}'
         '.learn-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-top:8px}'
         '.learn-grid figure{margin:0}.learn-grid figcaption{font-size:10px;color:var(--muted);margin-top:4px}/* /apprendimento */')
css = re.sub(r'/\* apprendimento \*/.*?/\* /apprendimento \*/', '', css, flags=re.S).rstrip('\n') + '\n' + RULES + '\n'
open(css_path, 'w').write(css)
print('pannello:', len(files), 'grafici +', 'stato.svg', '·', sum(len(x) for x in files.values()) // 1024, 'kB')
