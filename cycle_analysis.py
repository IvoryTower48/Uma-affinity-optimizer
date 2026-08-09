# -*- coding: utf-8 -*-
"""
"Esplorazione a un salto": dato un personaggio selezionato X e i suoi 4 migliori
compatibili (A, B, C, D, in ordine di ranking), calcola la struttura a 5 cicli
che permette di riusare lo stesso gruppo di 5 personaggi come legacy loop
perpetuo, senza che nessuno diventi mai il proprio nonno.

Schema fisso (derivato e validato insieme all'utente su carta prima di
implementarlo):

    Ciclo 1: figlio=X  genitori=(A, B)
    Ciclo 2: figlio=C  genitori=(X, B)
    Ciclo 3: figlio=D  genitori=(X, C)
    Ciclo 4: figlio=A  genitori=(C, D)
    Ciclo 5: figlio=B  genitori=(A, D)

Una volta completato questo primo giro, tutti e 5 i personaggi risultano
"stabiliti" (hanno genitori fissi, riusabili come nonni in futuro), e la
struttura si ripete identica all'infinito (ciclo 6 = ciclo 1, ecc.) -- per
questo i nonni di ogni genitore, in QUALSIASI ciclo, si leggono direttamente
dalla tabella "stabiliti" finale.

NOTA: l'assegnazione (A, B, C, D) = i 4 trovati in ordine di ranking e' una
scelta di default, non l'unica strutturalmente valida.

--- Modello di affinita' (corretto secondo il meccanismo reale del gioco,
vedi uma-compat.md fornito dall'utente) ---

Per ogni ciclo si calcolano due tipi di grandezza:

- Individual Affinity (una per genitore e una per nonno): e' quella che conta
  davvero in gioco, determina il tasso di attivazione delle spark.
    IA(genitore)  = bAff[figlio,genitore] + bAff[genitore1,genitore2]
                    + bAff[figlio,genitore,nonno1] + bAff[figlio,genitore,nonno2]
                    + Bonus[genitore,nonno1] + Bonus[genitore,nonno2]
                    + Bonus[genitore1,genitore2]
    IA(nonno)     = bAff[figlio,genitore,nonno] + Bonus[genitore,nonno]

  dove bAff[...] e' la somma dei pesi degli ID condivisi da TUTTI i personaggi
  elencati (affinita' di base, a due o a tre), e Bonus[A,B] e' il +3 per ogni
  gara G1 vinta in comune tra A e B.

  IMPORTANTE: l'affinita' da gare vinte NON si applica mai tra figlio e
  genitore, solo tra genitore1<->genitore2 e genitore<->nonno.

- Overall Affinity (una per ciclo): somma di OGNI bAff e OGNI Bonus coinvolti
  nell'albero, ciascuno contato UNA SOLA VOLTA (non e' la somma delle Individual
  Affinity, che conterebbe due volte i termini condivisi tra genitore e nonno).
  E' "generalmente inutile" ai fini del gameplay (determina solo il simbolo
  ◎/〇/△ a schermo) ma utile come stima complessiva della bonta' del gruppo.

--- Bonus "group-aware" (matching gara/turno fisico, priorita' di gruppo) ---

Quando si valuta una COPPIA isolata (per il ranking dei top-4/loop, in
loop_search.py), la scelta di quale gara tenere per ogni slot fisico conteso
resta quella "locale" (affinity.resolve_achievable, tie-break alfabetico)
perche' in quel momento non si conosce ancora il resto del gruppo.

Ma una volta che si ha un GRUPPO FISSO di 5 (esattamente il caso di questo
modulo), la scelta deve essere coerente su tutto il gruppo: per ogni gara
contesa, si preferisce quella raggiungibile dal maggior numero di membri del
gruppo (una gara obbligatoria per qualcuno la rende automaticamente
raggiungibile per lui, quindi "obbligatoria per piu' persone" e "raggiungibile
da piu' persone" sono la stessa cosa vista da due lati); a parita' vince il
criterio alfabetico, come prima. La risoluzione (affinity.resolve_achievable)
funziona in modo uniforme su gare singole E ricorrenti: quando piu' gare
condividono complessivamente MENO turni fisici di quante gare siano candidate
(es. le 4 gare JBC su soli 2 turni, anno 2 e anno 3), solo le prime N in
ordine di priorita' (N = turni disponibili) restano davvero raggiungibili; le
altre vengono correttamente escluse (non piu' un limite noto/accettato, ma un
caso gestito). Ogni singola coppia dentro il gruppo usa comunque, come
fallback, la gara che ESSA PUO' raggiungere tra quelle rimaste disponibili,
anche se non e' quella "vincente" per il gruppo nel suo complesso.
"""
from itertools import combinations
from affinity import base_affinity_three, achievable_races_for, resolve_achievable
from display_names import format_character_name, format_race_name
from config import RACE_SHARED_WIN_POINTS, RACE_PRIORITY_OVERRIDE, ANCHOR_LOOP_SIZE
from loop_search import has_duplicate_base, shortlist_candidates_for_fixed
from naming import base_character
from aptitude_inheritance import (
    apply_character_spark_plan, validate_spark_plan, validate_signature_spark, spark_plan_warning,
)


def pair_detail(a, b, matrix):
    """Ritorna il dettaglio completo {base, race, total} tra due personaggi."""
    key = (a, b) if a < b else (b, a)
    return matrix[key]


def base_two(a, b, matrix):
    """bAff a due (affinita' di base pairwise), letta dalla matrice precalcolata."""
    return pair_detail(a, b, matrix)["base"]


def build_five_cycle_schedule(child, top4_ordered):
    """
    child: il personaggio selezionato (X).
    top4_ordered: lista di 4 personaggi (A, B, C, D) in ordine di ranking
    (il piu' compatibile per primo).

    Ritorna la tabella dei "genitori stabiliti" per ciascuno dei 5 personaggi:
    dict[personaggio] -> (genitore1, genitore2)
    """
    if len(top4_ordered) != 4:
        raise ValueError("Servono esattamente 4 personaggi (i top-4 trovati).")
    X = child
    A, B, C, D = top4_ordered
    established = {
        X: (A, B),
        C: (X, B),
        D: (X, C),
        A: (C, D),
        B: (A, D),
    }
    return established


