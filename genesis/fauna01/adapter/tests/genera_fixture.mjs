/**
 * Genera fixtures/habitat_sintetico_v1.json. FIXTURE SINTETICA DI TEST: non e' la scena demo, non e' canonica,
 * i valori di cibo e le coordinate sono inventati apposta per esercitare l'adapter. Deterministica (nessun random).
 * Uso: node genesis/fauna01/adapter/tests/genera_fixture.mjs
 */
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { hashHabitat } from '../habitat.mjs';

export function habitatSintetico({ w = 24, h = 24, zone_id = 'sintetico-test-01', spawn = [[7, 7], [8, 6]] } = {}) {
  const rumore = (x, y) => (((x * 73856093) ^ (y * 19349663)) >>> 0) % 7;
  const playable = [], biome = [], cap = [], ini = [], reg = [], danger = [];
  // legenda: F bosco, S riva, M affioramento, W acqua aperta (non percorribile), B roccia nuda (percorribile ma non idonea a F01), X fuori zona
  const cibo = { F: [4, 4, 0.15], S: [3, 2, 0.1], M: [1, 1, 0.02], W: [0, 0, 0], B: [0, 0, 0], X: [0, 0, 0] };
  for (let y = 0; y < h; y++) {
    let rp = '', rb = '';
    const rc = [], ri = [], rr = [], rd = [];
    for (let x = 0; x < w; x++) {
      const dx = (x - (w - 1) / 2) / (w / 2), dy = (y - (h - 1) / 2) / (h / 2);
      const dentro = dx * dx + dy * dy + (rumore(x, y) - 3) * 0.035 < 0.86;   // bordo irregolare, non un quadrato
      let b = 'X';
      if (dentro) {
        if (x + y < w * 0.55) b = 'F';
        else if (x - y > w * 0.25) b = 'M';
        else if (y > h * 0.7 && x > w * 0.3 && x < w * 0.7) b = 'W';
        else if (Math.abs(x + y - w) <= 3) b = 'S';
        else b = rumore(x, y) === 0 ? 'B' : 'F';
      }
      rp += dentro && b !== 'W' ? '1' : '0';
      rb += b;
      rc.push(cibo[b][0]); ri.push(cibo[b][1]); rr.push(cibo[b][2]); rd.push(0);
    }
    playable.push(rp); biome.push(rb); cap.push(rc); ini.push(ri); reg.push(rr); danger.push(rd);
  }
  const h0 = {
    schema: 'osixbay.genesis.habitat.demo-export', version: 1, zone_id, synthetic: true,
    avviso: 'FIXTURE SINTETICA DI TEST - NON e\' la scena demo, NON canonica, valori inventati per i test',
    source: { kind: 'synthetic_fixture', generator: 'genesis/fauna01/adapter/tests/genera_fixture.mjs' },
    grid: { width: w, height: h, cell_size_m: 2.5, origin_world: [0, 0] },
    biomes: { F: 'alien_forest', S: 'wet_shore', M: 'mineral_outcrop', W: 'open_water', B: 'bare_rock', X: 'outside' },
    layers: { playable, biome, food_capacity: cap, food_initial: ini, food_regrowth: reg, danger },
    species: { F01: { suitable_biomes: ['alien_forest', 'wet_shore', 'mineral_outcrop'], spawn } },
  };
  return { ...h0, sha256: hashHabitat(h0) };
}

/** Ricalcola l'hash dopo una modifica di test. */
export const rifirma = (h) => { const { sha256, ...r } = h; return { ...r, sha256: hashHabitat(r) }; };

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const out = fileURLToPath(new URL('../fixtures/habitat_sintetico_v1.json', import.meta.url));
  writeFileSync(out, JSON.stringify(habitatSintetico(), null, 1) + '\n');
  console.log('scritto', out);
}
