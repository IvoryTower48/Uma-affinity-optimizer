const modeSelect = document.getElementById("mode-select");
const modeTabs = document.getElementById("mode-tabs");
const characterField = document.getElementById("character-field");
const characterSelect = document.getElementById("character-select");
const calendarSelect = document.getElementById("calendar-select");
const calendarTabs = document.getElementById("calendar-tabs");
const globalOnlyCheckbox = document.getElementById("global-only-checkbox");
const minAptitudeSelects = Array.from(document.querySelectorAll(".min-aptitude-select"));
const independentTrainingThresholdInput = document.getElementById("independent-training-threshold");
const infoAptitudeTable = document.getElementById("info-aptitude-table");
// GRADE_ORDER/GRADE_RANK sono dichiarate piu' sotto (gia' esistenti per la logica
// spark): populateMinAptitudeSelects()/renderMinAptitudeTable() vengono quindi
// invocate solo dopo quel punto, vedi in fondo al file vicino a GRADE_RANK.
const autoUpdateCheckbox = document.getElementById("auto-update-checkbox");
const debugCheckbox = document.getElementById("debug-checkbox");
const ownedList = document.getElementById("owned-list");
const ownedSortSelect = document.getElementById("owned-sort-select");
const ownedSortDirectionButton = document.getElementById("owned-sort-direction-button");
const selectAllButton = document.getElementById("select-all-button");
const selectNoneButton = document.getElementById("select-none-button");
const gametoraExportButton = document.getElementById("gametora-export-button");
const gametoraImportButton = document.getElementById("gametora-import-button");
const gametoraImportFileInput = document.getElementById("gametora-import-file-input");
const gametoraImportStatus = document.getElementById("gametora-import-status");
const gametoraImportSkipped = document.getElementById("gametora-import-skipped");
const gametoraImportSkippedList = document.getElementById("gametora-import-skipped-list");
const loopField = document.getElementById("loop-field");
const mustIncludeSelects = Array.from(document.querySelectorAll(".must-include-select"));
const rentalField = document.getElementById("rental-field");
const rentalAnchorSelect = document.getElementById("rental-anchor-select");
const rentalGpASelect = document.getElementById("rental-gp-a-select");
const rentalGpBSelect = document.getElementById("rental-gp-b-select");
const rentalFixedSelects = Array.from(document.querySelectorAll(".rental-fixed-select"));
const aceField = document.getElementById("ace-field");
const aceCharacterSelects = Array.from(document.querySelectorAll(".ace-character-select"));
const aceSlotSelects = Array.from(document.querySelectorAll(".ace-slot-select"));
const aceShareCheckboxes = Array.from(document.querySelectorAll(".ace-share-checkbox"));
const runButton = document.getElementById("run-button");
const saveButton = document.getElementById("save-button");
const loadButton = document.getElementById("load-button");
const loadFileInput = document.getElementById("load-file-input");
const pdfButton = document.getElementById("pdf-button");
const pdfStatus = document.getElementById("pdf-status");
const settingsToggle = document.getElementById("settings-toggle");
const settingsPanel = document.getElementById("settings-panel");
const themeSwitch = document.getElementById("theme-switch");
const layoutSwitch = document.getElementById("layout-switch");
const results = document.getElementById("results");
const debugPanel = document.getElementById("debug-panel");
const timelinePanel = document.getElementById("timeline-panel");
const langSwitch = document.getElementById("lang-switch");
const metaParentsOpenButton = document.getElementById("meta-parents-open-button");
const metaParentsModal = document.getElementById("meta-parents-modal");
const metaParentsList = document.getElementById("meta-parents-list");
const metaParentsSelectAllButton = document.getElementById("meta-parents-select-all");
const metaParentsSelectNoneButton = document.getElementById("meta-parents-select-none");
const metaParentsCancelButton = document.getElementById("meta-parents-cancel-button");
const metaParentsSaveButton = document.getElementById("meta-parents-save-button");
const metaParentsError = document.getElementById("meta-parents-error");
const veteransOpenButton = document.getElementById("veterans-open-button");
const veteransModal = document.getElementById("veterans-modal");
const veteransCloseButton = document.getElementById("veterans-close-button");
const veteranAddCharacterSelect = document.getElementById("veteran-add-character-select");
const veteranAddButton = document.getElementById("veteran-add-button");
const veteransListEl = document.getElementById("veterans-list");
const veteranDetailEl = document.getElementById("veteran-detail");
const aceSlotVeteranImportButtons = Array.from(document.querySelectorAll(".ace-slot-veteran-import-button"));
const aceSlotSparkPickers = Array.from(document.querySelectorAll(".ace-slot-spark-picker"));
const aceSlotSparkAddButtons = Array.from(document.querySelectorAll(".ace-slot-spark-add-button"));
const veteranImportModal = document.getElementById("veteran-import-modal");
const veteranImportListEl = document.getElementById("veteran-import-list");
const veteranImportCancelButton = document.getElementById("veteran-import-cancel-button");

// Tiene aperta una connessione verso il server per tutta la vita di QUESTA
// scheda (vedi app.py, /api/heartbeat): quando la scheda si chiude il
// browser interrompe la connessione, e il server -- se l'ha aperta lui
// stesso all'avvio -- chiude il programma da solo dopo un breve periodo di
// grazia. Nessuna azione da fare qui: EventSource si riconnette da solo su
// problemi di rete transitori, e non fa nulla se il browser non la supporta
// (il programma resta semplicemente aperto finche' non lo si chiude a mano).
if (window.EventSource) new EventSource("/api/heartbeat");

let pdfContext = null;  // { oneHop, target, resultBox } dell'ultimo pannello spark renderizzato (mode top4 only)
let allCharactersData = [];   // [{character, global_release_date}], caricato una volta
let ownedSelection = new Set();  // stato persistente: sopravvive a filtri/ordinamenti
let ownedSortDescending = false;  // false = ascendente (default, "come e' adesso")

// --- i18n (IT/EN) -----------------------------------------------------------
// Ogni stringa visibile nella UI passa da qui: le etichette statiche in
// index.html hanno un attributo data-i18n (chiave in questo dizionario) e
// vengono applicate da applyStaticTranslations(); il testo generato in JS usa
// t(key, vars) allo stesso modo. I messaggi di errore/avviso che arrivano dal
// server (app.py e i moduli di calcolo) restano in italiano lato backend --
// tradurli davvero richiederebbe passare la lingua a tutta la catena di
// validazione Python, fuori scopo per questa feature -- percio' vengono
// tradotti qui via translateServerMessage() con un elenco esplicito dei
// messaggi noti (fallback: mostrati in italiano se un messaggio nuovo non e'
// ancora stato aggiunto all'elenco).
const I18N = {
  it: {
    label_auto_update: "Aggiorna automaticamente i dati da internet (nuovi personaggi/gare, una volta al giorno)",
    note_auto_update: "Disattivato di default: attivalo solo se vuoi che il programma si connetta a internet da solo. La modifica ha effetto dal prossimo avvio.",
    label_mode: "Modalità di utilizzo",
    opt_mode_top4: "Top-4 compatibili con un personaggio",
    opt_mode_loop: "Miglior loop a 5",
    label_calendar: "Vincolo di calendario",
    opt_calendar_career: "Con vincoli di carriera normale",
    opt_calendar_mant: "Nessun vincolo (Make A New Track)",
    label_global_only: "Solo personaggi già usciti su Global",
    label_debug: "Modalità debug",
    label_min_aptitude: "Soglie minime di aptitude per considerare una gara vincibile (solo per questa sessione)",
    label_apt_turf: "Turf",
    label_apt_dirt: "Dirt",
    label_apt_sprint: "Sprint",
    label_apt_mile: "Mile",
    label_apt_medium: "Medium",
    label_apt_long: "Long",
    label_character_variant: "Variante",
    label_it_threshold: "Soglia consigliata independent training:",
    it_section_title: "Independent training — probabilità di vittoria",
    it_cycle_heading: "Ciclo {cycle} — Figlio: {name}",
    th_year: "Anno",
    th_streak: "Posizione in serie",
    th_win_probability: "Probabilità di vittoria",
    it_mandatory_badge: "obbligatoria",
    label_owned_title: "Personaggi posseduti",
    label_owned_intro: "Vuoto = verranno considerati tutti i personaggi.",
    btn_select_all: "Seleziona tutti",
    btn_select_none: "Deseleziona tutti",
    label_owned_sort: "Ordina per",
    opt_sort_alpha: "Ordine alfabetico",
    opt_sort_release: "Data di rilascio",
    btn_sort_direction_title: "Inverti ordine",
    sort_ascending: "↑ Ascendente",
    sort_descending: "↓ Discendente",
    btn_gametora_export: "Esporta collezione per Gametora",
    btn_gametora_import: "Importa collezione da Gametora",
    gametora_import_error: "Import fallito: {message}",
    gametora_import_success: "{count} personaggi posseduti importati da Gametora ({unmatched} non riconosciuti, ignorati).",
    gametora_skipped_note: "Nella maggior parte dei casi si tratta di varianti che questo tool non traccia separatamente, perché condividono le stesse aptitude e la stessa carriera del personaggio base ai fini del looping:",
    label_character: "Personaggio",
    label_loop_include: "Personaggi da includere nel loop (fino a 5, opzionale)",
    opt_none: "-- nessuno --",
    opt_mode_rental: "Loop con genitore in prestito",
    rental_section_title: "Loop con genitore in prestito",
    rental_intro: "Il genitore è obbligatorio e viene utilizzato in ogni step del ciclo; i nonni sono opzionali ma aiutano a calcolare correttamente l'affinità massima.",
    label_rental_anchor: "Genitore preso in prestito",
    label_rental_gp_a: "Nonno/a 1 (opzionale)",
    label_rental_gp_b: "Nonno/a 2 (opzionale)",
    label_rental_fixed: "Personaggi posseduti gia' scelti per la rotazione (fino a 3, opzionale)",
    rental_spark_title: "Pink spark del genitore preso in prestito (opzionale)",
    rental_spark_intro: "Sempre la stessa in ogni step della rotazione. Conta doppio per il genitore (è sia genitore diretto che nonno, tramite il membro precedente).",
    label_rental_spark_anchor: "Genitore",
    label_rental_spark_gp_a: "Nonno/a 1",
    label_rental_spark_gp_b: "Nonno/a 2",
    rental_spark_preview_title: "Anteprima aptitude (personaggi già scelti per la rotazione)",
    rental_spark_no_preview: "Scegli almeno un personaggio nella rotazione per vedere l'anteprima.",
    unknown_ancestor: "N/D",
    rental_heading: "Rental loop con {name}",
    rental_total_label: "Total Loop Affinity",
    opt_mode_ace: "Pianifica ace (PvP)",
    ace_section_title: "Pianifica ace (PvP)",
    ace_intro: "Fino a 3 ace (i veterani schierabili in PvP): scegli genitori/nonni manualmente per una spark importante, lascia \"(automatico)\" per farli suggerire. Se più ace condividono lo stesso stile di corsa, puoi condividere lo stesso genitore tra loro invece di allevarne uno per ciascuno.",
    label_ace_parent1: "Genitore 1",
    label_ace_parent2: "Genitore 2",
    label_ace_gp1a: "Nonno/a 1a",
    label_ace_gp1b: "Nonno/a 1b",
    label_ace_gp2a: "Nonno/a 2a",
    label_ace_gp2b: "Nonno/a 2b",
    opt_auto: "(automatico)",
    label_ace_share_parent1: "Genitore 1 condiviso da:",
    label_ace_share_parent2: "Genitore 2 condiviso da:",
    ace_heading: "Piano ace",
    ace_total_label: "Affinità totale",
    rental_partial_note: "Nonni ignoti: alcuni termini non sono calcolati (mostrati come N/D), il totale copre solo quelli noti.",
    rental_gp_suggestions_label: "Nonni suggeriti, in ordine di affinità potenziale massima",
    rental_gp_pairs_label: "Migliori coppie di nonni per affinità aggiunta al loop (Δ per step)",
    th_gp_affinity_steps: "Affinità (1/2/3)",
    th_gp_pair: "Coppia",
    th_gp_deltas: "Δ per step (1/2/3)",
    th_gp_total: "Totale",
    btn_run: "Esegui",
    btn_save: "Salva",
    btn_cancel: "Annulla",
    btn_manage_meta_parents: "Gestisci genitori meta…",
    meta_parents_modal_title: "Genitori meta",
    meta_parents_modal_intro: "Personaggi mostrati con il badge \"META\" nei risultati. La modifica ha effetto subito, su tutti i risultati futuri.",
    btn_manage_veterans: "Gestisci veterani…",
    veterans_modal_title: "Veterani",
    veterans_modal_intro: "Genitori/nonni già allevati, con le loro spark: si riusano su più piani. Permanenti, salvati sul tuo PC.",
    btn_veteran_add: "Aggiungi veterano",
    opt_spark_picker_placeholder: "-- scegli una spark --",
    opt_group_race_spark: "Race spark",
    opt_group_white_spark: "White spark",
    btn_close: "Chiudi",
    veterans_empty: "Nessun veterano salvato ancora.",
    btn_import_veteran: "Importa",
    veteran_import_modal_title: "Importa veterano",
    ace_slot_spark_remove_title: "Rimuovi",
    veteran_parents_title: "Genitori del veterano (diventeranno i nonni, una volta importato come genitore)",
    btn_load: "Carica",
    save_filename_prompt: "Nome del file di salvataggio (lascia vuoto per il nome predefinito):",
    load_error: "Impossibile caricare il file: {message}",
    placeholder_results: "I risultati compariranno qui.",
    heading_timeline: "Timeline delle carriere",
    placeholder_timeline: "Esegui una ricerca per vedere il calendario del gruppo.",
    info_aptitude_title: "Quando una gara è vincibile?",
    info_aptitude_text: "Vincibile solo se l'aptitude soddisfa ENTRAMBE le soglie minime (superficie e distanza):",
    info_aptitude_note: "Voto minimo o migliore (scala S migliore di A, ..., G peggiore).",
    info_inspiration_title: "Probabilità di ispirazione",
    info_inspiration_text: "i = % di ereditare una spark almeno una volta (2 eventi di Inspiration in carriera), secondo l'Affinità Individuale",
    spark_color_blue: "Blu",
    spark_color_pink: "Rosa",
    spark_color_green: "Verde",
    spark_color_white: "Bianca",
    spark_color_race: "Gara",

    table_header_character: "Personaggio",
    table_header_value: "Valore",
    table_header_term: "Termine",
    overall_formula_title: "Formula Overall Affinity (per ciclo)",
    overall_formula_text: "Overall Affinity = bAff(figlio,genitore1) + bAff(figlio,genitore2) + bAff(genitore1,genitore2) + bAff(figlio,genitore,nonno) [x4] + Bonus(genitore1,genitore2) + Bonus(genitore,nonno) [x4] — ogni termine contato una sola volta.",
    overall_formula_cycle_heading: "Ciclo {n}: {name}",
    overall_formula_total_label: "Totale (Overall Affinity)",
    first_cycle_races_title: "Gare vinte in comune — solo primo ciclo",
    table_header_pair: "Coppia",
    table_header_shared_races: "Gare in comune",
    races_none: "(nessuna)",

    spark_a_intro: "<strong>Modalità A</strong> — stelle totali per categoria, per ciclo " +
      "(max 4 categorie e 18★ per ciclo). Un ciclo lasciato vuoto equivale a nessuna spark.",
    spark_cycle_title: "Ciclo {cycle} — Figlio: {name}",
    spark_summary: "{stars}★ su {categories} categorie",
    spark_b_intro: "<strong>Modalità B</strong> — assegna la spark che un personaggio ottiene " +
      "a fine carriera: si propaga da sola agli altri cicli in cui quel personaggio compare come " +
      "genitore o nonno (contata una volta per ogni slot che occupa). Aiuta a capire quali spark " +
      "conviene avere su una carta, invece di pianificare a tavolino un fabbisogno per un punto del loop.",
    btn_add: "Aggiungi",
    btn_remove: "Rimuovi",
    substitution_none: "Nessuna sostituzione nel pool disponibile migliora il punteggio con questo piano spark.",
    substitution_found: "Sostituire <strong>{oldName}</strong> con <strong>{newName}</strong> porterebbe " +
      "la Total Loop Affinity da {baseline} a <strong>{total}</strong> (+{delta}).",
    calc_in_progress: "Calcolo in corso...",
    error_unknown: "Errore sconosciuto",
    total_loop_affinity: "Total Loop Affinity: {value}",
    spark_panel_title: "Piano spark (Aptitude Inheritance)",
    spark_mode_a_title: "Modalità A",
    spark_mode_b_title: "Modalità B",
    breakdown_base_affinity: "Affinità di base",
    breakdown_race_bonus: "Affinità bonus gare",
    btn_calc_spark: "Calcola con queste spark",
    btn_generate_pdf: "Genera PDF",
    pdf_generating: "Generazione PDF in corso...",
    pdf_error: "Errore nella generazione del PDF: {message}",

    th_child: "Figlio",
    th_parent1: "Genitore 1",
    th_parent2: "Genitore 2",
    th_gp1a: "Nonno 1 di G1",
    th_gp1b: "Nonno 2 di G1",
    th_gp2a: "Nonno 1 di G2",
    th_gp2b: "Nonno 2 di G2",
    th_overall_affinity: "Overall Affinity",

    one_hop_heading: "Esplorazione a un salto — rotazione a 5 cicli",
    timeline_no_calendar: "Nessun calendario disponibile per questo risultato.",
    timeline_race_col: "Gara (turno)",

    status_obbligatoria: "Obbligatoria",
    status_obbligatoria_non_vincibile: "Obbligatoria (aptitude insufficiente, non vincibile)",
    status_impossibile: "Impossibile (slot occupato da un'altra obbligatoria)",
    status_raggiungibile_condivisa: "Raggiungibile e condivisa con altri",
    status_raggiungibile: "Raggiungibile (nessun altro la raggiunge)",
    status_aptitude: "Raggiungibile solo migliorando l'aptitude",

    legend_obbligatoria: "● Obbligatoria",
    legend_obbligatoria_non_vincibile: "○ Obbligatoria, non vincibile (aptitude)",
    legend_impossibile: "– Impossibile (slot occupato)",
    legend_condivisa: "★ Raggiungibile e condivisa",
    legend_raggiungibile: "✓ Raggiungibile (non condivisa)",
    legend_aptitude: "△ Solo migliorando l'aptitude",

    tab_original: "Originale",
    tab_with_spark: "Con spark",

    top4_heading: "Top-4 compatibili con {name}",
    th_total: "Totale",
    th_base: "Base",
    th_race: "Gara",
    meta_tag: "META",
    debug_details_title: "Dettagli modalità debug",
    top10_base_title: "Top-10 affinità di base con {name}",
    top10_race_title: "Top-10 affinità di calendario con {name}",
    top10_total_title: "Top-10 affinità totale (base + calendario) con {name}",

    loop_heading: "Miglior loop trovato (punteggio totale: {value})",
    meta_suffix: " (META)",

    error_prefix: "Errore: {message}",

    settings_title: "Impostazioni",
    settings_language: "Lingua",
    settings_theme: "Tema",
    settings_theme_light: "Chiaro",
    settings_theme_dark: "Scuro",
    settings_layout: "Aspetto",
    settings_layout_modern: "Nuovo",
    settings_layout_classic: "Classico",
    genealogy_label_grandparents: "Nonni",
    genealogy_label_parents: "Genitori",
    genealogy_label_child: "Figlio",
    credits_footer: "Codice: Claude (Anthropic). Idea e design: IvoryTower.",
  },
  en: {
    label_auto_update: "Automatically update data from the internet (new characters/races, once a day)",
    note_auto_update: "Off by default: turn it on only if you want the program to connect to the internet on its own. The change takes effect from the next launch.",
    label_mode: "Usage mode",
    opt_mode_top4: "Top-4 compatible with a character",
    opt_mode_loop: "Best 5-loop",
    label_calendar: "Calendar constraint",
    opt_calendar_career: "With normal career constraints",
    opt_calendar_mant: "No constraints (Make A New Track)",
    label_global_only: "Only characters already released on Global",
    label_debug: "Debug mode",
    label_min_aptitude: "Minimum aptitude thresholds to consider a race winnable (this session only)",
    label_apt_turf: "Turf",
    label_apt_dirt: "Dirt",
    label_apt_sprint: "Sprint",
    label_apt_mile: "Mile",
    label_apt_medium: "Medium",
    label_apt_long: "Long",
    label_character_variant: "Variant",
    label_it_threshold: "Independent training recommendation threshold:",
    it_section_title: "Independent training — win probability",
    it_cycle_heading: "Cycle {cycle} — Child: {name}",
    th_year: "Year",
    th_streak: "Streak position",
    th_win_probability: "Win probability",
    it_mandatory_badge: "mandatory",
    label_owned_title: "Owned characters",
    label_owned_intro: "Empty = every character will be considered.",
    btn_select_all: "Select all",
    btn_select_none: "Deselect all",
    label_owned_sort: "Sort by",
    opt_sort_alpha: "Alphabetical order",
    opt_sort_release: "Release date",
    btn_sort_direction_title: "Reverse order",
    sort_ascending: "↑ Ascending",
    sort_descending: "↓ Descending",
    btn_gametora_export: "Export collection to Gametora",
    btn_gametora_import: "Import collection from Gametora",
    gametora_import_error: "Import failed: {message}",
    gametora_import_success: "{count} owned characters imported from Gametora ({unmatched} unrecognized, skipped).",
    gametora_skipped_note: "Most of the time these are variants this tool doesn't track separately, since they share the same aptitudes and career as the base character for looping purposes:",
    label_character: "Character",
    label_loop_include: "Characters to include in the loop (up to 5, optional)",
    opt_none: "-- none --",
    opt_mode_rental: "Loop with a rental parent",
    rental_section_title: "Loop with a rental parent",
    rental_intro: "The parent is mandatory and is used in every step of the cycle; the grandparents are optional but help compute the maximum affinity correctly.",
    label_rental_anchor: "Rental parent",
    label_rental_gp_a: "Grandparent 1 (optional)",
    label_rental_gp_b: "Grandparent 2 (optional)",
    label_rental_fixed: "Owned characters already chosen for the rotation (up to 3, optional)",
    rental_spark_title: "Rented parent's pink spark (optional)",
    rental_spark_intro: "Always the same at every step of the rotation. Counts double for the parent (it's both the direct parent and a grandparent, via the previous member).",
    label_rental_spark_anchor: "Parent",
    label_rental_spark_gp_a: "Grandparent 1",
    label_rental_spark_gp_b: "Grandparent 2",
    rental_spark_preview_title: "Aptitude preview (characters already chosen for the rotation)",
    rental_spark_no_preview: "Pick at least one character in the rotation to see the preview.",
    unknown_ancestor: "N/A",
    rental_heading: "Rental loop with {name}",
    rental_total_label: "Total Loop Affinity",
    opt_mode_ace: "Plan aces (PvP)",
    ace_section_title: "Plan aces (PvP)",
    ace_intro: "Up to 3 aces (the veterans you can field in PvP): manually pick parents/grandparents for an important spark, leave \"(auto)\" to get them suggested. If several aces share the same running style, you can share the same parent between them instead of breeding one for each.",
    label_ace_parent1: "Parent 1",
    label_ace_parent2: "Parent 2",
    label_ace_gp1a: "Grandparent 1a",
    label_ace_gp1b: "Grandparent 1b",
    label_ace_gp2a: "Grandparent 2a",
    label_ace_gp2b: "Grandparent 2b",
    opt_auto: "(auto)",
    label_ace_share_parent1: "Parent 1 shared by:",
    label_ace_share_parent2: "Parent 2 shared by:",
    ace_heading: "Ace plan",
    ace_total_label: "Total affinity",
    rental_partial_note: "Grandparents unknown: some terms aren't computed (shown as N/A), the total only covers the known ones.",
    rental_gp_suggestions_label: "Suggested grandparents, ordered by potential maximum affinity",
    rental_gp_pairs_label: "Best grandparent pairs by affinity added to the loop (Δ per step)",
    th_gp_affinity_steps: "Affinity (1/2/3)",
    th_gp_pair: "Pair",
    th_gp_deltas: "Δ per step (1/2/3)",
    th_gp_total: "Total",
    btn_run: "Run",
    btn_save: "Save",
    btn_cancel: "Cancel",
    btn_manage_meta_parents: "Manage meta parents…",
    meta_parents_modal_title: "Meta parents",
    meta_parents_modal_intro: "Characters shown with the \"META\" badge in results. The change takes effect immediately, on all future results.",
    btn_manage_veterans: "Manage veterans…",
    veterans_modal_title: "Veterans",
    veterans_modal_intro: "Already-bred parents/grandparents, with their sparks: reused across multiple plans. Permanent, saved on your PC.",
    btn_veteran_add: "Add veteran",
    opt_spark_picker_placeholder: "-- choose a spark --",
    opt_group_race_spark: "Race spark",
    opt_group_white_spark: "White spark",
    btn_close: "Close",
    veterans_empty: "No veterans saved yet.",
    btn_import_veteran: "Import",
    veteran_import_modal_title: "Import veteran",
    ace_slot_spark_remove_title: "Remove",
    veteran_parents_title: "Veteran's parents (become grandparents once imported as a parent)",
    btn_load: "Load",
    save_filename_prompt: "Save file name (leave empty for the default name):",
    load_error: "Could not load the file: {message}",
    placeholder_results: "Results will appear here.",
    heading_timeline: "Career timeline",
    placeholder_timeline: "Run a search to see the group's calendar.",
    info_aptitude_title: "When is a race winnable?",
    info_aptitude_text: "Winnable only if aptitude meets BOTH minimum thresholds (surface and distance):",
    info_aptitude_note: "Minimum grade or better (scale: S best, ..., G worst).",
    info_inspiration_title: "Inspiration chance",
    info_inspiration_text: "i = % of inheriting a spark at least once (2 Inspiration events per career), based on Individual Affinity",
    spark_color_blue: "Blue",
    spark_color_pink: "Pink",
    spark_color_green: "Green",
    spark_color_white: "White",
    spark_color_race: "Race",

    table_header_character: "Character",
    table_header_value: "Value",
    table_header_term: "Term",
    overall_formula_title: "Overall Affinity formula (per cycle)",
    overall_formula_text: "Overall Affinity = bAff(child,parent1) + bAff(child,parent2) + bAff(parent1,parent2) + bAff(child,parent,grandparent) [x4] + Bonus(parent1,parent2) + Bonus(parent,grandparent) [x4] — each term counted once.",
    overall_formula_cycle_heading: "Cycle {n}: {name}",
    overall_formula_total_label: "Total (Overall Affinity)",
    first_cycle_races_title: "Races won in common — first cycle only",
    table_header_pair: "Pair",
    table_header_shared_races: "Shared races",
    races_none: "(none)",

    spark_a_intro: "<strong>Mode A</strong> — total stars per category, per cycle " +
      "(max 4 categories and 18★ per cycle). A cycle left empty means no spark.",
    spark_cycle_title: "Cycle {cycle} — Child: {name}",
    spark_summary: "{stars}★ across {categories} categories",
    spark_b_intro: "<strong>Mode B</strong> — assign the spark a character gets " +
      "at the end of its career: it propagates on its own to every other cycle where that " +
      "character appears as a parent or grandparent (counted once per slot it occupies). Helps " +
      "figure out which sparks are worth having on a card, instead of planning a need for one " +
      "spot in the loop from scratch.",
    btn_add: "Add",
    btn_remove: "Remove",
    substitution_none: "No substitution in the available pool improves the score with this spark plan.",
    substitution_found: "Replacing <strong>{oldName}</strong> with <strong>{newName}</strong> would raise " +
      "the Total Loop Affinity from {baseline} to <strong>{total}</strong> (+{delta}).",
    calc_in_progress: "Calculating...",
    error_unknown: "Unknown error",
    total_loop_affinity: "Total Loop Affinity: {value}",
    spark_panel_title: "Spark plan (Aptitude Inheritance)",
    spark_mode_a_title: "Mode A",
    spark_mode_b_title: "Mode B",
    breakdown_base_affinity: "Base affinity",
    breakdown_race_bonus: "Race bonus affinity",
    btn_calc_spark: "Calculate with these sparks",
    btn_generate_pdf: "Generate PDF",
    pdf_generating: "Generating PDF...",
    pdf_error: "Error generating PDF: {message}",

    th_child: "Child",
    th_parent1: "Parent 1",
    th_parent2: "Parent 2",
    th_gp1a: "Grandparent 1 of P1",
    th_gp1b: "Grandparent 2 of P1",
    th_gp2a: "Grandparent 1 of P2",
    th_gp2b: "Grandparent 2 of P2",
    th_overall_affinity: "Overall Affinity",

    one_hop_heading: "One-hop exploration — 5-cycle rotation",
    timeline_no_calendar: "No calendar available for this result.",
    timeline_race_col: "Race (turn)",

    status_obbligatoria: "Mandatory",
    status_obbligatoria_non_vincibile: "Mandatory (aptitude too low, not winnable)",
    status_impossibile: "Impossible (slot taken by another mandatory race)",
    status_raggiungibile_condivisa: "Reachable and shared with others",
    status_raggiungibile: "Reachable (no one else reaches it)",
    status_aptitude: "Reachable only by improving aptitude",

    legend_obbligatoria: "● Mandatory",
    legend_obbligatoria_non_vincibile: "○ Mandatory, not winnable (aptitude)",
    legend_impossibile: "– Impossible (slot taken)",
    legend_condivisa: "★ Reachable and shared",
    legend_raggiungibile: "✓ Reachable (not shared)",
    legend_aptitude: "△ Only by improving aptitude",

    tab_original: "Original",
    tab_with_spark: "With sparks",

    top4_heading: "Top-4 compatible with {name}",
    th_total: "Total",
    th_base: "Base",
    th_race: "Race",
    meta_tag: "META",
    debug_details_title: "Debug mode details",
    top10_base_title: "Top-10 base affinity with {name}",
    top10_race_title: "Top-10 calendar affinity with {name}",
    top10_total_title: "Top-10 total affinity (base + calendar) with {name}",

    loop_heading: "Best loop found (total score: {value})",
    meta_suffix: " (META)",

    error_prefix: "Error: {message}",

    settings_title: "Settings",
    settings_language: "Language",
    settings_theme: "Theme",
    settings_theme_light: "Light",
    settings_theme_dark: "Dark",
    settings_layout: "Look",
    settings_layout_modern: "New",
    settings_layout_classic: "Classic",
    genealogy_label_grandparents: "Grandparents",
    genealogy_label_parents: "Parents",
    genealogy_label_child: "Child",
    credits_footer: "Code: Claude (Anthropic). Idea and design: IvoryTower.",
  },
};

