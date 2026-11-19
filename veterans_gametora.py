# -*- coding: utf-8 -*-
"""
Conversione dei veterani (veterans.py) da/verso il formato di export di
Gametora (gametora.com/umamusume/collection-tracker/veterans -- Backup >
Veterans > Export). Non documentato: decodificato a mano (2026-08-15)
confrontando un file esportato REALE dall'utente (un veterano con entrambi
i genitori noti e spark reali su tutti i livelli) con data/spark_race.json /
data/spark_skill.json (stesso 'tid' di factors.json, vedi data_updater.py)
e data/gametora_tid_map.json (tid dei PERSONAGGI, namespace separato).

Struttura di UN veterano nell'export (array a 11 elementi, verificata sul
file reale, non su una singola ipotesi):
  [0]  1                    costante fissa (verificata su piu' veterani/
                             personaggi diversi, non e' un riferimento)
  [1]  tid personaggio       stesso namespace di data/gametora_tid_map.json
  [2]  punteggio (int) o null   non tracciato da questo tool
  [3]  null                  non tracciato (probabile data di training)
  [4]  [int x5]              blue spark (5 statistiche) -- non tracciato
  [5]  null                  sconosciuto, sempre null nei campioni osservati
  [6]  []                    sconosciuto, sempre vuoto nei campioni osservati
  [7]  "sparks bucket" (7 elementi, STESSA forma per il veterano e per
       ciascun Legacy sotto):
         [0] [tid,stelle] o [0,0]  badge riassuntivo (pink/blue mischiati
                                    nei campioni osservati) -- non tracciato
         [1] [tid,stelle] o [0,0]  come sopra
         [2] int                   contatore legato ai due badge sopra --
                                    non tracciato
         [3] [[tid,stelle],...]    RACE SPARK -- TRACCIATO (race_sparks)
         [4] [[tid,stelle],...]    WHITE/SKILL SPARK -- TRACCIATO (white_sparks)
         [5] [[tid,stelle],...]    scenario spark -- non tracciato
         [6] [[tid,stelle],...]    altre spark -- non tracciato
  [8]  [Legacy1, Legacy2]    uno o entrambi null se ignoto. Ciascun Legacy
       noto: [tid personaggio, punteggio|null, sparks bucket (STESSA forma
       del [7] sopra), []] -- MAI un veterano a se' stante (niente
       ricorsione, coerente con veterans.py).
  [9]  []                    sconosciuto (probabile "gare vinte in
                              carriera") -- non tracciato
  [10] [[], [], null, creato_ms, modificato_ms]  i due timestamp sono UNIX ms

Questo tool traccia SOLO white_sparks/race_sparks (per il veterano stesso e
per i suoi 2 genitori noti, vedi veterans.py) -- punteggio/data/blue/pink/
scenario/other/tag/gare-vinte NON sono modellati: l'export scrive sempre i
valori di default osservati nel campione senza spark (baseline), l'import
li ignora silenziosamente (mai un errore se presenti, semplicemente non
finiscono da nessuna parte in questo tool).
"""
import uuid
from datetime import datetime, timezone

GAMETORA_APP_FIELDS = {"app": "gametora", "game": "umamusume", "type": "collection", "version": 4}


def _id_to_tid_map(spark_list: list) -> dict:
    return {s["id"]: s["tid"] for s in spark_list if s.get("tid")}


def _tid_to_entry_map(spark_list: list) -> dict:
    return {s["tid"]: s for s in spark_list if s.get("tid")}


def _sparks_to_pairs(sparks: list, id_to_tid: dict) -> list:
    """[{'spark_id':..,'stars':..}] -> [[tid,stars],...] (formato Gametora),
    scartando quelle senza un tid noto -- mai un tid inventato."""
    pairs = []
    for s in sparks:
        tid = id_to_tid.get(s["spark_id"])
        if tid:
            pairs.append([tid, s["stars"]])
    return pairs


def _pairs_to_sparks(pairs: list, tid_to_entry: dict) -> list:
    """Inverso di _sparks_to_pairs -- scarta le coppie con un tid sconosciuto
    (spark non nel nostro catalogo aggiornato, mai un id/nome inventato)."""
    sparks = []
    for tid, stars in pairs:
        entry = tid_to_entry.get(tid)
        if entry:
            sparks.append({"spark_id": entry["id"], "name_en": entry["name_en"], "stars": stars})
    return sparks


def _empty_sparks_bucket(race_pairs: list, skill_pairs: list) -> list:
    return [[0, 0], [0, 0], 0, race_pairs, skill_pairs, [], []]


def _sub_veteran_to_legacy(sub_veteran: dict, char_tid_by_id: dict, race_id_to_tid: dict, skill_id_to_tid: dict):
    """Un genitore noto (veterans.py: {character, white_sparks, race_sparks})
    -> voce Legacy dell'export, o None se il suo personaggio non ha un tid
    noto (si esporta comunque il resto del veterano, non si blocca tutto)."""
    tid = char_tid_by_id.get(sub_veteran["character"])
    if tid is None:
        return None
    race_pairs = _sparks_to_pairs(sub_veteran["race_sparks"], race_id_to_tid)
    skill_pairs = _sparks_to_pairs(sub_veteran["white_sparks"], skill_id_to_tid)
    return [tid, None, _empty_sparks_bucket(race_pairs, skill_pairs), []]


