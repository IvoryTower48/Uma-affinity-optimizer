# -*- coding: utf-8 -*-
"""
Funzioni di calcolo dell'affinita' tra due personaggi (varianti incluse):
  - base_affinity: dalla matrice di ID/pesi (richiede name_map slug -> nome giapponese)
  - achievable_races_for/resolve_achievable: raggiungibilita' gare dal calendario + soglie di aptitude
"""
from itertools import product

from config import GRADE_RANK


def meets_threshold(grade: str, min_grade: str) -> bool:
    """True se 'grade' e' pari o migliore di 'min_grade' (scala A..G, A = migliore)."""
    return GRADE_RANK.get(grade, len(GRADE_RANK)) <= GRADE_RANK[min_grade]


def race_is_winnable(character: str, race_id: str, races: dict, aptitudes: dict, min_aptitude: dict) -> bool:
    """
    True se il personaggio soddisfa le soglie minime di aptitude (superficie E distanza,
    date da min_aptitude -- di norma config.MIN_APTITUDE, ma regolabile per sessione)
    per poter considerare quella gara "vinta" ai fini dell'affinita'.
    """
    if character not in aptitudes:
        return False
    race_info = races[race_id]
    surface = race_info["surface"]
    distance = race_info["distance"]
    apt = aptitudes[character]
    return (
        meets_threshold(apt[surface], min_aptitude[surface])
        and meets_threshold(apt[distance], min_aptitude[distance])
    )


def slot_occupation_map(character: str, calendar: dict) -> dict:
    """
    Ritorna dict[slot] -> race_id occupante quello slot nel calendario obbligato del
    personaggio ('blocked:<slot>' incluso, marcato come '__blocked__' perche' non
    corrisponde a nessuna riga in races.xlsx). Un personaggio ha al massimo una
    entry per slot (non puo' correre due gare nello stesso turno).
    Le alternative degli obiettivi a scelta NON sono qui (nessuna occupa il
    turno finche' non viene scelta): vedi choice_groups/resolve_achievable.
    """
    occ = {}
    for e in calendar.get(character, []):
        if e.get("choice"):
            continue
        race_id = "__blocked__" if e["is_blocked"] else e["race"]
        occ[e["slot"]] = race_id
    return occ


def choice_groups(character: str, calendar: dict) -> list:
    """Obiettivi a scelta del personaggio: lista di gruppi, ognuno una lista
    di alternative (slot, race_id) -- race_id '__blocked__' per una gara non
    G1. In carriera se ne corre UNA per gruppo (vedi resolve_achievable)."""
    groups = {}
    for e in calendar.get(character, []):
        if e.get("choice"):
            race_id = "__blocked__" if e["is_blocked"] else e["race"]
            groups.setdefault(e["choice"], []).append((e["slot"], race_id))
    return [groups[k] for k in sorted(groups)]


def race_is_achievable(character: str, race_id: str, races: dict, aptitudes: dict,
                        occupation: dict, mode: str, min_aptitude: dict) -> bool:
    """
    True se il personaggio PUO' vincere questa gara (ai fini dell'affinita'):
      - deve sempre soddisfare le soglie di aptitude (superficie + distanza)
      - in mode='mant' non c'e' altro vincolo (nessuna carriera obbligata: si sceglie
        liberamente cosa correre in ogni turno)
      - in mode='career', basta che ALMENO UNA delle occorrenze della gara (una
        gara ricorrente come arima_kinen ha piu' occorrenze, una per anno) non
        sia occupata da UN'ALTRA entry obbligata (gara diversa o 'blocked:').
        Un vincolo obbligatorio in un anno non blocca quindi automaticamente
        questa gara se e' raggiungibile in un anno diverso.
    """
    if not race_is_winnable(character, race_id, races, aptitudes, min_aptitude):
        return False
    if mode == "mant":
        return True
    for occurrence in races[race_id]["occurrences"]:
        occupant = occupation.get(occurrence["slot"])
        if occupant is None or occupant == race_id:
            return True
    return False


def achievable_races_for(character: str, races: dict, aptitudes: dict,
                          calendar: dict, mode: str, min_aptitude: dict) -> set:
    """Precalcola l'insieme di gare (di races.xlsx) raggiungibili da un personaggio."""
    occupation = slot_occupation_map(character, calendar)
    return {
        race_id for race_id in races
        if race_is_achievable(character, race_id, races, aptitudes, occupation, mode, min_aptitude)
    }


def _character_used_slots(character: str, calendar: dict, mode: str) -> dict:
    """
    Slot gia' fissi (occupati da un'obbligatoria reale o 'blocked:') nel
    calendario del personaggio. In mode='mant' non c'e' alcun vincolo di
    calendario: nessuno slot e' pre-occupato (scelta libera ovunque).
    """
    if mode == "mant":
        return {}
    return slot_occupation_map(character, calendar)


