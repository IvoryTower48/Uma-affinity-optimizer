# -*- coding: utf-8 -*-
"""
Risoluzione nome-variante -> nome-base, per il calcolo dell'affinita' di base
(due varianti della stessa umamusume devono risolvere allo stesso nome base,
cosi' la self-affinity a 0 scatta automaticamente).
"""
from config import KNOWN_SUFFIXES


def base_character(variant_name: str, suffixes=KNOWN_SUFFIXES) -> str:
    """
    Rimuove iterativamente i suffissi noti dalla fine del nome, finche' non ce ne
    sono piu' da rimuovere. Gestisce anche suffissi concatenati (es. "_og_xmas").
    Se il nome non ha alcun suffisso noto, viene restituito invariato (e' gia' un
    nome base).
    """
    name = variant_name
    changed = True
    while changed:
        changed = False
        for suf in suffixes:
            if name.endswith(suf) and len(name) > len(suf):
                name = name[: -len(suf)]
                changed = True
                break  # ricomincia il controllo dei suffissi sul nome accorciato
    return name


def variant_group(all_variant_names, suffixes=KNOWN_SUFFIXES):
    """
    Dato l'elenco di tutti i nomi-variante conosciuti (quelli usati in
    aptitudes/mandatory_races), restituisce un dict {nome_base: [varianti]} --
    utile per generare le note informative in output quando un loop include
    una variante che ne ha altre.
    """
    groups = {}
    for name in all_variant_names:
        base = base_character(name, suffixes)
        groups.setdefault(base, []).append(name)
    return groups


def resolve_character_input(user_input: str, all_characters, suffixes=KNOWN_SUFFIXES):
    """
    Risolve l'input dell'utente (da riga di comando) al nome-variante esatto usato
    nei dataset, con due liberta':
      1) l'utente puo' scrivere solo il nome base, senza suffisso (es. "fuji_kiseki"
         invece di "fuji_kiseki_og") -- SE il nome base identifica una sola variante.
      2) l'utente puo' usare spazi al posto degli underscore (es. "fuji kiseki").

    Ritorna una tupla (nome_risolto, candidati):
      - match esatto o base univoca: (nome_risolto, None)
      - input ambiguo (piu' varianti con lo stesso nome base): (None, [candidati])
      - input non trovato: (None, [])
    """
    normalized = user_input.strip().lower().replace(" ", "_")

    # 1) match esatto (compreso il caso di un personaggio senza varianti)
    if normalized in all_characters:
        return normalized, None

    # 2) match per nome base (suffisso omesso dall'utente)
    matches = sorted(c for c in all_characters if base_character(c, suffixes) == normalized)
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, matches

    return None, []