const LANG_STORAGE_KEY = "uma_tool_lang";
const THEME_STORAGE_KEY = "uma_tool_theme";
const LAYOUT_STORAGE_KEY = "uma_tool_layout";
let currentLang = "en";
let currentTheme = "light";
let layoutMode = "modern";  // "modern" (default, card/ritratti) | "classic" (tabelle di sempre)

function t(key, vars) {
  const dict = I18N[currentLang] || I18N.it;
  let text = dict[key] !== undefined ? dict[key] : (I18N.it[key] !== undefined ? I18N.it[key] : key);
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replace(new RegExp(`\\{${name}\\}`, "g"), value);
    }
  }
  return text;
}

// Elenco esplicito dei messaggi noti che arrivano dal server (in italiano):
// ogni voce e' [regex, (match) => testo inglese]. Se un messaggio nuovo non e'
// ancora in elenco, viene mostrato in italiano anche con lingua EN attiva
// (fallback sicuro, non un errore silente: il testo resta sempre leggibile).
const SERVER_MESSAGE_TRANSLATIONS = [
  [/^Personaggio '(.+?)' non trovato( \(con il filtro Global attivo\))?\.$/,
    m => `Character '${m[1]}' not found${m[2] ? " (with the Global filter active)" : ""}.`],
  [/^'(.+?)' e' ambiguo tra le varianti: (.+?)\. Specifica quale con il nome completo\.$/,
    m => `'${m[1]}' is ambiguous between variants: ${m[2]}. Specify which one using the full name.`],
  [/^Servono esattamente 4 personaggi trovati per l'esplorazione a un salto \(trovati: (\d+)\)\.$/,
    m => `Exactly 4 characters must be found for the one-hop exploration (found: ${m[1]}).`],
  [/^Servono esattamente 4 personaggi trovati per il piano spark \(trovati: (\d+)\)\. Controlla i filtri posseduti\/Global attivi\.$/,
    m => `Exactly 4 characters must be found for the spark plan (found: ${m[1]}). Check the owned/Global filters.`],
  [/^Le chiavi di 'spark_plan' devono essere numeri di ciclo \(1-5\)\.$/,
    () => `'spark_plan' keys must be cycle numbers (1-5).`],
  [/^'character_spark_plan' contiene personaggi non presenti nel gruppo attuale: (.+?)\.$/,
    m => `'character_spark_plan' contains characters not present in the current group: ${m[1]}.`],
  [/^Servono almeno 5 personaggi posseduti \(dopo i filtri attivi\) per cercare un loop\.$/,
    () => `At least 5 owned characters (after active filters) are required to search for a loop.`],
  [/^Puoi includere al massimo 5 personaggi\.$/,
    () => `You can include at most 5 characters.`],
  [/^'(.+?)' non trovato tra i personaggi disponibili \(dopo i filtri Global\/posseduti attivi\)\.$/,
    m => `'${m[1]}' not found among the available characters (after the active Global/owned filters).`],
  [/^Non e' stato possibile trovare un loop completo con questi vincoli \(pool troppo ristretto dopo aver escluso basi duplicate\)\.$/,
    () => `It was not possible to find a complete loop with these constraints (pool too small after excluding duplicate bases).`],
  [/^Massimo (\d+) tipi di aptitude diversi per ciclo \(un ciclo coinvolge solo \d+ personaggi distinti\), ricevuti (\d+)\.$/,
    m => `Maximum ${m[1]} different aptitude types per cycle (a cycle only involves ${m[1]} distinct characters), received ${m[2]}.`],
  [/^Massimo (\d+) stelle totali per ciclo \(6 slot antenato x 3 stelle\), ricevute (\d+)\.$/,
    m => `Maximum ${m[1]} total stars per cycle (6 ancestor slots x 3 stars), received ${m[2]}.`],
  [/^Stelle negative non valide per '(.+?)': (-?\d+)\.$/,
    m => `Invalid negative stars for '${m[1]}': ${m[2]}.`],
  [/^La spark 'firma' di un personaggio riguarda una sola categoria di aptitude \(ricevute (\d+)\)\.$/,
    m => `A character's 'signature' spark covers only one aptitude category (received ${m[1]}).`],
  [/^Le stelle di una spark 'firma' devono essere tra 1 e (\d+) \(ricevute (\d+) per '(.+?)'\)\.$/,
    m => `A signature spark's stars must be between 1 and ${m[1]} (received ${m[2]} for '${m[3]}').`],
  [/^Piano difficilmente sostenibile nella pratica \((\d+) stelle totali su (\d+) aptitude diverse\): probabilmente irrealistico da ottenere facendo grinding con le carte a disposizione\.$/,
    m => `Plan hard to sustain in practice (${m[1]} total stars across ${m[2]} different aptitudes): probably unrealistic to achieve by grinding with the available cards.`],
  [/^Servono esattamente 4 personaggi \(i top-4 trovati\)\.$/,
    () => `Exactly 4 characters are required (the top-4 found).`],
  [/^Numero di ciclo non valido: (\d+) \(atteso 1-5\)\.$/,
    m => `Invalid cycle number: ${m[1]} (expected 1-5).`],
  [/^Troppi personaggi fissi \((\d+)\): il loop ha spazio per al massimo (\d+)\.$/,
    m => `Too many fixed characters (${m[1]}): the loop has room for at most ${m[2]}.`],
  [/^I personaggi fissi includono due varianti dello stesso nome base \(stessa identita' genealogica\) -- non possono coesistere nello stesso loop\.$/,
    () => `The fixed characters include two variants of the same base name (same genealogical identity) — they can't coexist in the same loop.`],
  [/^character_info\.csv assente: filtro Global ignorato\.$/,
    () => `character_info.csv missing: Global filter ignored.`],
];

function translateServerMessage(msg) {
  if (!msg || currentLang === "it") return msg;
  for (const [regex, build] of SERVER_MESSAGE_TRANSLATIONS) {
    const m = msg.match(regex);
    if (m) return build(m);
  }
  return msg;  // messaggio non ancora mappato: fallback in italiano, sempre leggibile
}

function applyStaticTranslations() {
  document.documentElement.lang = currentLang;
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    if (key === "sort_ascending") return;  // gestito a parte, dipende dallo stato corrente
    el.textContent = t(key);
  });
  document.querySelectorAll("[data-i18n-title]").forEach(el => {
    el.title = t(el.dataset.i18nTitle);
  });
  ownedSortDirectionButton.textContent = t(ownedSortDescending ? "sort_descending" : "sort_ascending");
  langToggle.applyButtons(currentLang);
}

let lastRun = null;  // { type: "top4"|"loop", data } -- per ri-renderizzare al cambio lingua/aspetto

function rerenderLastRun() {
  if (!lastRun) return;
  if (lastRun.type === "top4") renderTop4(lastRun.data);
  else if (lastRun.type === "loop") renderLoop(lastRun.data);
}

// I tre toggle delle Impostazioni (lingua/tema/aspetto) condividono lo stesso
// schema: valida il valore, applica l'effetto, salva in localStorage (se non
// disponibile non e' bloccante, la scelta semplicemente non sopravvive al
// reload), aggiorna lo stato attivo dei bottoni.
function makeToggleControl(switchEl, buttonSelector, choiceAttr, activeClass, storageKey, validValues, onSet) {
  function applyButtons(current) {
    switchEl.querySelectorAll(buttonSelector).forEach(btn => {
      btn.classList.toggle(activeClass, btn.dataset[choiceAttr] === current);
    });
  }
  function set(value) {
    if (!validValues.includes(value)) return;
    onSet(value);
    try {
      localStorage.setItem(storageKey, value);
    } catch (err) {
      // localStorage non disponibile: non bloccante, la scelta non sopravvive al reload.
    }
    applyButtons(value);
  }
  switchEl.querySelectorAll(buttonSelector).forEach(btn => {
    btn.addEventListener("click", () => set(btn.dataset[choiceAttr]));
  });
  return { set, applyButtons };
}

const langToggle = makeToggleControl(
  langSwitch, ".lang-button", "lang", "lang-button-active", LANG_STORAGE_KEY, ["it", "en"],
  (lang) => {
    currentLang = lang;
    applyStaticTranslations();
    populateMustIncludeSelects();
    buildRentalSparkPanel();
    rerenderLastRun();
  },
);
const setLang = langToggle.set;

const themeToggle = makeToggleControl(
  themeSwitch, ".theme-button", "themeChoice", "theme-button-active", THEME_STORAGE_KEY, ["light", "dark"],
  (theme) => {
    currentTheme = theme;
    document.documentElement.dataset.theme = theme;
  },
);
const setTheme = themeToggle.set;
const applyThemeButtons = () => themeToggle.applyButtons(currentTheme);

const layoutToggle = makeToggleControl(
  layoutSwitch, ".layout-button", "layoutChoice", "layout-button-active", LAYOUT_STORAGE_KEY, ["modern", "classic"],
  (mode) => {
    layoutMode = mode;
    document.documentElement.dataset.layout = mode;
    // Top-4/genealogia hanno markup DIVERSO tra i due layout (card vs tabella):
    // ri-renderizza l'ultimo risultato per riflettere subito il cambio. Stessa
    // cosa per i posseduti (griglia ritratti vs lista checkbox).
    rerenderLastRun();
    renderOwnedList();
    // Cambio layout = colonne dell'ace-field di larghezza diversa: ricalcola
    // (vedi lo stesso ragionamento in updateFieldVisibility sopra).
    if (modeSelect.value === "ace") [...aceCharacterSelects, ...aceSlotSelects].forEach(fitSelectFont);
  },
);
const setLayoutMode = layoutToggle.set;
const applyLayoutButtons = () => layoutToggle.applyButtons(layoutMode);

// --- Pannello Impostazioni (icona ingranaggio nell'header) -----------------
function openSettingsPanel() {
  settingsPanel.hidden = false;
  settingsToggle.setAttribute("aria-expanded", "true");
}
function closeSettingsPanel() {
  settingsPanel.hidden = true;
  settingsToggle.setAttribute("aria-expanded", "false");
}
settingsToggle.addEventListener("click", () => {
  if (settingsPanel.hidden) openSettingsPanel();
  else closeSettingsPanel();
});
document.addEventListener("click", (event) => {
  if (settingsPanel.hidden) return;
  if (event.target === settingsToggle || settingsToggle.contains(event.target)) return;
  if (settingsPanel.contains(event.target)) return;
  closeSettingsPanel();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !settingsPanel.hidden) closeSettingsPanel();
});

// --- Persistenza tra sessioni (2026-07-30) ---------------------------------
// Filtro Global, modalita' debug, ordinamento/direzione dei posseduti, e la
// selezione dei posseduti stessa: salvati in localStorage (locale al
// browser dell'utente, non un artifact Claude.ai -- questo e' un progetto
// Flask standalone, localStorage funziona normalmente) cosi' da restare
// invariati tra un avvio e l'altro del programma. Un problema con
// localStorage (privacy mode restrittiva, quota, ecc.) non deve MAI
// bloccare l'uso del programma: fallisce in silenzio, si usano i default.
const SETTINGS_STORAGE_KEY = "uma_tool_settings_v1";

function loadPersistedSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (err) {
    return null;
  }
}

function savePersistedSettings() {
  try {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({
      global_only: globalOnlyCheckbox.checked,
      debug: debugCheckbox.checked,
      owned_sort: ownedSortSelect.value,
      owned_sort_descending: ownedSortDescending,
      owned: Array.from(ownedSelection),
    }));
  } catch (err) {
    // localStorage non disponibile: non bloccante, si continua senza persistenza.
  }
}

// Legge una scelta validata da localStorage, o il fallback se assente/non
// disponibile (privacy mode restrittiva, quota, ecc. -- mai bloccante).
function restoreChoice(storageKey, validValues, fallback) {
  try {
    const stored = localStorage.getItem(storageKey);
    if (validValues.includes(stored)) return stored;
  } catch (err) {
    // localStorage non disponibile: si resta sul default.
  }
  return typeof fallback === "function" ? fallback() : fallback;
}

currentLang = restoreChoice(LANG_STORAGE_KEY, ["it", "en"], currentLang);

