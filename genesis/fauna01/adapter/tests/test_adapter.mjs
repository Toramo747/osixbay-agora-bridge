/** Test dell'adapter puro (habitat + zona). Tutti gli habitat qui sono FIXTURE SINTETICHE dichiarate. */
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { sha256hex, canonico } from '../sha256.mjs';
import { importaHabitat, hashHabitat, ErroreHabitat, cellaInMondo, MAX_CELLE } from '../habitat.mjs';
import { creaZona, passoZona, snapshotZona, ripristinaZona, vistaClient, ErroreFauna, FAUNA_SCHEMA_VERSION } from '../zona.mjs';
import { habitatSintetico, rifirma } from './genera_fixture.mjs';

const grezzo = () => JSON.parse(readFileSync(new URL('../fixtures/habitat_sintetico_v1.json', import.meta.url), 'utf8'));
const SI = { consentiSintetico: true };
const habitat = () => importaHabitat(grezzo(), SI);
const modifica = (f) => { const h = grezzo(); f(h); return rifirma(h); };
const tutte = (h, nome, v) => { h.layers[nome] = h.layers[nome].map(r => r.map(() => v)); };
const codice = (c) => (e) => e instanceof ErroreFauna && e.codice === c;
const rimonta = (h, s, f) => { const d = JSON.parse(s.testo); f(d); return () => ripristinaZona(h, canonico(d)); };

test('sha256 sincrono identico a node:crypto', () => {
  for (const t of ['', 'abc', 'è€🙂', 'x'.repeat(55), 'x'.repeat(56), 'x'.repeat(64), 'y'.repeat(100_000)]) {
    assert.equal(sha256hex(t), createHash('sha256').update(t, 'utf8').digest('hex'));
  }
});

test('fixture: file uguale al generatore, hash valido, dichiarata sintetica', () => {
  assert.deepStrictEqual(grezzo(), habitatSintetico());
  const g = grezzo();
  assert.equal(g.synthetic, true);
  assert.equal(g.source.kind, 'synthetic_fixture');
  assert.equal(hashHabitat(g), g.sha256);
});

test('una fixture sintetica e\' rifiutata se non esplicitamente consentita (integrazione reale)', () => {
  assert.throws(() => importaHabitat(grezzo()), ErroreHabitat);
  assert.throws(() => importaHabitat(grezzo(), { consentiSintetico: false }), /fixture sintetica rifiutata/);
});

test('un export dichiarato reale richiede scena, commit, data ed exporter', () => {
  const finto = modifica(h => { h.synthetic = false; h.source = { kind: 'godot_export' }; });
  assert.throws(() => importaHabitat(finto), /source\.scene obbligatorio/);
  const incoerente = modifica(h => { h.synthetic = false; });
  assert.throws(() => importaHabitat(incoerente, SI), /incoerente/);
});

test('habitat malformati rifiutati', () => {
  const casi = {
    'hash manomesso': (() => { const h = grezzo(); h.layers.playable[5] = '1'.repeat(24); return h; })(),
    'riga corta': modifica(h => { h.layers.biome[0] = 'XXX'; }),
    'simbolo sconosciuto': modifica(h => { h.layers.biome[0] = 'Q' + h.layers.biome[0].slice(1); }),
    'cibo negativo': modifica(h => { h.layers.food_initial[7][7] = -1; }),
    'cibo NaN': modifica(h => { h.layers.food_capacity[7][7] = null; }),
    'scorta sopra capacita': modifica(h => { h.layers.food_initial[7][7] = 99; }),
    'spawn fuori griglia': modifica(h => { h.species.F01.spawn = [[99, 0]]; }),
    'spawn fuori mask': modifica(h => { h.species.F01.spawn = [[0, 0]]; }),
    'spawn in acqua': modifica(h => { h.species.F01.spawn = [[10, 18]]; }),
    'spawn su bioma non idoneo': modifica(h => { h.species.F01.spawn = [[9, 6]]; }),
    'spawn duplicato': modifica(h => { h.species.F01.spawn = [[7, 7], [7, 7]]; }),
    'troppe celle': modifica(h => { h.grid.width = 100; h.grid.height = 100; }),
    'schema': modifica(h => { h.schema = 'altro'; }),
    'versione': modifica(h => { h.version = 2; }),
    'nessuna cella adatta': modifica(h => { h.species.F01.suitable_biomes = []; }),
    'bioma idoneo inesistente': modifica(h => { h.species.F01.suitable_biomes = ['lava']; }),
    'origine': modifica(h => { h.grid.origin_world = [0]; }),
  };
  for (const [nome, h] of Object.entries(casi)) assert.throws(() => importaHabitat(h, SI), ErroreHabitat, nome);
  assert.ok(64 * 64 <= MAX_CELLE);
});

