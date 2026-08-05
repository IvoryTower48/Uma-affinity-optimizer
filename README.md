# Uma Legacy Loop Optimizer

Tool per pianificare "legacy loop" (gruppi chiusi di 5 umamusume che si
allenano a vicenda come genitori/nonni) in Umamusume Pretty Derby: top-4
compatibili con un personaggio, miglior loop a 5, pianificazione delle
pink spark, timeline delle carriere, esportazione PDF illustrata. UI
disponibile in italiano e inglese (si cambia dal pannello Impostazioni).

## Per chi vuole solo usarlo (Windows, nessuna installazione)

Scarica l'ultimo pacchetto dalla pagina [Releases](../../releases) di
questo repository, estrai lo zip in una cartella e fai doppio clic su
`UmaLegacyLoopOptimizer.exe`. Si apre da solo nel browser — non serve
Python, non serve il terminale. Dettagli nel `LEGGIMI.txt` (italiano) o
`README.txt` (inglese) dentro lo zip.

## Per sviluppo (da sorgente)

```bash
pip install -r requirements.txt
python app.py
```

Poi apri **http://localhost:5000**. Il server gira solo sul tuo PC:
nessun hosting, nessun costo, nessuna dipendenza da servizi esterni — è
l'equivalente di lanciare un programma. Chiudendo la scheda del browser
(o il terminale), si ferma da solo.

Per ricompilare l'eseguibile standalone dopo una modifica: `build_exe.bat`
(richiede `pip install pyinstaller`, solo per questo passaggio).

## Struttura

```
config.py              costanti (suffissi varianti, soglie aptitude, pesi, dimensione loop)
naming.py               risoluzione nome variante -> nome base
display_names.py        formattazione nomi per l'interfaccia
data_loader.py           caricamento e normalizzazione di tutti i dataset
data_updater.py          aggiornamento dati da gametora.com (opzionale, disattivato di default)
affinity.py              affinità di base, compatibilità di gara, soglie di vincibilità
loop_search.py           ricerca top-4 per personaggio e miglior loop a 5
cycle_analysis.py        esplorazione a un salto, cicli, breakdown dei punteggi
aptitude_inheritance.py  pianificazione pink spark ("Aptitude Inheritance")
timeline.py              calendario/timeline del gruppo
pdf_export.py            esportazione PDF illustrata del loop
main.py                  CLI
app.py                   server Flask locale (UI), riusa gli stessi moduli di calcolo
templates/               pagina HTML della UI
static/                  CSS e JS della UI
data/                    dataset (vedi sotto)
```

## Dataset in data/

- `character_ids.csv`, `id_weights.csv` — affinità di base
- `aptitudes.xlsx` — voti A-G per personaggio
- `races.xlsx`, `race_gametora_ids.json` — metadati gara
- `mandatory_races.xlsx` — calendario obbligato per personaggio
- `character_info.csv` — mapping nome-variante → nome giapponese + data di uscita Global

`data/image_cache/` (ritratti personaggi e targhe gara) non è inclusa nel
repository per motivi di copyright: si popola da sola al primo utilizzo
(richiede rete) o resta assente, con segnaposto automatico al suo posto.

## Uso da riga di comando (CLI)

```bash
# Top-4 personaggi più compatibili con uno specifico, in modalità career
python main.py --data-dir data --character mejiro_mcqueen

# Stesso, ma ignorando i vincoli di calendario (tutte le parent run in MANT)
python main.py --data-dir data --character mejiro_mcqueen --mode mant

# Ricerca del miglior loop chiuso a 5 (esaustiva su un pool ristretto)
python main.py --data-dir data --loop --pool-size 20

# Solo personaggi già usciti su Global
python main.py --data-dir data --loop --global-only
```

## Note di design (per riferimento futuro)

- **Punteggio combinato** = affinità di base + (gare condivise vincibili × 3 punti),
  senza normalizzazione: la race-compatibility ha naturalmente un tetto più alto,
  come richiesto.
- **`career` vs `mant`**: in `career`, una gara è vincibile in comune solo se lo slot
  non è occupato da un'altra obbligatoria (gara diversa o `blocked:`); in `mant`
  non c'è alcun vincolo di calendario, solo soglie di aptitude.
- **Varianti**: risolte tramite suffissi noti (rimozione iterativa, gestisce anche
  suffissi concatenati tipo `_og_xmas`). Due varianti della stessa umamusume hanno
  sempre affinità di base 0 tra loro (self-affinity), quindi non vengono escluse a
  priori dal loop ma il loro contributo reciproco è nullo; lo script le segnala
  comunque come nota informativa se compaiono insieme in un loop.
- **`best_loop`** è una ricerca esaustiva (tutte le combinazioni da 5) ristretta a un
  pool ridotto (`--pool-size`, default 20) scelto per punteggio medio più alto —
  non è garantito l'ottimo globale su tutto il roster, ma è trattabile
  computazionalmente. Con roster molto più grandi, valutare un pool più ampio o
  un euristico di ricerca locale.
- **Soglie di aptitude minime** (`MIN_APTITUDE` in `config.py`) e **punti per gara
  condivisa** (`RACE_SHARED_WIN_POINTS`) sono costanti, modificabili senza toccare
  la logica.

## Crediti

Tutto lo sviluppo (scrittura del codice) è stato realizzato interamente da
un'intelligenza artificiale (Claude, Anthropic). Idea, direzione del
progetto, ogni scelta di design e di funzionalità: IvoryTower.

## Licenza

Codice rilasciato con licenza [MIT](LICENSE). I dati di gioco (nomi,
statistiche, aptitude, calendario gare ecc.) appartengono a Cygames —
questo è un tool amatoriale non ufficiale, senza alcuna affiliazione con
Cygames/Cygames Umamusume Pretty Derby.
