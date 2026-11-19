# -*- coding: utf-8 -*-
"""
Controllo incrociato: confronta le nostre affinita' di base (affinity.py,
coppie e terne) con le matrici gia' calcolate pubblicate da uma.moe
(/resources/current/affinity.json.gz: 'chars' = id personaggio del gioco a
4 cifre, 'aff2' = matrice n*n, 'aff3' = matrice n*n*n appiattite).

Lanciato a mano dal pulsante nelle impostazioni (POST /api/affinity_check,
esito in un avviso a scomparsa) -- non aggiorna nessun dato. Anche da riga
di comando:
    python check_affinity_umamoe.py
Uma.moe copre solo i personaggi Global: i nostri personaggi non ancora
usciti non vengono confrontati. Differenza nota (2026-11-19): Shinko Windy,
0-1 su uma.moe contro 4-20 da noi -- dati probabilmente incompleti lato loro.
"""
import itertools
import re
import sys
from collections import Counter

import requests

from affinity import base_affinity, base_affinity_three
from data_loader import load_base_affinity_data, load_character_info
from naming import base_character

UMAMOE = "https://uma.moe/resources/current/"


def _key(english_name: str) -> str:
    """'T.M. Opera O' -> 'tm_opera_o', 'Mr. C.B.' -> 'mr_cb' -- stessa forma
    dei nostri nomi base (naming.base_character)."""
    return re.sub(r"[^a-z0-9]+", "_", english_name.lower().replace(".", "")).strip("_")


def compare_with_umamoe(data_dir) -> dict:
    """Ritorna {pairs, triples, diffs, by_character: [[nome, n], ...] (top
    5), examples: [str, ...] (max 20), unmapped: [nome, ...]}. Solleva
    eccezione se uma.moe non risponde (il chiamante decide cosa farne)."""
    def get(name):
        resp = requests.get(UMAMOE + name, timeout=30)
        resp.raise_for_status()
        return resp.json()  # requests decomprime il gzip da solo
    aff, names = get("affinity.json.gz"), get("character_names.json.gz")
    character_ids, id_weights = load_base_affinity_data(data_dir)
    name_map, _ = load_character_info(data_dir)

    variant_by_base = {}
    for variant in name_map:
        variant_by_base.setdefault(base_character(variant), variant)

    chars = aff["chars"]
    n = len(chars)
    label = [names[str(c)]["name"] for c in chars]
    ours = [variant_by_base.get(_key(name)) for name in label]
    unmapped = [label[i] for i in range(n) if ours[i] is None]

    by_character = Counter()
    examples = []
    diff_count = 0

    def record(involved, mine, theirs):
        nonlocal diff_count
        diff_count += 1
        by_character.update(involved)
        if len(examples) < 20:
            examples.append(f"  {' + '.join(involved)}: noi {mine}, uma.moe {theirs}")

    pairs = triples = 0
    for i, j in itertools.combinations(range(n), 2):
        if None in (ours[i], ours[j]):
            continue
        pairs += 1
        mine = base_affinity(ours[i], ours[j], name_map, character_ids, id_weights)
        theirs = aff["aff2"][i * n + j]
        if mine != theirs:
            record((label[i], label[j]), mine, theirs)
    for i, j, k in itertools.combinations(range(n), 3):
        if None in (ours[i], ours[j], ours[k]):
            continue
        triples += 1
        mine = base_affinity_three(ours[i], ours[j], ours[k], name_map, character_ids, id_weights)
        theirs = aff["aff3"][(i * n + j) * n + k]
        if mine != theirs:
            record((label[i], label[j], label[k]), mine, theirs)

    return {
        "pairs": pairs, "triples": triples, "diffs": diff_count,
        "by_character": by_character.most_common(5), "examples": examples, "unmapped": unmapped,
    }


if __name__ == "__main__":
    result = compare_with_umamoe("data")
    print(f"Confrontate {result['pairs']} coppie e {result['triples']} terne: {result['diffs']} differenze.")
    if result["unmapped"]:
        print("Personaggi uma.moe senza corrispondenza nei nostri dati:", ", ".join(result["unmapped"]))
    for name, count in result["by_character"]:
        print(f"  {name}: {count}")
    print("\n".join(result["examples"]))
    sys.exit(1 if result["diffs"] else 0)
