# -*- coding: utf-8 -*-
"""
Libreria PERMANENTE dei "veterani" (genitori/nonni gia' allevati, con le
proprie spark) -- persistita in data/veterans.json, indipendente da un
singolo piano ace/loop (lo stesso veterano si riusa in piu' piani diversi,
proprio come una carta genitore reale in gioco).

Per ora traccia solo white spark e race spark (le uniche richieste ora):
- pink e' gia' gestita altrove con un meccanismo diverso, per-ciclo, non
  legato a un veterano permanente (vedi aptitude_inheritance.py) -- non va
  duplicata qui.
- blue (solo 5 statistiche fisse) e green (nessun nome da cercare, un solo
  flag/livello per personaggio) non richiedono un catalogo da consultare:
  verranno aggiunti come campi semplici quando servira', non ora.

Ogni veterano: {id, character, name, white_sparks: [...], race_sparks: [...],
parent1, parent2}, dove ogni spark e' {spark_id, name_en, stars} (spark_id =
campo 'id' dei cataloghi data/spark_skill.json / data/spark_race.json, vedi
data_updater.py -- NON il 'tid' compatto usato da Gametora per il proprio
export/import, quella e' una traduzione separata (vedi veterans_gametora.py).

name: etichetta scelta dall'utente (di default "<Personaggio> #N", N =
conteggio tra i veterani con lo stesso 'character' al momento della
creazione -- MAI ricalcolato dopo, resta stabile anche se altri veterani
vengono creati/rimossi in seguito). Serve perche' un veterano rappresenta
una "copia" del personaggio template, personalizzata dalle sue spark: senza
un nome proprio, piu' copie dello stesso personaggio sono indistinguibili
in una lista (bug segnalato dall'utente, 2026-08-15, con screenshot: piu'
"Aston Machan" tutti uguali nell'elenco). Rinominabile in qualsiasi momento
(vedi rename_veteran) -- 'character' invece non cambia mai dopo la
creazione, resta il riferimento al personaggio template vero e proprio.

parent1/parent2: i genitori NOTI del veterano stesso (None se ignoti) --
quando questo veterano viene importato come genitore diretto di un ace,
questi diventano i NONNI dell'ace (vedi conversazione 2026-08-14: prima di
"risolvere" quell'import bisognava correggere QUI la creazione del
veterano, che non teneva traccia dei suoi genitori). Ciascuno, se noto, ha
la STESSA forma di un veterano ridotto: {character, white_sparks,
race_sparks} -- ma NON e' un veterano a se' stante (niente id proprio,
niente ricorsione su ULTERIORI genitori: un veterano ha al massimo 2
generazioni note, coerente con l'albero a 3 generazioni ace/genitori/nonni
e con Gametora stesso, la cui scheda "Veteran" si ferma a "Legacy 1/2").
"""
import json
import uuid
from pathlib import Path

from display_names import format_character_name

def _card_id_from_green(holder: dict):
    greens = holder.get("green_sparks") or []
    return int(greens[0]["spark_id"]) if greens and str(greens[0].get("spark_id", "")).isdigit() else None


def _normalize_all(veterans: list) -> tuple[list, bool]:
    """Aggiunge i campi assenti nei record scritti prima che esistessero --
    solo in lettura, ma essendo una migrazione la scrive UNA SOLA VOLTA (vedi
    get_veterans) cosi' resta stabile ai letture successive.

    'name' di ripiego per i veterani creati prima di questo campo: NUMERATO
    (non lasciato ambiguo) -- un batch di veterani gia' esistenti con lo
    stesso personaggio (es. piu' "Aston Machan" creati prima di questa
    funzionalita', caso reale segnalato dall'utente 2026-08-15) riceve
    "<Personaggio> #1", "#2", ecc. nell'ordine in cui compaiono nel file,
    esattamente come la numerazione degli import. Rinominabile dopo (vedi rename_veteran) se l'ordine non
    corrisponde a quello reale (non ricostruibile con certezza)."""
    changed = False
    counts = {}
    for v in veterans:
        # Costume vero (card_id, 2026-11-22) per i veterani importati prima:
        # l'id della spark verde E' il card_id della carta. Fissato una volta,
        # cosi' modificare le spark nel tool non cambia il costume.
        for holder in (v, v.get("parent1"), v.get("parent2")):
            if holder is not None and "card_id" not in holder:
                holder["card_id"] = _card_id_from_green(holder)
                changed = True
        if "parent1" not in v:
            v["parent1"] = None
            changed = True
        if "parent2" not in v:
            v["parent2"] = None
            changed = True
        if "name" not in v:
            counts[v["character"]] = counts.get(v["character"], 0) + 1
            v["name"] = f"{format_character_name(v['character'])} #{counts[v['character']]}"
            changed = True
    return veterans, changed


def _veterans_path(data_dir) -> Path:
    return Path(data_dir) / "veterans.json"


def get_veterans(data_dir) -> list:
    """Elenco dei veterani salvati (lista vuota se non ancora creato nessuno).
    Migra sul posto i record scritti prima di un campo nuovo (vedi
    _normalize_all) -- se qualcosa e' cambiato, lo scrive subito su disco
    (una tantum), cosi' la migrazione resta stabile invece di ricalcolare
    (potenzialmente diverso) ad ogni lettura."""
    path = _veterans_path(data_dir)
    if not path.exists():
        return []
    try:
        veterans = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return []
    veterans, changed = _normalize_all(veterans)
    if changed:
        _save_veterans(data_dir, veterans)
    return veterans


