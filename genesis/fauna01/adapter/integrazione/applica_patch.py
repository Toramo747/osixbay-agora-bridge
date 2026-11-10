"""Applica la patch di integrazione fauna F01 a una COPIA LOCALE del sorgente del Worker genesis-world-test.

Il sorgente del Worker non e' in questo repository: va passato come cartella (i 7 file src/*.js).
Non tocca Cloudflare, non fa deploy: scrive solo nella cartella di uscita indicata.

Uso:  python3 genesis/fauna01/adapter/integrazione/applica_patch.py <cartella_src_worker> <cartella_uscita>
"""
import shutil, sys, pathlib
if len(sys.argv) != 3:
    sys.exit(__doc__)
orig = pathlib.Path(sys.argv[1]).resolve(); dst = pathlib.Path(sys.argv[2]).resolve()
adp = pathlib.Path(__file__).resolve().parents[2]
if dst == orig or orig in dst.parents:
    sys.exit('la cartella di uscita deve essere diversa dal sorgente e fuori da esso: gli originali non si modificano')
(dst / 'fauna').mkdir(parents=True, exist_ok=True)
for f in ['auth.js','corpo.js','schema.js','tempo.js','regole.js','index.js','mondo.js']:
    shutil.copy(orig/f, dst/f)
for f in ['sha256.mjs','habitat.mjs','zona.mjs','persistenza.mjs']:
    shutil.copy(adp/'adapter'/f, dst/'fauna'/f)
shutil.copy(adp/'sim.mjs', dst/'sim.mjs')
hab = (adp/'adapter/fixtures/habitat_sintetico_v1.json').read_text()
(dst/'fauna'/'habitat_dati.mjs').write_text('export default ' + hab.strip() + ';\n')

def sost(testo, vecchio, nuovo, n=1):
    assert testo.count(vecchio) == n, (vecchio, testo.count(vecchio))
    return testo.replace(vecchio, nuovo)

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
print('patch applicata in', dst)
