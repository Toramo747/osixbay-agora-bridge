/**
 * Replica minima, solo per i test, del contratto di tempo di Mondo.avanza() osservato nel Worker genesis-world-test
 * (tick derivato dall'orologio, al massimo maxTick per allarme, una sola transactionSync). NON e' il Worker.
 * Mostra dove si aggancia la fauna: dentro la stessa transazione, dopo l'ultimo tick.
 */
import { inizializzaFauna, faunaAvanza } from '../persistenza.mjs';

export const SCHEMA_MONDO = [
  `CREATE TABLE IF NOT EXISTS meta (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS stato (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL, versione INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS eventi (id INTEGER PRIMARY KEY AUTOINCREMENT, tick INTEGER NOT NULL, ts INTEGER NOT NULL, tipo TEXT NOT NULL, origine TEXT NOT NULL, dati TEXT NOT NULL)`,
];

export class MondoFinto {
  constructor(storage, habitat, cfg, { tickMs = 60_000, maxTick = 20, t0 = 1_000_000 } = {}) {
    Object.assign(this, { storage, sql: storage.sql, habitat, cfg, tickMs, maxTick });
    for (const q of SCHEMA_MONDO) this.sql.exec(q);
    if (this.meta('tick') === null) { this.setMeta('tick', 0); this.setMeta('ultimo_ms', t0); }
    if (cfg.attiva) inizializzaFauna(this.sql);
    this.guastoPrimaDelCommit = false;
    this.ultimaFauna = null;
  }
  meta(k) { const r = this.sql.exec('SELECT valore FROM meta WHERE chiave = ?', k).toArray()[0]; return r ? r.valore : null; }
  num(k) { return Number(this.meta(k)); }
  setMeta(k, v) { this.sql.exec('INSERT INTO meta (chiave, valore) VALUES (?, ?) ON CONFLICT(chiave) DO UPDATE SET valore = excluded.valore', k, String(v)); }

  /** Come Mondo.avanza(ora): restituisce l'arretrato di tick del mondo. */
  avanza(ora) {
    const dovuti = ora <= this.num('ultimo_ms') ? 0 : Math.floor((ora - this.num('ultimo_ms')) / this.tickMs);
    const n = Math.min(dovuti, this.maxTick);
    if (n === 0) return 0;                       // come nel Worker: alarm doppio o anticipato => nessuna transazione
    this.storage.transactionSync(() => {
      const tick = this.num('tick') + n;
      this.setMeta('tick', tick);
      this.setMeta('ultimo_ms', this.num('ultimo_ms') + n * this.tickMs);
      if (this.cfg.attiva) this.ultimaFauna = faunaAvanza(this.sql, this.habitat, tick, this.cfg);
      if (this.guastoPrimaDelCommit) throw new Error('guasto simulato tra calcolo e commit');
    });
    return dovuti - n;
  }
}
