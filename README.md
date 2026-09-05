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

### Band plan

A station reference at `/bandplan`, in three layers kept deliberately apart
because they carry very different authority:

- **Privileges are law**, and they come from your actual licence. Enter your
  callsign once and ELMER reads the FCC record through callook.info: licence
  class, grant and expiry dates, and the grid square. The band plan then shows
  *your* privileges rather than a class you picked from a list, and the page
  tells you how long the licence has left — flagging the last 90 days, and the
  two-year grace period after expiry during which you may not transmit but can
  still renew without re-testing. Only the class, dates and grid are kept; the
  name and address the lookup also returns are public record but ELMER has no
  use for them, so they are discarded. 47 CFR 97.301 and 97.305 per class.
  Anything outside your class is hatched out on the bar and marked "no" in the
  table, so the legal picture is never in doubt.
- **Activity is convention.** 160 segments across sixteen bands, coloured by
  what happens there — CW, digital, phone, image, beacons, satellite,
  repeaters, FM simplex, calling frequencies. None of it is enforceable, but a
  signal in the wrong place is what people complain about.
- **Regional plans come from your frequency coordinator.** Minnesota is wired
  up: 80 coordinated segments across 6 m, 2 m, 1.25 m, 70 cm and 23 cm, fetched
  from the Minnesota Repeater Council and cached for 30 days. Coordinator plans
  are somebody else's work, so they are fetched rather than bundled; adding
  another state means adding one entry with a parser to
  `elmer/regional.py`.

**Download chart (PDF)** produces a landscape band chart for your licence class,
with the regional segments folded in, to print and pin up.

The page also points at the **NIFOG** — the National Interoperability Field
Operations Guide, published by CISA at the Department of Homeland Security and
revised most years. It is the pocket reference that the standard interoperability
channel names, and a fair number of the band charts in circulation, are copied
out of, and it is oddly missing from the amateur study material. ELMER says where
to get it, what is in it for an amateur and on which page, what it is actually
for — programming a radio and filling in an ICS 205 — and, at least as
importantly, that nearly nothing in it is amateur spectrum. Monitoring is free;
transmitting on those channels needs an authorisation a licence does not give
you, and owning the book is not it. Being a work of the US government it carries
no copyright and can be printed and handed out freely.

`./elmer.py --fetch-nifog` goes further: it finds the current edition from CISA's
own page rather than a filename remembered in the source, downloads it, converts
it with the poppler tools ELMER already needs, and reads the nationwide
interoperability channels straight out of the tables — VCALL and VTAC, UCALL and
UTAC, the 700 MHz and 800 MHz calling and tactical channels, with their CTCSS
tones and P25 network access codes. They then appear on the band plan page,
folded away behind a summary line, and can be added to the printed chart with a
checkbox that is off by default — a band chart is a one-page thing to pin up, and
three pages of channels nobody may transmit on is paper wasted on most people who
print it. Because the guide is revised and a transcribed channel list goes quietly
stale, ELMER reads the current one rather than carrying a copy.

Everything parsed is checked before it is used: channel names against their
pattern, every frequency against the band its group belongs to, and the four
nationwide calling channels have to be present or the parse is judged not to have
understood the document. A parse that fails is discarded whole and the previous
copy kept — ELMER would rather show something a year old, and say so, than a
number it has not satisfied itself about. Provenance travels with it: the version,
the date on the cover, and when it was read all print on the chart.

When they are included they go on pages of their own, never folded into the band
chart: everything on the chart is spectrum you may transmit on, nothing on those
pages is, and the two must not be read as one list.

Nothing in the guide feeds ELMER's own calculations. Privileges, power limits and
the mode checks all come from ELMER's reading of 47 CFR 97.301, 97.305 and 97.313.
The NIFOG has been useful as an independent check on that reading — it confirmed
the five 60 m carrier frequencies and the Novice and Technician power restriction
— but it is a reference held alongside, not a source ELMER computes from.

### CW

A page at `/cw` for learning, practising and using Morse, with the tone
adjustable from 300 to 1200 Hz and its own volume — pick whatever you hear
most comfortably, and it is remembered.

