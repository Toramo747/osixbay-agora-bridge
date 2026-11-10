/**
 * Prova LOCALE nel runtime workerd (miniflare): Worker reale + patch fauna, Durable Object SQLite su disco locale.
 * Nessuna chiamata a Cloudflare, nessun deploy, chiave di firma usa e getta. Habitat: fixture sintetica dichiarata.
 *
 * Preparazione (fuori dal repository):
 *   python3 genesis/fauna01/adapter/integrazione/applica_patch.py <src_worker> /tmp/mondo-fauna
 *   npm install --no-save miniflare        (in una cartella di lavoro; nessun account richiesto)
 * Uso:  node genesis/fauna01/adapter/integrazione/prova_workerd.mjs /tmp/mondo-fauna
 */
import { Miniflare } from 'miniflare';
import { readFileSync, rmSync, mkdtempSync } from 'node:fs';
import { generateKeyPairSync, sign, createHash, randomBytes } from 'node:crypto';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
const A = new URL('../', import.meta.url).href;
const { importaHabitat } = await import(A + 'habitat.mjs');
const { creaZona, passoZona, vistaClient } = await import(A + 'zona.mjs');
const habitat = importaHabitat(JSON.parse(readFileSync(new URL('../fixtures/habitat_sintetico_v1.json', import.meta.url), 'utf8')), { consentiSintetico: true });

if (!process.argv[2]) { console.error('uso: node prova_workerd.mjs <cartella prodotta da applica_patch.py>'); process.exit(2); }
const SRC = path.resolve(process.argv[2]) + path.sep;
const files = ['index.js', 'auth.js', 'corpo.js', 'mondo.js', 'schema.js', 'tempo.js', 'regole.js', 'sim.mjs',
  'fauna/sha256.mjs', 'fauna/habitat.mjs', 'fauna/zona.mjs', 'fauna/persistenza.mjs', 'fauna/habitat_dati.mjs'];
const { publicKey, privateKey } = generateKeyPairSync('ed25519');      // chiave di prova usa e getta, solo locale
const pub = publicKey.export({ format: 'der', type: 'spki' }).subarray(-32).toString('base64');
const TICK_MS = 200;
const crea = (persist, extra = {}) => new Miniflare({
  modules: files.map(f => ({ type: 'ESModule', path: SRC + f, contents: readFileSync(SRC + f, 'utf8') })),
  modulesRoot: SRC, compatibilityDate: '2026-07-01',
  durableObjects: { MONDO: { className: 'Mondo', useSQLite: true } }, durableObjectsPersist: persist,
  bindings: { TICK_MS: String(TICK_MS), TICK_PER_GIORNO: '6', MAX_TICK_PER_ALLARME: '20', CHIAVI_PUBBLICHE: JSON.stringify({ 'prova-locale': pub }),
    FAUNA_ATTIVA: '1', FAUNA_FIXTURE_SINTETICA: '1', FAUNA_SEED: '13', ...extra },
});
async function chiama(mf, metodo, percorso, corpo = '', firma = true) {
  const headers = {};
  if (firma) {
    const ts = String(Math.floor(Date.now() / 1000)), nonce = randomBytes(12).toString('hex');
    const msg = `${metodo}\n${percorso}\n${ts}\n${nonce}\n${createHash('sha256').update(corpo).digest('hex')}`;
    Object.assign(headers, { 'X-Genesis-Agente': 'prova-locale', 'X-Genesis-Timestamp': ts, 'X-Genesis-Nonce': nonce,
      'X-Genesis-Firma': sign(null, Buffer.from(msg), privateKey).toString('base64') });
  }
  const r = await mf.dispatchFetch('http://mondo.locale' + percorso, { method: metodo, headers, body: corpo || undefined });
  return { status: r.status, corpo: await r.json() };
}
const pausa = (ms) => new Promise(r => setTimeout(r, ms));
function atteso(passi) { const z = creaZona(habitat, { seed: 13 }); for (let i = 0; i < passi; i++) passoZona(z); return vistaClient(z).entita; }
const esiti = [];
const ok = (nome, dettagli = '') => { esiti.push(nome); console.log('PASS', nome, dettagli); };