def compute_turn_priority(group_members, races, aptitudes, calendar, mode, min_aptitude):
    """
    Per un gruppo FISSO di personaggi (qui: i 5 dell'esplorazione a un salto),
    calcola per OGNI gara (singola o ricorrente, nessuna distinzione) quanti
    membri del gruppo la raggiungono (aptitude/calendario permettendo, tramite
    la stessa achievable_races_for gia' usata altrove, PRIMA di risolvere
    eventuali conflitti di turno). Questo conteggio serve da criterio di
    priorita' quando piu' gare competono per lo stesso slot fisico (vedi
    affinity.resolve_achievable): vince quella raggiungibile da PIU' membri
    del gruppo; a parita', vince il race_id alfabeticamente minore.

    Generalizza la vecchia versione (che considerava solo le gare a occorrenza
    singola): ora anche gruppi di gare ricorrenti che si contendono meno turni
    di quante ce ne sarebbero bisogno (es. le 4 gare JBC su 2 soli turni)
    vengono correttamente arbitrati.

    Ritorna dict[race_id] -> chiave di ordinamento (conteggio decrescente,
    poi RACE_PRIORITY_OVERRIDE se la gara vi compare, poi alfabetico), da
    passare come priority_key a resolve_achievable. RACE_PRIORITY_OVERRIDE
    (vedi config.py) e' una preferenza manuale esplicita dell'utente per un
    piccolo elenco di gare note per condividere fisicamente lo stesso turno
    (le 4 gare JBC/QE2 Cup su y2_m11_d1/y3_m11_d1) -- si applica SOLO a
    parita' di conteggio, e SOLO alle gare elencate; tutte le altre
    mantengono il tie-break alfabetico di sempre.
    """
    achievable_per_member = {
        c: achievable_races_for(c, races, aptitudes, calendar, mode, min_aptitude)
        for c in group_members
    }
    counts = {
        race_id: sum(1 for ach in achievable_per_member.values() if race_id in ach)
        for race_id in races
    }
    return {
        race_id: (
            -counts[race_id],
            RACE_PRIORITY_OVERRIDE.index(race_id) if race_id in RACE_PRIORITY_OVERRIDE else len(RACE_PRIORITY_OVERRIDE),
            race_id,
        )
        for race_id in races
    }


def shared_wins_group_aware(a, b, resolved_per_member):
    """
    Gare vinte in comune tra a e b, usando la risoluzione group-aware GIA'
    calcolata UNA VOLTA per l'intero gruppo (resolve_group_achievable -- la
    STESSA usata da timeline.py per la colonna "raggiungibile"/"condivisa").

    Fix (2026-08-02, bug segnalato dall'utente su un caso concreto: Hanshin
    J.F. mostrata come gara in comune per un ciclo, pur essendo impossibile
    perche' sullo stesso turno fisico di Asahi Hai F.S., la gara che quello
    stesso personaggio vince davvero in un ALTRO ciclo). La versione
    precedente rifaceva una risoluzione ad hoc PER COPPIA (achievable_races_for
    intersecato tra a e b, poi un resolve_achievable separato per OGNI
    chiamata): un personaggio compare in piu' coppie nello stesso ciclo
    (genitore con l'altro genitore, con ciascun nonno...), e risolvendo ogni
    volta da capo su un sottoinsieme diverso di gare candidate poteva
    assegnargli gare DIVERSE per lo stesso turno in coppie diverse --
    fisicamente impossibile (un personaggio corre un solo turno alla volta).
    Usando ovunque lo stesso resolved_per_member (risolto una sola volta per
    tutto il gruppo), ogni personaggio ha un'UNICA gara assegnata per turno
    conteso, coerente in OGNI coppia in cui compare e con quanto mostra la
    timeline.
    """
    return sorted(resolved_per_member[a] & resolved_per_member[b])


def bonus_group_aware(a, b, resolved_per_member):
    """Bonus da gare G1 vinte in comune, con la scelta group-aware per i turni contesi."""
    wins = shared_wins_group_aware(a, b, resolved_per_member)
    return len(wins) * RACE_SHARED_WIN_POINTS


