# ELMER

A study assistant, progress tracker and game for radio theory, built around the
current US license question pools — amateur (NCVEC) and commercial (FCC) — with
a live propagation dashboard and a lab of the calculators the exams actually
test.

Runs as a small local web app. Open it on the Pi itself, or from a phone or
laptop on the same network.

```
git clone https://github.com/skpeterson2000/elmer.git
cd elmer
pip install -r requirements.txt
./elmer.py             # serve; open it from anywhere on the network
./elmer.py --kiosk     # serve, and open full screen on this machine
#   ELMER is on http://192.168.1.119:5000
```

The pools ship built, so it runs straight from a clone — no build step.


---

## What's in it

### The question pools — 2,475 questions, all of them

| Pool | Element | Questions | Exam | Pass | Edition |
|---|---|---|---|---|---|
| Technician | 2 | 409 | 35 | 26 | 2026–2030, errata of 19 Feb 2026 |
| General | 3 | 423 | 35 | 26 | 2023–2027, 6th errata of 4 Feb 2026 |
| Amateur Extra | 4 | 599 | 50 | 37 | 2024–2028, 4th errata of 4 Feb 2026 |
| Marine Radio Operator Permit | 1 | 144 | 24 | 18 | 2009 pool |
| **GROL** — General Radiotelephone | 3 | 600 | 100 | 75 | 2009 pool |
| Ship Radar Endorsement | 8 | 300 | 50 | 38 | 2009 pool, updated 6 Mar 2024 |

All 43 diagrams are included and pinned to the questions that reference them —
the Technician and General schematics, the Extra figures as vector SVG, and the
FCC circuit and radar drawings extracted from the official PDFs.

The pools are parsed straight from the released NCVEC `.docx` and FCC `.pdf`
files and validated on every build: question counts must match the published
syllabus, every question must have four choices and exactly one keyed answer,
every section must be populated, and every referenced figure must exist. The
build fails loudly rather than shipping a pool with a hole in it.

### Study that knows what you don't know

Every question carries its own spaced-repetition schedule (SM-2, with the grade
inferred from whether you were right and how long you took — no self-rating).

**Mastery is not "percent of questions seen."** Each question gets an estimated
probability that you would answer it correctly *right now*: a smoothed accuracy
discounted by a forgetting curve, floored at the 25% you would get by guessing
between four choices. Questions you have never seen are estimated from your
performance on their section, and discounted for being unproven — which is why
the readiness number stays honest instead of flattering you.

Study modes:

- **Drill** — overdue reviews first, then new material
- **Weak spots** — lowest estimated mastery first
- **New** — questions you have never seen
- **Lapses** — the ones that have caught you out before
- **Contest** — five-minute rapid-fire round
- Or drill any single syllabus section from the progress and browse pages

### Explanations on every question

Every one of the 2,475 questions carries an explanation, shown in the pool
browser and again in a drill the moment you commit to an answer &mdash; right or
wrong, so a correct answer is reinforced rather than just ticked off. It comes
from four sources, in descending order of authority:

1. **Your own note.** A free-text box on every question. What you write in your
   own words is shown first, every time that question comes round. Ctrl+Enter
   saves, Esc hands the keyboard back to the drill.
2. **The FCC rule itself.** For the 194 questions carrying a citation, ELMER
   shows the actual text of 47 CFR Part 97, pulled from eCFR and narrowed to the
   cited paragraph &mdash; including the band-privilege tables, which are the
   substance of rules like &sect;97.301(d). Not a paraphrase, so there is nothing
   to mistrust, and each one links through to the full section.
3. **A concept note per syllabus section.** All 294 sections across the six
   pools have one: a short explanation of the underlying idea plus the key facts
   and formulas, written by hand. Sections whose concept is interactive link
   straight into the matching Lab tab.
4. **The syllabus context**, always &mdash; which section and subelement the
   question belongs to.

