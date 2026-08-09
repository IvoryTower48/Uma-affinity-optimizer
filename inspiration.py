# -*- coding: utf-8 -*-
"""
Calcolo del tasso di ispirazione: probabilita' che una specifica spark venga
ereditata durante un evento di Inspiration in carriera. Diverso da
aptitude_inheritance.py, che modella le pink spark come ereditarieta'
pre-run deterministica -- questo modulo copre invece gli eventi casuali in
carriera, esplicitamente fuori scope li' (vedi il suo docstring).

Formula (fonti community incrociate -- uma.guide, umareference.com -- NON
datamine ufficiale confermato, vedi HANDOFF.md per i dettagli e le fonti):

    Probabilita' = TassoBase(categoria, stelle) x (1 + AffinitaIndividuale / 100)

Nessun moltiplicatore esplicito genitore/nonno: l'Affinita' Individuale
usata e' gia' quella calcolata da cycle_analysis.build_cycle_details per
quello specifico slot (parent1/parent2/gp1a/gp1b/gp2a/gp2b), che per
costruzione e' gia' piu' bassa per i nonni -- coerente con la lettura di
Chun nella conversazione originale con l'utente ("same formula [for parents
and grandparents]... GPs usually have about half the Affinity Ps have, so
about half the proc rate" -- non una regola a parte, solo l'Affinita' che
differisce).

Le chiavi 'stelle' nella tabella tassi sono STRINGHE ("1"/"2"/"3"), non int:
la tabella viaggia come JSON (persistita su disco, esposta via API) e le
chiavi di un oggetto JSON sono sempre stringhe -- usare stringhe ovunque
anche lato Python evita conversioni silenziosamente sbagliate al round-trip.
"""

DEFAULT_BASE_RATES = {
    "blue": {"1": 70, "2": 80, "3": 90},
    "pink": {"1": 1, "2": 3, "3": 5},
    "green": {"1": 5, "2": 10, "3": 15},
    "white": {"1": 3, "2": 6, "3": 9},
    "race": {"1": 1, "2": 2, "3": 3},
}

# blu/rosa/verde: ogni personaggio ne ha esattamente una (una stat spark, una
# aptitude spark, una unique skill) -- si aggregano direttamente tra
# antenati, nessuna identita' da tracciare.
# bianca/gara: un personaggio puo' portarne multiple e diverse tra loro --
# l'aggregazione "probabilita' di ereditare ALMENO UNA VOLTA" va fatta per
# NOME di skill, non per categoria (vedi combined_chance_by_skill sotto).
CATEGORIES_WITH_IDENTITY = {"white", "race"}


def inspiration_chance(base_rates: dict, category: str, stars: int, individual_affinity: float) -> float:
    """
    Probabilita' (percentuale, 0-100+) che una spark venga ereditata in un
    singolo evento di Inspiration. Funzione pura, nessun I/O -- stesso stile
    di aptitude_inheritance.apply_pink_sparks. Puo' superare 100 con
    Affinita' molto alte sommata a un tasso base gia' alto (es. blu ad alta
    Affinita'): il chiamante decide se troncare per la visualizzazione, qui
    si ritorna il valore "vero" della formula.
    """
    if category not in base_rates:
        raise ValueError(f"Categoria spark sconosciuta: {category}")
    stars_key = str(stars)
    if stars_key not in ("1", "2", "3"):
        raise ValueError(f"Stelle non valide: {stars} (atteso 1, 2 o 3)")
    base = base_rates[category][stars_key]
    return base * (1 + individual_affinity / 100)


def combined_chance(chances_percent: list) -> float:
    """
    Probabilita' (percentuale) che ALMENO UNA di piu' probabilita'
    indipendenti si verifichi: 1 - prodotto(1 - p_i). Le probabilita' in
    ingresso e il risultato sono in percentuale (0-100), non frazioni 0-1.
    Eventi indipendenti, come sottolineato dall'utente/Chun.
    """
    product = 1.0
    for p in chances_percent:
        product *= (1 - p / 100)
    return (1 - product) * 100


def validate_base_rates(payload_dict: dict) -> dict:
    """
    Merge di un dict parziale (es. da un payload JSON) sopra i default,
    poi validazione: solleva ValueError se una categoria/valore di stelle
    non e' tra le note, o un tasso non e' un numero tra 0 e 100. Stesso
    pattern di config.validate_min_aptitude.
    """
    merged = {cat: dict(stars) for cat, stars in DEFAULT_BASE_RATES.items()}
    for cat, stars_dict in (payload_dict or {}).items():
        if cat not in DEFAULT_BASE_RATES:
            raise ValueError(f"Categoria spark sconosciuta: {cat}")
        if not isinstance(stars_dict, dict):
            raise ValueError(f"Valore non valido per la categoria {cat}: atteso un oggetto stelle->tasso.")
        for star_key, rate in stars_dict.items():
            if star_key not in ("1", "2", "3"):
                raise ValueError(f"Stelle non valide per {cat}: {star_key}")
            if not isinstance(rate, (int, float)) or isinstance(rate, bool) or not (0 <= rate <= 100):
                raise ValueError(f"Tasso non valido per {cat} {star_key}: {rate}")
            merged[cat][star_key] = rate
    return merged
