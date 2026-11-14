# OSIXBAY Genesis — ECO-LONG-13 su Kaggle (CPU, offline)

## Stato e vincoli
Esperimento di ricerca **non canonico**. Sorgente privata; non pubblicare il dataset su Kaggle in modalita pubblica. Nessun costo volontario, GPU, accesso Internet durante le esecuzioni, deploy, merge, aggiornamento Cloudflare, Godot o Agora.

## Preparazione riproducibile
1. Aprire GitHub Actions `genesis-eco-long13-kaggle-audit` sul ramo `feature/genesis-eco-long13-kaggle-batch-20261114`.
2. Solo dopo **SUCCESS**, scaricare l'artifact `genesis-eco-long13-kaggle-source-and-audit`. Contiene una cartella `long13_results/` con la matrice gia verificata e `OSIXBAY_ECO_LONG13_KAGGLE_SOURCE.zip`.
3. Su Kaggle, creare un **dataset privato** dal solo file `OSIXBAY_ECO_LONG13_KAGGLE_SOURCE.zip` (non pubblicarlo).
4. Creare un nuovo notebook Kaggle, con **Accelerator: None**, **Internet: Off**; allegare il dataset privato alla sezione Input.
5. Il file `kaggle/eco_long13_cpu.ipynb` e gia nel pacchetto; caricarlo come notebook o copiarne il codice nella prima cella. Eseguire.
6. Scaricare `/kaggle/working/eco_long13_results/` o salvare una versione notebook con output. Conservare `summary.json`, `cohorts.csv`, `events.csv`.

## Quantita e parallelismo
Il primo esperimento usa tre semi `11,23,37` per sei frazioni prole (`12%,18%,24%,32%,40%,48%`), 18 casi da 1200 tick, equivalenti a 100 anni **simbolici** (12 tick per anno). Per ampliare il campione, modificare la lista dei semi nella cella (max 50 per batch); piu notebook possono usare gruppi disgiunti di semi. Non lanciare simultaneamente modifiche ai moduli globali nello stesso processo Python: ogni caso deve restare isolato e deterministico.

## Controlli scientifici
- `pre_potential` rappresenta una **stima prima del tick**, non nascita garantita. La crescita/redistribuzione di biomassa nel tick cambia i valori.
- `births_on_year` e cumulativo nella stessa patch/specie; le nascite effettive sono in `events.csv`.
- Il controllo di una coorte adulta a fine tick puo risultare falso a causa del cooldown successivo alla nascita. Non interpretarlo come infertilita.
- Morti giovanili e adulte sono classificate dall'eta prima dell'aggiornamento, non da una diagnosi fisiologica completa.
- Verifica per ogni tick: massa e acqua conservate; prole generata da genitore tracciabile; nessuna apparizione o risurrezione artificiale.
- La F01 originale della PR88 rimane distinta dal proxy ECO-P0 della PR93.

## Provenienza
GitHub fornisce l'artifact del collaudo; Kaggle agisce solo come esecutore CPU dei batch; Drive conserva report verificati. Il notebook non possiede credenziali Kaggle, GitHub, token o chiavi Cloudflare, non invia dati a Internet e non programma esecuzioni automatiche.

## Stato del servizio
La creazione e l'esecuzione di notebook nell'account Kaggle richiedono che il proprietario lo configuri o colleghi un'integrazione autorizzata. La sola presenza del codice su GitHub non prova un run Kaggle.
