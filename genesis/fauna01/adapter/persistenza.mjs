/**
 * Persistenza della fauna nel Durable Object SQLite `MONDO`, in tabelle SEPARATE (prefisso fauna_).
 * Non legge ne' scrive meta/stato/eventi/programmati/nonce del World Engine.
 *
 * `faunaAvanza` va chiamata DENTRO la transactionSync di Mondo.avanza(), dopo l'ultimo tick del mondo:
 * cosi' mondo e fauna avanzano o falliscono insieme, e un alarm doppio non applica nulla due volte
 * (i passi dovuti derivano dal tick del mondo, non dal numero di chiamate).
 *
 * `sql` e' ctx.storage.sql del Durable Object (o lo shim di test con la stessa interfaccia exec()).
 */
import { creaZona, ripristinaZona, passoZona, snapshotZona, vistaClient, ErroreFauna, FAUNA_SCHEMA_VERSION } from './zona.mjs';

export const SCHEMA_FAUNA = [
  `CREATE TABLE IF NOT EXISTS fauna_meta (chiave TEXT PRIMARY KEY, valore TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS fauna_zona (zona TEXT PRIMARY KEY, specie TEXT NOT NULL, schema_version INTEGER NOT NULL,
     habitat_sha256 TEXT NOT NULL, seed TEXT NOT NULL, tick_nascita INTEGER NOT NULL, tick_mondo INTEGER NOT NULL,
     passo INTEGER NOT NULL, versione INTEGER NOT NULL, stato TEXT NOT NULL, motivo TEXT,
     snapshot TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS fauna_diario (zona TEXT NOT NULL, passo INTEGER NOT NULL, vivi INTEGER NOT NULL,
     nati INTEGER NOT NULL, morti INTEGER NOT NULL, PRIMARY KEY (zona, passo)) WITHOUT ROWID`,
];

// maxPassi 5: prudente rispetto al budget CPU per invocazione (vedi tests/bench.mjs); l'arretrato si smaltisce negli allarmi successivi.
export const PREDEFINITI_FAUNA = { tickOgni: 1, maxPassi: 5, diarioMax: 2880 };

/** Crea le tabelle fauna se mancano. Idempotente. Rifiuta un database scritto da uno schema piu' recente. */
export function inizializzaFauna(sql) {
  for (const q of SCHEMA_FAUNA) sql.exec(q);
  const r = sql.exec(`SELECT valore FROM fauna_meta WHERE chiave = 'schema_version'`).toArray()[0];
  if (!r) sql.exec(`INSERT INTO fauna_meta (chiave, valore) VALUES ('schema_version', ?)`, String(FAUNA_SCHEMA_VERSION));
  else if (Number(r.valore) > FAUNA_SCHEMA_VERSION) throw new ErroreFauna('versione_futura', 'schema fauna piu\' recente del codice');
}

/** Configurazione dalle variabili del Worker. Spenta se FAUNA_ATTIVA non e' esattamente "1". */
export function configuraFauna(env = {}) {
  const intero = (nome, pred, min, max) => {
    const g = env[nome];
    if (g === undefined || g === null || g === '') return pred;
    const n = Number(g);
    return Number.isSafeInteger(n) && n >= min && n <= max ? n : pred;
  };
  return {
    attiva: env.FAUNA_ATTIVA === '1',
    consentiSintetico: env.FAUNA_FIXTURE_SINTETICA === '1',
    seed: typeof env.FAUNA_SEED === 'string' && /^\d{1,19}$/.test(env.FAUNA_SEED) ? env.FAUNA_SEED : null,
    tickOgni: intero('FAUNA_TICK_OGNI', PREDEFINITI_FAUNA.tickOgni, 1, 100_000),
    maxPassi: intero('FAUNA_MAX_PASSI', PREDEFINITI_FAUNA.maxPassi, 1, 100),
    diarioMax: intero('FAUNA_DIARIO_MAX', PREDEFINITI_FAUNA.diarioMax, 1, 100_000),
  };
}

const leggi = (sql, zona) => sql.exec('SELECT * FROM fauna_zona WHERE zona = ?', zona).toArray()[0] ?? null;

function sospendi(sql, zona, versione, e) {
  const motivo = String(e instanceof ErroreFauna ? e.codice : 'errore_interno').slice(0, 64);
  sql.exec(`UPDATE fauna_zona SET stato = 'sospesa', motivo = ?, versione = versione + 1 WHERE zona = ? AND versione = ?`, motivo, zona, versione);
  return { stato: 'sospesa', motivo, passi: 0, arretrato: 0 };
}

/**
 * Porta la fauna della zona al tick del mondo indicato, al massimo cfg.maxPassi passi per chiamata.
 * Calcola tutto in memoria e scrive solo alla fine: un errore di calcolo sospende la zona (fail closed)
 * senza bloccare l'orologio del mondo; un errore di scrittura si propaga e annulla l'intera transazione.
 */