currentTheme = restoreChoice(THEME_STORAGE_KEY, ["light", "dark"], () =>
  // primo avvio, nessuna preferenza salvata: segue il tema di sistema
  (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light"
);
document.documentElement.dataset.theme = currentTheme;

layoutMode = restoreChoice(LAYOUT_STORAGE_KEY, ["modern", "classic"], layoutMode);
document.documentElement.dataset.layout = layoutMode;
applyThemeButtons();
applyLayoutButtons();

const persistedSettings = loadPersistedSettings();
if (persistedSettings) {
  if (typeof persistedSettings.global_only === "boolean") {
    globalOnlyCheckbox.checked = persistedSettings.global_only;
  }
  if (typeof persistedSettings.debug === "boolean") {
    debugCheckbox.checked = persistedSettings.debug;
  }
  if (persistedSettings.owned_sort) {
    ownedSortSelect.value = persistedSettings.owned_sort;
  }
  if (typeof persistedSettings.owned_sort_descending === "boolean") {
    ownedSortDescending = persistedSettings.owned_sort_descending;
  }
  if (Array.isArray(persistedSettings.owned)) {
    ownedSelection = new Set(persistedSettings.owned);
  }
}

applyStaticTranslations();

// --- Formattazione nomi per la visualizzazione (gemella di display_names.py) ---
// Usata SOLO per il testo mostrato; ID grezzi (valori, chiavi) restano invariati.
// I nomi dei personaggi/gare NON sono tradotti (sono nomi propri/termini di
// gioco identici in entrambe le lingue nel client Global di Umamusume).
const KNOWN_SUFFIXES = [
  "_og", "_xmas", "_cheer", "_island", "_ny", "_wedding",
  "_valen", "_ballroom", "_anime", "_alt", "_tl", "_summer", "_onsen",
];
const SPECIAL_VARIANT_LABELS = { valen: "Valentine" };
const SPECIAL_CHARACTER_WORD_LABELS = { tm: "T.M.", mr: "Mr.", cb: "CB" };

function baseCharacter(variantName) {
  let name = variantName;
  let changed = true;
  while (changed) {
    changed = false;
    for (const suf of KNOWN_SUFFIXES) {
      if (name.endsWith(suf) && name.length > suf.length) {
        name = name.slice(0, -suf.length);
        changed = true;
        break;
      }
    }
  }
  return name;
}

function capitalizeWord(word) {
  if (!word) return word;
  return word[0].toUpperCase() + word.slice(1).toLowerCase();
}

// Le <select> dei blocchi "Pianifica ace" sono strette (colonna fissa a
// 220px, condivisa fra genitore/nonno: ~100px a testa nella griglia 2
// colonne), quindi il nome scelto puo' non starci ed essere tagliato dal
// browser senza nessun avviso. Si riduce il font-size finche' il testo
// attualmente selezionato non ci sta piu' nella larghezza disponibile
// (misurata con canvas, stesso font della select), fino a una soglia
// leggibile; oltre quella soglia (nomi molto lunghi in colonna strettissima,
// nessun font ragionevole ci basterebbe) resta il fallback nativo -- title
// per il nome intero al passaggio del mouse, ellipsis invece del taglio
// a meta' parola (vedi regola CSS abbinata su .ace-ancestor-grid select).
const ACE_SELECT_BASE_FONT_PX = 15.2; // = var(--fs-base) = 0.95rem
const ACE_SELECT_MIN_FONT_PX = 10;
function fitSelectFont(select) {
  const style = getComputedStyle(select);
  const available = select.clientWidth
    - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
    - 18; // spazio riservato alla freccia nativa della select
  const text = select.options[select.selectedIndex]?.textContent || "";
  select.title = text;
  if (!text || available <= 0) return;
  const canvas = fitSelectFont._canvas || (fitSelectFont._canvas = document.createElement("canvas"));
  const ctx = canvas.getContext("2d");
  let size = ACE_SELECT_BASE_FONT_PX;
  while (true) {
    ctx.font = `${style.fontWeight} ${size}px ${style.fontFamily}`;
    if (ctx.measureText(text).width <= available || size <= ACE_SELECT_MIN_FONT_PX) break;
    size -= 0.5;
  }
  select.style.fontSize = Math.max(size, ACE_SELECT_MIN_FONT_PX) + "px";
}

function formatCharacterName(characterId) {
  const base = baseCharacter(characterId);
  const baseDisplay = base.split("_")
    .map(w => SPECIAL_CHARACTER_WORD_LABELS[w.toLowerCase()] || capitalizeWord(w))
    .join(" ");
  const remainder = characterId.slice(base.length);
  const tags = remainder.split("_").filter(t => t.length > 0);
  if (tags.length === 0) return baseDisplay;
  const tagLabels = tags.map(tag => SPECIAL_VARIANT_LABELS[tag] || capitalizeWord(tag));
  return baseDisplay + " " + tagLabels.map(l => `(${l})`).join(" ");
}

// --- Ritratti personaggio (layout moderno, vedi /api/portrait in app.py) ---
// Riusati da card Top-4 e alberi genealogici. Fallback sempre presente sotto
// l'<img> (cerchio con iniziali): se il ritratto non e' disponibile (rete
// assente, personaggio non trovato su Gametora -> 404) si nasconde solo
// l'<img>, il fallback resta visibile -- mai un'icona di immagine rotta.
function characterInitials(character) {
  const words = formatCharacterName(character).replace(/[()]/g, "").split(" ").filter(Boolean);
  return words.slice(0, 2).map(w => w[0].toUpperCase()).join("");
}

function buildPortraitWrap(character) {
  const wrap = document.createElement("div");
  wrap.className = "portrait-wrap";
  const fallback = document.createElement("span");
  fallback.className = "portrait-fallback";
  fallback.setAttribute("aria-hidden", "true");
  fallback.textContent = characterInitials(character);
  wrap.appendChild(fallback);
  const img = document.createElement("img");
  img.className = "portrait-img";
  img.src = `/api/portrait/${encodeURIComponent(character)}`;
  img.alt = "";
  img.loading = "lazy";
  img.addEventListener("error", () => { img.style.display = "none"; });
  wrap.appendChild(img);
  return wrap;
}

function updateFieldVisibility() {
  // "" (non "block") per mostrare: rimuove lo style inline e lascia vincere
  // il display:flex di .control-card in style.css -- un inline style
  // "block" avrebbe priorita' sulla classe e romperebbe l'impilamento
  // verticale label/select dei campi con piu' coppie (es. #rental-field).
  const mode = modeSelect.value;
  characterField.style.display = mode === "top4" ? "" : "none";
  loopField.style.display = mode === "loop" ? "" : "none";
  rentalField.style.display = mode === "rental" ? "" : "none";
  aceField.style.display = mode === "ace" ? "" : "none";
  applyModeTabButtons();
  // Mentre #ace-field era display:none le sue select avevano clientWidth 0,
  // quindi fitSelectFont (chiamata al popolamento) non poteva calcolare
  // niente -- va rifatta ora che tornano visibili e misurabili.
  if (mode === "ace") [...aceCharacterSelects, ...aceSlotSelects].forEach(fitSelectFont);
}
modeSelect.addEventListener("change", updateFieldVisibility);

// Tab della modalita' d'uso: il <select> nascosto resta la fonte di verita'
// (letto/scritto ovunque altrove nel file), i tab si limitano a pilotarlo e
// a specchiarne lo stato attivo -- stesso schema di lang/theme/layout-switch,
// ma senza persistenza in localStorage (il modo non lo era nemmeno prima).
function applyModeTabButtons() {
  modeTabs.querySelectorAll(".mode-tab-button").forEach(btn => {
    btn.classList.toggle("mode-tab-active", btn.dataset.modeChoice === modeSelect.value);
  });
}
modeTabs.querySelectorAll(".mode-tab-button").forEach(btn => {
  btn.addEventListener("click", () => {
    if (btn.dataset.modeChoice === modeSelect.value) return;
    modeSelect.value = btn.dataset.modeChoice;
    modeSelect.dispatchEvent(new Event("change"));
  });
});
updateFieldVisibility();

// Tab del vincolo di calendario: stesso identico schema dei tab di modalita'
// sopra (stessa classe .mode-tab-button/-active, resa "identica" su
// richiesta esplicita). Nessun listener "change" preesistente su
// calendarSelect da preservare (il suo valore viene solo letto al bisogno),
// quindi qui basta pilotare il <select> nascosto e specchiare lo stato
// attivo -- niente updateFieldVisibility-like da richiamare.
function applyCalendarTabButtons() {
  calendarTabs.querySelectorAll(".mode-tab-button").forEach(btn => {
    btn.classList.toggle("mode-tab-active", btn.dataset.calendarChoice === calendarSelect.value);
  });
}
calendarSelect.addEventListener("change", applyCalendarTabButtons);
calendarTabs.querySelectorAll(".mode-tab-button").forEach(btn => {
  btn.addEventListener("click", () => {
    if (btn.dataset.calendarChoice === calendarSelect.value) return;
    calendarSelect.value = btn.dataset.calendarChoice;
    calendarSelect.dispatchEvent(new Event("change"));
  });
});
applyCalendarTabButtons();

function populateMinAptitudeSelects() {
  const defaultsEl = document.getElementById("min-aptitude-default");
  const defaults = defaultsEl ? JSON.parse(defaultsEl.textContent) : {};
  minAptitudeSelects.forEach(select => {
    select.innerHTML = "";
    GRADE_ORDER.forEach(grade => {
      const opt = document.createElement("option");
      opt.value = grade;
      opt.textContent = grade;
      select.appendChild(opt);
    });
    select.value = defaults[select.dataset.category] || "C";
  });
}

function getMinAptitude() {
  const result = {};
  minAptitudeSelects.forEach(select => { result[select.dataset.category] = select.value; });
  return result;
}

function getIndependentTrainingThreshold() {
  const value = Number(independentTrainingThresholdInput.value);
  if (!Number.isFinite(value)) return 80;
  return Math.max(1, Math.min(100, Math.round(value)));
}

function renderMinAptitudeTable() {
  if (!infoAptitudeTable) return;
  const values = getMinAptitude();
  infoAptitudeTable.innerHTML = Object.entries(values)
    .map(([key, grade]) => `<tr><td>${key.charAt(0).toUpperCase()}${key.slice(1)}</td><td><strong>${grade}</strong></td></tr>`)
    .join("");
}

// Nome base per il filtro "solo Global" -- riusato ovunque un personaggio
// possa essere scelto, VETERANI COMPRESI (bug segnalato dall'utente,
// 2026-08-14: un veterano creato con un personaggio non-Global mentre il
// filtro era attivo su ALTRI menu restava comunque selezionabile per il
// veterano stesso, ma poi lo slot ace corrispondente -- gia' filtrato --
// non aveva quell'opzione: il <select> risultava vuoto invece di mostrare
// il personaggio importato).
function characterPassesGlobalFilter(character) {
  if (!globalOnlyCheckbox.checked) return true;
  const info = allCharactersData.find(c => c.character === character);
  return !!(info && info.global_release_date);
}

function globalFilteredCharacterNames() {
  return allCharactersData
    .filter(c => characterPassesGlobalFilter(c.character))
    .map(c => c.character)
    .sort((a, b) => a.localeCompare(b));
}

// Un veterano e' selezionabile per l'import solo se TUTTI i personaggi che
// porta con se' (se stesso + i suoi genitori noti, che diventerebbero nonni)
// passano il filtro -- altrimenti l'import cadrebbe nello stesso bug per lo
// slot nonno anche quando il veterano stesso e' Global.
function veteranPassesGlobalFilter(veteran) {
  const characters = [veteran.character, veteran.parent1 && veteran.parent1.character,
    veteran.parent2 && veteran.parent2.character].filter(Boolean);
  return characters.every(characterPassesGlobalFilter);
}

function populateMustIncludeSelects() {
  const sortedNames = globalFilteredCharacterNames();

  const fillWithNone = select => {
    const current = select.value;
    select.innerHTML = `<option value="">${t("opt_none")}</option>`;
    sortedNames.forEach(name => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = formatCharacterName(name);
      select.appendChild(opt);
    });
    select.value = current;  // se 'current' non e' piu' tra le opzioni, resta vuoto
  };

  mustIncludeSelects.forEach(fillWithNone);
  rentalFixedSelects.forEach(fillWithNone);
  fillWithNone(rentalGpASelect);
  fillWithNone(rentalGpBSelect);

  // l'anchor e' obbligatorio (non serve un'opzione "nessuno"), stesso universo degli altri
  const currentAnchor = rentalAnchorSelect.value;
  rentalAnchorSelect.innerHTML = "";
  sortedNames.forEach(name => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = formatCharacterName(name);
    rentalAnchorSelect.appendChild(opt);
  });
  rentalAnchorSelect.value = sortedNames.includes(currentAnchor) ? currentAnchor : (sortedNames[0] || "");

  // Ace: il primo e' obbligatorio (stesso schema dell'anchor sopra), gli
  // altri due opzionali. Gli slot genitore/nonno sono TUTTI opzionali, ma
  // con "(automatico)" invece di "-- nessuno --": un valore vuoto significa
  // "lascialo suggerire", non "nessuno" in senso assoluto (vedi ace_planner.py).
  const [ace1Select, ace2Select, ace3Select] = aceCharacterSelects;
  fillWithNone(ace2Select);
  fillWithNone(ace3Select);
  const currentAce1 = ace1Select.value;
  ace1Select.innerHTML = "";
  sortedNames.forEach(name => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = formatCharacterName(name);
    ace1Select.appendChild(opt);
  });
  ace1Select.value = sortedNames.includes(currentAce1) ? currentAce1 : (sortedNames[0] || "");

  aceSlotSelects.forEach(select => {
    const current = select.value;
    select.innerHTML = `<option value="">${t("opt_auto")}</option>`;
    sortedNames.forEach(name => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = formatCharacterName(name);
      select.appendChild(opt);
    });
    select.value = current;
  });

  [...aceCharacterSelects, ...aceSlotSelects].forEach(fitSelectFont);
}

function renderCharacterSelect() {
  const globalOnly = globalOnlyCheckbox.checked;
  const current = characterSelect.value;
  const baseNames = [...new Set(
    allCharactersData
      .filter(c => !globalOnly || !!c.global_release_date)
      .map(c => c.base)
  )].sort((a, b) => a.localeCompare(b));

  characterSelect.innerHTML = "";
  baseNames.forEach(name => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = formatCharacterName(name);
    characterSelect.appendChild(opt);
  });
  characterSelect.value = current;  // se 'current' non e' piu' disponibile, si sceglie il primo
  buildAptitudeOverridePanel();
}

function getMustInclude() {
  return mustIncludeSelects.map(s => s.value).filter(v => v);
}

function getRentalFixedMembers() {
  return rentalFixedSelects.map(s => s.value).filter(v => v);
}

// Costruisce il payload di /api/ace_plan dai controlli #ace-field: aces (1-3
// personaggi), slots (dict[ace] -> dict[ruolo] -> personaggio o null) e
// shared_groups (coppie [ace,ruolo] da riempire con lo stesso personaggio,
// una per ruolo genitore -- vedi ace_planner.plan_ace_group). Gli slot/
// checkbox si riferiscono all'INDICE del blocco (1/2/3), tradotto qui nel
// personaggio effettivo scelto in quella posizione.
function getAcePayload() {
  const [ace1, ace2, ace3] = aceCharacterSelects.map(s => s.value);
  const indexToCharacter = { 1: ace1 || null, 2: ace2 || null, 3: ace3 || null };
  const aces = [ace1, ace2, ace3].filter(v => v);

  const slots = {};
  aces.forEach(ace => { slots[ace] = {}; });
  aceSlotSelects.forEach(select => {
    const character = indexToCharacter[Number(select.dataset.aceIndex)];
    if (!character || !slots[character]) return;
    slots[character][select.dataset.role] = select.value || null;
  });

  const groupsByRole = { parent1: [], parent2: [] };
  aceShareCheckboxes.forEach(cb => {
    if (!cb.checked) return;
    const character = indexToCharacter[Number(cb.dataset.aceIndex)];
    if (!character) return;
    groupsByRole[cb.dataset.role].push([character, cb.dataset.role]);
  });
  const shared_groups = Object.values(groupsByRole).filter(g => g.length >= 2);

  return { aces, slots, shared_groups };
}

function visibleItems() {
  const globalOnly = globalOnlyCheckbox.checked;
  const sortMode = ownedSortSelect.value;

  let items = allCharactersData;
  if (globalOnly) {
    items = items.filter(c => !!c.global_release_date);
  }

  if (sortMode === "alpha") {
    items = [...items].sort((a, b) => a.character.localeCompare(b.character));
  } else {
    // ordine di rilascio: chi ha una data va per data crescente, chi non
    // ce l'ha va dopo, in ordine alfabetico tra loro (rilevante solo quando
    // global-only e' spento, perche' altrimenti tutti hanno una data).
    const withDate = items.filter(c => !!c.global_release_date)
      .sort((a, b) => a.global_release_date.localeCompare(b.global_release_date));
    const withoutDate = items.filter(c => !c.global_release_date)
      .sort((a, b) => a.character.localeCompare(b.character));
    items = [...withDate, ...withoutDate];
  }

  if (ownedSortDescending) {
    items = [...items].reverse();
  }
  return items;
}

function renderOwnedList() {
  if (layoutMode === "classic") renderOwnedListClassic();
  else renderOwnedListModern();
}

function renderOwnedListClassic() {
  const items = visibleItems();
  ownedList.innerHTML = "";
  items.forEach(c => {
    const id = `owned-cb-${c.character}`;
    const wrapper = document.createElement("label");
    wrapper.setAttribute("for", id);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = id;
    checkbox.value = c.character;
    checkbox.checked = ownedSelection.has(c.character);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) ownedSelection.add(c.character);
      else ownedSelection.delete(c.character);
      savePersistedSettings();
    });

    wrapper.appendChild(checkbox);
    wrapper.appendChild(document.createTextNode(
      c.global_release_date
        ? `${formatCharacterName(c.character)} (${c.global_release_date})`
        : formatCharacterName(c.character)
    ));
    ownedList.appendChild(wrapper);
  });
}

// Griglia di ritratti selezionabili (layout moderno) -- riusa buildPortraitWrap
// (stesso ritratto/fallback delle card Top-4 e degli alberi genealogici, vedi
// sopra) invece di una lista testuale a checkbox. Ogni chip resta una <label>
// con la checkbox reale nascosta dentro (per submit/stato nativi), cliccabile
// per intero; lo stato selezionato e' riflesso da una classe sul chip stesso.
function renderOwnedListModern() {
  const items = visibleItems();
  ownedList.innerHTML = "";
  items.forEach(c => {
    const id = `owned-cb-${c.character}`;
    const selected = ownedSelection.has(c.character);

    const chip = document.createElement("label");
    chip.className = "owned-chip" + (selected ? " owned-chip-selected" : "");
    chip.setAttribute("for", id);
    chip.title = c.global_release_date
      ? `${formatCharacterName(c.character)} (${c.global_release_date})`
      : formatCharacterName(c.character);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = id;
    checkbox.value = c.character;
    checkbox.hidden = true;
    checkbox.checked = selected;
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) ownedSelection.add(c.character);
      else ownedSelection.delete(c.character);
      chip.classList.toggle("owned-chip-selected", checkbox.checked);
      savePersistedSettings();
    });

    const portrait = buildPortraitWrap(c.character);
    portrait.classList.add("owned-chip-portrait");

    const name = document.createElement("span");
    name.className = "owned-chip-name";
    name.textContent = formatCharacterName(c.character);

    chip.appendChild(checkbox);
    chip.appendChild(portrait);
    chip.appendChild(name);
    ownedList.appendChild(chip);
  });
}

function selectAllOwned() {
  // come se l'utente spuntasse ogni checkbox attualmente visibile
  visibleItems().forEach(c => ownedSelection.add(c.character));
  renderOwnedList();
  savePersistedSettings();
}

function selectNoneOwned() {
  // come se l'utente togliesse la spunta da ogni checkbox attualmente visibile
  visibleItems().forEach(c => ownedSelection.delete(c.character));
  renderOwnedList();
  savePersistedSettings();
}

selectAllButton.addEventListener("click", selectAllOwned);
selectNoneButton.addEventListener("click", selectNoneOwned);

gametoraExportButton.addEventListener("click", handleGametoraExportClick);
gametoraImportButton.addEventListener("click", () => gametoraImportFileInput.click());
gametoraImportFileInput.addEventListener("change", () => {
  const file = gametoraImportFileInput.files[0];
  if (file) handleGametoraImportFile(file);
  gametoraImportFileInput.value = "";  // permette di reimportare lo stesso file una seconda volta
});

globalOnlyCheckbox.addEventListener("change", () => {
  renderOwnedList();
  populateMustIncludeSelects();
  renderCharacterSelect();
  buildRentalSparkPanel();
  savePersistedSettings();
});
debugCheckbox.addEventListener("change", savePersistedSettings);
ownedSortSelect.addEventListener("change", () => {
  renderOwnedList();
  savePersistedSettings();
});
ownedSortDirectionButton.addEventListener("click", () => {
  ownedSortDescending = !ownedSortDescending;
  ownedSortDirectionButton.textContent = t(ownedSortDescending ? "sort_descending" : "sort_ascending");
  renderOwnedList();
  savePersistedSettings();
});

async function loadCharacters() {
  const resp = await fetch("/api/characters");
  const data = await resp.json();
  allCharactersData = data.characters;
  renderOwnedList();
  populateMustIncludeSelects();
  renderCharacterSelect();
  buildRentalSparkPanel();
  await initAceSlotAuxiliaryUI();
}
const charactersLoadedPromise = loadCharacters();  // await-abile dal ripristino di un salvataggio (vedi restoreFromSave)

function getOwnedSelection() {
  return Array.from(ownedSelection);
}

function renderWarning(warning) {
  if (!warning) return "";
  return `<p class="warning">⚠ ${translateServerMessage(warning)}</p>`;
}

// Scaffold condiviso dalle liste nascondibili (<details><summary>+tabella):
// top-10, top-10 col dettaglio, formule Overall Affinity, gare del primo
// ciclo -- stessa struttura, cambiano solo intestazioni/righe.
function makeCollapsibleSection(title, container = results) {
  const details = document.createElement("details");
  details.className = "collapsible-list";
  const summary = document.createElement("summary");
  summary.textContent = title;
  details.appendChild(summary);
  container.appendChild(details);
  return details;
}

function appendTable(details, headers, rows, className) {
  const table = document.createElement("table");
  if (className) table.className = className;
  table.innerHTML = `<thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody></tbody>`;
  const tbody = table.querySelector("tbody");
  rows.forEach(cells => {
    const tr = document.createElement("tr");
    tr.innerHTML = cells.map(c => `<td>${c}</td>`).join("");
    tbody.appendChild(tr);
  });
  details.appendChild(table);
  return table;
}

function renderTop10List(title, items, container = results) {
  const details = makeCollapsibleSection(title, container);
  appendTable(
    details, [t("table_header_character"), t("table_header_value")],
    items.map(row => [formatCharacterName(row.character), `<strong>${row.value}</strong>`]),
  );
}

// Modalita' debug: formula dell'Overall Affinity (vedi cycle_analysis.py,
// docstring del modulo) + valori EFFETTIVI di ogni termine per ciascuno dei
// 5 cicli, in tabella -- una sola sezione nascondibile con un click (come
// le altre liste debug), con una sotto-tabella per ciclo. Riusa
// cycle.overall_breakdown (server-side, cycle_analysis.build_cycle_details):
// stessi termini che sommati danno cycle.overall_affinity, ciascuno UNA
// sola volta (a differenza di cycle.breakdown, usato per i tooltip
// dell'Individual Affinity, dove alcuni termini compaiono due volte).
function renderOverallAffinityFormulas(cycles, container = results) {
  const details = makeCollapsibleSection(t("overall_formula_title"), container);

  const formula = document.createElement("p");
  formula.className = "spark-intro";
  formula.textContent = t("overall_formula_text");
  details.appendChild(formula);

  cycles.forEach((c, i) => {
    const heading = document.createElement("div");
    heading.className = "spark-cycle-title";
    heading.textContent = t("overall_formula_cycle_heading", { n: i + 1, name: formatCharacterName(c.child) });
    details.appendChild(heading);

    const rows = c.overall_breakdown.map(([label, value]) => [label, value]);
    rows.push([`<strong>${t("overall_formula_total_label")}</strong>`, `<strong>${c.overall_affinity}</strong>`]);
    appendTable(details, [t("table_header_term"), t("table_header_value")], rows);
  });
}

function renderTop10TotalList(title, items, container = results) {
  const details = makeCollapsibleSection(title, container);
  appendTable(
    details, [t("table_header_character"), t("th_base"), t("th_race"), t("table_header_value")],
    items.map(row => [formatCharacterName(row.character), row.base, row.race, `<strong>${row.value}</strong>`]),
  );
}

// Le label del breakdown arrivano dal server in notazione a formula (es.
// "bAff(child,p1,gp1a)", "Bonus(p1,p2)") -- utile per il debug (vedi
// renderOverallAffinityFormulas, che la mostra cosi' apposta) ma opaca nel
// tooltip al hover sui personaggi: qui viene tradotta in etichette leggibili
// (nomi formattati, "bAff" -> affinita' di base, "Bonus" -> bonus da gare).
function humanizeBreakdownLabel(label) {
  let m = label.match(/^bAff\(([^,]+),([^,]+),([^)]+)\)$/);
  if (m) return `${t("breakdown_base_affinity")}: ${formatCharacterName(m[1])} – ${formatCharacterName(m[2])} – ${formatCharacterName(m[3])}`;
  m = label.match(/^bAff\(([^,]+),([^)]+)\)$/);
  if (m) return `${t("breakdown_base_affinity")}: ${formatCharacterName(m[1])} – ${formatCharacterName(m[2])}`;
  m = label.match(/^Bonus\(([^,]+),([^)]+)\)$/);
  if (m) return `${t("breakdown_race_bonus")}: ${formatCharacterName(m[1])} – ${formatCharacterName(m[2])}`;
  return label;
}

function formatBreakdownTooltip(terms) {
  // "label: valore" uno per riga, per il title (tooltip nativo al hover)
  return terms.map(([label, value]) => `${humanizeBreakdownLabel(label)} = ${value}`).join("\n");
}

function characterWithAffinity(name, value, breakdownTerms) {
  if (name == null) return `<span class="affinity-unknown">${t("unknown_ancestor")}</span>`;
  const tooltip = formatBreakdownTooltip(breakdownTerms);
  return `${formatCharacterName(name)} (<span class="affinity-value" title="${tooltip}">${value}</span>${buildInspirationPopover(value)})`;
}

function renderFirstCycleRaces(firstCycleRaces, container = results) {
  const details = makeCollapsibleSection(t("first_cycle_races_title"), container);
  appendTable(
    details, [t("table_header_pair"), t("table_header_shared_races")],
    firstCycleRaces.map(row => [row.label, row.races.length ? row.races.join(", ") : t("races_none")]),
    "shared-races-table",
  );
}

// --- v3: Piano spark (Aptitude Inheritance / "pink spark") ----------------
// Disponibile SOLO dentro il pannello "Esplorazione a un salto" (serve gia'
// il gruppo di 5 trovato). Modalita' A: stelle totali per categoria, per
// ciclo -- max 4 categorie e 18 stelle per ciclo (vedi
// aptitude_inheritance.py). Il server valida i limiti hard; qui si mostra
// solo un riepilogo informativo (non bloccante) mentre si compila.

