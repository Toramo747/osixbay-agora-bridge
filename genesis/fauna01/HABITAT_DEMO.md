# FAUNA-02 — Habitat effettivo = zona demo giocabile

**Decisione di Andrea:** la specie F01 deve vivere e venire simulata **nella porzione di mondo effettivamente giocabile della demo Genesis**, non su una regione P01 generica, su una griglia immaginaria né sull'intero pianeta. P01 è soltanto il contesto geografico proposto e NON implica che l'Atlante/DEM siano canonici.

## Cosa costituisce la demo
La demo prevede una zona locale limitata, riconoscibile dal globo e attraversabile in Godot; il bordo è naturale e irregolare, non un quadrato paesaggistico visibile. Sono previsti tre sottoambienti contigui: bosco alieno, riva umida e affioramento roccioso/minerale. Questi dettagli sono **specifiche di progetto, non prova che le mappe reali siano state esportate o collaudate**.

## Contratto di integrazione da verificare su dati REALI

**Sorgente autorevole:** maschera/contorno giocabile e mappa degli habitat dal terreno di Godot/World Engine usato nella demo. Non ricostruire la geometria usando stime dell'Atlante. Nessuna creazione artificiale di risorse solo per far sopravvivere F01.

Per ogni posizione simulata devono essere verificabili:
- Identità, versione e coordinate locali della zona DEMO, con conversione coerente tra mondo Godot e celle server (scala/offset/risoluzione espliciti).
- `playable` (cella entro i confini irregolari realmente percorribili), `biome` e informazioni locali di quota/pendenza/acqua/substrato quando disponibili.
- `suitable_for_f01` determinato da esigenze biologiche concordate per la specie (ancora da approvare).
- Scorta e tipologia di cibo provenienti da risorse reali lato World Engine, con disponibilità e rinnovabilità coerenti; possibile valore **zero**.
- Livelli di pericolo ed eventuali rifugi collegati a eventi/stato del mondo, non generati arbitrariamente.
- Stato serializzabile e verificabile per replay, cap per zona e consumo server-autorevole.

**Proiezione per l'attuale prototipo:** `suitable = playable AND suitable_for_f01`. Le celle esterne sono sempre inadatte: nessuno spawn, nessuna migrazione, nessuna nascita oltre il confine. `food` va inizializzato da scorte realmente disponibili; `danger` da eventi reali. La griglia sintetica di `sim.py`/`sim.mjs` rimane SOLO per test dell'algoritmo.

## Test obbligatori prima di collegare GPLE e Godot
1. Import di una vera mappa/maschera demo versionata, senza inventare contorni o posizioni.
2. Nessuna creatura generata fuori dalla zona percorribile o in habitat vietato, compresi bordi e raccordi irregolari.
3. Cibo e acqua coerenti con i tre microambienti e con le quantità realmente presenti (anche in assenza totale).
4. Riproduzione, morte e locomozione rispettano bordi e bioma, anche dopo snapshot/rientro e offline.
5. Lo stesso seed + stessa versione mondo + stessa sequenza di eventi = stessa fauna.
6. Nessuna entità visibile al client se non esiste nello stato World/GPLE.
7. Compatibilità con i flussi globo → zona → avatar e telecamera senza riquadri artificiali.
8. Conferma di Andrea sulla scelta F01 e sull'aspetto biologico; il minimo originale della roadmap demo contempla due specie, quindi F01 non esaurisce il lavoro fauna della demo.

## Stato al 10 novembre 2026
- Specifica corretta e registrata.
- Algoritmo sperimentale con test disponibili nella PR #88.
- **Mancano ancora:** export della maschera reale demo, modello di risorse e biomi validato, scelta anatomica della specie, adapter World/GPLE/Godot e test end-to-end.
- Nessun merge, deploy, modifica Cloudflare/Agora o accesso a segreti.
