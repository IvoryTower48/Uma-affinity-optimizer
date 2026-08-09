# -*- coding: utf-8 -*-
"""
Costanti di progetto per il tool di ottimizzazione dei legacy loop di Umamusume.
Tutti i valori qui sono regole di gioco fisse o scelte di design confermate in chat,
non dati per-personaggio (quelli vivono nei file in data/).
"""
import json
import os
import sys


def app_dir():
    """
    Cartella base per i dati persistenti ('data/'): quella dell'eseguibile
    impacchettato (PyInstaller, vedi build_exe.py) se il programma gira
    "frozen", altrimenti quella di questo file sorgente. MAI la cartella
    temporanea interna del bundle (sys._MEIPASS) -- quella e' effimera/
    read-only, usata solo per le risorse statiche (template/CSS/JS), non
    per 'data/' che deve restare scrivibile e visibile accanto all'exe.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# Suffissi noti per le varianti (costumi) di una stessa umamusume.
# La risoluzione del nome base rimuove questi suffissi IN MODO ITERATIVO
# (es. "oguri_cap_og_xmas" -> rimuove "_xmas" -> "oguri_cap_og" -> rimuove "_og" -> "oguri_cap")
KNOWN_SUFFIXES = [
    "_og", "_xmas", "_cheer", "_island", "_ny", "_wedding",
    "_valen", "_ballroom", "_anime", "_alt", "_tl", "_summer", "_onsen",
]

# Suffissi scoperti automaticamente da data_updater.py (nuove varianti che non
# corrispondevano a nessuno dei precedenti): persistiti qui invece che nel
# codice sorgente, cosi' l'aggiornamento automatico dei dati puo' estendere
# l'elenco senza dover modificare questo file .py. Vedi
# data_updater.epithet_to_suffix / data/extra_suffixes.json.
_EXTRA_SUFFIXES_PATH = os.path.join(app_dir(), "data", "extra_suffixes.json")
if os.path.exists(_EXTRA_SUFFIXES_PATH):
    with open(_EXTRA_SUFFIXES_PATH, encoding="utf-8") as _f:
        for _suf in json.load(_f):
            if _suf not in KNOWN_SUFFIXES:
                KNOWN_SUFFIXES.append(_suf)

# Genitori "meta" noti per strategia/PvP -- default curato a mano, ma
# personalizzabile dall'utente da UI (vedi data_updater.get_meta_parents/
# set_meta_parents, endpoint /api/meta_parents in app.py). Se esiste
# data/meta_parents.json, SOSTITUISCE per intero questo default (a differenza
# di data/extra_suffixes.json sopra, che invece si limita ad AGGIUNGERE --
# qui l'utente deve poter anche rimuovere una voce di default che non
# condivide, non solo aggiungerne).
# NOTA: qui teniamo solo l'elenco piatto fornito dall'utente (senza distinzione di
# strategia per ora) - da espandere in futuro con {strategia: [personaggi]} se serve.
META_PARENTS = [
    "seiun_sky", "mejiro_dober", "mejiro_ryan", "oguri_cap_og_xmas",
    "symboli_rudolf", "agnes_digital", "maruzensky", "taiki_shuttle",
    "narita_brian", "kitasan_black", "el_condor_pasa",
]
_META_PARENTS_PATH = os.path.join(app_dir(), "data", "meta_parents.json")
if os.path.exists(_META_PARENTS_PATH):
    with open(_META_PARENTS_PATH, encoding="utf-8") as _f:
        META_PARENTS = json.load(_f)

# Ordinamento dei voti aptitude, dal migliore al peggiore.
# Un voto e' "sufficiente" se il suo indice e' <= indice della soglia richiesta.
GRADE_ORDER = ["S", "A", "B", "C", "D", "E", "F", "G"]
GRADE_RANK = {g: i for i, g in enumerate(GRADE_ORDER)}

# Soglie minime di aptitude per poter vincere una gara ai fini dell'affinita'.
# Chiavi = valori possibili delle colonne 'surface' e 'distance' di races.xlsx.
MIN_APTITUDE = {
    "turf": "B",
    "dirt": "C",
    "sprint": "B",
    "mile": "B",
    "medium": "C",
    "long": "C",
}

# Priorita' manuale per il tie-break dei conflitti di turno (vedi
# cycle_analysis.compute_turn_priority), usata SOLO quando piu' gare sono
# raggiungibili dallo stesso numero di membri del gruppo (a quel punto il
# default sarebbe l'ordine alfabetico). Preferenza esplicita dell'utente
# (2026-08-02), NON derivata da un dato oggettivo (tutte le gare del dataset
# sono G1, nessun campo di "importanza" a monte) -- vale solo per queste 4
# gare, che condividono fisicamente gli stessi 2 turni (y2_m11_d1/y3_m11_d1):
# al massimo 2 delle 4 sono vincibili per davvero. Gare non elencate qui
# mantengono il tie-break alfabetico di sempre.
RACE_PRIORITY_OVERRIDE = ["qe2_cup", "jbc_classic", "jbc_ladies_classic", "jbc_sprint"]

# Punti di affinita' assegnati per ogni gara G1 vinta in comune (entrambi i personaggi
# soddisfano le soglie di aptitude per quella gara). Valore preso dal patch note ufficiale
# (Second Anniversary Balance Patch); esposto qui come costante modificabile.
RACE_SHARED_WIN_POINTS = 3

# Dimensione del loop da cercare (personaggi diversi, chiuso).
LOOP_SIZE = 5

# Dimensione della rotazione posseduta nel "rental loop" (un genitore costante
# preso in prestito + N personaggi posseduti che ruotano): con un genitore
# sempre disponibile (si riaffitta, non "nasce" mai) bastano 3 identita'
# genealogiche distinte per chiudere il ciclo, non 5.
ANCHOR_LOOP_SIZE = 3


def validate_min_aptitude(payload_dict: dict) -> dict:
    """
    Merge di un dict parziale (es. da un payload JSON) sopra i default di
    MIN_APTITUDE, poi validazione: solleva ValueError se una chiave non e' tra
    le 6 note o un valore non e' un voto valido (GRADE_RANK).
    """
    merged = {**MIN_APTITUDE, **(payload_dict or {})}
    unknown_keys = set(merged) - set(MIN_APTITUDE)
    if unknown_keys:
        raise ValueError(f"Chiavi min_aptitude sconosciute: {sorted(unknown_keys)}")
    invalid = {k: v for k, v in merged.items() if v not in GRADE_RANK}
    if invalid:
        raise ValueError(f"Voti min_aptitude non validi: {invalid}")
    return merged
