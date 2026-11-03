"""Rilevatore di vincoli, modalità SOLO MISURA: controlla un giro concluso e annota nel registro le violazioni
dei vincoli dell'ambiente. I residenti non lo vedono: niente entra nei loro prompt, diari o schede.

Controlli deterministici, ricavati dall'ambiente reale (knowledge.TOOLS, bots/dati/):
- strumento_inesistente: nel testo un nome di strumento presentato come reale ma assente dall'ambiente
  (es. AuthentiCheck, QRE). Euristica: nomi CamelCase o noti, fuori dalla lista dei nomi reali; i candidati
  vengono riportati così come trovati, per la verifica umana.
- richiesta_ridondante: un desiderio chiede una risorsa che esiste già (con il comando che la apre).
- comando_errato: CERCA chiamato con il nome di un comando, di un residente o con un segnaposto (<cosa>).
- copia_riferimenti: il testo riprende alla lettera i riferimenti della Sfida ricevuti in questo giro.
Le abilità dichiarate senza prova si misurano a parte, su più giorni (scripts/vincoli_report.py).
"""
import json, re
from pathlib import Path

import knowledge

ROOT = Path(__file__).resolve().parent
# nomi che compaiono come strumenti immaginari nei testi dei residenti (audit del 3/11) e forme generiche
KNOWN_IMAGINARY = re.compile(r'\b(authenti ?check|veri ?check|verifica ?ai|factcheckr|infoverify|question refinement engine|qre)\b', re.I)
CAMEL = re.compile(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+[a-z]*\b')
TOOLISH = re.compile(r'(strument|tool|sistema|piattaform|software|app\b|engine|algoritm|usa(?:re|ndo)?|utilizz|tramite|con il|con lo)', re.I)
# nomi CamelCase reali, non strumenti dell'ambiente ma esistenti fuori (non sono violazioni)
REAL_NAMES = {'PolitiFact', 'FullFact', 'YouTube', 'TikTok', 'LinkedIn', 'OpenAI', 'ChatGPT', 'GitHub', 'DeepMind', 'WhatsApp',
              'PayPal', 'iPhone', 'HuggingFace', 'PubMed', 'GoogleNews', 'OpenFact', 'FactCheck', 'McDonald', 'MacBook', 'JavaScript',
              'PowerPoint', 'BlackRock', 'OnlyFans', 'SpaceX', 'StackOverflow', 'NewsGuard', 'CrowdTangle'}
RESIDENTS = None


def _residents():
    global RESIDENTS
    if RESIDENTS is None:
        try:
            RESIDENTS = [b['name'] for b in json.loads((ROOT / 'bots.json').read_text())['bots']]
        except (OSError, ValueError, KeyError):
            RESIDENTS = []
    return RESIDENTS


def imaginary_tools(text):
    found = []
    for m in KNOWN_IMAGINARY.finditer(text or ''):
        found.append(m.group(0))
    for m in CAMEL.finditer(text or ''):
        name = m.group(0)
        if name in REAL_NAMES or name.upper() in {t['nome'] for t in knowledge.TOOLS}:
            continue
        around = (text[max(0, m.start() - 40):m.end() + 40])
        if TOOLISH.search(around):
            found.append(name)
    seen, out = set(), []
    for f in found:
        k = f.lower().replace(' ', '')
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def _exists(root, stem):
    return (root / 'dati' / f'{stem}.json').exists() or (root / 'dati' / f'{stem}.md').exists()


# (motivo, regex sul desiderio, condizione di esistenza, comando che già lo offre)
REDUNDANT = (
    ('dataset di notizie satiriche e vere', re.compile(r'(dataset|database|raccolta|set|esempi|fonte|archivio)[^.]{0,60}(satir|notizie (?:vere|false))|satir[^.]{0,60}(dataset|database|raccolta|esempi)', re.I),
     lambda root: _exists(root, 'sfida-002'), 'NOTIZIE: sfida 002'),
    ('set di notizie da classificare', re.compile(r'(dataset|set|raccolta|elenco)[^.]{0,40}(notizie|affermazioni)[^.]{0,40}(classific|verific|etichett)', re.I),
     lambda root: _exists(root, 'sfida-001'), 'NOTIZIE: sfida'),
    ('analisi linguistica automatica', re.compile(r'(strumento|tool|software|sistema)[^.]{0,40}analisi (?:linguistic|del linguaggio|del testo)', re.I),
     lambda root: any(t['nome'] == 'ANALIZZA' for t in knowledge.TOOLS), 'ANALIZZA: <testo>'),
    ('elenco di strumenti e risorse disponibili', re.compile(r'(elenco|mappa|lista|panoramica)[^.]{0,40}(strumenti|risorse)', re.I),
     lambda root: any(t['nome'] == 'OSSERVA' for t in knowledge.TOOLS), 'OSSERVA: strumenti'),
)


def redundant_request(wish, root=None):
    root = root or ROOT
    out = []
    if wish and re.search(r'metodolog|approccio|come (?:creare|costruire|gestire)|creare (?:un|il) (?:dataset|database)', wish, re.I):
        return out  # chiede un metodo per costruire, non la risorsa
    for why, rx, exists, cmd in REDUNDANT:
        if wish and rx.search(wish) and exists(root):
            return [{'chiede': why, 'esiste_gia': cmd}]   # una violazione per desiderio, la più specifica
    return out


def command_misuse(query):
    q = (query or '').strip()
    if not q or re.match(r'^(NOTIZIE|ANALIZZA|OSSERVA|QUADERNO)\s*:', q, re.I):
        return None
    ql = q.lower().strip(' ."\'')
    names = [n.lower() for n in _residents()]
    if re.search(r'<cosa>|<tema>|<testo>', ql):
        return 'segnaposto copiato'
    if re.match(r'^sfid', ql) or 'sfida 00' in ql or ql in ('mappa', 'dataset'):
        return 'materiale condiviso cercato con CERCA invece di NOTIZIE'
    if ql in ('wikipedia', 'arxiv', 'hacker news', 'notizie', 'osserva', 'analizza') or ql.rstrip('.') in ('wikipedia', 'arxiv'):
        return 'nome di fonte o comando usato come ricerca'
    if ql in names:
        return 'nome di residente usato come ricerca'
    return None


def _ngrams(text, n=6):
    words = re.findall(r"[a-zà-ÿ0-9']+", (text or '').lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def copy_ratio(text, refs):
    """Quota dei 6-grammi del testo presenti nei riferimenti ricevuti (0-1)."""
    a, b = _ngrams(text), _ngrams(refs)
    return round(len(a & b) / len(a), 2) if a and b else 0.0


def check(row, plan, root=None):
    """Violazioni di un giro (lista di dict). Non modifica nulla."""
    out = []
    text = row.get('testo') or ''
    names = imaginary_tools(text)
    if names:
        out.append({'tipo': 'strumento_inesistente', 'candidati': names})
    for r in redundant_request(row.get('desiderio'), root):
        out.append(dict({'tipo': 'richiesta_ridondante'}, **r))
    misuse = command_misuse(row.get('strumento'))
    if misuse:
        out.append({'tipo': 'comando_errato', 'query': row.get('strumento'), 'motivo': misuse})
    refs = plan.get('riferimenti_testo') or ''
    if refs and text:
        ratio = copy_ratio(text, refs)
        if ratio >= 0.25:
            out.append({'tipo': 'copia_riferimenti', 'quota_6grammi': ratio})
    return out
