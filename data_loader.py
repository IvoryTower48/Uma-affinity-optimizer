# -*- coding: utf-8 -*-
"""
Carica tutti i dataset dal filesystem e li normalizza in strutture Python semplici
(dict/set), cosi' il resto dello script non dipende da pandas per la logica di calcolo.
"""
import os
import re
from datetime import date
import pandas as pd

SLOT_PATTERN = re.compile(r"^y([123])_m(0[1-9]|1[0-2])_d([12])$")


def load_base_affinity_data(data_dir):
    """
    Ritorna:
      character_ids: dict[str base_jp_name] -> set[int]  (chiavi in giapponese, come da fonte)
      id_weights: dict[int] -> int
    """
    ids_df = pd.read_csv(os.path.join(data_dir, "character_ids.csv"))
    weights_df = pd.read_csv(os.path.join(data_dir, "id_weights.csv"))

    character_ids = {}
    for name, group in ids_df.groupby("character"):
        character_ids[name] = set(group["id"].astype(int).tolist())

    id_weights = dict(zip(weights_df["id"].astype(int), weights_df["weight"].astype(int)))
    return character_ids, id_weights


def load_aptitudes(data_dir):
    """
    Ritorna dict[character] -> dict con chiavi:
      turf, dirt, sprint, mile, medium, long, front, pace, late, end (voti A-G)
    """
    df = pd.read_excel(os.path.join(data_dir, "aptitudes.xlsx"))
    df.columns = [c.strip().lower() for c in df.columns]
    aptitudes = {}
    for _, row in df.iterrows():
        char = row["character"]
        aptitudes[char] = {
            col: str(row[col]).strip().upper()
            for col in ["turf", "dirt", "sprint", "mile", "medium", "long",
                        "front", "pace", "late", "end"]
        }
    return aptitudes


def load_races(data_dir):
    """
    Ritorna dict[race_id] -> dict con chiavi: surface, distance, turn, distance_type,
    season, occurrences, years, slot, turn_number. Gestisce l'header duplicato
    'turn' leggendo per posizione di colonna invece che per nome.

    Alcune gare (es. arima_kinen) ricorrono su piu' anni con righe separate in
    races.xlsx (slot/turn_number diversi per anno). Queste vengono tenute TUTTE
    in 'occurrences' (lista di {year, slot, turn_number}), cosi' la logica di
    raggiungibilita' puo' verificare se ALMENO UN anno e' libero per quella gara,
    invece di perdere le altre occorrenze. 'slot'/'turn_number' a livello di
    gara restano come campi di comodo (la prima occorrenza, usata per
    ordinamento/visualizzazione quando non serve la lista completa); 'years'
    lista tutti gli anni in cui la gara ricorre (solo per visualizzazione, es.
    "arima_kinen (Y2, Y3)").
    """
    df = pd.read_excel(os.path.join(data_dir, "races.xlsx"), header=None)
    header_row = df.iloc[0].tolist()
    df = df.iloc[1:]
    df.columns = header_row

    races = {}
    for _, row in df.iterrows():
        race_id = row.iloc[0]
        slot = str(row.iloc[6]).strip()
        year = int(slot[1]) if slot.startswith("y") else None
        turn_number = int(row.iloc[7])

        if race_id not in races:
            races[race_id] = {
                "surface": str(row.iloc[1]).strip().lower(),
                "distance": str(row.iloc[2]).strip().lower(),
                "turn": str(row.iloc[3]).strip().lower(),
                "distance_type": str(row.iloc[4]).strip().lower(),
                "season": str(row.iloc[5]).strip().lower(),
                "occurrences": [],
            }
        races[race_id]["occurrences"].append({
            "year": year, "slot": slot, "turn_number": turn_number,
        })

    for race_id, info in races.items():
        info["occurrences"].sort(key=lambda o: o["year"])
        info["years"] = [o["year"] for o in info["occurrences"]]
        # campi di comodo: prima occorrenza, per codice che non ha ancora
        # bisogno della lista completa (es. ordinamento per visualizzazione)
        info["slot"] = info["occurrences"][0]["slot"]
        info["turn_number"] = info["occurrences"][0]["turn_number"]
    return races


