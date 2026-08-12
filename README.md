# IvoryTower48's Uma Legacy Loop Optimizer

The purpose of this tool is to help planning for "legacy loops" (closed 
groups of characters that become each others' parents and grandparents) 
in Umamusume Pretty Derby.
There are three main modes: 
- top-4 compatibles with a chosen character (max affinity in first loop
  without degrading the other four steps);
- best 5-loop for affinity (with the possibility of choosing multiple
  characters that must be in the loop);
- rental loop, for the common case of a rented (never owned) "anchor"
  parent: only 3 owned characters need to rotate instead of 5.

This tool also features:
- pink spark planning (Aptitude Inheritance): simulate the aptitude boost
  from pink sparks across the whole loop, preview the resulting career
  timeline live, and get a suggested single-member substitution if another
  character would score higher;
- a table that summarizes the career timeline of the loop;
- an illustrated PDF export of the finished loop (character portraits,
  real race plaques, genealogy trees);
- save/load of a full session (search results, spark plan, filters) as JSON;
- independent training win probability: an additional, non-authoritative
  per-race win chance based on aptitude and race-turn fatigue (the
  affinity/loop search itself stays fully deterministic), with an
  adjustable recommendation threshold;
- a temporary, session-only aptitude boost for the Top-4 target character
  only (never worse than its real grade, never past "A") — this one DOES
  affect that search's ranking, unlike the read-only feature above;
- for the rental loop: plan a signature pink spark for the rented anchor
  parent and its two grandparents (fixed for the whole rotation, since the
  anchor is always the same character in every cycle), with a live
  aptitude preview and the same effect on that search's ranking.

All of the above is configurable from the in-app Settings panel: UI language
(English/Italian), light/dark theme, modern/classic layout, per-category
minimum aptitude thresholds, the auto-update toggle, and a custom
meta-parent list.

At the moment this tool supports English and Italian, and the .exe can
be ran only in Windows without requiring any installation.

## The Simple Way to Use this Tool

Download the latest package from the [Releases page](../../releases) 
of this repository, extract the .zip file in a folder and run
`UmaLegacyLoopOptimizer.exe`. Soon after the app will open a browser page,
and it can be used as-is; by closing the tab, you'll stop the program. 

## From the source code (Python required)

Run these two commands:
```bash
pip install -r requirements.txt
python app.py
```
then open the browser and go to **http://localhost:5000**. This program 
starts a local server on the PC that runs it; this is equivalent to
running the .exe file provided. As for the .exe, closing the browser tab 
will automatically stop the local server in the background.

If, for any reason, you'd like to modify this tool, you can compile the .exe
using`build_exe.bat`(requires`pip install pyinstaller`only for this step).

## Structure

```
config.py                constants (suffixes related to uma variants, aptitude thresholds,
                         weights to compute base affinity, loop size)
naming.py                mapping from uma variant name -> uma base name
display_names.py         Name format for the UI
data_loader.py           loading and normalization of all datasets
data_updater.py          data update from gametora.com/GitHub/Wikipedia/umapyoi.net
                         (optional, turned off by default; toggle also in the UI)
affinity.py              base affinity, achievable races, calendar conflict resolution,
                         regular aptitude requirements for a win
loop_search.py           searches the top-4 compatible characters or searches the best 5-loop
cycle_analysis.py        full description of a parent cycle, affinity score breakdown,
                         rental loop schedule, candidate substitution search
aptitude_inheritance.py  pink spark (Aptitude Inheritance) planning
inspiration.py           pink spark inspiration-chance formulas (category/stars -> % base
                         rates); calculation-only module, no UI yet
independent_training.py  pure win-probability formula (aptitude + consecutive-race
                         fatigue) and exhaustive occurrence search for recurring
                         races; additive only, never changes the affinity/loop score
timeline.py              race caledndar/timeline for the looping characters
pdf_export.py            illustrated PDF export of the finished loop (character portraits,
                         race plaques, genealogy trees)
main.py                  CLI (does not expose pink spark planning, rental loop mode, or
                         meta-parent management, which are UI-only)
app.py                   local Flask server (UI)
templates/               HTML page for the UI
static/                  CSS and JS for the UI
data/                    dataset (see below)
```

## Datasets in data/

- `character_ids.csv`, `id_weights.csv` — to compute base affinity
- `aptitudes.xlsx` — base aptitudes for a character (and variants, if at least one aptude differs)
- `races.xlsx`, `race_gametora_ids.json` — race metadata
- `mandatory_races.xlsx` — mandatory career races for each character
- `character_info.csv` — mapping variant → japanese name + Global server release date

`data/image_cache/` (character portraits and race plaques) are not included
in the repository: this folder will fill itself the first time it's requested
(requires allowing internet connection at least once) or it will stay empty.
In their place, there are placeholders to represent the umas and races.

A few more files under `data/` are runtime settings, not part of the curated
dataset above: `meta_parents.json` (custom meta-parent list), `update_settings.json`
(auto-update toggle), `extra_suffixes.json` (variant suffixes discovered
automatically), `.update_state.json`/`.variant_check_state.json` (auto-update
timestamps), and `update_backups/` (timestamped backup before every automatic
write to the datasets above). None of these need to exist for the tool to work.

## Further command examples to use this tool (CLI)

```bash
# Top-4 characters most compatible with a chosen character, normal career mode
python main.py --data-dir data --character <character_id>

# Same as above, but ignoring race calendar constraints (MANT parent runs)
python main.py --data-dir data --character <character_id> --mode mant

# Search for best closed 5-loop
python main.py --data-dir data --loop

# Same as above, but using only characteres that have already been released in Global
python main.py --data-dir data --loop --global-only
```

## Design notes

- **`career` vs `mant`**: in `career`, a race is 'winnable' and 'shared' between 2 umas
  only if the time slot is not occupied with a different mandatory race; in `mant`
  there are no calendar constraints to account for, just aptitude thresholds.
- **`best_loop`** works as a research that considers ALL possible sets of 5 unique umas,
  and computes inidividual and overall affninity for each. It's more useful if
  1+ characters are selected, since the program restricts the pool size to avoid
  unnecessary computations (`--pool-size`, default 20).
- **`rental_loop`** (UI only): plans around a fixed "anchor" parent that is rented
  every time instead of owned, so only 3 owned characters rotate through the loop
  instead of 5.
- The **minimum threshold for each aptitude** (`MIN_APTITUDE` in `config.py`) is the
  default value; it can be adjusted per-category from the UI for the current
  session (not persisted between restarts), without touching the underlying logic.
- **Independent training** (UI only, Top-4 and rental loop): a per-race win
  probability table shown alongside a result, using ALL races as candidates
  (not gated by `MIN_APTITUDE`) and an adjustable recommendation threshold
  (`MIN_INDEPENDENT_TRAINING_PROBABILITY` in `config.py`, default 80%,
  session-only). Purely additive — it never feeds back into the affinity or
  loop-search calculation.
- **Aptitude override** (UI only, Top-4 target character): lets you preview
  a temporary aptitude boost for the selected character alone (never worse,
  never past grade "A"), and it DOES affect that search's ranking — unlike
  independent training above, or the min-aptitude threshold, this one is
  scoped to a single character rather than the whole candidate pool.
- **Rented-parent signature spark** (UI only, rental loop): since the
  anchor is the same character in every cycle, its pink spark (and its
  grandparents', if known) is a constant for the whole rotation instead of
  a per-cycle plan — it counts double for the anchor itself (both the
  direct parent and, through the previous rotation member, a grandparent
  too). Boosts every candidate character except the anchor/grandparents
  themselves (they pass the spark down, they don't receive it), and feeds
  into the rotation search.

## Credits

[mee1080](https://github.com/mee1080) and its repository [Umaishow](https://github.com/mee1080/umaishow)
for easy access to the raw data on character id and relative weights to compute affinity.

[Gametora](https://gametora.com/umamusume) and its Discord for general knowledge, 
affinity computation clarification, and downloadable illustrations.

[uma.guide](https://uma.guide) for the race plaque illustrations used in the
timeline grid and in the PDF export.

[umapyoi.net](https://umapyoi.net) for Japanese-server release dates, used to
order characters still pending a Global release.

Each line of Python code has been written by an AI, supervised and micromanaged by IvoryTower48 (in game: Arnit, Trainer ID 600 621 108 642).

## Additional notes
This is my most serious attempt at learning how to work with AI and its limits and capabilities.
I tested each function and the tool works to a satisfactory degree, but I'm not a seasoned programmer:
this tool will have bugs and is surely badly written from a programmer's PoV.

While I'm not a fan of contributing to GitHub and the community with AI code, I have to recognize that
this tool would not exist in its present form without it. I have a data science background, so
tasks like preparing the UI and automatically updating the data would've been tough for me;
since the Umamusume community is quite active, speed and presentation were qualities I wanted.

Feel free to improve this tool, or to tell me which issues it has so I can also try my hand at
maintaining code with AI (and, for maintenance, the occasional 'manual' touch).

I hope it'll be useful for preparing future parents and to enjoy Umamusume more!

## License

AGPL v3

This tool is unofficial, and neither the tool nor the author are affiliated to 
Cygames or Umamusume Pretty Derby.
