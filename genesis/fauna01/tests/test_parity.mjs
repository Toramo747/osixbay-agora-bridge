import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { World, Parameters, demonstration } from '../sim.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const PY_SCRIPT = `
import json, sys
from genesis.fauna01.sim import World, Parameters
c = json.loads(sys.stdin.read())
w = World(c['habitat'], seed=c['seed'], parameters=Parameters(**c.get('params', {})))
for o in c['animals']:
    w.add_organism(*o)
for cell in c.get('dangers', []):
    w.cells[cell[1]][cell[0]].danger=cell[2]
outputs=[]
for tick in range(c['ticks'] + 1):
    if tick in c['capture']:
        outputs.append(json.loads(w.snapshot()))
    if tick < c['ticks']:
        w.step()
print(json.dumps(outputs, sort_keys=True, separators=(',',':')))
`;

function comparable(c, js = true) {
  if (!js) {
    const out = spawnSync('python3', ['-c', PY_SCRIPT], {
      cwd: root, input: JSON.stringify(c), encoding: 'utf8',
      env: {...process.env, PYTHONPATH: root}, timeout: 30_000,
    });
    assert.equal(out.status, 0, out.stderr);
    return JSON.parse(out.stdout);
  }
  const w = new World(c.habitat, c.seed, new Parameters(c.params));
  for (const a of c.animals) w.add_organism(...a);
  for (const [x, y, danger] of c.dangers ?? []) w.cells[y][x].danger = danger;
  const outputs = [];
  for (let tick = 0; tick <= c.ticks; tick++) {
    if (c.capture.includes(tick)) outputs.push(JSON.parse(w.snapshot()));
    if (tick < c.ticks) w.step();
  }
  return outputs;
}

const habitat = Array.from({length: 8}, (_, y) =>
  Array.from({length: 8}, (_, x) => (x + y) % 7 !== 0));

for (const [label, additions] of [
  ['default', {}],
  ['danger', {dangers: [[3, 3, 0.8], [4, 2, 0.65]]}],
  ['rapid reproduction', {params: {birth_threshold: 9, cooldown: 1, max_population: 23}}],
  ['starvation', {params: {regrowth: 0, birth_threshold: 19, basal_cost: 1.3}}],
]) {
  test(`Python/JavaScript snapshot parity: ${label}`, () => {
    const config = {habitat, seed: 13, animals: [[3, 3], [4, 2]],
      capture: [0, 1, 2, 20, 80, 200], ticks: 200, ...additions};
    assert.deepStrictEqual(comparable(config, true), comparable(config, false));
  });
}

test('demonstration matches baseline', () => {
  assert.deepStrictEqual(demonstration(), {
    seed: 13, ticks: 80, alive: 14, born: 34, died: 22, remaining_food: 114.6,
  });
});

test('snapshot resumes identically in JavaScript', () => {
  const w = new World(habitat, 42);
  w.add_organism(2, 2);
  for (let i = 0; i < 50; i++) w.step();
  const resumed = World.from_snapshot(w.snapshot());
  for (let i = 0; i < 100; i++) {
    assert.deepStrictEqual(w.step(), resumed.step());
    assert.deepStrictEqual(JSON.parse(w.snapshot()), JSON.parse(resumed.snapshot()));
  }
});

test('population remains bounded at 2000 ticks', () => {
  const w = new World(habitat, 42, new Parameters({max_population: 100}));
  w.add_organism(2, 2);
  for (let i = 0; i < 2000; i++) {
    w.step();
    assert.ok(w.organisms.length <= 100);
    for (const row of w.cells) for (const c of row) {
      assert.ok(c.food >= 0 && c.food <= w.parameters.capacity);
    }
  }
});
