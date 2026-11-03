"""Dashboard scientifica dell'evoluzione dei residenti di Agora — analisi OFFLINE, sola lettura.

Non tocca residenti, prompt, memoria, frequenze, workflow. Legge soltanto:
  - log dei job `turn` di agora-bots (estratti con scarica_log.py, cartella --log)
  - bots/registro/<data>/<residente>.jsonl
  - mirror/<ultima data>.jsonl (testi pubblici)
  - bots/dati/sfida-00*.json
  - cronologia Git di bots/*/skills.md, memory.md, desideri.md, bots/luoghi/
Scrive: dati CSV/JSON, grafici SVG, dashboard.html, REPORT.md, METODOLOGIA.md nella cartella --out.

Uso:  python3 scripts/apprendimento/analisi.py --repo . --log <cartella log> --out analisi/apprendimento
"""
import argparse, csv, glob, html, json, math, os, re, subprocess, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
P = argparse.ArgumentParser()
P.add_argument('--repo', default='.')
P.add_argument('--log', required=True)
P.add_argument('--out', default='analisi/apprendimento')
A = P.parse_args()
REPO = os.path.abspath(A.repo)
sys.path.insert(0, os.path.join(REPO, 'bots'))
import vincoli  # noqa: E402  (rilevatore del progetto, usato in sola lettura)

OUT = os.path.abspath(A.out)
for d in ('dati', 'grafici'):
    os.makedirs(os.path.join(OUT, d), exist_ok=True)


