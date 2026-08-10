# -*- coding: utf-8 -*-
"""
Independent training: probabilita' di vincere UNA gara data l'aptitude del
personaggio (non la soglia binaria si'/no usata altrove nel tool) e la
fatica da turni di gara consecutivi (nessun turno di allenamento in mezzo).
Diverso da affinity.py/cycle_analysis.py: qui il risultato NON entra MAI nel
calcolo dell'affinita' (richiesta esplicita dell'utente -- calcolare
l'affinita' massima richiederebbe la probabilita' CONGIUNTA di vittoria di
due personaggi, un problema diverso e molto piu' complesso). E' un calcolo
AGGIUNTIVO, mai una sostituzione: le modalita' esistenti (career/mant)
restano identiche, questo modulo produce solo un'indicazione in piu' per il
figlio di ogni ciclo in Top-4/Rental loop.

Formula (fonte: tabella fornita dall'utente, verificata su tutte le 49
celle + le 4 soglie di fatica -- vedi self-check in fondo al file):
    P(vittoria) = clamp(BaseRate(voto_superficie, voto_distanza)
                         - PenalitaFatica(posizione_in_serie), 0, 100)
    BaseRate(v1, v2) = clamp(110 - 10*(indice(v1) + indice(v2)), 0, 110)
    indice: S/A -> 0, B -> 1, C -> 2, D -> 3, E -> 4, F -> 5, G -> 6
    PenalitaFatica: posizione 1-2 -> 0, 3 -> 10, 4 -> 25, 5 -> 35, 6+ -> 50

Selezione delle gare (CONFERMATO dall'utente, non e' piu' solo "le stesse
gare gia' raggiungibili altrove"): TUTTE le gare del dataset sono candidate,
non solo quelle che superano la soglia binaria MIN_APTITUDE -- e' proprio il
punto della feature (una gara che oggi sarebbe "impossibile" per aptitude
insufficiente puo' avere comunque una chance reale qui). I conflitti di
turno si risolvono con affinity.resolve_achievable (estesa con slot_key/
return_slots per questo scopo, comportamento di default invariato per tutti
gli altri chiamanti), passandole l'INTERO elenco gare come candidate invece
del sottoinsieme filtrato per aptitude.

Rotazione consigliata: si cammina sulle gare (ordinate per turno) tenendo il
conteggio della serie di turni consecutivi. Le obbligatorie restano SEMPRE
nella serie (il gioco le forza), qualunque sia la loro probabilita'. Le
flessibili vengono scartate dalla rotazione consigliata se la probabilita'
(gia' scontata della fatica accumulata finora) e' sotto la soglia
regolabile (config.MIN_INDEPENDENT_TRAINING_PROBABILITY di default, 1-100)
-- scartarle azzera la serie per le gare successive, esattamente come un
turno di allenamento vero. Le gare scartate restano visibili in tabella con
la loro probabilita' reale, solo marcate "non consigliata".

Scelta dell'anno per le gare ricorrenti (es. Yasuda Kinen, vincibile sia
all'anno 2 sia all'anno 3): RICERCA ESAUSTIVA su tutte le combinazioni
possibili (segnalato dall'utente con un caso concreto -- una prima euristica
"allontana dalla mediana" sceglieva un anno arbitrario che affollava turni
consecutivi senza motivo, quando l'altro anno avrebbe spezzato la serie e
salvato le gare successive). Le gare ricorrenti nel dataset sono poche
(14 su 34, verificato ~1-2ms/combinazione), quindi si provano TUTTE le
combinazioni di anno per le gare ricorrenti non obbligatorie di questo
personaggio e si tiene quella che massimizza il numero di gare consigliate
(a parita', la somma delle probabilita' delle consigliate) -- non
un'euristica, il vero massimo per costruzione.
"""
import itertools

from affinity import resolve_achievable

