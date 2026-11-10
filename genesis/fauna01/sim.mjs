/** FAUNA-02 F01: pure JavaScript/Cloudflare-compatible reference engine. No I/O. */
const MASK = (1n << 64n) - 1n;

export class Parameters {
  constructor(input = {}) {
    Object.assign(this, {
      capacity: 4.0, regrowth: 0.15, food_per_tick: 1.2,
      food_energy: 2.5, basal_cost: 0.55, movement_cost: 0.2,
      birth_threshold: 13.0, child_energy: 4.0, birth_cost: 1.0,
      energy_cap: 20.0, max_age: 120, max_population: 50, cooldown: 6,
    }, input);
    const p = this;
    const numeric = Object.values(this).every(v => typeof v === 'number' && Number.isFinite(v));
    if (!numeric || !(p.capacity > 0 && p.regrowth >= 0 && p.regrowth <= p.capacity &&
        p.food_per_tick > 0 && p.food_energy > 0 && p.basal_cost > 0 && p.movement_cost >= 0 &&
        p.child_energy > 0 && p.child_energy < p.birth_threshold &&
        p.birth_threshold <= p.energy_cap && p.birth_cost >= 0 &&
        p.child_energy + p.birth_cost < p.birth_threshold && p.max_age > 0 &&
        Number.isInteger(p.max_age) && Number.isInteger(p.max_population) && p.max_population > 0 &&
        Number.isInteger(p.cooldown) && p.cooldown >= 0)) {
      throw new Error('invalid parameters');
    }
  }
}

export class World {
  constructor(habitat, seed = 1, parameters = new Parameters()) {
    if (!Array.isArray(habitat) || !habitat.length ||
        !Array.isArray(habitat[0]) || !habitat[0].length ||
        !habitat.every(row => Array.isArray(row) && row.length === habitat[0].length)) {
      throw new Error('habitat must be rectangular and nonempty');
    }
    const bigintSeed = typeof seed === 'bigint' ? seed :
      (typeof seed === 'number' && Number.isSafeInteger(seed)) ? BigInt(seed) : null;
    if (bigintSeed === null) throw new Error('invalid seed');
    this.parameters = parameters instanceof Parameters ? parameters : new Parameters(parameters);
    this.width = habitat[0].length;
    this.height = habitat.length;
    this.cells = habitat.map(row => row.map(v => ({suitable: Boolean(v), food: v ? this.parameters.capacity : 0, danger: 0})));
    this.organisms = [];
    this.next_id = 1;
    this.ticks = 0;
    this.rng_state = bigintSeed & MASK;
  }

  random() {
    this.rng_state = (this.rng_state * 6364136223846793005n + 1442695040888963407n) & MASK;
    return Number(this.rng_state >> 11n) / 2 ** 53;
  }

