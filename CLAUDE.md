# CLAUDE.md — working on ELMER

ELMER is a study program, progress tracker and game for the US radio operator
exams. It is a Flask server that runs on a Raspberry Pi, a Linux box or a
Windows laptop, and any browser on the same network is its screen. Each unit
keeps its own SQLite database. There is no hosted version and nowhere to visit.

README.md is the one-screen version. DESIGN.md is the notebook: the reasoning
behind every decision. When DESIGN.md and the code disagree, the code is right
and DESIGN.md has a bug to fix. USER-GUIDE.md is the operator's manual, and it
is also built into a PDF on every unit's Library shelf.

## Before any commit: lint and test

**1. The lint check that fails the build.** This is the same command CI runs,
and it runs before the tests. If it fails, CI never reaches the tests at all.

    flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

It must print `0`. The most common thing it catches is a name used in a module
that never imports it. A path the tests never reach will still crash on a real
unit days later.

**2. The tests.** They are standalone scripts, not pytest. Each one prints its
checks in order and exits non-zero if any check failed. There are no `test_*`
functions, so running bare `pytest` collects nothing and "fails".

    python3 tests/test_<name>.py            # one test
    for t in tests/test_*.py; do python3 "$t" >/dev/null 2>&1 || echo "FAIL $t"; done

- Run the tests for whatever you touched, then the whole suite before
  committing. The full suite takes several minutes.
- Some tests drive a real headless browser (`tests/_browser.py`). They fail on
  purpose, rather than skip, when no Chromium or Chrome is on PATH.
- The library tests need poppler-utils.

**3. Writing a new test:**

- Copy the shape of an existing one: a docstring saying what is being proved
  and why, then `check(label, got, want)`, `FAILS`, and `sys.exit(1)` at the end.
- `import _isolate` must come **before anything from elmer**. It moves the
  operator's state to a temporary directory (`ELMER_STATE`), turns off the
  report address, the FCC license download and TowerWitch, points the shipped
  shelf at an empty directory (`ELMER_SHELF`), and fails the test loudly if it
  writes into the real `data/`.
- A test must not touch the network. Stub the fetch or use bundled data.
- A test must not change tracked files.
- A bug that only appears after days of use (anything read back from the
  database as JSON text, anything keyed on how many days since something) needs
  a test that seeds that state. A fresh database will never reach it.

## Platform and dependencies

- **Python 3.11 is the floor**, because Raspberry Pi OS bookworm ships 3.11 and
  CI tests on it. Use no syntax or standard-library features from 3.12 or later.
- **Runtime dependencies are Flask, Pillow, reportlab, numpy and scipy**, and
  nothing else. Everything else is the standard library, including the QR
  encoder. Do not add a dependency without asking. numpy and scipy were added
  on 2026-09-27 for the numerical work (the antenna solver, the ground-wave
  physics, the golf flight), each of which gets its own plan before any code.
  Import scipy lazily, inside the function that uses it, never at the top of
  a module. poppler-utils and pyserial are optional, and the self-check
  (`./elmer.py --doctor`) names them when missing, numpy and scipy too.
- **Raspberry Pi OS refuses `pip install`** (PEP 668). `install.sh` uses apt
  there and a virtual environment elsewhere. Never tell a user to pip install.
- **Windows is a first-class target.** The release workflow builds and
  smoke-tests a Windows zip when a `v*` tag is pushed.
  - Use `pathlib` for paths, never string-joined separators.
  - File permissions: mode 600 does nothing on Windows. Private files get
    their inherited permissions removed and are granted to the owner and
    SYSTEM only.
  - The suite must pass on Windows as well as Linux.
- **Operator state lives under `paths.STATE`** (`ELMER_STATE`, or `data/` when
  unset). What ships with the program lives under `paths.CONTENT`. Never write
  under `CONTENT`, and never compute your own path into `data/`.

## Fidelity rules (the project's promises; do not break them quietly)

- **The question pools are the published documents, verbatim**: the NCVEC's
  .docx files and the FCC's PDFs, with every correction the question pool
  committee has issued. Never edit pool text, even to fix spelling. The pools
  keep the FCC's own spelling. `./elmer.py --build` validates the counts, the
  answer keys, the sections and the figures, and it stops rather than ship a
  hole in a pool.
