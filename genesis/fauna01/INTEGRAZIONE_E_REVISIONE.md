# FAUNA-02 F01 — Piano di revisione e integrazione NON PRODUTTIVA

Stato: **specifica di integrazione, NON un adapter installato**. Codice sorgente disponibile nella PR in bozza #88. Non fare merge, deploy, rollback, pubblicazione in Agora o modifiche a Cloudflare senza autorizzazione specifica di Andrea.

## 1. Contratto minimo del simulatore

`sim.mjs` espone `Parameters`, `World` e `demonstration`. Il modello è puro JavaScript ES module, senza dipendenze npm e senza I/O o rete. Compatibile a livello di sintassi con il runtime JavaScript di Cloudflare Workers, **ma non ancora testato in un Worker reale**.

Ingressi del tick:
- Griglia `suitable` (habitat provvisorio); celle con `food` limitato e `danger`;
- Organismi con ID stabile, posizione di griglia, energia, età, due tratti ereditabili;
- Configurazione esplicita, seed a 64 bit, stato corrente del PRNG.

Uscite del tick: `{tick,alive,born,died}`, stato del mondo aggiornato e snapshot serializzabile.

**Regole di sicurezza e autorità:** il server è l'unica fonte autorevole; il client Godot riceve solo un sottoinsieme osservabile; nessun client può fissare arbitrariamente nascite, energia o risorse. Non inserire testi privati di Agora negli snapshot né nei log.

## 2. Possibile adapter per Durable Object SQLite (NON implementato)

1. Leggere il codice originale dello staging Cloudflare e recuperare gli schemi, le migrazioni e la politica di allarmi. Non assumere che corrispondano a questo prototipo.
2. Introdurre una versione separata del contratto fauna (`fauna_schema_version=1`) e identificare la cella/zona nella struttura server esistente; non sovrascrivere `MONDO` o alterare la migrazione di produzione.
3. Scrivere in SQLite uno snapshot transazionale **solo in staging isolato**, con tick e versione monotoni. Rifiutare snapshot corrupti, troppo grandi, non validi o provenienti da client non autorizzati.
4. Applicare un tetto per tick, per zona e per coda arretrata: niente avvio infinito in un `alarm()`, CPU e scritture misurate.
5. Testare crash prima/dopo commit, doppio alarm, replay identico, idempotenza, ritardi, snapshot vecchio e migrazione in avanti.
6. Nessuna chiave, API mutativa o token nei report. Nessun deploy fino a PR separata approvata.

**Valori non canonici:** parametri metabolici attuali, griglia, tipologia di cibo, pericolo e durata di un tick sono inventati per esperimento, non regole biologiche definitive.

## 3. Possibile adapter Godot 4.6 (NON implementato)

Un client mostra creature usando ID, posizione e stato di animazione provenienti dal server. La gestione locale della grafica non modifica il modello biologico autorevole. Servono un contratto per coordinate/chunk/LOD e la trasmissione a interesse spaziale limitato, ancora da validare su scena Godot reale.

## 4. Evidenze già eseguite sul codice di riferimento

- Python `python3 -m unittest discover -s genesis/fauna01/tests -v`: **13/13 PASS**.
- Node.js `node --test genesis/fauna01/tests/test_parity.mjs`: **7/7 PASS**, quattro scenari e snapshot intermedi confrontati numericamente con Python.
- 10.000 tick Python su una griglia 64×64, limite popolazione 500: senza superare limiti di risorse, energia e cap; 16,399 secondi nel container di prova. **Non è un benchmark Cloudflare**.
- Esempio seed=13, 80 tick: 14 vivi, 34 nati, 22 morti, cibo finale 114,6 (unità astratte).

## 5. Revisione biologica ancora aperta

Richiedere ai residenti contributi brevi, contestabili e specifici su anatomia, locomozione, uso delle risorse, organismi competitori, mutazioni ed ecosistema P01. L'Atlante propone habitat in P01, **ma non fissa ancora** temperatura media, atmosfera, ciclo idrologico, chimica numerica o organismi canonici. Trattare numeri come il presunto «ciclo idrologico di 30 giorni» come **non verificati**.

**Accettazione:** Andrea approva la descrizione specie; un revisore verifica i test; un adapter separato dimostra parità/sicurezza e supera i gate di staging. Il completamento del solo simulatore non costituisce un mondo persistentemente popolato.