- **Learn** uses the Koch method: two characters sent at full target speed, and
  one more added each time you copy at 90%. Speed is slowed by stretching the
  gaps between characters rather than the characters themselves (Farnsworth),
  because a slowed-down character is a different sound that has to be unlearned
  later. ELMER tracks each character's copy rate and, more usefully, *what you
  heard it as* — the confusions are what still need separating.
- **Copy practice** sends and you type: Koch groups, plain letters, numbers,
  mixed, callsigns, Q signals, abbreviations, prosigns, and whole QSO fragments
  built around your own callsign. Scored per character.
- **Your sending** turns the space bar or an on-screen paddle into a straight
  key, decodes what you actually sent, and measures your timing against the
  target — dit, dah, the gaps, and the dah-to-dit ratio. You cannot hear your
  own swing; a chart shows it.
- **Decode off air** listens through the microphone, locks onto the strongest
  tone between 250 and 1400 Hz, and decodes the timing. It learns the sending
  speed as it goes, so expect the first character or two to garble before it
  locks on. Clean signals decode well; QRM, QSB and a swinging fist degrade it
  as they do for every decoder.

Tone is generated with a shaped 5 ms rise and fall rather than by switching an
oscillator, because hard keying is what produces key clicks — the same wide
sidebands E8D asks about.

### Your QTH, set once

Your location is a single setting shared by everything that needs it. Set it on
the propagation page or in the path tool and both pick it up: the path tool
opens with your end already filled in, and the propagation page uses it for
local solar elevation and day/night band ratings. It accepts a grid square,
coordinates or a place name, and a QTH entered as a bare grid is given a
readable name the first time it is used, so `FN31pr` shows as *Newington*.

Where the browser allows it there is a **locate me** button. Browsers only
permit geolocation in a secure context, which over plain HTTP means the machine
itself — so it appears when you open ELMER on the Pi (including in `--kiosk`
mode, which opens `localhost`) and stays hidden on the LAN address rather than
offering something that would fail.

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

- **Ionospheric hop** — drag frequency, foF2 and F2 peak height and watch rays
  refract or escape, with the skip zone drawn to scale. Uses the proper
  curved-earth secant law, so the M-factor tops out near 3.4 the way the real
  ionosphere does, instead of the flat-earth formula that claims a 90 MHz MUF.
  The height is adjustable because the layer genuinely moves — the F2 peak runs
  roughly 250 to 400 km, lower and denser by day, higher and thinner at night —
  and you do not judge that by ear. It is measured, by ionosondes: a radar
  pointed straight up that sweeps frequency and times the echo. **Use a real
  measurement** pulls the nearest reporting station's current foF2 and hmF2 in,
  and says how far away and how old they are, so the simulator runs on
  observation rather than on a guess.
- **Ohm and power** — fill in any two of E, I, R, P
- **Reactance and resonance** — X_L, X_C and the resonance point, plotted
- **SWR and feed line** — SWR, reflection coefficient, return loss, reflected
  power in watts, mismatch loss
- **Antenna dimensions** — dipole and vertical lengths, coax electrical length
  by velocity factor
- **Decibels** — power ratios both ways, plus dBm
- **NVIS setup** — tick the box on any horizontal wire and the antenna tab
  works out the height that actually puts the lobe overhead: the 0.15&ndash;0.25 λ
  window in feet for your frequency, the resulting lobe elevation, and whether
  you are in it. For an inverted-V it gives apex height, end height for each
  leg, the span between the ends, and the *effective* height — because the
  pattern follows the current-weighted mean height, which sits (π−2)/π = 0.363
  of the way out along each leg, so an inverted-V behaves lower than its apex
  suggests. Above about 10 MHz it says plainly that NVIS will not work, since a
  near-vertical signal only returns below foF2.