def build_cycle_details(established, matrix, name_map, character_ids, id_weights,
                         resolved_per_member, children=None):
    """
    Costruisce, per ciascuno dei personaggi-figlio richiesti, il dettaglio
    completo del ciclo corrispondente secondo il modello Individual/Overall
    Affinity. Il bonus da gare condivise usa la risoluzione group-aware GIA'
    calcolata per l'intero gruppo (resolved_per_member, da
    resolve_group_achievable), non piu' il valore precalcolato nella matrice
    (che e' pairwise puro).

    children: quali chiavi di 'established' processare come figlio. Default
    None = tutte (comportamento del loop chiuso a 5: ogni membro e' figlio di
    esattamente un ciclo). Un chiamante puo' passare un sottoinsieme esplicito
    quando 'established' contiene anche membri che non devono mai comparire
    come figlio (es. il rental loop, dove l'anchor e' sempre genitore, mai
    figlio -- vedi build_anchor_loop_schedule).

    Un genitore puo' non avere una entry in 'established' (es. l'anchor del
    rental loop quando le sue nonne/nonni non sono noti): in quel caso i
    termini che dipendono dai suoi nonni vengono OMESSI (non calcolati come
    0) dai dict individual_affinity/breakdown restituiti -- il chiamante puo'
    distinguere "ignoto" da "affinita' zero" controllando se la chiave e'
    presente.

    Ritorna una lista di dict, uno per ciclo, con chiavi:
      child, parent1, parent2, gp_parent1 (tupla), gp_parent2 (tupla),
      individual_affinity: dict con le IA di parent1, parent2, e le gp note
      overall_affinity: somma di ogni bAff/Bonus NOTO, contato una sola volta
    """
    cycles = []
    for child in (established.keys() if children is None else children):
        p1, p2 = established[child]
        gp1a, gp1b = established.get(p1, (None, None))
        gp2a, gp2b = established.get(p2, (None, None))

        # --- termini di base (bAff), a due e a tre (invariati, non c'entra il calendario) ---
        b_child_p1 = base_two(child, p1, matrix)
        b_child_p2 = base_two(child, p2, matrix)
        b_p1_p2 = base_two(p1, p2, matrix)
        b3_p1_gp1a = base_affinity_three(child, p1, gp1a, name_map, character_ids, id_weights) if gp1a is not None else None
        b3_p1_gp1b = base_affinity_three(child, p1, gp1b, name_map, character_ids, id_weights) if gp1b is not None else None
        b3_p2_gp2a = base_affinity_three(child, p2, gp2a, name_map, character_ids, id_weights) if gp2a is not None else None
        b3_p2_gp2b = base_affinity_three(child, p2, gp2b, name_map, character_ids, id_weights) if gp2b is not None else None

        # --- termini di bonus da gare (group-aware, mai tra figlio e genitore) ---
        bonus_p1_p2 = bonus_group_aware(p1, p2, resolved_per_member)
        bonus_p1_gp1a = bonus_group_aware(p1, gp1a, resolved_per_member) if gp1a is not None else None
        bonus_p1_gp1b = bonus_group_aware(p1, gp1b, resolved_per_member) if gp1b is not None else None
        bonus_p2_gp2a = bonus_group_aware(p2, gp2a, resolved_per_member) if gp2a is not None else None
        bonus_p2_gp2b = bonus_group_aware(p2, gp2b, resolved_per_member) if gp2b is not None else None

        individual_affinity = {
            "parent1": b_child_p1 + b_p1_p2 + (b3_p1_gp1a or 0) + (b3_p1_gp1b or 0)
                       + (bonus_p1_gp1a or 0) + (bonus_p1_gp1b or 0) + bonus_p1_p2,
            "parent2": b_child_p2 + b_p1_p2 + (b3_p2_gp2a or 0) + (b3_p2_gp2b or 0)
                       + (bonus_p2_gp2a or 0) + (bonus_p2_gp2b or 0) + bonus_p1_p2,
        }
        if gp1a is not None:
            individual_affinity["gp1a"] = b3_p1_gp1a + bonus_p1_gp1a
        if gp1b is not None:
            individual_affinity["gp1b"] = b3_p1_gp1b + bonus_p1_gp1b
        if gp2a is not None:
            individual_affinity["gp2a"] = b3_p2_gp2a + bonus_p2_gp2a
        if gp2b is not None:
            individual_affinity["gp2b"] = b3_p2_gp2b + bonus_p2_gp2b

        # scomposizione dei singoli addendi per ruolo, usata per il tooltip in UI.
        # I termini con un gp ignoto (None) sono filtrati via, non mostrati a 0.
        breakdown = {
            "parent1": [
                t for t in [
                    (f"bAff({child},{p1})", b_child_p1),
                    (f"bAff({p1},{p2})", b_p1_p2),
                    (f"bAff({child},{p1},{gp1a})", b3_p1_gp1a) if gp1a is not None else None,
                    (f"bAff({child},{p1},{gp1b})", b3_p1_gp1b) if gp1b is not None else None,
                    (f"Bonus({p1},{gp1a})", bonus_p1_gp1a) if gp1a is not None else None,
                    (f"Bonus({p1},{gp1b})", bonus_p1_gp1b) if gp1b is not None else None,
                    (f"Bonus({p1},{p2})", bonus_p1_p2),
                ] if t is not None
            ],
            "parent2": [
                t for t in [
                    (f"bAff({child},{p2})", b_child_p2),
                    (f"bAff({p1},{p2})", b_p1_p2),
                    (f"bAff({child},{p2},{gp2a})", b3_p2_gp2a) if gp2a is not None else None,
                    (f"bAff({child},{p2},{gp2b})", b3_p2_gp2b) if gp2b is not None else None,
                    (f"Bonus({p2},{gp2a})", bonus_p2_gp2a) if gp2a is not None else None,
                    (f"Bonus({p2},{gp2b})", bonus_p2_gp2b) if gp2b is not None else None,
                    (f"Bonus({p1},{p2})", bonus_p1_p2),
                ] if t is not None
            ],
        }
        if gp1a is not None:
            breakdown["gp1a"] = [
                (f"bAff({child},{p1},{gp1a})", b3_p1_gp1a),
                (f"Bonus({p1},{gp1a})", bonus_p1_gp1a),
            ]
        if gp1b is not None:
            breakdown["gp1b"] = [
                (f"bAff({child},{p1},{gp1b})", b3_p1_gp1b),
                (f"Bonus({p1},{gp1b})", bonus_p1_gp1b),
            ]
        if gp2a is not None:
            breakdown["gp2a"] = [
                (f"bAff({child},{p2},{gp2a})", b3_p2_gp2a),
                (f"Bonus({p2},{gp2a})", bonus_p2_gp2a),
            ]
        if gp2b is not None:
            breakdown["gp2b"] = [
                (f"bAff({child},{p2},{gp2b})", b3_p2_gp2b),
                (f"Bonus({p2},{gp2b})", bonus_p2_gp2b),
            ]

        overall_affinity = (
            b_child_p1 + b_child_p2 + b_p1_p2
            + (b3_p1_gp1a or 0) + (b3_p1_gp1b or 0) + (b3_p2_gp2a or 0) + (b3_p2_gp2b or 0)
            + bonus_p1_p2 + (bonus_p1_gp1a or 0) + (bonus_p1_gp1b or 0) + (bonus_p2_gp2a or 0) + (bonus_p2_gp2b or 0)
        )

        # scomposizione della formula Overall Affinity, ciascun termine NOTO
        # contato UNA SOLA VOLTA (a differenza di 'breakdown' sopra, dove
        # es. bAff(p1,p2)/Bonus(p1,p2) compaiono sia in parent1 sia in
        # parent2 perche' contribuiscono all'Individual Affinity di
        # ENTRAMBI) -- usata solo per la UI in modalita' debug.
        overall_breakdown = [
            t for t in [
                (f"bAff({child},{p1})", b_child_p1),
                (f"bAff({child},{p2})", b_child_p2),
                (f"bAff({p1},{p2})", b_p1_p2),
                (f"bAff({child},{p1},{gp1a})", b3_p1_gp1a) if gp1a is not None else None,
                (f"bAff({child},{p1},{gp1b})", b3_p1_gp1b) if gp1b is not None else None,
                (f"bAff({child},{p2},{gp2a})", b3_p2_gp2a) if gp2a is not None else None,
                (f"bAff({child},{p2},{gp2b})", b3_p2_gp2b) if gp2b is not None else None,
                (f"Bonus({p1},{p2})", bonus_p1_p2),
                (f"Bonus({p1},{gp1a})", bonus_p1_gp1a) if gp1a is not None else None,
                (f"Bonus({p1},{gp1b})", bonus_p1_gp1b) if gp1b is not None else None,
                (f"Bonus({p2},{gp2a})", bonus_p2_gp2a) if gp2a is not None else None,
                (f"Bonus({p2},{gp2b})", bonus_p2_gp2b) if gp2b is not None else None,
            ] if t is not None
        ]

        cycles.append({
            "child": child,
            "parent1": p1,
            "parent2": p2,
            "gp_parent1": (gp1a, gp1b),
            "gp_parent2": (gp2a, gp2b),
            "individual_affinity": individual_affinity,
            "breakdown": breakdown,
            "overall_affinity": overall_affinity,
            "overall_breakdown": overall_breakdown,
        })
    return cycles


