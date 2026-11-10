/** Test di persistenza su SQLite reale (node:sqlite) con l'interfaccia del Durable Object. Habitat: fixture sintetica dichiarata. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { importaHabitat, hashHabitat } from '../habitat.mjs';
import { creaZona, passoZona, snapshotZona, FAUNA_SCHEMA_VERSION } from '../zona.mjs';
import { inizializzaFauna, faunaAvanza, faunaVista, faunaStato, configuraFauna, SCHEMA_FAUNA } from '../persistenza.mjs';
import { creaStorage } from './sql_shim.mjs';
import { MondoFinto } from './mondo_finto.mjs';
import { habitatSintetico } from './genera_fixture.mjs';

const habitat = importaHabitat(JSON.parse(readFileSync(new URL('../fixtures/habitat_sintetico_v1.json', import.meta.url), 'utf8')), { consentiSintetico: true });
const ZONA = habitat.zone_id;
const cfg = (extra = {}) => ({ ...configuraFauna({ FAUNA_ATTIVA: '1', FAUNA_FIXTURE_SINTETICA: '1', FAUNA_SEED: '13', FAUNA_MAX_PASSI: '20' }), ...extra });
const MIN = 60_000, T0 = 1_000_000;
const nuovo = (extra, opz) => { const st = creaStorage(); return { st, m: new MondoFinto(st, habitat, cfg(extra), { t0: T0, ...opz }) }; };
/** Hash atteso rieseguendo da zero: seed + habitat + numero di passi (replay puro, senza database). */
function replay(passi, seed = 13) { const z = creaZona(habitat, { seed }); for (let i = 0; i < passi; i++) passoZona(z); return snapshotZona(z).sha256; }
const conta = (st, tabella) => st.sql.exec(`SELECT COUNT(*) AS n FROM ${tabella}`).one().n;

test('configurazione: spenta di default, valori non validi ignorati', () => {
  assert.equal(configuraFauna({}).attiva, false);
  assert.equal(configuraFauna({ FAUNA_ATTIVA: 'true' }).attiva, false);
  assert.equal(configuraFauna({}).consentiSintetico, false);
  const c = configuraFauna({ FAUNA_ATTIVA: '1', FAUNA_SEED: '-3', FAUNA_MAX_PASSI: '99999', FAUNA_TICK_OGNI: 'NaN', FAUNA_DIARIO_MAX: '0' });
  assert.deepStrictEqual([c.seed, c.maxPassi, c.tickOgni, c.diarioMax], [null, 5, 1, 2880]);
});

test('schema separato e idempotente: le tabelle del mondo non vengono toccate', () => {
  const { st, m } = nuovo();
  st.sql.exec(`INSERT INTO stato (chiave, valore, versione) VALUES ('genesi', '{"privato":true}', 1)`);
  for (const q of SCHEMA_FAUNA) assert.match(q, /^CREATE TABLE IF NOT EXISTS fauna_/);
  inizializzaFauna(st.sql); inizializzaFauna(st.sql);
  for (let i = 1; i <= 30; i++) m.avanza(T0 + i * MIN);
  assert.equal(conta(st, 'stato'), 1);
  assert.equal(conta(st, 'eventi'), 0);
  assert.equal(st.sql.exec(`SELECT valore FROM stato WHERE chiave = 'genesi'`).one().valore, '{"privato":true}');
  assert.equal(st.sql.exec(`SELECT valore FROM fauna_meta WHERE chiave = 'schema_version'`).one().valore, String(FAUNA_SCHEMA_VERSION));
  assert.equal(faunaStato(st.sql, ZONA).snapshot_sha256, replay(29));    // creata al tick 1, 29 passi ai tick 2..30
});

test('schema fauna piu\' recente del codice: rifiuto', () => {
  const st = creaStorage();
  inizializzaFauna(st.sql);
  st.sql.exec(`UPDATE fauna_meta SET valore = '99' WHERE chiave = 'schema_version'`);
  assert.throws(() => inizializzaFauna(st.sql), /versione_futura/);
});

