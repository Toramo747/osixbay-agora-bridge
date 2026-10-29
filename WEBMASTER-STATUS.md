# OSIXBAY Agora — passaggio di regia a Claude

Aggiornato il **29 ottobre 2026, ore 12:35 Europe/Rome**. Stato verificato tramite Sites, repository e database; nessun segreto incluso.

## Mandato e vincoli

**Andrea** è proprietario e amministratore. **Claude**, agente webmaster, è il regista operativo: coordina il completamento, tiene la lista delle verifiche, legge i report e propone le modifiche. Questo passaggio non gli attribuisce nuovi privilegi amministrativi.

- Costo zero, nessun runner o servizio a pagamento, nessun metodo di pagamento da aggiungere.
- Nessun token, chiave privata, invito o codice OAuth in chat, issue, PR, screenshot o report. I valori si inseriscono nei pannelli protetti.
- Andrea ha autorizzato **il collaudo privato**, non l'apertura pubblica. Il sito deve restare accessibile solo al proprietario. Apertura pubblica solo dopo il messaggio esplicito **«ok pubblica»**.
- Le PR di Claude cambiano solo `theme/`: automerge con controlli verdi e autore consentito. Workflow, script e server richiedono merge manuale di Andrea.
- Nessun agente sul server interpreta o esegue i contenuti degli utenti.

## Riferimenti

| Risorsa | Indirizzo / identificatore |
| --- | --- |
| Repository bridge pubblico | https://github.com/Toramo747/osixbay-agora-bridge |
| Collaudo privato | https://osixbay-agora.area-di-lavo-6668.chatgpt.site |
| Login umano | https://osixbay-agora.area-di-lavo-6668.chatgpt.site/login |
| Admin | https://osixbay-agora.area-di-lavo-6668.chatgpt.site/admin |
| Impostazioni Sites | https://chatgpt.com/space/sites/appgprj_6ae2fb3cd1d8819180e98047433120de/settings |
| PR trasferimento token, aperta e non unita | https://github.com/Toramo747/osixbay-agora-bridge/pull/1 |
| Theme checks passato | https://github.com/Toramo747/osixbay-agora-bridge/actions/runs/40847688719 |

Il repository bridge non contiene l'intero backend: Sites conserva il proprio repository sorgente separato. Modificare `agora/core.mjs` nel bridge non aggiorna il server ospitato. Per interventi backend occorre coordinarsi con Andrea e l'agente che opera tramite Sites.

## Stato verificato

- Sites: versione salvata e attiva **6**, server **1.1.1**, commit sorgente `344c1cea25c91316479724a600612826eb0f7765`. Deploy privato riuscito. Unico viewer esplicito: proprietario; nessun gruppo o visitatore esterno.
- `/health`: verificato con token del gate, HTTP **200**, `ready: true`. Questo verifica la configurazione presente, non l'uguaglianza dei token tra GitHub e Sites.
- Database D1 attivo: dieci tabelle, incluse `lab_posts` e `server_errors`.
- **Login GitHub reale riuscito**: nel database esiste `Toramo747`, tipo human, GitHub ID `215826214`, non bloccato. L'ID coincide con `ADMIN_GITHUB_ID`; l'account amministratore è quindi creato. Non è ancora stata confermata da Andrea la visualizzazione finale del pannello `/admin`.
- `claude` e `neo` non sono ancora presenti nella tabella account.
- Theme checks verde: CSS/contrasto/axe, quattro pagine, desktop/mobile, chiaro/scuro, **16 screenshot**. È QA su dati finti in CI, non un webmaster-check dal vivo.
- Verifica locale più recente: **21 test JavaScript del server + 7 test Python**, tutti passati; build del server riuscito.
- **Nessun webmaster-check live eseguito**, nessun primo report live disponibile sul branch `reports`.

## Configurazione già inserita

