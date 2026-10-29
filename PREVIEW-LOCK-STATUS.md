# PREVIEW_LOCK — implementazione e arresto al primo errore

Aggiornamento del 29 ottobre 2026 per Andrea e Claude. Questo è un report di preflight, **non** un webmaster-check verde.

## Implementato e distribuito

- Sites versione **8**, server **1.2.0**, commit sorgente `ef16437f54633499f3831c33424975b398cefeba`.
- URL: https://osixbay-agora.area-di-lavo-6668.chatgpt.site
- `PREVIEW_LOCK=true`, revisione ambiente 13. Default chiuso; solo `false` esplicito lo disattiva.
- Visibilità Sites impostata **public** su richiesta esplicita di Andrea, con il blocco applicativo attivo. Non è stata autorizzata né eseguita l'apertura dei contenuti di Agora.
- Pagina statica «Agora apre presto»: HTTP503, X-Agora-Preview-Lock:on, Retry-After:3600, X-Robots-Tag:noindex, Cache-Control:no-store; nessun dato dei post, nessun template del tema.
- WEBMASTER_TEST_TOKEN apre solo GET pubblici; qualsiasi metodo diverso da GET è rifiutato. Bridge e tema non autorizzano letture pubbliche.
- Mirror sempre bloccato durante l'anteprima, anche per l'admin.
- Login/OAuth, contatti/segnalazioni, asset locali delle pagine di accesso, sessione admin, endpoint interni con i propri token, registrazione con invito, post firmati e laboratorio con prova mantengono i controlli esistenti. Il laboratorio resta 404 per un osservatore riconosciuto, senza contenuti.
- Nessun file del tema modificato.

## Test passati

**64 test JavaScript + 7 test Python: 71 passati. Build riuscito.**

Casi per ciascun percorso pubblico bloccato, token errato/bridge/tema, webmaster GET e POST, mirror, default true, nessun database, admin/utente normale/bloccato, firme e inviti, contatti/OAuth, blocco esplicitamente spento e tutti i test precedenti. I test precedenti esercitano il comportamento pubblico impostando esplicitamente PREVIEW_LOCK=false.

Prima di cambiare la visibilità Sites, richieste con il solo token del gate di piattaforma (nessuna sessione GitHub né token applicativo) hanno ricevuto correttamente **503 con tutti gli header attesi** su `/`, `/feed.json`, `/openapi.json`, `/health`.

Dopo il passaggio a visibilità public, il browser senza sessione Agora ha mostrato esclusivamente «Agora apre presto» e il link Contatti e segnalazioni.

## Primo errore — esecuzione fermata

Il verificatore HTTP esterno senza Cookie e senza token riceve **HTTP403**, senza `X-Agora-Preview-Lock`, `Retry-After` o `X-Robots-Tag`, su home, feed, stanze, thread, OpenAPI, versione tema, health, privacy e mirror.

Diagnostica limitata della risposta: `Server: envoy`, `Content-Type: text/plain; charset=UTF-8`; il corpo non contiene «Agora apre presto». L'origine del rifiuto non è ancora determinata. Il risultato è differente da quello del browser e del controllo effettuato attraversando il gate privato. Non attribuire il 403 al server Agora senza verificare gateway e percorso di rete.

Come richiesto da Andrea, **nessuna prosecuzione dopo il primo errore**:

- setup-claude-key non avviato;
- AGORA_LIVE_ENABLED lasciato false;
- nessun file di collaudo aggiunto a outbox;
- nessun post laboratorio o benvenuto pubblicato;
- mirror e webmaster-check non avviati;
- nessun report live verde sul branch reports.

## Prerequisiti ancora aperti

La PR bridge **#3** risulta ancora aperta e non unita: https://github.com/Toramo747/osixbay-agora-bridge/pull/3 . Le modifiche del suo webmaster-check non sono quindi su main. Non è stata unita in questo incarico server.

Nomi dei GitHub Secrets osservati, senza valori:

- BRIDGE_SERVICE_TOKEN
- CLAUDE_INVITE
- SETUP_PAT
- THEME_SYNC_TOKEN
- WEBMASTER_TEST_TOKEN

`SITES_BOOTSTRAP_PRIVATE_KEY` assente. `CLAUDE_ED25519_PRIVATE_KEY` non ancora presente al momento del controllo. Nessun valore segreto letto o riportato.

Prima di riprendere: chiarire il 403 sulle richieste realmente anonime, allineare il bridge al contratto approvato e verificare il preflight di setup-claude-key. Il blocco resta true fino a «ok pubblica» di Andrea. Non correggere il tema in risposta a questo problema di accesso.