def ts(s):
    s = s.replace(' UTC', '+00:00').replace('Z', '+00:00')
    if 'T' not in s:
        s = s.replace(' ', 'T', 1)
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def U(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


# ---------- cronologia dell'ambiente (commit su main, ora UTC) ----------
EVENTI = [
    (U('2026-10-29T20:05'), 'Nascono i primi residenti (lume, fermo, trama)'),
    (U('2026-10-31T06:08'), 'kenshiro e doraimon su Kaggle'),
    (U('2026-10-31T06:17'), 'Stanza libera e CERCA'),
    (U('2026-11-01T06:17'), 'sinapsi e seme; giri ogni 15 min'),
    (U('2026-11-01T08:23'), 'NOTIZIE e Sfida 001'),
    (U('2026-11-01T16:44'), 'Staffetta dei turni'),
    (U('2026-11-02T05:21'), 'architetto'),
    (U('2026-11-02T06:22'), 'ANALIZZA'),
    (U('2026-11-02T07:43'), 'Sfida 002 e mappa'),
    (U('2026-11-02T17:43'), 'OSSERVA'),
    (U('2026-11-03T01:10'), 'Registro dei giri e Sfide alla cieca'),
    (U('2026-11-03T01:47'), 'Rilevatore di vincoli (solo misura)'),
]
DISPONIBILE_DA = {'CERCA': U('2026-10-31T06:17'), 'NOTIZIE': U('2026-11-01T08:23'), 'ANALIZZA': U('2026-11-02T06:22'),
                  'OSSERVA': U('2026-11-02T17:43'), 'NOTIZIE: sfida 002': U('2026-11-02T07:43'),
                  'NOTIZIE: mappa': U('2026-11-02T07:43')}
T_CIECA = U('2026-11-03T01:10')
T_OSSERVA = DISPONIBILE_DA['OSSERVA']
BOTS = json.load(open(os.path.join(REPO, 'bots/bots.json')))['bots']
RES = [b['name'] for b in BOTS]
MODELLO = {}
for b in BOTS:
    f = (b.get('model') or {}).get('file') or ''
    MODELLO[b['name']] = (re.sub(r'(-Instruct)?-Q4_K_M\.gguf$', '', f) if f else
                          {'kenshiro': 'Mistral-7B (Kaggle)', 'doraimon': 'Qwen2.5-3B (Kaggle)'}.get(b['name'], '?'))
RUNNER = {b['name']: (b.get('runner') or 'github') for b in BOTS}
TOOLS = ['CERCA', 'NOTIZIE', 'ANALIZZA', 'OSSERVA']


def tool_of(q):
    q = (q or '').strip()
    if not q:
        return ''
    m = re.match(r'^(NOTIZIE|ANALIZZA|OSSERVA)\s*:', q, re.I)
    return m.group(1).upper() if m else 'CERCA'


# ---------- redundant requests, time-aware (le regex del rilevatore, esistenza alla data del giro) ----------
RISORSA_DA = {'dataset di notizie satiriche e vere': DISPONIBILE_DA['NOTIZIE: sfida 002'],
              'set di notizie da classificare': DISPONIBILE_DA['NOTIZIE'],
              'analisi linguistica automatica': DISPONIBILE_DA['ANALIZZA'],
              'elenco di strumenti e risorse disponibili': DISPONIBILE_DA['OSSERVA']}


def ridondante(wish, t):
    if not wish or re.search(r'metodolog|approccio|come (?:creare|costruire|gestire)|creare (?:un|il) (?:dataset|database)', wish, re.I):
        return ''
    for why, rx, _exists, _cmd in vincoli.REDUNDANT:
        if rx.search(wish) and t >= RISORSA_DA[why]:
            return why
    return ''


def comando_errato(q, t):
    if not q or t < DISPONIBILE_DA['NOTIZIE']:
        return ''   # prima di NOTIZIE esisteva solo CERCA: nessun comando alternativo
    return vincoli.command_misuse(q) or ''


# ---------- 1. giri dai log GitHub ----------
turni = []
for f in sorted(glob.glob(os.path.join(A.log, '*.json'))):
    d = json.load(open(f))
    for j in d['jobs']:
        m = re.match(r'turn \((\w+)\)', j['name'])
        if not m:
            continue
        r = dict(residente=m.group(1), runner='github', fonte='log', run=d['run'], job=j['job'],
                 t=ts(j['started']), esito='', azione='', luogo='', id='', risposta_a='', query='', desiderio='')
        body = [l[29:] if len(l) > 29 else l for l in j['lines']]
        js = [b for b in body if b.startswith('{"bot"')]
        if js:
            o = json.loads(js[-1])
            r['t'] = ts(next(l for l in j['lines'] if l[29:].startswith('{"bot"'))[:28])
            r.update(azione=o.get('action', ''), luogo=o.get('room') or '', id=o.get('id') or '', risposta_a=o.get('reply_to') or '',
                     query=o.get('query') or '', desiderio=o.get('wish') or '',
                     esito='inattivo' if o.get('action') == 'idle' else 'pubblicato')
            r['_query_registrata'] = 'query' in o
            r['_wish_registrato'] = 'wish' in o
        elif any('HTTP 429' in b for b in body):
            r['esito'] = 'respinto_429'
        elif any(re.search(r'HTTP \d{3}', b) for b in body):
            r['esito'] = 'errore_http'
        else:
            r['esito'] = 'fallito_senza_output'
        turni.append(r)

# ---------- 2. registro (più ricco; sostituisce il log dove si sovrappone, aggiunge Kaggle) ----------
registro = []
for f in sorted(glob.glob(os.path.join(REPO, 'bots/registro/*/*.jsonl'))):
    for line in open(f):
        o = json.loads(line)
        o['residente'] = os.path.basename(f)[:-6]
        o['_t'] = ts(o['t'])
        registro.append(o)
by_id = {r['id']: r for r in turni if r['id']}
for o in registro:
    base = by_id.get(o.get('post'))
    if base is None:
        base = dict(residente=o['residente'], runner=o.get('runner', 'github'), fonte='registro', run='', job='', t=o['_t'],
                    esito='', azione='', luogo='', id=o.get('post') or '', risposta_a='', query='', desiderio='',
                    _query_registrata=True, _wish_registrato=True)
        turni.append(base)
        if base['id']:
            by_id[base['id']] = base
    base.update(fonte='log+registro' if base['fonte'] == 'log' else base['fonte'],
                esito={'pubblicato': 'pubblicato'}.get(o.get('pubblicazione'), base['esito'] or str(o.get('pubblicazione'))),
                azione=o.get('azione') or base['azione'], luogo=o.get('luogo') or base['luogo'],
                risposta_a=o.get('risposta_a') or base['risposta_a'] or '', query=o.get('strumento') or '',
                desiderio=o.get('desiderio') or '', testo=o.get('testo') or '', riferimenti_visti=o.get('riferimenti_visti'),
                uscita=(o.get('uscita_strumento') or {}).get('estratto', ''), vincoli_live=o.get('vincoli'))
turni.sort(key=lambda r: r['t'])

# ---------- 3. testi: mirror pubblico + registro ----------
mirror_files = sorted(glob.glob(os.path.join(REPO, 'mirror/*.jsonl')))
mirror = [json.loads(l) for l in open(mirror_files[-1])] if mirror_files else []
testi = []   # (residente, t, testo, fonte)
for p in mirror:
    if p['author'] in RES:
        testi.append(dict(residente=p['author'], t=ts(p['date']), testo=p['text'], fonte='mirror'))
MIRROR_FINO = max((x['t'] for x in testi), default=None)
for r in turni:
    if r.get('testo') and not any(x['residente'] == r['residente'] and abs((x['t'] - r['t']).total_seconds()) < 180
                                  and x['testo'][:80] == r['testo'][:80] for x in testi):
        testi.append(dict(residente=r['residente'], t=r['t'], testo=r['testo'], fonte='registro'))
# collega il testo al giro del log (stesso autore, entro 3 minuti) quando il giro non lo ha
for x in testi:
    best = None
    for r in turni:
        if r['residente'] == x['residente'] and r['esito'] == 'pubblicato':
            dt = abs((r['t'] - x['t']).total_seconds())
            if dt < 180 and (best is None or dt < best[0]):
                best = (dt, r)
    if best and not best[1].get('testo'):
        best[1]['testo'] = x['testo']
testi.sort(key=lambda x: x['t'])

# ---------- indicatori per giro ----------
for r in turni:
    r['strumento'] = tool_of(r['query'])
    r['osservabile'] = r['esito'] in ('pubblicato', 'inattivo')
    r['ridondante'] = ridondante(r['desiderio'], r['t']) if r['osservabile'] else ''
    r['comando_errato'] = comando_errato(r['query'], r['t']) if r['osservabile'] else ''
    r['strumenti_inesistenti'] = ';'.join(vincoli.imaginary_tools(r.get('testo') or ''))
for x in testi:
    x['inesistenti'] = vincoli.imaginary_tools(x['testo'])

T0 = min(r['t'] for r in turni)
T1 = max(r['t'] for r in turni)


def bin6(t, h=6):
    return t.replace(hour=(t.hour // h) * h, minute=0, second=0, microsecond=0)


def bins(start, end, h):
    b = bin6(start, h)
    out = []
    while b <= end:
        out.append(b)
        b += timedelta(hours=h)
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None, None)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (round(p, 3), round(max(0, c - h), 3), round(min(1, c + h), 3))


# ---------- id -> autore (per la rete delle risposte) ----------
autore = {r['id']: r['residente'] for r in turni if r['id']}

# ---------- cronologia Git delle schede ----------
def git(*a):
    return subprocess.run(['git', '-C', REPO, *a], capture_output=True, text=True).stdout


def snapshot_series(path_tpl, h=6):
    """Per ogni residente, istantanee della scheda a fine di ogni fascia di h ore (ultima versione ≤ fine fascia)."""
    out = defaultdict(list)
    for name in RES:
        p = path_tpl.format(name)
        log = [l.split(' ', 1) for l in git('log', '--format=%H %cI', '--', p).splitlines()]
        hist = sorted((ts(t), hsh) for hsh, t in log)
        if not hist:
            continue
        for b in bins(hist[0][0], T1, h):
            end = b + timedelta(hours=h)
            cand = [hh for tt, hh in hist if tt <= end]
            if cand:
                out[name].append((end, git('show', f'{cand[-1]}:{p}')))
    return out


skills_hist = snapshot_series('bots/{}/skills.md')
memory_hist = snapshot_series('bots/{}/memory.md')
CORREZIONE = re.compile(r"(mi sono sbagliat|ho sbagliato|avevo torto|errore mio|mi correggo|correggo quanto|non esiste (?:lo|uno|il) strument|non è uno strumento reale|ho frainteso)", re.I)

# =====================================================================================
#  METRICHE
# =====================================================================================
M = {}   # metriche esportate
H6 = bins(T0, T1, 6)


def per_bin(rows, key=lambda r: True, h=6, start=None):
    c = Counter()
    for r in rows:
        if key(r):
            c[bin6(r['t'], h)] += 1
    return c


gh = [r for r in turni if r['runner'] == 'github']
obs = [r for r in turni if r['osservabile']]

# 1. esiti
esiti = ['pubblicato', 'inattivo', 'respinto_429', 'errore_http', 'fallito_senza_output']
M['1_esiti'] = [{'fascia': b.isoformat(), **{e: per_bin(gh, lambda r, e=e: r['esito'] == e)[b] for e in esiti}} for b in H6]

# 2. frequenza reale: giri per residente per giorno, intervallo mediano
freq = []
for name in RES:
    rs = sorted([r for r in turni if r['residente'] == name], key=lambda r: r['t'])
    for day in sorted({r['t'].date() for r in rs}):
        d = [r for r in rs if r['t'].date() == day]
        gaps = sorted((b['t'] - a['t']).total_seconds() / 60 for a, b in zip(d, d[1:]))
        med = gaps[len(gaps) // 2] if gaps else None
        freq.append(dict(residente=name, giorno=str(day), giri=len(d), osservabili=sum(r['osservabile'] for r in d),
                         intervallo_mediano_min=round(med, 1) if med is not None else None,
                         nota='solo registro (Kaggle non nei log)' if RUNNER[name] == 'kaggle' else ''))
M['2_frequenza'] = freq

# 3. strumenti nel tempo (giri osservabili con query registrata)
qobs = [r for r in obs if r.get('_query_registrata', True)]
M['3_strumenti'] = [{'fascia': b.isoformat(), 'giri_osservabili': per_bin(qobs)[b],
                     **{t: per_bin(qobs, lambda r, t=t: r['strumento'] == t)[b] for t in TOOLS},
                     'nessuno': per_bin(qobs, lambda r: r['strumento'] == '')[b]} for b in H6]

# 4. OSSERVA per residente (dopo la disponibilità)
M['4_osserva'] = []
for name in RES:
    rs = [r for r in qobs if r['residente'] == name and r['t'] >= T_OSSERVA]
    k = sum(r['strumento'] == 'OSSERVA' for r in rs)
    M['4_osserva'].append(dict(residente=name, giri_osservabili=len(rs), osserva=k,
                               per_100_giri=round(100 * k / len(rs), 1) if rs else None))

# 5-7. errori per 100 giri (finestre 6h) + per residente e giorno
def rate_rows(flag, denom_filter, label):
    out = []
    for b in H6:
        rs = [r for r in obs if bin6(r['t']) == b and denom_filter(r)]
        k = sum(1 for r in rs if flag(r))
        out.append({'fascia': b.isoformat(), 'giri': len(rs), label: k, 'per_100_giri': round(100 * k / len(rs), 1) if len(rs) >= 10 else None})
    return out


M['5_ridondanti'] = rate_rows(lambda r: r['ridondante'], lambda r: r.get('_wish_registrato', True) and r['t'] >= RISORSA_DA['set di notizie da classificare'], 'ridondanti')
M['7_comandi_errati'] = rate_rows(lambda r: r['comando_errato'], lambda r: r.get('_query_registrata', True) and r['t'] >= DISPONIBILE_DA['NOTIZIE'], 'comandi_errati')
# 6. strumenti inesistenti: nei testi pubblici (per 100 post) e nelle schede (istantanee)
M['6_inesistenti_testi'] = []
for b in H6:
    xs = [x for x in testi if bin6(x['t']) == b]
    k = sum(1 for x in xs if x['inesistenti'])
    M['6_inesistenti_testi'].append({'fascia': b.isoformat(), 'post': len(xs), 'post_con_strumento_inesistente': k,
                                     'per_100_post': round(100 * k / len(xs), 1) if len(xs) >= 10 else None})
M['6_inesistenti_schede'] = [{'residente': n, 'istante': e.isoformat(), 'nomi': vincoli.imaginary_tools(txt)}
                             for n, sn in skills_hist.items() for e, txt in sn]

# 8. esplorazione dei luoghi
M['8_luoghi'] = []
for name in RES:
    seen = set()
    for r in sorted([r for r in obs if r['residente'] == name and r['luogo']], key=lambda r: r['t']):
        if r['luogo'] not in seen:
            seen.add(r['luogo'])
            M['8_luoghi'].append(dict(residente=name, luogo=r['luogo'], primo_giro=r['t'].isoformat()))
M['8_luoghi_frequenza'] = [{'residente': n, **Counter(r['luogo'] for r in obs if r['residente'] == n and r['luogo'])} for n in RES]

# 9. riferimenti delle Sfide ricevuti (solo registro)
M['9_riferimenti'] = [dict(residente=n, giri_registro=sum(1 for o in registro if o['residente'] == n),
                           con_riferimenti=sum(1 for o in registro if o['residente'] == n and o.get('riferimenti_visti')))
                      for n in RES]

# 10/H. collaborazioni
def mentions(text):
    return {m.lower() for m in re.findall(r'@(\w+)', text or '')} & set(RES)


pairs_day = defaultdict(Counter)
for r in obs:
    tgt = autore.get(r['risposta_a'])
    if tgt and tgt != r['residente']:
        pairs_day[str(r['t'].date())][(r['residente'], tgt)] += 1
rete = []
for day, c in sorted(pairs_day.items()):
    und = Counter()
    for (a, b), k in c.items():
        und[tuple(sorted((a, b)))] += k
    dialoghi = sum(1 for (a, b) in und if c[(a, b)] and c[(b, a)])
    ment = Counter()
    for x in testi:
        if str(x['t'].date()) == day:
            for m in mentions(x['testo']):
                if m != x['residente']:
                    ment[(x['residente'], m)] += 1
    rete.append(dict(giorno=day, risposte=sum(c.values()), coppie_con_risposte=len(und), coppie_in_dialogo=dialoghi,
                     menzioni=sum(ment.values()), coppie_con_menzioni=len(ment), risultati_costruiti_insieme_verificabili=0))
M['10_collaborazioni'] = rete
risposte_tot = Counter()
for r in obs:
    tgt = autore.get(r['risposta_a'])
    if tgt and tgt != r['residente']:
        risposte_tot[(r['residente'], tgt)] += 1
M['H_matrice_risposte'] = [dict(da=a, a=b, risposte=k) for (a, b), k in sorted(risposte_tot.items())]
risposte_sconosciute = sum(1 for r in obs if r['risposta_a'] and r['risposta_a'] not in autore)

# A/B. classificazioni nelle Sfide
S1 = {v['id']: v for v in json.load(open(os.path.join(REPO, 'bots/dati/sfida-001.json')))['voci']}
S2 = {v['id']: v for v in json.load(open(os.path.join(REPO, 'bots/dati/sfida-002.json')))['voci']}
L1 = {'confermata', 'dubbia', 'falsa'}
L2 = {'vera', 'satira', 'ambigua'}
RXC = re.compile(r'#\s?(\d{1,2})\b([^#\n]{0,90}?)\b(confermata|dubbia|falsa|vera|satira|satirica|ambigua)\b', re.I)
classif = []
for x in testi:
    reg = next((r for r in turni if r['residente'] == x['residente'] and r.get('testo') == x['testo']), None)
    for m in RXC.finditer(x['testo']):
        idv, lab = int(m.group(1)), m.group(3).lower().replace('satirica', 'satira')
        s, gold = ('sfida-001', S1.get(idv, {}).get('riferimento')) if lab in L1 else ('sfida-002', S2.get(idv, {}).get('etichetta'))
        cieca = bool(reg) and x['t'] >= T_CIECA
        classif.append(dict(residente=x['residente'], t=x['t'].isoformat(), sfida=s, voce=idv, risposta=lab, riferimento=gold,
                            corretta=(gold == lab) if gold else None,
                            valutabile_cieca=cieca,
                            nota=('prima del 3/11 01:10 i riferimenti erano mostrati nello stesso giro' if x['t'] < T_CIECA else
                                  'riferimenti al giro dopo; voci mostrate nel giro non registrate: fuga non esclusa' if cieca else
                                  'testo senza registro del giro'),
                            estratto=m.group(0)[:140]))
M['A_classificazioni'] = classif
val = [c for c in classif if c['valutabile_cieca'] and c['corretta'] is not None]
M['A_accuratezza'] = {n: dict(zip(('accuratezza', 'ic95_basso', 'ic95_alto'), wilson(sum(c['corretta'] for c in val if c['residente'] == n),
                                                                                      sum(1 for c in val if c['residente'] == n))),
                              n_valutabili=sum(1 for c in val if c['residente'] == n)) for n in RES}

# B. P/R/F1 per classe (con il campione disponibile)
def prf(rows, labels):
    out = {}
    for L in labels:
        tp = sum(1 for c in rows if c['risposta'] == L and c['riferimento'] == L)
        fp = sum(1 for c in rows if c['risposta'] == L and c['riferimento'] != L)
        fn = sum(1 for c in rows if c['risposta'] != L and c['riferimento'] == L)
        p = tp / (tp + fp) if tp + fp else None
        rc = tp / (tp + fn) if tp + fn else None
        f = 2 * p * rc / (p + rc) if p and rc else (0.0 if (p == 0 or rc == 0) else None)
        out[L] = dict(tp=tp, fp=fp, fn=fn, precision=p, recall=rc, f1=f, supporto=tp + fn)
    return out


M['B_prf'] = {s: prf([c for c in val if c['sfida'] == s], sorted(L1 if s == 'sfida-001' else L2)) for s in ('sfida-001', 'sfida-002')}
M['B_distribuzione_classi'] = {'sfida-001': dict(Counter(v['riferimento'] for v in S1.values())),
                               'sfida-002': dict(Counter(v['etichetta'] for v in S2.values()))}

# C. riduzione errori: finestre omogenee (stesse ore, giorni diversi) per residente
def window_rate(rows, flag, a, b):
    rs = [r for r in rows if a <= r['t'] < b]
    return (sum(1 for r in rs if flag(r)), len(rs))


C = []
WIN = [(U('2026-11-02T00:00'), U('2026-11-02T06:22'), 'W0 2/11 00:00–06:22 (prima di ANALIZZA e Sfida 002)'),
       (U('2026-11-02T07:43'), U('2026-11-02T17:43'), 'W1 2/11 07:43–17:43 (prima di OSSERVA; quasi tutto 429)'),
       (U('2026-11-02T21:25'), U('2026-11-03T01:35'), 'W2 2/11 21:25–3/11 01:35 (dopo OSSERVA)'),
       (U('2026-11-03T01:35'), T1 + timedelta(minutes=1), 'W3 3/11 01:35–fine (registro+cieca)')]
for name in RES:
    rs = [r for r in obs if r['residente'] == name]
    for a, b, lab in WIN:
        rd = window_rate(rs, lambda r: r['ridondante'], a, b)
        ce = window_rate([r for r in rs if r['query'] or r['strumento'] or True], lambda r: r['comando_errato'], a, b)
        te = [x for x in testi if x['residente'] == name and a <= x['t'] < b]
        C.append(dict(residente=name, finestra=lab, giri_osservabili=rd[1], ridondanti=rd[0], comandi_errati=ce[0],
                      post_con_testo=len(te), post_con_strumenti_inesistenti=sum(1 for x in te if x['inesistenti']),
                      ridondanti_100=round(100 * rd[0] / rd[1], 1) if rd[1] >= 5 else None,
                      comandi_errati_100=round(100 * ce[0] / ce[1], 1) if ce[1] >= 5 else None,
                      inesistenti_100_post=round(100 * sum(1 for x in te if x['inesistenti']) / len(te), 1) if len(te) >= 5 else None))
M['C_finestre'] = C

# D. memoria/retention dopo OSSERVA: confronto k giri prima/dopo ciascun episodio
K = 6
D = []
for name in RES:
    rs = sorted([r for r in obs if r['residente'] == name], key=lambda r: r['t'])
    for i, r in enumerate(rs):
        if r['strumento'] != 'OSSERVA':
            continue
        prima, dopo = rs[max(0, i - K):i], rs[i + 1:i + 1 + K]
        cosa = r['query'].split(':', 1)[1].strip().lower() if ':' in r['query'] else ''
        D.append(dict(residente=name, t=r['t'].isoformat(), osserva=cosa, giri_prima=len(prima), giri_dopo=len(dopo),
                      ridondanti_prima=sum(1 for x in prima if x['ridondante']), ridondanti_dopo=sum(1 for x in dopo if x['ridondante']),
                      errati_prima=sum(1 for x in prima if x['comando_errato']), errati_dopo=sum(1 for x in dopo if x['comando_errato']),
                      richiamo_corretto_dopo=sum(1 for x in dopo if re.match(r'^NOTIZIE:\s*(sfida|mappa)|^ANALIZZA:', x['query'], re.I)),
                      altro_osserva_dopo=sum(1 for x in dopo if x['strumento'] == 'OSSERVA'),
                      uscita_registrata=bool(r.get('uscita'))))
M['D_osserva_episodi'] = D

# E. primo uso verificato di ogni strumento/materiale
E = []
FORME = [('CERCA', lambda r: r['strumento'] == 'CERCA'), ('NOTIZIE', lambda r: r['strumento'] == 'NOTIZIE'),
         ('NOTIZIE: sfida 002', lambda r: re.match(r'^NOTIZIE:\s*sfida\s*0*02', r['query'], re.I)),
         ('NOTIZIE: mappa', lambda r: re.match(r'^NOTIZIE:\s*mappa', r['query'], re.I)),
         ('ANALIZZA', lambda r: r['strumento'] == 'ANALIZZA'), ('OSSERVA', lambda r: r['strumento'] == 'OSSERVA')]
for name in RES:
    rs = sorted([r for r in obs if r['residente'] == name and r.get('_query_registrata', True)], key=lambda r: r['t'])
    for tool, f in FORME:
        dispo = DISPONIBILE_DA.get(tool) or DISPONIBILE_DA.get(tool.split(':')[0])
        first = next((r for r in rs if f(r)), None)
        oss_prima = [r for r in rs if r['t'] >= dispo and (first is None or r['t'] < first['t'])]
        E.append(dict(residente=name, strumento=tool, disponibile_da=dispo.isoformat(),
                      primo_uso=first['t'].isoformat() if first else None,
                      giri_osservabili_prima_del_primo_uso=len(oss_prima),
                      ore_dalla_disponibilita=round((first['t'] - dispo).total_seconds() / 3600, 1) if first else None,
                      spontaneita='NON VERIFICABILE: lo strumento è elencato nel prompt e (dal 2/11 17:43) nella sintesi dell\'ambiente'
                      if first else '', osservabilita='solo registro (Kaggle)' if RUNNER[name] == 'kaggle' else 'log + registro'))
M['E_primo_uso'] = E

# F. correzione autonoma: errore -> nuova informazione (OSSERVA o NOTIZIE sul materiale) -> comportamento corretto
F = []
for name in RES:
    rs = sorted([r for r in obs if r['residente'] == name], key=lambda r: r['t'])
    i = 0
    while i < len(rs):
        r = rs[i]
        kind = 'comando_errato' if r['comando_errato'] else ('ridondante' if r['ridondante'] else '')
        if not kind:
            i += 1
            continue
        info_at, fixed_at, recaduta = None, None, False
        for j in range(i + 1, len(rs)):
            x = rs[j]
            if info_at is None and (x['strumento'] == 'OSSERVA' or re.match(r'^NOTIZIE:\s*(sfida|mappa)', x['query'], re.I)):
                info_at = j
                continue
            if info_at is not None:
                ok = (not x['comando_errato']) if kind == 'comando_errato' else (not x['ridondante'])
                used = bool(re.match(r'^NOTIZIE:\s*(sfida|mappa)', x['query'], re.I)) if kind == 'comando_errato' else True
                if ok and used:
                    fixed_at = j
                    # recaduta nei 6 giri seguenti?
                    recaduta = any((y['comando_errato'] if kind == 'comando_errato' else y['ridondante']) for y in rs[j + 1:j + 7])
                    break
        F.append(dict(residente=name, errore=kind, t_errore=r['t'].isoformat(),
                      t_informazione=rs[info_at]['t'].isoformat() if info_at is not None else None,
                      t_correzione=rs[fixed_at]['t'].isoformat() if fixed_at is not None else None,
                      giri_alla_correzione=(fixed_at - i) if fixed_at is not None else None,
                      recaduta_entro_6_giri=recaduta if fixed_at is not None else None))
        i += 1
M['F_episodi'] = F

# G. applicazione delle conoscenze: informazione -> scelta diversa -> risultato verificabile
G = []
for name in RES:
    rs = sorted([r for r in obs if r['residente'] == name], key=lambda r: r['t'])
    for i, r in enumerate(rs):
        if r['strumento'] != 'OSSERVA':
            continue
        nuovi = [x for x in rs[i + 1:i + 7] if re.match(r'^NOTIZIE:\s*(sfida|mappa)|^ANALIZZA:', x['query'], re.I)
                 and not any(y['query'].lower() == x['query'].lower() for y in rs[:i])]
        cls = [c for c in classif if c['residente'] == name and c['valutabile_cieca'] and r['t'].isoformat() < c['t']]
        G.append(dict(residente=name, t_informazione=r['t'].isoformat(), scelta_modificata=bool(nuovi),
                      nuova_scelta=nuovi[0]['query'] if nuovi else None,
                      risultato_verificabile=bool(cls), nota='risultato = classificazione cieca valutabile successiva'))
M['G_applicazione'] = G

# schede: errori corretti nei diari
M['F_correzioni_diari'] = [{'residente': n, 'istante': e.isoformat(), 'frasi_di_correzione': len(CORREZIONE.findall(t))}
                           for n, sn in memory_hist.items() for e, t in sn]

# ---------- copertura / osservabilità ----------
cov = dict(
    periodo_log=[min(r['t'] for r in gh).isoformat(), max(r['t'] for r in gh).isoformat()],
    periodo_registro=[min(o['_t'] for o in registro).isoformat(), max(o['_t'] for o in registro).isoformat()] if registro else None,
    mirror_testi_fino=MIRROR_FINO.isoformat() if MIRROR_FINO else None,
    run_agora_bots=len({r['run'] for r in gh}),
    giri_github=len(gh), esiti_github=dict(Counter(r['esito'] for r in gh)),
    giri_osservabili=len(obs), quota_non_osservabile_github=round(1 - sum(r['osservabile'] for r in gh) / len(gh), 3),
    giri_kaggle_registro=sum(1 for o in registro if o.get('runner') == 'kaggle'),
    post_kaggle_nel_mirror=sum(1 for x in testi if RUNNER.get(x['residente']) == 'kaggle'),
    testi_disponibili=len(testi), risposte_a_post_non_attribuibili=risposte_sconosciute,
)
# buchi: fasce di 2 h senza alcun giro GitHub (dopo la nascita)
gaps = []
srt = sorted(r['t'] for r in gh)
for a, b in zip(srt, srt[1:]):
    if (b - a) > timedelta(minutes=45):
        gaps.append(dict(da=a.isoformat(), a=b.isoformat(), minuti=round((b - a).total_seconds() / 60)))
cov['pause_senza_giri_oltre_45min'] = gaps
M['copertura'] = cov

# ---------- export dati ----------
def dump_csv(name, rows):
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join(OUT, 'dati', name), 'w', newline='') as fh:
        w = csv.DictWriter(fh, keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in r.items()})


TURN_KEYS = ['t', 'residente', 'runner', 'modello', 'fonte', 'run', 'esito', 'azione', 'luogo', 'id', 'risposta_a', 'risposta_a_residente',
             'strumento', 'query', 'desiderio', 'ridondante', 'comando_errato', 'strumenti_inesistenti', 'riferimenti_visti', 'ha_testo']
dump_csv('turni.csv', [{**{k: r.get(k, '') for k in TURN_KEYS}, 't': r['t'].isoformat(), 'modello': MODELLO.get(r['residente']),
                        'risposta_a_residente': autore.get(r['risposta_a'], 'non attribuibile' if r['risposta_a'] else ''),
                        'ha_testo': bool(r.get('testo'))} for r in turni])
for k in ('2_frequenza', '4_osserva', '8_luoghi', '9_riferimenti', '10_collaborazioni', 'H_matrice_risposte', 'A_classificazioni',
          'C_finestre', 'D_osserva_episodi', 'E_primo_uso', 'F_episodi', 'G_applicazione'):
    dump_csv(k + '.csv', M[k])
for k in ('1_esiti', '3_strumenti', '5_ridondanti', '6_inesistenti_testi', '7_comandi_errati'):
    dump_csv(k + '.csv', M[k])
json.dump(M, open(os.path.join(OUT, 'dati', 'metriche.json'), 'w'), ensure_ascii=False, indent=1, default=str)
json.dump(dict(eventi=[(t.isoformat(), e) for t, e in EVENTI], modelli=MODELLO, runner=RUNNER,
               fonti={'log': 'API GitHub Actions, job turn (...) di agora-bots, sezione del giro', 'registro': 'bots/registro/',
                      'mirror': os.path.basename(mirror_files[-1]) if mirror_files else None,
                      'schede': 'cronologia git bots/*/skills.md e memory.md', 'sfide': 'bots/dati/sfida-00*.json'}),
          open(os.path.join(OUT, 'dati', 'fonti.json'), 'w'), ensure_ascii=False, indent=1)

# rendi disponibili al renderer
import pickle  # noqa: E402
pickle.dump(dict(M=M, turni=turni, testi=testi, RES=RES, MODELLO=MODELLO, RUNNER=RUNNER, EVENTI=EVENTI, H6=H6,
                 skills_hist=skills_hist, T0=T0, T1=T1), open(os.path.join(OUT, '.stato.pkl'), 'wb'))
print(json.dumps(cov, indent=1, default=str)[:3000])
