# -*- coding: utf-8 -*-
"""
Costruisce la "timeline delle carriere": una matrice gara x personaggio per un
gruppo fisso (tipicamente i 5 di un loop, o figlio+top4 dell'esplorazione a un
salto), pensata per il confronto visivo nel pannello destro della UI.

Per ogni coppia (personaggio, gara) lo stato e' uno tra:
  - "obbligatoria": la gara e' quella obbligatoria del personaggio in quello slot.
  - "impossibile": o lo slot di quella gara e' occupato da UN'ALTRA obbligatoria
    (reale o 'blocked:') dello stesso personaggio, oppure lo slot e' libero e
    l'aptitude basterebbe ma la gara PERDE la competizione per un turno conteso
    con altre gare candidate del personaggio (matching gara/turno fisico, vedi
    affinity.resolve_achievable: es. 2 delle 4 gare JBC quando tutte e 4 sono
    candidate ma esistono solo 2 turni in cui correrle) -- in entrambi i casi
    non puo' correrla in nessun caso.
  - "raggiungibile": slot libero, aptitude sufficiente, E la gara ha
    effettivamente un turno assegnato nella risoluzione dei conflitti. Se anche
    almeno un ALTRO personaggio del gruppo la raggiunge (a sua volta risolta),
    viene marcata anche come "condivisa" (candidato reale per il bonus di
    affinita').
  - "aptitude": slot libero ma aptitude insufficiente -- raggiungibile solo
    migliorando l'aptitude (fuori scope per la v1/v2 del tool, e' materiale
    per la v3 sulle simulazioni di spark). Non compete mai per un turno (non
    verrebbe comunque scelta finche' l'aptitude non basta).

Nota: se una gara e' l'obbligatoria del personaggio ma la sua aptitude non la
soddisfa, resta comunque "obbligatoria" (il gioco lo forza a correrla lo
stesso) -- viene pero' marcata separatamente come "non vincibile" perche' non
conta ai fini del bonus di affinita' (coerente con la regola gia' stabilita
per Haru Urara/Arima Kinen).
"""
from affinity import race_is_winnable, slot_occupation_map
from cycle_analysis import resolve_group_achievable
from display_names import format_race_name


def race_status_for_character(character, race_id, races, aptitudes, calendar, mode, resolved_achievable):
    """
    Ritorna un dict {status, winnable} per una singola coppia (personaggio, gara).
    status in {"obbligatoria", "impossibile", "raggiungibile", "aptitude"}.
    winnable: True se l'aptitude e' sufficiente per quella gara (rilevante
    soprattutto per lo stato 'obbligatoria', che puo' essere non vincibile).

    resolved_achievable: insieme delle gare DAVVERO raggiungibili per questo
    personaggio DOPO la risoluzione group-aware dei conflitti di turno
    (resolve_group_achievable) -- usato per riclassificare a "impossibile" le
    gare che, pur avendo slot libero e aptitude sufficiente, perdono la
    competizione per un turno conteso.

    Una gara ricorrente (piu' occorrenze, una per anno) viene valutata su TUTTE
    le occorrenze: se anche una sola e' la sua obbligatoria, lo stato e'
    "obbligatoria"; altrimenti se almeno una e' libera, lo stato dipende dalla
    risoluzione dei conflitti (resolved_achievable); solo se OGNI occorrenza e'
    bloccata da un'altra obbligatoria, lo stato e' "impossibile" a priori.
    """
    winnable = race_is_winnable(character, race_id, races, aptitudes)

    if mode == "mant":
        # nessun vincolo di calendario obbligatorio, ma il matching gara/turno
        # fisico resta valido (un personaggio corre comunque un turno alla volta).
        if not winnable:
            return {"status": "aptitude", "winnable": winnable}
        status = "raggiungibile" if race_id in resolved_achievable else "impossibile"
        return {"status": status, "winnable": winnable}

    occupation = slot_occupation_map(character, calendar)
    occupants = [occupation.get(o["slot"]) for o in races[race_id]["occurrences"]]

    if race_id in occupants:
        return {"status": "obbligatoria", "winnable": winnable}
    if any(o is None for o in occupants):
        if not winnable:
            return {"status": "aptitude", "winnable": winnable}
        status = "raggiungibile" if race_id in resolved_achievable else "impossibile"
        return {"status": status, "winnable": winnable}
    return {"status": "impossibile", "winnable": False}


def build_calendar_matrix(group_members, races, aptitudes, calendar, mode):
    """
    Ritorna una lista di righe (una per gara, ordinate per turn_number), ognuna:
      {
        "race": race_id, "turn_number": int, "slot": str,
        "surface": str, "distance": str,
        "cells": {personaggio: {"status": ..., "winnable": ..., "shared": bool}}
      }
    "shared" e' True solo per celle "raggiungibile" quando almeno un altro
    personaggio del gruppo la raggiunge a sua volta (vincolo di calendario,
    aptitude E matching di turno propri di quell'altro personaggio, non solo
    lo stesso status grezzo).
    """
    ordered_races = sorted(races.keys(), key=lambda r: races[r]["turn_number"])

    # risoluzione group-aware dei conflitti di turno, una volta per l'intero
    # gruppo (vedi cycle_analysis.resolve_group_achievable)
    resolved_per_member = resolve_group_achievable(group_members, races, aptitudes, calendar, mode)

    # precalcolo stato per ogni (personaggio, gara), cosi' il controllo di
    # condivisione non ricalcola nulla
    raw = {
        race_id: {
            char: race_status_for_character(
                char, race_id, races, aptitudes, calendar, mode, resolved_per_member[char],
            )
            for char in group_members
        }
        for race_id in ordered_races
    }

    rows = []
    for race_id in ordered_races:
        info = races[race_id]
        cells = {}
        for char in group_members:
            entry = raw[race_id][char]
            shared = False
            if entry["status"] == "raggiungibile":
                shared = any(
                    other != char and raw[race_id][other]["status"] == "raggiungibile"
                    for other in group_members
                )
            cells[char] = {
                "status": entry["status"],
                "winnable": entry["winnable"],
                "shared": shared,
            }
        rows.append({
            "race": race_id,
            "label": _race_label(race_id, info),
            "turn_number": info["turn_number"],
            "slot": info["slot"],
            "surface": info["surface"],
            "distance": info["distance"],
            "cells": cells,
        })
    return rows


def _race_label(race_id, info):
    """
    Nome visualizzato per la gara (formattato, vedi display_names.format_race_name),
    con anno/i e turno/i tra parentesi. Se la gara ricorre su piu' anni, mostra
    TUTTI gli anni e i TURNI corrispondenti (es. 'Arima Kinen (Y2, Y3) (T48, T72)'),
    non solo il primo come in una versione precedente -- cosi' resta chiaro che
    si puo' scegliere in quale dei due correrla, ed e' immediato vedere quali
    turni sono davvero in competizione con altre gare.
    """
    name = format_race_name(race_id)
    occurrences = info.get("occurrences") or []
    if len(occurrences) > 1:
        years_label = ", ".join(f"Y{o['year']}" for o in occurrences)
        turns_label = ", ".join(f"T{o['turn_number']}" for o in occurrences)
        return f"{name} ({years_label}) ({turns_label})"
    turn = info.get("turn_number")
    return f"{name} (T{turn})" if turn is not None else name