def resolve_achievable(character: str, candidate_race_ids, races: dict, aptitudes: dict,
                        calendar: dict, mode: str, priority_key=None, slot_key=None,
                        return_slots: bool = False, return_choices: bool = False):
    """
    Dato un insieme di gare CANDIDATE per un singolo personaggio (gia' filtrate
    altrove per raggiungibilita' di base, es. l'intersezione con un altro
    personaggio in shared_wins, o l'intero achievable_races_for per la
    timeline), risolve i conflitti di TURNO FISICO (slot): un personaggio puo'
    vincere al massimo UNA gara per slot, quindi se piu' gare candidate
    competono per lo stesso slot (o insieme di slot, per le ricorrenti) solo
    alcune possono davvero contare come raggiungibili.

    Le gare che sono l'obbligatoria del personaggio in una delle loro
    occorrenze sono sempre GARANTITE (non competono, il gioco le forza
    comunque). Le restanti (flessibili) vengono assegnate con un vero
    ALGORITMO DI MATCHING BIPARTITO (Kuhn / augmenting path), NON con un
    semplice greedy "assegna al primo slot libero trovato": un greedy
    semplice puo' essere SUBOTTIMALE quando una gara ricorrente (piu'
    occorrenze/slot possibili) viene processata prima di una a occorrenza
    singola e le "ruba" l'unico slot disponibile, anche se la ricorrente
    avrebbe potuto usare tranquillamente un suo slot alternativo -- risultato:
    si perde una gara che sarebbe stata raggiungibile per davvero (bug
    segnalato dall'utente su un caso concreto: autumn_tenno_sho, con slot sia
    a turno 44 che a turno 68, occupava greedily il turno 44 anche quando
    libero era pure il 68, lasciando poi sia kikuka_sho che shuka_sho -- che
    hanno SOLO il turno 44 -- entrambe "impossibile", quando in realta' una
    delle due avrebbe potuto tranquillamente correre a 44 e autumn_tenno_sho
    a 68, per un totale di 2 gare raggiungibili invece di 1).
    Il matching con augmenting path GARANTISCE sempre il numero MASSIMO di
    gare assegnabili in totale (dimostrabile, indipendente dall'ordine di
    elaborazione); priority_key (default alfabetico su race_id, o group-aware
    nel contesto di un gruppo fisso) decide solo QUALI gare specifiche
    vengono scelte quando esistono piu' matching massimi equivalenti, non
    quante in totale.

    Ritorna il sottoinsieme di candidate_race_ids davvero raggiungibile (di
    default). Due parametri opzionali, additivi e retrocompatibili (default
    None/False => comportamento identico a prima per tutti i chiamanti
    esistenti):
    - slot_key: se dato, ordina le occorrenze di CIASCUNA gara (non solo
      l'ordine di elaborazione tra gare diverse, quello e' priority_key) --
      chiamata come slot_key(race_id, slot), cosi' la preferenza puo' variare
      per gara (usato dall'independent training per provare specifiche
      combinazioni di anno per le gare ricorrenti, vedi independent_training.py).
    - return_slots: se True, ritorna anche lo slot fisico assegnato a
      ciascuna gara raggiungibile (comprese le obbligatorie, il cui slot e'
      comunque noto a priori) come dict slot->race_id -- serve a chi ha
      bisogno del turn_number esatto (l'insieme raggiungibile da solo non
      lo dice), non solo del conteggio.
    - return_choices: se True, ritorna anche le alternative scelte per gli
      obiettivi a scelta, come dict slot->race_id ('__blocked__' per una non
      G1) -- serve alla timeline per mostrarle come "obbligatoria".

    Obiettivi a scelta (2026-11-21, richiesta dell'utente): se ne sceglie
    UNA alternativa per gruppo -- l'alternativa scelta occupa il suo turno
    (e, se G1 tra le candidate, e' una vittoria garantita); i turni delle
    alternative scartate restano liberi. Si provano tutte le combinazioni
    (pochissime in pratica, max 9) e si tiene quella con PIU' gare
    raggiungibili, a parita' quella con le gare di priorita' migliore (nel
    contesto di un gruppo: le piu' condivise, vedi
    cycle_analysis.compute_turn_priority). Chiamata UNA volta per personaggio
    per l'intero gruppo (resolve_group_achievable), la scelta e' quindi la
    stessa in TUTTE le coppie in cui compare -- es. Daiwa Scarlet che vince
    il Derby con 3 membri non puo' contare l'Oaks con il quarto.
    """
    priority_key = priority_key or (lambda r: r)
    groups = choice_groups(character, calendar) if mode != "mant" else []
    best = None
    for chosen in product(*groups):
        choice_occupation = dict(chosen)
        result = _resolve_with_occupation(character, candidate_race_ids, races, mode, priority_key, slot_key,
                                          {**_character_used_slots(character, calendar, mode), **choice_occupation})
        score = (-len(result[0]), sorted(priority_key(r) for r in result[0]))
        if best is None or score < best[0]:
            best = (score, result, choice_occupation)
    _, (achievable, slot_owner), choice_occupation = best
    extra = (slot_owner,) if return_slots else ()
    extra += (choice_occupation,) if return_choices else ()
    return (achievable, *extra) if extra else achievable


