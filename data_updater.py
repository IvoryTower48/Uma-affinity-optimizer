# -*- coding: utf-8 -*-
"""
Aggiornamento automatico dei dati da internet, senza input dell'utente,
al massimo una volta ogni 24 ore (vedi maybe_run_update, chiamata da app.py
all'avvio del server).

Quattro fonti, quattro scopi diversi:

1. GitHub (mee1080/umaishow, Source.kt) -- ID di affinita' e relativi pesi
   (character_ids.csv / id_weights.csv). Formato testuale stabile:
     chara: "NomeGiapponese:id1,id2,id3,..."  (un personaggio per riga)
     relation: "id:peso"                       (un ID per riga)
   IMPORTANTE (verificato su gametora.com/umamusume/compatibility): le
   varianti/costumi di uno stesso personaggio condividono TUTTI gli stessi ID
   di affinita' del personaggio base -- quindi questa fonte serve SOLO per
   personaggi nuovi o ID nuovi, mai per varianti.

2. Wikipedia (ja + en) -- SOLO per risalire al nome inglese di un personaggio
   giapponese mai visto prima (comparso nella fonte 1 ma assente da
   character_info.csv). Cerca l'articolo giapponese, segue il langlink verso
   l'inglese. Nessuna chiave richiesta.

3. Gametora (gametora.com/umamusume/characters/<slug>) -- pagina per-
   personaggio, renderizzata lato server (verificato: contiene in chiaro nome
   giapponese, data di rilascio Global, aptitude, ed eventuali "Character
   versions" collegate). Usata per:
   - confermare che il nome inglese trovato via Wikipedia sia quello giusto
     (confronto sulla stringa del nome giapponese mostrata dalla pagina);
   - ottenere la data di rilascio Global per personaggi NON ancora rilasciati
     (vedi punto 4 sotto per quali, esattamente, vengono ricontrollati);
   - rilevare nuove varianti/costumi per personaggi GIA' rilasciati su Global
     (vedi REGOLA CHIAVE sotto per la frequenza, diversa dal resto).

4. umapyoi.net -- date di rilascio sul server GIAPPONESE per tutti i
   personaggi, usate SOLO per stabilire l'ORDINE in cui i personaggi ancora
   privi di data Global usciranno (il rilascio Global segue circa l'ordine
   cronologico JP). Schema JSON non documentato pubblicamente: si prova un
   elenco di nomi di campo plausibili (vedi _JP_NAME_FIELD_CANDIDATES /
   _RELEASE_DATE_FIELD_CANDIDATES), fallback sicuro (dict vuoto) se non
   corrisponde nulla.

REGOLA CHIAVE su COSA si ricontrolla e QUANDO (**due gate separati**, non
confonderli):
- La RICERCA DELLA DATA DI RILASCIO GLOBAL (check_pending_global_releases)
  riguarda SOLO i personaggi ANCORA PRIVI di data Global: una volta trovata,
  quel personaggio esce per sempre dalla lista dei "pending" e non viene mai
  piu' ricontrollato PER QUESTO SCOPO. Gate: 24 ore (lo stesso di tutto il
  resto di run_update), ma si controllano solo i prossimi 5 in ordine
  cronologico JP (fonte 4), non tutti i pending (spreco: molti usciranno tra
  mesi).
- Il RILEVAMENTO DI NUOVE VARIANTI/COSTUMI (check_new_variants) riguarda
  invece SOLO i personaggi GIA' rilasciati su Global (e' proprio per loro
  che ha senso chiedersi se e' uscito un nuovo costume, dato che il
  giocatore puo' gia' usare quel personaggio) -- ATTENZIONE, questo era
  stato scambiato per errore in una versione precedente ("una volta
  rilasciato non serve piu' controllare nulla", confondendo rilascio JP con
  rilascio Global e rimuovendo per sbaglio questo controllo). Gate SEPARATO
  e piu' lento: **7+ giorni** (vedi VARIANT_CHECK_INTERVAL_DAYS), non 24 ore,
  perche' scansiona TUTTI i personaggi base gia' rilasciati (~60-90 richieste
  a Gametora per giro) -- troppo per farlo ogni volta che si controllano i
  prossimi 5 pending.

LIMITE IMPORTANTE E NOTO: le fonti 2/3/4 (Wikipedia/Gametora/umapyoi.net) non
sono raggiungibili dalla rete sandbox usata in sviluppo (solo alcuni domini
sono autorizzati, vedi rete del container) -- la fonte 1/2/3 sono state
validate MANUALMENTE con un caso reale (personaggio "Rulership", ID nuovo
trovato nella fonte 1 il 27/07/2026); la fonte 4 (umapyoi.net) NON e' stata
verificabile nemmeno manualmente (il sito blocca le richieste automatiche
dei miei stessi strumenti di ricerca) -- lo schema JSON usato in
fetch_jp_release_dates() e' un'ipotesi ragionevole ma NON confermata contro
dati reali, verificare al primo utilizzo vero. In ogni caso il meccanismo
fallisce SEMPRE in modo sicuro (nessuna scrittura, nessun dato inventato) se
una pagina/risposta non e' raggiungibile o il parsing non torna un risultato
affidabile.
"""
import csv
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import KNOWN_SUFFIXES, META_PARENTS