GRADE_TIER_INDEX = {"S": 0, "A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6}

FATIGUE_PENALTY_BY_STREAK = {1: 0, 2: 0, 3: 10, 4: 25, 5: 35}
FATIGUE_PENALTY_MAX = 50  # 6+ turni di fila


def base_win_rate(surface_grade: str, distance_grade: str) -> float:
    """Percentuale (0-110) di vincere una gara in base ai due voti aptitude
    coinvolti, PRIMA della penalita' da gare consecutive."""
    idx = GRADE_TIER_INDEX[surface_grade] + GRADE_TIER_INDEX[distance_grade]
    return max(0.0, min(110.0, 110.0 - 10.0 * idx))


def fatigue_penalty(streak_position: int) -> float:
    """Penalita' (punti percentuali) da sottrarre in base a QUANTE gare di
    fila (turni consecutivi, nessun allenamento in mezzo) sono state corse
    fino a questa compresa. streak_position=1 -> prima gara della serie."""
    if streak_position >= 6:
        return FATIGUE_PENALTY_MAX
    return FATIGUE_PENALTY_BY_STREAK.get(streak_position, FATIGUE_PENALTY_MAX)


def race_win_probability(surface_grade: str, distance_grade: str, streak_position: int) -> float:
    """Probabilita' finale (0-100) di vincere una gara -- combina le due
    funzioni sopra e cappa il risultato per la visualizzazione."""
    rate = base_win_rate(surface_grade, distance_grade) - fatigue_penalty(streak_position)
    return max(0.0, min(100.0, rate))


def _slot_to_occurrence_map(races: dict) -> dict:
    """slot -> (turn_number, year), costruita una volta da TUTTE le gare
    (i turni/slot sono posizioni di calendario condivise tra gare diverse)."""
    return {
        o["slot"]: (o["turn_number"], o.get("year"))
        for race in races.values() for o in race["occurrences"]
    }


def _preference_slot_key(races: dict, preferred_year_by_race: dict) -> "callable":
    """
    Chiave d'ordinamento (race_id, slot) -> le occorrenze dell'anno preferito
    per QUELLA gara (se presente in preferred_year_by_race) vengono provate
    prima dal matching. L'anno si legge dallo slot stesso (es. 'y2_m06_d1'
    -> anno 2), non serve altro. Gare assenti da preferred_year_by_race
    (obbligatorie, o a occorrenza singola) non hanno preferenza (ordine
    invariato).
    """
    def key(race_id, slot):
        preferred_year = preferred_year_by_race.get(race_id)
        if preferred_year is None:
            return 0
        slot_year = int(slot.split("_")[0][1:])  # 'y2_m06_d1' -> 2
        return 0 if slot_year == preferred_year else 1

    return key


def _base_rate_priority_key(character: str, races: dict, aptitudes: dict) -> "callable":
    """
    Ordine di elaborazione delle gare nel matching (affinity.resolve_achievable):
    quando piu' gare si contendono lo stesso turno, viene privilegiata quella
    per cui il personaggio ha il base-rate (senza fatica) piu' alto -- una
    stima context-free ragionevole, dato che la fatica dipende da QUALI gare
    finiscono per essere incluse, non ancora note in questa fase.
    """
    apt = aptitudes.get(character, {})

    def key(race_id):
        race_info = races[race_id]
        surface_grade = apt.get(race_info["surface"], "G")
        distance_grade = apt.get(race_info["distance"], "G")
        return (-base_win_rate(surface_grade, distance_grade), race_id)

    return key


def _mandatory_race_ids(character: str, calendar: dict, mode: str) -> set:
    if mode == "mant":
        return set()
    return {e["race"] for e in calendar.get(character, []) if not e["is_blocked"]}


def _movable_race_ids(races: dict, mandatory_race_ids: set) -> list:
    """
    Gare con piu' di un'occorrenza E non obbligatorie per questo personaggio
    (le obbligatorie hanno l'anno gia' fissato dal calendario, nessuna
    scelta) -- sono le uniche su cui vale la pena provare combinazioni
    diverse di anno.
    """
    return sorted(
        rid for rid, r in races.items()
        if len(r["occurrences"]) > 1 and rid not in mandatory_race_ids
    )


def _year_options(races: dict, race_id: str) -> list:
    return sorted({o["year"] for o in races[race_id]["occurrences"]})


def _evaluate_schedule(character: str, races: dict, aptitudes: dict, calendar: dict, mode: str,
                        threshold: float, mandatory_race_ids: set, preferred_year_by_race: dict) -> list:
    """
    Calcola il calendario REALE (tutte le gare, conflitti di turno risolti
    secondo preferred_year_by_race per le ricorrenti) e la probabilita' di
    vittoria/serie per UNA specifica combinazione di scelte anno. Stessa
    logica di cammino-e-classificazione per entrambe le chiamate da
    compute_race_probabilities (ricerca esaustiva + risultato finale) --
    nessuna duplicazione, questa e' l'unica funzione che la implementa.
    """
    all_race_ids = list(races.keys())
    slot_key = _preference_slot_key(races, preferred_year_by_race)
    _, slot_owner = resolve_achievable(
        character, all_race_ids, races, aptitudes, calendar, mode,
        priority_key=_base_rate_priority_key(character, races, aptitudes),
        slot_key=slot_key, return_slots=True,
    )
    slot_to_occurrence = _slot_to_occurrence_map(races)

    schedule = []
    for slot, race_id in slot_owner.items():
        turn_number, year = slot_to_occurrence[slot]
        schedule.append({
            "race": race_id, "turn_number": turn_number, "year": year,
            "is_mandatory": race_id in mandatory_race_ids,
        })
    schedule.sort(key=lambda e: e["turn_number"])

    apt = aptitudes.get(character, {})
    results = []
    streak = 0
    previous_turn = None
    for entry in schedule:
        turn_number = entry["turn_number"]
        continues_streak = previous_turn is not None and turn_number - previous_turn == 1
        candidate_streak = streak + 1 if continues_streak else 1

        race_info = races[entry["race"]]
        surface_grade = apt.get(race_info["surface"], "G")
        distance_grade = apt.get(race_info["distance"], "G")
        probability = race_win_probability(surface_grade, distance_grade, candidate_streak)

        if entry["is_mandatory"] or probability >= threshold:
            streak = candidate_streak
            previous_turn = turn_number
            recommended = True
        else:
            # scartata: non avanza la serie, e la "libera" per le prossime
            # gare (stesso effetto di un turno di allenamento vero).
            recommended = False

        results.append({
            "race": entry["race"],
            "turn_number": turn_number,
            "year": entry["year"],
            "is_mandatory": entry["is_mandatory"],
            "streak_position": candidate_streak,
            "probability": probability,
            "recommended": recommended,
        })
    return results


def _schedule_score(results: list) -> tuple:
    """(numero di gare consigliate, somma delle loro probabilita') -- il
    secondo termine e' solo un tie-break tra combinazioni equivalenti sul
    primo, mai l'obiettivo primario."""
    recommended = [r for r in results if r["recommended"]]
    return (len(recommended), sum(r["probability"] for r in recommended))


def compute_race_probabilities(character: str, races: dict, aptitudes: dict, calendar: dict,
                                mode: str, threshold: float) -> list:
    """
    Per ciascuna gara del calendario independent-training del personaggio, la
    probabilita' di vincerla in base all'aptitude e alla posizione nella
    serie di turni consecutivi (si azzera ad ogni gap di turno, e ad ogni
    gara flessibile scartata per soglia -- entrambi equivalgono a un turno
    di allenamento). Le obbligatorie restano sempre nella serie qualunque
    sia la loro probabilita' (il gioco le forza); le flessibili vengono
    scartate dalla rotazione consigliata (`recommended=False`) se la
    probabilita' e' sotto `threshold`, ma restano comunque nel risultato,
    solo marcate come non consigliate.

    L'ANNO delle gare ricorrenti (es. Yasuda Kinen, vincibile sia all'anno 2
    sia all'anno 3) viene scelto per RICERCA ESAUSTIVA su tutte le
    combinazioni possibili, massimizzando il numero di gare consigliate
    (vedi _schedule_score) -- spostare una ricorrente puo' rompere una serie
    di turni consecutivi e salvare le gare successive dalla penalita' di
    fatica (segnalato dall'utente con un caso concreto: un'euristica
    "distanza dalla mediana" non lo garantiva). Le gare ricorrenti nel
    dataset sono poche (14 su 34): anche nel caso peggiore (tutte non
    obbligatorie per questo personaggio) sono ~2^14 combinazioni, ciascuna
    economica da valutare -- nessun bisogno di un'euristica approssimata.
    """
    mandatory_race_ids = _mandatory_race_ids(character, calendar, mode)
    movable_race_ids = _movable_race_ids(races, mandatory_race_ids)

    best_results = None
    best_score = None
    for combo in itertools.product(*(_year_options(races, rid) for rid in movable_race_ids)):
        preferred_year_by_race = dict(zip(movable_race_ids, combo))
        results = _evaluate_schedule(
            character, races, aptitudes, calendar, mode, threshold,
            mandatory_race_ids, preferred_year_by_race,
        )
        score = _schedule_score(results)
        if best_score is None or score > best_score:
            best_score = score
            best_results = results
    return best_results


if __name__ == "__main__":
    # Formula base: verifica tutte le 49 celle della tabella fornita
    # dall'utente (S e A nello stesso tier, indice 0).
    tiers = ["S", "B", "C", "D", "E", "F", "G"]
    expected = [
        [110, 100, 90, 80, 70, 60, 50],
        [100, 90, 80, 70, 60, 50, 40],
        [90, 80, 70, 60, 50, 40, 30],
        [80, 70, 60, 50, 40, 30, 20],
        [70, 60, 50, 40, 30, 20, 10],
        [60, 50, 40, 30, 20, 10, 0],
        [50, 40, 30, 20, 10, 0, 0],
    ]
    for i, g1 in enumerate(tiers):
        for j, g2 in enumerate(tiers):
            assert base_win_rate(g1, g2) == expected[i][j], (g1, g2, base_win_rate(g1, g2))
    assert base_win_rate("A", "A") == 110  # A e' nello stesso tier di S

    assert [fatigue_penalty(p) for p in range(1, 8)] == [0, 0, 10, 25, 35, 50, 50]

    assert race_win_probability("S", "S", 1) == 100  # cap a 100, non 110
    assert race_win_probability("G", "G", 6) == 0
    assert race_win_probability("S", "B", 5) == 65  # 100 - 35, nessun cap coinvolto

    print("independent_training.py: self-check OK")