const dir = mkdtempSync(path.join(tmpdir(), 'mondo-'));
let mf = crea(dir);
assert.equal((await chiama(mf, 'GET', '/health', '', false)).status, 200);
assert.equal((await chiama(mf, 'GET', '/v1/fauna', '', false)).status, 401);
ok('richiesta non firmata a /v1/fauna respinta (401)');
assert.equal((await chiama(mf, 'GET', '/v1/stato')).status, 200);
let visti = 0, ultimo = -1, nascita = null;
for (let i = 0; i < 24; i++) {
  await pausa(500);
  const [f, s] = [await chiama(mf, 'GET', '/v1/fauna'), await chiama(mf, 'GET', '/v1/stato')];
  if (f.status !== 200) continue;
  nascita ??= f.corpo.tick_mondo - f.corpo.passo;
  assert.equal(f.corpo.tick_mondo - f.corpo.passo, nascita);
  assert.ok(f.corpo.passo >= ultimo); ultimo = f.corpo.passo;
  assert.ok(s.corpo.tempo.tick >= f.corpo.tick_mondo);
  assert.deepStrictEqual(f.corpo.entita, atteso(f.corpo.passo));
  assert.ok(!Object.keys(s.corpo.dati).some(k => k.includes('fauna')));
  visti++;
}
assert.ok(visti >= 15 && ultimo >= 40);
ok('tick autonomi via alarm nel runtime workerd: vista identica al replay Node a ogni lettura', `letture=${visti} passo=${ultimo}`);
assert.equal((await chiama(mf, 'POST', '/v1/fauna', '{}')).status, 405);
assert.equal((await chiama(mf, 'POST', '/v1/eventi', JSON.stringify({ tipo: 'fauna.imposta', dati: { energia: 99 } }))).status, 400);
assert.equal((await chiama(mf, 'POST', '/v1/eventi', JSON.stringify({ tipo: 'mondo.imposta', dati: { chiave: 'fauna_zona', valore: { organismi: [] } } }))).status, 201);
assert.equal((await chiama(mf, 'GET', '/v1/fauna?area=0,0,999,9999')).status, 400);
const area = await chiama(mf, 'GET', '/v1/fauna?area=0,0,8,8');
assert.ok(area.status === 200 && area.corpo.entita.every(e => e.cella[0] <= 8 && e.cella[1] <= 8));
const dopoScritture = await chiama(mf, 'GET', '/v1/fauna');
assert.deepStrictEqual(dopoScritture.corpo.entita, atteso(dopoScritture.corpo.passo));
ok('il client non puo\' scrivere la fauna (405/400) e mondo.imposta non la altera');

const prima = dopoScritture.corpo.passo;
await mf.dispose();
await pausa(6000);                                   // "Worker fermo" 6 s = ~30 tick di arretrato (> 20 per allarme)
mf = crea(dir);
await chiama(mf, 'GET', '/v1/stato');
await pausa(2500);
const rientro = await chiama(mf, 'GET', '/v1/fauna'), st = await chiama(mf, 'GET', '/v1/stato');
assert.ok(rientro.corpo.passo >= prima + 30, `passo ${rientro.corpo.passo} dopo ${prima}`);
assert.equal(rientro.corpo.tick_mondo - rientro.corpo.passo, nascita);
assert.ok(st.corpo.tempo.tick - rientro.corpo.tick_mondo <= 2);
assert.deepStrictEqual(rientro.corpo.entita, atteso(rientro.corpo.passo));
ok('riavvio con stato su disco + recupero arretrato: nessun passo perso o duplicato', `passo ${prima} -> ${rientro.corpo.passo}`);
await mf.dispose();

mf = crea(dir, { FAUNA_ATTIVA: '0' });               // rollback logico: interruttore spento, dati fauna intatti
await chiama(mf, 'GET', '/v1/stato'); await pausa(1500);
assert.equal((await chiama(mf, 'GET', '/v1/fauna')).status, 404);
const t1 = (await chiama(mf, 'GET', '/v1/stato')).corpo.tempo.tick; await pausa(1200);
assert.ok((await chiama(mf, 'GET', '/v1/stato')).corpo.tempo.tick > t1);
await mf.dispose();
mf = crea(dir);
await chiama(mf, 'GET', '/v1/stato'); await pausa(4000);
const riacceso = await chiama(mf, 'GET', '/v1/fauna');
assert.ok(riacceso.corpo.passo > rientro.corpo.passo);
assert.deepStrictEqual(riacceso.corpo.entita, atteso(riacceso.corpo.passo));
ok('interruttore FAUNA_ATTIVA=0: il mondo continua, la fauna si ferma; riaccesa riprende coerente', `passo ${riacceso.corpo.passo}`);
await mf.dispose();

const dir2 = mkdtempSync(path.join(tmpdir(), 'mondo-'));
mf = crea(dir2, { FAUNA_FIXTURE_SINTETICA: '0' });   // come in un'integrazione reale: la fixture sintetica viene rifiutata
await chiama(mf, 'GET', '/v1/stato'); await pausa(1200);
assert.equal((await chiama(mf, 'GET', '/v1/fauna')).status, 404);
assert.ok((await chiama(mf, 'GET', '/v1/stato')).corpo.tempo.tick >= 3);
ok('senza FAUNA_FIXTURE_SINTETICA=1 l\'habitat sintetico e\' rifiutato: fauna spenta, mondo regolare');
await mf.dispose();
rmSync(dir, { recursive: true, force: true }); rmSync(dir2, { recursive: true, force: true });
console.log(`\nworkerd locale: ${esiti.length}/6 PASS`);
