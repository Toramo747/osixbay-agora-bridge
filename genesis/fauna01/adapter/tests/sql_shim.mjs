/**
 * Shim di test: espone su node:sqlite la stessa interfaccia usata nel Durable Object
 * (ctx.storage.sql.exec(query, ...bindings) -> cursore con toArray()/one(); ctx.storage.transactionSync(fn)).
 * Serve a provare schema e query su un vero SQLite, senza Cloudflare.
 */
import { DatabaseSync } from 'node:sqlite';

export function creaStorage() {
  const db = new DatabaseSync(':memory:');
  const conteggi = { exec: 0, scritture: 0 };
  let livello = 0;
  const sql = {
    intercetta: null,     // (query) => void, per iniettare guasti nei test
    exec(query, ...bindings) {
      conteggi.exec++;
      if (/^\s*(INSERT|UPDATE|DELETE)/i.test(query)) conteggi.scritture++;
      if (sql.intercetta) sql.intercetta(query);
      const righe = db.prepare(query).all(...bindings);
      return {
        toArray: () => righe,
        one: () => { if (righe.length !== 1) throw new Error('one(): attesa una riga'); return righe[0]; },
        [Symbol.iterator]: () => righe[Symbol.iterator](),
      };
    },
  };
  return {
    sql, conteggi, db,
    transactionSync(fn) {
      const nome = `sp${livello++}`;
      db.exec(`SAVEPOINT ${nome}`);
      try { const r = fn(); db.exec(`RELEASE ${nome}`); return r; }
      catch (e) { db.exec(`ROLLBACK TO ${nome}`); db.exec(`RELEASE ${nome}`); throw e; }
      finally { livello--; }
    },
  };
}