// Le categorie di aptitude (Turf/Dirt/Sprint/...) sono termini di gioco
// identici in IT ed EN nel client Global -- non tradotte.
const SPARK_CATEGORY_OPTIONS = [
  { value: "turf", label: "Turf" }, { value: "dirt", label: "Dirt" },
  { value: "sprint", label: "Sprint" }, { value: "mile", label: "Mile" },
  { value: "medium", label: "Medium" }, { value: "long", label: "Long" },
  { value: "front", label: "Front" }, { value: "pace", label: "Pace" },
  { value: "late", label: "Late" }, { value: "end", label: "End" },
];
const SPARK_MAX_CATEGORIES_PER_CYCLE = 4;
const SPARK_MAX_STARS_PER_CYCLE = 18;
const SPARK_WARNING_STARS = 11;
const SPARK_WARNING_CATEGORIES = 3;

// Porting puro di aptitude_inheritance.py (stessa tabella soglie, stesso
// cap ad "A"), usato SOLO per l'anteprima live lato client -- il calcolo
// autoritativo resta sempre quello del server in /api/pink_spark.
const GRADE_ORDER = ["S", "A", "B", "C", "D", "E", "F", "G"];
const GRADE_RANK = Object.fromEntries(GRADE_ORDER.map((g, i) => [g, i]));

populateMinAptitudeSelects();
renderMinAptitudeTable();
minAptitudeSelects.forEach(select => select.addEventListener("change", renderMinAptitudeTable));

const APTITUDE_CATEGORIES = ["turf", "dirt", "sprint", "mile", "medium", "long"];

// Override temporaneo (mai persistito, mai incluso in salvataggio/ripristino
// JSON) delle aptitude del SOLO personaggio selezionato in Top-4 -- diverso
// dal piano pink spark v3 (per posizione nel ciclo, sull'intero loop): qui
// riguarda un singolo personaggio, editabile solo in meglio e mai oltre 'A'
// (stesso tetto del piano spark).
//
// Un nome base puo' avere piu' varianti (es. Oguri Cap): SOLO UNA alla
// volta va davvero eseguita (mai entrambe, mai una scelta arbitraria e
// silenziosa dal server) -- se le varianti disponibili (dopo il filtro
// Global, se attivo) hanno aptitude DIVERSE in almeno una delle 6 mostrate
// (quelle che contano per le gare, non lo stile di corsa), si mostra un
// selettore esplicito e l'utente scegie quale usare; altrimenti (una sola
// variante disponibile, o piu' varianti ma aptitude-equivalenti per le
// gare) si usa senza chiedere nulla. getResolvedCharacter() e' la fonte di
// verita' su QUALE id esatto verra' davvero inviato al server.
function selectedVariantsForBase(baseName) {
  const globalOnly = globalOnlyCheckbox.checked;
  return allCharactersData
    .filter(c => c.base === baseName && (!globalOnly || !!c.global_release_date))
    .sort((a, b) => a.character.localeCompare(b.character));
}

function raceAptitudesDiffer(variants) {
  if (variants.length < 2) return false;
  const first = variants[0].aptitudes || {};
  return variants.some(v => {
    const apt = v.aptitudes || {};
    return APTITUDE_CATEGORIES.some(cat => apt[cat] !== first[cat]);
  });
}

function getResolvedCharacter() {
  const variantSelect = document.getElementById("character-variant-select");
  if (variantSelect) return variantSelect.value;
  const variants = selectedVariantsForBase(characterSelect.value);
  return variants.length ? variants[0].character : characterSelect.value;
}

function buildAptitudeBlock(variant) {
  const block = document.createElement("div");
  block.className = "aptitude-override-block";
  block.dataset.character = variant.character;

  const grid = document.createElement("div");
  grid.className = "aptitude-override-grid";
  APTITUDE_CATEGORIES.forEach(category => {
    const baseGrade = (variant.aptitudes || {})[category];
    if (!baseGrade) return;
    const row = document.createElement("div");
    row.className = "aptitude-override-row";
    const label = document.createElement("span");
    label.textContent = t(`label_apt_${category}`);
    row.appendChild(label);

    if (GRADE_RANK[baseGrade] <= GRADE_RANK["A"]) {
      // gia' 'A' (o 'S'): nessun margine di miglioramento, testo statico.
      const value = document.createElement("span");
      value.className = "aptitude-override-static";
      value.textContent = baseGrade;
      row.appendChild(value);
    } else {
      const select = document.createElement("select");
      select.className = "aptitude-override-select";
      select.dataset.category = category;
      select.dataset.baseGrade = baseGrade;
      for (let i = GRADE_RANK[baseGrade]; i >= GRADE_RANK["A"]; i--) {
        const opt = document.createElement("option");
        opt.value = GRADE_ORDER[i];
        opt.textContent = GRADE_ORDER[i];
        select.appendChild(opt);
      }
      select.value = baseGrade;
      row.appendChild(select);
    }
    grid.appendChild(row);
  });
  block.appendChild(grid);
  return block;
}

// Ricostruisce SOLO il blocco aptitude (non il selettore variante) in base
// al personaggio attualmente risolto -- cosi' cambiare la variante nel
// selettore non lo ricostruisce da capo (che ne resetterebbe il valore
// appena scelto al default, bug preso durante il testing).
function refreshAptitudeBlockForVariant(container, variants) {
  const existing = container.querySelector(".aptitude-override-block");
  if (existing) existing.remove();
  const resolvedCharacter = getResolvedCharacter();
  const variant = variants.find(v => v.character === resolvedCharacter) || variants[0];
  container.appendChild(buildAptitudeBlock(variant));
}

function buildAptitudeOverridePanel() {
  const container = document.getElementById("aptitude-override-panel");
  if (!container) return;
  container.innerHTML = "";
  const selectedBase = characterSelect.value;
  if (!selectedBase) return;

  const variants = selectedVariantsForBase(selectedBase);
  if (!variants.length) return;  // tutte le varianti escluse dal filtro Global

  if (raceAptitudesDiffer(variants)) {
    const pickerRow = document.createElement("div");
    pickerRow.className = "character-variant-row";
    const label = document.createElement("label");
    label.setAttribute("for", "character-variant-select");
    label.textContent = t("label_character_variant");
    pickerRow.appendChild(label);
    const select = document.createElement("select");
    select.id = "character-variant-select";
    variants.forEach(v => {
      const opt = document.createElement("option");
      opt.value = v.character;
      opt.textContent = formatCharacterName(v.character);
      select.appendChild(opt);
    });
    select.addEventListener("change", () => refreshAptitudeBlockForVariant(container, variants));
    pickerRow.appendChild(select);
    container.appendChild(pickerRow);
  }

  refreshAptitudeBlockForVariant(container, variants);
}

function getAptitudeOverride() {
  const override = {};
  document.querySelectorAll("#aptitude-override-panel .aptitude-override-block").forEach(block => {
    const changes = {};
    block.querySelectorAll(".aptitude-override-select").forEach(select => {
      if (select.value !== select.dataset.baseGrade) changes[select.dataset.category] = select.value;
    });
    if (Object.keys(changes).length) override[block.dataset.character] = changes;
  });
  return override;
}

characterSelect.addEventListener("change", buildAptitudeOverridePanel);

// --- Rental loop: pink spark "firma" del genitore preso in prestito -------
// (2026-08-12) -- simile alla Modalita' B del loop a 5 (personaggio +
// categoria + stelle, 1-3), ma qui il conteggio e' FISSO (il genitore vale
// sempre doppio, i nonni sempre singolo) invece di dipendere dal ciclo,
// perche' l'anchor e' sempre lo stesso in ogni step della rotazione --
// vedi cycle_analysis.anchor_signature_spark_plan, stessa logica qui
// duplicata in JS SOLO per l'anteprima locale (il calcolo autoritativo
// resta quello del server in /api/rental_loop). Solo le 6 categorie
// superficie/distanza (mai lo stile, ininfluente per le gare/l'affinita').
const RACE_APTITUDE_CATEGORY_OPTIONS = SPARK_CATEGORY_OPTIONS.filter(o => APTITUDE_CATEGORIES.includes(o.value));
const RENTAL_SPARK_SLOT_MULTIPLIER = { anchor: 2, gp_a: 1, gp_b: 1 };

function collectRentalSparkRowValues(container) {
  // Valori delle righe ATTUALMENTE nel DOM prima di un rebuild -- cosi'
  // cambiare quale nonno e' selezionato (che fa apparire/scomparire righe)
  // non perde l'input gia' inserito per le righe che restano, stesso bug
  // preso e corretto per il selettore di variante Top-4.
  const values = {};
  if (!container) return values;
  container.querySelectorAll(".rental-spark-row").forEach(row => {
    const category = row.querySelector(".rental-spark-category-select").value;
    const stars = Number(row.querySelector(".rental-spark-star-input").value);
    if (category && stars >= 1) values[row.dataset.slot] = { category, stars };
  });
  return values;
}

function buildRentalSparkRow(slot, previousValues) {
  const row = document.createElement("div");
  row.className = "spark-row rental-spark-row";  // spark-row: riusa lo stile esistente (allineamento select/input)
  row.dataset.slot = slot;

  const label = document.createElement("label");
  label.textContent = t(`label_rental_spark_${slot}`);
  row.appendChild(label);

  const categorySelect = document.createElement("select");
  categorySelect.className = "rental-spark-category-select";
  const emptyOpt = document.createElement("option");
  emptyOpt.value = "";
  emptyOpt.textContent = t("opt_none");
  categorySelect.appendChild(emptyOpt);
  RACE_APTITUDE_CATEGORY_OPTIONS.forEach(({ value, label: catLabel }) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = catLabel;
    categorySelect.appendChild(opt);
  });

  const starInput = document.createElement("input");
  starInput.type = "number";
  starInput.className = "rental-spark-star-input";
  starInput.min = "1";
  starInput.max = "3";
  starInput.disabled = true;

  const previous = previousValues[slot];
  if (previous) {
    categorySelect.value = previous.category;
    starInput.value = previous.stars;
    starInput.disabled = false;
  }

  categorySelect.addEventListener("change", () => {
    starInput.disabled = !categorySelect.value;
    starInput.value = categorySelect.value ? (starInput.value || "1") : "";
    refreshRentalSparkPreview();
  });
  starInput.addEventListener("input", refreshRentalSparkPreview);

  row.appendChild(categorySelect);
  row.appendChild(starInput);
  const starSuffix = document.createElement("span");
  starSuffix.className = "spark-star-suffix";
  starSuffix.textContent = "★";
  row.appendChild(starSuffix);
  return row;
}

function buildRentalSparkPanel() {
  const container = document.getElementById("rental-spark-panel");
  if (!container) return;
  const previousValues = collectRentalSparkRowValues(container);
  container.innerHTML = "";

  const title = document.createElement("p");
  title.className = "field-section-title";
  title.textContent = t("rental_spark_title");
  container.appendChild(title);
  const intro = document.createElement("p");
  intro.className = "field-intro";
  intro.textContent = t("rental_spark_intro");
  container.appendChild(intro);

  const rows = document.createElement("div");
  rows.className = "spark-rows";
  rows.appendChild(buildRentalSparkRow("anchor", previousValues));
  if (rentalGpASelect.value) rows.appendChild(buildRentalSparkRow("gp_a", previousValues));
  if (rentalGpBSelect.value) rows.appendChild(buildRentalSparkRow("gp_b", previousValues));
  container.appendChild(rows);

  const preview = document.createElement("div");
  preview.id = "rental-spark-preview";
  container.appendChild(preview);

  refreshRentalSparkPreview();
}

function getRentalSparkPlan() {
  const plan = {};
  document.querySelectorAll("#rental-spark-panel .rental-spark-row").forEach(row => {
    const category = row.querySelector(".rental-spark-category-select").value;
    const stars = Number(row.querySelector(".rental-spark-star-input").value);
    if (!category || !stars) return;
    plan[category] = (plan[category] || 0) + stars * RENTAL_SPARK_SLOT_MULTIPLIER[row.dataset.slot];
  });
  return plan;
}

// {slot: {categoria: stelle}} -- shape atteso dal payload /api/rental_loop
// (anchor_spark_plan), stesso formato della spark "firma" di Modalita' B
// (character -> {categoria: stelle}), solo indicizzato per slot invece che
// per nome.
function getRentalSparkInput() {
  const input = {};
  document.querySelectorAll("#rental-spark-panel .rental-spark-row").forEach(row => {
    const category = row.querySelector(".rental-spark-category-select").value;
    const stars = Number(row.querySelector(".rental-spark-star-input").value);
    if (category && stars >= 1) input[row.dataset.slot] = { [category]: stars };
  });
  return input;
}

function refreshRentalSparkPreview() {
  const preview = document.getElementById("rental-spark-preview");
  if (!preview) return;
  const plan = getRentalSparkPlan();
  const fixedCharacters = getRentalFixedMembers();
  preview.innerHTML = "";
  if (!Object.keys(plan).length) return;  // nessuna spark scelta: niente da mostrare

  if (!fixedCharacters.length) {
    const note = document.createElement("p");
    note.className = "rental-spark-preview-note";
    note.textContent = t("rental_spark_no_preview");
    preview.appendChild(note);
    return;
  }

  const title = document.createElement("p");
  title.className = "rental-spark-preview-title";
  title.textContent = t("rental_spark_preview_title");
  preview.appendChild(title);
  fixedCharacters.forEach(character => {
    const data = allCharactersData.find(c => c.character === character);
    if (!data || !data.aptitudes) return;
    const line = document.createElement("p");
    line.className = "rental-spark-preview-line";
    line.innerHTML = `<strong>${formatCharacterName(character)}</strong>: ` +
      renderAptitudePreviewLine(data.aptitudes, plan, RACE_APTITUDE_CATEGORY_OPTIONS);
    preview.appendChild(line);
  });
}

rentalAnchorSelect.addEventListener("change", buildRentalSparkPanel);
rentalGpASelect.addEventListener("change", buildRentalSparkPanel);
rentalGpBSelect.addEventListener("change", buildRentalSparkPanel);
rentalFixedSelects.forEach(select => select.addEventListener("change", refreshRentalSparkPreview));

// Ri-adatta il font-size al nome appena scelto (vedi fitSelectFont sopra):
// una select stretta puo' far stare un nome corto a piena taglia e uno
// lungo no, quindi va ricalcolato ad ogni cambio, non solo al popolamento.
[...aceCharacterSelects, ...aceSlotSelects].forEach(select => {
  select.addEventListener("change", () => fitSelectFont(select));
});

function starsToLevelsJs(totalStars) {
  if (totalStars >= 10) return 4;
  if (totalStars >= 7) return 3;
  if (totalStars >= 4) return 2;
  if (totalStars >= 1) return 1;
  return 0;
}

function applyPinkSparksJs(baseAptitudes, starsByCategory) {
  const result = { ...baseAptitudes };
  const capRank = GRADE_RANK["A"];
  for (const [category, stars] of Object.entries(starsByCategory)) {
    if (!(category in result) || !stars) continue;
    const levels = starsToLevelsJs(stars);
    if (levels <= 0) continue;
    const currentRank = GRADE_RANK[result[category]];
    const newRank = Math.max(capRank, currentRank - levels);
    result[category] = GRADE_ORDER[newRank];
  }
  return result;
}

// Porting puro di inspiration.py (stessa formula, stesso cap al 100% prima
// di combinare i 2 eventi di Inspiration in carriera) -- usato SOLO per il
// popover informativo sui nodi genitore/nonno: nessun input utente, l'unico
// dato che varia e' l'Individual Affinity gia' presente nel payload del
// server (pura/rientrante, aggiorna da sola quando cambia il risultato
// mostrato, incluso dopo un piano spark).
const INSPIRATION_BASE_RATES = {
  blue: { 1: 70, 2: 80, 3: 90 },
  pink: { 1: 1, 2: 3, 3: 5 },
  green: { 1: 5, 2: 10, 3: 15 },
  white: { 1: 3, 2: 6, 3: 9 },
  race: { 1: 1, 2: 2, 3: 3 },
};
const INSPIRATION_CATEGORY_ORDER = ["blue", "pink", "green", "white", "race"];

function inspirationChanceJs(category, stars, individualAffinity) {
  return INSPIRATION_BASE_RATES[category][stars] * (1 + individualAffinity / 100);
}

function combinedChanceJs(chancesPercent) {
  const product = chancesPercent.reduce((acc, p) => acc * (1 - p / 100), 1);
  return (1 - product) * 100;
}

function inspirationTableJs(individualAffinity) {
  const table = {};
  INSPIRATION_CATEGORY_ORDER.forEach(category => {
    table[category] = {};
    [1, 2, 3].forEach(stars => {
      const p = Math.min(inspirationChanceJs(category, stars, individualAffinity), 100);
      table[category][stars] = combinedChanceJs([p, p]);
    });
  });
  return table;
}

// Popover "i" riusato dal pattern gia' esistente (.info-popover/.info-icon/
// .info-popover-panel, vedi index.html per la soglia aptitude) -- qui
// costruito come stringa HTML perche' va inserito sia in nodi DOM (layout
// moderno, buildGenealogyNode) sia in celle di tabella costruite via
// innerHTML (layout classico, characterWithAffinity): il CSS hover funziona
// identico in entrambi i casi, nessun event listener da agganciare.
function buildInspirationPopover(individualAffinity) {
  const table = inspirationTableJs(individualAffinity);
  const rows = INSPIRATION_CATEGORY_ORDER.map(category => `
    <tr>
      <td>${t(`spark_color_${category}`)}</td>
      <td>${table[category][1].toFixed(2)}%</td>
      <td>${table[category][2].toFixed(2)}%</td>
      <td>${table[category][3].toFixed(2)}%</td>
    </tr>
  `).join("");
  // Niente testo introduttivo qui (spiegato una sola volta dalla legenda
  // "i = ..." accanto al titolo della sezione, vedi buildInspirationLegend):
  // popup piu' piccolo, meno rischio di eccedere i margini del contenitore.
  return `
    <span class="info-popover info-popover-inline">
      <button type="button" class="info-icon info-icon-sm" title="${t("info_inspiration_title")}">i</button>
      <span class="info-popover-panel info-popover-panel-inspiration">
        <table class="info-aptitude-table info-inspiration-table">
          <thead><tr><th></th><th>1★</th><th>2★</th><th>3★</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </span>
    </span>
  `;
}

// Etichetta statica e sempre visibile (niente hover) accanto al titolo di
// ogni sezione che mostra nodi genitore/nonno con popover di ispirazione --
// sostituisce il testo lungo che prima stava dentro OGNI singolo popup
// (spiegato una volta sola qui, popup ridotti alla sola tabella numerica).
function buildInspirationLegend() {
  // <span> (non <p>): deve poter stare sulla stessa riga del titolo sia
  // dentro un <summary> nativo (contenuto fraseggiato, un blocco lo
  // spezzerebbe su una riga nuova) sia dentro .section-heading-row (flex).
  const span = document.createElement("span");
  span.className = "inspiration-legend";
  span.textContent = t("info_inspiration_text");
  return span;
}

// Il popover di ispirazione e' position:fixed (vedi .info-popover-panel-inspiration
// in style.css): le coordinate non seguono automaticamente l'icona come con
// position:absolute, vanno calcolate qui ad ogni hover sul getBoundingClientRect()
// dell'icona e clampate dentro il viewport -- garantisce che non esca MAI dallo
// schermo (ne' a destra ne' in basso), quindi non puo' mai causare barre di
// scorrimento ne' venire clippato da un antenato con overflow:hidden/auto.
// Delega su document (mouseover/focusin, capture) invece di un listener per
// icona: funziona anche per i popover creati dopo la prima ricerca, senza
// dover reagganciare nulla a ogni render.
function positionInspirationPopover(event) {
  const icon = event.target.closest(".info-popover-inline > .info-icon");
  if (!icon) return;
  const panel = icon.nextElementSibling;
  if (!panel || !panel.classList.contains("info-popover-panel-inspiration")) return;
  const margin = 8;
  const iconRect = icon.getBoundingClientRect();
  // offsetWidth/Height: il browser applica lo stato :hover (quindi
  // display:block sul pannello) PRIMA di eseguire i listener su questo
  // stesso evento, quindi qui il pannello e' gia' quello vero (width:max-content).
  const panelWidth = panel.offsetWidth || 200;
  const panelHeight = panel.offsetHeight || 120;

  let left = Math.min(iconRect.left, window.innerWidth - margin - panelWidth);
  left = Math.max(margin, left);

  let top = iconRect.bottom + 6;
  if (top + panelHeight > window.innerHeight - margin) {
    top = iconRect.top - panelHeight - 6;  // niente spazio sotto: apri sopra l'icona
  }
  top = Math.max(margin, top);

  panel.style.left = `${left}px`;
  panel.style.top = `${top}px`;
}
document.addEventListener("mouseover", positionInspirationPopover, true);
document.addEventListener("focusin", positionInspirationPopover, true);

function buildSparkCategorySelect() {
  const select = document.createElement("select");
  select.className = "spark-category-select";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = t("opt_none");
  select.appendChild(empty);
  SPARK_CATEGORY_OPTIONS.forEach(({ value, label }) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    select.appendChild(opt);
  });
  return select;
}

function collectCycleSparkStars(cycleBox) {
  const categories = {};
  cycleBox.querySelectorAll(".spark-row").forEach(row => {
    const select = row.querySelector(".spark-category-select");
    const input = row.querySelector(".spark-star-input");
    const stars = Number(input.value);
    if (select.value && stars > 0) {
      categories[select.value] = (categories[select.value] || 0) + stars;
    }
  });
  return categories;
}

function renderAptitudePreviewLine(baseAptitudes, starsByCategory, categoryOptions = SPARK_CATEGORY_OPTIONS) {
  const modified = applyPinkSparksJs(baseAptitudes, starsByCategory);
  return categoryOptions.map(({ value, label }) => {
    const before = baseAptitudes[value];
    const after = modified[value];
    const text = before === after ? before : `${before} → <strong>${after}</strong>`;
    return `<span class="spark-aptitude-item">${label}: ${text}</span>`;
  }).join(" ");
}

function mergeStarDicts(a, b) {
  const merged = { ...a };
  for (const [category, stars] of Object.entries(b)) {
    merged[category] = (merged[category] || 0) + stars;
  }
  return merged;
}

function updateSparkCycleSummary(cycleBox, baseAptitudes, extraStars = {}) {
  const combined = mergeStarDicts(collectCycleSparkStars(cycleBox), extraStars);
  let totalStars = 0;
  let categoriesUsed = 0;
  Object.values(combined).forEach(stars => {
    if (stars > 0) {
      totalStars += stars;
      categoriesUsed += 1;
    }
  });
  const summary = cycleBox.querySelector(".spark-cycle-summary");
  const overLimit = totalStars > SPARK_MAX_STARS_PER_CYCLE || categoriesUsed > SPARK_MAX_CATEGORIES_PER_CYCLE;
  const overWarning = totalStars > SPARK_WARNING_STARS || categoriesUsed > SPARK_WARNING_CATEGORIES;
  summary.textContent = t("spark_summary", { stars: totalStars, categories: categoriesUsed });
  summary.classList.toggle("spark-summary-error", overLimit);
  summary.classList.toggle("spark-summary-warning", !overLimit && overWarning);

  const preview = cycleBox.querySelector(".spark-aptitude-preview");
  if (preview && baseAptitudes) {
    preview.innerHTML = renderAptitudePreviewLine(baseAptitudes, combined);
  }
}