- **Antennas** — ten configurations across wire (dipole, inverted-V, end-fed
  half wave, full-wave loop), vertical (quarter wave, 5/8 wave, J-pole, ground
  plane), the Yagi, and loaded mobile whips. Dimensions in feet, metres and
  inches, feed impedance, gain, and for horizontal wire the takeoff angle your
  height above ground actually buys. A short whip reports its radiation
  resistance, efficiency and the loading it needs, which is the honest answer to
  why mobile HF is hard.

  Every gain figure says what it was measured against and where — dBd, and free
  space for horizontal wire, over an average ground plane for verticals —
  because a gain number without those is the stuff antenna advertising is made
  of. They are estimates worth about ±1 dB, not measurements. Yagi gain comes
  from the **boom length**, which is what actually sets it: element count and
  spacing decide the boom, and two Yagis with the same boom get the same answer
  whether that boom carries five elements or seven. Spacing outside the 0.15 to
  0.30 wavelength range a good design uses is charged for, since elements
  crammed closer shadow each other and elements spread further leave holes in
  the aperture. What the figures deliberately do not include is your ground: a
  horizontal antenna picks up as much as 6 dB more at the peak of its lobe once
  it is about half a wavelength up. That ceiling is 6 dB in total — it is not,
  as the folklore has it, another 6 dB for every doubling of height.
- **RF exposure evaluation** — an antenna designed in the Antennas tab can be
  sent straight here, carrying its frequency, gain and description. The starting
  distances are worked out per antenna type, because how close a person can get
  has little to do with how high the antenna is: a horizontal wire is nearest
  directly beneath it, an inverted-V at its drooping ends rather than its apex,
  a ground-mounted vertical can be walked up to, and a mobile whip sits a few
  feet from the people in the car. Each hand-off says which assumption it used,
  and flags the high-voltage points — the ends of a dipole, the far end of an
  end-fed, the base of a ground-mounted vertical — where an RF burn does not
  need the field to exceed any limit. Send several antennas and they stack up as
  separate bands in one evaluation. The evaluation every amateur has been
  required to perform since 2021, under 47 CFR 97.13(c). Enter each band you
  actually run: frequency, PEP, mode, how much of the averaging period you
  transmit for, antenna gain, and how far away people get. ELMER computes the
  MPE limits from 47 CFR 1.1310, the estimated power density, the percentage of
  the limit, and the distance beyond which you comply — separately for the
  controlled/occupational (6-minute) and uncontrolled/general-population
  (30-minute) environments. Distances inside the near field are flagged rather
  than quietly reported.

  Inputs are checked, because a compliance record that accepts anything
  produces nonsense that looks authoritative. Impossible values are refused
  with the reason and the band at fault — 500 dBd is not an antenna gain, a
  megawatt is not a radio station, a distance cannot be negative. Implausible
  ones are computed but flagged in the record: power above the 1500 W legal
  limit, a gain large enough to suspect dBi was entered instead of dBd, a
  frequency outside the amateur bands, a distance close enough to touch the
  antenna. The mode list says what may actually be sent where the row is tuned:
  ELMER holds 47 CFR 97.301 and 97.305 in full, so offering every mode on every
  frequency would not be neutral — it would quietly suggest the operation is
  fine. Modes the licence class may not use in that segment are marked, and a
  line under the row names the band, the class and the terms. Nothing is
  blocked, because evaluating a station you cannot yet operate is legitimate,
  but a transmission the licence does not permit is written into the record and
  onto the printed sheet, where an unqualified green "compliant" would otherwise
  read as approval of the whole operation. The same check catches the 200 W PEP
  ceiling on 30 m, the 100 W ERP ceiling on 60 m, and a 60 m frequency that is
  not one of the five channels.

  The printed sheet carries a second page: the operating privileges of the
  operator whose callsign is on it, and of that class only — the bands they
  hold, segment by segment, with what may be sent in each and any power ceiling
  below the general 1500 W. Underneath, the bands that class holds nothing on
  at all, which is the half of the answer that keeps somebody out of trouble.
  It is clearly marked as a reference rather than part of the evaluation, and
  it is left out entirely when no licence class is known, rather than printing
  somebody else's bands under your callsign.

  The evaluation errs toward safety throughout — full ground
  reflection, the antenna treated as pointing its whole gain at the person, and
  a modelled gain rounded up rather than to nearest — and both the screen and
  the printed sheet say so, in as many words. A more detailed determination may
  well show a shorter compliant distance and still satisfy the rules; that is
  not a licence to work inside these distances, because this is the evaluation
  on record. And because antenna gain is the largest single lever on every
  figure, the record distinguishes a gain **modelled** by ELMER from the
  antenna's geometry from one **entered by the operator**, which nothing has
  checked against any antenna. Neither is a measurement, and the record says so.

  **Download station record (PDF)** produces a signed
  one-page document with the inputs, the equation used, every intermediate
  value and the conclusion — meant to be printed and posted in the shack.
