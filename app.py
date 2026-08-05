# -*- coding: utf-8 -*-
"""
Server locale Flask per la UI del Uma Legacy Loop Optimizer.
Riusa interamente i moduli di calcolo gia' scritti per la CLI (main.py) --
nessuna logica di dominio duplicata qui, solo caricamento dati + routing.

Uso:
    python3 app.py
    poi apri http://localhost:5000 nel browser

Costo: zero. Gira solo sul PC di chi lo lancia, nessun hosting.
"""
from flask import Flask, render_template, request, jsonify, Response, send_file, abort
import argparse
import os
import sys
import threading
import time
import webbrowser

import pdf_export

from config import META_PARENTS, MIN_APTITUDE, app_dir
from naming import base_character, resolve_character_input
from display_names import format_character_name
from data_loader import (
    load_base_affinity_data, load_aptitudes, load_races,
    load_mandatory_races, load_character_info, build_character_calendar,
    apply_global_filter,
)
from loop_search import (
    build_score_matrix, top_n_by_field, best_loop, shortlist_candidates,
    best_loop_with_fixed, shortlist_candidates_for_fixed,
)
from cycle_analysis import (
    one_hop_exploration, first_cycle_shared_races, all_cycles_shared_races,
    one_hop_exploration_with_sparks, find_best_substitution,
)
from timeline import build_calendar_matrix
import data_updater

def resource_path(*parts):
    """
    Percorso di una risorsa BUNDLATA in sola lettura (templates/static): dentro
    l'eseguibile impacchettato (PyInstaller estrae in sys._MEIPASS) se il
    programma gira "frozen", altrimenti la cartella di questo file sorgente.
    Diversa da config.app_dir() (quella e' per 'data/', che deve restare
    scrivibile accanto all'exe, mai dentro sys._MEIPASS).
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)

DATA_DIR = os.path.join(app_dir(), "data")

# --- flag opzionali da riga di comando per abilitare/disabilitare
# l'aggiornamento automatico dal PROSSIMO avvio in poi (persistito, vedi
# data_updater.is_auto_update_enabled/set_auto_update_enabled). Puramente
# additivi: non richiesti per l'uso normale, `python3 app.py` da solo
# continua a funzionare come sempre (aggiornamento abilitato di default).
_arg_parser = argparse.ArgumentParser(add_help=False)
_arg_group = _arg_parser.add_mutually_exclusive_group()
_arg_group.add_argument(
    "--disable-auto-update", action="store_true",
    help="Disattiva l'aggiornamento automatico dei dati (da questo avvio in poi).",
)
_arg_group.add_argument(
    "--enable-auto-update", action="store_true",
    help="Riattiva l'aggiornamento automatico dei dati (se era stato disattivato).",
)
_arg_parser.add_argument(
    "--no-browser", action="store_true",
    help="Non aprire automaticamente il browser all'avvio (utile per lo sviluppo).",
)
_cli_args, _ = _arg_parser.parse_known_args()
if _cli_args.disable_auto_update:
    data_updater.set_auto_update_enabled(DATA_DIR, False)
    print("[data_updater] Aggiornamento automatico DISATTIVATO (resta cosi' anche ai prossimi avvii).")
elif _cli_args.enable_auto_update:
    data_updater.set_auto_update_enabled(DATA_DIR, True)
    print("[data_updater] Aggiornamento automatico RIATTIVATO.")

# --- aggiornamento automatico dei dati da internet, al massimo ogni 24 ore ---
# (nuovi ID di affinita'/pesi, nuovi personaggi, date di rilascio Global, nuove
# varianti/costumi -- vedi data_updater.py). Non richiede alcun input
# dell'utente; un problema di rete non blocca l'avvio (si usano i dati gia'
# presenti), e un budget di tempo complessivo (MAX_UPDATE_SECONDS) protegge
# anche da una rete molto lenta. Il report completo viene comunque scritto in
# data/last_update_report.json ad ogni esecuzione, per controllo. Puo' essere
# disattivato con --disable-auto-update (vedi sopra).
_update_report = data_updater.maybe_run_update(DATA_DIR)
if _update_report is not None:
    print("[data_updater] Aggiornamento dati eseguito, vedi data/last_update_report.json")
    if _update_report.get("errors"):
        print(f"[data_updater] Attenzione, errori: {_update_report['errors']}")
    if _update_report.get("stopped_early"):
        print(f"[data_updater] Attenzione, budget di tempo ({data_updater.MAX_UPDATE_SECONDS}s) "
              f"esaurito: alcuni controlli sono stati rimandati al prossimo avvio.")

# --- caricamento dati una sola volta all'avvio ---
character_ids, id_weights = load_base_affinity_data(DATA_DIR)
aptitudes = load_aptitudes(DATA_DIR)
races = load_races(DATA_DIR)
mandatory_races = load_mandatory_races(DATA_DIR)
calendar = build_character_calendar(mandatory_races, races)
name_map, releases = load_character_info(DATA_DIR)

ALL_CHARACTERS = sorted(aptitudes.keys())
BASE_NAMES = sorted(set(base_character(c) for c in ALL_CHARACTERS))

# matrici precalcolate per entrambe le modalita' (dataset piccolo, costo trascurabile)
MATRICES = {
    mode: build_score_matrix(
        ALL_CHARACTERS, name_map, character_ids, id_weights,
        calendar, races, aptitudes, mode,
    )
    for mode in ("career", "mant")
}


def get_universe(global_only):
    """
    Ritorna (personaggi, avviso_o_None) -- stessa logica della CLI: se
    global_only e' attivo, filtra PRIMA di tutto il resto (target compreso),
    cosi' un personaggio non ancora uscito su Global non e' ne' interrogabile
    ne' proponibile come compagno/loop.
    """
    if not global_only:
        return ALL_CHARACTERS, None
    return apply_global_filter(ALL_CHARACTERS, releases)


def restrict_to_owned(characters, owned):
    """Se 'owned' e' una lista non vuota, restringe 'characters' alla loro intersezione."""
    if not owned:
        return characters
    owned_set = set(owned)
    return [c for c in characters if c in owned_set]


