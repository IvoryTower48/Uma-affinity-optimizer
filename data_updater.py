# -*- coding: utf-8 -*-
"""
Aggiornamento automatico dei dati da internet, senza input dell'utente,
al massimo una volta ogni 24 ore (vedi maybe_run_update, chiamata da app.py
all'avvio del server).

Quattro fonti, quattro scopi diversi (la Fonte 4, umapyoi.net, e' stata
RIMOSSA il 2026-08-12: non ha mai esposto una data di rilascio utilizzabile,
vedi "STATO NOTO" in fondo):

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
   personaggio, un tempo renderizzata lato server con nome giapponese, data
   di rilascio Global, aptitude e "Character versions" collegate in chiaro
   nell'HTML. **ROTTA dal 2026-08-12 (confermato, non solo sospettata)**:
   Gametora ha spostato questi dati al rendering client-side (li carica ora
   da character-cards.json, vedi fonte 5) -- l'HTML servito da requests.get
   non contiene piu' ne' l'etichetta "Release date" ne' le icone aptitude
   (verificato su gold-ship: 0 icone trovate), quindi fetch_gametora_character
   ritorna sempre None. check_pending_global_releases e' stata MIGRATA sulla
   fonte 5 (sotto) e non usa piu' questa fonte. check_new_variants e la
   conferma dei personaggi nuovi (righe piu' sotto in run_update) usano
   ANCORA fetch_gametora_character e sono quindi anch'esse non funzionanti
   al momento -- falliscono in modo sicuro (nessuna scrittura), ma non
   trovano piu' nulla. Migrarle a character-cards.json e' lavoro futuro,
   segnalato ma non fatto qui (fuori scope per la correzione del
   2026-08-12, che riguardava le date di rilascio mancanti).

4. Gametora (data/umamusume/character-cards.<hash>.json, lo stesso file JSON
   che alimenta il loro Collection Tracker E il rendering client-side della
   pagina per-personaggio, vedi fonte 3) -- fonte UNICA e affidabile per
   nome giapponese, data di rilascio Global e aptitude di ogni carta (10
   valori nello stesso ordine di APTITUDE_COLUMNS, verificato identico
   byte-per-byte a un'aptitude gia' salvata). Usata per due scopi, un solo
   fetch condiviso per esecuzione (vedi run_update):
   - `check_pending_global_releases`: trova la data di rilascio Global per i
     personaggi ancora privi (vedi commento dedicato sopra quella funzione
     per la storia completa del perche' e' cambiata).
   - costruisce `data/gametora_tid_map.json`: dict[tid_gametora] =
     nostro_id_interno. Il "tid" e' l'ID compatto usato nell'export/import
     "Backup" del Collection Tracker (gametora.com/umamusume/collection-
     tracker), verificato dal vivo (2026-08-12): esporta
     {"servers":{"en":{"charCards":{"<tid>":<stelle>}}}}. Serve per
     l'import/export della selezione posseduti compatibile con Gametora
     (vedi static/script.js, sezione "Personaggi posseduti"). L'hash nel
     nome del file cambia ad ogni deploy del sito: si risolve prima via
     data/manifests/umamusume.json (chiave "character-cards"), stesso
     pattern con cui il sito stesso carica i propri dati.
     IMPORTANTE -- l'abbinamento tid -> nostro ID NON si basa sul suffisso di
     variante (es. "_xmas"): un caso reale (Oguri Cap) mostra che il suffisso
     registrato in questo repository non riflette sempre il vero costume
     Gametora (vedi build_gametora_tid_map per il dettaglio). Si usa invece
     (nome giapponese, data di rilascio Global) come chiave, con match
     OBBLIGATORIAMENTE univoco -- se ambiguo o assente, quella carta viene
     ignorata (mai un abbinamento indovinato). Un fallback separato
     (`build_gametora_tid_fallback_map`) riconduce le carte SENZA
     abbinamento esatto al personaggio tracciato piu' vicino (stesso nome
     giapponese, costume piu' antico), cosi' possedere solo una variante non
     tracciata separatamente conta comunque come possedere il personaggio.

REGOLA CHIAVE su QUANDO si ricontrolla cosa:
- La RICERCA DELLA DATA DI RILASCIO GLOBAL (check_pending_global_releases)
  riguarda SOLO i personaggi ANCORA PRIVI di data Global: una volta trovata,
  quel personaggio esce per sempre dalla lista dei "pending" e non viene mai
  piu' ricontrollato PER QUESTO SCOPO. Nessun campionamento: dal 2026-08-12
  si controllano TUTTI i pending ad ogni esecuzione (character-cards.json da'
  gia' tutte le date in un colpo solo, non servono piu' richieste
  per-personaggio ne' un ordine di priorita').
- Il RILEVAMENTO DI NUOVE VARIANTI/COSTUMI (check_new_variants) riguarda
  invece SOLO i personaggi GIA' rilasciati su Global (e' proprio per loro
  che ha senso chiedersi se e' uscito un nuovo costume, dato che il
  giocatore puo' gia' usare quel personaggio). Gate SEPARATO e piu' lento:
  **7+ giorni** (vedi VARIANT_CHECK_INTERVAL_DAYS) -- ATTUALMENTE INEFFICACE
  comunque, perche' dipende dalla fonte 3 rotta (vedi sopra): non trova mai
  nulla finche' non viene migrata a character-cards.json.

STATO NOTO (2026-08-12): la fonte 4 (umapyoi.net, ex "Fonte 4" di questo
file) e' stata RIMOSSA -- indagando su un caso reale segnalato dall'utente
(Gold Ship, rilasciato al lancio Global ma senza global_release_date nei
dati) e' emerso che umapyoi.net/api/v1/character/list (e l'endpoint di
dettaglio per-personaggio) non hanno MAI esposto un campo data di rilascio,
in nessuna delle due risposte (verificato leggendo lo schema reale): la
fonte non ha mai funzionato, l'euristica sui nomi di campo falliva sempre in
modo silenzioso (fallback sicuro, ma di fatto muta). La fonte 3 (scraping
HTML per-personaggio) e' risultata SEPARATAMENTE rotta per lo stesso motivo
di fondo (il sito ora carica quei dati via JS da character-cards.json) --
entrambi i problemi sono stati scoperti insieme mentre si indagava sul
sintomo di Gold Ship. Il meccanismo fallisce SEMPRE in modo sicuro (nessuna
scrittura, nessun dato inventato) se una pagina/risposta non e' raggiungibile
o il parsing non torna un risultato affidabile -- questo e' il motivo per
cui il problema e' rimasto silenzioso cosi' a lungo invece di dare errore.
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
# Personaggi NON ancora su Global: cerca la data di rilascio in
# character-cards.json (Fonte 5, vedi fetch_gametora_character_cards)
# ---------------------------------------------------------------------------
# STORIA (2026-08-12): la versione precedente controllava solo i prossimi 5
# personaggi per volta, ordinati per data di rilascio JP presa da
# umapyoi.net (una "Fonte 4" a se stante, rimossa qui). Indagando su un caso
# reale segnalato dall'utente (Gold Ship, rilasciato al lancio Global ma
# ancora senza global_release_date nei dati), sono emersi DUE problemi reali,
# non uno solo:
# 1. umapyoi.net/api/v1/character/list NON ha mai avuto un campo data di
#    rilascio (verificato sia sull'elenco che sul dettaglio per-personaggio):
#    l'euristica sui nomi di campo (_JP_NAME_FIELD_CANDIDATES/
#    _RELEASE_DATE_FIELD_CANDIDATES) non ha mai potuto trovare nulla, quindi
#    l'ordinamento per data JP e' sempre stato un no-op silenzioso (fallback
#    sicuro, ma di fatto la fonte non ha MAI funzionato).
# 2. fetch_gametora_character (scraping HTML della pagina per-personaggio) e'
#    ROTTO: la pagina non contiene piu', nell'HTML servito lato server, ne'
#    l'etichetta "Release date" ne' le icone aptitude (verificato su
#    gold-ship: 0 "rank_alts" trovati) -- Gametora ha evidentemente spostato
#    questi dati al rendering client-side, alimentato dagli stessi JSON
#    (character-cards.json) gia' usati per la Fonte 5. Senza aptitude
#    riconosciute, fetch_gametora_character ritorna sempre None per QUALSIASI
#    personaggio ora, quindi anche i pochi controllati per data JP non
#    trovavano mai nulla (verificato: max_check=87, tutti i pending, zero
#    date aggiornate).
# FIX: character-cards.json (Fonte 5) da' GIA' la data di rilascio Global
# (release_en) per OGNI personaggio in UNA SOLA chiamata di rete -- non serve
# piu' ne' un ordinamento per priorita' ne' richieste per-personaggio: si
# controllano TUTTI i pending in un colpo solo, a costo pressoche' zero
# (nessuna richiesta aggiuntiva: 'cards' e' lo stesso elenco gia' scaricato
# per la Fonte 5 in run_update). Verificato: aptitude di gold_ship in
# character-cards.json identica byte-per-byte a quella gia' salvata in
# aptitudes.xlsx, quindi la fonte e' affidabile anche per questo scopo.
# check_new_variants (sotto) e la conferma di personaggi nuovi in run_update
# usano ANCORA fetch_gametora_character (quindi sono anch'essi rotti allo
# stesso modo) -- non migrati qui, fuori scope per questa correzione, vedi
# HANDOFF.md.

def check_pending_global_releases(character_info: pd.DataFrame, cards: list) -> dict:
    """
    I dati di un personaggio (aptitude, ecc.) NON cambiano una volta che ha
    una data di rilascio Global: per quelli con `global_release_date` gia'
    valorizzata NON si controlla piu' nulla (regola esplicita dell'utente).

    Per i personaggi ANCORA SENZA data Global, cerca tra 'cards' (l'intero
    catalogo Gametora, Fonte 5) quelle che condividono lo stesso nome
    giapponese e hanno gia' una 'release_en'.

    **Bug reale trovato e corretto (2026-08-12), stesso giorno in cui e'
    stata scritta la prima versione**: una prima versione usava la data PIU'
    ANTICA tra le carte Gametora con quel nome giapponese per QUALSIASI riga
    pending con quel nome -- ma un nome giapponese puo' avere PIU' carte
    Gametora (costume base + varianti) con date DIVERSE, e altrettante righe
    NOSTRE distinte. Risultato reale: a `oguri_cap_anime` (variante
    "Anime Collab", NON ancora uscita su Global secondo Gametora stesso,
    nessuna 'release_en') veniva assegnata per errore la data del costume
    BASE (2025-06-26, un'carta DIVERSA) solo perche' condivide lo stesso
    nome giapponese -- 11 righe su 13 risolte in quel giro erano sbagliate
    allo stesso modo (dati scritti nel repository e poi ripristinati da
    backup). **Fix**: l'abbinamento automatico si applica SOLO quando il
    nostro dataset ha ESATTAMENTE UNA riga per quel nome giapponese (nessuna
    variante gia' tracciata) -- in quel caso non c'e' ambiguita' su quale
    carta Gametora corrisponda alla nostra riga, e si usa la PIU' ANTICA
    'release_en' tra tutte le carte Gametora con quel nome (il momento in
    cui il personaggio e' diventato disponibile, a prescindere dal costume).
    Per i nomi giapponesi con PIU' righe nostre (varianti gia' tracciate),
    non c'e' modo affidabile di sapere quale riga corrisponde a quale carta
    SENZA il suffisso (dimostrato inaffidabile altrove in questo file, vedi
    build_gametora_tid_map) -- restano pending, mai un abbinamento indovinato.

    Nessuna richiesta di rete propria: 'cards' va gia' scaricato dal
    chiamante (vedi run_update, Fonte 5).

    Ritorna un dict con le date aggiornate trovate (non scrive nulla: la
    scrittura resta centralizzata in run_update).
    """
    result = {"release_dates_updated": []}

    pending = character_info[character_info["global_release_date"] == ""]
    if pending.empty:
        return result

    jp_name_row_counts = character_info["jp_name"].value_counts()

    earliest_release_by_jp = {}
    for card in cards:
        jp_name, release_en = card.get("name_jp"), card.get("release_en")
        if not jp_name or not release_en:
            continue
        current = earliest_release_by_jp.get(jp_name)
        if current is None or release_en < current:
            earliest_release_by_jp[jp_name] = release_en

    for _, row in pending.iterrows():
        if jp_name_row_counts.get(row["jp_name"], 0) != 1:
            continue  # nome giapponese con piu' righe nostre: ambiguo, non si indovina
        release = earliest_release_by_jp.get(row["jp_name"])
        if release:
            result["release_dates_updated"].append({"character": row["character"], "new_date": release})

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


# ---------------------------------------------------------------------------
# Fonte 5: Gametora character-cards.json -- mappa tid -> nostro ID interno
# (per import/export della selezione posseduti compatibile col Collection
# Tracker di Gametora, vedi static/script.js)
# ---------------------------------------------------------------------------

GAMETORA_MANIFEST_URL = "https://gametora.com/data/manifests/umamusume.json"
GAMETORA_DATA_BASE_URL = "https://gametora.com/data/umamusume/"


def _fetch_gametora_data_file(manifest_key: str):
    """Scarica un file dati generico di Gametora (data/umamusume/<manifest_key>.<hash>.json),
    risolvendo l'hash corrente via il manifest pubblico (stesso meccanismo con cui il
    sito carica i propri dati) -- fattorizzata da fetch_gametora_character_cards per
    essere riusata anche da fetch_gametora_factors (Fonte 6, sotto). Ritorna il JSON
    decodificato (list o dict, secondo il file), o None se manifest/file non sono
    raggiungibili o non hanno il formato atteso."""
    try:
        manifest_resp = requests.get(GAMETORA_MANIFEST_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        manifest_resp.raise_for_status()
        file_hash = manifest_resp.json()[manifest_key]

        data_resp = requests.get(
            f"{GAMETORA_DATA_BASE_URL}{manifest_key}.{file_hash}.json",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        data_resp.raise_for_status()
        return data_resp.json()
    except (requests.RequestException, ValueError, KeyError):
        return None


def fetch_gametora_character_cards() -> list | None:
    """Scarica l'elenco completo delle carte-personaggio (tutte le
    varianti/costumi) usato dal Collection Tracker di Gametora. Ritorna None
    (mai una lista parziale/sporca) se non raggiungibile o in un formato
    inatteso."""
    cards = _fetch_gametora_data_file("character-cards")
    return cards if isinstance(cards, list) else None


def build_gametora_tid_map(character_info: pd.DataFrame, cards: list) -> dict:
    """dict[tid] = nostro_id_interno, per ogni carta Gametora che trova un
    abbinamento UNIVOCO in character_info.csv.

    NON usa il suffisso di variante (es. "_xmas") per l'abbinamento: un caso
    reale (Oguri Cap) mostra che il suffisso registrato in questo repository
    non riflette sempre il vero costume Gametora --
    "oguri_cap_og_xmas" ha in realta' la data di rilascio del costume BASE
    (2025-06-26), non quella del vero costume natalizio Gametora (2026-01-05,
    non ancora presente come riga separata in questo repository) -- probabile
    refuso storico di una precedente rilevazione varianti, non toccato qui
    (fuori scope). L'abbinamento usa invece (nome giapponese, data di
    rilascio Global): entrambi i campi sono gia' tracciati e affidabili, e il
    match dev'essere univoco -- se una carta non trova ESATTAMENTE una riga
    corrispondente, viene ignorata silenziosamente (mai un abbinamento
    indovinato). Le carte non ancora rilasciate su Global (senza
    'release_en') sono escluse a monte: non possono comunque comparire in un
    export reale del Collection Tracker."""
    rows_by_key = {}
    for _, row in character_info.iterrows():
        rows_by_key.setdefault((row["jp_name"], row["global_release_date"]), []).append(row["character"])

    tid_map = {}
    for card in cards:
        tid = card.get("tid")
        jp_name = card.get("name_jp")
        release_en = card.get("release_en")
        if not tid or not jp_name or not release_en:
            continue
        candidates = rows_by_key.get((jp_name, release_en), [])
        if len(candidates) == 1:
            tid_map[tid] = candidates[0]
    return tid_map


def build_gametora_tid_fallback_map(character_info: pd.DataFrame, cards: list, tid_map: dict) -> dict:
    """dict[tid] = nostro_id_interno, SOLO per carte Gametora che
    build_gametora_tid_map non ha gia' risolto ma il cui personaggio (stesso
    nome giapponese) e' comunque tracciato da questo tool sotto ALMENO una
    variante -- caso reale segnalato dall'utente: possedere su Gametora solo
    "Rice Shower Halloween" (che questo tool non traccia come riga separata)
    non faceva risultare posseduta nemmeno "Rice Shower" base, pur essendo
    la STESSA umamusume ai fini di aptitude/carriera del looping. Si punta
    alla riga tracciata con la data di rilascio Global PIU' ANTICA per quel
    nome giapponese (in pratica il costume 'originale') -- se nessuna riga
    per quel nome giapponese ha una data nota, non c'e' un fallback
    affidabile e la carta resta non risolta (mai un abbinamento indovinato,
    stesso principio di build_gametora_tid_map)."""
    earliest_by_jp = {}
    for _, row in character_info.iterrows():
        jp_name, date = row["jp_name"], row["global_release_date"]
        if not date:
            continue
        current = earliest_by_jp.get(jp_name)
        if current is None or date < current[0]:
            earliest_by_jp[jp_name] = (date, row["character"])

    fallback_map = {}
    for card in cards:
        tid = card.get("tid")
        jp_name = card.get("name_jp")
        if not tid or not jp_name or tid in tid_map:
            continue
        entry = earliest_by_jp.get(jp_name)
        if entry:
            fallback_map[tid] = entry[1]
    return fallback_map


def build_gametora_tid_names(cards: list) -> dict:
    """dict[tid] = nome leggibile Gametora ("Special Week", "Special Week
    (Summer)", ...), per TUTTE le carte con un tid (comprese quelle SENZA un
    abbinamento in build_gametora_tid_map) -- serve solo per mostrare
    all'utente QUALI carte di un import sono state ignorate (vedi
    static/script.js), non per la logica di import/export in se'."""
    names = {}
    for card in cards:
        tid = card.get("tid")
        name_en = card.get("name_en")
        if not tid or not name_en:
            continue
        version = card.get("version")
        if version:
            names[tid] = f"{name_en} ({version.replace('_', ' ').title()})"
        else:
            names[tid] = name_en
    return names


