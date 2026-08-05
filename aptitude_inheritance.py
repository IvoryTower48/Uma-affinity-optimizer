# -*- coding: utf-8 -*-
"""
Aptitude Inheritance ("pink spark") — v3.

Modella l'unica delle 3 occasioni di miglioramento aptitude in carriera che e'
deterministica/prevedibile in anticipo: l'ereditarieta' pre-run da genitori e
nonni. Le altre 2 (eventi durante la carriera) dipendono da RNG e sono fuori
scope.

Regole di gioco (confermate dall'utente, vedi HANDOFF.md):
  - le stelle di pink spark sulla STESSA categoria di aptitude si sommano
    prima di applicare la tabella soglie;
  - soglie: 1 stella totale -> +1 livello, 4 -> +2, 7 -> +3, 10 -> +4 livelli
    (scala GRADE_ORDER, dove indice piu' basso = voto migliore);
  - il tetto massimo raggiungibile con questo meccanismo e' "A" (non si
    raggiunge mai "S", indice 0);
  - per uso di pianificazione, l'input e' aggregato per categoria (Modalita'
    A): l'utente specifica "quante stelle totali di categoria X" servono in
    un punto del loop, senza indicare quale personaggio le porta — vedi
    HANDOFF.md per il contesto completo. Questo modulo NON si occupa di
    tracciare quale antenato porta quale spark (Modalita' B, non ancora
    implementata), solo dell'effetto aggregato sull'aptitude risultante.

Vincoli strutturali del gioco (6 slot antenato per ciclo: 2 genitori + 4
nonni, ciascuno porta al massimo una spark da 1 a 3 stelle):
  - massimo 4 tipi di aptitude diversi per ciclo (coerente col fatto che, nel
    loop chiuso a 5, ogni ciclo coinvolge solo 4 personaggi distinti — vedi
    HANDOFF.md, sezione "Struttura genealogica del loop");
  - massimo 18 stelle totali per ciclo (6 slot x 3 stelle).

Soglie di AVVISO (soft warning, non bloccante — il piano "difficilmente
sostenibile" viene comunque calcolato e mostrato): oltre 11 stelle totali
e/o oltre 3 aptitude diverse in un ciclo.
"""
from config import GRADE_ORDER, GRADE_RANK

# Tabella soglie: stelle totali (minimo) -> livelli di miglioramento.
# Applicata prendendo la soglia piu' alta raggiunta dal totale di stelle.
_STAR_THRESHOLDS = [
    (10, 4),
    (7, 3),
    (4, 2),
    (1, 1),
]

MAX_CATEGORIES_PER_CYCLE = 4
MAX_STARS_PER_CYCLE = 18
WARNING_STAR_THRESHOLD = 11
WARNING_CATEGORY_THRESHOLD = 3

CAP_GRADE = "A"


def stars_to_levels(total_stars: int) -> int:
    """Converte un totale di stelle (sulla stessa categoria) nel numero di
    livelli di miglioramento, secondo la tabella soglie di gioco."""
    if total_stars <= 0:
        return 0
    for min_stars, levels in _STAR_THRESHOLDS:
        if total_stars >= min_stars:
            return levels
    return 0


def apply_pink_sparks(base_aptitudes: dict, spark_stars_by_category: dict) -> dict:
    """
    Applica l'ereditarieta' pink spark a un set di aptitude base.

    base_aptitudes: dict[categoria] -> voto (es. {"turf": "B", "dirt": "C", ...}),
      stesso formato di data_loader.load_aptitudes()[personaggio].
    spark_stars_by_category: dict[categoria] -> stelle totali per quella
      categoria (es. {"dirt": 7}). Categorie assenti o a 0 non vengono toccate.

    Ritorna un NUOVO dict (non modifica base_aptitudes), con le stesse chiavi,
    voti migliorati secondo stars_to_levels() e mai oltre CAP_GRADE ("A").
    Funzione pura, nessuna dipendenza da I/O.
    """
    result = dict(base_aptitudes)
    cap_rank = GRADE_RANK[CAP_GRADE]
    for category, stars in spark_stars_by_category.items():
        if category not in result or not stars:
            continue
        levels = stars_to_levels(stars)
        if levels <= 0:
            continue
        current_rank = GRADE_RANK[result[category]]
        new_rank = max(cap_rank, current_rank - levels)
        result[category] = GRADE_ORDER[new_rank]
    return result