def resolve_targets(name_input, universe):
    """Risolve l'input utente (nome base o variante) a una lista di varianti reali."""
    resolved, candidates = resolve_character_input(name_input, universe)
    if resolved is not None:
        return [resolved]
    return candidates or []


@app.route("/")
def index():
    base_names = [{"id": n, "display": format_character_name(n)} for n in BASE_NAMES]
    return render_template(
        "index.html", base_names=base_names,
        auto_update_enabled=data_updater.is_auto_update_enabled(DATA_DIR),
        min_aptitude=MIN_APTITUDE,
    )


@app.route("/api/auto_update_setting", methods=["GET", "POST"])
def api_auto_update_setting():
    """
    Permette all'utente di attivare/disattivare l'aggiornamento automatico dei
    dati dalla UI (stessa impostazione persistita usata dai flag da riga di
    comando --disable-auto-update/--enable-auto-update). Ha effetto dal
    PROSSIMO avvio del server, non su quello in corso (i dati sono gia'
    stati caricati in memoria all'avvio, vedi maybe_run_update sopra).
    """
    if request.method == "POST":
        enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
        data_updater.set_auto_update_enabled(DATA_DIR, enabled)
    return jsonify({"enabled": data_updater.is_auto_update_enabled(DATA_DIR)})


@app.route("/api/portrait/<path:character>")
def api_portrait(character):
    """
    Ritratto Gametora del personaggio per la UI web (layout moderno) --
    riusa la stessa funzione/cache gia' usata dal PDF (pdf_export), nessuna
    logica duplicata. 404 se non disponibile (rete assente, personaggio non
    trovato su Gametora): il frontend mostra un segnaposto con le iniziali,
    mai un'icona di immagine rotta.
    """
    path = pdf_export.fetch_character_portrait_image(character, DATA_DIR)
    if path is None:
        abort(404)
    return send_file(path)


@app.route("/api/base_names")
def api_base_names():
    """
    Elenco dei nomi base disponibili, filtrato per global_only se richiesto
    (un nome base resta disponibile se almeno una delle sue varianti e' uscita
    su Global). Usato per aggiornare la picklist del personaggio singolo
    coerentemente col filtro Global attivo nella UI.
    """
    global_only = request.args.get("global_only", "false").lower() in ("1", "true", "yes")
    universe, _ = get_universe(global_only)
    names = sorted({base_character(c) for c in universe})
    return jsonify({"base_names": names})


