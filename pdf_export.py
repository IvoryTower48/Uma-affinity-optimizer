# -*- coding: utf-8 -*-
"""
Documento PDF (1-2 pagine) del loop calcolato: ultima feature del modulo v3
Aptitude Inheritance (vedi HANDOFF.md, "Contenuto pianificato per JSON e
PDF"). Usa immagini reali (targhe delle gare, ritratti dei personaggi)
scaricate al volo da fonti pubbliche quando l'utente genera il PDF sul
proprio PC -- MAI committate nel repository, solo cache locale in
data/image_cache/ (creata alla prima generazione). Se un'immagine non e'
disponibile (rete assente, mapping mancante, richiesta fallita), il PDF
viene comunque generato senza quell'immagine (fallisce sempre in modo
sicuro, stesso principio di data_updater.py).
"""
import json
import math
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas

from cycle_analysis import derive_cycle_spark_plan_from_signature_sparks
from data_updater import HEADERS, gametora_slug
from display_names import format_character_name, format_race_name
from naming import base_character

REQUEST_TIMEOUT = 15
RACE_ICON_URL = "https://uma.guide/icon/race/thum_race_rt_000_{gt_id}_00.webp"
GAMETORA_CHARACTER_URL = "https://gametora.com/umamusume/characters/{slug}"
PORTRAIT_URL_RE = re.compile(r'media\.gametora\.com/umamusume/characters/profile/\d+\.png')


