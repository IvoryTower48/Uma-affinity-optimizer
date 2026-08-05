# -*- coding: utf-8 -*-
"""
Formattazione dei nomi (gare e personaggi) per la visualizzazione A SCHERMO.
Usata SOLO per il testo mostrato all'utente (CLI e UI web) -- tutta la logica
interna (confronti, chiavi di dizionario, matching) continua a usare gli ID
grezzi (snake_case) come prima, invariati.

Regole (confermate in chat):
  - underscore -> spazio, ogni parola capitalizzata.
  - Nei nomi di GARA, una parola di ESATTAMENTE 2 lettere diventa maiuscola
    con un punto dopo ogni lettera (es. 'jf' -> 'J.F.', 'mc' -> 'M.C.'); le
    sigle note di 3 lettere (KNOWN_RACE_ACRONYMS, es. 'jbc' -> 'JBC',
    'nhk' -> 'NHK') diventano tutte maiuscole senza punti. NON e' una regola
    generica sulla lunghezza: molte parole giapponesi/inglesi di 3 lettere
    (es. 'sho', 'hai', 'cup', 'zen') sono parole normali, non sigle, e vanno
    semplicemente capitalizzate come le altre.
  - Eccezione gara: 'qe2_cup' viene mostrato per intero come
    'Queen Elizabeth II Cup' (non e' un'abbreviazione derivabile dalle
    regole sopra).
  - Nei nomi dei PERSONAGGI, i suffissi di variante noti (KNOWN_SUFFIXES)
    diventano tag tra parentesi, con la prima lettera maiuscola, nell'ordine
    in cui compaiono nel nome originale (es. '_og_xmas' -> '(Og) (Xmas)').
    Eccezione: '_valen' -> '(Valentine)' invece di '(Valen)'.
  - Nel nome BASE dei personaggi, alcune parole sono eccezioni esplicite
    (SPECIAL_CHARACTER_WORD_LABELS, NON una regola generica -- come per le
    sigle di gara, una regola generica sulle parole di 2 lettere
    romperebbe nomi normali come 'El' in 'El Condor Pasa'): 'tm' -> 'T.M.'
    (sigla puntata lettera per lettera, es. 'tm_opera_o' -> 'T.M. Opera O'),
    'mr' -> 'Mr.' (abbreviazione con un solo punto finale), 'cb' -> 'CB'
    (sigla senza punti, es. 'mr_cb' -> 'Mr. CB').
"""
from naming import base_character

SPECIAL_VARIANT_LABELS = {
    "valen": "Valentine",
}

# Eccezioni parola-per-parola nel nome BASE di un personaggio, non derivabili
# da nessuna regola generica (vedi docstring sopra per il perche').
SPECIAL_CHARACTER_WORD_LABELS = {
    "tm": "T.M.",
    "mr": "Mr.",
    "cb": "CB",
}

# Eccezioni per nomi di gara non derivabili dalle regole generiche.
SPECIAL_RACE_LABELS = {
    "qe2_cup": "Queen Elizabeth II Cup",
}

# Sigle di 3 lettere note (elenco esplicito, NON una regola generica sulla
# lunghezza: parole normali di 3 lettere come 'sho'/'hai'/'cup'/'zen' NON
# vanno qui, altrimenti diventerebbero erroneamente tutte maiuscole).
KNOWN_RACE_ACRONYMS = {"jbc", "nhk"}


def format_race_name(race_id: str) -> str:
    """
    'hanshin_jf' -> 'Hanshin J.F.'; 'mc_nambu_hai' -> 'M.C. Nambu Hai';
    'jbc_classic' -> 'JBC Classic'; 'qe2_cup' -> 'Queen Elizabeth II Cup'
    (eccezione, vedi SPECIAL_RACE_LABELS).
    """
    if race_id in SPECIAL_RACE_LABELS:
        return SPECIAL_RACE_LABELS[race_id]

    words = race_id.split("_")
    formatted = []
    for w in words:
        if len(w) == 2 and w.isalpha():
            formatted.append(".".join(w.upper()) + ".")
        elif w.lower() in KNOWN_RACE_ACRONYMS:
            formatted.append(w.upper())
        else:
            formatted.append(w.capitalize())
    return " ".join(formatted)


def format_character_name(character_id: str) -> str:
    """
    'oguri_cap_og_xmas' -> 'Oguri Cap (Og) (Xmas)'.
    'manhattan_cafe_valen' -> 'Manhattan Cafe (Valentine)'.
    'agnes_digital' (nessuna variante) -> 'Agnes Digital'.
    """
    base = base_character(character_id)
    base_display = " ".join(
        SPECIAL_CHARACTER_WORD_LABELS.get(w.lower(), w.capitalize())
        for w in base.split("_")
    )

    # base_character rimuove solo dalla FINE, quindi 'base' e' sempre un
    # prefisso del nome originale: il resto sono i suffissi rimossi, nel loro
    # ordine originale di comparsa (non l'ordine in cui sono stati rimossi).
    remainder = character_id[len(base):]
    tags = [t for t in remainder.split("_") if t]
    if not tags:
        return base_display

    tag_labels = [SPECIAL_VARIANT_LABELS.get(t, t.capitalize()) for t in tags]
    return base_display + " " + " ".join(f"({label})" for label in tag_labels)