@app.route("/api/characters")
def api_characters():
    """
    Elenco di tutti gli ID (varianti complete, non nomi base) con la relativa
    data di uscita Global (o null se non ancora uscito) e il nome base -- usato
    dal frontend per popolare/ordinare/filtrare tutte le picklist (posseduti,
    personaggio singolo, must-include) senza dover ricaricare la pagina.
    """
    data = [
        {
            "character": c,
            "base": base_character(c),
            "global_release_date": (releases.get(c) or {}).get("global_release_date"),
        }
        for c in ALL_CHARACTERS
    ]
    return jsonify({"characters": data})


@app.route("/api/top4", methods=["POST"])
def api_top4():
    payload = request.get_json()
    name_input = payload.get("character", "")
    mode = payload.get("mode", "career")
    global_only = bool(payload.get("global_only", False))
    owned = payload.get("owned", [])
    debug = bool(payload.get("debug", False))
    matrix = MATRICES[mode]

    universe, warning = get_universe(global_only)
    # il personaggio richiesto puo' anche non essere posseduto (si valuta un
    # target futuro); solo i CANDIDATI proposti vengono ristretti ai posseduti.
    targets = resolve_targets(name_input, universe)
    if not targets:
        msg = f"Personaggio '{name_input}' non trovato"
        msg += " (con il filtro Global attivo)." if global_only else "."
        return jsonify({"error": msg}), 404

    candidate_pool = restrict_to_owned(universe, owned)

    results = []
    for target in targets:
        top4 = top_n_by_field(target, candidate_pool, matrix, n=4)
        entries = []
        for other, score in top4:
            key = (target, other) if target < other else (other, target)
            detail = matrix[key]
            entries.append({
                "character": other,
                "total": detail["total"],
                "base": detail["base"],
                "race": detail["race"],
                "is_meta_parent": other in META_PARENTS,
            })
        result = {"target": target, "top4": entries}

        # calcoli che richiedono il gruppo di 5 al completo (target + top4):
        # matrice calendario, aptitude di base del gruppo, esplorazione a un
        # salto -- SEMPRE, non solo in debug, perche' il pannello "Piano
        # spark" e' sempre visibile e ne ha bisogno (etichette dei cicli,
        # anteprima live delle aptitude).
        if len(entries) == 4:
            group_members = [target] + [e["character"] for e in entries]
            result["calendar_matrix"] = build_calendar_matrix(
                group_members, races, aptitudes, calendar, mode,
            )
            result["group_aptitudes"] = {m: aptitudes[m] for m in group_members}
            one_hop = one_hop_exploration(
                target, [e["character"] for e in entries], matrix,
                name_map, character_ids, id_weights,
                calendar, races, aptitudes, mode,
            )
            resolved_per_member = one_hop.pop("_resolved_per_member")
            one_hop["first_cycle_races"] = first_cycle_shared_races(
                one_hop["cycles"][0], races, resolved_per_member,
            )
            one_hop["all_cycle_races"] = all_cycles_shared_races(
                one_hop["cycles"], races, resolved_per_member,
            )
            result["one_hop"] = one_hop
        else:
            result["one_hop_error"] = (
                f"Servono esattamente 4 personaggi trovati per l'esplorazione "
                f"a un salto (trovati: {len(entries)})."
            )

        # modalita' debug: SOLO le liste top-10 aggiuntive restano dietro il
        # flag (dettaglio diagnostico, non serve al piano spark).
        if debug:
            top10_base = top_n_by_field(target, candidate_pool, matrix, "base", n=10)
            top10_race = top_n_by_field(target, candidate_pool, matrix, "race", n=10)
            top10_total = top_n_by_field(target, candidate_pool, matrix, "total", n=10)
            result["top10_base"] = [
                {"character": c, "value": v} for c, v in top10_base
            ]
            result["top10_race"] = [
                {"character": c, "value": v} for c, v in top10_race
            ]
            result["top10_total"] = [
                {
                    "character": c,
                    "base": matrix[(target, c) if target < c else (c, target)]["base"],
                    "race": matrix[(target, c) if target < c else (c, target)]["race"],
                    "value": v,
                }
                for c, v in top10_total
            ]
        results.append(result)

    return jsonify({"results": results, "warning": warning})