- **Explanations and concept notes** (`data/notes/`) are promised as "written
  by hand or quoted from 47 CFR; none machine-generated." Do not write, rewrite
  or "improve" them unless Scott explicitly asks. If he does, raise whether the
  README and DESIGN.md wording still holds.
- **Rule text is quoted from 47 CFR, never paraphrased.**
- **Everything that leaves a unit is listed** under *What leaves a unit* in the
  Fidelity section of DESIGN.md.
  - A new network fetch means updating that list, in the same commit.
  - Nothing about the operator goes out with a request beyond the thing asked.
  - Nothing is sent from a unit unless the operator pressed for it, or switched
    it on and was shown what goes.
  - A fetch that fails must end in something usable and a line in the log.
    Never fail silently.
- **The mock exam never sends the answer key or its shuffle to the browser.**
  The server grades against its own copy. The drill sends its shuffle on
  purpose; DESIGN.md says why.
- **Measured figures** (mastery, exam odds, difficulty, the forecast's error)
  are shown with the sample size beside them, and say so when there is not yet
  enough to know.

## Product principles

These come from Scott's decisions recorded in the changelog. Keep to them when
adding features.

- ELMER is an assistant, not a coach with a quota. It does not assign a day's
  work, count down "passes still to go", or use failure language.
- Being wrong is never free: every mode grades the same card the same way,
  including an answer revealed on purpose.
- No hidden or variable reward schedules. Thresholds are printed, and they
  never move backward.
- Sound is off until the operator turns it on. A miss gets a neutral tone,
  never a buzzer.
- Never call anybody "unlicensed". ELMER knows only what is on the account's
  record: "no FCC record", "unrecorded".
- Display units follow the operator's setting, except where the craft has its
  own convention: bands in meters, wire in feet, ionosonde heights in km.
- Diagnostics go to the log, where the dashboard shows the tail of it. They do
  not go on the study screens.
- A Pi has one job: the person or the table in front of it. While a game, a
  net, a mock exam or a study session is running, background work waits -
  fetches, the FCC license download and its index, spot sampling, Library
  indexing, anything a page did not ask for. It runs when the unit is idle,
  and never mid-question. New heavy work (the antenna solver, the ground-wave
  curves) is computed on demand for the page that asked, never ahead. A Pi
  decoding P25 or running TowerWitch is not an ELMER host; ELMER reaches it
  over the network.

## Writing: code comments, the user interface, docs, commits

- **American English** throughout: prose, identifiers and filenames alike
  (learned, meters, license, program, color). Pool text is the exception.
- **Plain, concrete sentences**, in the voice of the existing docs. Say what it
  does for the person using it, and why.
- **Commit subject:** one sentence about what changed *for the user*, not about
  the code. Several changes are joined: "A, B, and C". The body is grouped by
  area (Golf:, Study:, Papers:). Keep the Co-Authored-By trailer.
- **CHANGELOG.md:** newest date first, and a paragraph per change under that
  day's heading, written the same way as the commit. Update it in the same
  commit as the change.
- **When a feature changes what the operator sees**, update in the same commit:
  - USER-GUIDE.md, plus its figures (`tools/guideshots.py` for screenshots,
    `tools/guidefigures.py` for diagrams)
  - the "Since v1.0" and "What does not work yet" parts of README.md
  - the relevant section of DESIGN.md

  The guide's test fails if a figure it names is missing, or if a heading is
  stranded at the foot of a page.

## Layout

- `elmer.py` is the entry point and command line (`--kiosk`, `--doctor`,
  `--build`, `--update`, …).
- `elmer/app.py` holds every route, about 9,300 lines. `elmer/*.py` are the
  domain modules: srs, cw, golf, propagation, bandplan, party, netcontrol, and
  so on.
- `elmer/templates/` and `elmer/static/` are the pages and their JavaScript.
- `data/` is shipped content plus the operator's state (see Platform above).
- `tests/` holds the standalone test scripts, plus `_isolate.py` and
  `_browser.py`. `tools/` holds the build and asset scripts.
- `.github/workflows/`: `python-app.yml` (lint and tests on push or pull request
  to main) and `release.yml` (the Windows zip, on a `v*` tag).