# ---------------------------------------------------------------------------
# Fonte 6: Gametora factors.json -- elenco race spark e white spark (skill),
# per la pianificazione dell'eredita' (v4, vedi HANDOFF.md). Stesso schema
# hash-via-manifest della Fonte 5 (_fetch_gametora_data_file, condivisa).
#
# Il file e' GIA' risolto dal gioco alla forma effettivamente ereditabile:
# per le white spark (categoria "skill") il nome e' SEMPRE quello della
# versione BASE/white della skill, mai quello della versione gold, anche se
# la skill gold ha un nome completamente diverso (es. la skill gold "In Body
# and Mind" genera sempre la white spark "Straightaway Adept", MAI una spark
# col nome "In Body and Mind" -- verificato dal vivo, 2026-08-14: "In Body
# and Mind" non compare da nessuna parte in factors["skill"], solo
# "Straightaway Adept" -- 439 voci in factors["skill"] contro 582 skill con
# rarity=1/white nel catalogo skill completo di Gametora, quindi non e'
# nemmeno "tutte le white": e' gia' una selezione delle sole white
# effettivamente ottenibili come spark). Nessun mapping gold->white va
# quindi costruito qui, la fonte lo ha gia' risolto.
#
# Le race spark (categoria "race") includono gia' 'race_id' (riferimento
# alla gara G1 corrispondente, non usato per ora ma salvato per un futuro
# incrocio con races.xlsx). Le altre categorie del file (pink/blue/scenario)
# non sono salvate qui: pink e' gia' implementata a parte (aptitude
# inheritance), blue ha solo le 5 statistiche note (nessun dato da
# scaricare), scenario non e' richiesto per ora.

