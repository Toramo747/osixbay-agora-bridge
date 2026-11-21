# Genesis F01 - Contratto Godot 2.5D, proposta v0.1

**Implementazione:** `world25d.py` e `test_world25d.py` sul ramo di laboratorio. Sono un adattatore dati e test offline: non aggiungono nodi o scene a Godot e non sono stati installati in Cloudflare.

## Il 2.5D in Genesis
Il gioco presenta uno spazio con geometria tridimensionale e due distanze di camera: gestionale dall'alto ed esplorazione con avatar WASD. Una simulazione ecologica a celle e lecita solo come rappresentazione interna: l'organismo ha posizione persistente nel mondo, altezza del terreno e animazione in un unico sistema di coordinate.

### Contratto minimo del terreno
Importare dalla vera scena giocabile, con provenienza `source_scene`, commit, `world_version` e una maschera `playable` irregolare:
- Origine Godot `[x,y,z]` in metri. Horizontal plane XZ, elevation Y.
- Scala delle celle e conversione coordinate esplicite.
- `elevation_m`, `slope_deg`, `water_depth_m`, `water_surface_y_m`.
- `playable`, `traversable`, `suitable_for_f01`, bioma, substrato, cibo, rifugio e pericolo.
- Percorribilita F01 = maschera AND bioma idoneo AND pendenza/guado entro limiti fisici.
- Le soglie provvisorie di test 35 gradi e 0,45 metri non sono valori fisiologici approvati.
- Nessuna posizione viene proiettata con y arbitraria: Y deve venire dal terreno versionato.

### Navigazione e transizioni
Vietare attraversamenti diagonali o teletrasporti nella prova a griglia; un adapter NavMesh/Godot definira poi movimento fluido, offset corporali e raycast/collisione. Bordo frastagliato sempre vincolante; il quadrato della griglia esiste soltanto come contenitore dati. La transizione globo -> demo -> avatar richiede un transform univoco non ancora recuperato e testato.

### Contratto di visualizzazione
`visual_frame()` proietta dati **read-only**, con id stabile, specie, coordinate 3D, stato azione, stadio biologico, bioma, LOD e flag visibilita. I due modi `management` e `exploration` cambiano solo camera/presentazione, non energia, riproduzione, popolazione o stato del mondo.

Test LOD sperimentali: near sotto 15 m; mid 15-50 m; far 50-180 m; oltre 180 m culled visivamente. **Culled non equivale a morto**. Realizzare le soglie vere dopo benchmark sul PC target e sulla scena Godot. Le animazioni e il rig F01, come pure la scena demo reale, rimangono da realizzare o da importare.

### Blocchi prima dell'integrazione
1. Export affidabile della scena Godot realmente usata, comprensivo dei confini irregolari e acqua.
2. Verifica di pendenze, coordinate, scala, collisioni e mappa navigabile.
3. Collegamento con stato server-autorevole World/GPLE, senza client-write.
4. Un asset GLB F01 con rig, clip e LOD verificati nelle due modalita.
5. Test di 12-20 creature in scena, stress CPU/GPU e ripristino dopo disconnessione.
6. Nessun deploy Cloudflare o modifica alla produzione Agora senza consenso separato.
