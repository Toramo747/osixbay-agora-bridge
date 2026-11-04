# Genesis — vista 3D

Scena Godot 4.6.3 che mostra il mondo di Genesis in 3D low-poly, da aprire sul computer del ponte.

- **Aprire:** in Godot 4.6.3 → Importa → questa cartella → Esegui (F5).
- **Dati:** scarica `bots/genesi/mondo.json` da GitHub (seme e zone) e ricalcola il terreno con la stessa formula di `bots/dati/genesi_costruttore.gd`. Biomi e risorse coincidono con quelli del ponte; rilievo, alberi e acqua sono solo resa grafica.
- **Comandi:** trascina = ruota · rotella = zoom · WASD/frecce = sposta · Q/E = ruota · Spazio = giro automatico · R = ricarica il mondo.
- **Controlli senza schermo:** `godot --path . -- --mondo=mondo.json --foto=vista.png` salva una foto ed esce.

Grafica: terreno, alberi, rocce, cactus, argilla, pesci e nuvole sono generati dal codice. I ciuffi d'erba (`modelli/grass-small.glb`, `modelli/Textures/colormap.png`) sono di Kenney, Starter Kit 3D Platformer, licenza CC0.
