"""Applica la patch di integrazione fauna F01 a una COPIA LOCALE del sorgente del Worker genesis-world-test.

Il sorgente del Worker non e' in questo repository: va passato come cartella (i 7 file src/*.js).
Non tocca Cloudflare, non fa deploy: scrive solo nella cartella di uscita indicata.

Uso:  python3 genesis/fauna01/adapter/integrazione/applica_patch.py <cartella_src_worker> <cartella_uscita> [--habitat <export.json>]

--habitat  export REALE della scena demo (contratto CONTRATTO_HABITAT.md) da incorporare nel Worker al posto della fixture
           sintetica. Prima di scrivere qualunque file viene convalidato con habitat.mjs (serve `node`) in modalita'
           integrazione reale: un export sintetico, con hash errato o con campi mancanti ferma la patch.
           Senza --habitat si incorpora la fixture sintetica (solo prove; nel Worker serve FAUNA_FIXTURE_SINTETICA=1).
"""
import argparse, json, pathlib, shutil, subprocess, sys

ADP = pathlib.Path(__file__).resolve().parents[2]          # genesis/fauna01
FIXTURE = ADP / 'adapter/fixtures/habitat_sintetico_v1.json'

# Convalida con lo STESSO validatore del Worker (nessuna seconda implementazione del contratto in Python).
_CONVALIDA_JS = r"""
import { pathToFileURL } from 'node:url';
const { importaHabitat } = await import(pathToFileURL(process.argv[1]).href);
let testo = '';
for await (const c of process.stdin) testo += c;
try {
  const h = importaHabitat(JSON.parse(testo), { consentiSintetico: false });
  console.log(JSON.stringify({ zone_id: h.zone_id, sha256: h.sha256, width: h.width, height: h.height,
    cell_size_m: h.cell_size_m, suitable_cells: h.suitable_cells, spawn: h.spawn.length }));
} catch (e) { console.error(e.message); process.exit(1); }
"""


class HabitatRifiutato(Exception):
    pass


