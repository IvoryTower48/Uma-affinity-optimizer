# -*- coding: utf-8 -*-
"""
Pianificazione di uno o piu' "ace" (1-3 personaggi, il numero di slot PvP a
veterani): un ace non deve necessariamente richiudere il loop come genitore,
ma ha comunque una genealogia a 6 antenati (2 genitori + 4 nonni) di cui
massimizzare l'affinita'. Slot scelti manualmente dall'utente (per una spark
verde/unica importante) restano fissi; gli slot lasciati liberi vengono
suggeriti automaticamente.

Un ace + i suoi 6 antenati E' esattamente un "ciclo" gia' modellato da
cycle_analysis.build_cycle_details (stessa formula Individual/Overall
Affinity del loop a 5, Bonus da gare condivise incluso correttamente SOLO
tra genitore1<->genitore2 e genitore<->nonno, mai figlio<->antenato) --
nessuna nuova formula qui, solo orchestrazione. La CONDIVISIONE di un
genitore tra piu' ace (utile perche' gli utenti schierano 3 veterani in PvP,
spesso con lo stesso stile di corsa: conviene riusare la stessa carta
genitore invece di allevarne 3 diverse) e' altrettanto gratuita: basta che
due ace referenzino lo STESSO personaggio nel loro parent_slots, ed
established[quel_genitore] (quindi anche i suoi nonni) e' condiviso di
conseguenza -- build_cycle_details gia' generalizza a N figli via il
parametro 'children'.

Ricerca in due fasi (greedy, non esaustiva congiunta):
1. Genitori: candidato che massimizza la somma del punteggio pairwise
   (matrice gia' precalcolata, base+gara) verso gli ace coinvolti in quello
   slot (1 se indipendente, 2-3 se condiviso). I nonni non sono ancora noti
   in questa fase, quindi il Bonus genitore<->nonno non e' ancora nella
   somma -- rifinito in fase 2.
2. Nonni: con TUTTI i genitori ormai noti, usa la formula reale completa
   (build_cycle_details, Bonus incluso) per scegliere il candidato che
   massimizza la somma delle Overall Affinity degli ace che usano quel
   genitore.

ponytail: greedy per slot (prima tutti i genitori, poi i nonni), non una
ricerca esaustiva congiunta su tutti gli slot insieme -- puo' mancare
l'ottimo globale quando due slot interagiscono forte tra loro. Upgrade: se
in pratica il risultato greedy delude, provare combinazioni esaustive di
coppie (genitore1,genitore2) su uno shortlist ristretto, stesso pattern di
loop_search.best_loop.
ponytail: l'esclusione "nome base gia' usato" e' GLOBALE su tutto il piano
(tutti gli ace insieme), non per singolo albero-ace -- evita che un
personaggio compaia due volte nello STESSO albero (vietato, sarebbe un
proprio antenato duplicato) ma impedisce anche riusi legittimi e
indipendenti tra alberi DIVERSI non condivisi (es. stesso personaggio come
genitore di ace1 e nonno-indipendente di ace3, in teoria valido in gioco).
Upgrade: tracciare l'esclusione per singolo albero-ace se risultasse
limitante in pratica.
"""
from cycle_analysis import build_cycle_details, resolve_group_achievable
from loop_search import pair_score
from naming import base_character

ROLES = ("parent1", "parent2")


def _validate_aces(aces):
    if not 1 <= len(aces) <= 3:
        raise ValueError(f"Servono da 1 a 3 ace, ricevuti {len(aces)}.")
    if len(aces) != len({base_character(a) for a in aces}):
        raise ValueError("Due ace non possono condividere lo stesso nome base.")


def build_established(aces, parent_slots, grandparent_slots):
    """
    parent_slots: dict[(ace, 'parent1'/'parent2')] -> personaggio o None.
    grandparent_slots: dict[personaggio_genitore] -> [nonno_a, nonno_b]
      (None per slot ignoto) -- chiave e' IL GENITORE, non l'ace: una carta
      genitore ha nonni fissi indipendentemente da quanti ace la
      condividono come genitore.
    Ritorna established nello stesso formato di cycle_analysis (pronto per
    build_cycle_details con children=aces); un ace compare solo se ENTRAMBI
    i suoi genitori sono noti (coerente con build_cycle_details, che gestisce
    gia' gli antenati ignoti tramite established.get(..., (None, None))).
    """
    established = {}
    for ace in aces:
        p1 = parent_slots.get((ace, "parent1"))
        p2 = parent_slots.get((ace, "parent2"))
        if p1 is not None and p2 is not None:
            established[ace] = (p1, p2)
    for parent, gps in grandparent_slots.items():
        established[parent] = tuple(gps)
    return established