def _resolve_with_occupation(character, candidate_race_ids, races, mode, priority_key, slot_key, occupation):
    """Corpo del matching di resolve_achievable, con l'occupazione fissa dei
    turni (obbligatorie + alternative scelte) gia' decisa. Ritorna
    (achievable, slot_owner)."""
    used_slots_base = set(occupation.keys())

    guaranteed = set()
    free_slots_by_race = {}
    slot_owner = {}  # slot -> race_id assegnato (obbligatorie incluse, se return_slots)
    for race_id in candidate_race_ids:
        occ_slots = [o["slot"] for o in races[race_id]["occurrences"]]
        if slot_key is not None:
            occ_slots = sorted(occ_slots, key=lambda s: slot_key(race_id, s))
        if mode != "mant":
            matched_slot = next((s for s in occ_slots if occupation.get(s) == race_id), None)
            if matched_slot is not None:
                guaranteed.add(race_id)
                slot_owner[matched_slot] = race_id
                continue
        free_slots = [s for s in occ_slots if s not in used_slots_base]
        if free_slots:
            free_slots_by_race[race_id] = free_slots

    def try_augment(race_id, visited_slots):
        """DFS con augmenting path: prova ad assegnare race_id a uno dei suoi
        slot liberi, anche "spostando" chi lo occupa gia' su un suo slot
        alternativo, se esiste. Ritorna True se ci riesce."""
        for slot in free_slots_by_race[race_id]:
            if slot in visited_slots:
                continue
            visited_slots.add(slot)
            current_owner = slot_owner.get(slot)
            if current_owner is None or try_augment(current_owner, visited_slots):
                slot_owner[slot] = race_id
                return True
        return False

    for race_id in sorted(free_slots_by_race, key=priority_key):
        try_augment(race_id, set())

    achievable = guaranteed | set(slot_owner.values())
    return achievable, slot_owner


def base_affinity(char_a: str, char_b: str, name_map: dict,
                   character_ids: dict, id_weights: dict) -> int:
    """
    Affinita' di base tra due varianti: cerca il nome giapponese di ENTRAMBE tramite
    name_map (indicizzato per nome-variante completo, non per nome base -- due
    varianti della stessa umamusume avranno semplicemente lo stesso jp_name su righe
    diverse di character_info.csv), poi somma i pesi degli ID in comune.
    Ritorna 0 se sono la stessa umamusume di base (self-affinity, jp_a == jp_b), o
    se manca un mapping per una delle due (la componente di base viene ignorata =
    0, lo script segnala i mapping mancanti a parte, vedi main.py).
    """
    jp_a = name_map.get(char_a)
    jp_b = name_map.get(char_b)
    if jp_a is None or jp_b is None:
        return 0
    if jp_a == jp_b:
        return 0  # self-affinity (stesso personaggio base, varianti diverse)
    ids_a = character_ids.get(jp_a, set())
    ids_b = character_ids.get(jp_b, set())
    common = ids_a & ids_b
    return sum(id_weights.get(i, 1) for i in common)


def base_affinity_three(char_a: str, char_b: str, char_c: str, name_map: dict,
                         character_ids: dict, id_weights: dict) -> int:
    """
    Affinita' di base "a tre" (figlio-genitore-nonno): somma dei pesi degli ID
    presenti in TUTTI E TRE i personaggi (intersezione a tre insiemi), non solo
    a coppie. Usata per la componente 'nonni' dell'Individual Affinity, secondo
    il meccanismo reale del gioco (vedi uma-compat.md).
    Ritorna 0 se due dei tre risultano la stessa umamusume di base (self-affinity
    coinvolta), o se manca un mapping per uno dei tre.
    """
    jps = [name_map.get(c) for c in (char_a, char_b, char_c)]
    if None in jps:
        return 0
    if len(set(jps)) < 3:
        return 0  # almeno due dei tre sono la stessa umamusume di base
    ids = [character_ids.get(jp, set()) for jp in jps]
    common = ids[0] & ids[1] & ids[2]
    return sum(id_weights.get(i, 1) for i in common)
