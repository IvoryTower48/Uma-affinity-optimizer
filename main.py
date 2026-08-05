# -*- coding: utf-8 -*-
"""
CLI del tool di ottimizzazione dei legacy loop per Umamusume.

Uso base:
    python3 main.py --data-dir data --character mejiro_mcqueen
    python3 main.py --data-dir data --loop --pool-size 20
    python3 main.py --data-dir data --loop --mode mant

Note:
- Il mapping slug -> nome giapponese e le date di uscita Global vivono in un unico
  file: data/character_info.csv (colonne: character,jp_name,global_release_date).
  Se assente o incompleto, la componente di affinita' di base risulta 0 per i
  personaggi non mappati (lo script lo segnala esplicitamente, non lo nasconde),
  e il filtro --global-only viene ignorato con un avviso se il file manca.
"""
import argparse
import sys

from config import META_PARENTS, LOOP_SIZE
from naming import base_character, variant_group, resolve_character_input
from display_names import format_character_name
import data_updater
from data_loader import (
    load_base_affinity_data, load_aptitudes, load_races,
    load_mandatory_races, load_character_info, build_character_calendar,
    apply_global_filter,
)
from loop_search import (
    build_score_matrix, top_n_by_field, best_loop, shortlist_candidates,
)


def report_missing_name_map(characters, name_map):
    missing = sorted(c for c in characters if c not in name_map)
    if missing:
        print(f"[avviso] {len(missing)} personaggi/varianti senza mapping verso il "
              f"nome giapponese in character_info.csv (affinita' di base = 0 per "
              f"questi): {missing[:10]}" + (" ..." if len(missing) > 10 else ""))


def annotate_variants(group, all_characters):
    """Genera le note informative su varianti alternative per i personaggi nel gruppo."""
    groups = variant_group(all_characters)
    notes = []
    for char in group:
        base = base_character(char)
        siblings = [v for v in groups.get(base, []) if v != char]
        if siblings:
            notes.append(
                f"  \u26a0 {format_character_name(char)} ha anche variante/i "
                f"alternativa/e con aptitude diverse: "
                f"{', '.join(format_character_name(s) for s in siblings)}"
            )
    return notes


def main():
    parser = argparse.ArgumentParser(description="Uma Legacy Loop Optimizer")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--mode", choices=["career", "mant"], default="career",
                         help="career = rispetta il calendario obbligato; "
                              "mant = nessun vincolo di calendario")
    parser.add_argument("--character", help="Mostra i top-4 compatibili per questo personaggio")
    parser.add_argument("--loop", action="store_true", help="Cerca il miglior loop a 5")
    parser.add_argument("--pool-size", type=int, default=20,
                         help="Dimensione del pool ristretto per la ricerca esaustiva del loop")
    parser.add_argument("--global-only", action="store_true",
                         help="Considera solo personaggi gia' usciti su Global")
    args = parser.parse_args()

    update_report = data_updater.maybe_run_update(args.data_dir)
    if update_report is not None:
        print("[data_updater] Aggiornamento dati eseguito, vedi "
              f"{args.data_dir}/last_update_report.json")
        if update_report.get("errors"):
            print(f"[data_updater] Attenzione, errori: {update_report['errors']}")

    print(f"Caricamento dati da '{args.data_dir}'...")
    character_ids, id_weights = load_base_affinity_data(args.data_dir)
    aptitudes = load_aptitudes(args.data_dir)
    races = load_races(args.data_dir)
    mandatory_races = load_mandatory_races(args.data_dir)
    calendar = build_character_calendar(mandatory_races, races)
    name_map, releases = load_character_info(args.data_dir)

    all_characters = sorted(aptitudes.keys())
    report_missing_name_map(all_characters, name_map)

    if args.global_only:
        before = len(all_characters)
        all_characters, warning = apply_global_filter(all_characters, releases)
        if warning:
            print(f"[avviso] {warning}")
        print(f"Filtro Global: {before} -> {len(all_characters)} personaggi")

    print(f"Modalita' di calcolo: {args.mode}")
    print(f"Personaggi considerati: {len(all_characters)}")

    if args.character:
        resolved, candidates = resolve_character_input(args.character, all_characters)
        if resolved is None and not candidates:
            sys.exit(f"Personaggio '{args.character}' non trovato tra quelli caricati.")

        # ambiguo: rif. a piu' varianti -> esegue lo stesso comando per ciascuna
        targets = candidates if resolved is None else [resolved]
        if resolved is None:
            print(f"[info] '{args.character}' e' ambiguo, corrisponde a piu' varianti "
                  f"({', '.join(format_character_name(t) for t in targets)}): "
                  f"mostro i risultati per ciascuna.")
        elif resolved != args.character:
            print(f"[info] '{args.character}' interpretato come "
                  f"'{format_character_name(resolved)}'")

        matrix = build_score_matrix(
            all_characters, name_map, character_ids, id_weights,
            calendar, races, aptitudes, args.mode,
        )
        for target in targets:
            top4 = top_n_by_field(target, all_characters, matrix, n=4)
            print(f"\nTop-4 compatibili con {format_character_name(target)}:")
            for other, score in top4:
                key = (target, other) if target < other else (other, target)
                detail = matrix[key]
                meta_tag = " [GENITORE META]" if other in META_PARENTS else ""
                print(f"  {format_character_name(other):40s} totale={score:6.1f}  "
                      f"(base={detail['base']}, race={detail['race']}){meta_tag}")

    if args.loop:
        matrix = build_score_matrix(
            all_characters, name_map, character_ids, id_weights,
            calendar, races, aptitudes, args.mode,
        )
        pool = shortlist_candidates(all_characters, matrix, pool_size=args.pool_size)
        print(f"\nPool ristretto per la ricerca del loop ({len(pool)} personaggi): "
              f"{[format_character_name(c) for c in pool]}")
        group, score = best_loop(pool, matrix, loop_size=LOOP_SIZE)
        print(f"\nMiglior loop trovato (punteggio totale={score:.1f}):")
        for char in group:
            meta_tag = " [GENITORE META]" if char in META_PARENTS else ""
            print(f"  - {format_character_name(char)}{meta_tag}")
        notes = annotate_variants(group, all_characters)
        if notes:
            print("\nNote:")
            for n in notes:
                print(n)


if __name__ == "__main__":
    main()
