# GPLE / F01 - Habitat e ciclo vitale v0.1

Stato: SPECIFICA SPERIMENTALE, non integrazione Godot/World o parametri biologici canonici.
Fonte: scheda F01 del 10 novembre, F01_06 Design Data e PR #88 originale.

## Spazio
Demo giocabile approssimativamente 150 x 150 metri, nucleo 60 x 60 metri. Solo celle realmente percorribili dal mondo Godot, con bordi frastagliati: suitable = playable AND suitable_for_f01 AND traversable. La griglia sintetica non è il mondo reale.

## Biomi e catena ecologica
| Microhabitat | Risorse candidate | Uso F01 | Dati da recuperare |
| --- | --- | --- | --- |
| Bosco alieno | biomassa tenera, biofilm, microfauna | rifugio, riposo, foraggiamento | copertura, microclima, nodi risorse |
| Riva umida | biofilm organico, microfauna | cibo, guado e possibili fonti d'acqua | profondita, chimica dell'acqua, substrato |
| Affioramento minerale | biofilm in nicchie | rifugio, esplorazione | accessibilita, pendenza, disponibilita organica |

I minerali non sono calorie. Nessuna risorsa può essere creata in una cella reale solo per garantire la sopravvivenza F01; scorte zero sono lecite. Pericoli e rifugi devono derivare dallo stato World, non da dati immaginati.

## Ciclo vitale da sviluppare
1. Gemma / bud: ipotesi di riproduzione asessuata (non approvata), investimento energetico e controllo disponibilita spazio.
2. Giovane / juvenile: crescita, maggiore vulnerabilita, alimentazione e movimento.
3. Adulto / adult: percezione, metabolismo, foraggiamento, riposo, fuga, apprendimento individuale e possibile riproduzione.
4. Senescente / senescent: decadimento fisiologico da calibrare.
5. Morto / dead: rimozione e riciclo materia deterministici e server-autorevoli, senza duplicazione di nutrienti.

Durata stadi e tick, fabbisogno idrico, energia, soglie termiche e salinita restano NON DEFINITI. La PR #88 gia implementa una gemmazione semplificata e due tratti ereditabili: threshold ed efficiency. Riutilizzare quel simulatore, non sostituirlo con un nuovo organismo.

## Sottosistemi da integrare
- Import habitat: geometria vera maschera, world coordinates, bioma, accessibilita, profondita acqua, substrato, versione.
- Clima/acqua: umidita, temperatura, stagione, profondita e chimica, misurate/approvate.
- Nutrienti/risorse: biofilm, microfauna, vegetazione tenera con stock, capacita e rinnovamento; consumo atomico.
- Ripari/pericoli: shelter e danger con origini osservabili.
- Popolazione: competizione per risorse, crescita, nascita, morte, capacita portante, estinzione possibile.
- Ciclo vitale: passaggi a stadi, metabolismo dipendente da eta e ambiente, riproduzione limitata.
- Output: snapshot, seed, world_version, stato PRNG e log eventi sufficienti per replay.
- Godot: eventi osservabili e animazioni, senza autorita client su energia e nascite.

## Gate
A. Recuperare vera maschera frastagliata Godot e nodi ecologici della demo.
B. Importare dati versionati: nessun inventario fittizio in produzione.
C. Approvare parametri biologici e regole dell'acqua F01.
D. Adattare il simulatore della PR #88 ai tre biomi e agli stadi.
E. Eseguire test multi-seed, risorse zero, bordo irregolare, replay e limiti risorse.
F. Solo in seguito valutare adapter Cloudflare/Godot, con autorizzazione separata.
