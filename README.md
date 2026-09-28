# KZ Job Radar (prototipo locale)

Una piccola applicazione personale per **scoprire e valutare** offerte di lavoro.
Non si candida al posto tuo, non accede a LinkedIn/Indeed e non promette di trovare tutte le offerte.
Usa solo Python 3 (nessun `pip install` richiesto).

## Avvio su Windows

1. Estrai l'intero archivio ZIP in una cartella, per esempio sul Desktop.
2. Installa Python 3 se non è già presente (in precedenza avevi Python 3.13).
3. Fai doppio clic su `AVVIA_SU_WINDOWS.bat`.
4. Se il browser non si apre automaticamente, vai su `http://127.0.0.1:8765`.
5. Tieni aperta la finestra nera: se la chiudi, l'app e il monitoraggio si fermano.

Se il doppio clic non funziona: apri il Prompt dei comandi nella cartella e usa `py -3 start.py`.
L'app è accessibile **solo dal tuo computer**. Gli annunci e le preferenze sono in `data/jobs.sqlite3`, che viene creato al primo avvio. Il file non è incluso nello ZIP iniziale.

## Come usarla

- `Cerca annunci ora`: interroga le fonti abilitate; durante il primo test potresti vedere pochi annunci locali.
- `Controlla ogni ora`: attiva il monitoraggio mentre l'app resta aperta; di default è **spento**.
- `Abilita pulsanti GPT`: fa apparire l'analisi facoltativa su ciascun annuncio; di default è **spenta**. Attivare l'interruttore **non** genera chiamate né spese. Solo il clic su `Analizza con GPT` esegue una singola chiamata per quell'annuncio.
- Stato dell'annuncio: puoi segnare `Interessante`, `Candidatura inviata` (dopo averla fatta tu) o `Scartato`.
- `Aggiungi azienda`: se conosci un sito carriere Greenhouse o Lever, inserisci il codice dell'azienda che compare nella URL.
- `Aziende del Triveneto da consultare`: rubrica di 14 collegamenti ufficiali verificati il 28 settembre 2026; FiloBlu rimanda alla pagina contatti, che non mostra gli annunci. Due bacheche di esempio sono seguite automaticamente nelle nuove installazioni; le altre sono collegamenti da controllare di persona. Le sedi indicate non certificano tempi di viaggio né la presenza di annunci aperti.
- `Importa alert selezionati`: esporta un alert LinkedIn/Indeed dalla tua casella di posta come file `.eml` e selezionalo nell'app; vengono raccolti solo i link diretti riconosciuti. Gli alert non vengono controllati automaticamente e l'email non viene conservata.
- `Aggiungi un annuncio`: incolla manualmente un link e il titolo, per esempio da LinkedIn o Indeed. Il programma **non legge** automaticamente il contenuto di quel link.

Gli annunci sono divisi tra `Data della fonte entro 24 ore` (la fonte fornisce una data, non necessariamente la prima pubblicazione dal datore di lavoro),
`Data di pubblicazione non disponibile` (per esempio Greenhouse list), e più vecchi.
"Scoperto ora" non significa "pubblicato ora". Il punteggio 0-95 è solo una graduatoria
spiegabile, non una stima statistica della probabilità di assunzione.

## Fonti e copertura reale