- **Path and line of sight** — the tool that answers "will this link work".
  Both ends take whatever you happen to know: a grid square, a lat,lon pair, or
  a place name such as "Walker, MN" or "Swamp Lake, Cass County, MN", resolved
  through OpenStreetMap's Nominatim (cached, rate limited, no key).
  Great circle distance and bearing, radio horizon on the 4/3 earth radius,
  free-space loss, a full link budget with fade margin, and first Fresnel zone
  clearance checked against a real terrain profile from OpenTopoData SRTM 30 m.
  Where a ridge intrudes it costs the obstruction as knife-edge diffraction
  loss (ITU-R P.526) and reports the margin that survives it — so a blocked path
  is never quietly reported as comfortable. Terrain is cached, and without a
  network the smooth-earth maths still runs and says the terrain is unknown.
  The antenna tab hands its gain figure straight to it.

### Game layer

Titles are earned inside the licence class they name. Each class carries a
five-step ladder:

    <Class> Listener -> Learner -> Operator -> <Class> -> <Class> Elmer

The first two steps come from coverage and estimated mastery. The upper three
require mock exam evidence: one pass for Operator, two of your last three for
the class itself, and for the Elmer tier all of your last five passed averaging
90% or better. There is no route to a General title that does not run through
General questions, which is precisely what a single global XP ladder got wrong.

Exam evidence goes stale the way a licence does. A tier is **current** for 90
days after a passing exam, then sits in a 90-day **grace period** where it is
shown as lapsed and a single passing exam renews it, exactly as a licence in
grace is renewed without re-testing. Past that it **expires**, and the
exam-proven tiers must be earned again in full. Thresholds live as named
constants at the top of `elmer/ranks.py`.

Sustained practice keeps a tier current without re-sitting anything, because a
few questions a week is what actually protects proficiency. The bar rises with
the title: over a rolling 30 days, Operator needs 30 distinct questions at 75%,
the class tier 40 at 85%, and the Elmer tier 50 at 90%. Distinct questions, so
forty repeats of one easy card maintain nothing — and practice can only hold a
tier that was earned by exam in the first place.

Amateur and commercial are tracked separately, since progress in one says
nothing about the other. A track with nothing earned yet reads **Un-rated** —
never "unlicensed". Every title here is ELMER's own standing against its own
copy of the pools, it grants no operating privileges, and the wording is chosen
so nobody can come away thinking ELMER has licensed them. Only the FCC issues a
licence, and only a real session in front of accredited VEs or a COLEM leads to
one.

XP is kept as a pure effort meter and no longer confers any title. It is
weighted so the answers worth the most are the ones that teach you the
most — a hard, overdue, previously-failed question pays several times what a
question you already own does. Alongside it sit daily streaks, 22 achievements
and a timed contest mode.

---

## Commands

```
./elmer.py                    serve on 0.0.0.0:5000
./elmer.py --port 8080        serve on another port
./elmer.py --doctor           self-check, and print every URL to try
./elmer.py --stats            print progress in the terminal
./elmer.py --stats --user SAM  print one person's progress on a shared unit
./elmer.py --update           update this install and say what changed
./elmer.py --update-check     say whether an update is waiting, change nothing
./elmer.py --adopt            let a copied install update itself in future
./elmer.py --fetch-nifog      read the interoperability channels from the NIFOG
./install.sh                  install, or ask: update, repair, remove, check
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
  game.py             XP, streaks, achievements
  ranks.py            the nested class ladder, its decay and practice upkeep
  bandplan.py         privileges (law) and activity segments (convention)
  cw.py               Morse alphabet, Koch order, timing and practice text
  ionosonde.py        live foF2 and F2 peak height from the GIRO network
  bandpdf.py          the printable band chart
  regional.py         frequency coordinator plans, fetched per state
  rfexposure.py       MPE limits and power density, per OET-65 Supplement B
  rfpdf.py            the printable station record
  terrain.py          ground elevation profiles for the path tool
  explain.py          assembles rule text, concept notes and your own notes
  propagation.py      space weather fetch and band interpretation
  db.py               SQLite storage, per user, and the schema migrations
  update.py           checking the repository and fast-forwarding onto it
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
  terrain/            cached elevation profiles
  elmer.db            your progress
  elmer.log           request and error log
```

