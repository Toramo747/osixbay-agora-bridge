/**
 * Adapter World -> F01, versione 1: fa vivere il simulatore di riferimento (../sim.mjs, non modificato)
 * dentro un habitat importato con habitat.mjs. Puro e deterministico: nessun I/O, nessun orologio, nessun LLM.
 *
 * Differenze volute rispetto alla griglia sintetica di sim.mjs:
 *  - la mask `suitable` viene SOLO dall'habitat (mai dallo snapshot);
 *  - il cibo ha capacita', scorta iniziale e ricrescita PER CELLA, dall'export (anche zero);
 *    per questo la ricrescita uniforme di sim.mjs e' disattivata (regrowth = 0) e applicata qui.
 */
import { World, Parameters } from '../sim.mjs';
import { sha256hex, canonico } from './sha256.mjs';
import { cellaInMondo } from './habitat.mjs';

export const FAUNA_SCHEMA_VERSION = 1;
export const ADAPTER_VERSION = '0.1.0';
export const SPECIE = 'F01';
export const MAX_SNAPSHOT = 400_000;       // caratteri JSON: rifiuto esplicito oltre questa soglia
const AZIONI = new Set(['rest', 'forage', 'flee', 'reproduce']);
const DUE64 = 1n << 64n;

export class ErroreFauna extends Error {
  constructor(codice, messaggio) { super(`${codice}: ${messaggio}`); this.codice = codice; }
}
const rifiuta = (m) => { throw new ErroreFauna('snapshot_non_valido', m); };
const finito = (n) => typeof n === 'number' && Number.isFinite(n);

function parametriSim(habitat, parametri) {
  let massimo = 1;
  for (const riga of habitat.cells) for (const c of riga) if (c.cap > massimo) massimo = c.cap;
  // regrowth 0: la ricrescita per cella la applica l'adapter. capacity = tetto globale, mai raggiunto oltre il cap di cella.
  return new Parameters({ ...parametri, capacity: massimo, regrowth: 0 });
}

function seedBig(seed) {
  let s;
  try { s = BigInt(seed); } catch { throw new ErroreFauna('seed_non_valido', 'seed deve essere un intero'); }
  if (s < 0n || s >= DUE64) throw new ErroreFauna('seed_non_valido', 'seed fuori da 0..2^64-1');
  return s;
}

function mondoVuoto(habitat, rng, parametri) {
  const w = new World(habitat.cells.map(r => r.map(c => c.suitable)), rng, parametriSim(habitat, parametri));
  for (let y = 0; y < habitat.height; y++) for (let x = 0; x < habitat.width; x++) {
    const c = habitat.cells[y][x];
    w.cells[y][x].food = c.food0;
    w.cells[y][x].danger = c.danger;
  }
  return w;
}

/** Crea la zona al passo 0: organismi iniziali solo sulle celle di spawn dichiarate dall'export. */
export function creaZona(habitat, { seed, parametri = {} }) {
  const world = mondoVuoto(habitat, seedBig(seed), parametri);
  for (const [x, y] of habitat.spawn) world.add_organism(x, y);
  const zona = { habitat, world, seed: seedBig(seed).toString() };
  verificaInvarianti(zona);
  return zona;
}

/** Controlli difensivi dopo ogni passo: se falliscono il passo NON viene salvato. */
export function verificaInvarianti({ habitat, world }) {
  const p = world.parameters;
  if (world.organisms.length > p.max_population) throw new ErroreFauna('invariante', 'popolazione oltre il tetto');
  const ids = new Set();
  for (const o of world.organisms) {
    const c = habitat.cells[o.y]?.[o.x];
    if (!c || !c.suitable) throw new ErroreFauna('invariante', 'organismo fuori dalla mask playable AND suitable');
    if (!(o.energy > 0 && o.energy <= p.energy_cap)) throw new ErroreFauna('invariante', 'energia fuori intervallo');
    if (ids.has(o.identity)) throw new ErroreFauna('invariante', 'id duplicato');
    ids.add(o.identity);
  }
  for (let y = 0; y < habitat.height; y++) for (let x = 0; x < habitat.width; x++) {
    const f = world.cells[y][x].food, c = habitat.cells[y][x];
    if (!(f >= 0 && f <= c.cap)) throw new ErroreFauna('invariante', 'cibo fuori da 0..capacita');
  }
}