def fetch_gametora_factors() -> dict | None:
    """Scarica data/umamusume/factors.<hash>.json (database completo delle
    spark). Ritorna None (mai un dict parziale) se non raggiungibile o privo
    delle chiavi attese."""
    data = _fetch_gametora_data_file("factors")
    if not isinstance(data, dict) or "race" not in data or "skill" not in data:
        return None
    return data


def _build_spark_list(entries: list) -> list:
    """Riduce le voci grezze di una categoria di factors.json ai soli campi
    che servono al tool (id, nome inglese/giapponese, race_id se presente),
    scartando quelle senza id o senza alcun nome inglese utilizzabile.
    Ordinata per id per diff leggibili tra un aggiornamento e l'altro."""
    result = []
    for entry in entries:
        entry_id = entry.get("id")
        name = entry.get("name_en_gl") or entry.get("name_en")
        if not entry_id or not name:
            continue
        item = {"id": entry_id, "name_en": name, "name_ja": entry.get("name_ja", "")}
        if "race_id" in entry:
            item["race_id"] = entry["race_id"]
        result.append(item)
    result.sort(key=lambda e: e["id"])
    return result


def build_spark_race_list(factors: dict) -> list:
    return _build_spark_list(factors.get("race", []))


def build_spark_skill_list(factors: dict) -> list:
    return _build_spark_list(factors.get("skill", []))


