# -*- coding: utf-8 -*-
"""
Aggiornamento automatico dei dati da internet, senza input dell'utente, ad
ogni avvio se abilitato (vedi maybe_run_update, chiamata da app.py/main.py).

Fonti attive (la numerazione segue la storia del file, le fonti 2/3/4 sono
state rimosse):

1. GitHub (mee1080/umaishow, Source.kt) -- ID di affinita' e relativi pesi
   (character_ids.csv / id_weights.csv). Formato testuale stabile:
     chara: "NomeGiapponese:id1,id2,id3,..."  (un personaggio per riga)
     relation: "id:peso"                       (un ID per riga)
   IMPORTANTE (verificato su gametora.com/umamusume/compatibility): le
   varianti/costumi di uno stesso personaggio condividono TUTTI gli stessi ID
   di affinita' del personaggio base -- quindi questa fonte serve SOLO per
   personaggi nuovi o ID nuovi, mai per varianti.

5. Gametora character-cards.<hash>.json (lo stesso JSON che alimenta il loro
   Collection Tracker e le pagine per-personaggio): per ogni carta nome
   inglese/giapponese, aptitude (10 valori nello stesso ordine di
   APTITUDE_COLUMNS, verificato), data di rilascio Global, card_id/char_id,
   tid. UN solo fetch per esecuzione, usato per:
   - personaggi nuovi (resolve_new_characters),
   - date Global mancanti (check_pending_global_releases),
   - costumi nuovi (check_new_variants),
   - aptitude da verificare, SOLO segnalazione (check_aptitude_mismatches),
   - gare obbligatorie dei personaggi che non ne hanno, dal file gemello
     ura-objectives.<hash>.json (build_mandatory_races); per quelli che le
     hanno gia', differenze SOLO segnalate,
   - mappe tid Gametora -> nostro id (build_gametora_tid_map & co., per
     import/export posseduti e veterani) e card_id del gioco -> nostro id
     (data/card_characters.json, import veterani da umadump), costume di
     ogni carta (data/card_costumes.json, ritratti dei veterani). L'hash nel
     nome del file cambia ad ogni deploy del sito: si risolve via
     data/manifests/umamusume.json.

6. Gametora factors.<hash>.json -- catalogo delle spark: race, white
   (data/spark_race.json, data/spark_skill.json) e, per l'import da
   umadump, blue/pink/green (data/spark_blue.json, spark_pink.json,
   spark_green.json).

7. uma.moe character_names.json -- SOLO il nome del costume ("Summer",
   "Christmas"...) di una carta, che character-cards.json non contiene: per
   nominare un costume nuovo e per abbinare la data Global al costume
   giusto. Scaricato al massimo una volta per esecuzione, solo se serve.

8. uma.moe race_to_saddle_mapping.json -- "sella" vinta (win_saddle_id del
   gioco) -> nostra gara G1 (data/saddle_races.json), per leggere le G1
   vinte dai veterani importati da umadump.

STORIA (dettagli in HANDOFF.md): il 2026-08-12 Gametora ha spostato i dati
della pagina per-personaggio al rendering client-side; lo scraping HTML
(ex Fonte 3) e la ricerca del nome inglese via Wikipedia (ex Fonte 2) sono
rimasti silenziosamente rotti fino al 2026-11-20, quando personaggi nuovi e
costumi nuovi sono stati migrati su character-cards.json e quel codice e'
stato rimosso. L'ex Fonte 4 (umapyoi.net) non ha mai esposto una data di
rilascio ed e' stata rimossa il 2026-08-12.

Il meccanismo fallisce SEMPRE in modo sicuro (nessuna scrittura, nessun
dato inventato) se una fonte non e' raggiungibile o non torna un risultato
affidabile.
"""
import csv
import functools
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from config import KNOWN_SUFFIXES, META_PARENTS
from data_loader import load_races
from naming import base_character

SOURCE_KT_URL = (
    "https://raw.githubusercontent.com/mee1080/umaishow/main/core/src/"
    "commonMain/kotlin/io/github/mee1080/umaishow/data/Source.kt"
)
UMAMOE_CHARACTER_NAMES_URL = "https://uma.moe/resources/current/character_names.json.gz"
UMAMOE_SADDLE_URL = "https://uma.moe/resources/current/race_to_saddle_mapping.json.gz"
REQUEST_TIMEOUT = 15
# Budget di tempo COMPLESSIVO per una singola esecuzione di run_update, oltre
# al timeout per singola richiesta (REQUEST_TIMEOUT): con poche richieste in
# sequenza (GitHub, manifest+cards, factors, eventualmente uma.moe), evita
# comunque un'attesa lunga se la rete e' lentissima. Se superato, le fonti
# restanti vengono saltate e riprese al prossimo avvio.
MAX_UPDATE_SECONDS = 45
USER_AGENT = (
    "Mozilla/5.0 (compatible; uma-legacy-loop-tool/1.0; "
    "aggiornamento dati locale, uso personale)"
)
HEADERS = {"User-Agent": USER_AGENT}

APTITUDE_COLUMNS = ["Turf", "Dirt", "Sprint", "Mile", "Medium", "Long", "Front", "Pace", "Late", "End"]


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
# Nomi interni e suffissi di variante
# ---------------------------------------------------------------------------

def _slugify(name: str, sep: str) -> str:
    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", sep, slug).strip(sep).lower()


def internal_character_slug(english_name: str) -> str:
    return _slugify(english_name, "_")