/** Un passo deterministico: sim.mjs, poi ricrescita per cella limitata dalla capacita' reale. */
export function passoZona(zona) {
  const { habitat, world } = zona;
  const r = world.step();
  for (let y = 0; y < habitat.height; y++) for (let x = 0; x < habitat.width; x++) {
    const c = habitat.cells[y][x];
    if (c.suitable && c.regrowth > 0) world.cells[y][x].food = Math.min(c.cap, world.cells[y][x].food + c.regrowth);
  }
  verificaInvarianti(zona);
  return { passo: world.ticks, vivi: r.alive, nati: r.born, morti: r.died };
}

/** Snapshot compatto e canonico. Non contiene la mask: quella resta nell'habitat (identificato dal suo hash). */
export function snapshotZona({ habitat, world, seed }) {
  const cibo = [];
  for (let y = 0; y < habitat.height; y++) for (let x = 0; x < habitat.width; x++) {
    if (habitat.cells[y][x].suitable) cibo.push(world.cells[y][x].food);
  }
  const testo = canonico({
    fauna_schema_version: FAUNA_SCHEMA_VERSION, adapter_version: ADAPTER_VERSION, specie: SPECIE,
    zone_id: habitat.zone_id, habitat_sha256: habitat.sha256, seed, passo: world.ticks,
    parametri: { ...world.parameters }, rng_state: world.rng_state.toString(), next_id: world.next_id, cibo,
    organismi: world.organisms.map(o => [o.identity, o.x, o.y, o.energy, o.age, o.cooldown, o.threshold, o.efficiency, o.last_action]),
  });
  if (testo.length > MAX_SNAPSHOT) throw new ErroreFauna('snapshot_troppo_grande', `${testo.length} caratteri`);
  return { testo, sha256: sha256hex(testo) };
}

// Migrazioni in avanti dello snapshot: versione -> funzione che produce la versione successiva. Oggi esiste solo la 1.
const MIGRAZIONI = {};