def _spark_race_path(data_dir) -> Path:
    return Path(data_dir) / "spark_race.json"


def _spark_skill_path(data_dir) -> Path:
    return Path(data_dir) / "spark_skill.json"


def get_spark_race_list(data_dir) -> list:
    """Elenco delle race spark, cosi' come salvato dall'ultimo aggiornamento
    riuscito (lista vuota se non ancora generato)."""
    return _read_json(_spark_race_path(data_dir), [])


def get_spark_skill_list(data_dir) -> list:
    """Elenco delle white spark, stesso principio di get_spark_race_list."""
    return _read_json(_spark_skill_path(data_dir), [])


def _gametora_tid_map_path(data_dir) -> Path:
    return Path(data_dir) / "gametora_tid_map.json"


def _gametora_tid_fallback_map_path(data_dir) -> Path:
    return Path(data_dir) / "gametora_tid_fallback_map.json"


def _gametora_tid_names_path(data_dir) -> Path:
    return Path(data_dir) / "gametora_tid_names.json"


def get_gametora_tid_map(data_dir) -> dict:
    """dict[tid] = nostro_id_interno, cosi' come salvato dall'ultimo
    aggiornamento riuscito (dict vuoto se non ancora generato)."""
    return _read_json(_gametora_tid_map_path(data_dir), {})