def _save_veterans(data_dir, veterans: list) -> None:
    path = _veterans_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(veterans, ensure_ascii=False, indent=2), encoding="utf-8")


def rename_veteran(data_dir, veteran_id: str, name: str) -> list:
    """Rinomina un veterano (solo l'etichetta 'name', mai 'character'). Il
    nome non puo' essere vuoto -- se l'utente vuole "resettarlo" sceglie un
    nome a piacere, non c'e' un default speciale da poter tornare a
    scegliere qui (il default numerato vale solo alla creazione). Ritorna
    la lista aggiornata di tutti i veterani."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Il nome del veterano non puo' essere vuoto.")
    veterans = get_veterans(data_dir)
    veteran = next((v for v in veterans if v["id"] == veteran_id), None)
    if veteran is None:
        raise ValueError("Veterano non trovato.")
    veteran["name"] = name
    _save_veterans(data_dir, veterans)
    return veterans


def import_veterans(data_dir, parsed_veterans: list) -> list:
    """
    Crea in blocco veterani gia' completi (personaggio + spark proprie +
    genitori noti, gia' pronti come {character, white_sparks, race_sparks,
    parent1, parent2}) -- usato dall'import da Gametora
    (vedi veterans_gametora.parse_gametora_import), UN SOLO salvataggio su
    disco invece di N chiamate separate. Il nome di ciascuno segue la
    numerazione "<Personaggio> #N" (per personaggio, in base a quanti ne
    esistono gia') -- CONTA anche i veterani appena aggiunti nello stesso
    batch, cosi' piu' veterani importati insieme con lo stesso personaggio
    restano distinti fin da subito, non tutti "#1". Ritorna la lista
    aggiornata di TUTTI i veterani (esistenti + importati)."""
    veterans = get_veterans(data_dir)
    for parsed in parsed_veterans:
        existing_count = sum(1 for v in veterans if v["character"] == parsed["character"])
        veterans.append({
            "id": uuid.uuid4().hex,
            "character": parsed["character"],
            "name": f"{format_character_name(parsed['character'])} #{existing_count + 1}",
            "white_sparks": parsed["white_sparks"],
            "race_sparks": parsed["race_sparks"],
            "parent1": parsed["parent1"],
            "parent2": parsed["parent2"],
        })
    _save_veterans(data_dir, veterans)
    return veterans


def _source_key(veteran: dict):
    """(viewer_id, trained_chara_id) di un veterano importato da file
    umadump, None per uno creato a mano o importato da Gametora."""
    source = veteran.get("source") or {}
    if source.get("type") != "umadump":
        return None
    return source.get("viewer_id"), source.get("trained_chara_id")


def sync_imported_veterans(data_dir, parsed_veterans: list, full: bool) -> tuple:
    """
    Import da file umadump (regole dell'utente, 2026-11-21):
    - un veterano nuovo viene aggiunto (nome "Personaggio — memo" o
      "Personaggio #N", vedi veterans_umadump.default_name);
    - uno gia' presente (stesso giocatore + stesso id nel gioco) resta
      com'e', comprese le modifiche fatte nel tool (nome, spark);
    - con un inventario COMPLETO (full), i veterani importati da file dello
      stesso giocatore che non ci sono piu' vengono cancellati (trasferiti
      in gioco). Quelli di altri giocatori (presi in prestito) e quelli
      creati a mano o importati da Gametora non vengono mai toccati.
    Ritorna (tutti i veterani, {added, unchanged, removed}).
    """
    from veterans_umadump import default_name

    veterans = get_veterans(data_dir)
    existing_keys = {_source_key(v) for v in veterans} - {None}
    incoming_keys = {_source_key(p) for p in parsed_veterans}
    stats = {"added": 0, "unchanged": 0, "removed": 0}

    if full:
        viewers = {key[0] for key in incoming_keys}
        kept = [v for v in veterans
                if not (_source_key(v) and _source_key(v)[0] in viewers and _source_key(v) not in incoming_keys)]
        stats["removed"] = len(veterans) - len(kept)
        veterans = kept

    for parsed in parsed_veterans:
        if _source_key(parsed) in existing_keys:
            stats["unchanged"] += 1
            continue
        count = sum(1 for v in veterans if v["character"] == parsed["character"])
        record = {k: v for k, v in parsed.items() if k != "memo"}
        veterans.append({"id": uuid.uuid4().hex,
                         "name": default_name(parsed["character"], parsed["memo"], count), **record})
        stats["added"] += 1
    _save_veterans(data_dir, veterans)
    return veterans, stats


def delete_veteran(data_dir, veteran_id: str) -> bool:
    """Rimuove il veterano con quell'id. Ritorna True se trovato e rimosso,
    False se l'id non esisteva (nessun errore, il chiamante decide come
    segnalarlo)."""
    veterans = get_veterans(data_dir)
    remaining = [v for v in veterans if v["id"] != veteran_id]
    if len(remaining) == len(veterans):
        return False
    _save_veterans(data_dir, remaining)
    return True