test('seed esplicito obbligatorio alla creazione', () => {
  const st = creaStorage();
  inizializzaFauna(st.sql);
  assert.throws(() => faunaAvanza(st.sql, habitat, 1, cfg({ seed: null })), /seed_non_valido/);
  assert.equal(conta(st, 'fauna_zona'), 0);
});

test('alarm duplicato e retry: lo stesso tick non viene mai applicato due volte', () => {
  const { st, m } = nuovo();
  for (let i = 1; i <= 50; i++) {
    m.avanza(T0 + i * MIN);
    const prima = faunaStato(st.sql, ZONA), scritture = st.conteggi.scritture;
    assert.equal(m.avanza(T0 + i * MIN + 250), 0);                      // seconda consegna dello stesso alarm
    const r = faunaAvanza(st.sql, habitat, m.num('tick'), m.cfg);      // chiamata diretta ripetuta
    assert.equal(r.passi, 0);
    assert.deepStrictEqual(faunaStato(st.sql, ZONA), prima);
    assert.equal(st.conteggi.scritture, scritture);
  }
  assert.equal(faunaStato(st.sql, ZONA).snapshot_sha256, replay(49));
});

test('monotonicita\': un tick del mondo piu\' vecchio non fa tornare indietro la fauna', () => {
  const { st, m } = nuovo();
  for (let i = 1; i <= 20; i++) m.avanza(T0 + i * MIN);
  const prima = faunaStato(st.sql, ZONA);
  assert.equal(faunaAvanza(st.sql, habitat, 5, m.cfg).passi, 0);
  assert.deepStrictEqual(faunaStato(st.sql, ZONA), prima);
  assert.throws(() => faunaAvanza(st.sql, habitat, -1, m.cfg), /tick_non_valido/);
  assert.throws(() => faunaAvanza(st.sql, habitat, 1.5, m.cfg), /tick_non_valido/);
});

test('crash tra calcolo e commit: rollback totale di mondo e fauna, poi ripresa identica', () => {
  const { st, m } = nuovo();
  for (let i = 1; i <= 40; i++) m.avanza(T0 + i * MIN);
  const prima = faunaStato(st.sql, ZONA), tickPrima = m.num('tick'), diarioPrima = conta(st, 'fauna_diario');
  m.guastoPrimaDelCommit = true;
  for (let k = 0; k < 3; k++) assert.throws(() => m.avanza(T0 + 41 * MIN), /guasto simulato/);
  assert.deepStrictEqual(faunaStato(st.sql, ZONA), prima);
  assert.equal(m.num('tick'), tickPrima);
  assert.equal(conta(st, 'fauna_diario'), diarioPrima);
  m.guastoPrimaDelCommit = false;
  for (let i = 41; i <= 80; i++) m.avanza(T0 + i * MIN);
  assert.equal(faunaStato(st.sql, ZONA).snapshot_sha256, replay(79));
});

test('scrittura concorrente (versione cambiata tra lettura e scrittura): CAS fallisce e la transazione si annulla', () => {
  const { st, m } = nuovo();
  for (let i = 1; i <= 10; i++) m.avanza(T0 + i * MIN);
  const prima = faunaStato(st.sql, ZONA);
  let fatto = false;
  st.sql.intercetta = (q) => {
    if (!fatto && /UPDATE fauna_zona SET passo/.test(q)) { fatto = true; st.db.exec(`UPDATE fauna_zona SET versione = versione + 1`); }
  };
  assert.throws(() => m.avanza(T0 + 11 * MIN), /scrittura concorrente/);
  st.sql.intercetta = null;
  assert.deepStrictEqual(faunaStato(st.sql, ZONA), prima);    // anche l'incremento intruso e' stato annullato dal rollback
  assert.equal(m.num('tick'), 10);
});