def veteran_to_gametora_array(veteran: dict, char_tid_by_id: dict, race_id_to_tid: dict,
                               skill_id_to_tid: dict, now_ms: int):
    """Converte UN veterano nell'array posizionale a 11 elementi dell'export
    Gametora. Ritorna None se il personaggio del veterano STESSO non ha un
    tid noto (mai un abbinamento indovinato) -- il chiamante decide come
    segnalarlo (vedi build_gametora_export)."""
    char_tid = char_tid_by_id.get(veteran["character"])
    if char_tid is None:
        return None

    race_pairs = _sparks_to_pairs(veteran["race_sparks"], race_id_to_tid)
    skill_pairs = _sparks_to_pairs(veteran["white_sparks"], skill_id_to_tid)
    legacies = [
        _sub_veteran_to_legacy(veteran[slot], char_tid_by_id, race_id_to_tid, skill_id_to_tid)
        if veteran.get(slot) else None
        for slot in ("parent1", "parent2")
    ]

    return [
        1, char_tid, None, None, [0, 0, 0, 0, 0], None, [],
        _empty_sparks_bucket(race_pairs, skill_pairs),
        legacies,
        [],
        [[], [], None, now_ms, now_ms],
    ]


def build_gametora_export(veterans: list, char_tid_by_id: dict, race_list: list, skill_list: list,
                           server: str = "en") -> tuple:
    """
    Costruisce il payload di backup completo (stesso formato del "Copy
    JSON" di Gametora, Backup > Veterans > Export) per TUTTI i veterani
    passati. char_tid_by_id: dict[nostro_id] -> tid Gametora (l'INVERSO di
    data_updater.get_gametora_tid_map, che va nell'altro verso -- vedi
    app.py per la costruzione).

    Ritorna (payload, skipped_names): skipped_names = i nomi dei veterani
    il cui personaggio non ha un tid Gametora noto (es. non ancora uscito
    su Global) -- mai esportati con un abbinamento indovinato.
    """
    race_id_to_tid = _id_to_tid_map(race_list)
    skill_id_to_tid = _id_to_tid_map(skill_list)
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    veterans_out = {}
    skipped_names = []
    for v in veterans:
        array = veteran_to_gametora_array(v, char_tid_by_id, race_id_to_tid, skill_id_to_tid, now_ms)
        if array is None:
            skipped_names.append(v["name"])
            continue
        veterans_out[f"v_{uuid.uuid4().hex}"] = array

    payload = {
        **GAMETORA_APP_FIELDS,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "servers": {server: {"veterans": veterans_out}},
    }
    return payload, skipped_names


def _legacy_to_sub_veteran(entry, char_id_by_tid: dict, race_tid_to_entry: dict, skill_tid_to_entry: dict):
    """Inverso di _sub_veteran_to_legacy. entry = None o [tid, punteggio,
    sparks_bucket, ...]. Ritorna None se assente o se il personaggio non ha
    un abbinamento noto (il resto del veterano viene comunque importato)."""
    if entry is None:
        return None
    character = char_id_by_tid.get(entry[0])
    if character is None:
        return None
    bucket = entry[2]
    return {
        "character": character,
        "race_sparks": _pairs_to_sparks(bucket[3], race_tid_to_entry),
        "white_sparks": _pairs_to_sparks(bucket[4], skill_tid_to_entry),
    }


def gametora_array_to_veteran(array: list, char_id_by_tid: dict, race_tid_to_entry: dict, skill_tid_to_entry: dict):
    """
    Converte l'array posizionale di un veterano Gametora nella forma usata
    da questo tool (senza 'id'/'name', assegnati dal chiamante -- vedi
    veterans.import_veterans). Ritorna None se il personaggio del veterano
    STESSO non ha un abbinamento noto (mai un abbinamento indovinato, tutto
    il veterano viene scartato in quel caso); un genitore non mappabile
    viene invece semplicemente omesso (None), non blocca l'import del resto.
    """
    character = char_id_by_tid.get(array[1])
    if character is None:
        return None
    bucket = array[7]
    legacy1, legacy2 = array[8]
    return {
        "character": character,
        "race_sparks": _pairs_to_sparks(bucket[3], race_tid_to_entry),
        "white_sparks": _pairs_to_sparks(bucket[4], skill_tid_to_entry),
        "parent1": _legacy_to_sub_veteran(legacy1, char_id_by_tid, race_tid_to_entry, skill_tid_to_entry),
        "parent2": _legacy_to_sub_veteran(legacy2, char_id_by_tid, race_tid_to_entry, skill_tid_to_entry),
    }


def parse_gametora_import(payload: dict, char_id_by_tid: dict, race_list: list, skill_list: list,
                           server: str = "en") -> tuple:
    """
    Legge un backup Gametora (stesso formato di build_gametora_export) e
    ritorna (veterans, skipped_count): veterans = lista di dict pronti per
    veterans.import_veterans (senza 'id'/'name'). skipped_count = quanti
    veterani NON sono stati importati perche' il loro personaggio non ha un
    abbinamento noto -- mai un abbinamento indovinato.

    'server': quale server dentro payload["servers"] leggere (default "en",
    coerente col resto del tool) -- se assente, usa il primo disponibile
    (un utente non-EN potrebbe esportare sotto un'altra chiave).
    """
    race_tid_to_entry = _tid_to_entry_map(race_list)
    skill_tid_to_entry = _tid_to_entry_map(skill_list)

    servers = payload.get("servers") or {}
    server_data = servers.get(server) or next(iter(servers.values()), {})
    veterans_raw = (server_data or {}).get("veterans") or {}

    result = []
    skipped_count = 0
    for array in veterans_raw.values():
        parsed = gametora_array_to_veteran(array, char_id_by_tid, race_tid_to_entry, skill_tid_to_entry)
        if parsed is None:
            skipped_count += 1
            continue
        result.append(parsed)
    return result, skipped_count