function buildSparkCycleBox(cycleNumber, childName, baseAptitudes, getExtraStars) {
  const box = document.createElement("div");
  box.className = "spark-cycle";
  box.dataset.cycle = String(cycleNumber);
  const extra = getExtraStars || (() => ({}));

  const title = document.createElement("div");
  title.className = "spark-cycle-title";
  title.textContent = t("spark_cycle_title", { cycle: cycleNumber, name: formatCharacterName(childName) });
  box.appendChild(title);

  const preview = document.createElement("div");
  preview.className = "spark-aptitude-preview";
  preview.innerHTML = renderAptitudePreviewLine(baseAptitudes, {});
  box.appendChild(preview);

  const rowsContainer = document.createElement("div");
  rowsContainer.className = "spark-rows";
  for (let i = 0; i < SPARK_MAX_CATEGORIES_PER_CYCLE; i++) {
    const row = document.createElement("div");
    row.className = "spark-row";

    const select = buildSparkCategorySelect();
    const input = document.createElement("input");
    input.type = "number";
    input.className = "spark-star-input";
    input.min = "0";
    input.max = String(SPARK_MAX_STARS_PER_CYCLE);
    input.value = "0";
    input.disabled = true;

    select.addEventListener("change", () => {
      input.disabled = !select.value;
      if (!select.value) input.value = "0";
      updateSparkCycleSummary(box, baseAptitudes, extra());
    });
    input.addEventListener("input", () => updateSparkCycleSummary(box, baseAptitudes, extra()));

    row.appendChild(select);
    row.appendChild(input);
    const star = document.createElement("span");
    star.className = "spark-star-suffix";
    star.textContent = "★";
    row.appendChild(star);
    rowsContainer.appendChild(row);
  }
  box.appendChild(rowsContainer);

  const summary = document.createElement("div");
  summary.className = "spark-cycle-summary";
  summary.textContent = t("spark_summary", { stars: 0, categories: 0 });
  box.appendChild(summary);

  return box;
}

function collectSparkPlan(panel) {
  const plan = {};
  panel.querySelectorAll(".spark-cycle[data-cycle]").forEach(cycleBox => {
    const categories = collectCycleSparkStars(cycleBox);
    if (Object.keys(categories).length > 0) {
      plan[cycleBox.dataset.cycle] = categories;
    }
  });
  return plan;
}

// --- Modalita' B (corretta, 2026-07-30): ogni personaggio del gruppo puo'
// avere UNA SOLA "spark firma" (quella che ottiene a fine carriera). Quando
// viene riusato come genitore/nonno in cicli successivi, la spark si
// eredita AL VALORE PIENO per ciascuno slot antenato che occupa in quel
// ciclo (se occupa 2 slot, conta 2 volte -- schema confermato dall'utente
// con l'esempio X=2★ Dirt: 2★ nel Ciclo2 (1 slot), 4★ nei Cicli 3/4 (2
// slot ciascuno)). Le assegnazioni si ACCUMULANO per personaggi diversi
// (assegnarne una nuova non cancella le altre); riassegnare lo STESSO
// personaggio sovrascrive solo la SUA spark (ne ha una sola per volta).
// Qui serve solo aggiornare le anteprime aptitude dei box Modalita' A
// (mai i loro input) -- il conteggio slot usa i dati gia' presenti in
// oneHop.cycles (parent1/parent2/gp_parent1/gp_parent2), nessuna chiamata
// al server per l'anteprima.

function countAncestorSlotOccurrences(cycle, character) {
  const slots = [
    cycle.parent1, cycle.parent2,
    cycle.gp_parent1[0], cycle.gp_parent1[1],
    cycle.gp_parent2[0], cycle.gp_parent2[1],
  ];
  return slots.filter(s => s === character).length;
}

function deriveCycleSparkFromSignatures(cycle, signatureSparks) {
  const aggregated = {};
  for (const [character, plan] of Object.entries(signatureSparks)) {
    const count = countAncestorSlotOccurrences(cycle, character);
    if (count === 0) continue;
    for (const [category, stars] of Object.entries(plan)) {
      aggregated[category] = (aggregated[category] || 0) + stars * count;
    }
  }
  return aggregated;
}

function buildSignatureSparkSection(oneHop, groupMembers, groupAptitudes, panel, signatureSparks) {
  const section = document.createElement("details");
  section.className = "collapsible-list spark-mode-b";
  section.open = true;
  const summary = document.createElement("summary");
  summary.textContent = t("spark_mode_b_title");
  section.appendChild(summary);

  const intro = document.createElement("p");
  intro.className = "spark-intro";
  intro.innerHTML = t("spark_b_intro");
  section.appendChild(intro);

  const picker = document.createElement("div");
  picker.className = "spark-b-picker";

  const characterSelect = document.createElement("select");
  characterSelect.className = "spark-b-character-select";
  groupMembers.forEach(name => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = formatCharacterName(name);
    characterSelect.appendChild(opt);
  });
  picker.appendChild(characterSelect);

  const categorySelect = document.createElement("select");
  categorySelect.className = "spark-b-category-select";
  SPARK_CATEGORY_OPTIONS.forEach(({ value, label }) => {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    categorySelect.appendChild(opt);
  });
  picker.appendChild(categorySelect);

  const starInput = document.createElement("input");
  starInput.type = "number";
  starInput.className = "spark-b-star-input";
  starInput.min = "1";
  starInput.max = "3";
  starInput.value = "1";
  picker.appendChild(starInput);

  const starSuffix = document.createElement("span");
  starSuffix.className = "spark-star-suffix";
  starSuffix.textContent = "★";
  picker.appendChild(starSuffix);

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "spark-b-add-button";
  addButton.textContent = t("btn_add");
  picker.appendChild(addButton);

  section.appendChild(picker);

  const list = document.createElement("ul");
  list.className = "spark-b-assignment-list";
  section.appendChild(list);

  function refreshAllCyclePreviews() {
    panel.querySelectorAll(".spark-cycle[data-cycle]").forEach(cycleBox => {
      const cycleIndex = Number(cycleBox.dataset.cycle) - 1;
      const cycle = oneHop.cycles[cycleIndex];
      const extra = deriveCycleSparkFromSignatures(cycle, signatureSparks);
      updateSparkCycleSummary(cycleBox, groupAptitudes[cycle.child], extra);
    });
  }

  function renderList() {
    list.innerHTML = "";
    Object.entries(signatureSparks).forEach(([character, plan]) => {
      const [category, stars] = Object.entries(plan)[0];
      const label = SPARK_CATEGORY_OPTIONS.find(o => o.value === category)?.label || category;
      const li = document.createElement("li");
      // dataset = fonte di verita' per il salvataggio JSON (evita di esporre
      // lo stato interno signatureSparks fuori dalla closure, vedi
      // collectSparkPanelState in fondo al file).
      li.dataset.character = character;
      li.dataset.category = category;
      li.dataset.stars = String(stars);
      li.innerHTML = `${formatCharacterName(character)}: ${label} ${stars}★ `;
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.textContent = t("btn_remove");
      removeButton.className = "spark-b-remove-button";
      removeButton.addEventListener("click", () => {
        delete signatureSparks[character];
        renderList();
        refreshAllCyclePreviews();
      });
      li.appendChild(removeButton);
      list.appendChild(li);
    });
  }

  addButton.addEventListener("click", () => {
    const character = characterSelect.value;
    const category = categorySelect.value;
    const stars = Number(starInput.value);
    if (!stars || stars < 1 || stars > 3) return;
    signatureSparks[character] = { [category]: stars };  // una sola spark per personaggio: sovrascrive solo la sua
    renderList();
    refreshAllCyclePreviews();
  });

  return section;
}

function renderSubstitutionBox(substitution, container) {
  const box = document.createElement("div");
  const best = substitution.best_substitution;
  if (!best) {
    box.className = "substitution-box substitution-none";
    box.textContent = t("substitution_none");
  } else {
    box.className = "substitution-box substitution-found";
    box.innerHTML = t("substitution_found", {
      oldName: formatCharacterName(best.old_character),
      newName: formatCharacterName(best.new_character),
      baseline: substitution.baseline_total_loop_affinity,
      total: best.total_loop_affinity,
      delta: best.delta,
    });
  }
  container.appendChild(box);
}

// Disegna il risultato di /api/pink_spark dentro resultBox. Estratta da
// runSparkPlan cosi' da poter essere riusata TALE E QUALE dal ripristino di
// un salvataggio JSON (stessi identici dati "congelati", nessuna nuova
// chiamata al server -- vedi restoreSparkPanels). activateTimeline=false
// aggiunge la scheda "Con spark" alla timeline senza attivarla subito (il
// ripristino decide alla fine quale scheda era attiva al momento del
// salvataggio, vedi restoreFromSave).
function renderSparkResultData(resultBox, data, { activateTimeline = true } = {}) {
  resultBox._sparkResultData = data;  // stashato sul nodo DOM: fonte di verita' per il salvataggio JSON
  resultBox.innerHTML = "";
  if (data.warning) resultBox.innerHTML += renderWarning(data.warning);

  Object.values(data.spark_warnings || {}).forEach(msg => {
    const p = document.createElement("p");
    p.className = "warning";
    p.textContent = `⚠ ${translateServerMessage(msg)}`;
    resultBox.appendChild(p);
  });

  const totalLine = document.createElement("p");
  totalLine.className = "total-loop-affinity";
  totalLine.innerHTML = t("total_loop_affinity", { value: `<strong>${data.total_loop_affinity}</strong>` });
  resultBox.appendChild(totalLine);

  resultBox.appendChild(
    layoutMode === "classic" ? buildCycleTable(data.cycles) : buildGenealogyCards(data.cycles),
  );
  if (data.first_cycle_races) renderFirstCycleRaces(data.first_cycle_races, resultBox);
  if (data.substitution) renderSubstitutionBox(data.substitution, resultBox);
  if (data.calendar_matrix) {
    setTimelineTab("spark", t("tab_with_spark"), data.calendar_matrix, [data.target, ...data.top4], activateTimeline);
  }
}

async function runSparkPlan(panel, target, signatureSparks) {
  const resultBox = panel.querySelector(".spark-result");
  resultBox.innerHTML = `<p class="placeholder">${t("calc_in_progress")}</p>`;

  const sparkPlan = collectSparkPlan(panel);
  try {
    const resp = await fetch("/api/pink_spark", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        character: target,
        mode: calendarSelect.value,
        global_only: globalOnlyCheckbox.checked,
        owned: getOwnedSelection(),
        min_aptitude: getMinAptitude(),
        spark_plan: sparkPlan,
        character_spark_plan: signatureSparks,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(translateServerMessage(data.error) || t("error_unknown"));
    // per il PDF (vedi handlePdfClick): il piano EFFETTIVAMENTE inviato al
    // server, non ricostruibile a posteriori dalla sola risposta.
    data.spark_plan = sparkPlan;
    data.character_spark_plan = signatureSparks;
    renderSparkResultData(resultBox, data, { activateTimeline: true });
  } catch (err) {
    resultBox.innerHTML = `<p class="placeholder">${t("error_prefix", { message: err.message })}</p>`;
  }
}

// Genera il documento PDF illustrato del loop (ultima feature del modulo v3
// -- vedi HANDOFF.md). Bottone SEPARATO da Salva/Carica (genera un file a
// parte, non lo stato dell'intera schermata): usa il piano spark GIA'
// calcolato (resultBox._sparkResultData) se presente, altrimenti il
// risultato "puro" di /api/top4 (oneHop, nessuna spark applicata) -- stessa
// distinzione concettuale del salvataggio JSON.
async function handleGeneratePdf(oneHop, target, resultBox, statusEl) {
  const sparkResult = resultBox._sparkResultData;
  const payload = sparkResult
    ? {
        target: sparkResult.target,
        mode: calendarSelect.value,
        cycles: sparkResult.cycles,
        all_cycle_races: sparkResult.all_cycle_races,
        total_loop_affinity: sparkResult.total_loop_affinity,
        spark_plan: sparkResult.spark_plan,
        character_spark_plan: sparkResult.character_spark_plan,
        spark_warnings: sparkResult.spark_warnings,
        substitution: sparkResult.substitution,
      }
    : {
        target,
        mode: calendarSelect.value,
        cycles: oneHop.cycles,
        all_cycle_races: oneHop.all_cycle_races,
        total_loop_affinity: oneHop.total_loop_affinity,
      };
  payload.calendar_matrix = resultBox._originalCalendarMatrix;  // timeline "senza spark", sempre disponibile
  if (sparkResult && sparkResult.calendar_matrix) {
    payload.calendar_matrix_spark = sparkResult.calendar_matrix;  // timeline "con spark", solo se gia' calcolata
  }
  payload.generated_at = new Date().toISOString();
  payload.lang = currentLang;

  statusEl.textContent = t("pdf_generating");
  try {
    const resp = await fetch("/api/export_pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      throw new Error(translateServerMessage(data.error) || t("error_unknown"));
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Loop_${target}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    statusEl.textContent = "";
  } catch (err) {
    statusEl.textContent = t("pdf_error", { message: err.message });
  }
}

function renderPinkSparkPanel(oneHop, target, groupAptitudes, calendarMatrix, container) {
  const panel = document.createElement("details");
  panel.className = "debug-box spark-panel";
  panel.dataset.target = target;  // usato dal salvataggio/ripristino JSON per ritrovare il pannello
  panel.open = true;
  const summary = document.createElement("summary");
  summary.textContent = t("spark_panel_title");
  // niente .section-heading-row qui: <summary> e' display:list-item nativo
  // (marker/triangolo di <details>), un flex lo romperebbe -- la legenda
  // resta contenuto fraseggiato in coda, stessa riga se c'e' spazio.
  summary.appendChild(document.createTextNode(" "));
  summary.appendChild(buildInspirationLegend());
  panel.appendChild(summary);

  const modeA = document.createElement("details");
  modeA.className = "collapsible-list spark-mode-a";
  modeA.open = true;
  const modeASummary = document.createElement("summary");
  modeASummary.textContent = t("spark_mode_a_title");
  modeA.appendChild(modeASummary);

  const intro = document.createElement("p");
  intro.className = "spark-intro";
  intro.innerHTML = t("spark_a_intro");
  modeA.appendChild(intro);

  // stato condiviso con la sezione Modalita' B sotto: dict[personaggio] ->
  // {categoria: stelle}, referenziato per closure dai box Modalita' A cosi'
  // che la loro anteprima aptitude rifletta SEMPRE anche il contributo B
  // corrente per il proprio ciclo, senza bisogno di ricostruire i box.
  const signatureSparks = {};

  oneHop.cycles.forEach((c, i) => {
    modeA.appendChild(buildSparkCycleBox(
      i + 1, c.child, groupAptitudes[c.child],
      () => deriveCycleSparkFromSignatures(oneHop.cycles[i], signatureSparks),
    ));
  });
  panel.appendChild(modeA);

  const groupMembers = oneHop.cycles.map(c => c.child);
  panel.appendChild(buildSignatureSparkSection(oneHop, groupMembers, groupAptitudes, panel, signatureSparks));

  const button = document.createElement("button");
  button.type = "button";
  button.textContent = t("btn_calc_spark");
  button.addEventListener("click", () => runSparkPlan(panel, target, signatureSparks));
  panel.appendChild(button);

  const resultBox = document.createElement("div");
  resultBox.className = "spark-result";
  resultBox._originalCalendarMatrix = calendarMatrix;  // per il PDF (vedi handleGeneratePdf): timeline "senza spark"
  panel.appendChild(resultBox);

  container.appendChild(panel);

  // Bottone PDF spostato accanto a Salva/Carica (statico in index.html):
  // qui aggiorniamo solo a quale risultato deve puntare il prossimo click.
  pdfContext = { oneHop, target, resultBox };
  pdfButton.disabled = false;
  pdfStatus.textContent = "";
}

function buildCycleTable(cycles) {
  const table = document.createElement("table");
  table.className = "cycle-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>${t("th_child")}</th><th>${t("th_parent1")}</th><th>${t("th_parent2")}</th>
        <th>${t("th_gp1a")}</th><th>${t("th_gp1b")}</th>
        <th>${t("th_gp2a")}</th><th>${t("th_gp2b")}</th>
        <th>${t("th_overall_affinity")}</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  cycles.forEach(c => {
    const ia = c.individual_affinity;
    const bd = c.breakdown;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatCharacterName(c.child)}</td>
      <td>${characterWithAffinity(c.parent1, ia.parent1, bd.parent1)}</td>
      <td>${characterWithAffinity(c.parent2, ia.parent2, bd.parent2)}</td>
      <td>${characterWithAffinity(c.gp_parent1[0], ia.gp1a, bd.gp1a)}</td>
      <td>${characterWithAffinity(c.gp_parent1[1], ia.gp1b, bd.gp1b)}</td>
      <td>${characterWithAffinity(c.gp_parent2[0], ia.gp2a, bd.gp2a)}</td>
      <td>${characterWithAffinity(c.gp_parent2[1], ia.gp2b, bd.gp2b)}</td>
      <td><strong>${c.overall_affinity}</strong></td>
    `;
    tbody.appendChild(tr);
  });
  return table;
}

// Nodo di un albero genealogico (layout moderno): ritratto + nome, con
// l'Individual Affinity sotto e lo stesso tooltip di dettaglio (breakdown)
// gia' usato da characterWithAffinity nella tabella classica. 'ia'/'terms'
// omessi per il figlio (non ha una sua Individual Affinity, e' il centro
// dell'albero -- stesso motivo per cui la tabella classica non gliene
// mostra una).
function buildGenealogyNode(character, ia, breakdownTerms) {
  const node = document.createElement("div");
  if (character == null) {
    node.className = "genealogy-node genealogy-node-unknown";
    node.textContent = t("unknown_ancestor");
    return node;
  }
  node.className = "genealogy-node";
  node.title = breakdownTerms ? formatBreakdownTooltip(breakdownTerms) : formatCharacterName(character);
  node.appendChild(buildPortraitWrap(character));
  const name = document.createElement("div");
  name.className = "genealogy-node-name";
  name.textContent = formatCharacterName(character);
  node.appendChild(name);
  if (ia !== undefined) {
    const iaEl = document.createElement("div");
    iaEl.className = "genealogy-node-ia";
    iaEl.innerHTML = `${ia}${buildInspirationPopover(ia)}`;
    node.appendChild(iaEl);
  }
  return node;
}

// dividerIndex: indice del nodo prima del quale disegnare una linea
// verticale leggera -- segna dove finisce un ramo dell'albero (un
// genitore/coppia di nonni) e comincia l'altro, per distinguerli a colpo
// d'occhio (non sono interscambiabili tra loro).
function buildGenealogyTier(labelKey, className, entries, dividerIndex = null) {
  const wrap = document.createElement("div");
  const label = document.createElement("div");
  label.className = "genealogy-tier-label";
  label.textContent = t(labelKey);
  wrap.appendChild(label);
  const tier = document.createElement("div");
  tier.className = `genealogy-tier ${className}`;
  entries.forEach(([character, ia, terms], i) => {
    const node = buildGenealogyNode(character, ia, terms);
    if (i === dividerIndex) node.classList.add("genealogy-branch-divider");
    tier.appendChild(node);
  });
  wrap.appendChild(tier);
  return wrap;
}

// Albero genealogico dei 5 cicli (layout moderno) -- alternativa alla
// tabella classica di buildCycleTable: stessa gerarchia gia' disegnata per
// il PDF (vedi pdf_export._draw_cycle_tree), qui in HTML/CSS invece che
// canvas. Nonni in alto, genitori al centro, figlio in basso.
function buildGenealogyCards(cycles) {
  const row = document.createElement("div");
  row.className = "genealogy-row";
  cycles.forEach(c => {
    const ia = c.individual_affinity;
    const bd = c.breakdown;
    const card = document.createElement("div");
    card.className = "genealogy-card";

    const title = document.createElement("div");
    title.className = "genealogy-card-title";
    title.textContent = formatCharacterName(c.child);
    card.appendChild(title);

    card.appendChild(buildGenealogyTier("genealogy_label_grandparents", "genealogy-tier-gp", [
      [c.gp_parent1[0], ia.gp1a, bd.gp1a],
      [c.gp_parent1[1], ia.gp1b, bd.gp1b],
      [c.gp_parent2[0], ia.gp2a, bd.gp2a],
      [c.gp_parent2[1], ia.gp2b, bd.gp2b],
    ], 2));
    card.appendChild(buildGenealogyTier("genealogy_label_parents", "genealogy-tier-parents", [
      [c.parent1, ia.parent1, bd.parent1],
      [c.parent2, ia.parent2, bd.parent2],
    ], 1));
    card.appendChild(buildGenealogyTier("genealogy_label_child", "genealogy-tier-child", [
      [c.child],
    ]));

    const overall = document.createElement("div");
    overall.className = "genealogy-overall";
    overall.innerHTML = `${t("th_overall_affinity")}: <strong>${c.overall_affinity}</strong>`;
    card.appendChild(overall);

    row.appendChild(card);
  });
  return row;
}

function renderOneHop(oneHop, container) {
  const headingRow = document.createElement("div");
  headingRow.className = "section-heading-row";
  const h3 = document.createElement("h3");
  h3.textContent = t("one_hop_heading");
  headingRow.appendChild(h3);
  headingRow.appendChild(buildInspirationLegend());
  container.appendChild(headingRow);
  container.appendChild(
    layoutMode === "classic" ? buildCycleTable(oneHop.cycles) : buildGenealogyCards(oneHop.cycles),
  );
  buildIndependentTrainingSection(oneHop.cycles, container);
}

// Independent training (2026-08-10): calcolo AGGIUNTIVO e SEPARATO
// dall'affinita'/bonus di cui sopra (mai usato per calcolare quelle) -- una
// tabella per ciclo con la probabilita' REALE di vincere ciascuna gara del
// figlio (aptitude + fatica da turni consecutivi), invece della soglia
// binaria si'/no del resto del tool. Riga verde/rossa (CSS, non nuovi colori
// hardcoded) secondo `recommended` (gia' deciso dal server in base alla
// soglia corrente), numero esatto sempre visibile in cella.
function buildIndependentTrainingTable(entries) {
  const table = document.createElement("table");
  table.className = "independent-training-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>${t("th_race")}</th><th>${t("th_year")}</th>
        <th>${t("th_streak")}</th><th>${t("th_win_probability")}</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  entries.forEach(entry => {
    const tr = document.createElement("tr");
    tr.className = entry.recommended ? "it-recommended" : "it-not-recommended";
    const yearLabel = entry.year != null ? `Y${entry.year}` : "–";
    const mandatoryBadge = entry.is_mandatory
      ? ` <span class="it-mandatory-badge">${t("it_mandatory_badge")}</span>` : "";
    tr.innerHTML = `
      <td>${entry.race_label}${mandatoryBadge}</td>
      <td>${yearLabel}</td>
      <td>${entry.streak_position}</td>
      <td><strong>${Math.round(entry.probability)}%</strong></td>
    `;
    tbody.appendChild(tr);
  });
  return table;
}

function buildIndependentTrainingSection(cycles, container) {
  if (!cycles.some(c => c.independent_training)) return null;
  const details = makeCollapsibleSection(t("it_section_title"), container);
  details.classList.add("independent-training-section");
  details.open = true;  // sezione esterna aperta di default...
  cycles.forEach((cycle, i) => {
    if (!cycle.independent_training) return;
    // ...ma ogni singolo ciclo collassato di default (details.open = false,
    // default nativo): con 5 cicli x ~25-30 righe ciascuno la tabella
    // intera sarebbe troppo lunga da scorrere, meglio aprirne uno alla volta.
    const cycleDetails = makeCollapsibleSection(
      t("it_cycle_heading", { cycle: i + 1, name: formatCharacterName(cycle.child) }),
      details,
    );
    cycleDetails.classList.add("independent-training-cycle");
    cycleDetails.appendChild(buildIndependentTrainingTable(cycle.independent_training));
  });
  return details;
}

// --- Timeline delle carriere: gestione a schede (2026-07-30) -------------
// Una scheda "Originale" (aptitude base, sempre presente quando c'e' un
// calendario) e una scheda "Con spark" che appare SOLO dopo aver calcolato
// un piano spark (Modalita' A o B) — non sovrascrive mai la prima, e si
// attiva automaticamente quando viene (ri)calcolata. Ricalcolare le spark
// piu' volte SOSTITUISCE la stessa scheda "Con spark" (non ne crea altre).

let timelineTabs = [];  // [{id, label, calendarMatrix, groupMembers}]
let activeTimelineTabId = null;

function resetTimelineTabs() {
  timelineTabs = [];
  activeTimelineTabId = null;
  renderTimelinePanel();
}

function setTimelineTab(id, label, calendarMatrix, groupMembers, activate = false, separatorIndex = null) {
  const tab = { id, label, calendarMatrix, groupMembers, separatorIndex };
  const existingIndex = timelineTabs.findIndex(t => t.id === id);
  if (existingIndex >= 0) timelineTabs[existingIndex] = tab;
  else timelineTabs.push(tab);
  if (activate || activeTimelineTabId === null) activeTimelineTabId = id;
  renderTimelinePanel();
}

function buildTimelineContent(calendarMatrix, groupMembers, separatorIndex = null) {
  const fragment = document.createDocumentFragment();
  if (!calendarMatrix) {
    const p = document.createElement("p");
    p.className = "placeholder";
    p.textContent = t("timeline_no_calendar");
    fragment.appendChild(p);
    return fragment;
  }

  const table = document.createElement("table");
  table.className = "timeline-table";

  const theadRow = document.createElement("tr");
  theadRow.innerHTML = `<th class="race-col">${t("timeline_race_col")}</th>` +
    groupMembers.map((c, i) => `<th class="char-col${i === separatorIndex ? " col-separator" : ""}">${formatCharacterName(c)}</th>`).join("");
  const thead = document.createElement("thead");
  thead.appendChild(theadRow);
  table.appendChild(thead);

  const symbolFor = (cell) => {
    if (cell.status === "obbligatoria") return cell.winnable ? "●" : "○";
    if (cell.status === "impossibile") return "–";
    if (cell.status === "raggiungibile") return cell.shared ? "★" : "✓";
    return "△";  // aptitude
  };
  const classFor = (cell) => {
    if (cell.status === "obbligatoria") return cell.winnable ? "cal-obbligatoria" : "cal-obbligatoria-non-vincibile";
    if (cell.status === "impossibile") return "cal-impossibile";
    if (cell.status === "raggiungibile") return cell.shared ? "cal-condivisa" : "cal-raggiungibile";
    return "cal-aptitude";
  };
  const titleFor = (char, cell) => {
    const labels = {
      obbligatoria: cell.winnable ? t("status_obbligatoria") : t("status_obbligatoria_non_vincibile"),
      impossibile: t("status_impossibile"),
      raggiungibile: cell.shared ? t("status_raggiungibile_condivisa") : t("status_raggiungibile"),
      aptitude: t("status_aptitude"),
    };
    return `${formatCharacterName(char)}: ${labels[cell.status]}`;
  };

  const tbody = document.createElement("tbody");
  calendarMatrix.forEach(row => {
    const tr = document.createElement("tr");
    const raceCell = document.createElement("td");
    raceCell.className = "race-col";
    raceCell.textContent = row.label;
    raceCell.title = row.label;
    tr.appendChild(raceCell);

    groupMembers.forEach((char, i) => {
      const cell = row.cells[char];
      const td = document.createElement("td");
      td.className = `cell ${classFor(cell)}${i === separatorIndex ? " col-separator" : ""}`;
      td.textContent = symbolFor(cell);
      td.title = titleFor(char, cell);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  fragment.appendChild(table);

  const legend = document.createElement("div");
  legend.className = "timeline-legend";
  legend.innerHTML = `
    <div><span class="swatch cal-obbligatoria"></span>${t("legend_obbligatoria")}</div>
    <div><span class="swatch cal-obbligatoria-non-vincibile"></span>${t("legend_obbligatoria_non_vincibile")}</div>
    <div><span class="swatch cal-impossibile"></span>${t("legend_impossibile")}</div>
    <div><span class="swatch cal-condivisa"></span>${t("legend_condivisa")}</div>
    <div><span class="swatch cal-raggiungibile"></span>${t("legend_raggiungibile")}</div>
    <div><span class="swatch cal-aptitude"></span>${t("legend_aptitude")}</div>
  `;
  fragment.appendChild(legend);
  return fragment;
}

function renderTimelinePanel() {
  timelinePanel.innerHTML = "";
  if (timelineTabs.length === 0) {
    timelinePanel.innerHTML = `<p class="placeholder">${t("placeholder_timeline")}</p>`;
    return;
  }
  if (timelineTabs.length > 1) {
    const tabBar = document.createElement("div");
    tabBar.className = "timeline-tab-bar";
    timelineTabs.forEach(tab => {
      const tabButton = document.createElement("button");
      tabButton.type = "button";
      tabButton.className = "timeline-tab" + (tab.id === activeTimelineTabId ? " timeline-tab-active" : "");
      tabButton.textContent = tab.label;
      tabButton.addEventListener("click", () => {
        activeTimelineTabId = tab.id;
        renderTimelinePanel();
      });
      tabBar.appendChild(tabButton);
    });
    timelinePanel.appendChild(tabBar);
  }
  const activeTab = timelineTabs.find(t => t.id === activeTimelineTabId) || timelineTabs[0];
  timelinePanel.appendChild(buildTimelineContent(activeTab.calendarMatrix, activeTab.groupMembers, activeTab.separatorIndex));
}

function disablePdfButton() {
  pdfContext = null;
  pdfButton.disabled = true;
  pdfStatus.textContent = "";
}

// Card candidato Top-4 (layout moderno) -- alternativa alla tabella classica
// costruita in renderTop4 in modalita' "classic": stessi dati, ritratto +
// nome + punteggi invece di righe di tabella.
function buildCandidateCards(top4) {
  const row = document.createElement("div");
  row.className = "candidate-row";
  top4.forEach(entry => {
    const card = document.createElement("div");
    card.className = "candidate-card";
    card.appendChild(buildPortraitWrap(entry.character));

    const info = document.createElement("div");
    info.className = "candidate-info";

    const name = document.createElement("div");
    name.className = "candidate-name";
    name.appendChild(document.createTextNode(formatCharacterName(entry.character)));
    if (entry.is_meta_parent) {
      const badge = document.createElement("span");
      badge.className = "meta-tag";
      badge.textContent = t("meta_tag");
      name.appendChild(badge);
    }
    info.appendChild(name);

    const scores = document.createElement("div");
    scores.className = "candidate-scores";
    scores.innerHTML = `
      <span class="candidate-score-total">${t("th_total")}: <strong>${entry.total}</strong></span>
      <span>${t("th_base")}: <strong>${entry.base}</strong></span>
      <span>${t("th_race")}: <strong>${entry.race}</strong></span>
    `;
    info.appendChild(scores);

    card.appendChild(info);
    row.appendChild(card);
  });
  return row;
}

function renderTop4(data) {
  lastRun = { type: "top4", data };
  disablePdfButton();  // riabilitato da renderPinkSparkPanel se un one_hop produce un pannello
  results.innerHTML = renderWarning(data.warning);
  debugPanel.innerHTML = "";
  resetTimelineTabs();
  let timelineRendered = false;
  data.results.forEach(({
    target, top4, top10_base, top10_race, top10_total, one_hop, one_hop_error,
    calendar_matrix, group_aptitudes,
  }) => {
    const h2 = document.createElement("h2");
    h2.textContent = t("top4_heading", { name: formatCharacterName(target) });
    results.appendChild(h2);

    if (layoutMode === "classic") {
      const table = document.createElement("table");
      table.innerHTML = `
        <thead>
          <tr><th>${t("table_header_character")}</th><th>${t("th_total")}</th><th>${t("th_base")}</th><th>${t("th_race")}</th><th></th></tr>
        </thead>
        <tbody></tbody>
      `;
      const tbody = table.querySelector("tbody");
      top4.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${formatCharacterName(row.character)}</td>
          <td><strong>${row.total}</strong></td>
          <td><strong>${row.base}</strong></td>
          <td><strong>${row.race}</strong></td>
          <td>${row.is_meta_parent ? `<span class="meta-tag">${t("meta_tag")}</span>` : ""}</td>
        `;
        tbody.appendChild(tr);
      });
      results.appendChild(table);
    } else {
      results.appendChild(buildCandidateCards(top4));
    }

    // Esplorazione a un salto + piano spark: SEMPRE visibili (non solo in
    // modalita' debug), perche' non sono dettagli diagnostici ma la feature
    // principale per pianificare il loop.
    if (one_hop) {
      renderOneHop(one_hop, results);
      if (one_hop.first_cycle_races) renderFirstCycleRaces(one_hop.first_cycle_races, results);
      renderPinkSparkPanel(one_hop, target, group_aptitudes, calendar_matrix, results);
    }
    if (one_hop_error) {
      const p = document.createElement("p");
      p.className = "warning";
      p.textContent = translateServerMessage(one_hop_error);
      results.appendChild(p);
    }

    // modalita' debug: le liste top-10 aggiuntive vanno in #debug-panel, NON
    // in #results -- cosi' i risultati restano leggibili anche con debug
    // attivo invece di allungarsi con le tabelle diagnostiche in mezzo (vedi
    // il tag <section id="debug-panel"> in index.html).
    if (top10_base || top10_race || top10_total) {
      if (data.results.length > 1) {
        const targetHeading = document.createElement("h3");
        targetHeading.textContent = formatCharacterName(target);
        debugPanel.appendChild(targetHeading);
      }
      const debugBox = document.createElement("details");
      debugBox.className = "debug-box";
      debugBox.open = true;
      const debugSummary = document.createElement("summary");
      debugSummary.textContent = t("debug_details_title");
      debugBox.appendChild(debugSummary);

      if (one_hop) renderOverallAffinityFormulas(one_hop.cycles, debugBox);
      if (top10_total) renderTop10TotalList(t("top10_total_title", { name: formatCharacterName(target) }), top10_total, debugBox);
      if (top10_base) renderTop10List(t("top10_base_title", { name: formatCharacterName(target) }), top10_base, debugBox);
      if (top10_race) renderTop10List(t("top10_race_title", { name: formatCharacterName(target) }), top10_race, debugBox);

      debugPanel.appendChild(debugBox);
    }

    if (!timelineRendered && calendar_matrix) {
      setTimelineTab("original", t("tab_original"), calendar_matrix, [target, ...top4.map(r => r.character)], true);
      timelineRendered = true;
    }
  });
  debugPanel.hidden = debugPanel.childElementCount === 0;
}