@app.route("/api/pink_spark", methods=["POST"])
def api_pink_spark():
    """
    v3 -- Aptitude Inheritance ("pink spark"), Modalita' A (aggregata per
    categoria/ciclo). Disponibile SOLO per un personaggio con esattamente 4
    trovati (stesso presupposto dell'esplorazione a un salto in debug su
    /api/top4): applica un piano spark ai 5 cicli e ricalcola la Total Loop
    Affinity, poi cerca sull'intero pool posseduto/Global-filtrato se
    sostituire uno dei 4 compagni (mai il personaggio scelto) alzi il
    punteggio.

    Payload atteso:
      character: nome (base o variante) del personaggio scelto (mai sostituito)
      mode: "career" | "mant"
      global_only, owned: stessi filtri degli altri endpoint
      spark_plan: Modalita' A -- dict[str(numero ciclo 1-5)] -> dict
        [categoria] -> stelle totali (un ciclo assente equivale a "nessuna
        spark"). Pensata per pianificare "quante stelle mi servono in un
        punto del loop", senza sapere quale personaggio le portera'.
      character_spark_plan: Modalita' B (2026-07-30) -- dict[nome
        personaggio] -> dict[categoria] -> stelle totali. Il personaggio
        DEVE essere uno dei 5 del gruppo attuale (il target o uno dei suoi
        top-4); pensata per pianificare "questa carta reale ha/avrebbe
        queste spark" -- l'effetto si propaga automaticamente a ogni altro
        punto del loop in cui quel personaggio ricompare (come genitore o
        nonno), dato che l'aptitude e' un dict indicizzato per nome. Un
        personaggio con un piano qui non e' MAI sostituibile dalla ricerca
        di un sostituto (non avrebbe senso "sostituire" la carta che si sta
        proprio analizzando). Le due modalita' sono componibili nella stessa
        richiesta.
    """
    payload = request.get_json()
    name_input = payload.get("character", "")
    mode = payload.get("mode", "career")
    global_only = bool(payload.get("global_only", False))
    owned = payload.get("owned", [])
    raw_spark_plan = payload.get("spark_plan", {})
    raw_character_spark_plan = payload.get("character_spark_plan", {})
    matrix = MATRICES[mode]

    universe, warning = get_universe(global_only)
    targets = resolve_targets(name_input, universe)
    if not targets:
        msg = f"Personaggio '{name_input}' non trovato"
        msg += " (con il filtro Global attivo)." if global_only else "."
        return jsonify({"error": msg}), 404
    if len(targets) > 1:
        return jsonify({
            "error": f"'{name_input}' e' ambiguo tra le varianti: {targets}. "
                     f"Specifica quale con il nome completo."
        }), 400
    target = targets[0]

    candidate_pool = restrict_to_owned(universe, owned)
    top4 = top_n_by_field(target, candidate_pool, matrix, n=4)
    if len(top4) != 4:
        return jsonify({
            "error": f"Servono esattamente 4 personaggi trovati per il piano "
                     f"spark (trovati: {len(top4)}). Controlla i filtri "
                     f"posseduti/Global attivi."
        }), 400
    top4_ordered = [c for c, _ in top4]
    group_members_ordered = [target] + top4_ordered
    group_members_set = set(group_members_ordered)

    try:
        spark_plan = {int(k): v for k, v in raw_spark_plan.items()}
    except (TypeError, ValueError):
        return jsonify({
            "error": "Le chiavi di 'spark_plan' devono essere numeri di ciclo (1-5)."
        }), 400

    character_spark_plan = dict(raw_character_spark_plan)
    unknown = set(character_spark_plan) - group_members_set
    if unknown:
        return jsonify({
            "error": f"'character_spark_plan' contiene personaggi non presenti "
                     f"nel gruppo attuale: {sorted(unknown)}."
        }), 400

    try:
        result = one_hop_exploration_with_sparks(
            target, top4_ordered, spark_plan, matrix, name_map,
            character_ids, id_weights, calendar, races, aptitudes, mode,
            character_spark_plan=character_spark_plan,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    resolved_per_member = result.pop("_resolved_per_member")
    modified_aptitudes = result.pop("_modified_aptitudes")
    result["first_cycle_races"] = first_cycle_shared_races(
        result["cycles"][0], races, resolved_per_member,
    )
    result["all_cycle_races"] = all_cycles_shared_races(
        result["cycles"], races, resolved_per_member,
    )
    # timeline con le aptitude modificate dalle spark -- NON sostituisce
    # quella originale (calcolata a monte in /api/top4 con le aptitude base):
    # il frontend mostra le due come schede separate, la nuova si apre
    # automaticamente quando viene calcolato questo risultato. Stesso ordine
    # di colonne di /api/top4 ([target] + top4_ordered), per coerenza.
    result["calendar_matrix"] = build_calendar_matrix(
        group_members_ordered, races, modified_aptitudes, calendar, mode,
    )

    substitution = find_best_substitution(
        target, top4_ordered, spark_plan, matrix, name_map,
        character_ids, id_weights, calendar, races, aptitudes, mode, candidate_pool,
        character_spark_plan=character_spark_plan,
    )
    result["substitution"] = substitution

    return jsonify({"target": target, "top4": top4_ordered, **result, "warning": warning})


@app.route("/api/loop", methods=["POST"])
def api_loop():
    payload = request.get_json()
    mode = payload.get("mode", "career")
    global_only = bool(payload.get("global_only", False))
    owned = payload.get("owned", [])
    must_include_input = [x for x in payload.get("must_include", []) if x]
    pool_size = int(payload.get("pool_size", 20))
    matrix = MATRICES[mode]

    universe, warning = get_universe(global_only)
    # per il loop, l'INTERO gruppo deve venire dai posseduti (altrimenti il
    # loop non sarebbe realizzabile in pratica).
    universe = restrict_to_owned(universe, owned)
    if len(universe) < 5:
        return jsonify({
            "error": "Servono almeno 5 personaggi posseduti (dopo i filtri attivi) "
                     "per cercare un loop."
        }), 400

    # risolvi ciascun input 'must_include' (accetta nome base o variante,
    # stessa logica di --character) all'interno dell'universo consentito
    fixed_members = []
    if must_include_input:
        if len(must_include_input) > 5:
            return jsonify({"error": "Puoi includere al massimo 5 personaggi."}), 400
        for name_input in must_include_input:
            resolved, candidates = resolve_character_input(name_input, universe)
            if resolved is None:
                if candidates:
                    return jsonify({
                        "error": f"'{name_input}' e' ambiguo tra le varianti: "
                                 f"{candidates}. Specifica quale con il nome completo."
                    }), 400
                return jsonify({
                    "error": f"'{name_input}' non trovato tra i personaggi disponibili "
                             f"(dopo i filtri Global/posseduti attivi)."
                }), 404
            fixed_members.append(resolved)

    try:
        if fixed_members:
            pool = shortlist_candidates_for_fixed(fixed_members, universe, matrix, pool_size=pool_size)
            group, score = best_loop_with_fixed(fixed_members, pool, matrix)
        else:
            pool = shortlist_candidates(universe, matrix, pool_size=pool_size)
            group, score = best_loop(pool, matrix)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if group is None:
        return jsonify({
            "error": "Non e' stato possibile trovare un loop completo con questi "
                     "vincoli (pool troppo ristretto dopo aver escluso basi duplicate)."
        }), 400

    members = [{"character": c, "is_meta_parent": c in META_PARENTS} for c in group]
    calendar_matrix = build_calendar_matrix(list(group), races, aptitudes, calendar, mode)
    return jsonify({
        "pool": pool, "group": members, "total_score": score, "warning": warning,
        "calendar_matrix": calendar_matrix,
    })


@app.route("/api/export_pdf", methods=["POST"])
def api_export_pdf():
    """
    Documento PDF illustrato (1-2 pagine, ultima feature del modulo v3 --
    vedi HANDOFF.md) del loop attualmente mostrato in UI: stesso contenuto
    sostanziale del salvataggio JSON (target, mode, cycles, all_cycle_races,
    total_loop_affinity, spark_plan/spark_warnings/substitution se presenti),
    assemblato lato client da 'lastRun'/il risultato del piano spark gia'
    calcolato -- nessun ricalcolo qui, solo generazione del documento.
    Scarica le immagini (ritratti, targhe gara) al volo da Gametora/uma.guide
    -- se la rete non e' disponibile il PDF viene comunque generato, solo
    senza quelle immagini (vedi pdf_export.py).
    """
    payload = request.get_json()
    if not payload or "cycles" not in payload:
        return jsonify({"error": "Payload mancante o incompleto (serve almeno 'cycles')."}), 400
    try:
        pdf_bytes = pdf_export.build_loop_pdf(payload, data_dir=DATA_DIR)
    except Exception as e:
        return jsonify({"error": f"Errore nella generazione del PDF: {e}"}), 500

    filename = f"Loop_{payload.get('target', 'loop')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Chiusura automatica quando si chiude la scheda del browser ------------
# Richiesta esplicita dell'utente: chiudere SOLO la scheda aperta dal
# programma deve terminare anche il server (niente console/processo che
# resta acceso in background senza che l'utente se ne accorga). Il browser
# non notifica mai direttamente un server quando una scheda si chiude --
# l'approccio usato e' tenere aperta una connessione SSE per tutta la vita
# della pagina (script.js apre un EventSource verso /api/heartbeat all'avvio):
# finche' la scheda resta aperta la connessione resta aperta; quando si
# chiude (o si naviga altrove), il browser la interrompe e il generatore qui
# sotto se ne accorge al tentativo di invio successivo. Un refresh (F5) crea
# una nuova connessione quasi subito, quindi si aspetta un breve periodo di
# grazia (HEARTBEAT_GRACE_SECONDS) con ZERO connessioni attive prima di
# considerare il programma davvero chiuso e uscire.
HEARTBEAT_PING_SECONDS = 1.5
HEARTBEAT_GRACE_SECONDS = 4
_heartbeat_lock = threading.Lock()
_heartbeat_state = {"connections": 0, "zero_since": None, "ever_connected": False}


@app.route("/api/heartbeat")
def api_heartbeat():
    def stream():
        with _heartbeat_lock:
            _heartbeat_state["connections"] += 1
            _heartbeat_state["zero_since"] = None
            _heartbeat_state["ever_connected"] = True
        try:
            while True:
                yield "data: ping\n\n"
                time.sleep(HEARTBEAT_PING_SECONDS)
        finally:
            with _heartbeat_lock:
                _heartbeat_state["connections"] -= 1
                if _heartbeat_state["connections"] <= 0:
                    _heartbeat_state["connections"] = 0
                    _heartbeat_state["zero_since"] = time.time()

    return Response(stream(), mimetype="text/event-stream")


def _shutdown_when_no_tabs_left():
    """Gira su un thread daemon separato: chiude il processo quando nessuna
    scheda del programma e' rimasta aperta per piu' di HEARTBEAT_GRACE_SECONDS.
    Non fa nulla finche' non si e' MAI connessa una scheda (ever_connected),
    cosi' non chiude subito il server all'avvio prima che il browser abbia
    fatto in tempo ad aprirsi. os._exit() invece di sys.exit(): quest'ultimo
    termina solo il thread corrente, non l'intero processo."""
    while True:
        time.sleep(1)
        with _heartbeat_lock:
            ever_connected = _heartbeat_state["ever_connected"]
            zero_since = _heartbeat_state["zero_since"]
        if ever_connected and zero_since is not None:
            if time.time() - zero_since > HEARTBEAT_GRACE_SECONDS:
                print("[app] Nessuna scheda del programma piu' aperta: chiudo il server.")
                sys.stdout.flush()  # os._exit() salta il flush normale dell'interprete
                os._exit(0)


if __name__ == "__main__":
    # Apre il browser di sistema da solo (a meno di --no-browser, usato per lo
    # sviluppo/test): l'utente non deve aprire manualmente localhost:5000.
    # Ritardo breve su un thread separato perche' app.run() e' bloccante --
    # il server deve gia' essere in ascolto quando il browser prova a
    # connettersi. Fallisce in silenzio se non c'e' un browser disponibile
    # (es. ambiente headless): non deve mai impedire l'avvio del server.
    if not _cli_args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    # Watchdog di chiusura SEMPRE attivo (non solo quando apriamo noi il
    # browser): innocuo se nessuna scheda si connette mai a /api/heartbeat
    # (ever_connected resta False, non scatta mai). Se una scheda si
    # connette e poi si chiude senza che ne resti aperta un'altra, il
    # server esce da solo -- vale anche con --no-browser (scheda aperta a
    # mano durante lo sviluppo), scelta deliberata per restare un
    # comportamento unico e prevedibile invece di un caso speciale.
    threading.Thread(target=_shutdown_when_no_tabs_left, daemon=True).start()
    # threaded=True: la connessione SSE di /api/heartbeat resta aperta per
    # tutta la vita della scheda -- senza thread multipli bloccherebbe ogni
    # altra richiesta (server di sviluppo Werkzeug, un thread per richiesta).
    app.run(port=5000, threaded=True)