def _race_gametora_ids(data_dir):
    path = Path(data_dir) / "race_gametora_ids.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_race_plaque_image(race_id, data_dir):
    """
    Path locale (scaricato o gia' in cache) dell'immagine della targa della
    gara 'race_id', o None se non disponibile (mapping assente in
    data/race_gametora_ids.json, richiesta fallita, ecc.).
    """
    cache_path = Path(data_dir) / "image_cache" / "races" / f"{race_id}.webp"
    if cache_path.exists():
        return str(cache_path)

    gt_id = _race_gametora_ids(data_dir).get(race_id)
    if gt_id is None:
        return None

    try:
        resp = requests.get(
            RACE_ICON_URL.format(gt_id=gt_id), headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(resp.content)
    return str(cache_path)


def fetch_character_portrait_image(character, data_dir):
    """
    Path locale (scaricato o gia' in cache) del ritratto Gametora del
    personaggio (nome base o variante -- le varianti condividono lo stesso
    ritratto del personaggio base), o None se non disponibile.
    """
    base = base_character(character)
    cache_path = Path(data_dir) / "image_cache" / "characters" / f"{base}.png"
    if cache_path.exists():
        return str(cache_path)

    slug = gametora_slug(base.replace("_", " "))
    try:
        page_resp = requests.get(
            GAMETORA_CHARACTER_URL.format(slug=slug), headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return None
    if page_resp.status_code != 200:
        return None

    match = PORTRAIT_URL_RE.search(page_resp.text)
    if match is None:
        return None

    try:
        img_resp = requests.get(
            "https://" + match.group(0), headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return None
    if img_resp.status_code != 200:
        return None

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(img_resp.content)
    return str(cache_path)


# --- Costruzione del documento PDF (1-2 pagine, illustrato) -----------------
#
# Ultima feature del modulo v3 (vedi HANDOFF.md): stesso contenuto sostanziale
# del salvataggio JSON, ma pensato per l'uso pratico durante il gioco -- un
# diagramma di flusso mostra la rotazione dei 5 personaggi nell'ordine reale
# in cui vanno giocate le carriere (Pagina 1), poi un albero genealogico
# compatto per ciascuno dei 5 cicli con le gare da vincere (Pagina 2). Le
# immagini mancanti (rete assente, personaggio non trovato su Gametora, ecc.)
# non bloccano la generazione: si disegna un riquadro segnaposto col solo
# nome al posto del ritratto/targa.

ACCENT = colors.HexColor("#2f5d50")
BORDER = colors.HexColor("#cccccc")
BG_ALT = colors.HexColor("#f5f5f5")
TEXT = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#555555")
WARNING_COLOR = colors.HexColor("#8a6d00")

# Stringhe statiche del PDF, IT/EN -- il documento segue la lingua scelta
# nella UI (payload['lang'], stesso valore di 'currentLang' in script.js).
# Nomi di personaggi/gare NON sono qui: sono termini di gioco identici in
# entrambe le lingue (display_names.py), stessa scelta gia' fatta per la UI
# web. "Total Loop Affinity"/"Overall Affinity" restano invariati per lo
# stesso motivo (termini coniati dal tool, mai tradotti nemmeno in UI).
PDF_STRINGS = {
    "it": {
        "target_label": "Personaggio target",
        "mode_label": "Modalità",
        "mode_career": "Con vincoli di carriera normale",
        "mode_mant": "Nessun vincolo (Make A New Track)",
        "generated_label": "Generato",
        "flow_title": "Rotazione del loop (ordine di gioco)",
        "cycle_legend": "Ciclo {n}: {name}",
        "substitution_line": (
            "Sostituzione applicata: {old} -> {new} (posizione {position}, "
            "+{delta} Total Loop Affinity)"
        ),
        "page2_title": "I 5 cicli, in dettaglio (giocali in quest'ordine)",
        "cycle_label": "Ciclo {n}",
        "races_to_win": "Gare da vincere:",
        "no_shared_races": "(nessuna gara in comune)",
        "sustainability_warning": (
            "Piano difficilmente sostenibile nella pratica ({stars} stelle totali "
            "su {categories} aptitude diverse): probabilmente irrealistico da "
            "ottenere facendo grinding con le carte a disposizione."
        ),
        "timeline_page_title": "Timeline delle carriere",
        "timeline_original_title": "Senza piano spark",
        "timeline_spark_title": "Con piano spark",
        "timeline_no_spark": "(nessun piano spark calcolato per questo target)",
        "legend_obbligatoria": "M = Obbligatoria",
        "legend_obbligatoria_non_vincibile": "m = Obbligatoria, non vincibile (aptitude)",
        "legend_impossibile": "- = Impossibile (slot occupato)",
        "legend_condivisa": "* = Raggiungibile e condivisa",
        "legend_raggiungibile": "v = Raggiungibile (non condivisa)",
        "legend_aptitude": "A = Solo migliorando l'aptitude",
    },
    "en": {
        "target_label": "Target character",
        "mode_label": "Mode",
        "mode_career": "With normal career constraints",
        "mode_mant": "No constraints (Make A New Track)",
        "generated_label": "Generated",
        "flow_title": "Loop rotation (play order)",
        "cycle_legend": "Cycle {n}: {name}",
        "substitution_line": (
            "Substitution applied: {old} -> {new} (position {position}, "
            "+{delta} Total Loop Affinity)"
        ),
        "page2_title": "The 5 cycles, in detail (play them in this order)",
        "cycle_label": "Cycle {n}",
        "races_to_win": "Races to win:",
        "no_shared_races": "(no races in common)",
        "sustainability_warning": (
            "Plan hard to sustain in practice ({stars} total stars across "
            "{categories} different aptitudes): probably unrealistic to achieve "
            "by grinding with the available cards."
        ),
        "timeline_page_title": "Career timelines",
        "timeline_original_title": "Without spark plan",
        "timeline_spark_title": "With spark plan",
        "timeline_no_spark": "(no spark plan calculated for this target)",
        "legend_obbligatoria": "M = Mandatory",
        "legend_obbligatoria_non_vincibile": "m = Mandatory, not winnable (aptitude)",
        "legend_impossibile": "- = Impossible (slot taken)",
        "legend_condivisa": "* = Reachable and shared",
        "legend_raggiungibile": "v = Reachable (not shared)",
        "legend_aptitude": "A = Only by improving aptitude",
    },
}


def _s(lang, key, **kwargs):
    text = PDF_STRINGS.get(lang, PDF_STRINGS["it"])[key]
    return text.format(**kwargs) if kwargs else text


def _sustainability_warning(cyc_spark, lang):
    """Ricostruisce localizzato lo stesso avviso soft di
    aptitude_inheritance.spark_plan_warning, a partire dalle stelle/categorie
    EFFETTIVE del ciclo (gia' note qui) -- evita di dover ri-tradurre a
    posteriori la stringa italiana gia' pronta in spark_warnings."""
    return _s(lang, "sustainability_warning", stars=sum(cyc_spark.values()), categories=len(cyc_spark))


def _safe_image_reader(path):
    if not path:
        return None
    try:
        return ImageReader(path)
    except Exception:
        return None


def _draw_fitted_text(c, text, cx, y, max_width, font, size, color=None):
    """Testo centrato in cx, troncato con ellissi se supera max_width."""
    c.setFont(font, size)
    if color is not None:
        c.setFillColor(color)
    if c.stringWidth(text, font, size) <= max_width:
        c.drawCentredString(cx, y, text)
        return
    truncated = text
    while truncated and c.stringWidth(truncated + "…", font, size) > max_width:
        truncated = truncated[:-1]
    c.drawCentredString(cx, y, truncated + "…")


def _draw_portrait_box(c, x, y, size, image_path, label, sub_label=None, label_width=None):
    """Riquadro personaggio: ritratto (o segnaposto) + nome (+ eventuale
    sotto-etichetta, es. Individual Affinity). 'label_width' e' lo spazio
    ORIZZONTALE realmente disponibile per il testo (lo slot della colonna,
    non solo la larghezza del riquadro) -- evita che nomi lunghi si
    sovrappongano a quelli dei riquadri vicini quando sono ravvicinati."""
    img = _safe_image_reader(image_path)
    drawn = False
    if img is not None:
        try:
            c.drawImage(img, x, y, width=size, height=size, preserveAspectRatio=True, mask="auto")
            drawn = True
        except Exception:
            drawn = False
    if not drawn:
        c.setFillColor(BG_ALT)
        c.setStrokeColor(BORDER)
        c.rect(x, y, size, size, fill=1, stroke=1)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.6)
    c.rect(x, y, size, size, fill=0, stroke=1)

    text_w = label_width if label_width is not None else size + 20
    _draw_fitted_text(c, label, x + size / 2, y - 8, text_w, "Helvetica", 7.5, TEXT)
    if sub_label is not None:
        _draw_fitted_text(c, str(sub_label), x + size / 2, y - 17, text_w, "Helvetica-Bold", 8, ACCENT)


def _draw_arrow(c, x1, y1, x2, y2, gap):
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy)
    if dist == 0:
        return
    ux, uy = dx / dist, dy / dist
    sx, sy = x1 + ux * gap, y1 + uy * gap
    ex, ey = x2 - ux * gap, y2 - uy * gap
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.4)
    c.line(sx, sy, ex, ey)

    ah = 6.5
    angle = math.atan2(ey - sy, ex - sx)
    left = (ex - ah * math.cos(angle - math.radians(25)), ey - ah * math.sin(angle - math.radians(25)))
    right = (ex - ah * math.cos(angle + math.radians(25)), ey - ah * math.sin(angle + math.radians(25)))
    p = c.beginPath()
    p.moveTo(ex, ey)
    p.lineTo(*left)
    p.lineTo(*right)
    p.close()
    c.setFillColor(ACCENT)
    c.drawPath(p, fill=1, stroke=0)