  add_organism(x, y, energy = 9, threshold = 14, efficiency = 1) {
    if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0 ||
        x >= this.width || y >= this.height || !this.cells[y][x].suitable) {
      throw new Error('unsuitable habitat');
    }
    if (!(energy > 0 && energy <= this.parameters.energy_cap &&
          threshold >= 2 && threshold <= 18 && efficiency >= 0.5 && efficiency <= 1.5)) {
      throw new Error('invalid organism parameters');
    }
    if (this.organisms.length >= this.parameters.max_population) throw new Error('population full');
    const organism = {identity: this.next_id, x, y, energy, age: 0, cooldown: 0,
      threshold, efficiency, last_action: 'rest'};
    this.next_id++;
    this.organisms.push(organism);
    return organism;
  }

  neighbors(a) {
    const options = [[a.x, a.y], [a.x + 1, a.y], [a.x - 1, a.y], [a.x, a.y + 1], [a.x, a.y - 1]];
    return options.filter(([x, y]) => x >= 0 && y >= 0 && x < this.width && y < this.height && this.cells[y][x].suitable);
  }

  step() {
    const p = this.parameters, births = [], survivors = [];
    let deaths = 0;
    for (const a of [...this.organisms].sort((x, y) => x.identity - y.identity)) {
      a.age += 1;
      a.cooldown = Math.max(0, a.cooldown - 1);
      if (!this.cells[a.y][a.x].suitable) { deaths++; continue; }
      a.energy = Math.max(0, a.energy - p.basal_cost);
      if (a.energy <= 0 || a.age >= p.max_age) { deaths++; continue; }
      const nearby = this.neighbors(a);
      if (this.cells[a.y][a.x].danger > 0.5) {
        let chosen = nearby[0];
        for (const xy of nearby.slice(1)) {
          const [x, y] = xy, [cx, cy] = chosen;
          const cell = this.cells[y][x], current = this.cells[cy][cx];
          if (cell.danger < current.danger || (cell.danger === current.danger &&
               (cell.food > current.food || (cell.food === current.food &&
               (y < cy || (y === cy && x < cx)))))) chosen = xy;
        }
        a.last_action = 'flee';
        if (chosen[0] !== a.x || chosen[1] !== a.y) {
          a.energy = Math.max(0, a.energy - p.movement_cost);
          [a.x, a.y] = chosen;
        }
      } else if (a.energy < a.threshold) {
        a.last_action = 'forage';
        let chosen = nearby[0];
        for (const xy of nearby.slice(1)) {
          const [x, y] = xy, [cx, cy] = chosen;
          const cell = this.cells[y][x], current = this.cells[cy][cx];
          if (cell.food > current.food || (cell.food === current.food &&
               (y < cy || (y === cy && x < cx)))) chosen = xy;
        }
        if (chosen[0] !== a.x || chosen[1] !== a.y) {
          a.energy = Math.max(0, a.energy - p.movement_cost);
          [a.x, a.y] = chosen;
        }
        if (a.energy <= 0) { deaths++; continue; }
        const cell = this.cells[a.y][a.x];
        const eaten = Math.min(p.food_per_tick, cell.food);
        cell.food = Math.max(0, cell.food - eaten);
        a.energy = Math.min(p.energy_cap, a.energy + eaten * p.food_energy * a.efficiency);
      } else {
        a.last_action = 'rest';
      }
      if (a.energy <= 0) { deaths++; continue; }
      if (a.energy >= p.birth_threshold && a.cooldown === 0 &&
          this.organisms.length - deaths + births.length < p.max_population) {
        a.energy -= p.child_energy + p.birth_cost;
        a.cooldown = p.cooldown;
        a.last_action = 'reproduce';
        const threshold = Math.min(18, Math.max(2, a.threshold + this.random() - 0.5));
        const efficiency = Math.min(1.5, Math.max(0.5, a.efficiency + (this.random() - 0.5) * 0.1));
        births.push({identity: this.next_id, x: a.x, y: a.y, energy: p.child_energy,
          age: 0, cooldown: 0, threshold, efficiency, last_action: 'rest'});
        this.next_id++;
      }
      survivors.push(a);
    }
    this.organisms = [...survivors, ...births].slice(0, p.max_population);
    for (const row of this.cells) for (const cell of row) {
      cell.food = cell.suitable ? Math.min(p.capacity, cell.food + p.regrowth) : 0;
    }
    this.ticks++;
    return {tick: this.ticks, alive: this.organisms.length,
      born: Math.max(0, this.organisms.length - survivors.length), died: deaths};
  }

  snapshot() {
    return JSON.stringify({version: 1, width: this.width, height: this.height,
      parameters: {...this.parameters}, cells: this.cells, organisms: this.organisms,
      next_id: this.next_id, ticks: this.ticks, rng_state: this.rng_state.toString()});
  }

  static from_snapshot(source) {
    const d = typeof source === 'string' ? JSON.parse(source) : source;
    if (d.version !== 1) throw new Error('unsupported snapshot');
    const w = new World(d.cells.map(row => row.map(c => c.suitable)),
      BigInt(d.rng_state), new Parameters(d.parameters));
    if (w.width !== d.width || w.height !== d.height) throw new Error('snapshot dimensions mismatch');
    w.cells = d.cells.map(row => row.map(c => ({...c})));
    w.organisms = d.organisms.map(o => ({...o}));
    w.next_id = d.next_id;
    w.ticks = d.ticks;
    return w;
  }
}

export function demonstration(seed = 13, ticks = 80) {
  const habitat = Array.from({length: 8}, (_, y) => Array.from({length: 8}, (_, x) => (x + y) % 7 !== 0));
  const world = new World(habitat, seed);
  world.add_organism(3, 3);
  world.add_organism(4, 2);
  const tally = {born: 0, died: 0};
  for (let i = 0; i < ticks; i++) {
    const r = world.step(); tally.born += r.born; tally.died += r.died;
  }
  return {seed, ticks: world.ticks, alive: world.organisms.length, ...tally,
    remaining_food: Math.round(world.cells.flat().reduce((a, c) => a + c.food, 0) * 1e5) / 1e5};
}
