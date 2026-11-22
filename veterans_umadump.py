# -*- coding: utf-8 -*-
"""
Lettura dei veterani esportati da umadump (trained_chara_data.json) nel
formato dei veterani del tool (veterans.py). Solo funzioni pure: ricevono il
JSON gia' letto e i dati di traduzione, nessun accesso a rete o disco (cosi'
la stessa logica si porta tale e quale in un futuro sito statico).

Formato umadump (verificato sul file reale dell'utente, 250 veterani,
2026-11-21): una LISTA di veterani; un singolo veterano e' lo stesso oggetto
da solo. Campi usati:
  viewer_id, trained_chara_id   chi lo possiede + id nel gioco (chiave stabile)
  card_id                       carta del personaggio (data/card_characters.json)
  rank_score, rank, create_time, is_locked, memo
  factor_info_array             [{factor_id}] tutte le spark del veterano
  win_saddle_id_array           selle vinte (data/saddle_races.json -> G1)
  succession_chara_array        6 antenati: position_id 10/20 = genitori,
                                11/12 e 21/22 = i loro genitori (non usati:
                                il modello del tool si ferma ai genitori)

factor_id = id della spark nei cataloghi Gametora * 100 + stelle (es.
2001602 = white spark 20016 a 2 stelle, 203 = blue 2 (Stamina) a 3 stelle,
10460102 = green della carta 104601 a 2 stelle). Le spark di scenario sono
ignorate (non richieste).

Non importati (scelta dell'utente, 2026-11-21): statistiche, attitudini,
skill, support card, gare corse -- servono al veterano in gara, non come
genitore.
"""
from display_names import format_character_name

PARENT_POSITIONS = {10: "parent1", 20: "parent2"}
SPARK_KINDS = ("white", "race", "blue", "pink", "green")


