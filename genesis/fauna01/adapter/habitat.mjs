/**
 * Contratto di importazione dell'habitat demo (World/Godot -> fauna F01), versione 1.
 * Questo modulo NON genera habitat: convalida un export e lo proietta in `suitable = playable AND suitable_for_f01`.
 * Vedi CONTRATTO_HABITAT.md. Nessun I/O.
 */
import { sha256hex, canonico } from './sha256.mjs';

export const SCHEMA_HABITAT = 'osixbay.genesis.habitat.demo-export';
export const VERSIONE_HABITAT = 1;
export const MAX_CELLE = 4096;            // tetto di CPU/dimensione snapshot: vedi bench in INTEGRAZIONE_WORKER.md
export const MAX_LATO = 256;
const ID = /^[a-z0-9][a-z0-9_.-]{0,63}$/;
const SHA = /^[0-9a-f]{64}$/;
const PROVENIENZE = new Set(['godot_export', 'synthetic_fixture']);

export class ErroreHabitat extends Error {}
const rifiuta = (m) => { throw new ErroreHabitat(`habitat non valido: ${m}`); };
const finito = (n) => typeof n === 'number' && Number.isFinite(n);

/** Hash dell'export senza il campo sha256: identifica in modo univoco la versione dell'habitat. */
export function hashHabitat(h) {
  const { sha256, ...resto } = h;
  return sha256hex(canonico(resto));
}

/**
 * Convalida un export e restituisce l'habitat proiettato (immutabile).
 * `consentiSintetico` deve essere esplicitamente true per accettare una fixture sintetica: mai in integrazione reale.
 */
