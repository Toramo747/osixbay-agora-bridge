# Genesis — città

Scena Godot 4.6.3 da aprire sul computer del ponte: il mondo di Genesis a tessere 1×1, in stile city builder, con gli edifici CC0 di Kenney.

- **Aprire:** in Godot 4.6.3 → Importa → questa cartella → Esegui (F5).
- **Terreno:** scarica `bots/genesi/mondo.json` (seme e zone) e ricalcola ogni cella con la stessa formula di `bots/dati/genesi_costruttore.gd`: biomi e risorse coincidono con il ponte. I gradoni, gli alberi e l'acqua servono solo alla resa grafica.
- **Costruire:** barra in basso o tasti 1–0 (strada, casa, palazzina, torre, negozio, garage, piazza, fontana, parco, demolisci). Clic sinistro costruisce, R ruota, clic destro o X demolisce. Le strade si collegano da sole. Si costruisce su prateria, foresta, deserto e spiaggia; non su acqua e montagna.
- **Camera:** WASD/frecce, rotella, tasto destro o centrale trascinato, Q/E.
- **Salvataggio:** `user://citta.json`, legato al seme. Il collegamento con `Mondo.dati` e con i residenti viene dopo.
- **Foto senza schermo:** `godot --path . -- --mondo=mondo.json --foto=f.png [--demo --zoom=30]`.

Crediti: modelli, suoni e font in `kenney/`. Modelli e suoni: Kenney, Starter Kit City Builder (github.com/KenneyNL/Starter-Kit-City-Builder, commit 4535092), licenza CC0. Font Lilita One: licenza SIL OFL 1.1 (`kenney/font/OFL.txt`).