def resolve_group_achievable(group_members, races, aptitudes, calendar, mode, min_aptitude):
    """
    Per un gruppo FISSO (qui: i 5 dell'esplorazione a un salto, o del loop),
    ritorna dict[personaggio] -> insieme delle gare DAVVERO raggiungibili,
    risolvendo per ciascuno i conflitti di turno tra le proprie gare candidate
    con la priorita' group-aware (compute_turn_priority): a parita' di scelta,
    si privilegiano le gare che aiutano di piu' il gruppo nel suo complesso.
    Usata da timeline.py per classificare correttamente come "impossibile" le
    gare che perdono la competizione per un turno conteso (es. 2 delle 4 gare
    JBC), invece di mostrarle come "raggiungibile" senza tener conto della
    scarsita' di turni disponibili.
    """
    achievable_per_member = {
        c: achievable_races_for(c, races, aptitudes, calendar, mode, min_aptitude)
        for c in group_members
    }
    turn_priority = compute_turn_priority(group_members, races, aptitudes, calendar, mode, min_aptitude)
    priority_key = lambda race_id: turn_priority[race_id]
    return {
        c: resolve_achievable(c, achievable_per_member[c], races, aptitudes, calendar, mode, priority_key)
        for c in group_members
    }


def one_hop_exploration(child, top4_ordered, matrix, name_map, character_ids, id_weights,
                         calendar, races, aptitudes, mode, min_aptitude):
    """
    Funzione di alto livello: dato il personaggio selezionato e i suoi top-4
    (in ordine di ranking), ritorna la lista dei 5 cicli con tutti i dettagli,
    usando la scelta group-aware per il bonus da gare condivise (calcolata una
    sola volta sull'intero gruppo di 5, poi riusata per ogni ciclo/coppia).
    """
    established = build_five_cycle_schedule(child, top4_ordered)
    group_members = [child] + list(top4_ordered)
    resolved_per_member = resolve_group_achievable(group_members, races, aptitudes, calendar, mode, min_aptitude)
    cycles = build_cycle_details(
        established, matrix, name_map, character_ids, id_weights, resolved_per_member,
    )
    total_loop_affinity = sum(c["overall_affinity"] for c in cycles)
    return {
        "cycles": cycles, "total_loop_affinity": total_loop_affinity,
        "_resolved_per_member": resolved_per_member,
    }


# --- Rental loop: genitore costante preso in prestito + rotazione a 3 ------
#
# Chi fa parent-looping usa spesso un genitore "in prestito" (rental, non
# posseduto, non modificabile) che non "nasce" mai -- si riaffitta sempre.
# Con un genitore sempre disponibile non servono 5 identita' genealogiche
# distinte per chiudere il loop, ne bastano 3 (vedi config.ANCHOR_LOOP_SIZE):
#
#     members[0]: genitori = (anchor, members[2])
#     members[1]: genitori = (anchor, members[0])
#     members[2]: genitori = (anchor, members[1])
#
# Le nonne/nonni dell'anchor (gp_a, gp_b), se noti, sono anch'essi fissi/non
# posseduti; se ignoti, i termini che dipendono da loro vengono OMESSI (non
# calcolati come 0) da build_cycle_details -- vedi il suo parametro 'children'.


def build_anchor_loop_schedule(anchor, members, gp_a=None, gp_b=None):
    """
    members: i 3 personaggi posseduti della rotazione, nell'ordine in cui si
    succedono (members[i] e' allevato da anchor + members[i-1]).
    Ritorna established: dict[personaggio] -> (genitore1, genitore2), stesso
    formato di build_five_cycle_schedule. 'anchor' compare come chiave anche
    se solo UNO tra gp_a/gp_b e' noto (es. (gp_a, None)): build_cycle_details
    gestisce gia' i singoli slot ignoti omettendone i termini (vedi il suo
    parametro 'children' e i confronti 'is not None'), quindi il nonno noto
    viene mostrato con la sua Individual Affinity reale, come se l'altro
    slot semplicemente non esistesse. 'anchor' non compare come chiave SOLO
    se ENTRAMBI i nonni sono ignoti (mai figlio di alcun ciclo in quel caso:
    si riaffitta, non si alleva).
    """
    if len(members) != ANCHOR_LOOP_SIZE:
        raise ValueError(f"Il rental loop richiede esattamente {ANCHOR_LOOP_SIZE} personaggi posseduti.")
    established = {
        members[0]: (anchor, members[2]),
        members[1]: (anchor, members[0]),
        members[2]: (anchor, members[1]),
    }
    if gp_a is not None or gp_b is not None:
        established[anchor] = (gp_a, gp_b)
    return established


