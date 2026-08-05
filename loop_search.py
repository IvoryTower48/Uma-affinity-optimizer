# -*- coding: utf-8 -*-
"""
- top_n_by_field: per un personaggio, i migliori N candidati per un campo del punteggio
- best_loop: cerca il gruppo di LOOP_SIZE personaggi che massimizza la somma dei punteggi
  su tutte le coppie interne. Esaustivo se il pool di candidati e' piccolo, altrimenti
  ristretto a un pool ridotto (i piu' promettenti) per restare trattabile.
"""
from itertools import combinations
from config import LOOP_SIZE, RACE_SHARED_WIN_POINTS
from affinity import base_affinity, achievable_races_for, resolve_achievable
from naming import base_character


def build_score_matrix(characters, name_map, character_ids, id_weights,
                        calendar, races, aptitudes, mode="career"):
    """
    Precalcola il punteggio combinato per ogni coppia di personaggi (una sola volta),
    per evitare di ricalcolarlo ripetutamente durante la ricerca del loop.
    Le gare raggiungibili per personaggio vengono calcolate una sola volta a testa
    (invece che una volta per ogni coppia), poi la race-compatibility di ogni
    coppia e' una semplice intersezione di insiemi.
    Ritorna dict[(a,b)] -> score_dict, con a < b alfabeticamente (chiave unica per coppia).
    """
    achievable = {
        char: achievable_races_for(char, races, aptitudes, calendar, mode)
        for char in characters
    }

    matrix = {}
    for a, b in combinations(sorted(characters), 2):
        common = achievable[a] & achievable[b]
        resolved_a = resolve_achievable(a, common, races, aptitudes, calendar, mode)
        resolved_b = resolve_achievable(b, common, races, aptitudes, calendar, mode)
        shared = resolved_a & resolved_b
        race_score = len(shared) * RACE_SHARED_WIN_POINTS
        base = base_affinity(a, b, name_map, character_ids, id_weights)
        total = base + race_score
        matrix[(a, b)] = {"base": base, "race": race_score, "total": total}
    return matrix


def pair_score(a, b, matrix):
    key = (a, b) if a < b else (b, a)
    return matrix[key]["total"]


def top_n_by_field(character, all_characters, matrix, field="total", n=10):
    """
    Ritorna i migliori n personaggi (diversi da 'character') per un campo del
    punteggio ('total' per il ranking principale, 'base' o 'race' in modalita'
    debug per mostrare separatamente le migliori affinita' di base e le
    migliori compatibilita' di calendario), con AL MASSIMO un membro per nome
    base: due varianti della stessa umamusume (es. daiwa_scarlet_og e
    daiwa_scarlet_xmas) non possono comparire entrambe nel risultato, perche'
    occuperebbero due dei quattro slot con la stessa identita' genealogica
    (affinita' di base 0 tra loro, e nella pratica "la stessa nonna" se poi
    usate insieme in un loop).
    """
    own_base = base_character(character)
    scored = [
        (other, matrix[(character, other) if character < other else (other, character)][field])
        for other in all_characters
        if other != character and base_character(other) != own_base
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    result = []
    used_bases = set()
    for other, score in scored:
        b = base_character(other)
        if b in used_bases:
            continue
        result.append((other, score))
        used_bases.add(b)
        if len(result) == n:
            break
    return result


def loop_total_score(group, matrix):
    """Somma i punteggi di tutte le coppie interne al gruppo (grafo completo)."""
    return sum(pair_score(a, b, matrix) for a, b in combinations(group, 2))


def has_duplicate_base(group):
    """True se due o piu' membri del gruppo condividono lo stesso nome base."""
    bases = [base_character(c) for c in group]
    return len(set(bases)) != len(bases)


def best_loop(candidate_pool, matrix, loop_size=LOOP_SIZE):
    """
    Ricerca esaustiva del sottoinsieme di loop_size personaggi con somma massima dei
    punteggi a coppie, ristretta a candidate_pool (deve essere di dimensione
    trattabile, es. <= 20-25 per restare veloce: C(20,5) = 15504 combinazioni).
    Scarta a priori qualunque gruppo con due varianti dello stesso personaggio base:
    altrimenti il loop a 5 perderebbe il suo scopo (garantire 5 identita'
    genealogiche distinte, cosi' nessuno rischia di essere il proprio nonno).
    Ritorna (miglior_gruppo: tuple, punteggio_totale: float).
    """
    best_group = None
    best_score = float("-inf")
    for group in combinations(sorted(candidate_pool), loop_size):
        if has_duplicate_base(group):
            continue
        score = loop_total_score(group, matrix)
        if score > best_score:
            best_score = score
            best_group = group
    return best_group, best_score


def shortlist_candidates(all_characters, matrix, pool_size=20):
    """
    Costruisce un pool ridotto di personaggi piu' promettenti su cui poi fare la
    ricerca esaustiva del loop: quelli con la media piu' alta di punteggio verso
    tutti gli altri personaggi (euristica semplice per restringere lo spazio di
    ricerca su roster grandi).
    """
    avg_scores = []
    for char in all_characters:
        others = [o for o in all_characters if o != char]
        if not others:
            continue
        avg = sum(pair_score(char, o, matrix) for o in others) / len(others)
        avg_scores.append((char, avg))
    avg_scores.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in avg_scores[:pool_size]]