def get_gametora_tid_fallback_map(data_dir) -> dict:
    """dict[tid] = nostro_id_interno "di ripiego" (vedi
    build_gametora_tid_fallback_map), dict vuoto se non ancora generato."""
    return _read_json(_gametora_tid_fallback_map_path(data_dir), {})


def get_gametora_tid_names(data_dir) -> dict:
    """dict[tid] = nome leggibile Gametora, per ogni carta conosciuta (dict
    vuoto se non ancora generato). Vedi build_gametora_tid_names."""
    return _read_json(_gametora_tid_names_path(data_dir), {})


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

    # --- Fonte 5: character-cards.json, scaricato UNA VOLTA e riusato sia per
    # le date di rilascio mancanti (sotto) sia per le mappe tid Gametora (in
    # fondo) -- una singola chiamata di rete economica, non piu' N richieste
    # per-personaggio come nella versione precedente (vedi commento sopra
    # check_pending_global_releases per il perche' del cambio).
    cards = fetch_gametora_character_cards() if not _budget_exceeded(deadline) else None

    # --- Personaggi NON ancora su Global: cerca la data di rilascio in
    # 'cards' (Fonte 5). I personaggi GIA' su Global non vengono piu'
    # ricontrollati per nulla (i loro dati non cambiano una volta rilasciati
    # -- regola esplicita dell'utente).
    # (rilegge da disco cosi' da includere i personaggi appena aggiunti sopra)
    character_info = _load_character_info(character_info_path)
    if cards is not None:
        pending_check = check_pending_global_releases(character_info, cards)
        report["release_dates_updated"] = pending_check["release_dates_updated"]

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

    # --- Fonte 5 (continua): mappe tid Gametora -> nostro ID interno
    # (import/export posseduti compatibile col Collection Tracker), costruite
    # dallo stesso 'cards' gia' scaricato sopra -- nessuna richiesta di rete
    # aggiuntiva. Fallisce in modo sicuro (nessuna scrittura) se Gametora non
    # era raggiungibile ('cards' None).
    report["gametora_tid_map_updated"] = False
    if cards is not None:
        character_info = _load_character_info(character_info_path)  # rilegge per includere eventuali variant/date aggiunte sopra
        tid_map = build_gametora_tid_map(character_info, cards)
        tid_map_path = _gametora_tid_map_path(data_dir)
        if tid_map != get_gametora_tid_map(data_dir):
            tid_map_path.write_text(json.dumps(tid_map, ensure_ascii=False, indent=2, sort_keys=True))
            report["gametora_tid_map_updated"] = True

        fallback_map = build_gametora_tid_fallback_map(character_info, cards, tid_map)
        fallback_map_path = _gametora_tid_fallback_map_path(data_dir)
        if fallback_map != get_gametora_tid_fallback_map(data_dir):
            fallback_map_path.write_text(json.dumps(fallback_map, ensure_ascii=False, indent=2, sort_keys=True))

        tid_names = build_gametora_tid_names(cards)
        tid_names_path = _gametora_tid_names_path(data_dir)
        if tid_names != get_gametora_tid_names(data_dir):
            tid_names_path.write_text(json.dumps(tid_names, ensure_ascii=False, indent=2, sort_keys=True))

    # --- Fonte 6: factors.json -- elenco race spark e white spark, per la
    # pianificazione dell'eredita' (v4). Fetch indipendente da 'cards' sopra
    # (file diverso), ma stesso schema hash-via-manifest e stessa politica di
    # scrittura solo se cambiato rispetto all'ultimo salvataggio.
    report["spark_lists_updated"] = False
    if not _budget_exceeded(deadline):
        factors = fetch_gametora_factors()
        if factors is not None:
            spark_race = build_spark_race_list(factors)
            spark_skill = build_spark_skill_list(factors)
            if spark_race != get_spark_race_list(data_dir) or spark_skill != get_spark_skill_list(data_dir):
                # encoding="utf-8" esplicito: name_ja e' testo non-ASCII, il
                # default di sistema (cp1252 su Windows) non lo rappresenta
                # (vedi commento su _read_json).
                _spark_race_path(data_dir).write_text(
                    json.dumps(spark_race, ensure_ascii=False, indent=2), encoding="utf-8",
                )
                _spark_skill_path(data_dir).write_text(
                    json.dumps(spark_skill, ensure_ascii=False, indent=2), encoding="utf-8",
                )
                report["spark_lists_updated"] = True

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
    mancante/corrotto equivale semplicemente a 'non ancora impostato').
    encoding='utf-8' esplicito (non il default di sistema, cp1252 su
    Windows): i file scritti da questo modulo possono contenere testo non-
    ASCII (es. name_ja delle spark, Fonte 6) e vanno scritti con lo stesso
    encoding esplicito -- vedi _spark_race_path/_spark_skill_path in
    run_update."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
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