export function faunaAvanza(sql, habitat, tickMondo, cfg) {
  if (!Number.isSafeInteger(tickMondo) || tickMondo < 0) throw new ErroreFauna('tick_non_valido', 'tick del mondo');
  const zonaId = habitat.zone_id;
  const riga = leggi(sql, zonaId);
  if (!riga) {
    if (cfg.seed === null || cfg.seed === undefined) throw new ErroreFauna('seed_non_valido', 'seed esplicito obbligatorio');
    const z = creaZona(habitat, { seed: cfg.seed, parametri: cfg.parametri });
    const s = snapshotZona(z);
    sql.exec(`INSERT INTO fauna_zona (zona, specie, schema_version, habitat_sha256, seed, tick_nascita, tick_mondo, passo, versione, stato, motivo, snapshot, snapshot_sha256)
              VALUES (?, 'F01', ?, ?, ?, ?, ?, 0, 1, 'attiva', NULL, ?, ?)`,
      zonaId, FAUNA_SCHEMA_VERSION, habitat.sha256, z.seed, tickMondo, tickMondo, s.testo, s.sha256);
    return { stato: 'creata', passi: 0, arretrato: 0, passo: 0, vivi: z.world.organisms.length };
  }
  if (riga.stato !== 'attiva') return { stato: riga.stato, motivo: riga.motivo, passi: 0, arretrato: 0 };
  if (tickMondo <= riga.tick_mondo) return { stato: 'attiva', passi: 0, arretrato: 0, passo: riga.passo };   // retry, alarm doppio o tick non avanzato
  const dovuti = Math.floor((tickMondo - riga.tick_nascita) / cfg.tickOgni) - riga.passo;
  if (dovuti <= 0) return { stato: 'attiva', passi: 0, arretrato: 0, passo: riga.passo };
  const n = Math.min(dovuti, cfg.maxPassi);

  let z, s;
  const diario = [];
  try {
    if (riga.habitat_sha256 !== habitat.sha256) throw new ErroreFauna('habitat_diverso', 'hash habitat');
    z = ripristinaZona(habitat, riga.snapshot, riga.snapshot_sha256);
    if (z.world.ticks !== riga.passo) throw new ErroreFauna('snapshot_non_valido', 'passo incoerente con la riga');
    for (let i = 0; i < n; i++) diario.push(passoZona(z));
    s = snapshotZona(z);
  } catch (e) {
    return sospendi(sql, zonaId, riga.versione, e);
  }
  // tick_mondo avanza solo fino all'ultimo passo applicato: l'eventuale arretrato resta dovuto alla chiamata successiva.
  const tickApplicato = dovuti === n ? tickMondo : riga.tick_nascita + (riga.passo + n) * cfg.tickOgni;
  const scritte = sql.exec(`UPDATE fauna_zona SET passo = ?, tick_mondo = ?, versione = versione + 1, snapshot = ?, snapshot_sha256 = ?
                            WHERE zona = ? AND versione = ? AND passo = ? RETURNING versione`,
    z.world.ticks, tickApplicato, s.testo, s.sha256, zonaId, riga.versione, riga.passo).toArray();
  if (scritte.length !== 1) throw new Error('fauna: scrittura concorrente rilevata (versione cambiata)');
  for (const d of diario) sql.exec('INSERT INTO fauna_diario (zona, passo, vivi, nati, morti) VALUES (?, ?, ?, ?, ?)', zonaId, d.passo, d.vivi, d.nati, d.morti);
  sql.exec('DELETE FROM fauna_diario WHERE zona = ? AND passo <= ?', zonaId, z.world.ticks - cfg.diarioMax);
  const ultimo = diario[diario.length - 1];
  return { stato: 'attiva', passi: n, arretrato: dovuti - n, passo: ultimo.passo, vivi: ultimo.vivi,
    nati: diario.reduce((a, d) => a + d.nati, 0), morti: diario.reduce((a, d) => a + d.morti, 0), snapshot_sha256: s.sha256 };
}

/** Lettura per il client (sola lettura, nessuna scrittura). null se la zona non esiste. */
export function faunaVista(sql, habitat, { area, limite } = {}) {
  const riga = leggi(sql, habitat.zone_id);
  if (!riga) return null;
  if (riga.stato !== 'attiva') return { zone_id: riga.zona, stato: riga.stato, entita: [] };
  const z = ripristinaZona(habitat, riga.snapshot, riga.snapshot_sha256);
  return { stato: 'attiva', ...vistaClient(z, { area, limite, tickMondo: riga.tick_mondo }) };
}

/** Riepilogo non sensibile per report e log: solo contatori e hash. */
export function faunaStato(sql, zonaId) {
  const r = leggi(sql, zonaId);
  if (!r) return null;
  return { zona: r.zona, stato: r.stato, motivo: r.motivo, passo: r.passo, tick_mondo: r.tick_mondo, versione: r.versione,
    snapshot_sha256: r.snapshot_sha256, snapshot_caratteri: r.snapshot.length };
}
