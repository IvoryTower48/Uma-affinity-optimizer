====================================================
 Uma Legacy Loop Optimizer
====================================================

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

This tool also features pink spark planning (Aptitude Inheritance: simulate
the aptitude boost from pink sparks and preview its effect on the loop live),
a table that summarizes the career timeline of the loop, save/load of a
full session, and an illustrated PDF export of the finished loop.

The UI is available in both English and Italian, with a light/dark theme
and a modern/classic layout: change these from the gear icon (Settings)
inside the program.


HOW TO START
--------------
1. Extract the ENTIRE contents of this zip into any folder (keep
   "UmaLegacyLoopOptimizer.exe", the "_internal" folder and the "data"
   folder together, in the same folder).
2. Double-click "UmaLegacyLoopOptimizer.exe".
3. A black window opens (the program's console) and, after a moment, your
   browser opens by itself on the program's page: no need to install
   Python or anything else, no need to use a terminal.
4. To close it, just close the browser tab: the program shuts itself down
   (including the black window). Alternatively you can close the black
   window directly.

The .exe is Windows only; the program runs entirely on your PC.

ABOUT INTERNET CONNECTION
--------------
Not required to use the program. Character portraits and race plaques
(used in the UI and in the exported PDF) are already included in this
package: internet access is only needed for two optional things:
- downloading images for any new characters/races not yet included in the
  package — if there is no connection, the program automatically falls
  back to a placeholder, with no errors;
- automatic data updates (new characters/races) are DISABLED by default:
  turn it on manually from the Settings panel (gear icon) inside the
  program, if you want to.

====================================================
 Credits
====================================================

mee1080 (https://github.com/mee1080) and its repository Umaishow for easy access to the raw data 
on character id and relative weights to compute affinity.

Gametora and its Discord server for general knowledge,
affinity computation explanation, and downloadable illustrations.

uma.guide (https://uma.guide) for the race plaque illustrations used in
the timeline grid and in the PDF export.

umapyoi.net (https://umapyoi.net) for Japanese-server release dates, used
to order characters still pending a Global release.

Each line of Python code has been written by an AI, supervised and micromanaged by IvoryTower48 (in game: Arnit, Trainer ID 600 621 108 642).