SOURCE_KT_URL = (
    "https://raw.githubusercontent.com/mee1080/umaishow/main/core/src/"
    "commonMain/kotlin/io/github/mee1080/umaishow/data/Source.kt"
)
WIKIPEDIA_JA_API = "https://ja.wikipedia.org/w/api.php"
GAMETORA_CHARACTER_URL = "https://gametora.com/umamusume/characters/{slug}"
UPDATE_INTERVAL_HOURS = 24
REQUEST_TIMEOUT = 15
# Budget di tempo COMPLESSIVO per una singola esecuzione di run_update, oltre
# al timeout per singola richiesta (REQUEST_TIMEOUT): protegge da un caso in
# cui MOLTE richieste in sequenza vadano ciascuna in timeout (es.
# check_new_variants scansiona ~60-90 personaggi, ~1-2 richieste ciascuno --
# nel caso peggiore, 90 * 2 * 15s = 45 minuti). Se superato, l'aggiornamento
# si interrompe a meta' (i dati gia' raccolti restano validi e vengono
# comunque scritti/salvati), il resto viene ripreso al prossimo avvio.
MAX_UPDATE_SECONDS = 45
USER_AGENT = (
    "Mozilla/5.0 (compatible; uma-legacy-loop-tool/1.0; "
    "aggiornamento dati locale, uso personale)"
)
HEADERS = {"User-Agent": USER_AGENT}

APTITUDE_COLUMNS = ["Turf", "Dirt", "Sprint", "Mile", "Medium", "Long", "Front", "Pace", "Late", "End"]
# Nomi mostrati da Gametora per le stesse 10 colonne, nello stesso ordine in
# cui compaiono sulla pagina (Sprint la chiamano "Short").
GAMETORA_APTITUDE_LABELS = ["Turf", "Dirt", "Short", "Mile", "Medium", "Long", "Front", "Pace", "Late", "End"]


def _budget_exceeded(deadline: float | None) -> bool:
    """True se 'deadline' (un time.monotonic() limite) e' stato superato.
    deadline=None significa nessun limite (usato nei test/uso diretto delle
    funzioni fuori da run_update)."""
    return deadline is not None and time.monotonic() >= deadline


# ---------------------------------------------------------------------------
# Fonte 1: GitHub (character_ids.csv / id_weights.csv)
# ---------------------------------------------------------------------------