def validate_spark_plan(spark_stars_by_category: dict) -> None:
    """
    Verifica i vincoli STRUTTURALI (hard limit, non aggirabili nel gioco) di
    un piano di spark per un singolo ciclo. Solleva ValueError se violati.
    Non controlla le soglie di avviso soft (vedi spark_plan_warning).
    """
    categories_used = [c for c, s in spark_stars_by_category.items() if s]
    if len(categories_used) > MAX_CATEGORIES_PER_CYCLE:
        raise ValueError(
            f"Massimo {MAX_CATEGORIES_PER_CYCLE} tipi di aptitude diversi per "
            f"ciclo (un ciclo coinvolge solo {MAX_CATEGORIES_PER_CYCLE} "
            f"personaggi distinti), ricevuti {len(categories_used)}."
        )
    total_stars = sum(spark_stars_by_category.values())
    if total_stars > MAX_STARS_PER_CYCLE:
        raise ValueError(
            f"Massimo {MAX_STARS_PER_CYCLE} stelle totali per ciclo (6 slot "
            f"antenato x 3 stelle), ricevute {total_stars}."
        )
    for category, stars in spark_stars_by_category.items():
        if stars < 0:
            raise ValueError(f"Stelle negative non valide per '{category}': {stars}.")


def spark_plan_warning(spark_stars_by_category: dict) -> str | None:
    """
    Ritorna un messaggio di avviso (soft, non bloccante) se il piano supera le
    soglie di sostenibilita' pratica (>11 stelle totali e/o >3 aptitude
    diverse in un ciclo), altrimenti None. Il chiamante calcola comunque il
    risultato e lo mostra: questo e' solo un avviso informativo.
    """
    categories_used = [c for c, s in spark_stars_by_category.items() if s]
    total_stars = sum(spark_stars_by_category.values())
    n_categories = len(categories_used)
    if total_stars > WARNING_STAR_THRESHOLD or n_categories > WARNING_CATEGORY_THRESHOLD:
        return (
            f"Piano difficilmente sostenibile nella pratica ({total_stars} "
            f"stelle totali su {n_categories} aptitude diverse): probabilmente "
            f"irrealistico da ottenere facendo grinding con le carte a "
            f"disposizione."
        )
    return None


MAX_SIGNATURE_SPARK_STARS = 3


def validate_signature_spark(plan: dict) -> None:
    """
    Modalita' B (2026-07-30, versione corretta): valida la spark "firma" di
    UN personaggio -- quella che il personaggio ottiene a fine carriera,
    esattamente UNA categoria (non fino a 4 come il piano per-ciclo della
    Modalita' A), da 1 a 3 stelle (corretto dall'utente il 2026-07-30: una
    singola spark non supera mai le 3 stelle). Solleva ValueError se viola
    questi vincoli.
    """
    if len(plan) > 1:
        raise ValueError(
            "La spark 'firma' di un personaggio riguarda una sola categoria "
            f"di aptitude (ricevute {len(plan)})."
        )
    for category, stars in plan.items():
        if not (1 <= stars <= MAX_SIGNATURE_SPARK_STARS):
            raise ValueError(
                f"Le stelle di una spark 'firma' devono essere tra 1 e "
                f"{MAX_SIGNATURE_SPARK_STARS} (ricevute {stars} per '{category}')."
            )


def apply_character_spark_plan(character_spark_plan: dict, base_aptitudes: dict) -> dict:
    """
    Primitiva di basso livello: sovrascrive DIRETTAMENTE l'aptitude di un
    personaggio con un valore aggregato gia' pronto (usata da Modalita' A,
    vedi cycle_analysis.apply_spark_plan_to_aptitudes, che vi delega dopo
    aver tradotto il piano per-ciclo in un piano per-nome). NON e' la
    Modalita' B (spark "firma" di un personaggio, che si propaga per
    conteggio-slot agli ALTRI cicli in cui quel personaggio compare come
    antenato): quella logica di derivazione vive in
    cycle_analysis.derive_cycle_spark_plan_from_signature_sparks, che poi
    passa comunque per QUESTA stessa funzione una volta tradotta in valori
    aggregati per ciclo.

    character_spark_plan: dict[nome_personaggio] -> dict[categoria] -> stelle.
    base_aptitudes: dict completo aptitudes (tutti i personaggi), non modificato.

    Ritorna un NUOVO dict aptitudes con le aptitude dei personaggi presenti in
    character_spark_plan sovrascritte secondo apply_pink_sparks. Personaggi
    assenti dal piano restano invariati. Dato che le aptitude sono un dict
    piatto indicizzato per nome, l'effetto si propaga AUTOMATICAMENTE a ogni
    punto del calcolo dove quel personaggio ricompare (come genitore o nonno
    in cicli diversi da quello in cui e' figlio) -- non serve nessuna logica
    di propagazione esplicita, e' una conseguenza diretta di come e' fatto il
    dict delle aptitude.
    """
    modified = dict(base_aptitudes)
    for character, plan in character_spark_plan.items():
        if character not in base_aptitudes or not plan:
            continue
        modified[character] = apply_pink_sparks(base_aptitudes[character], plan)
    return modified
