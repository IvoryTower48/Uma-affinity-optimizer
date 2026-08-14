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
export/import, quella e' una traduzione separata per quando si costruira'
quella feature).

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

PARENT_SLOTS = ("parent1", "parent2")


def _normalize_all(veterans: list) -> tuple[list, bool]:
    """Aggiunge i campi assenti nei record scritti prima che esistessero --
    solo in lettura, ma essendo una migrazione la scrive UNA SOLA VOLTA (vedi
    get_veterans) cosi' resta stabile ai letture successive.

    'name' di ripiego per i veterani creati prima di questo campo: NUMERATO
    (non lasciato ambiguo) -- un batch di veterani gia' esistenti con lo
    stesso personaggio (es. piu' "Aston Machan" creati prima di questa
    funzionalita', caso reale segnalato dall'utente 2026-08-15) riceve
    "<Personaggio> #1", "#2", ecc. nell'ordine in cui compaiono nel file,
    esattamente come se fossero stati creati uno alla volta con
    add_veteran. Rinominabile dopo (vedi rename_veteran) se l'ordine non
    corrisponde a quello reale (non ricostruibile con certezza)."""
    changed = False
    counts = {}
    for v in veterans:
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


def add_veteran(data_dir, character: str) -> dict:
    """Crea un nuovo veterano vuoto (nessuna spark, nessun genitore noto
    ancora) per 'character'. Nome di default "<Personaggio> #N" (N = quanti
    veterani con lo stesso personaggio esistono gia' + 1) -- distingue le
    "copie" fin da subito, rinominabile dopo (vedi rename_veteran). Ritorna
    il record creato, con 'id' assegnato (uuid4 esadecimale)."""
    veterans = get_veterans(data_dir)
    existing_count = sum(1 for v in veterans if v["character"] == character)
    record = {
        "id": uuid.uuid4().hex, "character": character,
        "name": f"{format_character_name(character)} #{existing_count + 1}",
        "white_sparks": [], "race_sparks": [],
        "parent1": None, "parent2": None,
    }
    veterans.append(record)
    _save_veterans(data_dir, veterans)
    return record


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


def set_veteran_sparks(data_dir, veteran_id: str, white_sparks: list, race_sparks: list) -> list:
    """Sostituisce per intero le spark PROPRIE del veterano (non quelle dei
    suoi genitori, vedi set_veteran_parent per quelle) -- stesso principio di
    sostituzione piena gia' usato li': il chiamante manda sempre la lista
    completa desiderata (add/rimuovi una spark = ricalcolare la lista lato
    client e rimandarla tutta), gia' validate a monte (vedi app.py).
    Sostituisce la vecchia apply_spark_to_veterans (bulk "applica a piu'
    veterani insieme"), rimossa su richiesta esplicita dell'utente
    (2026-08-15): con veterani dello stesso personaggio ma copie diverse,
    quel flusso rendeva troppo facile applicare la spark sbagliata alla
    copia sbagliata -- ogni veterano si modifica ora individualmente, come
    i suoi genitori."""
    veterans = get_veterans(data_dir)
    veteran = next((v for v in veterans if v["id"] == veteran_id), None)
    if veteran is None:
        raise ValueError("Veterano non trovato.")
    veteran["white_sparks"] = white_sparks
    veteran["race_sparks"] = race_sparks
    _save_veterans(data_dir, veterans)
    return veterans


def set_veteran_parent(data_dir, veteran_id: str, slot: str, character: str | None,
                        white_sparks: list, race_sparks: list) -> list:
    """
    Imposta (o cancella) un genitore NOTO del veterano -- vedi il commento in
    cima al modulo per cosa rappresenta. Sostituzione PIENA dello slot (mai
    un merge): character None/vuoto cancella lo slot per intero, ignorando
    eventuali spark passate (non avrebbe senso una spark senza un
    personaggio a cui appartiene). white_sparks/race_sparks gia' validate
    dal chiamante (vedi app.py), non ricontrollate qui.

    Solleva ValueError se lo slot non e' 'parent1'/'parent2' o il veterano
    non esiste. Ritorna la lista aggiornata di TUTTI i veterani.
    """
    if slot not in PARENT_SLOTS:
        raise ValueError(f"Slot genitore non valido: '{slot}' (atteso 'parent1' o 'parent2').")
    veterans = get_veterans(data_dir)
    veteran = next((v for v in veterans if v["id"] == veteran_id), None)
    if veteran is None:
        raise ValueError("Veterano non trovato.")

    if not character:
        veteran[slot] = None
    else:
        veteran[slot] = {
            "character": character,
            "white_sparks": white_sparks or [],
            "race_sparks": race_sparks or [],
        }
    _save_veterans(data_dir, veterans)
    return veterans


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


