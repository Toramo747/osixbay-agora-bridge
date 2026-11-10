# Adapter World Engine → fauna F01 (v0.1.0, schema fauna 1)

**Stato: codice e test locali. Non deployato, non collegato a un habitat reale.** PR in bozza, impilata sulla PR #88. Nessun deploy, merge o modifica Cloudflare senza OK esplicito di Andrea.

Fa vivere il simulatore di riferimento `../sim.mjs` (non modificato) dentro il Durable Object SQLite `MONDO` del Worker `genesis-world-test`, limitandolo a `playable AND suitable_for_f01`.

## File

| File | Ruolo |
|---|---|
| `habitat.mjs` | convalida e proiezione dell'export habitat ([contratto](CONTRATTO_HABITAT.md)) |
| `zona.mjs` | zona F01: creazione, passo deterministico, snapshot/ripristino, vista client |
| `persistenza.mjs` | tabelle `fauna_*`, `faunaAvanza` (tick), `faunaVista` (sola lettura) |
| `sha256.mjs` | SHA-256 sincrono (dentro `transactionSync` non si può usare `crypto.subtle`) |
| `integrazione/applica_patch.py` | applica la patch a una copia locale del sorgente del Worker |
| `integrazione/prova_workerd.mjs` | prova nel runtime workerd locale (miniflare) |
| `tests/` | test Node, shim SQLite, replica del clock del mondo, benchmark |

## Come si aggancia al Worker

Il sorgente del Worker non è in nessun repository (vive solo nella versione deployata): la patch è uno script che lavora su una copia locale. Tocca due file:

- `mondo.js`: configurazione fauna nel costruttore; `inizializzaFauna` dopo lo schema; **una chiamata a `faunaAvanza` dentro la `transactionSync` di `avanza()`**, dopo l'aggiornamento di `tick`; un metodo RPC di lettura `faunaLeggi`.
- `index.js`: percorso `GET /v1/fauna[?area=x0,y0,x1,y1]`, firmato come gli altri.

Nessuna modifica a `meta`, `stato`, `eventi`, `programmati`, `nonce`, autenticazione, cron o alarm.

## Schema (proposto, non eseguito su Cloudflare)

`CREATE TABLE IF NOT EXISTS`, quindi additivo e senza migrazione Durable Object (`wrangler` invariato):

- `fauna_meta(chiave, valore)`: `schema_version`.
- `fauna_zona(zona, specie, schema_version, habitat_sha256, seed, tick_nascita, tick_mondo, passo, versione, stato, motivo, snapshot, snapshot_sha256)`: una riga per zona.
- `fauna_diario(zona, passo, vivi, nati, morti)`: ultimi `FAUNA_DIARIO_MAX` passi.

Lo snapshot non sta in `stato`: non pesa sul limite di 200.000 caratteri del mondo e non esce da `/v1/stato`.

## Garanzie

- **Atomicità**: mondo e fauna nella stessa transazione; un guasto prima del commit annulla entrambi.
- **Idempotenza**: i passi dovuti derivano dal tick del mondo, non dal numero di allarmi; alarm doppio = zero scritture.
- **Monotonicità**: un tick più vecchio non fa nulla; aggiornamento con controllo di versione (CAS).
- **Budget**: al massimo `FAUNA_MAX_PASSI` (5) passi per allarme; l'arretrato si recupera negli allarmi successivi; nessun ciclo illimitato.
- **Fail closed**: snapshot corrotto, manomesso, di versione futura o habitat cambiato → zona `sospesa`, il mondo continua.
- **Client**: sola lettura; riceve id, cella, posizione mondo, bioma, azione, passo, tick. Mai energia, tratti, cibo o stato del generatore casuale. Nessuna rotta di scrittura.
- **Niente LLM**, niente orologio e niente I/O nei passi.

## Variabili (tutte facoltative; senza `FAUNA_ATTIVA=1` il Worker si comporta come oggi)

`FAUNA_ATTIVA`, `FAUNA_SEED` (obbligatorio se attiva), `FAUNA_TICK_OGNI` (1), `FAUNA_MAX_PASSI` (5), `FAUNA_DIARIO_MAX` (2880), `FAUNA_FIXTURE_SINTETICA` (solo prove).

## Test

```sh
python3 -m unittest discover -s genesis/fauna01/tests -v
node --test genesis/fauna01/tests/test_parity.mjs
node --test genesis/fauna01/adapter/tests/test_adapter.mjs genesis/fauna01/adapter/tests/test_persistenza.mjs
node genesis/fauna01/adapter/tests/bench.mjs
```

Prova nel runtime reale, in locale (serve una copia del sorgente del Worker):

```sh
python3 genesis/fauna01/adapter/integrazione/applica_patch.py <src_worker> /tmp/mondo-fauna
npm install --no-save miniflare
node genesis/fauna01/adapter/integrazione/prova_workerd.mjs /tmp/mondo-fauna
```

## Limiti dichiarati

- Habitat reale assente: tutti i test usano la fixture sintetica.
- Parametri metabolici, tick biologico e biomi idonei sono valori di prova, non canonici.
- Pericolo: solo il livello statico dell'export. Predazione, raccolta del giocatore ed eventi del mondo sulla fauna non esistono in v1.
- Nessun evento per singola nascita o morte: il client riconcilia per id sulla vista.
- Tempo CPU misurato solo in Node; in workerd locale non è misurabile. Una sola zona.
- Modello 3D, rig, animazioni e suoni F01 non esistono.