def fetch_source_kt() -> str:
    resp = requests.get(SOURCE_KT_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def parse_source_kt(text: str):
    """Ritorna (chara_map, relation_map): chara_map[nome_jp] = [id,...] (int);
    relation_map[id] = peso (int)."""
    chara_match = re.search(r'val chara: String = """(.*?)"""', text, re.DOTALL)
    relation_match = re.search(r'val relation: String = """(.*?)"""', text, re.DOTALL)
    if not chara_match or not relation_match:
        raise ValueError("Formato di Source.kt non riconosciuto (blocco chara/relation mancante)")

    chara_map = {}
    for line in chara_match.group(1).strip().splitlines():
        line = line.strip()
        if not line:
            continue
        name, ids = line.split(":", 1)
        chara_map[name.strip()] = [int(x) for x in ids.split(",") if x.strip()]

    relation_map = {}
    for line in relation_match.group(1).strip().splitlines():
        line = line.strip()
        if not line:
            continue
        id_str, weight_str = line.split(":", 1)
        relation_map[int(id_str)] = int(weight_str)

    return chara_map, relation_map


def load_character_ids_csv(path: Path):
    """dict[nome_jp] = [id,...] (int), dall'esistente character_ids.csv."""
    result = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            result.setdefault(row["character"], []).append(int(row["id"]))
    return result


def load_id_weights_csv(path: Path):
    result = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            result[int(row["id"])] = int(row["weight"])
    return result


def diff_character_ids(existing: dict, incoming: dict):
    """Ritorna (nuovi_personaggi, id_aggiuntivi_per_esistenti).
    nuovi_personaggi: dict[nome_jp] = [id,...] per personaggi mai visti.
    id_aggiuntivi_per_esistenti: dict[nome_jp] = [id,...] SOLO i nuovi id per
    personaggi che avevamo gia' (capita se un personaggio guadagna nuovi ID
    di affinita' nel tempo, es. per nuove skill/scenario)."""
    new_characters = {}
    added_ids = {}
    for name, ids in incoming.items():
        if name not in existing:
            new_characters[name] = ids
        else:
            extra = sorted(set(ids) - set(existing[name]))
            if extra:
                added_ids[name] = extra
    return new_characters, added_ids


def diff_id_weights(existing: dict, incoming: dict):
    """dict[id] = peso, solo per id nuovi o con peso cambiato."""
    changed = {}
    for id_, weight in incoming.items():
        if existing.get(id_) != weight:
            changed[id_] = weight
    return changed


# ---------------------------------------------------------------------------
# Fonte 2: Wikipedia (solo per nome_jp -> nome inglese, personaggi mai visti)
# ---------------------------------------------------------------------------

def resolve_english_name_via_wikipedia(jp_name: str) -> str | None:
    """Cerca jp_name su ja.wikipedia.org, segue il langlink verso l'inglese.
    Ritorna il nome inglese (senza eventuali suffissi di disambiguazione tipo
    ' (horse)'/' (Umamusume: Pretty Derby)'), o None se non trovato."""
    try:
        search_resp = requests.get(
            WIKIPEDIA_JA_API,
            params={"action": "opensearch", "search": jp_name, "limit": 1, "namespace": 0, "format": "json"},
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        search_resp.raise_for_status()
        titles = search_resp.json()[1]
        if not titles:
            return None
        ja_title = titles[0]

        langlinks_resp = requests.get(
            WIKIPEDIA_JA_API,
            params={"action": "query", "titles": ja_title, "prop": "langlinks", "lllang": "en", "format": "json"},
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        langlinks_resp.raise_for_status()
        pages = langlinks_resp.json().get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
        langlinks = page.get("langlinks")
        if not langlinks:
            return None
        en_title = langlinks[0]["*"]
        # rimuove eventuali suffissi di disambiguazione tra parentesi
        en_name = re.sub(r"\s*\([^)]*\)\s*$", "", en_title).strip()
        return en_name or None
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Fonte 3: Gametora (pagina per-personaggio)
# ---------------------------------------------------------------------------

def _slugify(name: str, sep: str) -> str:
    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", sep, slug).strip(sep).lower()


def gametora_slug(english_name: str) -> str:
    return _slugify(english_name, "-")


def internal_character_slug(english_name: str) -> str:
    return _slugify(english_name, "_")


def fetch_gametora_character(slug: str) -> dict | None:
    """Scarica e fa il parsing della pagina di un personaggio su Gametora.
    Ritorna None se la pagina non esiste (404) o se il parsing fallisce in
    modo da non poter fidarsi dei dati estratti (mai un dict parziale/sporco).
    """
    url = GAMETORA_CHARACTER_URL.format(slug=slug)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    html = resp.text
    soup = BeautifulSoup(html, "lxml")
    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]

    def value_after(label):
        for i, line in enumerate(lines):
            if line == label and i + 1 < len(lines):
                return lines[i + 1]
        return None

    jp_name = value_after("Japanese name")
    release_raw = value_after("Release date")
    release_date = release_raw if release_raw and re.match(r"^\d{4}-\d{2}-\d{2}$", release_raw) else None

    # Le aptitude sono icone (<img alt="A" src=".../ui/rank/simple/12.png">),
    # non testo semplice: si estraggono dall'HTML grezzo via regex sull'attributo
    # alt delle immagini "rank/simple", nell'ordine in cui appaiono in pagina
    # (Turf, Dirt, Short, Mile, Medium, Long, Front, Pace, Late, End).
    rank_alts = re.findall(r'<img[^>]+src="[^"]*/ui/rank/simple/[^"]*"[^>]*alt="([A-Za-z]+)"', html)
    aptitudes = None
    if len(rank_alts) >= len(GAMETORA_APTITUDE_LABELS):
        aptitudes = dict(zip(APTITUDE_COLUMNS, rank_alts[:len(GAMETORA_APTITUDE_LABELS)]))

    # Non ancora rilasciato su Global: la pagina lo dice esplicitamente.
    not_on_global = "not yet released on the Global server" in html

    # Epiteto della versione mostrato nel titolo, es. "Rulership (Original)"
    # -> "Original" (serve per il suffisso di una eventuale nuova variante).
    title_match = re.search(r"<title>([^<(]+)\(([^)<]+)\)", html)
    epithet = title_match.group(2).strip() if title_match else None

    # Altre versioni/costumi collegate (link a pagine sorelle tipo
    # /characters/104602-smart-falcon): si tiene lo SLUG COMPLETO (id incluso)
    # cosi' da poterle scaricare direttamente. NOTA: il rilevamento automatico
    # di nuove varianti che usava questo campo (insieme a "epithet" sotto) e'
    # stato RIMOSSO su richiesta esplicita dell'utente (i dati di un
    # personaggio gia' rilasciato non cambiano piu', non serve piu'
    # ricontrollarlo affatto) -- questi due campi restano estratti (innocui,
    # gia' scritti e testati) ma non sono piu' usati da nessuna funzione,
    # nel caso servisse reintrodurre la funzionalita' in futuro.
    sibling_slugs = sorted(set(re.findall(r'/umamusume/characters/(\d+-[a-z0-9-]+)', html)))
    sibling_slugs = [s for s in sibling_slugs if s != slug]

    if jp_name is None or aptitudes is None:
        return None  # parsing inaffidabile: meglio non applicare nulla

    return {
        "slug": slug,
        "url": url,
        "jp_name": jp_name,
        "release_date": release_date,
        "not_on_global": not_on_global,
        "aptitudes": aptitudes,
        "epithet": epithet,
        "sibling_slugs": sibling_slugs,
    }


def base_character_slug(character: str) -> str:
    """Rimuove un eventuale suffisso noto (es. _og) per ottenere la chiave
    'base' da usare per costruire lo slug Gametora."""
    for suf in KNOWN_SUFFIXES:
        if character.endswith(suf):
            return character[: -len(suf)]
    return character


def epithet_to_suffix(epithet: str) -> str:
    """
    Converte l'epiteto/nome versione mostrato da Gametora (es. 'Original',
    'Grand Live', 'Christmas') in un suffisso stile KNOWN_SUFFIXES
    (underscore, minuscolo, es. '_grand_live'). Se l'epiteto corrisponde a un
    suffisso gia' noto con nome diverso (es. 'Christmas' -> _xmas, 'New
    Year' -> _ny), usa la mappatura nota invece di generarne una nuova.
    """
    known_epithet_map = {
        "original": "og", "christmas": "xmas", "new year": "ny",
        "wedding": "wedding", "valentine": "valen", "halloween": "halloween",
        "summer": "summer", "cheer": "cheer", "island": "island",
        "ballroom": "ballroom", "anime": "anime", "onsen": "onsen",
        "hot spring": "onsen",
    }
    key = epithet.strip().lower()
    if key in known_epithet_map:
        return "_" + known_epithet_map[key]
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return "_" + slug if slug else ""


def _register_new_suffix(data_dir, suffix: str):
    """Aggiunge un nuovo suffisso a data/extra_suffixes.json (creato se assente),
    cosi' che config.KNOWN_SUFFIXES lo includa dai prossimi avvii in poi."""
    path = Path(data_dir) / "extra_suffixes.json"
    existing = json.loads(path.read_text()) if path.exists() else []
    if suffix not in existing and suffix not in KNOWN_SUFFIXES:
        existing.append(suffix)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Fonte 4: umapyoi.net -- date di rilascio JP (per ordinare i "non ancora Global")
# ---------------------------------------------------------------------------

UMAPYOI_CHARACTER_LIST_URL = "https://umapyoi.net/api/v1/character/list"

# Nomi di campo plausibili per nome giapponese / data di rilascio nella
# risposta JSON di umapyoi.net -- lo schema esatto non e' documentato
# pubblicamente (la documentazione elenca solo gli endpoint, non i campi),
# quindi si prova un elenco di alternative comuni, in modo difensivo: se
# nessuna corrisponde si torna un dict vuoto (fallback sicuro, vedi
# check_pending_global_releases).
_JP_NAME_FIELD_CANDIDATES = ("name_jp", "jp_name", "name", "chara_name")
_RELEASE_DATE_FIELD_CANDIDATES = ("release_date", "release", "start_date", "debut_date", "date")


def fetch_jp_release_dates() -> dict:
    """dict[nome_jp] = data di rilascio JP (stringa 'YYYY-MM-DD') per TUTTI i
    personaggi noti a umapyoi.net (dati del server giapponese). Ritorna un
    dict vuoto se la richiesta fallisce o lo schema JSON non e' quello atteso
    (fallback sicuro: la fase successiva si limita a non poter ordinare per
    data JP e salta il controllo, senza rompere nulla)."""
    try:
        resp = requests.get(UMAPYOI_CHARACTER_LIST_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return {}

    entries = data if isinstance(data, list) else data.get("characters", data.get("data", []))
    result = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        jp_name = next((entry[k] for k in _JP_NAME_FIELD_CANDIDATES if entry.get(k)), None)
        release = next((entry[k] for k in _RELEASE_DATE_FIELD_CANDIDATES if entry.get(k)), None)
        if jp_name and release and re.match(r"^\d{4}-\d{2}-\d{2}", str(release)):
            result[jp_name] = str(release)[:10]
    return result


# ---------------------------------------------------------------------------
# Personaggi NON ancora su Global: controlla solo i prossimi 5 per data JP
# ---------------------------------------------------------------------------

def check_pending_global_releases(character_info: pd.DataFrame, max_check: int = 5,
                                   deadline: float | None = None) -> dict:
    """
    I dati di un personaggio (aptitude, ecc.) NON cambiano una volta che ha
    una data di rilascio Global: per quelli con `global_release_date` gia'
    valorizzata NON si controlla piu' nulla (regola esplicita dell'utente) --
    a differenza di una versione precedente, che ri-controllava OGNI
    personaggio base ad ogni esecuzione (~130 richieste a gametora.com).

    Per i personaggi ANCORA SENZA data Global, non ha senso controllarli
    tutti ad ogni esecuzione: il rilascio su Global segue (circa) l'ordine
    cronologico di rilascio JP, quindi si ottengono le date di rilascio JP
    (fonte 4, umapyoi.net) per ordinarli, e si controlla su Gametora SOLO
    quelli con data JP piu' vicina (i prossimi `max_check`, default 5) --
    quelli molto piu' in la' nella coda JP non usciranno su Global a breve,
    controllarli ora sarebbe uno spreco di richieste.
    Personaggi con data JP sconosciuta finiscono in fondo alla coda (non
    prioritari, ma comunque controllati se restano tra i primi `max_check`).

    deadline: time.monotonic() limite oltre il quale interrompere i
    controlli restanti (vedi MAX_UPDATE_SECONDS/_budget_exceeded); None =
    nessun limite. Se superato a meta', i personaggi non ancora controllati
    vengono ripresi al prossimo avvio (nessun dato perso, solo rimandato).

    Ritorna un dict con le date aggiornate trovate (non scrive nulla: la
    scrittura resta centralizzata in run_update).
    """
    result = {"release_dates_updated": [], "checked": 0, "errors": [], "stopped_early": False}

    pending = character_info[character_info["global_release_date"] == ""]
    if pending.empty:
        return result

    jp_dates = fetch_jp_release_dates()
    pending = pending.copy()
    pending["_jp_date"] = pending["jp_name"].map(lambda n: jp_dates.get(n, "9999-99-99"))
    pending = pending.sort_values("_jp_date").head(max_check)

    for _, row in pending.iterrows():
        if _budget_exceeded(deadline):
            result["stopped_early"] = True
            break
        character = row["character"]
        slug_gt = gametora_slug(base_character_slug(character).replace("_", " "))
        gt_data = fetch_gametora_character(slug_gt)
        time.sleep(0.3)  # non sovraccaricare gametora.com con richieste consecutive
        result["checked"] += 1
        if not gt_data or gt_data["jp_name"] != row["jp_name"]:
            continue  # pagina non raggiungibile o slug corrisponde a un personaggio diverso: si salta

        if not gt_data["not_on_global"] and gt_data["release_date"]:
            result["release_dates_updated"].append({
                "character": character, "new_date": gt_data["release_date"],
            })

    return result


def check_new_variants(character_info: pd.DataFrame, aptitudes_df: pd.DataFrame,
                        deadline: float | None = None) -> dict:
    """
    RIPRISTINATA su richiesta esplicita dell'utente (era stata rimossa,
    scambiando per errore "rilasciato su Global" con "rilasciato in JP" nel
    motivo dello stop): il rilevamento di nuove varianti/costumi riguarda
    SOLO i personaggi GIA' RILASCIATI SU GLOBAL (global_release_date
    valorizzata) -- e' proprio per LORO che ha senso controllare se e'
    uscita una nuova versione, dato che un nuovo costume si aggiunge a un
    personaggio che il giocatore puo' gia' usare. I personaggi ancora privi
    di data Global sono gestiti separatamente da check_pending_global_releases
    (che li controlla per LA data di rilascio, non per varianti). Questa
    funzione va chiamata dal chiamante SOLO ogni 7+ giorni (gate a frequenza
    piu' bassa, vedi run_update/_variant_check_due), non ad ogni esecuzione
    di 24 ore, perche' scansiona TUTTI i personaggi base gia' rilasciati
    (~60-90 richieste a Gametora per giro).

    Per ogni personaggio BASE (senza suffisso, o con suffisso _og) GIA' con
    una global_release_date: scarica la sua pagina Gametora, e per ogni
    'Character version' collegata, verifica PRIMA che sia davvero una
    variante DELLO STESSO personaggio (stesso nome giapponese -- la pagina
    puo' linkare anche personaggi del tutto diversi in sezioni come
    "Character Rate Up", quindi questo controllo non e' opzionale); solo se
    confermata, confronta le sue aptitude con quelle della versione BASE: se
    diverse, e' una nuova variante da aggiungere; se identiche, non serve
    nulla (regola utente esplicita, gia' confermata in precedenza).

    deadline: time.monotonic() limite oltre il quale interrompere i
    controlli restanti (vedi MAX_UPDATE_SECONDS/_budget_exceeded); None =
    nessun limite. Se superato a meta' della scansione (~60-90 personaggi,
    la piu' lunga delle 4 fonti), run_update NON marca il controllo varianti
    come "fatto" per questo giro (vedi _mark_variant_check_done in
    run_update): la scansione incompleta viene ritentata al prossimo avvio
    (24h) invece di aspettare altri 7 giorni.

    Ritorna un dict con le nuove varianti trovate (non scrive nulla: la
    scrittura resta centralizzata in run_update).
    """
    result = {"new_variants_found": [], "checked": 0, "errors": [], "stopped_early": False}

    known_characters = set(character_info["character"])
    aptitude_lookup = {
        row["Character"]: {col: row[col] for col in APTITUDE_COLUMNS}
        for _, row in aptitudes_df.iterrows()
    }

    is_base = character_info["character"].apply(
        lambda c: not any(c.endswith(s) for s in KNOWN_SUFFIXES if s != "_og")
    )
    already_released = character_info["global_release_date"] != ""

    for _, row in character_info[is_base & already_released].iterrows():
        if _budget_exceeded(deadline):
            result["stopped_early"] = True
            break
        character = row["character"]
        base_jp_name = row["jp_name"]
        slug_gt = gametora_slug(base_character_slug(character).replace("_", " "))

        gt_data = fetch_gametora_character(slug_gt)
        time.sleep(0.3)  # non sovraccaricare gametora.com con richieste consecutive
        result["checked"] += 1
        if not gt_data or gt_data["jp_name"] != base_jp_name:
            continue  # pagina non raggiungibile o slug corrisponde a un personaggio diverso: si salta

        base_aptitudes = aptitude_lookup.get(character)
        for sibling_slug in gt_data.get("sibling_slugs", []):
            if _budget_exceeded(deadline):
                result["stopped_early"] = True
                break
            sib_data = fetch_gametora_character(sibling_slug)
            time.sleep(0.3)
            if not sib_data or sib_data["jp_name"] != base_jp_name:
                continue  # verifica di sicurezza: non e' una variante di QUESTO personaggio

            if base_aptitudes is not None and sib_data["aptitudes"] == base_aptitudes:
                continue  # stesse aptitude della base: non serve una nuova riga (regola utente)

            epithet = sib_data.get("epithet") or sibling_slug
            suffix = epithet_to_suffix(epithet)
            new_character = base_character_slug(character) + suffix
            if new_character in known_characters:
                continue  # gia' presente (aggiunta in un run precedente)

            result["new_variants_found"].append({
                "character": new_character,
                "base_character": character,
                "jp_name": base_jp_name,
                "epithet": epithet,
                "aptitudes": sib_data["aptitudes"],
                "release_date": "" if sib_data["not_on_global"] else (sib_data["release_date"] or ""),
                "gametora_url": sib_data["url"],
            })
            known_characters.add(new_character)  # evita doppioni nello stesso run
        if result["stopped_early"]:
            break

    return result


def _load_character_info(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def _load_aptitudes(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, dtype=str)


def run_update(data_dir: str) -> dict:
    """Esegue l'intero aggiornamento e SCRIVE i file (character_ids.csv,
    id_weights.csv, character_info.csv, aptitudes.xlsx) se ci sono novita'.
    Fa sempre un backup dei file coinvolti PRIMA di scrivere.
    Ritorna un report strutturato (dict) con tutte le modifiche applicate e
    gli eventuali casi che richiedono attenzione manuale.
    """
    data_dir = Path(data_dir)
    deadline = time.monotonic() + MAX_UPDATE_SECONDS
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "new_characters_added": [],       # personaggi nuovi aggiunti con successo
        "new_characters_needs_review": [],  # personaggi nuovi NON risolti automaticamente
        "new_affinity_ids_added": {},     # personaggi esistenti con nuovi ID
        "new_id_weights_added": {},
        "release_dates_updated": [],
        "new_variants_added": [],
        "errors": [],
        "stopped_early": False,  # True se MAX_UPDATE_SECONDS e' scaduto a meta'
    }

    # --- Fonte 1: GitHub ---
    try:
        source_text = fetch_source_kt()
        incoming_chara, incoming_relation = parse_source_kt(source_text)
    except Exception as exc:  # rete assente, formato cambiato, ecc: non blocca l'app
        report["errors"].append(f"Impossibile leggere Source.kt da GitHub: {exc}")
        return report

    character_ids_path = data_dir / "character_ids.csv"
    id_weights_path = data_dir / "id_weights.csv"
    character_info_path = data_dir / "character_info.csv"
    aptitudes_path = data_dir / "aptitudes.xlsx"

    existing_chara = load_character_ids_csv(character_ids_path)
    existing_weights = load_id_weights_csv(id_weights_path)
    character_info = _load_character_info(character_info_path)
    aptitudes_df = _load_aptitudes(aptitudes_path)

    new_characters, added_ids = diff_character_ids(existing_chara, incoming_chara)
    new_weights = diff_id_weights(existing_weights, incoming_relation)

    # Backup SEMPRE prima di scrivere qualunque cosa, anche se la fonte 1 non
    # ha novita': il controllo sui personaggi esistenti (date Global/varianti,
    # piu' sotto) gira comunque ad ogni esecuzione, indipendentemente da GitHub.
    _backup_data_files(data_dir)

    # --- id_weights.csv: aggiunge/aggiorna pesi nuovi o cambiati ---
    if new_weights:
        merged_weights = {**existing_weights, **new_weights}
        with open(id_weights_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "weight"])
            for id_ in sorted(merged_weights):
                writer.writerow([id_, merged_weights[id_]])
        report["new_id_weights_added"] = new_weights

    # --- character_ids.csv: nuove righe per personaggi esistenti con id in piu' ---
    new_rows = []
    for name, ids in added_ids.items():
        for id_ in ids:
            new_rows.append((name, id_))
    report["new_affinity_ids_added"] = added_ids

    # --- Personaggi nuovi: risolvi nome inglese + verifica su Gametora ---
    jp_name_to_info = dict(zip(character_info["jp_name"], character_info["character"]))
    new_character_info_rows = []
    new_aptitude_rows = []

    for jp_name, ids in new_characters.items():
        for id_ in ids:
            new_rows.append((jp_name, id_))

        if _budget_exceeded(deadline):
            report["stopped_early"] = True
            report["new_characters_needs_review"].append({
                "jp_name": jp_name, "ids": ids,
                "reason": "Budget di tempo dell'aggiornamento esaurito, ripreso al prossimo avvio.",
            })
            continue

        english_name = resolve_english_name_via_wikipedia(jp_name)
        if not english_name:
            report["new_characters_needs_review"].append({
                "jp_name": jp_name, "ids": ids,
                "reason": "Nome inglese non trovato via Wikipedia",
            })
            continue

        slug_gt = gametora_slug(english_name)
        gt_data = fetch_gametora_character(slug_gt)
        if not gt_data or gt_data["jp_name"] != jp_name:
            report["new_characters_needs_review"].append({
                "jp_name": jp_name, "ids": ids,
                "candidate_english_name": english_name,
                "reason": (
                    "Pagina Gametora non trovata o nome giapponese non corrispondente "
                    f"(atteso '{jp_name}', slug provato '{slug_gt}')"
                ),
            })
            continue

        internal_slug = internal_character_slug(english_name)
        release_date = "" if gt_data["not_on_global"] else (gt_data["release_date"] or "")

        new_character_info_rows.append({
            "character": internal_slug, "jp_name": jp_name, "global_release_date": release_date,
        })
        new_aptitude_rows.append({"Character": internal_slug, **gt_data["aptitudes"]})
        report["new_characters_added"].append({
            "character": internal_slug, "jp_name": jp_name,
            "english_name": english_name, "global_release_date": release_date,
            "gametora_url": gt_data["url"],
        })

    # --- Scrive character_ids.csv (righe aggiunte, esistenti invariate) ---
    if new_rows:
        with open(character_ids_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for name, id_ in new_rows:
                writer.writerow([name, id_])

    # --- Scrive character_info.csv / aptitudes.xlsx per i nuovi personaggi ---
    if new_character_info_rows:
        character_info = pd.concat(
            [character_info, pd.DataFrame(new_character_info_rows)], ignore_index=True,
        )
        character_info.to_csv(character_info_path, index=False)

    if new_aptitude_rows:
        aptitudes_df = pd.concat(
            [aptitudes_df, pd.DataFrame(new_aptitude_rows)], ignore_index=True,
        )
        aptitudes_df.to_excel(aptitudes_path, index=False)

    # --- Personaggi NON ancora su Global: controlla solo i prossimi 5 per
    # data di rilascio JP (fonte 4). I personaggi GIA' su Global non vengono
    # piu' ricontrollati per nulla (i loro dati non cambiano una volta
    # rilasciati -- regola esplicita dell'utente, sostituisce la precedente
    # scansione esaustiva di TUTTI i personaggi base ad ogni esecuzione).
    # (rilegge da disco cosi' da includere i personaggi appena aggiunti sopra)
    character_info = _load_character_info(character_info_path)
    pending_check = check_pending_global_releases(character_info, deadline=deadline)
    report["release_dates_updated"] = pending_check["release_dates_updated"]
    report["errors"].extend(pending_check["errors"])
    report["stopped_early"] = report["stopped_early"] or pending_check["stopped_early"]

    if pending_check["release_dates_updated"]:
        by_character = {r["character"]: r["new_date"] for r in pending_check["release_dates_updated"]}
        character_info["global_release_date"] = character_info.apply(
            lambda r: by_character.get(r["character"], r["global_release_date"]), axis=1,
        )
        character_info.to_csv(character_info_path, index=False)

    # --- Nuove varianti/costumi: SOLO ogni 7+ giorni (gate separato dalle 24
    # ore del resto di run_update, vedi _variant_check_due/_variant_state_path
    # sotto) -- scansiona TUTTI i personaggi base GIA' rilasciati su Global
    # (~60-90 richieste a Gametora), troppo per farlo ad ogni avvio.
    if _variant_check_due(data_dir) and not _budget_exceeded(deadline):
        aptitudes_df = _load_aptitudes(aptitudes_path)
        variant_check = check_new_variants(character_info, aptitudes_df, deadline=deadline)
        report["new_variants_added"] = variant_check["new_variants_found"]
        report["errors"].extend(variant_check["errors"])
        report["stopped_early"] = report["stopped_early"] or variant_check["stopped_early"]

        if variant_check["new_variants_found"]:
            new_variant_info_rows = []
            new_variant_aptitude_rows = []
            for variant in variant_check["new_variants_found"]:
                suffix = variant["character"][len(variant["base_character"]):] \
                    if variant["character"].startswith(variant["base_character"]) else ""
                if suffix and suffix not in KNOWN_SUFFIXES:
                    _register_new_suffix(data_dir, suffix)
                new_variant_info_rows.append({
                    "character": variant["character"], "jp_name": variant["jp_name"],
                    "global_release_date": variant["release_date"],
                })
                new_variant_aptitude_rows.append({"Character": variant["character"], **variant["aptitudes"]})
            character_info = pd.concat(
                [character_info, pd.DataFrame(new_variant_info_rows)], ignore_index=True,
            )
            aptitudes_df = pd.concat(
                [aptitudes_df, pd.DataFrame(new_variant_aptitude_rows)], ignore_index=True,
            )
            character_info.to_csv(character_info_path, index=False)
            aptitudes_df.to_excel(aptitudes_path, index=False)

        if not variant_check["stopped_early"]:
            _mark_variant_check_done(data_dir)
        # se interrotto per budget: NON si marca come fatto, cosi' viene
        # ritentato al prossimo avvio (24h) invece di aspettare altri 7
        # giorni per una scansione rimasta incompleta.

    return report


# ---------------------------------------------------------------------------
# Scheduling ("ogni 24 ore", controllato all'avvio dell'app -- vedi app.py)
# ---------------------------------------------------------------------------

def _state_path(data_dir: str) -> Path:
    return Path(data_dir) / ".update_state.json"


def _update_settings_path(data_dir: str) -> Path:
    return Path(data_dir) / "update_settings.json"


def _read_json(path: Path, default=None):
    """Legge un file JSON, ritornando 'default' se il file e' assente o
    illeggibile (nessuna eccezione verso il chiamante: uno stato
    mancante/corrotto equivale semplicemente a 'non ancora impostato')."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, ValueError):
        return default


def is_auto_update_enabled(data_dir: str) -> bool:
    """
    True se l'aggiornamento automatico e' abilitato (default, se il file di
    impostazioni non esiste o e' illeggibile: FALSE -- al primo avvio il
    programma non si connette a internet da solo, l'utente deve attivarlo
    esplicitamente dalla UI o con --enable-auto-update). Persistito in
    data/update_settings.json, cosi' la scelta resta valida tra un avvio e
    l'altro (vedi set_auto_update_enabled per come cambiarla).
    """
    settings = _read_json(_update_settings_path(data_dir), {})
    return bool(settings.get("auto_update_enabled", False))


def set_auto_update_enabled(data_dir: str, enabled: bool) -> None:
    """
    Abilita/disabilita l'aggiornamento automatico dal PROSSIMO avvio in poi
    (persistito su disco). Puo' essere richiamata da app.py tramite un flag
    da riga di comando (--disable-auto-update / --enable-auto-update).
    """
    path = _update_settings_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"auto_update_enabled": enabled}, indent=2))


def _meta_parents_path(data_dir: str) -> Path:
    return Path(data_dir) / "meta_parents.json"


def get_meta_parents(data_dir: str) -> list:
    """
    Lista corrente dei genitori 'meta' (personalizzabile dall'utente da UI,
    vedi /api/meta_parents in app.py). Se il file non esiste ancora (mai
    salvato), ritorna il default hardcoded di config.META_PARENTS -- stesso
    valore che config.py avrebbe gia' caricato all'avvio in quel caso.
    """
    return _read_json(_meta_parents_path(data_dir), list(META_PARENTS))


def set_meta_parents(data_dir: str, characters: list) -> None:
    """
    Sostituisce PER INTERO la lista dei genitori 'meta' (non additiva, a
    differenza di extra_suffixes.json: l'utente deve poter anche togliere
    una voce di default che non condivide). Il chiamante (app.py) valida
    che ogni voce sia un personaggio esistente prima di richiamare questa
    funzione -- qui si scrive senza ulteriori controlli.
    """
    path = _meta_parents_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(characters), indent=2))


def _variant_state_path(data_dir: str) -> Path:
    return Path(data_dir) / ".variant_check_state.json"


VARIANT_CHECK_INTERVAL_DAYS = 7


def _variant_check_due(data_dir: str) -> bool:
    """True se non e' mai stato fatto un controllo varianti, o se sono
    passati almeno VARIANT_CHECK_INTERVAL_DAYS giorni dall'ultimo. Gate
    SEPARATO dalle 24 ore del resto di run_update (quello scansiona TUTTI i
    personaggi gia' rilasciati, ~60-90 richieste: troppo per farlo ogni giorno)."""
    state = _read_json(_variant_state_path(data_dir), {})
    try:
        last = datetime.fromisoformat(state["last_variant_check_utc"])
    except (KeyError, ValueError):
        return True
    return (datetime.now(timezone.utc) - last).total_seconds() >= VARIANT_CHECK_INTERVAL_DAYS * 86400


def _mark_variant_check_done(data_dir: str):
    _variant_state_path(data_dir).write_text(
        json.dumps({"last_variant_check_utc": datetime.now(timezone.utc).isoformat()})
    )


def _backup_data_files(data_dir: str):
    data_dir = Path(data_dir)
    backup_dir = data_dir / "update_backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in ("character_ids.csv", "id_weights.csv", "character_info.csv", "aptitudes.xlsx"):
        src = data_dir / name
        if src.exists():
            (backup_dir / name).write_bytes(src.read_bytes())


def maybe_run_update(data_dir: str, force: bool = False) -> dict | None:
    """Controlla se sono passate piu' di 24 ore dall'ultimo aggiornamento
    riuscito; in tal caso lo esegue e aggiorna il timestamp. Pensato per
    essere chiamato all'AVVIO dell'app (non serve un processo sempre attivo).
    Non solleva mai eccezioni verso il chiamante: un problema di rete non
    deve impedire l'avvio dell'app con i dati gia' presenti. Un budget di
    tempo complessivo (MAX_UPDATE_SECONDS) protegge comunque da un'attesa
    troppo lunga anche in caso di rete molto lenta (vedi run_update).

    Se l'utente ha disattivato l'aggiornamento automatico (vedi
    is_auto_update_enabled/set_auto_update_enabled), non fa nulla e ritorna
    None immediatamente, anche con force=True (la disattivazione e'
    esplicita e ha sempre la precedenza).

    Ritorna il report se l'aggiornamento e' stato eseguito, altrimenti None.
    """
    if not is_auto_update_enabled(data_dir):
        return None

    state_path = _state_path(data_dir)
    if not force:
        state = _read_json(state_path, {})
        try:
            last = datetime.fromisoformat(state["last_update_utc"])
            if (datetime.now(timezone.utc) - last).total_seconds() < UPDATE_INTERVAL_HOURS * 3600:
                return None
        except (KeyError, ValueError):
            pass  # stato illeggibile/assente: procede come se non fosse mai stato eseguito

    try:
        report = run_update(data_dir)
    except Exception as exc:
        report = {"timestamp": datetime.now(timezone.utc).isoformat(), "errors": [str(exc)]}

    state_path.write_text(json.dumps({"last_update_utc": datetime.now(timezone.utc).isoformat()}))

    report_path = Path(data_dir) / "last_update_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    return report