def _sparks(factors: list, catalogs: dict) -> dict:
    """factor_info_array -> {white_sparks: [...], race_sparks: [...], ...},
    ogni spark {spark_id, name_en, stars} come nel resto del tool. Una spark
    che non e' in nessun catalogo (scenario, o una nuova non ancora
    scaricata) viene saltata."""
    result = {f"{kind}_sparks": [] for kind in SPARK_KINDS}
    for factor in factors or []:
        factor_id = factor.get("factor_id")
        if not isinstance(factor_id, int):
            continue
        spark_id, stars = str(factor_id // 100), factor_id % 10
        for kind in SPARK_KINDS:
            entry = catalogs[kind].get(spark_id)
            if entry:
                result[f"{kind}_sparks"].append({"spark_id": spark_id, "name_en": entry["name_en"], "stars": stars})
                break
    return result


def _won_races(saddles: list, saddle_races: dict) -> list:
    """Selle vinte -> nostre G1 vinte (ordinate, senza doppioni; le selle
    di corone e gare non G1 non hanno una voce e vengono ignorate)."""
    return sorted({saddle_races[str(s)] for s in saddles or [] if str(s) in saddle_races})


def parse_umadump(data, card_characters: dict, saddle_races: dict, catalogs: dict) -> tuple:
    """
    data: il JSON di umadump -- una lista (inventario completo) o un singolo
    veterano. catalogs: {kind: {spark_id: voce del catalogo}} per
    white/race/blue/pink/green.

    Ritorna (veterani, saltati, completo):
      veterani: [{character, memo, source, rank_score, rank, created_at,
                  is_locked, won_races, *_sparks, parent1, parent2}]
      saltati: veterani il cui personaggio non e' riconosciuto (card_id)
      completo: True se il file era una lista (inventario da sincronizzare)
    Solleva ValueError se il formato non e' quello di umadump.
    """
    full = isinstance(data, list)
    items = data if full else [data]
    if not items or not all(isinstance(v, dict) and "trained_chara_id" in v and "card_id" in v for v in items):
        raise ValueError("Il file non sembra un export di umadump (trained_chara_data.json).")

    veterans, skipped = [], []
    for item in items:
        character = card_characters.get(str(item["card_id"]))
        if not character:
            skipped.append(item["card_id"])
            continue
        veteran = {
            "character": character,
            "card_id": item["card_id"],  # costume vero, solo per i ritratti (i calcoli usano 'character')
            "memo": (item.get("memo") or "").strip(),
            "source": {"type": "umadump", "viewer_id": item.get("viewer_id"),
                       "trained_chara_id": item["trained_chara_id"]},
            "rank_score": item.get("rank_score"),
            "rank": item.get("rank"),
            "created_at": item.get("create_time"),
            "is_locked": bool(item.get("is_locked")),
            "won_races": _won_races(item.get("win_saddle_id_array"), saddle_races),
            **_sparks(item.get("factor_info_array"), catalogs),
            "parent1": None, "parent2": None,
        }
        for ancestor in item.get("succession_chara_array") or []:
            slot = PARENT_POSITIONS.get(ancestor.get("position_id"))
            parent_character = card_characters.get(str(ancestor.get("card_id")))
            if slot and parent_character:
                veteran[slot] = {
                    "character": parent_character,
                    "card_id": ancestor.get("card_id"),  # costume vero, solo per i ritratti
                    "won_races": _won_races(ancestor.get("win_saddle_id_array"), saddle_races),
                    **_sparks(ancestor.get("factor_info_array"), catalogs),
                }
        veterans.append(veteran)
    return veterans, skipped, full


def default_name(character: str, memo: str, same_character_count: int) -> str:
    """Nome iniziale (scelta dell'utente): "Personaggio — memo" se nel gioco
    c'e' un memo, altrimenti "Personaggio #N" come i veterani creati a mano.
    Rinominabile nel tool."""
    if memo:
        return f"{format_character_name(character)} — {memo}"
    return f"{format_character_name(character)} #{same_character_count + 1}"


if __name__ == "__main__":
    catalogs = {
        "white": {"20016": {"name_en": "Corner Recovery"}}, "race": {"10001": {"name_en": "February S."}},
        "blue": {"2": {"name_en": "Stamina"}}, "pink": {"32": {"name_en": "Mile"}},
        "green": {"104601": {"name_en": "Unique"}},
    }
    vet = {
        "viewer_id": 1, "trained_chara_id": 7, "card_id": 104601, "rank_score": 100, "rank": 13,
        "create_time": "2025-08-28 14:00:13", "is_locked": 1, "memo": " x ",
        "factor_info_array": [{"factor_id": 203}, {"factor_id": 3202}, {"factor_id": 2001602},
                              {"factor_id": 1000102}, {"factor_id": 10460102}, {"factor_id": 3000101}],
        "win_saddle_id_array": [9, 30],
        "succession_chara_array": [
            {"position_id": 10, "card_id": 104601, "factor_info_array": [{"factor_id": 2001601}],
             "win_saddle_id_array": [30]},
            {"position_id": 20, "card_id": 999999, "factor_info_array": [], "win_saddle_id_array": []},
            {"position_id": 11, "card_id": 104601, "factor_info_array": [], "win_saddle_id_array": []},
        ],
    }
    cards = {"104601": "smart_falcon"}
    veterans, skipped, full = parse_umadump([vet, {**vet, "card_id": 1}], cards, {"30": "february_stakes"}, catalogs)
    assert full and skipped == [1] and len(veterans) == 1, (skipped, veterans)
    v = veterans[0]
    assert v["blue_sparks"] == [{"spark_id": "2", "name_en": "Stamina", "stars": 3}]
    assert [s["stars"] for s in v["pink_sparks"]] == [2] and v["white_sparks"][0]["spark_id"] == "20016"
    assert v["race_sparks"][0]["stars"] == 2 and v["green_sparks"][0]["spark_id"] == "104601"
    assert v["won_races"] == ["february_stakes"] and v["memo"] == "x" and v["is_locked"] is True
    assert v["parent1"]["character"] == "smart_falcon" and v["parent1"]["won_races"] == ["february_stakes"]
    assert v["card_id"] == 104601 and v["parent1"]["card_id"] == 104601
    assert v["parent2"] is None  # personaggio non riconosciuto: genitore ignoto, non inventato
    assert parse_umadump(vet, cards, {}, catalogs)[2] is False
    try:
        parse_umadump({"foo": 1}, cards, {}, catalogs)
        raise AssertionError("formato sbagliato accettato")
    except ValueError:
        pass
    print("veterans_umadump.py: self-check OK")
