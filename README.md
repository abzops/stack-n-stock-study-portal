# Stack n Stock Study Portal

A local, single-computer pick-and-pack study workspace. Hardware is simulated; analysis provides advice without automatically changing a study.

## Run

Python 3.11+ is recommended. The portal server uses only Python's standard library.

```powershell
python portal/launch_portal.py
```

On Windows, double-click `Start_Study_Portal.bat`. Keep the server window open. The browser opens `http://127.0.0.1:8765` (or the next available port). Use the address printed by the launcher, rather than an old port-8000 bookmark.

## Features

- SQLite autosave, session history, reusable presets, paused recovery and browser pending-save recovery.
- Configurable study duration, work blocks, breaks, tote-cycle limits and completion rules.
- Tote inventory, verified replenishment, recorded corrections, exceptions and emergency stop.
- Slot and block analysis, session comparisons, explainable alerts and CSV/print exports.
- Defaults: 60 minutes, 10-minute work blocks, 1:42 breaks, 13 tote cycles, completion at time or cycle limit.

## Local data

Source runs save in `data/study_sessions.sqlite3`, outside the served portal directory. Portable builds save in a `data` folder beside the EXE. Data and reports are excluded from Git. Stop the app before backing up its database; keep the data folder when upgrading the executable. Resolve failed pending saves before moving computers.

## Windows portable build

```powershell
python -m pip install -r requirements-build.txt
python scripts/build_portable.py
```

This creates an EXE and ZIP in `portable/`. Extract the ZIP into a writable folder and double-click the EXE. The destination computer does not need Python or Node. If the browser does not open, use the generated `Open Portal.html` beside the running EXE. The executable is unsigned. Generated packages are not committed to this repository.

## Development and verification

```powershell
npm ci --prefix portal
npx --prefix portal playwright install chromium
python -m unittest discover -s tests -p test_study_store.py
python tests/test_launcher.py
node portal/test_models.cjs
node portal/test_control.cjs
node portal/test_portable.cjs
```

The portable test requires a built EXE. The control test starts an isolated local server and database. To rebuild the HTML after editing layout templates:

```powershell
node portal/rebuild-layout.cjs
```

## Optional CSV analysis

```powershell
python -m pip install -r requirements-analysis.txt
python scripts/analyze_study.py --csv path/to/export.csv
```

The analysis script supports legacy and detailed portal CSV column mappings. Historical workbooks and study records are not included. Unknown pick accuracy remains not assessed.

## Source layout

- `portal/`: HTML, styles, JavaScript, server, storage and browser tests.
- `scripts/`: analysis, simulation and portable build utilities.
- `tests/`: Python regression tests.

The repository intentionally excludes operational records, generated reports, installed dependencies, archived UI versions, personal files and unrelated assets.