def epithet_to_suffix(epithet: str) -> str:
    """
    Converte il nome del costume (da uma.moe, es. 'Original', 'Grand Live',
    'Christmas') in un suffisso stile KNOWN_SUFFIXES
    (underscore, minuscolo, es. '_grand_live'). Se l'epiteto corrisponde a un
    suffisso gia' noto con nome diverso (es. 'Christmas' -> _xmas, 'New
    Year' -> _ny), usa la mappatura nota invece di generarne una nuova.
    """
    known_epithet_map = {
        "original": "og", "christmas": "xmas", "new year": "ny",
        "wedding": "wedding", "valentine": "valen", "halloween": "halloween",
        "summer": "summer", "cheer": "cheer", "island": "island",
        "ballroom": "ballroom", "anime": "anime", "onsen": "onsen",
        "hot spring": "onsen", "cheerleader": "cheer", "anime collab": "anime",
        "alt version": "alt", "festival": "fes",
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
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if suffix not in existing and suffix not in KNOWN_SUFFIXES:
        existing.append(suffix)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


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
# Personaggi nuovi e costumi nuovi sono stati migrati allo stesso modo il
# 2026-11-20 (vedi resolve_new_characters/check_new_variants sotto) e lo
# scraping HTML rimosso.

def check_pending_global_releases(character_info: pd.DataFrame, cards: list, fetch_costume_names,
                                   aptitude_by_character: dict) -> dict:
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

    **Aggiornato il 2026-11-20**: la regola sopra lasciava SENZA data per
    sempre ogni costume di un personaggio con piu' righe (14 righe reali,
    tra cui Wonder Acute e Yukino Bijin interi, quindi nascosti dal filtro
    Global pur essendo usciti). Ora per quelle righe si abbina il suffisso
    della riga (es. "_xmas"; nessun suffisso o "_og" = costume originale)
    al nome del costume della carta preso da uma.moe (fetch_costume_names,
    chiamata solo se serve): data assegnata SOLO se esattamente una carta
    Global corrisponde, altrimenti la riga resta pending. Se nessun nome
    corrisponde (i nomi dei costumi solo-JP spesso cambiano all'uscita
    Global, es. "Boho Flare" per la nostra gold_city_island), si ripiega
    sulle aptitude: una riga di costume esiste solo se le sue aptitude sono
    diverse dall'originale, quindi un'unica carta Global con aptitude
    identiche e' quel costume.

    'cards' va gia' scaricato dal chiamante (vedi run_update, Fonte 5).

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

    global_cards_by_jp = {}
    for card in cards:
        if card.get("name_jp") and card.get("release_en"):
            global_cards_by_jp.setdefault(card["name_jp"], []).append(card)

    for _, row in pending.iterrows():
        if jp_name_row_counts.get(row["jp_name"], 0) == 1:
            release = earliest_release_by_jp.get(row["jp_name"])
        else:
            release = _release_for_costume_row(row["character"], global_cards_by_jp.get(row["jp_name"], []),
                                               fetch_costume_names, aptitude_by_character.get(row["character"]))
        if release:
            result["release_dates_updated"].append({"character": row["character"], "new_date": release})

    return result


def _release_for_costume_row(character: str, global_cards: list, fetch_costume_names,
                             aptitude: tuple | None) -> str | None:
    """Data Global della carta il cui costume (nome da uma.moe) corrisponde
    al suffisso della riga, o in mancanza l'unica con aptitude identiche;
    None se nessuna o piu' di una corrisponde."""
    if not global_cards:
        return None
    suffix = character[len(base_character(character)):] or "_og"
    names = fetch_costume_names() or {}
    matches = [c for c in global_cards if names.get(c.get("card_id")) and
               epithet_to_suffix(names[c["card_id"]]) == suffix]
    if not matches and suffix != "_og":
        matches = [c for c in global_cards if tuple(c.get("aptitude") or ()) == aptitude]
    return matches[0]["release_en"] if len(matches) == 1 else None


def _cards_by_jp_name(cards: list) -> dict:
    """dict[nome_jp] -> carte di quel personaggio ordinate per card_id: la
    prima e' il costume originale (card_id = char_id * 100 + 1). Scarta le
    carte senza nome giapponese o con aptitude incomplete."""
    grouped = {}
    for card in sorted(cards, key=lambda c: c.get("card_id") or 0):
        if card.get("name_jp") and len(card.get("aptitude") or []) == len(APTITUDE_COLUMNS):
            grouped.setdefault(card["name_jp"], []).append(card)
    return grouped


def _aptitudes_by_character(aptitudes_df: pd.DataFrame) -> dict:
    return {
        row["Character"]: tuple(row[col] for col in APTITUDE_COLUMNS)
        for _, row in aptitudes_df.iterrows()
    }


def resolve_new_characters(jp_names, cards: list, known_characters: set) -> tuple:
    """
    Per ogni nome giapponese con ID di affinita' ma senza riga in
    character_info.csv, cerca il personaggio in 'cards' (Fonte 5): nome
    inglese, aptitude e data Global del costume ORIGINALE. Ritorna
    (aggiunti, da_rivedere). Un nome non risolto resta "da rivedere" e viene
    ritentato al prossimo avvio (es. personaggio annunciato ma non ancora su
    Gametora) -- mai un dato inventato. 'known_characters' viene aggiornato
    con i nomi interni aggiunti (evita doppioni nello stesso giro).
    """
    by_jp = _cards_by_jp_name(cards)
    added, needs_review = [], []
    for jp_name in jp_names:
        jp_cards = by_jp.get(jp_name)
        if not jp_cards:
            needs_review.append({
                "jp_name": jp_name,
                "reason": "Non ancora presente su Gametora, ritentato al prossimo avvio.",
            })
            continue
        original = jp_cards[0]
        character = internal_character_slug(original["name_en"])
        if character in known_characters:
            needs_review.append({
                "jp_name": jp_name, "candidate_english_name": original["name_en"],
                "reason": f"Nome interno '{character}' gia' usato da un altro personaggio.",
            })
            continue
        added.append({
            "character": character, "jp_name": jp_name, "english_name": original["name_en"],
            "global_release_date": original.get("release_en") or "",
            "aptitudes": dict(zip(APTITUDE_COLUMNS, original["aptitude"])),
            "gametora_url": f"https://gametora.com/umamusume/characters/{original.get('url_name', '')}",
        })
        known_characters.add(character)
    return added, needs_review