/** Ricostruisce la zona da uno snapshot, rifiutando tutto cio' che non e' coerente con habitat, versione e limiti. */
export function ripristinaZona(habitat, testo, sha256Atteso) {
  if (typeof testo !== 'string' || testo.length > MAX_SNAPSHOT) rifiuta('testo assente o troppo grande');
  if (sha256Atteso !== undefined && sha256hex(testo) !== sha256Atteso) throw new ErroreFauna('snapshot_corrotto', 'sha256 non corrisponde');
  let d;
  try { d = JSON.parse(testo); } catch { rifiuta('JSON non valido'); }
  if (!d || typeof d !== 'object' || Array.isArray(d)) rifiuta('deve essere un oggetto');
  if (!Number.isInteger(d.fauna_schema_version) || d.fauna_schema_version < 1) rifiuta('versione');
  if (d.fauna_schema_version > FAUNA_SCHEMA_VERSION) throw new ErroreFauna('versione_futura', 'snapshot scritto da un adapter piu\' recente');
  while (d.fauna_schema_version < FAUNA_SCHEMA_VERSION) {
    const m = MIGRAZIONI[d.fauna_schema_version];
    if (!m) throw new ErroreFauna('migrazione_mancante', `da versione ${d.fauna_schema_version}`);
    d = m(d);
  }
  if (d.specie !== SPECIE) rifiuta('specie');
  if (d.zone_id !== habitat.zone_id) throw new ErroreFauna('habitat_diverso', 'zone_id');
  if (d.habitat_sha256 !== habitat.sha256) throw new ErroreFauna('habitat_diverso', 'l\'habitat e\' cambiato: serve una migrazione esplicita');
  if (!Number.isInteger(d.passo) || d.passo < 0) rifiuta('passo');
  if (typeof d.rng_state !== 'string' || !/^\d{1,20}$/.test(d.rng_state) || BigInt(d.rng_state) >= DUE64) rifiuta('rng_state');
  if (typeof d.seed !== 'string' || !/^\d{1,20}$/.test(d.seed)) rifiuta('seed');
  let world;
  try { world = mondoVuoto(habitat, BigInt(d.rng_state), d.parametri ?? {}); } catch (e) {
    if (e instanceof ErroreFauna) throw e;
    rifiuta('parametri');
  }
  const p = world.parameters;
  if (!Array.isArray(d.cibo) || d.cibo.length !== habitat.suitable_cells) rifiuta('cibo: numero di celle');
  let i = 0;
  for (let y = 0; y < habitat.height; y++) for (let x = 0; x < habitat.width; x++) {
    const c = habitat.cells[y][x];
    if (!c.suitable) continue;
    const f = d.cibo[i++];
    if (!finito(f) || f < 0 || f > c.cap) rifiuta('cibo fuori da 0..capacita');
    world.cells[y][x].food = f;
  }
  if (!Array.isArray(d.organismi) || d.organismi.length > p.max_population) rifiuta('organismi');
  if (!Number.isInteger(d.next_id) || d.next_id < 1) rifiuta('next_id');
  const ids = new Set();
  world.organisms = d.organismi.map(o => {
    if (!Array.isArray(o) || o.length !== 9) rifiuta('organismo');
    const [identity, x, y, energy, age, cooldown, threshold, efficiency, last_action] = o;
    if (!Number.isInteger(identity) || identity < 1 || identity >= d.next_id || ids.has(identity)) rifiuta('id organismo');
    ids.add(identity);
    if (!Number.isInteger(x) || !Number.isInteger(y) || !habitat.cells[y]?.[x]?.suitable) rifiuta('organismo fuori dalla mask');
    if (!finito(energy) || energy <= 0 || energy > p.energy_cap) rifiuta('energia');
    if (!Number.isInteger(age) || age < 0 || age >= p.max_age) rifiuta('eta');
    if (!Number.isInteger(cooldown) || cooldown < 0 || cooldown > p.cooldown) rifiuta('cooldown');
    if (!finito(threshold) || threshold < 2 || threshold > 18) rifiuta('threshold');
    if (!finito(efficiency) || efficiency < 0.5 || efficiency > 1.5) rifiuta('efficiency');
    if (!AZIONI.has(last_action)) rifiuta('azione');
    return { identity, x, y, energy, age, cooldown, threshold, efficiency, last_action };
  });
  world.next_id = d.next_id;
  world.ticks = d.passo;
  return { habitat, world, seed: d.seed };
}

/**
 * Vista di sola lettura per il client Godot: solo cio' che e' osservabile.
 * Niente energia, tratti, eta', stato del PRNG o cibo: il client non riceve nulla che gli serva per barare.
 */
export function vistaClient(zona, { area, tickMondo = null, limite = 64 } = {}) {
  const { habitat, world } = zona;
  let [x0, y0, x1, y1] = [0, 0, habitat.width - 1, habitat.height - 1];
  if (area !== undefined) {
    if (!Array.isArray(area) || area.length !== 4 || !area.every(Number.isInteger)) throw new ErroreFauna('richiesta_non_valida', 'area = [x0, y0, x1, y1] in celle');
    [x0, y0, x1, y1] = area;
    if (x0 > x1 || y0 > y1) throw new ErroreFauna('richiesta_non_valida', 'area vuota');
  }
  const max = Math.min(64, Math.max(1, Number.isInteger(limite) ? limite : 64));
  const dentro = world.organisms.filter(o => o.x >= x0 && o.x <= x1 && o.y >= y0 && o.y <= y1);
  return {
    fauna_schema_version: FAUNA_SCHEMA_VERSION, specie: SPECIE, zone_id: habitat.zone_id,
    habitat_sha256: habitat.sha256, sintetico: habitat.synthetic, passo: world.ticks, tick_mondo: tickMondo,
    totale_in_area: dentro.length,
    entita: dentro.slice(0, max).map(o => ({
      id: o.identity, cella: [o.x, o.y], posizione_mondo: cellaInMondo(habitat, o.x, o.y),
      bioma: habitat.cells[o.y][o.x].biome, azione: o.last_action,
    })),
  };
}