test('recupero arretrato a budget: 3 giorni di fermo, mai piu\' di maxPassi per chiamata, stesso risultato del tempo regolare', () => {
  const { st, m } = nuovo();
  for (let i = 1; i <= 10; i++) m.avanza(T0 + i * MIN);
  const ora = T0 + (10 + 3 * 1440) * MIN;
  let chiamate = 0, arretrato;
  do {
    arretrato = m.avanza(ora);
    chiamate++;
    assert.ok(m.ultimaFauna.passi <= 20);
    assert.ok(chiamate <= 300, 'il recupero deve terminare in un numero limitato di allarmi');
  } while (arretrato > 0);
  assert.equal(chiamate, 3 * 1440 / 20);
  assert.equal(m.num('tick'), 10 + 3 * 1440);
  assert.equal(faunaStato(st.sql, ZONA).snapshot_sha256, replay(9 + 3 * 1440));
});

test('budget fauna piu\' stretto del mondo: la fauna resta indietro e recupera, senza perdere passi', () => {
  const { st, m } = nuovo({ maxPassi: 3 });
  m.avanza(T0 + MIN);                              // creazione al tick 1
  m.avanza(T0 + 21 * MIN);                         // il mondo fa 20 tick, la fauna solo 3
  assert.equal(m.num('tick'), 21);
  assert.deepStrictEqual([m.ultimaFauna.passi, m.ultimaFauna.arretrato], [3, 17]);
  assert.equal(faunaStato(st.sql, ZONA).tick_mondo, 4);
  let i = 21;
  while (faunaStato(st.sql, ZONA).passo < m.num('tick') - 1) { m.avanza(T0 + ++i * MIN); assert.ok(m.ultimaFauna.passi <= 3); assert.ok(i < 100); }
  assert.equal(faunaStato(st.sql, ZONA).snapshot_sha256, replay(m.num('tick') - 1));
});

test('tick biologico configurabile: un passo fauna ogni 3 tick del mondo', () => {
  const { st, m } = nuovo({ tickOgni: 3 });
  for (let i = 1; i <= 100; i++) m.avanza(T0 + i * MIN);
  assert.equal(faunaStato(st.sql, ZONA).passo, 33);
  assert.equal(faunaStato(st.sql, ZONA).snapshot_sha256, replay(33));
});

test('snapshot corrotto nel database: zona sospesa (fail closed), il mondo continua, nessuna eccezione', () => {
  const { st, m } = nuovo();
  for (let i = 1; i <= 10; i++) m.avanza(T0 + i * MIN);
  st.db.exec(`UPDATE fauna_zona SET snapshot = replace(snapshot, '"passo":9', '"passo":8')`);
  m.avanza(T0 + 11 * MIN);
  assert.deepStrictEqual([m.ultimaFauna.stato, m.ultimaFauna.motivo], ['sospesa', 'snapshot_corrotto']);
  const s = faunaStato(st.sql, ZONA);
  assert.deepStrictEqual([s.stato, s.passo], ['sospesa', 9]);
  const scritture = st.conteggi.scritture;
  for (let i = 12; i <= 30; i++) m.avanza(T0 + i * MIN);
  assert.equal(m.num('tick'), 30);
  assert.equal(st.conteggi.scritture - scritture, 19 * 2);              // solo le due scritture meta del mondo per tick
  assert.deepStrictEqual(faunaVista(st.sql, habitat), { zone_id: ZONA, stato: 'sospesa', entita: [] });
});

test('snapshot manomesso ma con hash coerente (organismo fuori mask): sospesa, mai applicato', () => {
  const { st, m } = nuovo();
  for (let i = 1; i <= 10; i++) m.avanza(T0 + i * MIN);
  const r = st.sql.exec('SELECT snapshot FROM fauna_zona').one();
  const d = JSON.parse(r.snapshot); d.organismi[0][1] = 0; d.organismi[0][2] = 0;
  st.db.prepare('UPDATE fauna_zona SET snapshot = ?').run(JSON.stringify(d));
  m.avanza(T0 + 11 * MIN);
  assert.equal(m.ultimaFauna.stato, 'sospesa');
});

