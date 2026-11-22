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
nessuna nuova formula qui, solo orchestrazione.

Ogni ace e' un albero INDIPENDENTE (decisione dell'utente, 2026-11-22, al
posto della vecchia "condivisione del genitore" tra ace): i nonni
appartengono al ramo dell'ace, non al personaggio genitore, quindi lo
stesso personaggio (o lo stesso veterano) puo' stare in piu' ace, anche
con nonni diversi, e i suggerimenti possono ripetersi tra un ace e l'altro.
Dentro UN albero ogni nome base compare una sola volta.

Ricerca in due fasi per ace (greedy, non esaustiva congiunta):
1. Genitori: candidato col punteggio pairwise piu' alto verso l'ace
   (matrice gia' precalcolata, base+gara). I nonni non sono ancora noti,
   quindi il Bonus genitore<->nonno non e' ancora nella somma -- rifinito
   in fase 2.
2. Nonni: con i genitori noti, usa la formula reale completa
   (build_cycle_details, Bonus incluso) per scegliere il candidato che
   massimizza la Overall Affinity dell'ace.

ponytail: greedy per slot (prima i genitori, poi i nonni), non una ricerca
esaustiva congiunta -- puo' mancare l'ottimo quando due slot interagiscono
forte tra loro. Upgrade: provare combinazioni esaustive di coppie
(genitore1,genitore2) su uno shortlist ristretto, stesso pattern di
loop_search.best_loop.
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


def _validate_parents(aces, parent_slots):
    """Regole del gioco sui genitori scelti, per nome base (varianti incluse):
    mai genitore di se stesso, mai lo stesso personaggio come genitore 1 e 2."""
    for ace in aces:
        p1, p2 = parent_slots.get((ace, "parent1")), parent_slots.get((ace, "parent2"))
        for parent in (p1, p2):
            if parent and base_character(parent) == base_character(ace):
                raise ValueError(f"Un ace non puo' essere genitore di se stesso: '{ace}' / '{parent}'.")
        if p1 and p2 and base_character(p1) == base_character(p2):
            raise ValueError(f"Lo stesso personaggio non puo' essere genitore 1 e 2 dello stesso ace: '{p1}' / '{p2}'.")


ROLE_GPS = {"parent1": ("gp1a", "gp1b"), "parent2": ("gp2a", "gp2b")}
ALL_ROLES = ("parent1", "parent2", "gp1a", "gp1b", "gp2a", "gp2b")


def build_established(ace, slots):
    """Albero di UN ace nel formato di cycle_analysis.established: l'ace solo
    se entrambi i genitori sono noti, ogni genitore noto con i suoi 2 nonni
    (None = ignoto, gestito da build_cycle_details)."""
    established = {}
    if slots["parent1"] and slots["parent2"]:
        established[ace] = (slots["parent1"], slots["parent2"])
    for parent_role, (gp_a, gp_b) in ROLE_GPS.items():
        if slots[parent_role]:
            established[slots[parent_role]] = (slots[gp_a], slots[gp_b])
    return established


def _tree_bases(ace, slots):
    return {base_character(c) for c in [ace, *slots.values()] if c}


def plan_ace(ace, slots, fixed_branches, candidate_pool, matrix, name_map, character_ids,
             id_weights, calendar, races, aptitudes, mode, min_aptitude):
    """
    slots: dict[ruolo] -> personaggio o None (ruoli in ALL_ROLES; None = da
      suggerire). Copia interna, l'input del chiamante non viene modificato.
    fixed_branches: genitori ('parent1'/'parent2') aggiunti da veterano, i
      cui nonni sono quelli del veterano: mai suggeriti, un None resta ignoto.
    Ritorna (slots completati, ciclo o None se un genitore resta ignoto).
    """
    slots = {role: slots.get(role) or None for role in ALL_ROLES}

    def best(score_of):
        exclude = _tree_bases(ace, slots)
        best_candidate, best_score = None, float("-inf")
        for cand in candidate_pool:
            if base_character(cand) in exclude:
                continue
            score = score_of(cand)
            if score > best_score:
                best_score, best_candidate = score, cand
        return best_candidate

    def cycles():
        established = build_established(ace, slots)
        members = {ace} | {c for c in slots.values() if c}
        resolved = resolve_group_achievable(members, races, aptitudes, calendar, mode, min_aptitude)
        return build_cycle_details(established, matrix, name_map, character_ids, id_weights,
                                   resolved, children=[ace] if ace in established else [])

    # --- Fase 1: genitori, punteggio pairwise (base+gara) verso l'ace ---
    for role in ("parent1", "parent2"):
        if slots[role] is None:
            slots[role] = best(lambda cand: pair_score(ace, cand, matrix))

    # --- Fase 2: nonni, formula reale completa (Bonus genitore<->nonno incluso) ---
    for parent_role, gp_roles in ROLE_GPS.items():
        if slots[parent_role] is None or parent_role in fixed_branches:
            continue
        for gp_role in gp_roles:
            if slots[gp_role] is not None:
                continue

            def overall_with(cand, gp_role=gp_role):
                slots[gp_role] = cand
                result = cycles()
                slots[gp_role] = None
                return result[0]["overall_affinity"] if result else 0

            slots[gp_role] = best(overall_with)

    result = cycles()
    return slots, (result[0] if result else None)


def plan_ace_group(aces, slots, fixed_branches, candidate_pool, matrix, name_map, character_ids,
                   id_weights, calendar, races, aptitudes, mode, min_aptitude):
    """
    aces: lista di 1-3 personaggi.
    slots: dict[ace] -> dict[ruolo] -> personaggio o None (vedi plan_ace).
    fixed_branches: dict[ace] -> insieme dei genitori aggiunti da veterano.
    candidate_pool: personaggi tra cui cercare (gia' filtrati a monte per
      Global/posseduti, come altrove nel progetto).
    Ogni ace e' pianificato da solo (vedi docstring del modulo).
    Ritorna dict {slots, cycles, total_affinity}.
    """
    _validate_aces(aces)
    out_slots, cycles = {}, []
    for ace in aces:
        ace_slots = slots.get(ace, {})
        _validate_parents([ace], {(ace, r): ace_slots.get(r) for r in ("parent1", "parent2")})
        out_slots[ace], cycle = plan_ace(
            ace, ace_slots, fixed_branches.get(ace, set()), candidate_pool, matrix, name_map,
            character_ids, id_weights, calendar, races, aptitudes, mode, min_aptitude,
        )
        if cycle:
            cycles.append(cycle)
    return {"slots": out_slots, "cycles": cycles, "total_affinity": sum(c["overall_affinity"] for c in cycles)}


def _demo():
    """Self-check minimo su dati sintetici: (1) la ricerca sceglie davvero il
    candidato con punteggio piu' alto, anche per piu' ace insieme (ripetizioni
    ammesse tra ace diversi); (2) lo stesso genitore puo' avere nonni diversi
    in due ace; (3) i nonni di un veterano non vengono suggeriti."""
    aces = ["ace1", "ace2"]
    candidate_pool = ["cand_good", "cand_bad", "gp1", "gp2", "gp3"]
    matrix = {}
    for a in aces:
        for c in candidate_pool:
            key = (a, c) if a < c else (c, a)
            matrix[key] = {"base": 10 if c == "cand_good" else 1, "race": 0, "total": 10 if c == "cand_good" else 1}
    for i, c1 in enumerate(candidate_pool):
        for c2 in candidate_pool[i + 1:]:
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
    common = dict(candidate_pool=candidate_pool, matrix=matrix, name_map=name_map, character_ids=character_ids,
                  id_weights=id_weights, calendar=calendar, races=races, aptitudes=aptitudes,
                  mode="mant", min_aptitude={})
    try:
        result = plan_ace_group(aces, slots={}, fixed_branches={}, **common)
        # Stesso genitore in due ace con nonni diversi (due veterani diversi).
        split = plan_ace_group(
            aces,
            slots={"ace1": {"parent1": "cand_good", "gp1a": "gp1", "gp1b": "gp2"},
                   "ace2": {"parent1": "cand_good", "gp1a": "gp3", "gp1b": None}},
            fixed_branches={"ace1": {"parent1"}, "ace2": {"parent1"}}, **common,
        )
    finally:
        cycle_analysis.resolve_group_achievable = orig
        globals()["resolve_group_achievable"] = orig

    assert result["slots"]["ace1"]["parent1"] == "cand_good", result["slots"]
    assert result["slots"]["ace2"]["parent1"] == "cand_good", "Ripetizioni tra ace ammesse"
    assert len(result["cycles"]) == 2, "Devono risultare 2 cicli, uno per ace"
    assert split["slots"]["ace1"]["gp1a"] == "gp1" and split["slots"]["ace2"]["gp1a"] == "gp3"
    assert split["slots"]["ace2"]["gp1b"] is None, "Nonni di un veterano: un ignoto resta ignoto"
    assert split["slots"]["ace1"]["gp2a"] is not None, "Nonni del genitore non veterano vanno suggeriti"

    # Regole genitori per nome base (varianti incluse).
    for slots in ({("oguri_cap", "parent1"): "oguri_cap_og_xmas"},
                  {("ace1", "parent1"): "el_condor_pasa", ("ace1", "parent2"): "el_condor_pasa_og"}):
        try:
            _validate_parents(list({k[0] for k in slots}), slots)
            raise AssertionError(f"Atteso ValueError per {slots}")
        except ValueError:
            pass
    _validate_parents(["ace1"], {("ace1", "parent1"): "el_condor_pasa", ("ace1", "parent2"): "agnes_digital"})
    print("ace_planner: self-check OK")


if __name__ == "__main__":
    _demo()