Nothing here is machine-generated. A subtly wrong explanation teaches the wrong
thing, so the content is either quoted from the regulation or written
deliberately; where neither exists, ELMER says so and invites your own note
rather than inventing one.

### Mock exams built to the real blueprint

Every exam draws **exactly one question at random from each syllabus section**,
in order, with the choices shuffled. That is the published NCVEC and FCC
construction, so a Technician mock here has 6 from T1, 4 from T5, 3 from T0 and
so on — the same distribution as a VE session. Answers you give in an exam feed
back into your schedule, and the result breaks down by subelement so you know
where the marks went.

**Exam readiness** is a Monte-Carlo simulation: 4,000 exams drawn under the real
blueprint against your per-question estimates, reported as a pass probability
and a likely score range.

### Live propagation

Real solar and geomagnetic data from N0NBH (hamqsl.com) and NOAA SWPC: flux, K
and A indices, sunspots, solar wind, X-ray background, aurora, band-by-band
ratings for day and night, and an estimated MUF and foF2. Set your grid square
and it works out your local solar elevation to pick the right day/night ratings
and tell you when you're near the grey line.

Every indicator is annotated with what it means and why the exams care, with
one-click links into the matching pool sections — reading about the MUF while
the MUF is on screen sticks much better than reading an answer key.

### Lab

Interactive versions of the maths the pools test:

- **Ionospheric hop** — drag frequency, foF2 and layer height and watch rays
  refract or escape, with the skip zone drawn to scale. Uses the proper
  curved-earth secant law, so the M-factor tops out near 3.4 the way the real
  ionosphere does, instead of the flat-earth formula that claims a 90 MHz MUF.
- **Ohm and power** — fill in any two of E, I, R, P
- **Reactance and resonance** — X_L, X_C and the resonance point, plotted
- **SWR and feed line** — SWR, reflection coefficient, return loss, reflected
  power in watts, mismatch loss
- **Antenna dimensions** — dipole and vertical lengths, coax electrical length
  by velocity factor
- **Decibels** — power ratios both ways, plus dBm
- **Great circle path** — distance, bearing, long path and hop count between two
  grid squares

### Game layer

XP weighted so that the answers worth the most are the ones that teach you the
most — a hard, overdue, previously-failed question pays several times what a
question you already own does. Daily streaks, 22 achievements, a nine-step rank
ladder from SWL to Elmer, and a timed contest mode.

---

## Commands

```
./elmer.py                    serve on 0.0.0.0:5000
./elmer.py --port 8080        serve on another port
./elmer.py --doctor           self-check, and print every URL to try
./elmer.py --stats            print progress in the terminal
./elmer.py --build            rebuild the pools from data/raw
./elmer.py --fetch            re-download the source pools, then rebuild
./elmer.py --log-level DEBUG  verbose console output
./elmer.py --no-log-file      console only
```

## When it will not open

Start here:

```
./elmer.py --doctor
```

It checks the pools, diagrams, database, templates, network and port, then
prints every address the server can be reached on.

Then watch the log while you try to load the page:

```
tail -f data/elmer.log
```

- **A line appears** — the request arrived. The status code on that line says
  what happened, and any error is logged with a full traceback right above it.
- **Nothing appears** — the request never got here. That is a network problem,
  not an ELMER problem: check the device is on the same network as the Pi, that
  you used `http://` and not `https://`, and that you included the `:5000`.

Everything is logged to `data/elmer.log` (rotated at 2 MB, three kept) as well
as to the console: every request with its client address, status, duration and
browser; every unhandled exception with a traceback; and JavaScript errors,
which the page reports back to the server so a browser-side failure does not
vanish into a console nobody has open. When that happens the page also shows a
red banner rather than sitting silently on "Loading…".

Run `--fetch` when a pool is reissued or a new errata lands; it re-downloads
from NCVEC and the FCC, rebuilds, and revalidates. If a download fails, the
existing copy in `data/raw` is left untouched.