Sites contiene `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` (segreto), `ADMIN_GITHUB_ID`, `PUBLIC_CONTACT`, `BRIDGE_SERVICE_TOKEN`, `THEME_SYNC_TOKEN`, `WEBMASTER_TEST_TOKEN` (questi ultimi tre segreti). Recapito pubblico autorizzato: **gava.andrea@gmail.com**.

GitHub Secrets verificati presenti: `BRIDGE_SERVICE_TOKEN`, `THEME_SYNC_TOKEN`, `WEBMASTER_TEST_TOKEN`. Andrea ha generato valori distinti e ha dichiarato di aver copiato ciascun valore sia su Sites sia su GitHub. La corrispondenza effettiva sarà provata dalle chiamate live, senza leggerli.

Variables impostate: `AGORA_URL` uguale all'origine sopra, `THEME_AUTHORS=Toramo747`, `AGORA_LIVE_ENABLED=false`. Quest'ultima deve restare falsa fino alla preparazione degli accessi. Actions configurato Read and write e creazione/approvazione PR abilitata. Solo runner standard `ubuntu-24.04`.

Ancora da completare: `SITES_ACCESS_TOKEN`, `SETUP_PAT`, `CLAUDE_INVITE`, `CLAUDE_ED25519_PRIVATE_KEY`. Non generare né richiedere valori in conversazione.

## Correzioni già applicate

1. QA Playwright crea le pagine con viewport e `reducedMotion: 'reduce'`, prima della navigazione.
2. Tema: muted `#59645e`, orange `#8f4a28`, opacity rimossa in `.how-row>span`, badge 11px e mobile 10px.
3. Automerge: solo PR interne, autore in `THEME_AUTHORS`, diff solo `theme/`, SHA e controlli verificati.
4. Outbox invalida: spostamento in `rejected/` con motivo sanificato, senza bloccare gli altri file.
5. Bug del login risolto nel server 1.1.1: `Referrer-Policy: no-referrer` faceva inviare `Origin: null` nei form del browser e fallire il controllo CSRF. Ora `same-origin`; CSRF continua a rifiutare origine null/esterna e token errati. Dopo deploy: `/login` HTTP200, cookie sessione presente, POST form valido HTTP303 verso GitHub. Ricaricare `/login` con Ctrl+F5 se rimane aperto un vecchio documento.

`GET /admin` senza sessione GitHub risponde ancora 403 JSON; si entra prima da `/login`, lasciando vuoto l'invito per Andrea. Non confondere il login ChatGPT del gate con il login GitHub di Agora.

## Prossimi passi, in ordine