def _known_members(aces, parent_slots, grandparent_slots):
    members = set(aces) | {v for v in parent_slots.values() if v is not None}
    for gps in grandparent_slots.values():
        members |= {v for v in gps if v is not None}
    return members


def plan_ace_group(aces, parent_slots, grandparent_slots, parent_share_groups,
                    candidate_pool, matrix, name_map, character_ids, id_weights,
                    calendar, races, aptitudes, mode, min_aptitude):
    """
    aces: lista di 1-3 personaggi.
    parent_slots: dict[(ace, 'parent1'/'parent2')] -> personaggio o None
      (None = da suggerire). Copia interna, l'input del chiamante non viene
      modificato.
    grandparent_slots: dict[personaggio_genitore] -> [nonno_a, nonno_b]
      (None per slot ignoto/da suggerire). Solo per genitori gia' presenti
      in parent_slots o che lo saranno dopo la fase 1.
    parent_share_groups: lista di liste di (ace, role) da riempire con LO
      STESSO personaggio quando ancora ignoti (condivisione tra ace); una
      coppia (ace,role) non menzionata qui e' indipendente. Se uno degli
      slot di un gruppo e' gia' assegnato (bloccato dall'utente), quel
      valore si propaga a tutto il gruppo -- ValueError se il gruppo ha
      gia' valori diversi assegnati (input contraddittorio).
    candidate_pool: personaggi tra cui cercare (gia' filtrati a monte per
      Global/posseduti, come altrove nel progetto).

    Ritorna dict {parent_slots, grandparent_slots, cycles, total_affinity}.
    """
    _validate_aces(aces)
    parent_slots = dict(parent_slots)
    grandparent_slots = {k: list(v) for k, v in grandparent_slots.items()}

    # --- Fase 1: genitori, punteggio pairwise (base+gara) verso gli ace coinvolti ---
    grouped_keys = {key for group in parent_share_groups for key in group}
    pending = [list(g) for g in parent_share_groups]
    pending += [
        [(ace, role)] for ace in aces for role in ROLES
        if (ace, role) not in grouped_keys and parent_slots.get((ace, role)) is None
    ]

    for group in pending:
        existing_values = {parent_slots.get(k) for k in group if parent_slots.get(k) is not None}
        if len(existing_values) > 1:
            raise ValueError(f"Slot condivisi con personaggi diversi gia' assegnati: {group}")
        if existing_values:
            value = existing_values.pop()
            for k in group:
                parent_slots[k] = value
            continue

        target_aces = sorted({ace for ace, _ in group})
        exclude_bases = {base_character(c) for c in _known_members(aces, parent_slots, grandparent_slots)}
        best_candidate, best_score = None, float("-inf")
        for cand in candidate_pool:
            if base_character(cand) in exclude_bases:
                continue
            score = sum(pair_score(ace, cand, matrix) for ace in target_aces)
            if score > best_score:
                best_score, best_candidate = score, cand
        if best_candidate is not None:
            for k in group:
                parent_slots[k] = best_candidate

    # --- Fase 2: nonni, formula reale completa (Bonus genitore<->nonno incluso) ---
    def overall_sum(established, target_aces):
        members = _known_members(aces, parent_slots, grandparent_slots)
        resolved = resolve_group_achievable(members, races, aptitudes, calendar, mode, min_aptitude)
        cycles = build_cycle_details(established, matrix, name_map, character_ids, id_weights,
                                      resolved, children=target_aces)
        return sum(c["overall_affinity"] for c in cycles)

    known_parents = sorted({v for v in parent_slots.values() if v is not None})
    for parent in known_parents:
        gps = grandparent_slots.setdefault(parent, [None, None])
        target_aces = sorted({ace for (ace, role), v in parent_slots.items() if v == parent})
        for i in range(2):
            if gps[i] is not None:
                continue
            exclude_bases = {base_character(c) for c in _known_members(aces, parent_slots, grandparent_slots)}
            exclude_bases.add(base_character(parent))
            best_candidate, best_score = None, float("-inf")
            for cand in candidate_pool:
                if base_character(cand) in exclude_bases:
                    continue
                gps[i] = cand
                established = build_established(aces, parent_slots, grandparent_slots)
                score = overall_sum(established, target_aces)
                gps[i] = None
                if score > best_score:
                    best_score, best_candidate = score, cand
            gps[i] = best_candidate

    # --- risultato finale ---
    established = build_established(aces, parent_slots, grandparent_slots)
    children = [ace for ace in aces if ace in established]
    members = _known_members(aces, parent_slots, grandparent_slots)
    resolved = resolve_group_achievable(members, races, aptitudes, calendar, mode, min_aptitude)
    cycles = build_cycle_details(established, matrix, name_map, character_ids, id_weights,
                                  resolved, children=children)
    return {
        "parent_slots": parent_slots,
        "grandparent_slots": grandparent_slots,
        "cycles": cycles,
        "total_affinity": sum(c["overall_affinity"] for c in cycles),
    }