## Keyboard

| | |
|---|---|
| `1`–`4` or `A`–`D` | answer |
| `space` / `enter` | next question |
| `?` | give up on a question (scores it wrong, which is the honest thing) |
| `Ctrl`+`Enter` | save the note you are typing |
| `Esc` | leave the note box and return the keyboard to the drill |
| `←` `→` | move between exam questions |
| `f` | flag an exam question for review |

## Layout

```
elmer.py              entry point
elmer/
  app.py              Flask routes and JSON API
  content.py          pool loading, choice shuffling
  srs.py              scheduling, mastery, readiness simulation
  exams.py            blueprint-correct exam generation and scoring
  game.py             XP, ranks, streaks, achievements
  explain.py          assembles rule text, concept notes and your own notes
  propagation.py      space weather fetch and band interpretation
  db.py               SQLite storage
  report.py           terminal stats
  pools/
    fetch.py          download the source documents
    parse_ncvec.py    NCVEC .docx parser
    parse_fcc.py      FCC .pdf parser
    figures.py        diagram extraction
    rules.py          fetches 47 CFR Part 97 from eCFR
    build.py          normalise and validate into data/pools/*.json
data/
  raw/                source documents as published
  pools/              built, validated JSON
  figures/            extracted diagrams
  notes/              concept notes, one per syllabus section
  explanations/       per-question rationales
  rules/              47 CFR Part 97 text
  elmer.db            your progress
  elmer.log           request and error log
```

## Kiosk mode

On a Pi with a monitor, ELMER is more appliance than website:

```
./elmer.py --kiosk
```

That serves as usual and brings up a full-screen browser on the machine itself,
with an **Exit** button in the top bar that stops the server and closes the
window. No terminal, no address bar, no way to wander off to another site.

Chromium is used ahead of Firefox even if Firefox is your default browser — its
kiosk mode behaves better under Wayland, which is what Raspberry Pi OS runs now.
Either one gets a throwaway profile under `data/kiosk-profile/`, because pointed
at your normal profile a browser that is already open would just add a tab to
the existing window instead of going full screen.

The Exit button is deliberately narrow. ELMER binds every interface so a phone
can reach it, and nobody on the network should be able to switch the study
session off, so the button appears only on the machine the server is running on:
a shutdown needs a token minted at startup, which is rendered into the page only
for a request that came from this machine. A browser on the network sees a page
with no button and no token in it, and `/api/quit` does not exist at all unless
`--kiosk` is on.

ELMER also stops if you close the kiosk window — otherwise the server would be
left running on a machine with no terminal open to stop it from. `--doctor`
reports whether kiosk mode can start before you rely on it.

## Giving it an icon

Drop an image at `elmer/static/icon.png` (or `.svg`, `.jpg`, `.webp`) and it
becomes the browser tab icon, and the home-screen icon if you save ELMER to a
phone. Nothing else to change — without one, ELMER falls back to a 📻 glyph.
A square image of 512×512 or larger works best.

## Requirements

Python 3.11 with Flask and Pillow, plus `pdftotext`, `pdftoppm` and `pdfimages`
from poppler-utils for rebuilding the pools. All present on Raspberry Pi OS.
Serving needs no network; only the propagation dashboard reaches out.

## A note on the sources

The amateur pools are public releases from the NCVEC Question Pool Committee.
The commercial pools are published by the FCC and are US government works. Both
are freely redistributable. ELMER reproduces them verbatim — the wording of a
question and its keyed answer is exactly what the released document says,
including the errata, because that is what you will see on the test.

The GROL and Element 8 pools date from 2009 and the FCC has not reissued them;
they remain the current pools in use. Some formulas in Element 3 lost their
superscripts when the FCC typeset the PDF (`R2+X2` for √(R²+X²)); those are
reproduced as published.

Progress is stored locally in `data/elmer.db` and never leaves the machine.
