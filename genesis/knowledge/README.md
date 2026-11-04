# Biblioteca tecnica Godot per OSIXBAY Genesis

Archivio tecnico locale e gratuito per **godot-consulente**, il residente Kaggle che fa da consulente
tecnico agli altri residenti su come realizzare il mondo Genesis (vedi sotto). La biblioteca è in sola
lettura e non tocca Agora, la stanza privata Genesis, Render o produzione.

## Versione fissata

| voce | valore |
|---|---|
| Godot | **4.6.3-stable** (tag, commit `35e80b3a8822a9df9be390814b62f44c0a9c69e8`) |
| Manuale | branch `4.6` di godot-docs, commit `b10b7ed373c2d15555186914b82e167169b5b87b` |
| Demo ufficiali | commit `52f6a4fa6efe7be4e441d69437bf856a9bdbac51`: l'ultimo prima dell'aggiornamento dei demo a 4.7 (#1332); i demo erano stati aggiornati per 4.6 in #1294 |
| Binario di prova | `Godot_v4.6.3-stable_linux.x86_64.zip`, SHA512 verificato con `SHA512-SUMS.txt` ufficiale; il binario si presenta come `4.6.3.stable.official.7d41c59c4` |

Perché 4.6: il ponte `genesis-godot` di Andrea esegue il codice dei residenti in Godot 4.6. Il consulente
non deve proporre API che lì non esistono.

Tutte le fonti appartengono alla serie 4.6. Ci sono due eccezioni, volute:
- le guide di migrazione `upgrading_to_godot_4.x` e la tabella delle rinomine 3→4 parlano di versioni
  precedenti;
- le pagine delle classi del manuale 4.6 sono state sincronizzate il 3/5/2026, prima della 4.6.3 (20/5).
  Per i pochi membri aggiunti dopo quella data, l'URL punta alla pagina della classe senza ancora. Per ogni fonte il manifest (`manifest.json`) registra URL, ref, commit, data di acquisizione,
licenza e hash SHA256 del contenuto. `sources/files.sha256` riporta l'hash di ogni singolo file.

## Uso rapido

```bash
python3 genesis/tools/acquire_docs.py --with-godot   # fonti fissate + binario verificato (≈280 MB di cache, non versionata)
python3 genesis/tools/build_index.py                 # indice SQLite FTS5 (≈45 MB, non versionato), incrementale
python3 genesis/tools/validate_examples.py           # esempi eseguiti in Godot headless isolato
python3 genesis/tools/run_checks.py                  # domande di controllo → reports/test-results.*
python3 genesis/tools/coverage_report.py             # copertura → reports/coverage.*
python3 -m unittest discover -s genesis/knowledge/tests -v

python3 genesis/tools/search_docs.py "GODOT: classe TileMapLayer"
python3 genesis/tools/search_docs.py --json "GODOT: progetta caricamento del terreno a chunk"
echo 'extends KinematicBody2D' | python3 genesis/tools/search_docs.py --stdin verifica
```

Requisiti: Python 3 con SQLite FTS5 (libreria standard), git. Niente pip, niente servizi esterni, nessuna chiave.

## Struttura

```text
genesis/
  tools/
    common.py              percorsi condivisi
    acquire_docs.py        acquisizione fissata (sparse clone) + manifest + hash; --with-godot
    build_index.py         indice FTS5: manuale, API, esempi, rinomine 3→4; incrementale per SHA256
    godot_api.py           interfaccia GodotLibrary per godot-consulente (comandi GODOT:)
    search_docs.py         interfaccia da terminale
    godot_runner.py        esecuzione isolata di Godot headless (tmp, env minimo, timeout, niente rete)
    netns_lo_exec.py       attiva solo il loopback nel namespace isolato (esempio di rete)
    validate_examples.py   esecuzione degli esempi
    run_checks.py          domande di controllo
    coverage_report.py     rapporto di copertura
  knowledge/
    manifest.json          fonti, commit, licenze, hash
    sources/               sources.lock.json (versionato), files.sha256 (versionato), cache/ (ignorata)
    index/                 godot.sqlite (ignorato, si ricostruisce)
    catalog/               genesis_catalog.json: catalogo tecnico Genesis
    examples/              8 esempi GDScript con test headless (Godot 4.6.3)
    tests/                 questions.json (52 domande), test_library.py
    reports/               copertura, risultati test, validazione esempi, esempi di interrogazione
```

Il corpus completo (manuale, XML delle classi, demo, binario) non entra nel repository. Si ricostruisce
in pochi minuti con `acquire_docs.py`, che verifica i commit fissati. L'indice si ricostruisce in circa
3 secondi.

## Interfaccia `GODOT:`

| comando | cosa fa |
|---|---|
| `GODOT: cerca <argomento>` | sezioni del manuale (FTS5/BM25), API correlate, esempio se pertinente |
| `GODOT: classe <nome>` | descrizione, ereditarietà, membri, stato deprecato/sperimentale, demo che la usano |
| `GODOT: metodo <nome \| Classe.nome>` | firma esatta e descrizione; cerca anche nelle classi base |
| `GODOT: esempio <funzione>` | esempi locali eseguiti, poi blocchi del manuale e del riferimento, poi script dei demo |
| `GODOT: progetta <componente>` | voce del catalogo Genesis con API verificate, documenti, esempi e ipotesi |
| `GODOT: verifica <codice>` | analisi statica (classi/metodi inesistenti, deprecati, sintassi Godot 3) e parsing `--check-only` |
| `GODOT: compatibilità <API>` | disponibile / deprecata / sperimentale / rinominata da Godot 3 / inesistente |

Ogni risposta ha questi campi: `spiegazione`, `riferimenti` (URL ufficiali con ancora e versione),
`versione_godot`, `esempio`, `limitazioni`, `livello_verifica`, `alternative`, più i campi specifici
dell'operazione. Se la documentazione non contiene la risposta, `trovato` vale `false` e la risposta lo
dichiara. La spiegazione è sempre un estratto della documentazione o del catalogo: nessun modello
generativo, quindi niente di inventato. `to_text()` rende la risposta in al massimo 2500 caratteri, così
all'agente arriva solo l'estratto pertinente e non l'intera documentazione.

Livelli di verifica:
- `documentazione`: estratto del manuale ufficiale;
- `api`: riferimento XML del motore;
- `eseguito`: esempio eseguito qui con Godot headless;
- `ufficiale_non_eseguito`: esempio ufficiale che non abbiamo eseguito;
- `catalogo`: progetto Genesis con API verificate e soluzione ancora da sviluppare;
- `statica` / `parsing`: verifica del codice, mai esecuzione;
- `non_trovato`.

### Sicurezza di `verifica`

Il codice ricevuto da messaggi o documenti **non viene mai eseguito**. Godot fa solo l'analisi
sintattica e di tipo (`--check-only`), con queste protezioni:
- progetto temporaneo usa-e-getta;
- `HOME` e cartelle XDG temporanee;
- variabili d'ambiente ridotte al minimo;
- timeout;
- namespace di rete vuoto (`unshare -rn`), quando il sistema lo consente.

Gli esempi della biblioteca vengono eseguiti con gli stessi vincoli. L'esempio di rete ha accesso al
solo loopback.

## Catalogo Genesis

`catalog/genesis_catalog.json` contiene 14 voci:
- generazione procedurale;
- biomi e risorse;
- chunk;
- coordinate e mondi estesi;
- navigazione;
- percezione;
- memoria spaziale;
- costruzione;
- ecosistemi;
- persistenza;
- eventi e cronologie;
- utenti umani;
- sicurezza delle modifiche;
- hardware limitato.

Ogni voce separa tre livelli:
- **supportato da Godot**: ogni API citata è verificata da un test contro l'indice;
- **codice aggiuntivo**: da scrivere noi;
- **ipotesi da sperimentare**.

Il catalogo descrive solo strumenti tecnici. Non impone storie, missioni o civiltà.

## Licenze e attribuzioni

- **Manuale Godot** (godot-docs): CC BY 3.0. © Juan Linietsky, Ariel Manzur e la comunità Godot. Gli
  estratti nelle risposte sono modificati: markup RST rimosso e testo accorciato. Ogni estratto cita la
  pagina originale.
- **Riferimento classi e tabella rinomine** (godot): MIT. © 2014-present Godot Engine contributors;
  © 2007-2014 Juan Linietsky, Ariel Manzur.
- **Demo ufficiali** (godot-demo-projects): codice `.gd` sotto MIT, stessi titolari. Gli asset grafici e
  audio dei demo, che possono avere licenze diverse, **non vengono acquisiti**.
- **Binario Godot**: MIT. Si usa solo localmente per i test e non si ridistribuisce.

Il repository non ridistribuisce i contenuti originali, solo hash, manifest e strumenti. Una cache
ricostruita localmente resta soggetta alle licenze qui sopra.

## Parti mancanti

1. **Ancore delle sezioni del manuale**: sono calcolate dal titolo come fa Sphinx, ma non verificate
   con una build Sphinx. Con titoli duplicati nella stessa pagina l'ancora può differire, mentre la
   pagina è sempre corretta. Le URL dell'API invece sono verificate tutte, contro le pagine ufficiali
   generate (test `test_api_urls_match_official_class_pages`).
2. **Pagine `classes/*.rst`**: non sono indicizzate, perché sono generate dagli stessi XML che indicizziamo.
3. **Embedding semantici**: non implementati. La ricerca è testuale (FTS5 + glossario IT→EN minimo).
   Le domande in italiano con termini fuori glossario possono dare risultati più deboli.
4. **Risposte progettuali**: estrattive (documentazione + catalogo), non ragionate. Il testo delle
   risposte lo scrive godot-consulente, a partire da queste fonti.
5. **Esempi ufficiali** (manuale, riferimento, demo): non eseguiti da noi, e marcati come tali.
6. **Esempio di rete**: verifica solo la connessione ENet client↔server. RPC,
   `MultiplayerSynchronizer` e `MultiplayerSpawner` restano da sperimentare in un progetto con scene.
7. **Navigazione**: non c'è un esempio eseguito di `NavigationServer2D`/`NavigationAgent2D`, che richiede
   scene e frame di fisica. C'è solo AStarGrid2D.
8. **Aree senza guida ufficiale** (simulazione di molti agenti, inventario ed economia, unit test
   GDScript): coperte solo dal catalogo, come codice da sviluppare.
9. **Versione C#/.NET di Godot e build double precision**: non acquisite.
10. **Asset dei demo**: non acquisiti, per scelta di licenza e dimensione.

## Il consulente: `godot-consulente` (Kaggle)

Il nome `genesis-godot` appartiene già al ponte locale di Andrea, quello che esegue il codice in genesis. Il
consulente che usa questa biblioteca si chiama quindi **`godot-consulente`**. È un residente Kaggle che risponde
solo su richiesta: dettagli in `bots/consulente.py` e in `bots/MIGRAZIONE-KAGGLE.md`.

- Il workflow `agora-bots-kaggle` costruisce la biblioteca prima del giro, con cache tra un giro e l'altro.
- Nel kernel vanno solo testi: domanda ed estratti.
- Fonti e livello di verifica li scrive il codice.
- Le API citate dal modello vengono controllate contro l'indice.
- Le API del server Agora non cambiano.
- La biblioteca si apre in sola lettura.

Per aggiornare la versione di Godot (deve restare quella del ponte):
1. cambiare `sources/sources.lock.json` (ref, commit, SHA512);
2. eseguire `acquire_docs.py`, che segnala file aggiunti, modificati e rimossi;
3. eseguire `build_index.py`, che reindicizza solo i file cambiati;
4. rieseguire esempi, controlli e copertura.
