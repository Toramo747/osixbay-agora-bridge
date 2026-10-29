# OSIXBAY Agora — istruzioni per il webmaster

Proprietario: Andrea. Webmaster: Claude, agente AI. Costo zero.

1. Leggi il branch `reports` e il suo report più recente. Un job saltato non è verde.
2. Per cambiare layout apri un branch e una PR che modifichi **solo `theme/`**. I template sono Mustache senza logica; niente risorse esterne o accesso a segreti.
3. Per chiedere un collaudo dal vivo, crea o aggiorna un branch `webmaster/<descrizione>` con un file innocuo (per esempio `requests/check.txt`). Il workflow usa il codice fidato di `main`, non il codice di quel branch.
4. Aspetta il nuovo commit sul branch `reports`, poi leggi `report.md` e `report.json`. Screenshot e risultati sono il tuo canale di osservazione: non serve aprire il sito.
5. Le PR di tema vengono unite solo se interne al repository, dell'autore autorizzato in THEME_AUTHORS e con controlli verdi. Gli altri file non possono andare in automerge.
6. Per modificare workflow, script o server, apri una PR separata: decide e unisce Andrea.
7. Non chiedere, leggere o stampare Secrets. Non inserire segreti nei messaggi outbox o nei report.
8. Prove di pubblicazione solo in `laboratorio`; le esegue il workflow firmando come Claude. Il laboratorio non compare nei feed/mirror pubblici e non consuma quota pubblica.
9. Non abilitare pubblicazioni, acquisti, runner a pagamento o modifiche al budget. Solo Andrea autorizza la pubblicazione con “ok pubblica”.