- [Arbeitnow API](https://www.arbeitnow.com/blog/job-board-api), interrogata fino a 2 pagine per controllo. Richiede un link alla fonte: ogni annuncio visualizza la sua fonte e il collegamento originale. Ha copertura europea, ma non garantisce la zona di Padova.
- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html) e [Lever Postings API](https://github.com/lever/postings-api): due bacheche Greenhouse di esempio (`autoscout24` e `lovable`) sono preimpostate **per le nuove installazioni**; puoi aggiungere fino a 30 bacheche compatibili. Nessuna garanzia che tutte le posizioni delle aziende siano ospitate su queste piattaforme. Le impostazioni di un database già esistente non vengono modificate.
- [The Adzuna API](https://developer.adzuna.com/docs/search): fonte facoltativa per ricerche in Veneto. Registrati per ricevere `app_id` e `app_key`; i [termini](https://developer.adzuna.com/docs/terms_of_service) prevedono limiti e attribuzione della fonte. Tre ricerche all'ora al massimo (e-commerce, back office, marketing), restando sotto il limite predefinito dichiarato anche con monitoraggio continuo. I risultati Adzuna sono identificati come tali e aprono il loro link originale. Nessuna garanzia di completezza e nessuna falsa RAL stimata.

Per abilitare Adzuna solo nella sessione corrente, dal **Prompt dei comandi** aperto in questa cartella (non incollare chiavi in chat):

```bat
set ADZUNA_APP_ID=IL_TUO_ID
set ADZUNA_APP_KEY=LA_TUA_CHIAVE
py -3 start.py
```

Le chiavi non vengono archiviate in SQLite, mostrate nell'interfaccia o incluse nell'archivio ZIP.
Senza chiavi Adzuna, il resto del programma funziona comunque.

**Non interroga direttamente LinkedIn/Indeed**, né scavalca login, CAPTCHA o limiti. Non può garantire l'arrivo di ogni nuovo annuncio. Una ricerca specifica per azienda richiede che l'azienda usi una delle fonti disponibili.

| Fonte | Stato reale nell'app |
| --- | --- |
| Adzuna API | Ricerca automatica in Veneto **solo** con chiavi API configurate sul tuo PC. |
| EURES | Collegamento al portale per consultazione personale: **non importato**. I [termini del servizio «Find a job»](https://europa.eu/eures/portal/jv-se/home?lang=it&pageCode=find_a_job) vietano di estrarre gli annunci per elaborarli o ripubblicarli. |
| LinkedIn e Indeed Job Alert | Importazione **manuale** di email `.eml` selezionate da te. La pagina degli annunci e la casella email non vengono interrogate dall'app. |
| Siti aziendali / portali ATS | Solo le bacheche Greenhouse/Lever già configurate o aggiunte da te; gli altri siti non vengono seguiti automaticamente. |
| Tutte le aziende del Triveneto | **Non coperte**: non esiste un elenco universale già configurato; tante aziende usano siti, ATS e modalità di pubblicazione differenti. |

### Demo online su Streamlit Community Cloud

La [demo online](https://kz-job-radar.streamlit.app/) usa `app.py` e `requirements.txt` su Streamlit Community Cloud. Mostra annunci pubblici delle tre fonti abilitate (Arbeitnow, AutoScout24, Lovable) e una rubrica di 14 pagine aziendali. All'apertura mostra soltanto gli annunci con località esplicitamente indicata nel Triveneto; puoi scegliere «Tutte le sedi» per allargare la ricerca. Le richieste pubbliche condividono una cache di un'ora. Non sono caricati il tuo CV originale, indirizzi email né credenziali API; il codice contiene soltanto una lista generica di competenze e città per il punteggio.

La demo **non sostituisce** la versione Windows: niente ricerca ogni ora mentre nessuno la visita, niente salvataggio degli stati, importazione email, GPT o chiavi Adzuna. Queste funzioni richiedono l'app locale per evitare di esporre email e preferenze personali in un'app pubblica. Quando Community Cloud è inattivo, può andare in sospensione. Non pubblicare mai la cartella `data/`, le email `.eml` o chiavi API nel repository.

Gli alert `.eml` con soli link di tracciamento potrebbero importare zero annunci. L'app non confonde la data di ricezione dell'email con la data di pubblicazione: apri il link e verificala sul portale. Non inserire nell'app email personali diverse dagli alert di lavoro.

## AI: opzionale e a consumo separato

Per attivare davvero il pulsante GPT occorre una **chiave OpenAI API** associata a un account con fatturazione API separata dall'abbonamento ChatGPT. Dal Prompt dei comandi (non condividere la chiave):

```bat
set OPENAI_API_KEY=LA_TUA_CHIAVE
py -3 start.py
```

La chiamata è sempre manuale, **una offerta alla volta**; non è avviata dal monitoraggio.
Per evitare di inviare dati personali, manda all'API solo una lista essenziale di competenze
estratte dal CV e il testo dell'annuncio. La risposta è salvata localmente. Se disattivi
l'interruttore, non sono più possibili nuove chiamate dall'interfaccia. Il modello predefinito
è `gpt-5-mini`; si può cambiare con `JOB_RADAR_AI_MODEL` nell'ambiente.

## Scelte trasparenti

- CV italiano/inglese non sono inclusi nello ZIP, né copiati nel database: soltanto le competenze utili al filtro, senza telefono, email, referenze o indirizzo civico.
- Base: Padova. Padova, Mestre, Treviso e Vicenza hanno priorità; Venezia, Rovigo e Verona sono zona estesa. Le città non equivalgono a minuti di viaggio: **45 minuti è un obiettivo da verificare su Maps**, non un tempo calcolato dal programma.
- Retribuzione non dichiarata = `RAL da verificare`, non motivo per escludere l'annuncio.
- I ruoli manuali vengono esclusi in base al *titolo* (operaio, magazziniere, tornitore, autista, ecc.), non in base alla sola presenza di parole come `logistica` nella descrizione.
- Quando un sito non risponde, l'errore della fonte è mostrato e le altre fonti continuano a funzionare.
- Nessuna candidatura automatica, nessuna schedulazione quando l'app è chiusa, nessun uso automatico di token GPT.

## Verifiche (senza rete e senza spese)

```bat
py -3 -m unittest discover -s tests -v
```

Prototipo locale personale; non è un prodotto o un'affiliazione con le fonti elencate.