def best_anchor_loop(anchor, gp_a, gp_b, fixed_members, candidate_pool, matrix,
                      name_map, character_ids, id_weights, races, aptitudes,
                      calendar, mode, min_aptitude):
    """
    Cerca la rotazione di ANCHOR_LOOP_SIZE personaggi posseduti che, insieme
    all'anchor fisso (+ le sue nonne/nonni se noti), massimizza la somma
    delle Overall Affinity dei cicli risultanti -- ottimizzazione CONGIUNTA
    anchor-rotazione (include bAff/Bonus tra l'anchor e ciascun membro), non
    il solo punteggio grezzo di ciascun membro verso l'anchor.

    fixed_members: 0-ANCHOR_LOOP_SIZE personaggi posseduti gia' scelti
    dall'utente (stesso ruolo di must_include nel loop a 5). Gli slot
    restanti sono cercati esaustivamente su una shortlist economica
    (shortlist_candidates_for_fixed, la stessa euristica gia' usata per il
    loop a 5), provando entrambe le direzioni cicliche possibili per ogni
    combinazione (con 3 elementi ce ne sono solo 2).

    Ritorna dict {members, cycles, total_loop_affinity}, o None se nessuna
    combinazione valida e' stata trovata. Solleva ValueError se fixed_members
    e' troppo numeroso o condivide un nome base con se stesso/anchor/gp_a/gp_b.
    """
    if len(fixed_members) > ANCHOR_LOOP_SIZE:
        raise ValueError(
            f"Troppi personaggi fissi ({len(fixed_members)}): il rental loop ha "
            f"spazio per al massimo {ANCHOR_LOOP_SIZE}."
        )
    anchor_group = [anchor] + [g for g in (gp_a, gp_b) if g is not None]
    if has_duplicate_base(list(fixed_members) + anchor_group):
        raise ValueError(
            "L'anchor, le sue nonne/nonni e i personaggi fissi non possono "
            "condividere lo stesso nome base (stessa identita' genealogica)."
        )

    remaining_size = ANCHOR_LOOP_SIZE - len(fixed_members)
    fixed_bases = {base_character(c) for c in list(fixed_members) + anchor_group}
    if remaining_size == 0:
        pool = []
    else:
        shortlisted = shortlist_candidates_for_fixed(list(fixed_members) + [anchor], candidate_pool, matrix)
        pool = [c for c in shortlisted if base_character(c) not in fixed_bases]

    best = None
    for combo in combinations(pool, remaining_size):
        if has_duplicate_base(combo):
            continue
        candidate_members = list(fixed_members) + list(combo)
        orderings = [candidate_members]
        if len(candidate_members) == 3:
            orderings.append([candidate_members[0], candidate_members[2], candidate_members[1]])
        for members in orderings:
            established = build_anchor_loop_schedule(anchor, members, gp_a, gp_b)
            group_members = [anchor] + members + anchor_group[1:]
            resolved_per_member = resolve_group_achievable(
                group_members, races, aptitudes, calendar, mode, min_aptitude,
            )
            cycles = build_cycle_details(
                established, matrix, name_map, character_ids, id_weights,
                resolved_per_member, children=members,
            )
            total = sum(c["overall_affinity"] for c in cycles)
            if best is None or total > best["total_loop_affinity"]:
                best = {"members": members, "cycles": cycles, "total_loop_affinity": total}

    return best


def suggest_anchor_grandparents(anchor, members, candidate_pool, matrix, name_map,
                                 character_ids, id_weights, exclude_bases,
                                 races, aptitudes, calendar, mode, min_aptitude, limit=10):
    """
    Suggerimenti per le nonne/nonni dell'anchor quando non sono ancora noti:
    per ciascun candidato, la sua Individual Affinity REALE in ognuno dei 3
    step della rotazione (non un'approssimazione: stessi numeri che si
    vedrebbero davvero in ciascuna delle 3 card dopo averlo scelto), piu' la
    loro somma. Ordinati per somma decrescente.

    Per ogni candidato si fissa PROVVISORIAMENTE solo gp1a=candidato (gp1b
    resta ignoto) e si passa per la STESSA pipeline reale usata per il
    risultato finale (resolve_group_achievable + build_cycle_details, non
    un'approssimazione pairwise): established[anchor] = (candidato, None),
    children=members, poi si legge individual_affinity['gp1a'] in ciascuno
    dei 3 cicli. established[anchor] e' lo stesso per tutti e 3 (l'anchor
    non ruota), quindi gp1a e' il candidato in ognuno -- cambia solo il
    bAff a tre (dipende dal figlio del ciclo), il Bonus resta identico.

    Ritorna una lista di tuple (personaggio, [affinita_step1, step2, step3]).
    """
    scored = []
    for g in candidate_pool:
        if g == anchor or base_character(g) in exclude_bases:
            continue
        established = {
            members[0]: (anchor, members[2]),
            members[1]: (anchor, members[0]),
            members[2]: (anchor, members[1]),
            anchor: (g, None),
        }
        group_members = [anchor] + members + [g]
        resolved_per_member = resolve_group_achievable(
            group_members, races, aptitudes, calendar, mode, min_aptitude,
        )
        cycles = build_cycle_details(
            established, matrix, name_map, character_ids, id_weights,
            resolved_per_member, children=members,
        )
        steps = [c["individual_affinity"]["gp1a"] for c in cycles]
        scored.append((g, steps))
    scored.sort(key=lambda x: sum(x[1]), reverse=True)
    return scored[:limit]