test('habitat cambiato sotto una zona esistente: sospesa con motivo habitat_diverso', () => {
  const { st, m } = nuovo();
  for (let i = 1; i <= 10; i++) m.avanza(T0 + i * MIN);
  const g = habitatSintetico(); g.layers.food_initial[0][12] = 1;
  const { sha256, ...resto } = g;
  const altro = importaHabitat({ ...resto, sha256: hashHabitat(resto) }, { consentiSintetico: true });
  assert.equal(faunaAvanza(st.sql, altro, 11, m.cfg).motivo, 'habitat_diverso');
});

test('diario limitato: resta entro diarioMax righe', () => {
  const { st, m } = nuovo({ diarioMax: 50 });
  for (let i = 1; i <= 400; i++) m.avanza(T0 + i * MIN);
  assert.equal(conta(st, 'fauna_diario'), 50);
  const d = st.sql.exec('SELECT MIN(passo) AS a, MAX(passo) AS b FROM fauna_diario').one();
  assert.deepStrictEqual([d.a, d.b], [350, 399]);
});

test('vista client: sola lettura, null prima della creazione, niente fantasmi dopo disconnessione e rientro', () => {
  const { st, m } = nuovo();
  assert.equal(faunaVista(st.sql, habitat), null);
  for (let i = 1; i <= 150; i++) m.avanza(T0 + i * MIN);
  const scritture = st.conteggi.scritture;
  const prima = faunaVista(st.sql, habitat);
  assert.equal(st.conteggi.scritture, scritture);
  assert.equal(prima.tick_mondo, 150);
  for (let i = 151; i <= 600; i++) m.avanza(T0 + i * MIN);              // client scollegato per 450 tick
  const dopo = faunaVista(st.sql, habitat);
  const vivi = new Set(JSON.parse(st.sql.exec('SELECT snapshot FROM fauna_zona').one().snapshot).organismi.map(o => o[0]));
  assert.ok(dopo.entita.length > 0);
  for (const e of dopo.entita) assert.ok(vivi.has(e.id));
  assert.equal(dopo.totale_in_area, vivi.size);
  assert.ok(prima.entita.some(e => !vivi.has(e.id)), 'tra le due viste qualcuno e\' morto: il client deve riconciliare per id');
});

test('24 ore simulate (1440 tick, 1/min): nascite e morti, replay identico, scritture e dimensioni entro budget', () => {
  const { st, m } = nuovo();
  const inizio = process.hrtime.bigint();
  let peggiore = 0n;
  for (let i = 1; i <= 1441; i++) { const a = process.hrtime.bigint(); m.avanza(T0 + i * MIN); const d = process.hrtime.bigint() - a; if (d > peggiore) peggiore = d; }
  const totale = Number(process.hrtime.bigint() - inizio) / 1e6;
  const s = faunaStato(st.sql, ZONA);
  const d = st.sql.exec('SELECT SUM(nati) AS nati, SUM(morti) AS morti, MAX(vivi) AS picco, COUNT(*) AS righe FROM fauna_diario').one();
  assert.equal(s.passo, 1440);
  assert.equal(s.snapshot_sha256, replay(1440));
  assert.ok(d.nati > 0 && d.morti > 0);
  assert.ok(d.picco <= 50);
  const scrittureFauna = st.conteggi.scritture - 1441 * 2 - 2;
  assert.ok(scrittureFauna <= 1441 * 3 + 2, `scritture fauna/giorno: ${scrittureFauna}`);
  assert.ok(s.snapshot_caratteri < 20_000);
  console.log(JSON.stringify({ prova: '24h simulate', passi: s.passo, nati: d.nati, morti: d.morti, picco_vivi: d.picco, snapshot_caratteri: s.snapshot_caratteri,
    istruzioni_scrittura_fauna: scrittureFauna, ms_totali_node: +totale.toFixed(1), ms_allarme_peggiore_node: +(Number(peggiore) / 1e6).toFixed(3), sha256: s.snapshot_sha256 }));
});