function renderLoop(data) {
  lastRun = { type: "loop", data };
  disablePdfButton();  // modalita' "Miglior loop a 5" non produce la struttura cycles richiesta dal PDF
  results.innerHTML = renderWarning(data.warning);
  debugPanel.innerHTML = "";
  debugPanel.hidden = true;
  const h2 = document.createElement("h2");
  h2.textContent = t("loop_heading", { value: data.total_score });
  results.appendChild(h2);

  const ul = document.createElement("ul");
  data.group.forEach(member => {
    const li = document.createElement("li");
    li.textContent = formatCharacterName(member.character) + (member.is_meta_parent ? t("meta_suffix") : "");
    ul.appendChild(li);
  });
  results.appendChild(ul);

  resetTimelineTabs();
  setTimelineTab("original", t("tab_original"), data.calendar_matrix, data.group.map(m => m.character), true);
}

// Intestazione comune alle due tabelle sotto: due blocchi affiancati, ogni
// blocco ripete le stesse colonne (la colonna rank/# non ha un'intestazione,
// e' implicita). 'labels' = [nomeColonna2, nomeColonna3, nomeColonna4] (la
// prima colonna di ogni blocco e' sempre il rank, senza header).
function buildGpTableHead(labels) {
  const thead = document.createElement("thead");
  const tr = document.createElement("tr");
  const cells = labels.map(l => `<th>${l}</th>`).join("");
  tr.innerHTML = `<th></th>${cells}<th class="gp-divider"></th>${cells}`;
  thead.appendChild(tr);
  return thead;
}