def maybe_run_update(data_dir: str) -> dict | None:
    """Esegue un aggiornamento SEMPRE, se l'aggiornamento automatico e'
    abilitato (vedi is_auto_update_enabled/set_auto_update_enabled) --
    nessun gate a 24 ore (rimosso il 2026-08-12, su richiesta esplicita
    dell'utente, in preparazione al passaggio da .exe a sito web sempre
    aggiornato: un tool usato saltuariamente non deve aspettare un giorno
    intero per recuperare dati mancanti, es. una data di rilascio). Pensato
    per essere chiamato all'AVVIO dell'app (non serve un processo sempre
    attivo). Non solleva mai eccezioni verso il chiamante: un problema di
    rete non deve impedire l'avvio dell'app con i dati gia' presenti. Un
    budget di tempo complessivo (MAX_UPDATE_SECONDS) protegge comunque da
    un'attesa troppo lunga anche in caso di rete molto lenta (vedi
    run_update); il controllo varianti (fonte 3, comunque non funzionante al
    momento, vedi in cima al file) resta dietro il proprio gate separato a
    7+ giorni, non toccato da questo cambiamento.

    Se l'utente ha disattivato l'aggiornamento automatico, non fa nulla e
    ritorna None immediatamente.

    Ritorna il report se l'aggiornamento e' stato eseguito, altrimenti None.
    """
    if not is_auto_update_enabled(data_dir):
        return None

    try:
        report = run_update(data_dir)
    except Exception as exc:
        report = {"timestamp": datetime.now(timezone.utc).isoformat(), "errors": [str(exc)]}

    _state_path(data_dir).write_text(json.dumps({"last_update_utc": datetime.now(timezone.utc).isoformat()}))

    report_path = Path(data_dir) / "last_update_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    return report