## Putting it in the menu

```
./elmer.py --install-launcher
```

Adds ELMER to the applications menu and the desktop with its own icon, so it
starts with a click rather than from a terminal. The entry launches it full
screen; right-click it and choose **Open in a window** for an ordinary window
instead. `./elmer.py --remove-launcher` takes it all back out.

The icon is installed into the hicolor theme at 48, 64, 128, 256 and 512 px
from `elmer/static/icon.png`, so replacing the icon and re-running the install
updates the menu too.

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

Links that leave ELMER — the FCC ULS record, the full rule text on eCFR, a
frequency coordinator's own band plan — get a stop on the way out. A full-screen
browser has no back button, so following one straight out would leave you on the
FCC site with no way back to the study session and no way to reach the Exit
button. Instead you land on ELMER's own page saying where the link goes, with
**Back to ELMER** and an option to open the site in an ordinary window that has a
close button; the kiosk window stays on ELMER underneath, and windows opened this
way are closed when ELMER stops. Off a kiosk — a laptop, a phone on the LAN —
links open in a new tab as they always did.

## Sharing one unit

One ELMER in a house gets shared the way a radio does, so it holds more than one
person. Everyone gets their own cards, their own review schedule, their own
titles, streak, XP, achievements and notes. Nothing is pooled and nothing is
averaged.

The top bar names whoever is at it. Pressing it lists everybody on the unit,
switches between them in one press, and takes a name and an optional callsign to
add somebody new.

**A callsign is what ELMER calls you.** Somebody who has one earned it in front
of volunteer examiners, so that is the name the program uses — the same respect
an operator gets on the air. Everyone else is called by their name, which is
theirs and needs no licence. Add a callsign later and ELMER starts using it, at
the moment they actually earned it.

Once there are two of you the dashboard grows a **shack** panel: everyone side
by side, their standing in each track, questions answered this week, accuracy,
streak and XP. It sorts by what was answered this week, because that is the
figure anybody can do something about today.

There are no passwords. Switching user is a choice, not a sign-in: anyone who
can reach ELMER can be anyone on it. That is a deliberate trade for a family
appliance that holds nothing but how many radio questions somebody got right —
rather less than the FCC already publishes about every licensee by name and
address. Worth knowing before putting one on a network shared with people you
would not hand the radio to. The one exception is removing somebody, since that
destroys their work: that can only be done from a browser on the unit itself.

`--stats` prints whoever is first on the unit, plus a roster of everybody;
`--stats --user NAME` prints somebody in particular.

Existing installs need nothing done. The first time ELMER opens a database from
before it could be shared it migrates it in one transaction — every card, answer,
exam, title and achievement carried over — and whoever was using it becomes the
first user on the unit.

## Running the installer again

`./install.sh` on a machine that already has ELMER does not quietly install it
again. It looks for study data, a virtual environment or a menu entry belonging
to this copy, and if it finds any of them it asks what you came for:

```
ELMER is already installed here
  found: study data, menu entry

    1) Update    fetch the latest ELMER and apply it
    2) Repair    put back anything missing or changed, and re-check
    3) Remove    take away the menu entry and the virtualenv
    4) Check     run the self-check and change nothing
    5) Quit
```

The same four are flags for a scripted run — `--update`, `--repair`, `--check`,
`--remove` (`--uninstall` still means the same). A run with `--yes`, or one with
no terminal attached, behaves exactly as it always did and installs what is
missing, since a script that expected an install should get one.

**Repair** is the walk the installer already did — check what is here, put back
what is not — plus the thing that was missing from it: tracked files that have
drifted from the repository are what stops an install updating, so repair lists
them and offers to put them back. That question ignores `--yes` and defaults to
no, because "do not pester me" is not "you may delete my work"; a script has to
say `--discard-local-changes` to answer it. Untracked files are never touched,
and neither is anything in `data/`.

The menu entry lives in your own share directory rather than in the install, so
a machine with two copies of ELMER on it still has only one entry, belonging to
whichever copy wrote it. Removing from a copy that does not own it leaves it
alone and says where it lives, so a clone or a test checkout cannot take the
menu entry away from the install actually in use.