def _demo():
    """Self-check minimo su dati sintetici: verifica che (1) la condivisione
    di un genitore tra 2 ace produca UNA sola entry established per quel
    genitore, riusata da entrambi i cicli, e (2) la ricerca scelga
    davvero il candidato con punteggio piu' alto, non uno a caso."""
    aces = ["ace1", "ace2"]
    candidate_pool = ["cand_good", "cand_bad", "gp1", "gp2"]
    matrix = {}
    for a in aces:
        for c in candidate_pool:
            key = (a, c) if a < c else (c, a)
            matrix[key] = {"base": 10 if c == "cand_good" else 1, "race": 0, "total": 10 if c == "cand_good" else 1}
    for c1, c2 in [("cand_good", "cand_bad"), ("cand_good", "gp1"), ("cand_good", "gp2"), ("cand_bad", "gp1"), ("cand_bad", "gp2"), ("gp1", "gp2")]:
        key = (c1, c2) if c1 < c2 else (c2, c1)
        matrix[key] = {"base": 1, "race": 0, "total": 1}

    name_map = {c: c for c in aces + candidate_pool}
    character_ids, id_weights = {}, {}
    calendar, races = {}, {}
    aptitudes = {c: {} for c in aces + candidate_pool}

    def fake_resolve_group_achievable(members, races, aptitudes, calendar, mode, min_aptitude):
        return {m: set() for m in members}

    import cycle_analysis
    orig = cycle_analysis.resolve_group_achievable
    cycle_analysis.resolve_group_achievable = fake_resolve_group_achievable
    globals()["resolve_group_achievable"] = fake_resolve_group_achievable
    try:
        result = plan_ace_group(
            aces,
            parent_slots={("ace1", "parent1"): None, ("ace1", "parent2"): None,
                          ("ace2", "parent1"): None, ("ace2", "parent2"): None},
            grandparent_slots={},
            parent_share_groups=[[("ace1", "parent1"), ("ace2", "parent1")]],
            candidate_pool=candidate_pool,
            matrix=matrix, name_map=name_map, character_ids=character_ids, id_weights=id_weights,
            calendar=calendar, races=races, aptitudes=aptitudes, mode="mant", min_aptitude={},
        )
    finally:
        cycle_analysis.resolve_group_achievable = orig
        globals()["resolve_group_achievable"] = orig

    shared = result["parent_slots"][("ace1", "parent1")]
    assert shared == "cand_good", f"Atteso cand_good come genitore condiviso, trovato {shared}"
    assert result["parent_slots"][("ace2", "parent1")] == shared, "Il genitore condiviso deve essere identico per entrambi gli ace"
    assert len(result["cycles"]) == 2, "Devono risultare 2 cicli, uno per ace"
    print("ace_planner: self-check OK")


if __name__ == "__main__":
    _demo()