def _draw_flow_diagram(c, cycles, data_dir, cx, cy, radius, node_size=40):
    """Diagramma di flusso unico: i 5 personaggi disposti in cerchio,
    frecce che seguono l'ordine REALE di gioco (Ciclo1 -> Ciclo2 -> ... ->
    Ciclo5 -> di nuovo Ciclo1, loop perpetuo)."""
    n = len(cycles)
    points = []
    for i in range(n):
        angle = math.radians(-90 + i * 360 / n)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))

    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        _draw_arrow(c, x1, y1, x2, y2, node_size / 2 + 8)

    for i, cycle in enumerate(cycles):
        x, y = points[i]
        character = cycle["child"]
        portrait = fetch_character_portrait_image(character, data_dir)
        _draw_portrait_box(
            c, x - node_size / 2, y - node_size / 2, node_size, portrait,
            format_character_name(character),
        )
        badge_x, badge_y = x - node_size / 2 - 3, y + node_size / 2 + 3
        c.setFillColor(ACCENT)
        c.circle(badge_x, badge_y, 8, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(badge_x, badge_y - 3, str(i + 1))


def _draw_cycle_tree(c, cycle, x, y, w, h, data_dir):
    """
    Albero genealogico compatto per un ciclo: nonni in alto (4 riquadri),
    genitori al centro (2), figlio in basso (1), con linee di parentela.
    (x, y) = angolo in basso a sinistra dell'area riservata; w, h = dimensioni.
    """
    gp_size = min(w / 4 * 0.75, 34)
    p_size = min(w / 2 * 0.45, 40)
    c_size = min(w * 0.35, 44)

    row_gp_y = y + h * 0.78
    row_p_y = y + h * 0.40
    row_c_y = y + h * 0.02

    gp1a, gp1b = cycle["gp_parent1"]
    gp2a, gp2b = cycle["gp_parent2"]
    p1, p2 = cycle["parent1"], cycle["parent2"]
    child = cycle["child"]
    ia = cycle["individual_affinity"]

    gp_xs = [x + w * frac - gp_size / 2 for frac in (0.125, 0.375, 0.625, 0.875)]
    p_xs = [x + w * frac - p_size / 2 for frac in (0.25, 0.75)]
    c_x = x + w / 2 - c_size / 2

    c.setStrokeColor(BORDER)
    c.setLineWidth(0.7)
    for p_idx, gp_idx_pair in ((0, (0, 1)), (1, (2, 3))):
        for gp_idx in gp_idx_pair:
            c.line(
                p_xs[p_idx] + p_size / 2, row_p_y + p_size,
                gp_xs[gp_idx] + gp_size / 2, row_gp_y,
            )
    for p_idx in (0, 1):
        c.line(
            c_x + c_size / 2, row_c_y + c_size,
            p_xs[p_idx] + p_size / 2, row_p_y,
        )

    gp_slot_w = w / 4 - 2
    p_slot_w = w / 2 - 4
    for gx, gp_char, key in zip(gp_xs, (gp1a, gp1b, gp2a, gp2b), ("gp1a", "gp1b", "gp2a", "gp2b")):
        _draw_portrait_box(
            c, gx, row_gp_y, gp_size, fetch_character_portrait_image(gp_char, data_dir),
            format_character_name(gp_char), ia[key], label_width=gp_slot_w,
        )
    for px, p_char, key in zip(p_xs, (p1, p2), ("parent1", "parent2")):
        _draw_portrait_box(
            c, px, row_p_y, p_size, fetch_character_portrait_image(p_char, data_dir),
            format_character_name(p_char), ia[key], label_width=p_slot_w,
        )
    _draw_portrait_box(
        c, c_x, row_c_y, c_size, fetch_character_portrait_image(child, data_dir),
        format_character_name(child), label_width=w,
    )


def _draw_race_strip(c, race_ids, x, y, w, data_dir, lang="it"):
    """Striscia di targhe gara (immagine 2:1), su piu' righe se necessario --
    mostra SEMPRE tutte le gare condivise del ciclo (nessun troncamento:
    l'utente le vuole tutte in vista per sapere cosa puntare a vincere)."""
    if not race_ids:
        c.setFont("Helvetica-Oblique", 6.5)
        c.setFillColor(MUTED)
        c.drawString(x, y, _s(lang, "no_shared_races"))
        return

    thumb_h = 13
    thumb_w = thumb_h * 2
    gap = 2.5
    row_gap = 3
    per_row = max(1, int(w // (thumb_w + gap)))
    for idx, race_id in enumerate(race_ids):
        row, col = divmod(idx, per_row)
        rx = x + col * (thumb_w + gap)
        ry = y - row * (thumb_h + row_gap)
        img = _safe_image_reader(fetch_race_plaque_image(race_id, data_dir))
        drawn = False
        if img is not None:
            try:
                c.drawImage(img, rx, ry, width=thumb_w, height=thumb_h, preserveAspectRatio=True, mask="auto")
                drawn = True
            except Exception:
                drawn = False
        if not drawn:
            c.setFillColor(BG_ALT)
            c.setStrokeColor(BORDER)
            c.rect(rx, ry, thumb_w, thumb_h, fill=1, stroke=1)
            _draw_fitted_text(c, format_race_name(race_id), rx + thumb_w / 2, ry + thumb_h / 2 - 2, thumb_w - 2, "Helvetica", 4.5, TEXT)


CAL_STATUS_COLORS = {
    "obbligatoria": ACCENT,
    "obbligatoria_non_vincibile": colors.HexColor("#b7c9c4"),
    "impossibile": colors.HexColor("#e6e6e6"),
    "condivisa": colors.HexColor("#7cb342"),
    "raggiungibile": colors.HexColor("#d9ecc4"),
    "aptitude": colors.HexColor("#f2d9a0"),
}
CAL_STATUS_TEXT_COLORS = {
    "obbligatoria": colors.white,
    "obbligatoria_non_vincibile": TEXT,
    "impossibile": colors.HexColor("#aaaaaa"),
    "condivisa": TEXT,
    "raggiungibile": TEXT,
    "aptitude": TEXT,
}
# Simboli ASCII (non Unicode: i font base14 di reportlab/Helvetica non
# garantiscono i glifi ● ○ – ★ ✓ △ usati nella UI web) -- stesso significato,
# vedi legend_* in PDF_STRINGS.
CAL_STATUS_SYMBOLS = {
    "obbligatoria": "M",
    "obbligatoria_non_vincibile": "m",
    "impossibile": "-",
    "condivisa": "*",
    "raggiungibile": "v",
    "aptitude": "A",
}


def _cell_status_key(cell):
    status = cell["status"]
    if status == "obbligatoria":
        return "obbligatoria" if cell.get("winnable") else "obbligatoria_non_vincibile"
    if status == "raggiungibile":
        return "condivisa" if cell.get("shared") else "raggiungibile"
    if status == "impossibile":
        return "impossibile"
    return "aptitude"


def _group_members_from_cycles(cycles):
    """Ordine [target, A, B, C, D] (stesso ordine di ranking del top-4),
    ricavato dai cicli stessi (vedi cycle_analysis.build_five_cycle_schedule):
    cycles[0] e' il ciclo di X (figlio=target, genitori=A,B), cycles[1] e'
    quello di C, cycles[2] quello di D -- nessun campo aggiuntivo necessario
    nel payload."""
    c0 = cycles[0]
    return [c0["child"], c0["parent1"], c0["parent2"], cycles[1]["child"], cycles[2]["child"]]


def _draw_calendar_grid(c, calendar_matrix, group_members, x, y_top, w, h, title):
    """Griglia compatta gara x personaggio (vedi static/script.js,
    buildTimelineContent, per l'equivalente nella UI web): una riga per gara,
    una colonna per personaggio, cella colorata per stato + simbolo ASCII."""
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(ACCENT)
    c.drawCentredString(x + w / 2, y_top, title)

    if not calendar_matrix:
        return

    header_h = 20
    race_col_w = w * 0.34
    char_col_w = (w - race_col_w) / len(group_members)
    row_h = max(5, (h - header_h) / len(calendar_matrix))

    table_top = y_top - 14
    for i, char in enumerate(group_members):
        cx = x + race_col_w + i * char_col_w + char_col_w / 2
        _draw_fitted_text(c, format_character_name(char), cx, table_top - 7, char_col_w - 2, "Helvetica-Bold", 5.5, TEXT)

    y = table_top - header_h
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.3)
    symbol_size = max(4.5, min(6.5, row_h * 0.55))
    for row in calendar_matrix:
        c.line(x, y, x + w, y)
        _draw_fitted_text(c, row["label"], x + race_col_w / 2 - 2, y - row_h * 0.7, race_col_w - 4, "Helvetica", 5.5, TEXT)
        for i, char in enumerate(group_members):
            cell = row["cells"].get(char)
            if cell is None:
                continue
            key = _cell_status_key(cell)
            cx = x + race_col_w + i * char_col_w
            c.setFillColor(CAL_STATUS_COLORS[key])
            c.rect(cx, y - row_h, char_col_w - 1, row_h, fill=1, stroke=0)
            c.setFillColor(CAL_STATUS_TEXT_COLORS[key])
            c.setFont("Helvetica-Bold", symbol_size)
            c.drawCentredString(cx + (char_col_w - 1) / 2, y - row_h + row_h * 0.28, CAL_STATUS_SYMBOLS[key])
        y -= row_h


def _draw_calendar_legend(c, x, y, lang):
    c.setFont("Helvetica", 6)
    c.setFillColor(MUTED)
    parts = [
        _s(lang, key) for key in (
            "legend_obbligatoria", "legend_obbligatoria_non_vincibile", "legend_impossibile",
            "legend_condivisa", "legend_raggiungibile", "legend_aptitude",
        )
    ]
    c.drawCentredString(x, y, "   |   ".join(parts))


def _effective_spark_plan(payload):
    """
    Combina il piano spark Modalita' A (payload['spark_plan'], gia' per
    ciclo) con quello derivato dalle spark firma di Modalita' B
    (payload['character_spark_plan'], per personaggio -- vedi
    cycle_analysis.derive_cycle_spark_plan_from_signature_sparks), cosi' il
    PDF mostra le stelle EFFETTIVAMENTE applicate per ciclo, non solo quelle
    inserite direttamente in Modalita' A.
    """
    spark_plan = {int(k): dict(v) for k, v in (payload.get("spark_plan") or {}).items()}
    character_spark_plan = payload.get("character_spark_plan") or {}
    if not character_spark_plan:
        return spark_plan

    established = {c["child"]: (c["parent1"], c["parent2"]) for c in payload["cycles"]}
    derived = derive_cycle_spark_plan_from_signature_sparks(established, character_spark_plan)
    for cycle_number, plan in derived.items():
        merged = spark_plan.setdefault(cycle_number, {})
        for category, stars in plan.items():
            merged[category] = merged.get(category, 0) + stars
    return spark_plan


def _dedupe_cycle_race_ids(race_pairs):
    """Unione (senza duplicati, ordine di prima comparsa) delle gare condivise
    su TUTTE le coppie rilevanti di un ciclo -- vedi cycle_analysis.all_cycles_shared_races."""
    seen = set()
    race_ids = []
    for pair in race_pairs:
        for rid in pair.get("race_ids", []):
            if rid not in seen:
                seen.add(rid)
                race_ids.append(rid)
    return race_ids


def build_loop_pdf(payload, data_dir="data"):
    """
    payload: stesso contenuto sostanziale del salvataggio JSON (vedi
    HANDOFF.md) -- target, mode, cycles (i 5 dict di build_cycle_details),
    all_cycle_races (5 liste, da cycle_analysis.all_cycles_shared_races),
    total_loop_affinity, spark_plan/character_spark_plan/spark_warnings
    (opzionali, se e' stato applicato un piano spark), substitution
    (opzionale, se e' stata applicata/suggerita una sostituzione).
    Ritorna i byte del PDF generato (2 pagine, orientamento orizzontale).
    """
    cycles = payload["cycles"]
    all_cycle_races = payload.get("all_cycle_races") or [[] for _ in cycles]
    target = payload.get("target", "")
    mode = payload.get("mode", "career")
    lang = payload.get("lang") if payload.get("lang") in PDF_STRINGS else "it"
    total_loop_affinity = payload.get("total_loop_affinity")
    spark_plan = _effective_spark_plan(payload)
    spark_warnings = payload.get("spark_warnings") or {}
    substitution = payload.get("substitution")
    generated_at = payload.get("generated_at") or datetime.now(timezone.utc).isoformat()
    mode_label = _s(lang, "mode_career") if mode == "career" else _s(lang, "mode_mant")

    buf = BytesIO()
    page_w, page_h = landscape(A4)
    c = pdfcanvas.Canvas(buf, pagesize=(page_w, page_h))

    # --- Pagina 1: intestazione + diagramma di flusso della rotazione ---
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(ACCENT)
    c.drawString(30, page_h - 40, "Uma Legacy Loop Optimizer")
    c.setFont("Helvetica", 10)
    c.setFillColor(TEXT)
    c.drawString(
        30, page_h - 58,
        f"{_s(lang, 'target_label')}: {format_character_name(target)}    |    "
        f"{_s(lang, 'mode_label')}: {mode_label}",
    )
    if total_loop_affinity is not None:
        c.drawString(30, page_h - 72, f"Total Loop Affinity: {total_loop_affinity}")
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(MUTED)
    c.drawString(30, page_h - 86, f"{_s(lang, 'generated_label')}: {generated_at}")

    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(ACCENT)
    c.drawCentredString(page_w / 2, page_h - 112, _s(lang, "flow_title"))
    _draw_flow_diagram(c, cycles, data_dir, page_w / 2, page_h / 2 - 25, radius=150)

    legend_y = 66
    legend_parts = [
        _s(lang, "cycle_legend", n=i + 1, name=format_character_name(cyc["child"]))
        for i, cyc in enumerate(cycles)
    ]
    c.setFont("Helvetica", 8)
    c.setFillColor(TEXT)
    c.drawCentredString(page_w / 2, legend_y, "   |   ".join(legend_parts))

    if substitution and substitution.get("best_substitution"):
        best = substitution["best_substitution"]
        c.setFont("Helvetica", 8)
        c.setFillColor(MUTED)
        c.drawCentredString(
            page_w / 2, legend_y - 16,
            _s(
                lang, "substitution_line",
                old=format_character_name(best["old_character"]),
                new=format_character_name(best["new_character"]),
                position=best["position"], delta=best["delta"],
            ),
        )

    c.showPage()

    # --- Pagina 2: i 5 cicli in dettaglio (albero genealogico + gare) ---
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(ACCENT)
    c.drawString(30, page_h - 35, _s(lang, "page2_title"))

    n = len(cycles)
    margin = 20
    col_w = (page_w - 2 * margin) / n
    tree_top = page_h - 55
    tree_h = 250

    for i, cycle in enumerate(cycles):
        col_x = margin + i * col_w
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(ACCENT)
        c.drawCentredString(col_x + col_w / 2, tree_top, _s(lang, "cycle_label", n=i + 1))
        _draw_cycle_tree(c, cycle, col_x + 6, tree_top - tree_h - 4, col_w - 12, tree_h, data_dir)

        y_cursor = tree_top - tree_h - 16
        c.setFont("Helvetica", 7)
        c.setFillColor(MUTED)
        c.drawCentredString(col_x + col_w / 2, y_cursor, f"Overall Affinity: {cycle['overall_affinity']}")
        y_cursor -= 11

        cycle_number = i + 1
        cyc_spark = spark_plan.get(str(cycle_number)) or spark_plan.get(cycle_number)
        if cyc_spark:
            spark_text = "Spark: " + ", ".join(f"{cat.capitalize()} {stars}★" for cat, stars in cyc_spark.items())
            _draw_fitted_text(c, spark_text, col_x + col_w / 2, y_cursor, col_w - 8, "Helvetica", 6.5, ACCENT)
            y_cursor -= 10
        has_warning = bool(spark_warnings.get(str(cycle_number)) or spark_warnings.get(cycle_number))
        if has_warning and cyc_spark:
            _draw_fitted_text(
                c, _sustainability_warning(cyc_spark, lang), col_x + col_w / 2, y_cursor,
                col_w - 8, "Helvetica-Oblique", 6, WARNING_COLOR,
            )
            y_cursor -= 10

        race_ids = _dedupe_cycle_race_ids(all_cycle_races[i] if i < len(all_cycle_races) else [])
        c.setFont("Helvetica", 6.5)
        c.setFillColor(TEXT)
        c.drawString(col_x + 4, y_cursor, _s(lang, "races_to_win"))
        # spazio sufficiente sotto l'etichetta prima della prima riga di targhe
        # (drawImage ancora l'immagine dal BASSO: senza questo margine la riga
        # superiore di targhe finiva a coprire proprio il testo dell'etichetta)
        _draw_race_strip(c, race_ids, col_x + 4, y_cursor - 10 - 13, col_w - 8, data_dir, lang=lang)

    c.showPage()

    # --- Pagina 3: timeline delle carriere (senza spark / con spark) ---
    # Richiesta dall'utente (2026-08-02): stessa griglia gara x personaggio
    # mostrata nel pannello "Timeline delle carriere" della UI web. Non entra
    # in pagina 1 (gia' occupata da intestazione + diagramma di flusso, e la
    # griglia ha una riga per OGNI gara del gioco, ~34) -- va sempre su una
    # pagina propria, quindi qui e' pagina 3 direttamente invece di calcolare
    # se "ci sta" in pagina 1.
    calendar_matrix = payload.get("calendar_matrix")
    calendar_matrix_spark = payload.get("calendar_matrix_spark")
    if calendar_matrix:
        group_members = _group_members_from_cycles(cycles)
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(ACCENT)
        c.drawString(30, page_h - 35, _s(lang, "timeline_page_title"))

        margin = 20
        gap = 20
        grid_w = (page_w - 2 * margin - gap) / 2
        grid_top = page_h - 60
        grid_h = grid_top - 60

        _draw_calendar_grid(
            c, calendar_matrix, group_members, margin, grid_top, grid_w, grid_h,
            _s(lang, "timeline_original_title"),
        )
        if calendar_matrix_spark:
            _draw_calendar_grid(
                c, calendar_matrix_spark, group_members, margin + grid_w + gap, grid_top, grid_w, grid_h,
                _s(lang, "timeline_spark_title"),
            )
        else:
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(ACCENT)
            c.drawCentredString(margin + grid_w + gap + grid_w / 2, grid_top, _s(lang, "timeline_spark_title"))
            c.setFont("Helvetica-Oblique", 8)
            c.setFillColor(MUTED)
            c.drawCentredString(margin + grid_w + gap + grid_w / 2, grid_top - 20, _s(lang, "timeline_no_spark"))

        _draw_calendar_legend(c, page_w / 2, 28, lang)
        c.showPage()

    c.save()
    return buf.getvalue()
