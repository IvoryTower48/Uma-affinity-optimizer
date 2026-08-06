# IvoryTower48's Uma Legacy Loop Optimizer

The purpose of this tool is to help planning for "legacy loops" (closed 
sets of 5 characters that become each others' parents and grandparents) 
in Umamusume Pretty Derby.
There are two main modes: 
- top-4 compatibles with a chosen character (max affinity in first loop
  without degrading the other four steps);
- best 5-loop for affinity (with the possibility of choosing multiple
  characters that must be in the loop).

This tool also features a simple pink spark planning (e.g. requiring 
long or dirt sparks so that a character can run more races) and a
table that summarizes the career timeline of the 5 umamusume in the loop.

At the moment this tool supports English and Italian, and the .exe can
be ran only in Windows without requiring any installation.

## The Simple Way to Use this Tool

Download the latest package from the [Releases page](../../releases) 
of this repository, extract the .zip file in a folder and run
`UmaLegacyLoopOptimizer.exe`. Soon after the app will open a browser page,
and it can be used as-is; by closing the tab, you'll stop the program. 


If you prefer to run it in a terminal, you'll
find more details in `LEGGIMI.txt` (Italian) and `README.txt` (English)
inside the .zip you just downloaded.

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
data_updater.py          data update from gametora.com (optional, turned off by default)
affinity.py              base affinity, race compatibility, regular aptitude requirements for a win
loop_search.py           searches the top-4 compatible characters or searches the best 5-loop
cycle_analysis.py        full description of a parent cycle, affinity score breakdown
aptitude_inheritance.py  pink spark planning
timeline.py              race caledndar/timeline for the looping characters
pdf_export.py            rudimentary PDF export complete with illustrations for easy reference
main.py                  CLI
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

## Note di design (per riferimento futuro)

- **`career` vs `mant`**: in `career`, a race is 'winnable' and 'shared' between 2 umas
  only if the time slot is not occupied with a different mandatory race; in `mant`
  there are no calendar constraints to account for, just aptitude thresholds.
- **`best_loop`** works as a research that considers ALL possible sets of 5 unique umas,
  and computes inidividual and overall affninity for each. It's more useful if
  1+ characters are selected, since the program restricts the pool size to avoid
  unnecessary computations (`--pool-size`, default 20).
- The **minimum threshold for each aptitude** (`MIN_APTITUDE` in `config.py`) is defined
  as a constant, so it's easy to change them without touching the underlying logic.

## Credits

[mee1080](https://github.com/mee1080) and its repository [Umaishow](https://github.com/mee1080/umaishow)
for easy access to the raw data on character id and relative weights to compute affinity.

[Gametora](https://gametora.com/umamusume) and its Discord for general knowledge, 
affinity computation clarification, and downloadable illustrations.

Each line of Python code has been written by an AI, supervised and micromanaged by IvoryTower48 (in game: Arnit, Trainer ID 600 621 108 642).

## Additional notes
This is my most serious attempt at learning how to work with AI and its limits and capabilities.
I tested each function and the tool works to a satisfactory degree, but I'm not a seasoned programmer:
this tool will have bugs and is surely badly written from a programmer's PoV.

While I'm not a fan of contributing to GitHub and the community with AI code, I have to recognize that
this tool would not exist in its present form without it. I have a data science background, so
tasks like preparing the UI and automatically updating the data would've been hard tasks for me;
since the Umamusume community is quite active, speed and presentation were qualities I wanted.

Feel free to improve this tool, or to tell me which issues it has so I can also try my hand at
maintaining code with AI (and, for maintenance, the occasional 'manual' touch).

I hope it'll be useful for preparing future parents and to enjoy Umamusume more!

## License

AGPL v3

This tool is unofficial, and neither the tool nor the author are affiliated to 
Cygames or Umamusume Pretty Derby.
