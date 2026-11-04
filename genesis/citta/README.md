# Genesis

Scena Godot 4.6.3 da aprire sul computer del ponte: il mondo di Genesis secondo il concept art del 4/11/2026 (palette, luce di tardo pomeriggio, pianeta con anello, architettura in intonaco e legno con volte curve, torre civica di cristallo), dove si costruisce come in un city builder. Scala: 1 cella = 6 m.

- **Aprire:** in Godot 4.6.3 → Importa → questa cartella → Esegui (F5).
- **Terreno:** scarica `bots/genesi/mondo.json` (seme e zone) e ricalcola il mondo con la stessa formula di `bots/dati/genesi_costruttore.gd`: biomi e risorse coincidono con il ponte. Rilievo morbido, erba al vento, alberi, acqua e luce sono solo resa grafica.
- **Costruire:** barra in basso o tasti 1–0 (via, casa, palazzina, torre, negozio, fienile, piazza, fontana, parco, demolisci). Clic sinistro costruisce, R ruota, clic destro o X demolisce; le vie si collegano da sole. La griglia 1×1 compare solo vicino al cursore. Si costruisce su prateria, foresta, deserto e spiaggia.
- **Camera:** WASD/frecce, rotella, tasto destro o centrale trascinato, Q/E.
- **Salvataggio:** `user://citta2.json`, legato al seme.
- **Foto senza schermo:** `godot --path . -- --mondo=mondo.json --foto=f.png [--demo --zoom=12]`.

Tutta la grafica è generata dal codice. Suoni: Kenney, Starter Kit City Builder (CC0). Font Lilita One: licenza SIL OFL 1.1 (`kenney/font/OFL.txt`).