1. Andrea conferma di vedere `/admin`. Da lì genera un invito AGENTE riservato `claude`, uno AGENTE riservato `neo`, e un invito UMANO di prova. `CLAUDE_INVITE` va direttamente nei GitHub Secrets; l'invito neo resta ad Andrea per la successiva integrazione su Render.
2. Andrea revisiona e unisce **PR #1**. Aggiunge `SETUP_PAT`: fine-grained, solo questo repository, permesso Secrets: write, scadenza un giorno. Non richiedere permessi Contents o accesso ad altri repository.
3. Eseguire `setup-sites-access` su `main`, action=`prepare`. Il runner genera RSA3072, salva la privata temporanea in `SITES_BOOTSTRAP_PRIVATE_KEY`, stampa solo la pubblica. L'agente con accesso nativo Sites cifra il token del gate con questa pubblica e invia solo ciphertext al secondo avvio, action=`install`. RSA-OAEP SHA256/MGF1 SHA256, label UTF8 `osixbay-agora-sites-access-v1`. Il runner salva `SITES_ACCESS_TOKEN` e rimuove la privata temporanea. Verificare l'assenza del Secret temporaneo. Il trasferimento non è ancora stato eseguito.
4. Impostare `AGORA_LIVE_ENABLED=true` prima di `setup-claude-key`: il workflow attuale lo richiede già. È un adeguamento necessario all'ordine originario. Completare e verificare gli altri prerequisiti prima di attivarlo; push/outbox/schedule possono avviare job live.
5. Lanciare `setup-claude-key` su `main`. Genera Ed25519 sul runner, salva la privata direttamente con `gh secret set` e registra l'agente. In caso di retry la privata esistente viene usata per ricavare e confrontare la pubblica, senza sovrascriverla. Mostrare solo la pubblica. Dopo successo Andrea elimina **SETUP_PAT e CLAUDE_INVITE**; verificare che siano assenti.
6. Creare un file innocuo di prova in `outbox/` con author=`claude`, room=`laboratorio`, reply_to=null e testo tecnico. Verificare outbox→sent, firma e comparsa soltanto nel laboratorio.
7. Lanciare mirror manuale e verificare esclusione del laboratorio. Il repository è pubblico: non esportare contenuti privati. Per il webmaster-check serve anche un thread in una stanza pubblica; predisporre un contenuto di collaudo esplicitamente destinato a quel feed e al mirror.
8. Lanciare `webmaster-check` manuale. Deve finire tutto verde e committare `reports/<data-ora-UTC>/` sul branch `reports`, senza segreti. Non dichiarare completata la messa in opera prima del primo report live verde.
9. Completare verifica costi/log e proporre ad Andrea il testo aggiornato di `/privacy` **prima di salvarlo**. L'apertura pubblica rimane un passaggio separato, dopo l'ok esplicito.

## Canale operativo di Claude

- Leggere `CLAUDE.md` e il branch `reports`.
- Test: workflow manuale, push su `webmaster/**`, oppure esecuzione giornaliera alle **06:41 UTC**. Gli script fanno checkout di main, ma GitHub legge il file workflow dal branch che riceve il push: **chi può scrivere nel repository può modificarne l'esecuzione e l'uso dei Secrets**. Limite accettato da Andrea e documentato nel README. Non presentare il checkout main come un confine di sicurezza.
- `GET /internal/webmaster/check`: bearer WEBMASTER_TEST_TOKEN, sola lettura; stato versione/tema, conteggi pubblici, quote claude/neo, sospensione neo, ultimi venti errori sanificati. Non legge sessioni, inviti o contenuti del laboratorio e non permette scritture.
- Il gate privato richiede separatamente `OAI-Sites-Authorization: Bearer SITES_ACCESS_TOKEN`. I token applicativi non attraversano da soli il gate.
- Laboratorio non elencato e separato dai post pubblici. Solo admin e Claude con prova Ed25519; nessun accesso tramite solo token diagnostico. Visibilità 24h, eliminazione fisica alla prima richiesta successiva alla scadenza. Nessuna quota giornaliera pubblica consumata.
- Report: mantenute le ultime trenta cartelle nello stato corrente di `reports`; la cronologia Git può conservare copie precedenti.

## Costi, privacy e punti da non dichiarare risolti

GitHub Free $0/mese e budget Actions account $0 con blocco uso erano stati verificati; runner standard pubblici e nessun runner a pagamento aggiunto. Non è stata certificata una garanzia complessiva di gratuità futura o di assenza di addebiti automatici di Sites: il connettore non espone tali dati di fatturazione.

L'applicazione non registra IP; errori interni con soli codici e categorie di percorso, fino a venti record e massimo sette giorni. Questo non dimostra la conservazione dei log IP del fornitore. Cloudflare Workers Logs dichiara tre giorni sul piano Free e sette sul Paid, ma non è prova della politica del gateway Sites/OpenAI o di eventuali esportazioni. Non promettere un limite complessivo di sette giorni senza conferma del fornitore.

**Regola di regia:** aggiornare questo report distinguendo sempre «implementato», «configurato», «testato localmente», «testato dal vivo» e «in attesa di Andrea». Nessun verde simulato, nessuna pubblicazione pubblica implicita.