test('proiezione: suitable = playable AND bioma idoneo; cibo nullo fuori dall\'habitat', () => {
  const g = grezzo(), h = habitat();
  let adatte = 0;
  for (let y = 0; y < h.height; y++) for (let x = 0; x < h.width; x++) {
    const c = h.cells[y][x];
    const atteso = g.layers.playable[y][x] === '1' && g.species.F01.suitable_biomes.includes(g.biomes[g.layers.biome[y][x]]);
    assert.equal(c.suitable, atteso);
    if (!c.suitable) assert.deepStrictEqual([c.cap, c.food0, c.regrowth], [0, 0, 0]);
    adatte += atteso;
  }
  assert.equal(h.suitable_cells, adatte);
  assert.equal(h.cells[6][9].playable && !h.cells[6][9].suitable, true);   // roccia nuda: percorribile ma non idonea
  assert.deepStrictEqual(cellaInMondo(h, 0, 0), [1.25, 1.25]);
  assert.deepStrictEqual(cellaInMondo(h, 7, 3), [18.75, 8.75]);
});

test('mask irregolare e bordo: 1500 passi x 5 seed, mai un organismo (o una nascita) fuori dalla mask', () => {
  const h = habitat();
  let nascite = 0, morti = 0, sulBordo = 0;
  const bordo = (x, y) => [[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => !h.cells[y + dy]?.[x + dx]?.suitable);
  for (const seed of [1, 2, 13, 42, 2026]) {
    const z = creaZona(h, { seed });
    let noti = new Set(z.world.organisms.map(o => o.identity));
    for (let i = 0; i < 1500; i++) {
      const r = passoZona(z);
      nascite += r.nati; morti += r.morti;
      for (const o of z.world.organisms) {
        assert.equal(h.cells[o.y][o.x].suitable, true, `seed ${seed} passo ${i}: organismo ${o.identity} fuori mask`);
        if (!noti.has(o.identity)) assert.equal(o.age, 0);
        if (bordo(o.x, o.y)) sulBordo++;
      }
      noti = new Set(z.world.organisms.map(o => o.identity));
      for (let y = 0; y < h.height; y++) for (let x = 0; x < h.width; x++) {
        if (!h.cells[y][x].suitable) assert.equal(z.world.cells[y][x].food, 0);
      }
    }
  }
  assert.ok(nascite > 0 && morti > 0 && sulBordo > 0, `il test deve esercitare nascite (${nascite}), morti (${morti}) e celle di bordo (${sulBordo})`);
});

test('biome mismatch: organismo circondato da bioma non idoneo non esce mai dalla sua cella', () => {
  const h = importaHabitat(modifica(g => {
    g.layers.biome = g.layers.biome.map(r => r.replace(/[FSM]/g, 'B'));
    g.layers.biome[7] = g.layers.biome[7].slice(0, 7) + 'F' + g.layers.biome[7].slice(8);
    g.species.F01.spawn = [[7, 7]];
  }), SI);
  assert.equal(h.suitable_cells, 1);
  const z = creaZona(h, { seed: 5 });
  for (let i = 0; i < 300; i++) { passoZona(z); for (const o of z.world.organisms) assert.deepStrictEqual([o.x, o.y], [7, 7]); }
});

test('risorse zero: nessun cibo creato, nessuna nascita, estinzione per fame', () => {
  const h = importaHabitat(modifica(g => { for (const n of ['food_capacity', 'food_initial', 'food_regrowth']) tutte(g, n, 0); }), SI);
  const z = creaZona(h, { seed: 9 });
  let nati = 0;
  for (let i = 0; i < 60; i++) {
    nati += passoZona(z).nati;
    assert.equal(z.world.cells.flat().reduce((a, c) => a + c.food, 0), 0);
  }
  assert.equal(nati, 0);
  assert.equal(z.world.organisms.length, 0);
});

test('risorse finite non rinnovabili: il cibo totale non cresce mai e la popolazione si estingue', () => {
  const h = importaHabitat(modifica(g => tutte(g, 'food_regrowth', 0)), SI);
  const z = creaZona(h, { seed: 9 });
  const totale = () => z.world.cells.flat().reduce((a, c) => a + c.food, 0);
  let prima = totale(), nati = 0;
  for (let i = 0; i < 4000 && z.world.organisms.length; i++) {
    nati += passoZona(z).nati;
    const ora = totale();
    assert.ok(ora <= prima);
    prima = ora;
  }
  assert.ok(nati > 0);
  assert.equal(z.world.organisms.length, 0);
});

test('ricrescita per cella: parte dalla scorta reale e si ferma alla capacita\' della cella', () => {
  // (12,0) e' una cella di bosco isolata dal bordo irregolare: nessun organismo puo' raggiungerla.
  const h = importaHabitat(modifica(g => { g.layers.food_initial[0][12] = 0; }), SI);
  const z = creaZona(h, { seed: 3 });
  assert.equal(z.world.cells[0][12].food, 0);
  for (let i = 0; i < 10; i++) passoZona(z);
  assert.ok(Math.abs(z.world.cells[0][12].food - 1.5) < 1e-9);
  for (let i = 0; i < 400; i++) passoZona(z);
  assert.equal(z.world.cells[0][12].food, 4);
  for (let y = 0; y < h.height; y++) for (let x = 0; x < h.width; x++) assert.ok(z.world.cells[y][x].food <= h.cells[y][x].cap);
});

test('predazione assente e pericolo zero: nessuna fuga', () => {
  const z = creaZona(habitat(), { seed: 13 });
  for (let i = 0; i < 800; i++) { passoZona(z); assert.ok(z.world.organisms.every(o => o.last_action !== 'flee')); }
});

test('pericolo dichiarato dall\'export: fuga verso la cella meno pericolosa', () => {
  const h = importaHabitat(modifica(g => { g.layers.danger[7][7] = 0.9; }), SI);
  const z = creaZona(h, { seed: 13 });
  passoZona(z);
  const a = z.world.organisms.find(o => o.identity === 1);
  assert.equal(a.last_action, 'flee');
  assert.notDeepStrictEqual([a.x, a.y], [7, 7]);
});

test('mortalita\' per eta\' e tetto di popolazione', () => {
  const z = creaZona(habitat(), { seed: 13, parametri: { max_age: 30, max_population: 12 } });
  let morti = 0;
  for (let i = 0; i < 600; i++) {
    morti += passoZona(z).morti;
    assert.ok(z.world.organisms.length <= 12);
    assert.ok(z.world.organisms.every(o => o.age < 30));
  }
  assert.ok(morti > 0);
});

test('riproduzione: costo energetico e cooldown rispettati per ogni genitore', () => {
  const z = creaZona(habitat(), { seed: 13 });
  const p = z.world.parameters, ultima = new Map();
  let riproduzioni = 0;
  for (let i = 1; i <= 600; i++) {
    const idPrima = new Set(z.world.organisms.map(o => o.identity));
    passoZona(z);
    for (const o of z.world.organisms) {
      if (o.last_action !== 'reproduce') continue;
      riproduzioni++;
      assert.equal(o.cooldown, p.cooldown);
      // il genitore aveva almeno birth_threshold e ha pagato figlio + costo: l'energia non nasce dal nulla
      assert.ok(o.energy >= p.birth_threshold - p.child_energy - p.birth_cost - 1e-9);
      assert.ok(o.energy <= p.energy_cap - p.child_energy - p.birth_cost + 1e-9);
      if (ultima.has(o.identity)) assert.ok(i - ultima.get(o.identity) >= p.cooldown, 'riproduzione durante il cooldown');
      ultima.set(o.identity, i);
    }
    for (const o of z.world.organisms) if (!idPrima.has(o.identity)) assert.equal(o.energy, p.child_energy);
  }
  assert.ok(riproduzioni > 5);
});

test('snapshot: ripresa identica al mondo mai interrotto', () => {
  const h = habitat();
  const a = creaZona(h, { seed: 77 });
  for (let i = 0; i < 120; i++) passoZona(a);
  const s = snapshotZona(a);
  let b = ripristinaZona(h, s.testo, s.sha256);
  assert.equal(snapshotZona(b).sha256, s.sha256);
  for (let i = 0; i < 300; i++) {
    assert.deepStrictEqual(passoZona(a), passoZona(b));
    if (i % 50 === 0) { const t = snapshotZona(b); b = ripristinaZona(h, t.testo, t.sha256); }   // ripresa ripetuta
  }
  assert.equal(snapshotZona(a).sha256, snapshotZona(b).sha256);
});

test('seed replay: stesso seed => stesso hash; seed diverso => storia diversa', () => {
  const h = habitat();
  const corsa = (seed) => { const z = creaZona(h, { seed }); for (let i = 0; i < 500; i++) passoZona(z); return snapshotZona(z).sha256; };
  assert.equal(corsa(13), corsa(13));
  assert.equal(corsa('13'), corsa(13n));
  assert.notEqual(corsa(13), corsa(14));
  for (const cattivo of [-1, 1.5, 'abc', 2n ** 64n, null]) assert.throws(() => creaZona(h, { seed: cattivo }), codice('seed_non_valido'));
});

test('snapshot corrotti o manomessi rifiutati', () => {
  const h = habitat();
  const z = creaZona(h, { seed: 1 });
  for (let i = 0; i < 40; i++) passoZona(z);
  const s = snapshotZona(z);
  assert.throws(() => ripristinaZona(h, s.testo.replace('"passo":40', '"passo":41'), s.sha256), codice('snapshot_corrotto'));
  assert.throws(() => ripristinaZona(h, s.testo.slice(0, -5)), codice('snapshot_non_valido'));
  assert.throws(() => ripristinaZona(h, 'x'.repeat(500_000)), codice('snapshot_non_valido'));
  assert.throws(() => ripristinaZona(h, 'null'), codice('snapshot_non_valido'));
  const nv = {
    'organismo fuori mask': d => { d.organismi[0][1] = 0; d.organismi[0][2] = 0; },
    'organismo in acqua': d => { d.organismi[0][1] = 10; d.organismi[0][2] = 18; },
    'energia oltre il tetto': d => { d.organismi[0][3] = 9999; },
    'energia negativa': d => { d.organismi[0][3] = -1; },
    'id duplicato': d => { d.organismi.push([...d.organismi[0]]); },
    'id >= next_id': d => { d.organismi[0][0] = d.next_id; },
    'azione inventata': d => { d.organismi[0][8] = 'vola'; },
    'cibo negativo': d => { d.cibo[0] = -0.1; },
    'cibo oltre la capacita': d => { d.cibo[0] = 1e6; },
    'cibo: celle mancanti': d => { d.cibo.pop(); },
    'rng non numerico': d => { d.rng_state = '12x'; },
    'rng oltre 64 bit': d => { d.rng_state = '99999999999999999999'; },
    'passo negativo': d => { d.passo = -1; },
    'parametri invalidi': d => { d.parametri.basal_cost = -5; },
    'troppi organismi': d => { d.parametri.max_population = 1; d.organismi.push([d.next_id - 1, 7, 7, 5, 0, 0, 14, 1, 'rest']); },
    'specie': d => { d.specie = 'F02'; },
  };
  for (const [nome, f] of Object.entries(nv)) assert.throws(rimonta(h, s, f), codice('snapshot_non_valido'), nome);
  assert.throws(rimonta(h, s, d => { d.habitat_sha256 = '0'.repeat(64); }), codice('habitat_diverso'));
  const altro = importaHabitat(habitatSintetico({ zone_id: 'sintetico-test-02' }), SI);
  assert.throws(() => ripristinaZona(altro, s.testo, s.sha256), codice('habitat_diverso'));
});

test('versionamento: versione futura rifiutata, versione assente o zero rifiutata', () => {
  const h = habitat();
  const s = snapshotZona(creaZona(h, { seed: 1 }));
  assert.equal(JSON.parse(s.testo).fauna_schema_version, FAUNA_SCHEMA_VERSION);
  assert.throws(rimonta(h, s, d => { d.fauna_schema_version = FAUNA_SCHEMA_VERSION + 1; }), codice('versione_futura'));
  assert.throws(rimonta(h, s, d => { d.fauna_schema_version = 0; }), codice('snapshot_non_valido'));
  assert.throws(rimonta(h, s, d => { delete d.fauna_schema_version; }), codice('snapshot_non_valido'));
});

test('vista client: solo dati osservabili, area di interesse, limite, nessun fantasma', () => {
  const h = habitat();
  const z = creaZona(h, { seed: 13 });
  for (let i = 0; i < 200; i++) passoZona(z);
  const v = vistaClient(z, { tickMondo: 999 });
  assert.equal(v.sintetico, true);
  assert.equal(v.passo, 200);
  assert.ok(v.entita.length > 2);
  const vivi = new Set(z.world.organisms.map(o => o.identity));
  for (const e of v.entita) {
    assert.deepStrictEqual(Object.keys(e).sort(), ['azione', 'bioma', 'cella', 'id', 'posizione_mondo']);
    assert.ok(vivi.has(e.id));
    assert.deepStrictEqual(e.posizione_mondo, cellaInMondo(h, ...e.cella));
  }
  assert.ok(!/energ|threshold|efficien|rng|seed|cibo/.test(JSON.stringify(v).replace('"habitat_sha256"', '')));
  const area = vistaClient(z, { area: [0, 0, 8, 8] });
  assert.ok(area.entita.every(e => e.cella[0] <= 8 && e.cella[1] <= 8));
  assert.equal(area.totale_in_area, z.world.organisms.filter(o => o.x <= 8 && o.y <= 8).length);
  assert.equal(vistaClient(z, { limite: 1 }).entita.length, 1);
  assert.equal(vistaClient(z, { limite: 1e9 }).entita.length <= 64, true);
  assert.throws(() => vistaClient(z, { area: [5, 5, 1, 1] }), codice('richiesta_non_valida'));
  assert.throws(() => vistaClient(z, { area: 'tutto' }), codice('richiesta_non_valida'));
});