@functools.lru_cache(maxsize=1)  # un solo download per esecuzione, condiviso
def fetch_umamoe_costume_names() -> dict | None:
    """dict[card_id] -> nome del costume ('Original', 'Summer', ...), da
    uma.moe (character_names.json: {char_id: {name, skins: {"01": ...}}},
    card_id = char_id * 100 + numero skin). None se non raggiungibile."""
    try:
        resp = requests.get(UMAMOE_CHARACTER_NAMES_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return {
            int(char_id) * 100 + int(skin): name
            for char_id, entry in resp.json().items()
            for skin, name in (entry.get("skins") or {}).items()
        }
    except (requests.RequestException, ValueError, AttributeError, TypeError):
        return None


def check_new_variants(character_info: pd.DataFrame, aptitudes_df: pd.DataFrame,
                        cards: list, fetch_costume_names) -> dict:
    """
    Costumi nuovi dei personaggi GIA' usciti su Global (regola utente: un
    costume nuovo conta per un personaggio gia' giocabile). Un costume
    diventa una riga separata SOLO se le sue aptitude sono diverse da quelle
    del costume originale E da tutte le righe gia' tracciate per quel
    personaggio (regola utente: aptitude identiche = nessuna riga nuova).
    Il confronto parte da Gametora (costume vs originale), non dai nostri
    dati: un nostro dato sbagliato non deve far nascere costumi "fantasma"
    (caso reale Narita Taishin, 2026-11-20 -- vedi check_aptitude_mismatches).

    Il nome del costume non e' in 'cards': viene da uma.moe tramite
    fetch_costume_names (chiamata solo se c'e' almeno un candidato). Senza
    nome il costume non viene aggiunto (mai un nome inventato): finisce in
    'needs_name' e si ritenta al prossimo avvio.

    Ritorna {new_variants_found, needs_name} (non scrive nulla: la scrittura
    resta centralizzata in run_update).
    """
    result = {"new_variants_found": [], "needs_name": []}
    aptitude_by_character = _aptitudes_by_character(aptitudes_df)
    known_characters = set(character_info["character"])
    released_jp = set(character_info.loc[character_info["global_release_date"] != "", "jp_name"])
    rows_by_jp = character_info.groupby("jp_name")["character"].apply(list).to_dict()
    costume_names = None

    for jp_name, jp_cards in _cards_by_jp_name(cards).items():
        if jp_name not in released_jp:
            continue
        rows = rows_by_jp[jp_name]
        seen = {tuple(jp_cards[0]["aptitude"])}
        seen |= {aptitude_by_character[c] for c in rows if c in aptitude_by_character}
        base = min((base_character(c) for c in rows), key=len)

        for card in jp_cards[1:]:
            aptitude = tuple(card["aptitude"])
            if aptitude in seen:
                continue
            if costume_names is None:
                costume_names = fetch_costume_names() or {}
            costume = costume_names.get(card.get("card_id"))
            if not costume:
                result["needs_name"].append({
                    "jp_name": jp_name, "card_id": card.get("card_id"),
                    "reason": "Nome del costume non (ancora) disponibile su uma.moe, ritentato al prossimo avvio.",
                })
                continue
            suffix = epithet_to_suffix(costume)
            character = base + suffix
            if character in known_characters:
                continue
            result["new_variants_found"].append({
                "character": character, "base_character": base, "suffix": suffix,
                "jp_name": jp_name, "costume": costume,
                "aptitudes": dict(zip(APTITUDE_COLUMNS, aptitude)),
                "release_date": card.get("release_en") or "",
                "gametora_url": f"https://gametora.com/umamusume/characters/{card.get('url_name', '')}",
            })
            seen.add(aptitude)
            known_characters.add(character)
    return result


def check_aptitude_mismatches(character_info: pd.DataFrame, aptitudes_df: pd.DataFrame,
                               cards: list) -> list:
    """
    SOLO segnalazione, mai una correzione automatica (scelta dell'utente,
    2026-11-20; i dati di un personaggio uscito non si toccano da soli):
    personaggi gia' su Global le cui aptitude non coincidono con NESSUN
    costume Gametora dello stesso personaggio -- quasi sempre un nostro dato
    sbagliato (caso reale: Narita Taishin, Late A invece di B, corretto a
    mano). Ritorna [{character, ours, gametora: [...]}].
    """
    by_jp = _cards_by_jp_name(cards)
    aptitude_by_character = _aptitudes_by_character(aptitudes_df)
    mismatches = []
    for _, row in character_info[character_info["global_release_date"] != ""].iterrows():
        ours = aptitude_by_character.get(row["character"])
        jp_cards = by_jp.get(row["jp_name"])
        if ours is None or not jp_cards:
            continue
        theirs = sorted({tuple(card["aptitude"]) for card in jp_cards})
        if ours not in theirs:
            mismatches.append({
                "character": row["character"],
                "ours": dict(zip(APTITUDE_COLUMNS, ours)),
                "gametora": [dict(zip(APTITUDE_COLUMNS, t)) for t in theirs],
            })
    return mismatches


# ---------------------------------------------------------------------------
# Gare obbligatorie (obiettivi di carriera) da Gametora ura-objectives.json
# (aggiunto il 2026-11-21). Formato di una voce: {char_id, obj_id,
# objectives: [{order, turn (1-72), target_type (1 = obiettivo di carriera,
# 3 = finali URA), cond_type (1 = gara, 3 = fan, 2 = "vinci N gare"...),
# race_choice (0 = fisso, >0 = alternativa), races: [{id, icon_id, url_name,
# grade (100 = G1, 900 = debutto)...}]}]}. Verificato sui 148 personaggi
# gia' compilati a mano: 138 identici; le differenze erano 3 errori nostri
# (corretti), Matikanefukukitaru (obiettivi casuali in gioco) e gli
# obiettivi a scelta, ora rappresentati con la colonna Choice.
# ---------------------------------------------------------------------------

def _turn_to_slot(turn: int) -> str:
    """Turno 1-72 -> slot 'yA_mMM_dH' (24 turni per anno, 2 per mese)."""
    t = turn - 1
    return f"y{t // 24 + 1}_m{(t % 24) // 2 + 1:02d}_d{t % 2 + 1}"


def _objective_race(race: dict, slot: str, g1_by_slot: dict, our_race_by_gametora_id: dict) -> str:
    """Nostro race_id della G1 di un obiettivo, o 'blocked:<slot>' per una
    gara non G1 (o una G1 non presente in races.xlsx). La G1 si riconosce dal
    turno; se nello stesso turno ce n'e' piu' d'una (es. Japan Cup e Mile
    Championship), dall'id Gametora: quello della gara o il suo icon_id
    (l'id "canonico": Gametora usa id diversi per la stessa G1 in anni
    diversi, es. Japan Cup 1019/1031), o dal nome nell'url (satsuki-sho)."""
    candidates = g1_by_slot.get(slot, []) if race.get("grade") == 100 else []
    if len(candidates) > 1:
        keys = {our_race_by_gametora_id.get(race.get("id")), our_race_by_gametora_id.get(race.get("icon_id")),
                (race.get("url_name") or "").replace("-", "_")}
        candidates = [c for c in candidates if c in keys]
    return candidates[0] if len(candidates) == 1 else f"blocked:{slot}"


def build_mandatory_races(objectives: list, races: dict, gametora_race_ids: dict) -> list:
    """
    Obiettivi di carriera Gametora di UN personaggio -> righe di
    mandatory_races.xlsx [{race, year, choice}]. Ignorati il debutto, gli
    obiettivi senza gara (fan, "vinci N gare") e le finali URA: nessuno
    occupa un turno preciso. Un obiettivo con piu' gare dentro (JBC, che
    cambia ippodromo ogni anno) e' sempre la stessa gara: si usa la prima.
    Gli obiettivi a scelta (stesso 'order', alternative diverse) diventano
    righe con la stessa etichetta 'choice' (l'order) -- TUTTE le alternative,
    scelta dell'utente: in un gruppo se ne usa una sola, vedi
    affinity.resolve_achievable. Alternative identiche contano come una.
    """
    g1_by_slot = {}
    for race_id, info in races.items():
        for occurrence in info["occurrences"]:
            g1_by_slot.setdefault(occurrence["slot"], []).append(race_id)
    our_race_by_gametora_id = {gt_id: race_id for race_id, gt_id in gametora_race_ids.items()}

    options_by_order = {}
    for objective in sorted(objectives, key=lambda o: (o.get("order", 0), o.get("race_choice", 0),
                                                        o.get("race_choice_details", 0))):
        race_list = objective.get("races") or []
        if objective.get("target_type") != 1 or not race_list or race_list[0].get("grade") == 900:
            continue
        turn = objective["turn"]
        option = (_objective_race(race_list[0], _turn_to_slot(turn), g1_by_slot, our_race_by_gametora_id),
                  (turn - 1) // 24 + 1)
        options = options_by_order.setdefault(objective["order"], [])
        if option not in options:
            options.append(option)

    rows = []
    for order, options in sorted(options_by_order.items()):
        choice = str(order) if len(options) > 1 else ""
        rows.extend({"race": race, "year": year, "choice": choice} for race, year in options)
    return rows


def _mandatory_key(rows) -> set:
    """Forma confrontabile delle righe di un personaggio (l'etichetta della
    scelta conta solo come "e' un'alternativa o no")."""
    return {(r["race"], int(r["year"]), bool(r["choice"])) for r in rows}


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


def build_gametora_char_ids(cards: list) -> dict:
    """dict[nome_jp] = char_id Gametora (es. 1001): serve a pdf_export per
    scaricare il ritratto direttamente da media.gametora.com, senza passare
    dalla pagina per-personaggio (che dal 2026-08-12 non contiene piu' il
    link all'immagine nell'HTML)."""
    return {card["name_jp"]: card["char_id"] for card in cards if card.get("name_jp") and card.get("char_id")}


def get_gametora_char_ids(data_dir) -> dict:
    return _read_json(Path(data_dir) / "gametora_char_ids.json", {})


def build_card_characters(cards: list, tid_map: dict, fallback_map: dict) -> dict:
    """dict[str(card_id)] -> nostro id, per l'import da umadump (che usa il
    card_id del gioco, non il tid di Gametora): stesso abbinamento delle
    mappe tid (esatto, poi ripiego sul costume tracciato), solo con la
    chiave che usa il gioco."""
    by_tid = {**fallback_map, **tid_map}
    return {
        str(card["card_id"]): by_tid[card["tid"]]
        for card in cards
        if card.get("card_id") and card.get("tid") in by_tid
    }


def get_card_characters(data_dir) -> dict:
    return _read_json(Path(data_dir) / "card_characters.json", {})


def build_card_costumes(cards: list) -> dict:
    """dict[str(card_id)] = {char_id, costume}: per ogni carta il char_id
    Gametora (serve all'URL della miniatura del costume) e il tipo di costume
    ("summer", "christmas", ...; "" = originale). Solo per mostrare il costume
    vero dei veterani (2026-11-22): i calcoli usano sempre il nostro id
    personaggio, dove i costumi con le stesse aptitude restano accorpati."""
    return {
        str(card["card_id"]): {"char_id": card["char_id"], "costume": card.get("version") or ""}
        for card in cards
        if card.get("card_id") and card.get("char_id")
    }


def get_card_costumes(data_dir) -> dict:
    return _read_json(Path(data_dir) / "card_costumes.json", {})


def fetch_umamoe_saddles() -> list | None:
    """Gare di uma.moe con le loro selle ({race_id, short_name,
    win_saddles: [{saddle_id, win_saddle_type}]}). None se non raggiungibile."""
    try:
        resp = requests.get(UMAMOE_SADDLE_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        races = resp.json()["races"]
        return races if isinstance(races, list) else None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def build_saddle_races(saddle_races: list, gametora_race_ids: dict) -> dict:
    """dict[str(saddle_id)] -> nostro race_id, solo selle di una G1 singola
    (win_saddle_type 3; le corone sono ignorate: ogni loro G1 ha gia' la
    propria sella). La gara si riconosce dal race_id del gioco
    (race_gametora_ids.json); le versioni alternative della stessa G1 (JBC
    su ippodromi diversi, una seconda Takarazuka Kinen...) hanno un race_id
    diverso ma lo stesso nome, quindi si abbinano per nome."""
    our_by_game_id = {game_id: race for race, game_id in gametora_race_ids.items()}
    g1 = [(r, w["saddle_id"]) for r in saddle_races for w in r.get("win_saddles") or []
          if w.get("win_saddle_type") == 3]
    our_by_name = {r.get("short_name"): our_by_game_id[r["race_id"]] for r, _ in g1 if r.get("race_id") in our_by_game_id}
    result = {}
    for r, saddle_id in g1:
        race = our_by_game_id.get(r.get("race_id")) or our_by_name.get(r.get("short_name"))
        if race:
            result[str(saddle_id)] = race
    return result


def get_saddle_races(data_dir) -> dict:
    return _read_json(Path(data_dir) / "saddle_races.json", {})


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


def _build_spark_list(entries: list, name_ja_fallback: bool = False) -> list:
    """Riduce le voci grezze di una categoria di factors.json ai soli campi
    che servono al tool (id, nome inglese/giapponese, race_id se presente,
    tid), scartando quelle senza id o senza alcun nome inglese utilizzabile.
    Ordinata per id per diff leggibili tra un aggiornamento e l'altro.

    'tid': il codice corto usato da Gametora nel proprio export/import dei
    Veterans (es. "1n", "f") -- diverso dal 'tid' dei personaggi
    (data/gametora_tid_map.json, namespace separato, vedi
    veterans_gametora.py). Serve per la mappatura bidirezionale delle spark
    in quell'export, decodificato a mano confrontando un file reale
    esportato dall'utente con questo stesso factors.json (2026-08-15)."""
    result = []
    for entry in entries:
        entry_id = entry.get("id")
        name = entry.get("name_en_gl") or entry.get("name_en")
        if not name and name_ja_fallback:
            name = entry.get("name_ja")  # spark verdi di carte solo JP: nessun nome inglese
        if not entry_id or not name:
            continue
        item = {
            "id": entry_id, "name_en": name, "name_ja": entry.get("name_ja", ""),
            "tid": entry.get("tid", ""),
        }
        if "race_id" in entry:
            item["race_id"] = entry["race_id"]
        result.append(item)
    result.sort(key=lambda e: e["id"])
    return result


def build_spark_race_list(factors: dict) -> list:
    return _build_spark_list(factors.get("race", []))


def build_spark_skill_list(factors: dict) -> list:
    return _build_spark_list(factors.get("skill", []))


def build_extra_spark_lists(factors: dict) -> dict:
    """Cataloghi blue/pink/green (solo per l'import da umadump): blue e pink
    sono le categorie omonime, green le spark uniche (in 'other', type 3,
    id = card_id della carta)."""
    return {
        "spark_blue.json": _build_spark_list(factors.get("blue", [])),
        "spark_pink.json": _build_spark_list(factors.get("pink", [])),
        "spark_green.json": _build_spark_list(
            [e for e in factors.get("other", []) if e.get("type") == 3], name_ja_fallback=True,
        ),
    }


def get_spark_list(data_dir, filename: str) -> list:
    return _read_json(Path(data_dir) / filename, [])


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
        "new_variants_needs_name": [],   # costumi nuovi in attesa del nome da uma.moe
        "aptitude_mismatches": [],       # SOLO segnalazione, vedi check_aptitude_mismatches
        "mandatory_races_added": [],     # personaggi a cui sono state compilate le gare obbligatorie
        "mandatory_races_mismatches": [],  # SOLO segnalazione: differenze con Gametora
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
    # ha novita': i controlli basati su Gametora (personaggi/costumi nuovi,
    # date Global, piu' sotto) girano comunque ad ogni esecuzione.
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

    # --- character_ids.csv: righe dei personaggi comparsi per la prima volta
    # nella fonte 1 (scritte SUBITO, anche se il personaggio non si risolve:
    # vedi "Personaggi nuovi" sotto per come viene ritentato).
    for jp_name, ids in new_characters.items():
        new_rows.extend((jp_name, id_) for id_ in ids)
    if new_rows:
        with open(character_ids_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            for name, id_ in new_rows:
                writer.writerow([name, id_])

    # --- Fonte 5: character-cards.json, scaricato UNA VOLTA e riusato per
    # personaggi nuovi, date Global, costumi nuovi, aptitude da verificare e
    # mappe tid (in fondo).
    cards = fetch_gametora_character_cards() if not _budget_exceeded(deadline) else None

    # --- Personaggi nuovi: TUTTI i nomi giapponesi con ID di affinita' ma
    # senza riga in character_info.csv, non solo quelli comparsi in questo
    # giro. Bug corretto il 2026-11-20: gli ID venivano scritti anche quando
    # la conferma falliva, e al giro dopo il personaggio non risultava piu'
    # "nuovo" -- restava bloccato a meta' per sempre (5 casi reali). Cosi'
    # chi non si risolve viene semplicemente ritentato ad ogni avvio.
    to_resolve = sorted((set(existing_chara) | set(new_characters)) - set(character_info["jp_name"]))
    if to_resolve and cards is None:
        report["new_characters_needs_review"] = [
            {"jp_name": jp_name, "reason": "Gametora non raggiungibile, ritentato al prossimo avvio."}
            for jp_name in to_resolve
        ]
    elif to_resolve:
        added, needs_review = resolve_new_characters(to_resolve, cards, set(character_info["character"]))
        report["new_characters_added"] = added
        report["new_characters_needs_review"] = needs_review
        if added:
            character_info = pd.concat([character_info, pd.DataFrame([
                {"character": a["character"], "jp_name": a["jp_name"], "global_release_date": a["global_release_date"]}
                for a in added
            ])], ignore_index=True)
            character_info.to_csv(character_info_path, index=False)
            aptitudes_df = pd.concat([aptitudes_df, pd.DataFrame([
                {"Character": a["character"], **a["aptitudes"]} for a in added
            ])], ignore_index=True)
            aptitudes_df.to_excel(aptitudes_path, index=False)

    # --- Personaggi NON ancora su Global: cerca la data di rilascio in
    # 'cards'. I personaggi GIA' su Global non vengono piu' ricontrollati per
    # la data (i loro dati non cambiano una volta rilasciati -- regola
    # esplicita dell'utente).
    # (rilegge da disco cosi' da includere i personaggi appena aggiunti sopra)
    character_info = _load_character_info(character_info_path)
    if cards is not None:
        pending_check = check_pending_global_releases(character_info, cards, fetch_umamoe_costume_names,
                                                      _aptitudes_by_character(_load_aptitudes(aptitudes_path)))
        report["release_dates_updated"] = pending_check["release_dates_updated"]

        if pending_check["release_dates_updated"]:
            by_character = {r["character"]: r["new_date"] for r in pending_check["release_dates_updated"]}
            character_info["global_release_date"] = character_info.apply(
                lambda r: by_character.get(r["character"], r["global_release_date"]), axis=1,
            )
            character_info.to_csv(character_info_path, index=False)

    # --- Costumi nuovi + aptitude da verificare: dallo stesso 'cards', ad
    # ogni avvio (un solo fetch, nessun gate a 7 giorni come quando servivano
    # ~60-90 richieste per-personaggio). uma.moe solo se c'e' un costume
    # nuovo da nominare.
    if cards is not None:
        aptitudes_df = _load_aptitudes(aptitudes_path)
        variant_check = check_new_variants(character_info, aptitudes_df, cards, fetch_umamoe_costume_names)
        report["new_variants_added"] = variant_check["new_variants_found"]
        report["new_variants_needs_name"] = variant_check["needs_name"]

        if variant_check["new_variants_found"]:
            for variant in variant_check["new_variants_found"]:
                if variant["suffix"] and variant["suffix"] not in KNOWN_SUFFIXES:
                    _register_new_suffix(data_dir, variant["suffix"])
            character_info = pd.concat([character_info, pd.DataFrame([
                {"character": v["character"], "jp_name": v["jp_name"], "global_release_date": v["release_date"]}
                for v in variant_check["new_variants_found"]
            ])], ignore_index=True)
            aptitudes_df = pd.concat([aptitudes_df, pd.DataFrame([
                {"Character": v["character"], **v["aptitudes"]} for v in variant_check["new_variants_found"]
            ])], ignore_index=True)
            character_info.to_csv(character_info_path, index=False)
            aptitudes_df.to_excel(aptitudes_path, index=False)

        report["aptitude_mismatches"] = check_aptitude_mismatches(character_info, aptitudes_df, cards)

    # --- Gare obbligatorie: compilate SOLO per i personaggi che non ne hanno
    # (nuovi, o mai compilati come Rulership); le righe esistenti non si
    # toccano mai, le differenze con Gametora vengono solo segnalate.
    if cards is not None and not _budget_exceeded(deadline):
        objectives = _fetch_gametora_data_file("ura-objectives")
        if isinstance(objectives, list):
            mandatory_path = data_dir / "mandatory_races.xlsx"
            mandatory_df = pd.read_excel(mandatory_path)
            if "Choice" not in mandatory_df.columns:
                mandatory_df["Choice"] = ""
            objectives_by_char_id = {o.get("char_id"): o.get("objectives") or [] for o in objectives}
            char_id_by_jp = build_gametora_char_ids(cards)
            races = load_races(data_dir)
            gametora_race_ids = _read_json(data_dir / "race_gametora_ids.json", {})
            existing = {
                character: [{"race": r.Race, "year": r.Year, "choice": "" if pd.isna(r.Choice) else str(r.Choice)}
                            for r in rows.itertuples()]
                for character, rows in mandatory_df.groupby("Character")
            }
            new_rows = []
            for _, row in character_info.iterrows():
                char_objectives = objectives_by_char_id.get(char_id_by_jp.get(row["jp_name"]))
                if not char_objectives:
                    continue
                expected = build_mandatory_races(char_objectives, races, gametora_race_ids)
                if row["character"] not in existing:
                    new_rows += [{"Character": row["character"], "Race": r["race"], "Year": r["year"],
                                  "Choice": r["choice"]} for r in expected]
                    report["mandatory_races_added"].append(row["character"])
                elif _mandatory_key(existing[row["character"]]) != _mandatory_key(expected):
                    ours, theirs = _mandatory_key(existing[row["character"]]), _mandatory_key(expected)
                    report["mandatory_races_mismatches"].append({
                        "character": row["character"],
                        "only_ours": sorted(map(list, ours - theirs)),
                        "only_gametora": sorted(map(list, theirs - ours)),
                    })
            if new_rows:
                mandatory_df = pd.concat([mandatory_df, pd.DataFrame(new_rows)], ignore_index=True)
                mandatory_df.to_excel(mandatory_path, index=False)

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
            tid_map_path.write_text(json.dumps(tid_map, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            report["gametora_tid_map_updated"] = True

        fallback_map = build_gametora_tid_fallback_map(character_info, cards, tid_map)
        fallback_map_path = _gametora_tid_fallback_map_path(data_dir)
        if fallback_map != get_gametora_tid_fallback_map(data_dir):
            fallback_map_path.write_text(json.dumps(fallback_map, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

        card_characters = build_card_characters(cards, tid_map, fallback_map)
        if card_characters != get_card_characters(data_dir):
            (data_dir / "card_characters.json").write_text(
                json.dumps(card_characters, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
            )

        card_costumes = build_card_costumes(cards)
        if card_costumes != get_card_costumes(data_dir):
            (data_dir / "card_costumes.json").write_text(
                json.dumps(card_costumes, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
            )

        char_ids = build_gametora_char_ids(cards)
        if char_ids != get_gametora_char_ids(data_dir):
            (data_dir / "gametora_char_ids.json").write_text(
                json.dumps(char_ids, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8",
            )

        tid_names = build_gametora_tid_names(cards)
        tid_names_path = _gametora_tid_names_path(data_dir)
        if tid_names != get_gametora_tid_names(data_dir):
            tid_names_path.write_text(json.dumps(tid_names, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

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
            for filename, spark_list in build_extra_spark_lists(factors).items():
                if spark_list and spark_list != get_spark_list(data_dir, filename):
                    (data_dir / filename).write_text(json.dumps(spark_list, ensure_ascii=False, indent=2), encoding="utf-8")
                    report["spark_lists_updated"] = True

    # --- Fonte 8: selle uma.moe -> nostre G1 (import veterani da umadump)
    if not _budget_exceeded(deadline):
        saddles = fetch_umamoe_saddles()
        if saddles is not None:
            saddle_races = build_saddle_races(saddles, _read_json(data_dir / "race_gametora_ids.json", {}))
            if saddle_races and saddle_races != get_saddle_races(data_dir):
                (data_dir / "saddle_races.json").write_text(
                    json.dumps(saddle_races, indent=2, sort_keys=True), encoding="utf-8",
                )

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


def _backup_data_files(data_dir: str):
    data_dir = Path(data_dir)
    backup_dir = data_dir / "update_backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir.mkdir(parents=True, exist_ok=True)
    for name in ("character_ids.csv", "id_weights.csv", "character_info.csv", "aptitudes.xlsx",
                 "mandatory_races.xlsx"):
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
    run_update).

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
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


if __name__ == "__main__":
    # Self-check offline (nessuna rete) delle funzioni basate su
    # character-cards.json: personaggio nuovo, costume nuovo con e senza nome,
    # costume con aptitude identiche, aptitude nostra sbagliata.
    apt = lambda late: ["A", "G", "F", "D", "A", "A", "G", "F", late, "A"]
    card = lambda card_id, jp, en, late, release: {
        "card_id": card_id, "name_jp": jp, "name_en": en, "aptitude": apt(late),
        "release_en": release, "url_name": f"{card_id}-x",
    }
    cards = [
        card(100101, "ア", "Aaa", "B", "2025-06-26"),
        card(100102, "ア", "Aaa", "B", "2025-12-01"),  # aptitude identiche: nessuna riga
        card(100103, "ア", "Aaa", "C", "2026-01-01"),  # costume nuovo, nome da uma.moe
        card(100104, "ア", "Aaa", "D", None),          # costume nuovo senza nome
        card(100201, "イ", "Bee Bee", "B", None),       # personaggio nuovo (solo JP)
        card(100301, "ウ", "Ccc", "B", "2025-06-26"),
    ]
    info = pd.DataFrame([
        {"character": "aaa", "jp_name": "ア", "global_release_date": "2025-06-26"},
        {"character": "ccc", "jp_name": "ウ", "global_release_date": "2025-06-26"},
    ])
    apts = pd.DataFrame([
        {"Character": "aaa", **dict(zip(APTITUDE_COLUMNS, apt("B")))},
        {"Character": "ccc", **dict(zip(APTITUDE_COLUMNS, apt("A")))},  # dato nostro sbagliato
    ])

    added, review = resolve_new_characters(["イ", "エ"], cards, set(info["character"]))
    assert [a["character"] for a in added] == ["bee_bee"] and added[0]["global_release_date"] == ""
    assert [r["jp_name"] for r in review] == ["エ"]

    variants = check_new_variants(info, apts, cards, lambda: {100103: "Summer"})
    assert [(v["character"], v["release_date"]) for v in variants["new_variants_found"]] == [("aaa_summer", "2026-01-01")]
    assert [n["card_id"] for n in variants["needs_name"]] == [100104]
    assert check_new_variants(info, apts, cards[:2], lambda: 1 / 0)["new_variants_found"] == []  # uma.moe mai chiamato se non serve

    assert [m["character"] for m in check_aptitude_mismatches(info, apts, cards)] == ["ccc"]

    pending = pd.DataFrame([
        {"character": "aaa_og", "jp_name": "ア", "global_release_date": ""},
        {"character": "aaa_summer", "jp_name": "ア", "global_release_date": ""},
        {"character": "aaa_xmas", "jp_name": "ア", "global_release_date": ""},  # nessuna carta Global
        {"character": "aaa_island", "jp_name": "ア", "global_release_date": ""},  # nome diverso, aptitude uguali
    ])
    names = lambda: {100101: "Original", 100103: "Summer"}
    by_apt = {"aaa_xmas": tuple(apt("D")), "aaa_island": tuple(apt("C"))}
    dates = check_pending_global_releases(pending, cards, names, by_apt)["release_dates_updated"]
    assert dates == [{"character": "aaa_og", "new_date": "2025-06-26"},
                     {"character": "aaa_summer", "new_date": "2026-01-01"},
                     {"character": "aaa_island", "new_date": "2026-01-01"}], dates
    # Gare obbligatorie: G1 riconosciuta dal turno (e dall'icon_id se due G1
    # condividono il turno), gara minore bloccata, debutto/fan/URA ignorati,
    # alternative con la stessa etichetta, alternative identiche fuse.
    test_races = {
        "japan_cup": {"occurrences": [{"slot": "y3_m11_d2"}]},
        "mile_championship": {"occurrences": [{"slot": "y3_m11_d2"}]},
        "japanese_oaks": {"occurrences": [{"slot": "y2_m05_d2"}]},
        "japanese_derby": {"occurrences": [{"slot": "y2_m05_d2"}]},
    }
    gt_ids = {"japan_cup": 1019, "mile_championship": 1018, "japanese_oaks": 1009, "japanese_derby": 1010}
    objective = lambda order, turn, race_id, grade=100, choice=0, target=1, icon=None: {
        "order": order, "turn": turn, "target_type": target, "race_choice": choice,
        "races": [{"id": race_id, "icon_id": icon or race_id, "grade": grade}],
    }
    rows = build_mandatory_races([
        objective(1, 12, 9392, grade=900),                      # debutto
        {"order": 2, "turn": 24, "target_type": 1, "race_choice": 0},  # obiettivo a fan
        objective(3, 34, 1009, choice=1), objective(3, 34, 1010, choice=2),  # Oaks oppure Derby
        objective(4, 54, 2011, grade=200),                      # Nikkei Sho (G2)
        objective(5, 70, 1031, icon=1019),                      # Japan Cup, id di un altro anno
        objective(6, 72, 1023, choice=3), objective(6, 72, 1023, choice=3),  # alternative identiche
        objective(7, 74, 0, target=3),                          # finali URA
    ], test_races, gt_ids)
    assert rows == [
        {"race": "japanese_oaks", "year": 2, "choice": "3"}, {"race": "japanese_derby", "year": 2, "choice": "3"},
        {"race": "blocked:y3_m03_d2", "year": 3, "choice": ""},
        {"race": "japan_cup", "year": 3, "choice": ""},
        {"race": "blocked:y3_m12_d2", "year": 3, "choice": ""},
    ], rows
    # Selle: G1 per race_id, versione alternativa per nome, corone ignorate.
    saddles = [
        {"race_id": 1105, "short_name": "JBC Classic", "win_saddles": [{"saddle_id": 31, "win_saddle_type": 3}]},
        {"race_id": 1113, "short_name": "JBC Classic", "win_saddles": [{"saddle_id": 158, "win_saddle_type": 3}]},
        {"race_id": 1001, "short_name": "February S.", "win_saddles": [
            {"saddle_id": 9, "win_saddle_type": 0}, {"saddle_id": 30, "win_saddle_type": 3}]},
        {"race_id": 9999, "short_name": "Altra", "win_saddles": [{"saddle_id": 77, "win_saddle_type": 3}]},
    ]
    assert build_saddle_races(saddles, {"jbc_classic": 1105, "february_stakes": 1001}) == {
        "31": "jbc_classic", "158": "jbc_classic", "30": "february_stakes"}
    assert build_card_characters(
        [{"card_id": 100101, "tid": "a"}, {"card_id": 100102, "tid": "b"}, {"card_id": 100201, "tid": "z"}],
        {"a": "special_week"}, {"b": "special_week"}) == {"100101": "special_week", "100102": "special_week"}
    assert build_card_costumes(
        [{"card_id": 100601, "char_id": 1006}, {"card_id": 100602, "char_id": 1006, "version": "christmas"},
         {"card_id": 100701}]) == {"100601": {"char_id": 1006, "costume": ""},
                                   "100602": {"char_id": 1006, "costume": "christmas"}}
    print("data_updater.py: self-check OK")