// Tabella compatta per i suggerimenti nonni: sfrutta lo spazio orizzontale
// mostrando due blocchi (#, nome, affinita' per step, totale) affiancati
// invece di una lista verticale lunga -- prima meta' a sinistra, seconda
// meta' a destra, ordinate per somma decrescente, righe allineate per
// indice (non intrecciate 1,3,5.../2,4,6...).
function buildGpSuggestionsTable(suggestions) {
  const half = Math.ceil(suggestions.length / 2);
  const left = suggestions.slice(0, half);
  const right = suggestions.slice(half);
  const table = document.createElement("table");
  table.className = "gp-suggestions-table";
  table.appendChild(buildGpTableHead([t("table_header_character"), t("th_gp_affinity_steps"), t("th_gp_total")]));
  const tbody = document.createElement("tbody");
  const stepsText = s => s ? s.affinities.join(" / ") : "";
  const totalText = s => s ? s.affinities.reduce((a, b) => a + b, 0) : "";
  left.forEach((l, i) => {
    const r = right[i];
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="gp-rank">${i + 1}</td>
      <td>${formatCharacterName(l.character)}</td>
      <td class="gp-affinity">${stepsText(l)}</td>
      <td class="gp-affinity">${totalText(l)}</td>
      <td class="gp-rank gp-divider">${r ? half + i + 1 : ""}</td>
      <td>${r ? formatCharacterName(r.character) : ""}</td>
      <td class="gp-affinity">${stepsText(r)}</td>
      <td class="gp-affinity">${totalText(r)}</td>
    `;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  return table;
}

// Tabella delle migliori COPPIE di nonni: quanto aggiungono all'Overall
// Affinity di ciascuno dei 3 step se inserite ENTRAMBE (diverso dalla
// tabella sopra, che valuta un candidato alla volta) -- stesso layout a due
// blocchi affiancati (5+5, ordinate per somma decrescente) della tabella
// sopra.
function buildGpPairSuggestionsTable(pairs) {
  const half = Math.ceil(pairs.length / 2);
  const left = pairs.slice(0, half);
  const right = pairs.slice(half);
  const table = document.createElement("table");
  table.className = "gp-suggestions-table";
  table.appendChild(buildGpTableHead([t("th_gp_pair"), t("th_gp_deltas"), t("th_gp_total")]));
  const tbody = document.createElement("tbody");
  const pairName = p => p ? `${formatCharacterName(p.gp_a)}<br>${formatCharacterName(p.gp_b)}` : "";
  const pairDelta = p => p ? p.deltas.map(d => (d >= 0 ? "+" : "") + d).join(" / ") : "";
  const pairTotal = p => p ? (p.total_delta >= 0 ? "+" : "") + p.total_delta : "";
  left.forEach((l, i) => {
    const r = right[i];
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="gp-rank">${i + 1}</td>
      <td>${pairName(l)}</td>
      <td class="gp-affinity">${pairDelta(l)}</td>
      <td class="gp-affinity">${pairTotal(l)}</td>
      <td class="gp-rank gp-divider">${r ? half + i + 1 : ""}</td>
      <td>${pairName(r)}</td>
      <td class="gp-affinity">${pairDelta(r)}</td>
      <td class="gp-affinity">${pairTotal(r)}</td>
    `;
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  return table;
}

function renderRentalResult(data) {
  lastRun = { type: "rental", data };
  disablePdfButton();  // il rental loop non produce la struttura richiesta dal PDF (fuori scope)
  results.innerHTML = renderWarning(data.warning);
  debugPanel.innerHTML = "";
  debugPanel.hidden = true;

  const headingRow = document.createElement("div");
  headingRow.className = "section-heading-row";
  const h2 = document.createElement("h2");
  h2.textContent = t("rental_heading", { name: formatCharacterName(data.anchor) });
  headingRow.appendChild(h2);
  headingRow.appendChild(buildInspirationLegend());
  results.appendChild(headingRow);

  if (!data.gp_known) {
    const note = document.createElement("p");
    note.className = "warning";
    note.textContent = t("rental_partial_note");
    results.appendChild(note);
  }

  const totalLine = document.createElement("p");
  totalLine.className = "total-loop-affinity";
  totalLine.innerHTML = `${t("rental_total_label")}: <strong>${data.total_loop_affinity}</strong>`;
  results.appendChild(totalLine);

  results.appendChild(
    layoutMode === "classic" ? buildCycleTable(data.cycles) : buildGenealogyCards(data.cycles),
  );
  buildIndependentTrainingSection(data.cycles, results);

  const hasSingle = data.gp_suggestions && data.gp_suggestions.length;
  const hasPairs = data.gp_pair_suggestions && data.gp_pair_suggestions.length;
  if (hasSingle || hasPairs) {
    const row = document.createElement("div");
    row.className = "gp-suggestions-row";
    if (hasSingle) {
      const box = document.createElement("div");
      const label = document.createElement("p");
      label.textContent = t("rental_gp_suggestions_label");
      box.appendChild(label);
      box.appendChild(buildGpSuggestionsTable(data.gp_suggestions));
      row.appendChild(box);
    }
    if (hasPairs) {
      const box2 = document.createElement("div");
      const label2 = document.createElement("p");
      label2.textContent = t("rental_gp_pairs_label");
      box2.appendChild(label2);
      box2.appendChild(buildGpPairSuggestionsTable(data.gp_pair_suggestions));
      row.appendChild(box2);
    }
    results.appendChild(row);
  }

  resetTimelineTabs();
  // colonne: i 3 posseduti della rotazione, poi l'anchor per ultimo con un
  // separatore visivo (vedi setTimelineTab/buildTimelineContent, col-separator)
  const timelineMembers = [...data.members, data.anchor];
  setTimelineTab("original", t("tab_original"), data.calendar_matrix, timelineMembers, true, timelineMembers.length - 1);
}

// Un ace + i suoi 6 antenati e' esattamente un "ciclo" (vedi ace_planner.py):
// data.cycles ha lo STESSO formato di quelli di /api/top4 e /api/rental_loop,
// quindi si riusano buildCycleTable/buildGenealogyCards senza modifiche.
function renderAcePlan(data) {
  lastRun = { type: "ace", data };
  disablePdfButton();  // il piano ace non produce la struttura richiesta dal PDF (fuori scope, come loop/rental)
  results.innerHTML = renderWarning(data.warning);
  debugPanel.innerHTML = "";
  debugPanel.hidden = true;

  const h2 = document.createElement("h2");
  h2.textContent = t("ace_heading");
  results.appendChild(h2);

  const totalLine = document.createElement("p");
  totalLine.className = "total-loop-affinity";
  totalLine.innerHTML = `${t("ace_total_label")}: <strong>${data.total_affinity}</strong>`;
  results.appendChild(totalLine);

  results.appendChild(
    layoutMode === "classic" ? buildCycleTable(data.cycles) : buildGenealogyCards(data.cycles),
  );

  resetTimelineTabs();  // nessun calendario per il piano ace (v1): pannello a placeholder
}

async function runQuery() {
  const mode = modeSelect.value;
  const calendarMode = calendarSelect.value;
  const globalOnly = globalOnlyCheckbox.checked;
  const owned = getOwnedSelection();
  const minAptitude = getMinAptitude();
  const itThreshold = getIndependentTrainingThreshold();
  results.innerHTML = `<p class="placeholder">${t("calc_in_progress")}</p>`;

  try {
    if (mode === "top4") {
      // ID esatto della variante risolta (mai il nome base, che il server
      // potrebbe risolvere ad ambiguita' su piu' varianti -- vedi
      // getResolvedCharacter/buildAptitudeOverridePanel): garantisce che
      // venga eseguita SOLO la variante scelta dall'utente, mai entrambe.
      const character = getResolvedCharacter();
      const resp = await fetch("/api/top4", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          character, mode: calendarMode, global_only: globalOnly, owned,
          min_aptitude: minAptitude, debug: debugCheckbox.checked,
          independent_training_threshold: itThreshold,
          aptitude_override: getAptitudeOverride(),
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(translateServerMessage(data.error) || t("error_unknown"));
      renderTop4(data);
    } else if (mode === "loop") {
      const mustInclude = getMustInclude();
      const resp = await fetch("/api/loop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: calendarMode, global_only: globalOnly, owned, min_aptitude: minAptitude,
          must_include: mustInclude, pool_size: 20,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(translateServerMessage(data.error) || t("error_unknown"));
      renderLoop(data);
    } else if (mode === "rental") {
      const resp = await fetch("/api/rental_loop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: calendarMode, global_only: globalOnly, owned, min_aptitude: minAptitude,
          anchor: rentalAnchorSelect.value,
          anchor_gp_a: rentalGpASelect.value, anchor_gp_b: rentalGpBSelect.value,
          fixed_members: getRentalFixedMembers(),
          independent_training_threshold: itThreshold,
          anchor_spark_plan: getRentalSparkInput(),
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(translateServerMessage(data.error) || t("error_unknown"));
      renderRentalResult(data);
    } else if (mode === "ace") {
      const { aces, slots, shared_groups } = getAcePayload();
      const resp = await fetch("/api/ace_plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          aces, mode: calendarMode, global_only: globalOnly, owned, min_aptitude: minAptitude,
          slots, shared_groups,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(translateServerMessage(data.error) || t("error_unknown"));
      renderAcePlan(data);
    }
  } catch (err) {
    results.innerHTML = `<p class="placeholder">${t("error_prefix", { message: err.message })}</p>`;
  }
}

runButton.addEventListener("click", runQuery);

// --- Salvataggio/caricamento JSON (2026-08-01) -----------------------------
// Obiettivo: al caricamento la schermata deve apparire ESATTAMENTE come al
// momento del salvataggio. Approccio: invece di duplicare la logica di
// rendering in un secondo "motore di ripristino" parallelo, il caricamento
// RIUSA le stesse funzioni di rendering gia' esistenti:
//   - controlli (mode/calendario/filtri/posseduti/lingua) -> riassegnati
//     direttamente agli elementi del form.
//   - risultati principali (top4/loop) -> renderTop4(data)/renderLoop(data),
//     le stesse funzioni gia' usate per il cambio lingua (vedi setLang):
//     data e' l'intera risposta "congelata" del server al momento della
//     ricerca, quindi il rendering e' bit-per-bit identico.
//   - pannello spark (Modalita' A/B, se presenti): l'input dell'utente viene
//     riletto direttamente dal DOM al salvataggio (collectSparkPanelState) e
//     ririempito simulando le stesse interazioni che l'utente farebbe
//     (dispatchEvent di change/input, click sul bottone "Aggiungi") --
//     nessuna duplicazione della logica interna di buildSparkCycleBox/
//     buildSignatureSparkSection. Il risultato calcolato di /api/pink_spark
//     (se presente) e' anch'esso "congelato" e ridisegnato con la stessa
//     renderSparkResultData usata dal calcolo live, senza richiamare il
//     server (cosi' il salvataggio resta valido anche se i dati di gioco
//     cambiano nel frattempo).

function defaultSaveName() {
  const d = new Date();
  const pad = n => String(n).padStart(2, "0");
  return `Save_${d.getFullYear()}_${pad(d.getMonth() + 1)}_${pad(d.getDate())}`;
}

function collectSparkPanelState(panel) {
  const modeAPlan = collectSparkPlan(panel);  // {cicloStr: {categoria: stelle}}
  const modeBPlan = {};
  panel.querySelectorAll(".spark-b-assignment-list li").forEach(li => {
    modeBPlan[li.dataset.character] = { [li.dataset.category]: Number(li.dataset.stars) };
  });
  const resultBox = panel.querySelector(".spark-result");
  return {
    target: panel.dataset.target,
    mode_a_plan: modeAPlan,
    mode_b_plan: modeBPlan,
    result: resultBox ? (resultBox._sparkResultData || null) : null,
  };
}

function collectAllSparkPanels() {
  return Array.from(document.querySelectorAll(".spark-panel")).map(collectSparkPanelState);
}

function buildSaveData() {
  return {
    app: "uma_legacy_loop_tool_save",
    version: 1,
    saved_at: new Date().toISOString(),
    lang: currentLang,
    controls: {
      mode: modeSelect.value,
      calendar_mode: calendarSelect.value,
      global_only: globalOnlyCheckbox.checked,
      debug: debugCheckbox.checked,
      owned: getOwnedSelection(),
      owned_sort: ownedSortSelect.value,
      owned_sort_descending: ownedSortDescending,
      character: characterSelect.value,
      must_include: getMustInclude(),
      min_aptitude: getMinAptitude(),
      rental_anchor: rentalAnchorSelect.value,
      rental_gp_a: rentalGpASelect.value,
      rental_gp_b: rentalGpBSelect.value,
      rental_fixed_members: getRentalFixedMembers(),
    },
    last_run: lastRun,  // { type: "top4"|"loop", data } congelato, o null se nessuna ricerca ancora fatta
    spark_panels: collectAllSparkPanels(),
    active_timeline_tab: activeTimelineTabId,
  };
}

async function handleSaveClick() {
  const suggested = defaultSaveName();
  const input = window.prompt(t("save_filename_prompt"), suggested);
  if (input === null) return;  // annullato esplicitamente: nessun salvataggio
  const name = input.trim() || suggested;
  const filename = name.toLowerCase().endsWith(".json") ? name : `${name}.json`;

  const payload = buildSaveData();
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function restoreSparkPanels(sparkPanelsState) {
  if (!Array.isArray(sparkPanelsState)) return;
  sparkPanelsState.forEach(state => {
    if (!state || !state.target) return;
    const panel = document.querySelector(`.spark-panel[data-target="${state.target}"]`);
    if (!panel) return;

    // Modalita' A: per ogni ciclo salvato, riempie le righe libere e simula
    // gli stessi eventi change/input che l'utente scatenerebbe a mano, cosi'
    // i listener gia' presenti (validazione, anteprima aptitude) fanno il
    // resto senza duplicare logica qui.
    Object.entries(state.mode_a_plan || {}).forEach(([cycleNum, plan]) => {
      const cycleBox = panel.querySelector(`.spark-cycle[data-cycle="${cycleNum}"]`);
      if (!cycleBox) return;
      const rows = Array.from(cycleBox.querySelectorAll(".spark-row"));
      Object.entries(plan).forEach(([category, stars], idx) => {
        const row = rows[idx];
        if (!row) return;
        const select = row.querySelector(".spark-category-select");
        const input = row.querySelector(".spark-star-input");
        select.value = category;
        select.dispatchEvent(new Event("change"));
        input.value = String(stars);
        input.dispatchEvent(new Event("input"));
      });
    });

    // Modalita' B: simula un click su "Aggiungi" per ogni spark firma
    // salvata -- stesso identico codice del click reale (vedi addButton in
    // buildSignatureSparkSection), nessuno stato interno riscritto a mano.
    const charSelect = panel.querySelector(".spark-b-character-select");
    const catSelect = panel.querySelector(".spark-b-category-select");
    const starInput = panel.querySelector(".spark-b-star-input");
    const addButton = panel.querySelector(".spark-b-add-button");
    if (charSelect && catSelect && starInput && addButton) {
      Object.entries(state.mode_b_plan || {}).forEach(([character, plan]) => {
        const [category, stars] = Object.entries(plan)[0];
        charSelect.value = character;
        catSelect.value = category;
        starInput.value = String(stars);
        addButton.click();
      });
    }

    if (state.result) {
      const resultBox = panel.querySelector(".spark-result");
      renderSparkResultData(resultBox, state.result, { activateTimeline: false });
    }
  });
}

async function restoreFromSave(save) {
  if (!save || typeof save !== "object") {
    throw new Error(t("load_error", { message: "JSON non valido" }));
  }

  if (save.lang === "it" || save.lang === "en") {
    currentLang = save.lang;
    try {
      localStorage.setItem(LANG_STORAGE_KEY, currentLang);
    } catch (err) {
      // localStorage non disponibile: non bloccante.
    }
  }

  const controls = save.controls || {};
  if (controls.mode) modeSelect.value = controls.mode;
  if (controls.calendar_mode) calendarSelect.value = controls.calendar_mode;
  if (typeof controls.global_only === "boolean") globalOnlyCheckbox.checked = controls.global_only;
  if (typeof controls.debug === "boolean") debugCheckbox.checked = controls.debug;
  if (typeof controls.owned_sort_descending === "boolean") ownedSortDescending = controls.owned_sort_descending;
  if (controls.owned_sort) ownedSortSelect.value = controls.owned_sort;
  if (Array.isArray(controls.owned)) ownedSelection = new Set(controls.owned);

  await charactersLoadedPromise;  // le select dei personaggi devono essere popolate prima di assegnare i loro valori

  updateFieldVisibility();
  applyCalendarTabButtons();
  applyStaticTranslations();
  renderOwnedList();
  populateMustIncludeSelects();
  renderCharacterSelect();
  savePersistedSettings();

  if (controls.character) characterSelect.value = controls.character;
  buildAptitudeOverridePanel();  // override mai salvato/ripristinato (temporaneo per definizione): riparte vuoto per il personaggio ripristinato
  if (Array.isArray(controls.must_include)) {
    controls.must_include.forEach((name, i) => {
      if (mustIncludeSelects[i]) mustIncludeSelects[i].value = name;
    });
  }
  if (controls.min_aptitude) {
    minAptitudeSelects.forEach(select => {
      if (controls.min_aptitude[select.dataset.category]) {
        select.value = controls.min_aptitude[select.dataset.category];
      }
    });
    renderMinAptitudeTable();
  }
  if (controls.rental_anchor) rentalAnchorSelect.value = controls.rental_anchor;
  if (controls.rental_gp_a) rentalGpASelect.value = controls.rental_gp_a;
  if (controls.rental_gp_b) rentalGpBSelect.value = controls.rental_gp_b;
  if (Array.isArray(controls.rental_fixed_members)) {
    controls.rental_fixed_members.forEach((name, i) => {
      if (rentalFixedSelects[i]) rentalFixedSelects[i].value = name;
    });
  }
  buildRentalSparkPanel();  // piano spark mai salvato/ripristinato (temporaneo per definizione): riparte vuoto

  if (save.last_run && save.last_run.type === "top4") {
    renderTop4(save.last_run.data);
    restoreSparkPanels(save.spark_panels);
  } else if (save.last_run && save.last_run.type === "loop") {
    renderLoop(save.last_run.data);
  } else if (save.last_run && save.last_run.type === "rental") {
    renderRentalResult(save.last_run.data);
  } else {
    lastRun = null;
    disablePdfButton();
    results.innerHTML = `<p class="placeholder">${t("placeholder_results")}</p>`;
    resetTimelineTabs();
  }

  if (save.active_timeline_tab && timelineTabs.some(tab => tab.id === save.active_timeline_tab)) {
    activeTimelineTabId = save.active_timeline_tab;
    renderTimelinePanel();
  }
}

function handleLoadFile(file) {
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const save = JSON.parse(reader.result);
      await restoreFromSave(save);
    } catch (err) {
      results.innerHTML = `<p class="placeholder">${t("load_error", { message: err.message })}</p>`;
    }
  };
  reader.onerror = () => {
    results.innerHTML = `<p class="placeholder">${t("load_error", { message: reader.error })}</p>`;
  };
  reader.readAsText(file);
}

// Import/export della selezione posseduti compatibile col Collection
// Tracker di Gametora (gametora.com/umamusume/collection-tracker, "Backup" >
// Export/Import, formato verificato dal vivo il 2026-08-12). Le mappe
// tid <-> nostro ID interno arrivano da data_updater (Fonte 5), rigenerate
// insieme al resto dei dati ogni 24 ore -- crescono da sole man mano che il
// tool traccia piu' personaggi/varianti.
// gametoraTidMap: abbinamento ESATTO (stessa variante/costume tracciata).
// gametoraTidFallbackMap: SOLO per tid assenti da gametoraTidMap ma il cui
//   personaggio e' comunque tracciato sotto un'altra variante -- caso reale
//   segnalato dall'utente: possedere su Gametora solo "Rice Shower
//   Halloween" (non tracciata separatamente da questo tool) non faceva
//   risultare posseduta nemmeno "Rice Shower" base, pur essendo la STESSA
//   umamusume ai fini di aptitude/carriera del looping.
// gametoraTidNames: nome leggibile per OGNI tid conosciuto, usato solo per
//   mostrare all'utente le carte rimaste comunque irrisolte (vedi
//   handleGametoraImportFile).
let gametoraTidMap = {};
let gametoraTidFallbackMap = {};
let gametoraTidNames = {};
let gametoraIdToTid = {};   // inverso di gametoraTidMap, per l'export

async function loadGametoraTidMap() {
  try {
    const [mapResp, fallbackResp, namesResp] = await Promise.all([
      fetch("/api/gametora_tid_map"),
      fetch("/api/gametora_tid_fallback_map"),
      fetch("/api/gametora_tid_names"),
    ]);
    gametoraTidMap = await mapResp.json();
    gametoraTidFallbackMap = await fallbackResp.json();
    gametoraTidNames = await namesResp.json();
  } catch (err) {
    // rete assente: import/export restano no-op, mai un errore bloccante all'avvio
    gametoraTidMap = {};
    gametoraTidFallbackMap = {};
    gametoraTidNames = {};
  }
  gametoraIdToTid = {};
  Object.entries(gametoraTidMap).forEach(([tid, id]) => { gametoraIdToTid[id] = tid; });
}
const gametoraTidMapLoadedPromise = loadGametoraTidMap();

function handleGametoraExportClick() {
  const charCards = {};
  ownedSelection.forEach(id => {
    const tid = gametoraIdToTid[id];
    // Le stelle (limit break) non sono un concetto tracciato da questo tool:
    // valore fisso, ignorato sia da noi in lettura sia (verificato) da
    // Gametora per un import "Trainees" -- conta solo la presenza della chiave.
    if (tid) charCards[tid] = 3;
  });
  const payload = {
    app: "gametora", game: "umamusume", type: "collection", version: 4,
    timestamp: new Date().toISOString(),
    servers: { en: { charCards } },
  };
  const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "gametora_collection_export.json";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function showGametoraImportStatus(message) {
  gametoraImportStatus.textContent = message;
  gametoraImportStatus.hidden = false;
}

// Elenco puntato multicolonna delle carte Gametora rimaste irrisolte anche
// dopo il fallback (nessuna riga tracciata, nemmeno di un'altra variante,
// per quel personaggio) -- richiesto dall'utente per capire A COLPO D'OCCHIO
// cosa e' stato ignorato, invece di un semplice conteggio.
function renderGametoraSkippedList(skippedTids) {
  if (skippedTids.length === 0) {
    gametoraImportSkipped.hidden = true;
    gametoraImportSkippedList.innerHTML = "";
    return;
  }
  gametoraImportSkippedList.innerHTML = "";
  skippedTids.forEach(tid => {
    const li = document.createElement("li");
    li.textContent = gametoraTidNames[tid] || tid;
    gametoraImportSkippedList.appendChild(li);
  });
  gametoraImportSkipped.hidden = false;
}

async function handleGametoraImportFile(file) {
  await gametoraTidMapLoadedPromise;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      const charCards = data && data.servers && data.servers.en && data.servers.en.charCards;
      if (!charCards || typeof charCards !== "object") {
        throw new Error("formato non riconosciuto (atteso un export \"Trainees\" del Collection Tracker di Gametora)");
      }
      const tids = Object.keys(charCards);
      const matched = new Set();
      const skippedTids = [];
      tids.forEach(tid => {
        // abbinamento esatto prima, poi il fallback (stessa umamusume sotto
        // un'altra variante non tracciata separatamente) -- solo se nessuno
        // dei due risolve, la carta resta davvero irrisolta.
        const id = gametoraTidMap[tid] || gametoraTidFallbackMap[tid];
        if (id) matched.add(id);
        else skippedTids.push(tid);
      });
      ownedSelection = matched;  // SOSTITUISCE la selezione attuale (scelta confermata dall'utente)
      renderOwnedList();
      savePersistedSettings();
      renderGametoraSkippedList(skippedTids);
      showGametoraImportStatus(t("gametora_import_success", { count: matched.size, unmatched: skippedTids.length }));
    } catch (err) {
      showGametoraImportStatus(t("gametora_import_error", { message: err.message }));
      renderGametoraSkippedList([]);
    }
  };
  reader.onerror = () => {
    showGametoraImportStatus(t("gametora_import_error", { message: reader.error }));
  };
  reader.readAsText(file);
}

saveButton.addEventListener("click", handleSaveClick);
loadButton.addEventListener("click", () => loadFileInput.click());
pdfButton.addEventListener("click", () => {
  if (pdfContext) handleGeneratePdf(pdfContext.oneHop, pdfContext.target, pdfContext.resultBox, pdfStatus);
});

autoUpdateCheckbox.addEventListener("change", () => {
  fetch("/api/auto_update_setting", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled: autoUpdateCheckbox.checked }),
  });
});

// --- Modal genitori meta (personalizzabile da UI, persistito sul server) --
// Stato di lavoro separato da qualunque altra cosa: si ricarica da
// /api/meta_parents ogni volta che il modal si apre, cosi' Annulla scarta
// davvero le modifiche non salvate (basta non richiamare renderMetaParentsList
// dopo una chiusura senza salvare).
let metaParentsSelection = new Set();

function renderMetaParentsList() {
  const sorted = [...allCharactersData].sort((a, b) => a.character.localeCompare(b.character));
  metaParentsList.innerHTML = "";
  sorted.forEach(c => {
    const id = `meta-parent-cb-${c.character}`;
    const wrapper = document.createElement("label");
    wrapper.setAttribute("for", id);
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = id;
    checkbox.value = c.character;
    checkbox.checked = metaParentsSelection.has(c.character);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) metaParentsSelection.add(c.character);
      else metaParentsSelection.delete(c.character);
    });
    wrapper.appendChild(checkbox);
    wrapper.appendChild(document.createTextNode(formatCharacterName(c.character)));
    metaParentsList.appendChild(wrapper);
  });
}

async function openMetaParentsModal() {
  metaParentsError.hidden = true;
  await charactersLoadedPromise;
  const resp = await fetch("/api/meta_parents");
  const data = await resp.json();
  metaParentsSelection = new Set(data.characters || []);
  renderMetaParentsList();
  metaParentsModal.hidden = false;
}

function closeMetaParentsModal() {
  metaParentsModal.hidden = true;
}

metaParentsOpenButton.addEventListener("click", openMetaParentsModal);
metaParentsCancelButton.addEventListener("click", closeMetaParentsModal);
metaParentsSelectAllButton.addEventListener("click", () => {
  allCharactersData.forEach(c => metaParentsSelection.add(c.character));
  renderMetaParentsList();
});
metaParentsSelectNoneButton.addEventListener("click", () => {
  metaParentsSelection.clear();
  renderMetaParentsList();
});
metaParentsSaveButton.addEventListener("click", async () => {
  const resp = await fetch("/api/meta_parents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ characters: Array.from(metaParentsSelection) }),
  });
  const data = await resp.json();
  if (!resp.ok) {
    metaParentsError.textContent = translateServerMessage(data.error) || t("error_unknown");
    metaParentsError.hidden = false;
    return;
  }
  closeMetaParentsModal();
});
metaParentsModal.addEventListener("click", event => {
  if (event.target === metaParentsModal) closeMetaParentsModal();  // click fuori dal box chiude, come i popover
});

// --- Veterani (2026-08-14): libreria PERMANENTE di genitori/nonni con le
// proprie spark (persistita server-side in data/veterans.json, vedi
// veterans.py/app.py), riusabile su più piani ace/loop diversi -- diversa
// dal piano spark v3 (aptitude_inheritance.py), che è per-ciclo e transiente.
// Flusso di selezione spark richiesto esplicitamente dall'utente: si sceglie
// la spark UNA volta (menu diviso race/white, alfabetico), poi si applica a
// più veterani insieme, con le stelle scelte per ciascuno -- non una
// selezione ripetuta per veterano.
let veteransCache = [];
const sparkCatalog = { race: [], white: [] };
let sparkCatalogLoaded = false;

async function loadSparkCatalog() {
  if (sparkCatalogLoaded) return;
  const [race, white] = await Promise.all([
    fetch("/api/spark_race").then(r => r.json()),
    fetch("/api/spark_skill").then(r => r.json()),
  ]);
  sparkCatalog.race = [...race].sort((a, b) => a.name_en.localeCompare(b.name_en));
  sparkCatalog.white = [...white].sort((a, b) => a.name_en.localeCompare(b.name_en));
  sparkCatalogLoaded = true;
}

// Riempie un <select> con placeholder + due <optgroup> (race/white spark,
// gia' alfabetiche in sparkCatalog) -- condiviso da ogni punto in cui si
// aggiunge una spark a UN singolo bersaglio: i 18 selettori per-slot del
// piano ace, il proprio editor spark di un veterano e quello di ciascuno
// dei suoi 2 genitori (vedi buildSparkEditor), stessa struttura ovunque.
function buildSparkPickerOptions(selectEl) {
  const placeholder = selectEl.querySelector("option[value='']");
  selectEl.innerHTML = "";
  if (placeholder) selectEl.appendChild(placeholder);

  const raceGroup = document.createElement("optgroup");
  raceGroup.label = t("opt_group_race_spark");
  sparkCatalog.race.forEach(s => {
    const opt = document.createElement("option");
    opt.value = `race:${s.id}`;
    opt.textContent = s.name_en;
    raceGroup.appendChild(opt);
  });
  selectEl.appendChild(raceGroup);

  const whiteGroup = document.createElement("optgroup");
  whiteGroup.label = t("opt_group_white_spark");
  sparkCatalog.white.forEach(s => {
    const opt = document.createElement("option");
    opt.value = `white:${s.id}`;
    opt.textContent = s.name_en;
    whiteGroup.appendChild(opt);
  });
  selectEl.appendChild(whiteGroup);
}

function populateAceSlotSparkPickers() {
  aceSlotSparkPickers.forEach(buildSparkPickerOptions);
}

function populateVeteranAddSelect() {
  const current = veteranAddCharacterSelect.value;
  const sortedNames = globalFilteredCharacterNames();
  veteranAddCharacterSelect.innerHTML = "";
  sortedNames.forEach(name => {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = formatCharacterName(name);
    veteranAddCharacterSelect.appendChild(opt);
  });
  veteranAddCharacterSelect.value = sortedNames.includes(current) ? current : (sortedNames[0] || "");
}