def suggest_anchor_grandparent_pairs(anchor, members, candidate_pool, matrix, name_map,
                                      character_ids, id_weights, exclude_bases,
                                      races, aptitudes, calendar, mode, min_aptitude,
                                      baseline_cycles, limit=10, shortlist_size=20):
    """
    Le migliori COPPIE di nonne/nonni per l'anchor: quelle che, se inserite
    ENTRAMBE, aggiungono piu' Overall Affinity all'intero loop -- diverso da
    suggest_anchor_grandparents (che valuta un candidato alla volta, con
    l'altro slot ignoto): qui la coppia e' completa, established[anchor] e'
    pienamente noto, quindi TUTTI i termini della formula sono calcolati,
    incluso il Bonus group-aware sull'intera coppia insieme (che PUO'
    differire dalla somma dei due Bonus singoli, per via della risoluzione
    dei turni contesi condivisa su tutto il gruppo).

    baseline_cycles: i 3 cicli SENZA alcun nonno noto per questo stesso
    anchor/members (gia' calcolati da best_anchor_loop quando gp_a/gp_b non
    sono forniti -- passati qui per evitare di ricalcolarli). Il delta per
    step mostrato e' overall_affinity_con_coppia - overall_affinity_baseline,
    posizione per posizione (stessi 3 figli, nello stesso ordine).

    Ricerca ristretta a una shortlist dei migliori 'shortlist_size'
    candidati singoli (stesso criterio/ordine di suggest_anchor_grandparents)
    invece di tutto candidate_pool: i due slot nonno sono indipendenti nella
    formula (nessun termine incrociato tra gp1a e gp1b, l'unica interazione
    e' nel Bonus group-aware, un effetto secondario), quindi un buon
    candidato singolo e' quasi sempre parte della coppia migliore -- una
    ricerca esaustiva su tutto il roster posseduto (anche 100+ personaggi,
    C(100,2) = 4950 combinazioni) sarebbe altrimenti troppo lenta.

    Ritorna una lista di dict {gp_a, gp_b, total_delta, deltas} (deltas =
    lista di 3 delta interi, uno per step, stesso ordine di 'members'),
    ordinata per total_delta decrescente.
    """
    shortlist = [g for g, _ in suggest_anchor_grandparents(
        anchor, members, candidate_pool, matrix, name_map, character_ids,
        id_weights, exclude_bases, races, aptitudes, calendar, mode, min_aptitude,
        limit=shortlist_size,
    )]
    baseline = [c["overall_affinity"] for c in baseline_cycles]

    scored = []
    for g_a, g_b in combinations(shortlist, 2):
        if base_character(g_a) == base_character(g_b):
            continue
        established = build_anchor_loop_schedule(anchor, members, g_a, g_b)
        group_members = [anchor] + members + [g_a, g_b]
        resolved_per_member = resolve_group_achievable(
            group_members, races, aptitudes, calendar, mode, min_aptitude,
        )
        cycles = build_cycle_details(
            established, matrix, name_map, character_ids, id_weights,
            resolved_per_member, children=members,
        )
        deltas = [c["overall_affinity"] - b for c, b in zip(cycles, baseline)]
        scored.append({"gp_a": g_a, "gp_b": g_b, "total_delta": sum(deltas), "deltas": deltas})
    scored.sort(key=lambda x: x["total_delta"], reverse=True)
    return scored[:limit]


def first_cycle_shared_races(first_cycle, races, resolved_per_member):
    """
    Elenco delle gare vinte in comune (nomi), solo per le 5 coppie rilevanti ai
    fini del Bonus nel PRIMO ciclo (figlio=personaggio selezionato):
    genitore1-genitore2, genitore1-nonno1, genitore1-nonno2,
    genitore2-nonno1, genitore2-nonno2. Usa la stessa risoluzione group-aware
    (resolved_per_member) del resto del calcolo, cosi' la lista mostrata
    corrisponde esattamente al Bonus effettivamente conteggiato.
    """
    p1, p2 = first_cycle["parent1"], first_cycle["parent2"]
    gp1a, gp1b = first_cycle["gp_parent1"]
    gp2a, gp2b = first_cycle["gp_parent2"]

    pairs = [
        (f"{format_character_name(p1)} - {format_character_name(p2)}", p1, p2),
        (f"{format_character_name(p1)} - {format_character_name(gp1a)}", p1, gp1a),
        (f"{format_character_name(p1)} - {format_character_name(gp1b)}", p1, gp1b),
        (f"{format_character_name(p2)} - {format_character_name(gp2a)}", p2, gp2a),
        (f"{format_character_name(p2)} - {format_character_name(gp2b)}", p2, gp2b),
    ]
    return [
        {
            "label": label,
            "races": [
                format_race_name(race_id)
                for race_id in sorted(
                    shared_wins_group_aware(a, b, resolved_per_member),
                    key=lambda race_id: races[race_id]["turn_number"],
                )
            ],
            "race_ids": sorted(
                shared_wins_group_aware(a, b, resolved_per_member),
                key=lambda race_id: races[race_id]["turn_number"],
            ),
        }
        for label, a, b in pairs
    ]


def all_cycles_shared_races(cycles, races, resolved_per_member):
    """
    Come first_cycle_shared_races, ma per TUTTI e 5 i cicli (necessario per il
    documento PDF/JSON del loop completo -- vedi HANDOFF.md, "shared_races_per_cycle:
    DA ESTENDERE"): ogni ciclo coinvolge coppie di personaggi diverse (il figlio
    di un ciclo diventa genitore in un altro), quindi le gare condivise vanno
    ricalcolate per ciascuno, non dedotte da quelle del primo. first_cycle_shared_races
    non assume nulla di specifico sul "primo" ciclo (usa solo i campi generici
    parent1/parent2/gp_parent1/gp_parent2 presenti in OGNI ciclo), quindi si
    applica identica, una volta per ciclo.
    """
    return [
        first_cycle_shared_races(cycle, races, resolved_per_member)
        for cycle in cycles
    ]


# --- v3: Aptitude Inheritance ("pink spark") --------------------------------
#
# Disponibile SOLO dopo aver gia' calcolato i top-4 di un personaggio scelto
# (cioe' dopo one_hop_exploration): l'utente inserisce un piano spark -- per
# ognuno dei 5 cicli, stelle totali per categoria di aptitude (Modalita' A,
# aggregata, vedi aptitude_inheritance.py e HANDOFF.md) -- e il tool:
#   1. applica il piano alla aptitude del FIGLIO di ciascun ciclo e ricalcola
#      i 5 cicli, sommando l'Overall Affinity di ciascuno in una singola
#      "Total Loop Affinity" (apply_spark_plan_to_aptitudes / one_hop_exploration_with_sparks);
#   2. cerca, su tutto il pool di personaggi disponibili, se sostituire UNO dei
#      4 compagni (mai il personaggio scelto originariamente) con un altro
#      candidato alzi la Total Loop Affinity, tenendo FISSO lo stesso piano
#      spark (che segue la POSIZIONE nel ciclo, non il nome specifico -- se la
#      posizione cambia occupante, lo stesso piano si applica al nuovo
#      occupante) -- find_best_substitution.