export function importaHabitat(h, { consentiSintetico = false } = {}) {
  if (!h || typeof h !== 'object' || Array.isArray(h)) rifiuta('deve essere un oggetto');
  if (h.schema !== SCHEMA_HABITAT) rifiuta('schema sconosciuto');
  if (h.version !== VERSIONE_HABITAT) rifiuta('versione non supportata');
  if (typeof h.zone_id !== 'string' || !ID.test(h.zone_id)) rifiuta('zone_id');
  const s = h.source;
  if (!s || typeof s !== 'object' || !PROVENIENZE.has(s.kind)) rifiuta('source.kind');
  if (typeof h.synthetic !== 'boolean') rifiuta('synthetic deve essere booleano');
  if (h.synthetic !== (s.kind === 'synthetic_fixture')) rifiuta('synthetic incoerente con source.kind');
  if (h.synthetic && !consentiSintetico) rifiuta('fixture sintetica rifiutata: serve un export reale della scena demo');
  if (!h.synthetic) {
    for (const k of ['scene', 'commit', 'exported_at', 'exporter']) {
      if (typeof s[k] !== 'string' || !s[k]) rifiuta(`source.${k} obbligatorio per un export reale`);
    }
  }
  if (typeof h.sha256 !== 'string' || !SHA.test(h.sha256)) rifiuta('sha256 mancante');
  if (hashHabitat(h) !== h.sha256) rifiuta('sha256 non corrisponde al contenuto');

  const g = h.grid;
  if (!g || typeof g !== 'object') rifiuta('grid');
  const { width: w, height: hh, cell_size_m: lato, origin_world: o } = g;
  if (!Number.isInteger(w) || !Number.isInteger(hh) || w < 1 || hh < 1 || w > MAX_LATO || hh > MAX_LATO) rifiuta('dimensioni griglia');
  if (w * hh > MAX_CELLE) rifiuta(`troppe celle (max ${MAX_CELLE})`);
  if (!finito(lato) || lato <= 0) rifiuta('cell_size_m');
  if (!Array.isArray(o) || o.length !== 2 || !o.every(finito)) rifiuta('origin_world deve essere [x, z]');

  const biomi = h.biomes;
  if (!biomi || typeof biomi !== 'object' || Array.isArray(biomi)) rifiuta('biomes');
  const simboli = Object.keys(biomi);
  if (!simboli.length || simboli.some(k => k.length !== 1 || typeof biomi[k] !== 'string' || !ID.test(biomi[k]))) rifiuta('legenda biomi');

  const righe = (nome, valido) => {
    const r = h.layers?.[nome];
    if (!Array.isArray(r) || r.length !== hh) rifiuta(`layer ${nome}: numero di righe`);
    for (const riga of r) {
      if (typeof riga !== 'string' || riga.length !== w) rifiuta(`layer ${nome}: larghezza riga`);
      for (const c of riga) if (!valido(c)) rifiuta(`layer ${nome}: simbolo sconosciuto`);
    }
    return r;
  };
  const playable = righe('playable', c => c === '0' || c === '1');
  const bioma = righe('biome', c => Object.hasOwn(biomi, c));

  const matrice = (nome, obbligatorio, max) => {
    const m = h.layers?.[nome];
    if (m === undefined && !obbligatorio) return null;
    if (!Array.isArray(m) || m.length !== hh) rifiuta(`layer ${nome}: numero di righe`);
    for (const riga of m) {
      if (!Array.isArray(riga) || riga.length !== w) rifiuta(`layer ${nome}: larghezza riga`);
      for (const v of riga) if (!finito(v) || v < 0 || v > max) rifiuta(`layer ${nome}: valore fuori intervallo`);
    }
    return m;
  };
  // Scorte di cibo REALI per cella: capacita' massima, scorta iniziale e ricrescita per tick. Zero e' un valore lecito.
  const capacita = matrice('food_capacity', true, 1e6);
  const scorta = matrice('food_initial', true, 1e6);
  const ricrescita = matrice('food_regrowth', true, 1e6);
  const pericolo = matrice('danger', false, 1);

  const sp = h.species?.F01;
  if (!sp || typeof sp !== 'object') rifiuta('species.F01 mancante');
  if (!Array.isArray(sp.suitable_biomes) || sp.suitable_biomes.some(b => !Object.values(biomi).includes(b))) rifiuta('species.F01.suitable_biomes');
  const idonei = new Set(sp.suitable_biomes);
  if (!Array.isArray(sp.spawn) || sp.spawn.length < 1 || sp.spawn.length > 50) rifiuta('species.F01.spawn');

  const celle = [];
  let adatte = 0;
  for (let y = 0; y < hh; y++) {
    const riga = [];
    for (let x = 0; x < w; x++) {
      const gioc = playable[y][x] === '1';
      const nome = biomi[bioma[y][x]];
      const adatta = gioc && idonei.has(nome);
      if (scorta[y][x] > capacita[y][x]) rifiuta('food_initial supera food_capacity');
      if (adatta) adatte++;
      riga.push(Object.freeze({
        playable: gioc, biome: nome, suitable: adatta,
        // Fuori dall'habitat idoneo il cibo non esiste per F01: nessuna risorsa creata per farla sopravvivere.
        cap: adatta ? capacita[y][x] : 0, food0: adatta ? scorta[y][x] : 0, regrowth: adatta ? ricrescita[y][x] : 0,
        danger: pericolo ? pericolo[y][x] : 0,
      }));
    }
    celle.push(Object.freeze(riga));
  }
  if (adatte === 0) rifiuta('nessuna cella playable AND suitable_for_f01');
  const visti = new Set();
  for (const p of sp.spawn) {
    if (!Array.isArray(p) || p.length !== 2 || !p.every(Number.isInteger)) rifiuta('spawn: coordinate di cella intere');
    const [x, y] = p;
    if (x < 0 || y < 0 || x >= w || y >= hh) rifiuta('spawn fuori griglia');
    if (!celle[y][x].suitable) rifiuta('spawn fuori dalla mask playable AND suitable_for_f01');
    if (visti.has(`${x},${y}`)) rifiuta('spawn duplicato');
    visti.add(`${x},${y}`);
  }
  return Object.freeze({
    zone_id: h.zone_id, sha256: h.sha256, synthetic: h.synthetic, source_kind: s.kind,
    width: w, height: hh, cell_size_m: lato, origin_world: Object.freeze([...o]),
    cells: Object.freeze(celle), spawn: Object.freeze(sp.spawn.map(p => Object.freeze([...p]))), suitable_cells: adatte,
  });
}

/** Centro della cella in coordinate mondo Godot (x, z). Scala e offset vengono solo dall'export. */
export function cellaInMondo(habitat, x, y) {
  return [habitat.origin_world[0] + (x + 0.5) * habitat.cell_size_m, habitat.origin_world[1] + (y + 0.5) * habitat.cell_size_m];
}