// Salva per intero uno slot genitore di un veterano (PUT, sostituzione
// piena -- vedi app.py/veterans.set_veteran_parent): ricarica veteransCache
// dalla risposta e riDisegna, stesso principio "si salva subito, niente
// bottone Salva a parte" gia' usato ovunque nel modal Veterani.
async function saveVeteranParent(veteranId, slot, character, whiteSparks, raceSparks) {
  const resp = await fetch(`/api/veterans/${veteranId}/parent/${slot}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ character: character || null, white_sparks: whiteSparks, race_sparks: raceSparks }),
  });
  if (!resp.ok) return;
  veteransCache = await resp.json();
  renderVeteransList();
}

// Sostituisce per intero le spark PROPRIE di un veterano (non quelle di un
// suo genitore, vedi saveVeteranParent per quelle).
async function saveVeteranSparks(veteranId, whiteSparks, raceSparks) {
  const resp = await fetch(`/api/veterans/${veteranId}/sparks`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ white_sparks: whiteSparks, race_sparks: raceSparks }),
  });
  if (!resp.ok) return;
  veteransCache = await resp.json();
  renderVeteransList();
}

async function saveVeteranName(veteranId, name) {
  const resp = await fetch(`/api/veterans/${veteranId}/name`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!resp.ok) return;
  veteransCache = await resp.json();
  renderVeteransList();
}

// Chip (con rimozione) + riga "aggiungi spark", per UN bersaglio (un
// veterano o un suo genitore, mai piu' di uno alla volta -- l'applicazione
// "a piu' veterani insieme" e' stata rimossa su richiesta esplicita
// dell'utente, 2026-08-15: con piu' veterani dello stesso personaggio
// (copie diverse, vedi 'name' in veterans.py) era troppo facile applicare
// la spark alla copia sbagliata). onSave(newWhiteSparks, newRaceSparks)
// riceve la lista GIA' ricalcolata (add o remove), il chiamante decide dove
// salvarla (saveVeteranSparks per il veterano stesso, saveVeteranParent per
// un suo genitore).
function buildSparkEditor(whiteSparks, raceSparks, onSave) {
  const wrap = document.createElement("div");

  const chipRow = document.createElement("div");
  chipRow.className = "ace-slot-sparks";
  const combined = [
    ...whiteSparks.map(s => ({ ...s, sparkType: "white" })),
    ...raceSparks.map(s => ({ ...s, sparkType: "race" })),
  ];
  combined.forEach(spark => {
    const chip = document.createElement("span");
    chip.className = "ace-slot-spark-chip";
    chip.textContent = `${spark.name_en} ${"★".repeat(spark.stars)}`;
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.title = t("ace_slot_spark_remove_title");
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", () => {
      const newWhite = spark.sparkType === "white"
        ? whiteSparks.filter(s => s.spark_id !== spark.spark_id) : whiteSparks;
      const newRace = spark.sparkType === "race"
        ? raceSparks.filter(s => s.spark_id !== spark.spark_id) : raceSparks;
      onSave(newWhite, newRace);
    });
    chip.appendChild(removeBtn);
    chipRow.appendChild(chip);
  });
  wrap.appendChild(chipRow);

  const addRow = document.createElement("div");
  addRow.className = "ace-slot-spark-add-row";
  const picker = document.createElement("select");
  picker.innerHTML = `<option value="">${t("opt_spark_picker_placeholder")}</option>`;
  buildSparkPickerOptions(picker);
  const starsSelect = document.createElement("select");
  [1, 2, 3].forEach(n => {
    const opt = document.createElement("option");
    opt.value = String(n);
    opt.textContent = `${n}★`;
    starsSelect.appendChild(opt);
  });
  const addBtn = document.createElement("button");
  addBtn.type = "button";
  addBtn.textContent = t("btn_add");
  addBtn.addEventListener("click", () => {
    if (!picker.value) return;
    const [sparkType, sparkId] = picker.value.split(":");
    const sparkDef = (sparkType === "white" ? sparkCatalog.white : sparkCatalog.race).find(s => s.id === sparkId);
    if (!sparkDef) return;
    const stars = Number(starsSelect.value);
    const targetList = [...(sparkType === "white" ? whiteSparks : raceSparks)];
    const existing = targetList.find(s => s.spark_id === sparkId);
    if (existing) existing.stars = stars;
    else targetList.push({ spark_id: sparkId, name_en: sparkDef.name_en, stars });
    const newWhite = sparkType === "white" ? targetList : whiteSparks;
    const newRace = sparkType === "race" ? targetList : raceSparks;
    onSave(newWhite, newRace);
  });
  addRow.append(picker, starsSelect, addBtn);
  wrap.appendChild(addRow);

  return wrap;
}

// Un genitore NOTO del veterano (parent1/parent2, vedi veterans.py): scelta
// del personaggio + le sue spark -- diventera' un NONNO dell'ace quando
// questo veterano viene importato come genitore diretto (vedi
// importVeteranIntoSlot).
function buildVeteranParentEditor(veteran, slot) {
  const parent = veteran[slot];
  const wrap = document.createElement("div");
  wrap.className = "veteran-parent-editor";

  const label = document.createElement("span");
  label.className = "veteran-parent-label";
  label.textContent = slot === "parent1" ? t("label_ace_parent1") : t("label_ace_parent2");
  wrap.appendChild(label);

  const charSelect = document.createElement("select");
  charSelect.innerHTML = `<option value="">${t("opt_none")}</option>`;
  // esclude il veterano stesso: non puo' essere suo proprio genitore, stesso
  // principio del "mai genitore di se stesso" del piano ace (vedi
  // enforceNoSelfParent piu' sotto in questo file)
  globalFilteredCharacterNames()
    .filter(name => name !== veteran.character)
    .forEach(name => {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = formatCharacterName(name);
      charSelect.appendChild(opt);
    });
  charSelect.value = parent ? parent.character : "";
  charSelect.addEventListener("change", () => {
    // cambiare personaggio azzera le spark: appartenevano al personaggio precedente
    saveVeteranParent(veteran.id, slot, charSelect.value, [], []);
  });
  wrap.appendChild(charSelect);

  if (parent) {
    wrap.appendChild(buildSparkEditor(parent.white_sparks, parent.race_sparks, (newWhite, newRace) => {
      saveVeteranParent(veteran.id, slot, parent.character, newWhite, newRace);
    }));
  }

  return wrap;
}

// Quale veterano e' mostrato nel pannello di dettaglio (mai piu' di uno --
// bug segnalato dall'utente 2026-08-15: prima ogni veterano ripeteva
// l'intera struttura di editing in fila, illeggibile con piu' di 2-3
// salvati). null = nessuno selezionato (lista vuota).
let selectedVeteranId = null;

// Lista laterale compatta (icona + nome, click per selezionare) -- il
// dettaglio vero e proprio e' in renderVeteranDetail, chiamata alla fine.
function renderVeteransList() {
  veteransListEl.innerHTML = "";
  if (veteransCache.length === 0) {
    const p = document.createElement("p");
    p.className = "placeholder";
    p.textContent = t("veterans_empty");
    veteransListEl.appendChild(p);
    selectedVeteranId = null;
    renderVeteranDetail();
    return;
  }
  if (!veteransCache.some(v => v.id === selectedVeteranId)) {
    selectedVeteranId = veteransCache[0].id;  // selezione assente/rimossa: seleziona il primo
  }
  veteransCache.forEach(v => {
    const item = document.createElement("div");
    item.className = "veteran-list-item" + (v.id === selectedVeteranId ? " selected" : "");
    item.appendChild(buildPortraitWrap(v.character));
    const nameSpan = document.createElement("span");
    nameSpan.className = "veteran-list-item-name";
    nameSpan.textContent = v.name;
    item.appendChild(nameSpan);
    item.addEventListener("click", () => {
      selectedVeteranId = v.id;
      renderVeteransList();
    });
    veteransListEl.appendChild(item);
  });
  renderVeteranDetail();
}

// Il dettaglio completo (nome/personaggio/rimuovi, spark proprie, i 2
// genitori) del SOLO veterano selezionato -- stessa struttura di prima,
// solo renderizzata una volta invece che ripetuta per ogni veterano.
function renderVeteranDetail() {
  veteranDetailEl.innerHTML = "";
  const v = veteransCache.find(x => x.id === selectedVeteranId);
  if (!v) return;

  const row = document.createElement("div");
  row.className = "veteran-row";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.className = "veteran-row-name-input";
  nameInput.value = v.name;
  nameInput.addEventListener("change", () => saveVeteranName(v.id, nameInput.value));
  const charLabel = document.createElement("span");
  charLabel.className = "veteran-row-counts";
  charLabel.textContent = formatCharacterName(v.character);
  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.textContent = t("btn_remove");
  removeBtn.addEventListener("click", () => deleteVeteran(v.id));
  row.append(nameInput, charLabel, removeBtn);
  veteranDetailEl.appendChild(row);

  veteranDetailEl.appendChild(buildSparkEditor(v.white_sparks, v.race_sparks, (newWhite, newRace) => {
    saveVeteranSparks(v.id, newWhite, newRace);
  }));

  const parentsTitle = document.createElement("p");
  parentsTitle.className = "veteran-parents-title";
  parentsTitle.textContent = t("veteran_parents_title");
  veteranDetailEl.appendChild(parentsTitle);

  const parentsRow = document.createElement("div");
  parentsRow.className = "veteran-parents-row";
  parentsRow.append(buildVeteranParentEditor(v, "parent1"), buildVeteranParentEditor(v, "parent2"));
  veteranDetailEl.appendChild(parentsRow);
}

async function loadVeterans() {
  veteransCache = await fetch("/api/veterans").then(r => r.json());
  renderVeteransList();
}

async function openVeteransModal() {
  await charactersLoadedPromise;
  await loadSparkCatalog();
  populateVeteranAddSelect();
  await loadVeterans();
  veteransModal.hidden = false;
}

function closeVeteransModal() {
  veteransModal.hidden = true;
}

async function deleteVeteran(id) {
  await fetch(`/api/veterans/${id}`, { method: "DELETE" });
  await loadVeterans();
}

veteransOpenButton.addEventListener("click", openVeteransModal);
veteransCloseButton.addEventListener("click", closeVeteransModal);
veteransModal.addEventListener("click", event => {
  if (event.target === veteransModal) closeVeteransModal();  // click fuori dal box chiude, come i popover
});

veteranAddButton.addEventListener("click", async () => {
  const character = veteranAddCharacterSelect.value;
  if (!character) return;
  const resp = await fetch("/api/veterans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ character }),
  });
  const record = await resp.json();
  selectedVeteranId = record.id;  // seleziona subito il nuovo veterano, pronto per essere modificato
  await loadVeterans();
});


// --- Piano ace, passo 2: spark manuali per slot + import da veterano -------
// Ogni slot (genitore1/2, nonno1a/1b/2a/2b) di OGNI ace ha una propria lista
// di spark, tenuta SOLO lato client per ora (nessun consumatore server-side
// ancora: l'affinita' non usa le spark, servira' per la futura probabilita'
// di eredita' -- vedi conversazione). Chiave = (ace, ruolo) DELLO SLOT, non
// del personaggio: coerente con come gia' funziona il resto del piano ace
// (parent_slots lato server e' anch'esso indicizzato per slot). Lo specchio
// automatico tra slot condivisi (stesso personaggio E stesse spark su piu'
// ace) e' il prossimo passo, non ancora implementato qui.
const aceSlotSparks = {};

function aceSlotKey(aceIndex, role) {
  return `${aceIndex}|${role}`;
}

function getAceSlotSparks(aceIndex, role) {
  const key = aceSlotKey(aceIndex, role);
  if (!aceSlotSparks[key]) aceSlotSparks[key] = { white_sparks: [], race_sparks: [] };
  return aceSlotSparks[key];
}

// Svuota le spark di uno slot (bug segnalato dall'utente, 2026-08-15: dopo
// aver rimosso/cambiato il personaggio di un genitore/nonno, le sue spark
// restavano visibili -- appartenevano al personaggio precedente, non hanno
// piu' senso una volta cambiato chi occupa lo slot).
function clearAceSlotSparks(aceIndex, role) {
  aceSlotSparks[aceSlotKey(aceIndex, role)] = { white_sparks: [], race_sparks: [] };
  renderAceSlotSparks(aceIndex, role);
}

function renderAceSlotSparks(aceIndex, role) {
  const container = document.querySelector(
    `.ace-slot-sparks[data-ace-index="${aceIndex}"][data-role="${role}"]`,
  );
  const data = getAceSlotSparks(aceIndex, role);
  container.innerHTML = "";
  const combined = [
    ...data.white_sparks.map(s => ({ ...s, sparkType: "white" })),
    ...data.race_sparks.map(s => ({ ...s, sparkType: "race" })),
  ];
  combined.forEach(spark => {
    const chip = document.createElement("span");
    chip.className = "ace-slot-spark-chip";
    chip.textContent = `${spark.name_en} ${"★".repeat(spark.stars)}`;
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.title = t("ace_slot_spark_remove_title");
    removeBtn.textContent = "×";
    removeBtn.addEventListener("click", () => {
      const list = spark.sparkType === "white" ? data.white_sparks : data.race_sparks;
      const idx = list.findIndex(s => s.spark_id === spark.spark_id);
      if (idx >= 0) list.splice(idx, 1);
      renderAceSlotSparks(aceIndex, role);
      mirrorIfShared(aceIndex, role);
    });
    chip.appendChild(removeBtn);
    container.appendChild(chip);
  });
}

async function initAceSlotAuxiliaryUI() {
  await loadSparkCatalog();
  populateAceSlotSparkPickers();
  await loadVeterans();  // veteransCache pronta per il popup "importa da veterano" (vedi openVeteranImportModal)
}

aceSlotSparkAddButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    const { aceIndex, role } = btn.dataset;
    const picker = document.querySelector(
      `.ace-slot-spark-picker[data-ace-index="${aceIndex}"][data-role="${role}"]`,
    );
    const starsSelect = document.querySelector(
      `.ace-slot-spark-stars[data-ace-index="${aceIndex}"][data-role="${role}"]`,
    );
    if (!picker.value) return;
    const [sparkType, sparkId] = picker.value.split(":");
    const sparkDef = (sparkType === "white" ? sparkCatalog.white : sparkCatalog.race)
      .find(s => s.id === sparkId);
    if (!sparkDef) return;

    const data = getAceSlotSparks(aceIndex, role);
    const list = sparkType === "white" ? data.white_sparks : data.race_sparks;
    const stars = Number(starsSelect.value);
    const existing = list.find(s => s.spark_id === sparkId);
    if (existing) existing.stars = stars;
    else list.push({ spark_id: sparkId, name_en: sparkDef.name_en, stars });

    picker.value = "";
    renderAceSlotSparks(aceIndex, role);
    mirrorIfShared(aceIndex, role);
  });
});

// Applica 'veteran' allo slot (aceIndex, role): personaggio + proprie spark,
// piu' la cascata sui nonni del ramo se importato come genitore diretto
// (vedi commento sotto). Estratta a parte cosi' da poter essere chiamata sia
// dal vecchio flusso (rimosso: select inline + bottone) sia dal nuovo popup
// di selezione (vedi openVeteranImportModal), stessa logica in un solo posto.
function importVeteranIntoSlot(aceIndex, role, veteran) {
  // le spark vanno impostate PRIMA di scatenare il "change" sul personaggio:
  // lo specchio automatico (mirrorIfShared, sotto) legge le spark correnti
  // dello slot nel momento in cui il "change" scatta -- se arrivassero dopo,
  // lo specchio copierebbe ancora quelle vecchie.
  aceSlotSparks[aceSlotKey(aceIndex, role)] = {
    white_sparks: veteran.white_sparks.map(s => ({ ...s })),  // copia, non riferimento:
    race_sparks: veteran.race_sparks.map(s => ({ ...s })),    // modificarle dopo non deve toccare il veterano salvato
  };
  renderAceSlotSparks(aceIndex, role);

  // Se il veterano viene importato come GENITORE diretto (parent1/parent2,
  // non un nonno: non esiste un livello "bisnonno" nel piano ace), i SUOI
  // genitori noti (veterans.py: parent1/parent2 del veterano, se presenti)
  // diventano i 2 nonni di quel ramo -- gp1a/gp1b se importato in
  // parent1 (sono i genitori di parent1), gp2a/gp2b se in parent2.
  // Sostituzione PIENA anche qui: un nonno del veterano ignoto svuota lo
  // slot nonno corrispondente, non lo lascia con un valore residuo di
  // un'importazione precedente.
  if (role === "parent1" || role === "parent2") {
    const gpRoles = role === "parent1" ? ["gp1a", "gp1b"] : ["gp2a", "gp2b"];
    const veteranParents = [veteran.parent1, veteran.parent2];
    gpRoles.forEach((gpRole, i) => {
      const gpData = veteranParents[i];
      aceSlotSparks[aceSlotKey(aceIndex, gpRole)] = gpData
        ? {
          white_sparks: gpData.white_sparks.map(s => ({ ...s })),
          race_sparks: gpData.race_sparks.map(s => ({ ...s })),
        }
        : { white_sparks: [], race_sparks: [] };
      renderAceSlotSparks(aceIndex, gpRole);
      const gpSelect = slotSelect(aceIndex, gpRole);
      gpSelect.value = gpData ? gpData.character : "";
      gpSelect.dispatchEvent(new Event("change"));  // innesca lo specchio sul ramo, se condiviso
    });
  }

  const characterSelect = slotSelect(aceIndex, role);
  characterSelect.value = veteran.character;
  characterSelect.dispatchEvent(new Event("change"));  // innesca anche mirrorIfShared/enforceNoSelfParent
}

// Popup di selezione veterano (sostituisce il vecchio select inline + bottone
// "Importa" ridondanti, 2026-08-15): il bottone apre un popup con l'elenco
// dei veterani (gia' filtrati per il flag Global, vedi veteranPassesGlobalFilter),
// click su una riga importa e chiude. 'veteranImportTarget' ricorda quale
// slot ha aperto il popup, azzerato alla chiusura.
let veteranImportTarget = null;

function renderVeteranImportList() {
  veteranImportListEl.innerHTML = "";
  const importable = veteransCache.filter(veteranPassesGlobalFilter);
  if (importable.length === 0) {
    const p = document.createElement("p");
    p.className = "placeholder";
    p.textContent = t("veterans_empty");
    veteranImportListEl.appendChild(p);
    return;
  }
  importable.forEach(v => {
    const row = document.createElement("div");
    row.className = "veteran-import-row";
    row.textContent = v.name;  // il nome, non il personaggio: distingue le copie (vedi veterans.py)
    row.addEventListener("click", () => {
      importVeteranIntoSlot(veteranImportTarget.aceIndex, veteranImportTarget.role, v);
      closeVeteranImportModal();
    });
    veteranImportListEl.appendChild(row);
  });
}

function openVeteranImportModal(aceIndex, role) {
  veteranImportTarget = { aceIndex, role };
  renderVeteranImportList();
  veteranImportModal.hidden = false;
}

function closeVeteranImportModal() {
  veteranImportModal.hidden = true;
  veteranImportTarget = null;
}

aceSlotVeteranImportButtons.forEach(btn => {
  btn.addEventListener("click", () => openVeteranImportModal(btn.dataset.aceIndex, btn.dataset.role));
});

veteranImportCancelButton.addEventListener("click", closeVeteranImportModal);
veteranImportModal.addEventListener("click", event => {
  if (event.target === veteranImportModal) closeVeteranImportModal();  // click fuori dal box chiude, come gli altri modal
});

// --- Piano ace, passo 3: specchio automatico sugli slot condivisi ----------
// Se "Genitore N condiviso da" e' attivo su piu' ace, scegliere personaggio/
// spark in UNO di quegli slot li specchia SUBITO negli altri (stesso ruolo)
// -- niente da reimpostare a mano. La cascata copre anche i nonni del ramo
// (gp1a/gp1b per genitore1, gp2a/gp2b per genitore2): condividere lo stesso
// genitore vuol dire condividere anche i SUOI nonni (stessa carta fisica),
// altrimenti due rami indicati diversi per lo stesso genitore condiviso
// darebbero un errore in fase di calcolo (vedi ace_planner.build_established
// lato server, che unifica i nonni per personaggio-genitore).
//
// "Sorgente" dello specchio: lo slot appena modificato, se ha un valore;
// altrimenti il primo membro del gruppo che ne ha gia' uno (serve quando si
// attiva la spunta "condiviso" DOPO aver gia' scelto qualcosa in uno slot).
// Il controllo "valore gia' uguale, non ridispatchare" su ogni <select>
// evita un ping-pong infinito di eventi 'change' tra i membri del gruppo.

function sharedGroupForRole(role) {
  return aceShareCheckboxes
    .filter(cb => cb.dataset.role === role && cb.checked)
    .map(cb => cb.dataset.aceIndex);
}

function slotSelect(aceIndex, role) {
  return document.querySelector(`.ace-slot-select[data-ace-index="${aceIndex}"][data-role="${role}"]`);
}

function pickSyncSource(groupIndexes, role, preferred) {
  const hasValue = idx => !!(slotSelect(idx, role) && slotSelect(idx, role).value);
  if (preferred && hasValue(preferred)) return preferred;
  return groupIndexes.find(hasValue) || null;
}

function setSlotIfDifferent(aceIndex, role, character) {
  const select = slotSelect(aceIndex, role);
  if (select.value !== character) {
    select.value = character;
    select.dispatchEvent(new Event("change"));
  }
}

function copySlotSparks(fromAceIndex, fromRole, toAceIndex, toRole) {
  const source = getAceSlotSparks(fromAceIndex, fromRole);
  aceSlotSparks[aceSlotKey(toAceIndex, toRole)] = {
    white_sparks: source.white_sparks.map(s => ({ ...s })),
    race_sparks: source.race_sparks.map(s => ({ ...s })),
  };
  renderAceSlotSparks(toAceIndex, toRole);
}

function mirrorSharedGrandparent(preferredSourceAceIndex, gpRole) {
  const parentRole = gpRole === "gp1a" || gpRole === "gp1b" ? "parent1" : "parent2";
  const groupIndexes = sharedGroupForRole(parentRole);
  if (groupIndexes.length < 2) return;
  const sourceAceIndex = pickSyncSource(groupIndexes, gpRole, preferredSourceAceIndex);
  if (!sourceAceIndex) return;  // nessuno ha ancora scelto un nonno su questo ramo: niente da specchiare

  // le spark PRIMA del dispatch del personaggio (setSlotIfDifferent, che puo'
  // innescare una cascata rientrante sullo stesso ramo condiviso): se il
  // dispatch arrivasse prima, la cascata rientrante leggerebbe ancora le
  // spark vecchie del bersaglio invece di quelle appena copiate dalla fonte.
  groupIndexes.forEach(targetAceIndex => {
    if (targetAceIndex === sourceAceIndex) return;
    copySlotSparks(sourceAceIndex, gpRole, targetAceIndex, gpRole);
    setSlotIfDifferent(targetAceIndex, gpRole, slotSelect(sourceAceIndex, gpRole).value);
  });
}

function mirrorSharedSlot(preferredSourceAceIndex, role) {
  const groupIndexes = sharedGroupForRole(role);
  if (groupIndexes.length < 2) return;
  const sourceAceIndex = pickSyncSource(groupIndexes, role, preferredSourceAceIndex);
  if (!sourceAceIndex) return;

  // stesso ordine spark-prima-del-dispatch di mirrorSharedGrandparent sopra,
  // stesso motivo (evitare che una cascata rientrante legga spark vecchie).
  groupIndexes.forEach(targetAceIndex => {
    if (targetAceIndex === sourceAceIndex) return;
    copySlotSparks(sourceAceIndex, role, targetAceIndex, role);
    setSlotIfDifferent(targetAceIndex, role, slotSelect(sourceAceIndex, role).value);
  });

  const gpRoles = role === "parent1" ? ["gp1a", "gp1b"] : ["gp2a", "gp2b"];
  gpRoles.forEach(gpRole => mirrorSharedGrandparent(sourceAceIndex, gpRole));
}

function mirrorIfShared(aceIndex, role) {
  if (role === "parent1" || role === "parent2") mirrorSharedSlot(aceIndex, role);
  else mirrorSharedGrandparent(aceIndex, role);
}

// Mai un personaggio genitore di se' stesso -- puo' esserlo NONNO (permesso,
// anche se sconsigliato: riduce l'affinita' via la self-affinity=0 gia'
// gestita da affinity.base_affinity), ma MAI genitore diretto. Vale per
// ogni coppia figlio/genitore dell'albero: ace<->parent1/2, parent1<->
// gp1a/gp1b, parent2<->gp2a/gp2b. Un cambio che crea un conflitto viene
// annullato subito (torna "auto"/vuoto) -- innesca comunque "change" sullo
// slot svuotato, cosi' l'eventuale specchio (mirrorIfShared) propaga anche
// l'annullamento ai rami condivisi, invece di lasciarli disallineati.
function enforceNoSelfParent(aceIndex) {
  const aceCharSelect = document.querySelector(`.ace-character-select[data-ace-index="${aceIndex}"]`);
  const aceChar = aceCharSelect ? aceCharSelect.value : "";

  ["parent1", "parent2"].forEach(role => {
    const sel = slotSelect(aceIndex, role);
    if (aceChar && sel.value === aceChar) {
      sel.value = "";
      clearAceSlotSparks(aceIndex, role);
      sel.dispatchEvent(new Event("change"));
    }
  });

  const parentValue = {
    parent1: slotSelect(aceIndex, "parent1").value,
    parent2: slotSelect(aceIndex, "parent2").value,
  };
  [["gp1a", "parent1"], ["gp1b", "parent1"], ["gp2a", "parent2"], ["gp2b", "parent2"]].forEach(
    ([gpRole, parentRole]) => {
      const parentChar = parentValue[parentRole];
      const gpSel = slotSelect(aceIndex, gpRole);
      if (parentChar && gpSel.value === parentChar) {
        gpSel.value = "";
        clearAceSlotSparks(aceIndex, gpRole);
        gpSel.dispatchEvent(new Event("change"));
      }
    },
  );
}

aceCharacterSelects.forEach(select => {
  select.addEventListener("change", () => enforceNoSelfParent(select.dataset.aceIndex));
});

aceSlotSelects.forEach(select => {
  select.addEventListener("change", event => {
    const { aceIndex, role } = select.dataset;
    // Un cambio genuino dell'utente (event.isTrusted) parte da zero: le
    // vecchie spark appartenevano al personaggio/slot precedente. I nostri
    // stessi dispatch programmatici (import da veterano, specchio,
    // enforceNoSelfParent) impostano gia' le spark corrette PRIMA di
    // dispatchare "change" (isTrusted=false per un Event creato a mano) --
    // qui non vanno toccate, altrimenti lo specchio automatico
    // propagherebbe spark vuote invece di quelle appena importate.
    if (event.isTrusted) clearAceSlotSparks(aceIndex, role);
    enforceNoSelfParent(aceIndex);
    mirrorIfShared(aceIndex, role);
  });
});

aceShareCheckboxes.forEach(cb => {
  cb.addEventListener("change", () => {
    if (!cb.checked) return;  // disattivare la condivisione non "despecchia" nulla di gia' impostato
    mirrorIfShared(cb.dataset.aceIndex, cb.dataset.role);
  });
});

loadFileInput.addEventListener("change", () => {
  const file = loadFileInput.files[0];
  if (file) handleLoadFile(file);
  loadFileInput.value = "";  // permette di ricaricare lo stesso file una seconda volta
});