def load_mandatory_races(data_dir):
    """
    Ritorna dict[character] -> list of dict con chiavi: race, year, slot.
    Per le entry 'blocked:<slot>' lo slot e' estratto direttamente dal nome;
    per le gare reali, lo slot viene risolto tramite races.xlsx (passato a parte
    dal chiamante, vedi build_character_calendar).
    """
    df = pd.read_excel(os.path.join(data_dir, "mandatory_races.xlsx"))
    df.columns = [c.strip().lower() for c in df.columns]

    mandatory = {}
    for _, row in df.iterrows():
        char = row["character"]
        mandatory.setdefault(char, []).append({
            "race": row["race"],
            "year": int(row["year"]),
        })
    return mandatory


def load_character_info(data_dir):
    """
    Legge data/character_info.csv (colonne: character, jp_name, global_release_date)
    e ritorna due dict separati per comodita' d'uso a valle:
      name_map: dict[character (con suffisso)] -> jp_name
      releases: dict[character (con suffisso)] -> global_release_date (str 'YYYY-MM-DD' o None)
    File opzionale/parziale: se assente ritorna ({}, {}); righe con celle vuote
    vengono gestite singolarmente (es. jp_name presente ma global_release_date vuota).
    """
    path = os.path.join(data_dir, "character_info.csv")
    if not os.path.exists(path):
        return {}, {}
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]

    name_map = {}
    releases = {}
    for _, row in df.iterrows():
        char = row["character"]
        if "jp_name" in df.columns and not pd.isna(row.get("jp_name")):
            name_map[char] = str(row["jp_name"]).strip()
        global_date = row.get("global_release_date")
        releases[char] = {
            "global_release_date": None if pd.isna(global_date) else str(global_date).strip()
        }
    return name_map, releases


def build_character_calendar(mandatory_races, races):
    """
    Arricchisce mandatory_races con lo slot risolto per ogni entry:
      - se race == 'blocked:<slot>', lo slot e' quello embeddato nel nome
      - altrimenti lo slot viene cercato nell'OCCORRENZA di races[race] che
        corrisponde all'anno specifico di questa entry (una gara ricorrente
        come arima_kinen ha occorrenze diverse per anno 2 e anno 3, con slot
        diversi -- usare l'occorrenza sbagliata farebbe risultare occupato il
        turno sbagliato del calendario del personaggio).
    Ritorna dict[character] -> list of dict {race, year, slot, is_blocked}
    Solleva un errore chiaro se una gara reale non e' trovata in races.xlsx
    (non dovrebbe succedere, dato che i due file sono stati validati incrociati).
    """
    calendar = {}
    for char, entries in mandatory_races.items():
        enriched = []
        for e in entries:
            race = e["race"]
            if race.startswith("blocked:"):
                slot = race.split("blocked:", 1)[1]
                is_blocked = True
            else:
                if race not in races:
                    raise ValueError(
                        f"Gara '{race}' (personaggio {char}) non trovata in races.xlsx"
                    )
                occurrence = next(
                    (o for o in races[race]["occurrences"] if o["year"] == e["year"]),
                    None,
                )
                if occurrence is None:
                    raise ValueError(
                        f"Gara '{race}' (personaggio {char}) non ha un'occorrenza per "
                        f"l'anno {e['year']} in races.xlsx"
                    )
                slot = occurrence["slot"]
                is_blocked = False
            enriched.append({
                "race": race,
                "year": e["year"],
                "slot": slot,
                "is_blocked": is_blocked,
            })
        calendar[char] = enriched
    return calendar


def apply_global_filter(characters, releases, reference_date=None):
    """
    Esclude i personaggi non ancora usciti su Global alla data di riferimento.
    Ritorna (personaggi_filtrati, avviso_o_None) -- il chiamante decide come
    mostrare l'eventuale avviso (print in CLI, campo JSON nella UI).
    """
    if not releases:
        return characters, "character_info.csv assente: filtro Global ignorato."
    ref = reference_date or date.today().isoformat()
    kept = [
        char for char in characters
        if releases.get(char) and releases[char].get("global_release_date")
        and releases[char]["global_release_date"] <= ref
        # se non c'e' data Global (o il personaggio non e' nel file), viene escluso
    ]
    return kept, None