def shortlist_candidates_for_fixed(fixed_members, all_characters, matrix, pool_size=20):
    """
    Come shortlist_candidates, ma pensata per completare un gruppo che ha gia'
    'fixed_members' fissati: classifica i candidati per punteggio combinato
    verso i membri fissi specificamente (somma dei pair_score verso ciascuno),
    invece che per media generale verso tutto il roster -- piu' mirata quando
    si cerca chi completa al meglio un nucleo gia' scelto.
    Esclude i fixed_members stessi e chiunque condivida il loro nome base.
    """
    fixed_bases = {base_character(f) for f in fixed_members}
    scored = [
        (c, sum(pair_score(c, f, matrix) for f in fixed_members))
        for c in all_characters
        if c not in fixed_members and base_character(c) not in fixed_bases
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:pool_size]]


def best_loop_with_fixed(fixed_members, candidate_pool, matrix, loop_size=LOOP_SIZE):
    """
    Come best_loop, ma con un sottoinsieme di personaggi gia' fissato: cerca
    esaustivamente solo i (loop_size - len(fixed_members)) membri restanti tra
    candidate_pool, massimizzando il punteggio totale del gruppo completo
    (fixed_members + i nuovi). Scarta a priori i candidati che condividono il
    nome base con un membro fisso o tra di loro (stessa regola di best_loop).

    Solleva ValueError se fixed_members contiene gia' due varianti con lo
    stesso nome base (input contraddittorio: due "nonni" sarebbero in realta'
    la stessa identita' genealogica) o se sono piu' di loop_size.
    """
    if len(fixed_members) > loop_size:
        raise ValueError(
            f"Troppi personaggi fissi ({len(fixed_members)}): il loop ha spazio "
            f"per al massimo {loop_size}."
        )
    if has_duplicate_base(fixed_members):
        raise ValueError(
            "I personaggi fissi includono due varianti dello stesso nome base "
            "(stessa identita' genealogica) -- non possono coesistere nello stesso loop."
        )

    remaining_size = loop_size - len(fixed_members)
    if remaining_size == 0:
        return tuple(sorted(fixed_members)), loop_total_score(fixed_members, matrix)

    fixed_bases = {base_character(f) for f in fixed_members}
    pool = [
        c for c in candidate_pool
        if c not in fixed_members and base_character(c) not in fixed_bases
    ]

    best_group = None
    best_score = float("-inf")
    for combo in combinations(sorted(pool), remaining_size):
        if has_duplicate_base(combo):
            continue
        group = tuple(fixed_members) + combo
        score = loop_total_score(group, matrix)
        if score > best_score:
            best_score = score
            best_group = group
    return best_group, best_score