## Keeping it up to date

An ELMER install is a git checkout, so an update is a fast-forward and nothing
else. There is no downloader and no separate version feed: the checkout already
knows where it came from.

```
./elmer.py --update-check     say whether anything is waiting, change nothing
./elmer.py --update           apply it, after showing what it is
./elmer.py --update --yes     apply it without asking
```

**ELMER never applies an update on its own.** It looks, it tells you what it
found, and it waits. Nobody sitting down to study should find the program
changed underneath them, and an update that arrives unasked on a machine in a
shack is a fault report from somewhere far away rather than something anybody
chose. Applying one is always a press of a button or a command typed on purpose.

So it looks when it starts, and about once a day after that. If something is
waiting it says so on the console as it launches, and then launches:

```
  An ELMER update is waiting: 1 commit, latest "Read the licence instead of asking for it"
  Apply it from the dashboard, or with ./elmer.py --update, whenever it suits you.
```

The dashboard carries the same news. A **Software** panel at the bottom shows
which commit this install is on and when it last looked; when something is
waiting, a notice appears at the top of the dashboard with an **Update now**
button. Pressing that restarts ELMER onto the new code — in kiosk mode the
full-screen browser is handed to the new process rather than closed, so all
anyone sees is the page reloading. The button is offered only to a browser on
the machine itself; a phone on the LAN sees the version and nothing to press.

The only setting is whether it looks at all:

| | |
|---|---|
| **tell me** | the default: look at startup and daily, say so, wait to be told |
| **never check** | no looking at all |

Three rules hold whenever an update is actually asked for:

- **Fast-forward only.** No merge is attempted and no rebase considered. If
  history has diverged, ELMER says so and stops.
- **Never over local edits.** A change to a tracked file is somebody's work in
  progress, and an update that discards it is a bug. This is what keeps the
  updater quiet on the machine ELMER is actually written on. Untracked files are
  left out of that judgement — they are nobody's business but their owner's, and
  git refuses by itself if an incoming commit would land on one.
- **Never prompts.** The check runs on a background thread where a credential
  prompt would simply hang, so git runs with prompting off and ssh in batch
  mode. A repository it cannot read anonymously is reported as unreachable.

A public repository is readable over HTTPS with no credentials, so a Pi that
only consumes updates needs no key, no token and no account. When `origin` is an
SSH URL — the way the machine that *pushes* is set up — the check falls back to
the HTTPS form of the same repository.

If a copy was made by hand rather than cloned it has no history to update from.
`./elmer.py --adopt` gives it one without overwriting a single file: the history
is fetched alongside, HEAD is pointed at it, and anything that differs locally
is left in the working tree as ordinary uncommitted changes to look at.

A schema change still needs a migration written for it — `db.connect()` creates
missing tables on its own but cannot add a column to a table that already
exists, so `elmer/db.py` carries `migrate()` and `PRAGMA user_version` for the
rest. Since an update only ever lands when somebody asks for one, a forgotten
migration is a bad afternoon on one machine rather than every Pi at once.

## Giving it an icon

Drop an image at `elmer/static/icon.png` (or `.svg`, `.jpg`, `.webp`) and it
becomes the browser tab icon, and the home-screen icon if you save ELMER to a
phone. Nothing else to change — without one, ELMER falls back to a 📻 glyph.
A square image of 512×512 or larger works best.

## Requirements

Python 3.11 with Flask and Pillow, plus `pdftotext`, `pdftoppm` and `pdfimages`
from poppler-utils for rebuilding the pools. All present on Raspberry Pi OS.
Serving needs no network; only the propagation dashboard reaches out.

## Licence

ELMER's own code and artwork are under the
[PolyForm Noncommercial License 1.0.0](LICENSE) — free for personal study,
hobby and amateur use, for clubs, schools and other noncommercial
organisations, but not for commercial use. Note that this is deliberately not
an open-source licence in the OSI sense.

The question pools and rule text under `data/` are *not* covered by that
licence and are not this project's to relicense: the FCC pools and 47 CFR
Part 97 are US Government works in the public domain, and the amateur pools
belong to the NCVEC, which releases them for free use. [NOTICE](NOTICE) sets
out exactly which files fall under which terms.

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
