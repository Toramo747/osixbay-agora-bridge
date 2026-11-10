# Contratto di importazione habitat demo → fauna F01 (v1)

**Stato: contratto proposto. Nessun export reale della scena demo esiste ancora** (`authoritative_mask_imported: false` nella scheda F01). Finché manca, l'integrazione reale resta ferma: l'adapter rifiuta ogni habitat sintetico se non è acceso l'interruttore di prova `FAUNA_FIXTURE_SINTETICA=1`.

Lo produce un exporter Godot dalla **scena demo realmente usata** (da scrivere, lato Godot). L'adapter non genera né corregge nulla: convalida e proietta.

## File JSON

| Campo | Significato | Regola |
|---|---|---|
| `schema` | `osixbay.genesis.habitat.demo-export` | obbligatorio |
| `version` | `1` | altre versioni rifiutate |
| `zone_id` | identificativo zona demo | `[a-z0-9_.-]`, max 64 |
| `synthetic` | `false` per un export reale | deve coincidere con `source.kind` |
| `source` | `kind: godot_export`, `scene`, `commit`, `exported_at`, `exporter` | tutti obbligatori per un export reale |
| `grid.width/height` | celle | max 256 per lato, max 4096 celle totali |
| `grid.cell_size_m` | lato cella in metri | > 0 |
| `grid.origin_world` | `[x, z]` Godot dell'angolo della cella (0,0) | conversione: centro cella = origine + (indice + 0,5) × lato |
| `biomes` | legenda simbolo → nome bioma | un carattere per simbolo |
| `layers.playable` | righe di `0`/`1` | `1` = realmente percorribile |
| `layers.biome` | righe di simboli della legenda | |
| `layers.food_capacity` / `food_initial` / `food_regrowth` | matrici numeriche per cella | ≥ 0; **zero è lecito**; iniziale ≤ capacità |
| `layers.danger` | matrice 0..1, facoltativa | solo se deriva da stato reale del mondo |
| `species.F01.suitable_biomes` | biomi idonei a F01 | decisione biologica di Andrea, non dell'adapter |
| `species.F01.spawn` | celle iniziali `[x, y]` | 1–50, tutte dentro `playable AND suitable` |
| `sha256` | hash del JSON canonico senza questo campo | identifica la versione dell'habitat |

Proiezione: `suitable = playable AND bioma ∈ suitable_biomes`. Fuori da `suitable` il cibo vale zero per F01, qualunque cosa dica l'export.

Con 150 × 150 m e il tetto di 4096 celle la cella non può essere più piccola di circa 2,4 m. La risoluzione la sceglie chi esporta.

## Cosa manca per un export reale (non decidibile dall'adapter)

1. Scena demo e commit validati; exporter Godot di mask, biomi e risorse.
2. Unità e quantità del cibo reale per i tre microambienti, e loro rinnovabilità.
3. Biomi idonei e punti di comparsa di F01.
4. Durata del tick biologico (`FAUNA_TICK_OGNI`) e parametri metabolici: oggi sono i valori di prova di `sim.mjs`.

Cambiare habitat sotto una zona già viva la mette in stato `sospesa` (`habitat_diverso`): serve una migrazione esplicita, non automatica.

## Fixture

`fixtures/habitat_sintetico_v1.json` è **dichiaratamente sintetica** (`synthetic: true`, generata da `tests/genera_fixture.mjs`): 24 × 24 celle, bordo irregolare, tre biomi più acqua e roccia nuda. Serve solo ai test. Non è la demo.