def apply_spark_plan_to_aptitudes(established, spark_plan, base_aptitudes):
    """
    established: dict[personaggio] -> (parent1, parent2), nell'ordine di
      inserimento gia' usato altrove (chiavi = figlio di ciascun ciclo, in
      ordine Ciclo1..Ciclo5 -- vedi build_five_cycle_schedule).
    spark_plan: dict[cycle_number 1-5] -> dict[categoria] -> stelle totali.
      Un ciclo assente dal piano equivale a "nessuna spark per quel ciclo".
    base_aptitudes: dict completo aptitudes (tutti i personaggi), non modificato.

    Modalita' A: traduce il piano "per posizione nel ciclo" in un piano "per
    nome di personaggio" (ogni personaggio e' figlio di esattamente un
    ciclo, quindi la traduzione e' univoca) e delega ad
    apply_character_spark_plan, che fa il lavoro vero. Il piano "segue la
    posizione nel ciclo": se il gruppo cambia (sostituzione), basta
    ricostruire 'established' col nuovo membro in quella posizione e questa
    funzione applichera' comunque lo stesso piano al nuovo occupante.
    """
    child_order = list(established.keys())  # ordine Ciclo1..Ciclo5
    character_spark_plan = {
        child: spark_plan[cycle_number]
        for cycle_number, child in zip(range(1, 6), child_order)
        if spark_plan.get(cycle_number)
    }
    return apply_character_spark_plan(character_spark_plan, base_aptitudes)


def _ancestor_slots(established, child):
    """I 6 slot antenato (parent1, parent2, gp1a, gp1b, gp2a, gp2b) di un
    ciclo, ricavati da 'established' (il figlio non compare mai tra i propri
    stessi antenati, per costruzione dello schema a 5 cicli)."""
    parent1, parent2 = established[child]
    gp1a, gp1b = established[parent1]
    gp2a, gp2b = established[parent2]
    return [parent1, parent2, gp1a, gp1b, gp2a, gp2b]


def derive_cycle_spark_plan_from_signature_sparks(established, character_spark_plan):
    """
    Modalita' B (2026-07-30, versione CORRETTA -- la precedente, che
    sovrascriveva direttamente l'aptitude del personaggio scelto, era
    concettualmente sbagliata e sostituita su richiesta esplicita
    dell'utente).

    Ogni personaggio del loop ottiene, a fine carriera, UNA SOLA pink spark
    "firma" (categoria + stelle, vedi validate_signature_spark). Quando
    quel personaggio viene poi riusato come genitore O nonno in un ciclo
    successivo, la sua spark si eredita AL VALORE PIENO per ciascuno slot
    antenato che occupa in quel ciclo -- se occupa 2 slot nello stesso
    ciclo (capita nella rotazione: un personaggio puo' essere sia genitore
    diretto sia nonno "via" un altro genitore), la spark conta 2 volte
    (stelle raddoppiate), non 1. Esempio confermato dall'utente: X con 2★
    Dirt conta 2★ nel Ciclo2 (occupa 1 slot) ma 4★ nei Cicli 3 e 4 (occupa
    2 slot in entrambi).

    established: dict[personaggio] -> (parent1, parent2), ordine Ciclo1..5
      (vedi build_five_cycle_schedule).
    character_spark_plan: dict[nome_personaggio] -> dict[categoria] ->
      stelle (UNA sola categoria per personaggio, validato dal chiamante
      con validate_signature_spark).

    Ritorna un piano "per ciclo" (STESSO formato del piano Modalita' A:
    dict[cycle_number 1-5] -> dict[categoria] -> stelle), calcolato
    sommando, per ciascun ciclo, i contributi di TUTTI i personaggi con
    spark assegnata che occupano almeno uno dei 6 slot antenato di quel
    ciclo (sommando le stelle se piu' personaggi condividono la stessa
    categoria nello stesso ciclo). Un personaggio non contribuisce mai al
    proprio stesso ciclo (non puo' essere antenato di se stesso). Questo
    piano derivato viene poi applicato con la STESSA funzione della
    Modalita' A (apply_spark_plan_to_aptitudes) -- nessuna logica duplicata.
    """
    child_order = list(established.keys())
    derived = {}
    for cycle_number, child in zip(range(1, 6), child_order):
        slots = _ancestor_slots(established, child)
        aggregated = {}
        for character, plan in character_spark_plan.items():
            count = slots.count(character)
            if count == 0:
                continue
            for category, stars in plan.items():
                aggregated[category] = aggregated.get(category, 0) + stars * count
        if aggregated:
            derived[cycle_number] = aggregated
    return derived


def _merge_cycle_spark_plans(plan_a, plan_b):
    """Somma due piani 'per ciclo' (stesso formato: dict[cycle_number] ->
    dict[categoria] -> stelle), categoria per categoria, ciclo per ciclo."""
    merged = {}
    for cycle_number in set(plan_a) | set(plan_b):
        combined = {}
        for source in (plan_a.get(cycle_number, {}), plan_b.get(cycle_number, {})):
            for category, stars in source.items():
                combined[category] = combined.get(category, 0) + stars
        merged[cycle_number] = combined
    return merged


