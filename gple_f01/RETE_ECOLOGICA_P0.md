# GENESIS — ECO-P0: prima rete biologica visibile (candidata, 2026-11-11)

**Ambito:** DM-069, preparazione DM-071–074. Nessuna specie nuova è canonica, nessun asset è già stato creato. L'habitat della specie F01 resta l'area demo reale, non una mappa P01 immaginaria. I tre microambienti (bosco, riva, roccia) sono riferimenti e non impongono i biomi futuri.

## Organismi candidati (nomi tecnici provvisori)
- **PROD-A / Laminofora**: produttore biologico su suolo umido; accumula biomassa in lamine e trasferisce parte delle riserve a propaguli/frutti morbidi. La capacità di assimilazione è condizionata da acqua, luce e nutrienti del substrato. Aspetto, riproduzione e fonte d'energia devono essere approvati.
- **PROD-B / Nodulessa**: produttore di margini ripariali con corpo a noduli; produce escrescenze/secrezioni nutritive, non necessariamente frutti terrestri. Richiede acqua accessibile e nutrienti.
- **BIOFILM**: comunità aggregata di microorganismi superficiali. Non richiede individui 3D. Shader/mesh locali che mostrino quantità reale nello stock.
- **MICRO-01**: microfauna candidata, consuma biofilm; può essere consumata da F01. Visualizzazione iniziale a sciami/cluster con densità collegata allo stock.
- **DECOMP-01**: decomposizione come processo ecologico, non ancora una specie individuale, che converte detrito in nutrienti riutilizzabili.
- **F01**: semiaquatico quadrupede originale (PR #88, schede F01 Drive); fonti ipotetiche di cibo organico: biofilm, microfauna, biomassa morbida. Minerali **non** equivalgono a calorie. Non alterare anatomia, identità né comportamento canonico senza approvazione.

## Flusso di materia per la sandbox
Suolo(nutrienti) → PROD-A/PROD-B → frutti/secrezioni → F01.
Suolo(nutrienti) → biofilm → MICRO-01 → F01.
Detrito biologico → decomposizione → nutrienti del suolo.
Per un prototipo conservativo i trasferimenti sono uno-a-uno in **unità astratte di biomassa/materiale**, non sono chimica bilanciata o termodinamica. Crescita richiede luce come input energetico esterno e acqua, ma nessun nuovo materiale appare senza trasferimento da nutrienti. Ogni trasferimento F01 conserva materiale nella voce `f01_reserve` o nel detrito; non simula ancora una digestione completa, respirazione o emissioni. `f01_reserve` non è il vero peso di F01 e non può essere collegato direttamente alla sua energia.

## Contratto per asset Godot 2.5D
Ogni entità produttiva ha ID, posizione X/Y/Z sul terreno, patch/bioma, stock reale, stadio visivo `seed/juvenile/adult` (da confermare), mesh/GLB e materiali/skin, trigger di crescita/produzione, LOD e collisione. Il frutto ha identità derivata dalla pianta e quantità collegata a `fruit_a`/`fruit_b`; raccoglierlo aggiorna prima lo stock autorevole e poi nasconde/scala la mesh. Il biofilm varia copertura a seconda di `biofilm`; la microfauna può essere aggregata oltre il primo piano. Niente `free spawning` puramente grafico.

## Gate di accettazione
1. **ECO-0**: contratto alimentare, risorse e ipotesi esplicite, con approvazione delle specie prima del canon.
2. **ECO-1**: simulazione conservativa con seed ripetibile, contabilità dei trasferimenti, test fame e suolo vuoto.
3. **ECO-2**: schede anatomiche e flussi energetici/riproduttivi da sottoporre ad Andrea.
4. **ECO-3**: mesh/texture/skin/GLB dei due produttori, microfauna e F01; pipeline Blender/Godot reale e test 2.5D.
5. **ECO-4**: sandbox Godot osservabile e giocabile, 5–10 F01, frutti, nutrienti e crescita.
6. **ECO-5**: export della vera demo con confini irregolari, scala, quote, acqua, biomi, coordinate e ID risorse; nessun dato sintetico dichiarato reale.

**Limitazioni di oggi:** il modello di prova è una singola patch astratta, senza simulazione chimica, fotosintesi realistica, nascita della microfauna, texture, skin o integrazione Godot. Le specie sono proposte di design, non scoperte evolutive.
