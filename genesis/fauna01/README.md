# OSIXBAY Genesis — FAUNA-02 / F01 (candidato tecnico)

**Stato:** PROTOTIPO IN PR DRAFT, NON CANONICO, NON INTEGRATO. Issue di coordinamento: [#87](https://github.com/Toramo747/osixbay-agora-bridge/issues/87).

## Scopo
Isolare dal dialogo libero di Agora un **algoritmo eseguibile** per una prima specie biologica *candidata F01*. Questo non approva una specie, non simula l'intero pianeta e non autorizza alcuna modifica al Cloudflare Worker, Agora, Godot locale o produzione.

**Habitat di riferimento:** griglia sintetica di celle adatte/non adatte, usata solo per collaudo. La scelta di P01 e la biologia finale dipendono dai residenti e dall'approvazione di Andrea. Numeri in `Parameters` sono valori **esemplificativi**, non costanti fisiche o chimiche del pianeta.

## Modello minimo
- Cella: `suitable`, `food`, `danger`; cibo limitato dalla `capacity` e ricrescita per tick.
- Organismo: identificativo stabile, coordinate, energia, età, cooldown e due tratti ereditabili (`threshold`, `efficiency`).
- Un tick deterministico applica: metabolismo; morte; percezione di 4 vicini + cella attuale; fuga dal pericolo, ricerca cibo oppure riposo; riproduzione pagata in energia con piccola mutazione limitata; rigenerazione risorse.
- PRNG esplicito a 64 bit con seed e stato serializzabili. Nessun LLM per tick.
- `snapshot()` e `World.from_snapshot()` permettono la ripresa dello stato; l'ordine dei turni è per ID.

## Esecuzione locale (Python >=3.10, standard library)
Dalla root del repository:

```sh
python3 genesis/fauna01/sim.py
python3 -m unittest discover -s genesis/fauna01/tests -v
```

**Evidenza locale prima della PR:** 13/13 test `unittest` superati. Esempio seed=13, 80 tick: 14 vivi, 34 nati, 22 morti, cibo restante 114.6 (risultato di configurazione esemplificativa; non misura della fauna reale né del server). Gli stessi test devono essere rieseguiti sul codice **esatto della PR** prima del merge.

## Dieci gate: contano solo prove
1. **Selezione specie/habitat:** *BLOCKED*: biologia canonica non ancora approvata.
2. **Anatomia/locomozione:** *PARZIALE*: coordinate e movimento di griglia, anatomia non definita.
3. **Energia/materia:** *PROTOTIPO*: bilancio energetico illustrativo, nessuna biochimica approvata.
4. **Percezione:** *PROTOTIPO*: cibo/pericolo adiacente.
5. **Comportamenti:** *PROTOTIPO*: foraggiamento, fuga, riposo, riproduzione.
6. **Ereditarietà:** *PROTOTIPO*: due tratti trasmessi con mutazione limitata.
7. **Ecologia:** *PROTOTIPO*: risorse finite, competizione implicita e mortalità.
8. **Algoritmo:** *IMPLEMENTATO LOCALMENTE*: `sim.py` deterministico.
9. **Test:** *13 TEST LOCALI SUPERATI*; ulteriori prove necessarie su grandi popolazioni e su CPU/tempo cloud.
10. **Consegna:** *PARZIALE*: test e sorgenti pronti per revisione; mancano scheda specie condivisa, adapter GPLE/Godot e accettazione scientifica.

**Non dichiarare i gate conclusi** finché ogni criterio specificato nella issue #87 non è attestato.

## Revisione e integrazione futura
- **Residenti Agora:** valutazione di anatomia, metabolismo, genetica, ecologia e falsificazioni nella stanza privata `genesis`; non copiare messaggi privati in GitHub. Usare solo conclusioni esplicitamente approvate per la pubblicazione.
- **Sviluppatore:** migliorare e verificare il simulatore, mantenendo una PR draft. Implementare un adapter separato per World Engine autoritativo e client Godot 4.6.x soltanto dopo aver letto i contratti reali, con dati canonici approvati.
- **Sicurezza:** niente segreti, dipendenze a pagamento, azioni Cloudflare, deploy, merge automatici o modifica di configurazioni Agora.
- **Limiti dichiarati:** dinamiche ecologiche semplificate; assenza di predazione, agenti cognitivi, animazioni, geometria 2.5D e misure prestazionali; seed riproducibile in Python ma non ancora verificato come identico in Godot/JS.


## 10 novembre 2026 — Verifica ampliata della PR #88
- Ripetuti i 13 test Python sui file esatti della PR originale (blob SHA verificati): **13/13 PASS**.
- Aggiunti `sim.mjs` e `tests/test_parity.mjs`, con parità numerica dei modelli Python/JavaScript ai tick 0, 1, 2, 20, 80, 200 per quattro scenari: **7/7 PASS**.
- Controllato con Git blob SHA che il codice JavaScript pubblicato corrisponde al codice effettivamente testato.
- Stress test Python: **10.000 tick, 500 cap, griglia 64×64**; risultati di runtime locale, NON cloud.
- Vedi `INTEGRAZIONE_E_REVISIONE.md` per la proposta di adapter Cloudflare/Godot, **non implementato**.
- Rimangono bloccati: specie biologica canonica, revisione esterna della PR, test sul Worker reale, persistenza SQLite integrata e visualizzazione Godot.
- **La PR resta draft.** Questi test non autorizzano merge né deploy.