def convalida_habitat_reale(percorso, node='node'):
    """Restituisce (testo JSON, riepilogo) di un export reale valido; solleva HabitatRifiutato altrimenti."""
    p = pathlib.Path(percorso).resolve()
    try:
        testo = p.read_text(encoding='utf-8')
    except OSError as e:
        raise HabitatRifiutato(f'impossibile leggere {p}: {e}')
    try:
        json.loads(testo)
    except ValueError as e:
        raise HabitatRifiutato(f'{p} non e\' JSON valido: {e}')
    try:
        r = subprocess.run([node, '--input-type=module', '-e', _CONVALIDA_JS, str(ADP / 'adapter/habitat.mjs')],
                           input=testo, capture_output=True, text=True, encoding='utf-8', timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise HabitatRifiutato(f'convalida non eseguita (serve node): {e}')
    if r.returncode != 0:
        raise HabitatRifiutato(r.stderr.strip() or f'validatore uscito con codice {r.returncode}')
    return testo, json.loads(r.stdout)


def sost(testo, vecchio, nuovo, n=1):
    assert testo.count(vecchio) == n, (vecchio, testo.count(vecchio))
    return testo.replace(vecchio, nuovo)


def applica(orig, dst, habitat=None):
    orig = pathlib.Path(orig).resolve(); dst = pathlib.Path(dst).resolve()
    if dst == orig or orig in dst.parents:
        sys.exit('la cartella di uscita deve essere diversa dal sorgente e fuori da esso: gli originali non si modificano')
    # l'habitat si convalida PRIMA di scrivere: con un export rifiutato la cartella di uscita non viene toccata
    if habitat is None:
        hab, info = FIXTURE.read_text(encoding='utf-8'), {'origine': 'fixture sintetica (solo prove: FAUNA_FIXTURE_SINTETICA=1)'}
    else:
        hab, info = convalida_habitat_reale(habitat)
        info = {'origine': f'export reale {pathlib.Path(habitat).resolve()}', **info}

    (dst / 'fauna').mkdir(parents=True, exist_ok=True)
    for f in ['auth.js','corpo.js','schema.js','tempo.js','regole.js','index.js','mondo.js']:
        shutil.copy(orig/f, dst/f)
    for f in ['sha256.mjs','habitat.mjs','zona.mjs','persistenza.mjs']:
        shutil.copy(ADP/'adapter'/f, dst/'fauna'/f)
    shutil.copy(ADP/'sim.mjs', dst/'sim.mjs')
    (dst/'fauna'/'habitat_dati.mjs').write_text('export default ' + hab.strip() + ';\n', encoding='utf-8')

    m = (dst/'mondo.js').read_text()
    m = sost(m, "import { regoleTick } from './regole.js';\n", """import { regoleTick } from './regole.js';
import { inizializzaFauna, faunaAvanza, faunaVista, configuraFauna } from './fauna/persistenza.mjs';
import { importaHabitat } from './fauna/habitat.mjs';
import { ErroreFauna } from './fauna/zona.mjs';
import HABITAT_FAUNA from './fauna/habitat_dati.mjs';
""")
    m = sost(m, "    Object.assign(this, configura(env));\n", """    Object.assign(this, configura(env));
    this.fauna = configuraFauna(env);
    this.habitatFauna = null;
    if (this.fauna.attiva) {
      try { this.habitatFauna = importaHabitat(HABITAT_FAUNA, { consentiSintetico: this.fauna.consentiSintetico }); }
      catch (e) { this.fauna.attiva = false; console.error({ messaggio: 'fauna disattivata: habitat rifiutato', errore: String(e.message) }); }
    }
""")
    m = sost(m, "    for (const q of SCHEMA) this.sql.exec(q);\n", "    for (const q of SCHEMA) this.sql.exec(q);\n    if (this.fauna.attiva) inizializzaFauna(this.sql);\n")
    m = sost(m, "      this.setMeta('ultimo_ms', this.num('ultimo_ms') + n * this.tickMs);\n    });\n    return dovuti - n;", """      this.setMeta('ultimo_ms', this.num('ultimo_ms') + n * this.tickMs);
      if (this.fauna.attiva) {
        const f = faunaAvanza(this.sql, this.habitatFauna, tick, this.fauna);
        if (f.stato !== 'attiva' || f.arretrato > 0) console.warn({ messaggio: 'fauna', stato: f.stato, motivo: f.motivo, arretrato: f.arretrato });
      }
    });
    return dovuti - n;""")
    m = sost(m, "  // ---- tempo ----\n", """  async faunaLeggi(nonce, areaTesto) {
    await this.assicuraAllarme();
    if (!this.consumaNonce(nonce)) return NON_AUTORIZZATO;
    if (!this.fauna.attiva) return { status: 404, corpo: { errore: 'fauna non attiva' } };
    let area;
    if (areaTesto !== null) {
      if (!/^\\d{1,3}(,\\d{1,3}){3}$/.test(areaTesto)) return { status: 400, corpo: { errore: 'area non valida' } };
      area = areaTesto.split(',').map(Number);
    }
    try {
      const v = faunaVista(this.sql, this.habitatFauna, { area });
      return v ? { status: 200, corpo: v } : { status: 404, corpo: { errore: 'zona non ancora creata' } };
    } catch (e) {
      if (e instanceof ErroreFauna) return { status: 400, corpo: { errore: e.codice } };
      throw e;
    }
  }

  // ---- tempo ----
""")
    (dst/'mondo.js').write_text(m)
    i = (dst/'index.js').read_text()
    i = sost(i, "'/v1/eventi': ['GET', 'POST'] };", "'/v1/eventi': ['GET', 'POST'], '/v1/fauna': ['GET'] };")
    i = sost(i, "  if (url.pathname === '/v1/stato') return daMondo(await mondo.stato(a.nonce));\n", "  if (url.pathname === '/v1/stato') return daMondo(await mondo.stato(a.nonce));\n  if (url.pathname === '/v1/fauna') return daMondo(await mondo.faunaLeggi(a.nonce, url.searchParams.get('area')));\n")
    (dst/'index.js').write_text(i)
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0], usage=__doc__.split('Uso:  ')[1].split('\n')[0])
    ap.add_argument('src_worker'); ap.add_argument('uscita')
    ap.add_argument('--habitat', help='export reale della scena demo (convalidato con habitat.mjs prima di scrivere)')
    a = ap.parse_args(argv)
    try:
        info = applica(a.src_worker, a.uscita, a.habitat)
    except HabitatRifiutato as e:
        sys.exit(f'patch NON applicata, habitat rifiutato: {e}')
    print('patch applicata in', pathlib.Path(a.uscita).resolve())
    print('habitat incorporato:', json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    main()