def one_hop_exploration_with_sparks(child, top4_ordered, spark_plan, matrix, name_map,
                                     character_ids, id_weights, calendar, races,
                                     aptitudes, mode, min_aptitude, character_spark_plan=None):
    """
    Come one_hop_exploration, ma applicando prima il piano spark alle
    aptitude dei 5 personaggi coinvolti. Supporta ENTRAMBE le modalita' di
    input, componibili nella stessa chiamata:
      - spark_plan (Modalita' A, "per posizione nel ciclo", aggregata): dict
        [cycle_number 1-5] -> dict[categoria] -> stelle. L'utente specifica
        direttamente quante stelle servono in un punto del loop, senza dire
        chi le porta. Vedi apply_spark_plan_to_aptitudes.
      - character_spark_plan (Modalita' B, "spark firma di un personaggio
        reale", opzionale, default nessuno): dict[nome_personaggio] -> dict
        [UNA categoria] -> stelle. Il personaggio dev'essere uno dei 5 del
        gruppo attuale (child o uno dei top4_ordered) -- non e' controllato
        qui (spetta al chiamante, vedi app.py). La sua spark si propaga
        automaticamente, per conteggio-slot, a ogni ciclo in cui compare
        come antenato (vedi derive_cycle_spark_plan_from_signature_sparks).
    Solleva ValueError se: un ciclo del piano A non e' un intero 1-5; un
    piano A viola i vincoli strutturali (validate_spark_plan: max 4
    categorie, max 18 stelle per ciclo); un piano B ha piu' di una
    categoria o stelle non positive (validate_signature_spark).

    Ritorna lo stesso dict di one_hop_exploration, con in piu':
      total_loop_affinity: somma dell'Overall Affinity dei 5 cicli.
      spark_warnings: dict[cycle_number] -> messaggio di avviso soft (calcolato
        sul piano EFFETTIVO per ciclo, somma di quanto viene da A e da B --
        vedi aptitude_inheritance.spark_plan_warning).
    """
    character_spark_plan = character_spark_plan or {}

    for cycle_number, plan in spark_plan.items():
        if cycle_number not in (1, 2, 3, 4, 5):
            raise ValueError(f"Numero di ciclo non valido: {cycle_number} (atteso 1-5).")
        validate_spark_plan(plan)
    for character, plan in character_spark_plan.items():
        validate_signature_spark(plan)

    established = build_five_cycle_schedule(child, top4_ordered)
    derived_plan = derive_cycle_spark_plan_from_signature_sparks(established, character_spark_plan)
    effective_plan = _merge_cycle_spark_plans(spark_plan, derived_plan)
    modified_aptitudes = apply_spark_plan_to_aptitudes(established, effective_plan, aptitudes)

    group_members = [child] + list(top4_ordered)
    resolved_per_member = resolve_group_achievable(group_members, races, modified_aptitudes, calendar, mode, min_aptitude)
    cycles = build_cycle_details(
        established, matrix, name_map, character_ids, id_weights, resolved_per_member,
    )
    total_loop_affinity = sum(c["overall_affinity"] for c in cycles)
    spark_warnings = {
        cycle_number: msg
        for cycle_number, plan in effective_plan.items()
        if (msg := spark_plan_warning(plan)) is not None
    }
    return {
        "cycles": cycles,
        "total_loop_affinity": total_loop_affinity,
        "spark_warnings": spark_warnings,
        "_resolved_per_member": resolved_per_member,
        "_modified_aptitudes": modified_aptitudes,
    }


def find_best_substitution(child, top4_ordered, spark_plan, matrix, name_map,
                            character_ids, id_weights, calendar, races, aptitudes,
                            mode, min_aptitude, candidate_pool, character_spark_plan=None):
    """
    Con un piano spark FISSO (stesso per tutti i confronti -- la Modalita' A
    segue la posizione nel ciclo, vedi sopra), cerca tra le posizioni
    sostituibili del loop il singolo candidato esterno che, se sostituito,
    massimizza la Total Loop Affinity risultante. NON sono mai sostituibili:
    'child' (il personaggio originariamente scelto) e, se presente,
    qualunque personaggio con un piano Modalita' B (character_spark_plan) --
    non avrebbe senso "sostituire" una carta reale specifica che si sta
    proprio analizzando. Controlla automaticamente tutte le posizioni
    sostituibili rimanenti, ma ritorna un SOLO risultato: la migliore
    sostituzione trovata in assoluto (un personaggio sostituito, non piu' di
    uno alla volta).

    candidate_pool: personaggi tra cui cercare (gia' filtrati a monte per
    Global/posseduti, come per gli altri endpoint). Vengono scartati
    automaticamente i membri gia' nel gruppo e chiunque condivida il nome
    base con un membro del gruppo che NON e' quello da sostituire (stessa
    regola anti-duplicato-variante usata altrove).

    Ritorna dict con:
      baseline_group, baseline_total_loop_affinity: il gruppo attuale e il
        suo punteggio (con lo stesso piano spark applicato).
      best_substitution: None se nessuna sostituzione migliora il punteggio,
        altrimenti {position, old_character, new_character,
        total_loop_affinity, delta}.
    """
    character_spark_plan = character_spark_plan or {}

    baseline = one_hop_exploration_with_sparks(
        child, top4_ordered, spark_plan, matrix, name_map,
        character_ids, id_weights, calendar, races, aptitudes, mode, min_aptitude,
        character_spark_plan=character_spark_plan,
    )
    baseline_total = baseline["total_loop_affinity"]

    current_group = [child] + list(top4_ordered)
    current_group_set = set(current_group)
    protected = {child} | set(character_spark_plan.keys())

    best = None
    for position, old_character in enumerate(top4_ordered):
        if old_character in protected:
            continue
        other_bases = {
            base_character(c) for c in current_group if c != old_character
        }
        for candidate in candidate_pool:
            if candidate in current_group_set:
                continue
            if base_character(candidate) in other_bases:
                continue
            trial_top4 = list(top4_ordered)
            trial_top4[position] = candidate
            trial = one_hop_exploration_with_sparks(
                child, trial_top4, spark_plan, matrix, name_map,
                character_ids, id_weights, calendar, races, aptitudes, mode, min_aptitude,
                character_spark_plan=character_spark_plan,
            )
            trial_total = trial["total_loop_affinity"]
            if best is None or trial_total > best["total_loop_affinity"]:
                best = {
                    "position": position,
                    "old_character": old_character,
                    "new_character": candidate,
                    "total_loop_affinity": trial_total,
                    "delta": trial_total - baseline_total,
                }

    if best is not None and best["total_loop_affinity"] <= baseline_total:
        best = None  # nessuna sostituzione migliora davvero il punteggio attuale

    return {
        "baseline_group": current_group,
        "baseline_total_loop_affinity": baseline_total,
        "best_substitution": best,
    }
