# The golf build: weather, ball physics, routes, and measured difficulty

A working plan, agreed between KC9SP and Claude across 2026-09-22. It is
here rather than in DESIGN.md because DESIGN.md describes what ELMER *is*,
and this describes what it is going to be. Each stage folds into DESIGN.md
as it lands, and this file shrinks as that happens.

Nine stages. Every one is testable on its own, and only the last needs
recordings — so the game is playable and worth testing long before the
narration exists.

---

## The rules this whole plan is held to

**One fact, one rendering.** The bug class this project keeps finding — the
golf card and the inverted V disagreeing, the band tag naming a band the box
was not holding, the carry gusting while the drift did not — is one number
with two renderings allowed to drift apart. Every stage below either derives
both renderings from one value or says why it cannot.

**Failure is a state, not a crash.** Every fetch, every card, every
coefficient has a named fallback, and the log line says *what failed* and
*what was done instead*. A bad course card may not stop a round. A dead
network may not stop a tee-off. The failure tables in each stage are part of
the deliverable, not decoration.

**Unmeasured is a state, not a zero.** Where a number has not been earned
yet, the program says so — the way `ramped: False` already does — rather
than reporting a confident nought.

**Nothing is authored that can be measured.** No shipped difficulty ratings,
no hand-rated questions. See stage 7.

---

## Stage 1 — the day's wind, from the day rather than the minute — **LANDED 2026-09-22**

*Folded into DESIGN.md under "The day, and the wind it is played in".
Kept here as the record of what was agreed and why.*

Today `weather.read()` takes `periods[0]` — the current hour. Somebody who
tees off in a calm hour plays a dead round on a day that blew twenty-five
all afternoon.

**Note before building:** the `forecastHourly` feed already fetched is
*forward*-looking. Genuine "last 24 hours" needs the observations endpoint —
`points → observationStations → /stations/{id}/observations` — which is two
more requests. That is the reason this is not a one-line change.

- `weather.read()` gains `peak_mph` and `gust_mph`.
- `Day.__init__` takes `peak_mph` as `self.mean`.
- Observations come back as `wmoUnit:km_h-1` with a `unitCode`, and null
  values are common. Both must be handled explicitly.

**Agreed consequence:** rounds play windier. A round at three in the
afternoon starts from the day's worst, not the afternoon's. If that reads
too stiff on the Pi the knob is a single named scale factor.

| Failure | Level | Log says | Falls back to |
|---|---|---|---|
| no network | `debug` | course id, the exception | card's typical wind |
| no `observationStations` | `warning` | course id | forecast peak, next 24 h |
| no observations in window | `warning` | station id, the window | forecast peak |
| unknown `unitCode` | `warning` | the unitCode seen | that reading skipped |
| every value null | `warning` | station, how many seen | forecast peak |
| peak absurd (>100 mph) | `warning` | the value | clamped, and says to what |

**Testable with:** a recorded NWS payload. No network in tests.

---

## Stage 2 — the landing model — **LANDED 2026-09-22**

*Folded into DESIGN.md. The fringe was deliberately NOT changed: see
"Still undecided" and `tools/golf_roll.py --fringe`.*

One constant does two jobs today:

```python
ROLL         = {"driver": 24, "wood": 19, "iron": 11, "wedge": 6}
SURFACE_ROLL = {"fairway": 1.0, "green": 1.35, "fringe": 0.7, "rough": 0.35, "sand": 0.0}
```

`ROLL` bundles landing speed, descent angle and spin into one number per
club; `SURFACE_ROLL` is a fudge factor rather than a friction. Nothing in
there can answer *"what if it arrives shallow and fast"*, which is why
skipping is inexpressible and why the wind cannot reach the run.

Separate **how the ball arrives** from **how the ground answers**:

```python
DESCENT  = {"driver": 38, "wood": 43, "iron": 48, "wedge": 55}   # degrees
V_LAND   = {"driver": 1.00, "wood": 0.92, "iron": 0.78, "wedge": 0.62}
SPIN     = {"driver": 0.05, "wood": 0.12, "iron": 0.34, "wedge": 0.62}
FRICTION = {"green": 0.20, "fringe": 0.30, "fairway": 0.32, "rough": 0.90, "sand": 3.0}

run ≈ BASE · v² · cos(descent) / friction · firmness − spin_check
```

**Calibrated, not replaced.** The constants are derived so a full swing on a
fairway reproduces today's `24 / 19 / 11 / 6` — the same discipline that
kept 12/3/6/9 unchanged when the wind became a bearing. Checked: `v²·cos θ`
alone gives `1.00 / 0.79 / 0.52 / 0.28` against today's
`1.00 / 0.79 / 0.46 / 0.25`; the gap at iron and wedge is the spin term,
which is where the backspin is already noticeable in play.

**Open, deliberately:** `fringe`. Today it is `0.7`, braking *harder* than
fairway, and the player-facing text says so. KC9SP reads it as intermediate
between fairway and green; Claude argued a collar is cut near fairway height
so fairway ≈ fringe is truer. The table above splits the difference at
`0.30`. Not settled — revisit with `tools/golf_roll.py` in hand.

### The skip

Once descent angle is a real quantity, skipping is not a special case:

```python
SKIP_ANGLE = 20      # degrees; below this, a fast ball can skip
```

Normal shots descend at 38–55°, so it never happens. A stinger, a thinned
iron, or a punched shot into a headwind can drop under 20° — and then,
sometimes, it skips.

**It is a flair.** `golf.py` already has `worked`, `stinger`, `flop`,
`holed-out`, `launched`, `pure` — shots earned by an adept answer, each with
calls shown big at contact. `skipped` joins them as **the only flair the
game never chooses**: it cannot be aimed at, it is never offered, and it
arrives from physics rather than merit. The chain is the pleasure of it —
the stinger is an *earned* flair that flies low, so the trick shot is
reachable only through a shot you earned and never promised.

It must ship with its own call. A ball that goes in the water and comes out
reads as a bug unless the game says otherwise.

| Failure | Level | Log says | Falls back to |
|---|---|---|---|
| surface not in `FRICTION` | `warning` | surface name, hole | fairway's value |
| run negative or absurd (>80 yd) | `warning` | club, surface, speed, value | clamped, says to what |
| descent missing for a club | `warning` | the club | iron's value |
| skip fires on a ball that should be wet | `debug` | angle, speed, hazard | recorded, so we learn its real rate |

**Also in this stage:** `tools/golf_roll.py` — plays N shots per club per
surface per firmness and prints the run distribution, so the coefficients
are tuned by reading a table rather than by playing eighteen holes and
squinting.

---

## Stage 3 — route data, and the ocean tilt

A route is a **named mark + a carry requirement + the hazard that punishes a
miss**. Almost all of it is data; the hazards are already on the cards.

```json
"routes": [
  { "id": "seawall", "name": "down the seawall",
    "stroke": "tee", "carry": 245, "over": "the bay",
    "mark": {"at": 255, "off": -18},
    "fails_into": "water", "bail": "cypress",
    "shortens": 40, "boldness": 0.8 }
]
```

- `stroke` — `"tee"` or `"approach"`. The 6th and 8th shortcuts are *second*
  shots; without this every tee shot would glow gold.
- `carry` — yards that must be flown. `0` is the safe line.
- `fails_into` — reuses `_in_band`; no new hazard machinery.
- `boldness` — 0..1, how much nerve it takes.

**Holes:** 6, 8 and 18 first; then 3 and 14.

**Holes 9 and 10 are not routes.** They are a fairway that tilts toward the
ocean — a per-hole `tilt` on the card, in yards per hundred, applied
laterally. Cheap, and lands in this stage.

**Hole 7 is narration only.** The Snead-putted-off-the-tee story is lore
KC9SP explicitly would not vouch for, so it is told as lore and modelled not
at all.

| Failure | Level | Log says | Falls back to |
|---|---|---|---|
| route names a hazard not on the hole | `warning` | hole, route id, kind | route dropped, hole plays |
| `carry` beyond any club | `warning` | hole, route id, carry | route never offered |
| malformed `routes` | `warning` | hole, the key missing | that route skipped, others kept |

---

## Stage 4 — `read_mark()` — **club and reach LANDED 2026-09-24; routes to come**

*The club half is built and folded into DESIGN.md under "The bag, and the
mark that reads it": a twelve-club bag, and `read_mark(player, club)`
returning the club the yards want, the reach of the club in hand, where a
short club comes down, and the landing patch - drawn on the map and said on
the phone. It landed ahead of stage 3 because it needs no route data. What
remains of this stage is the route half: `kind`, `route` and the gold ring,
once stage 3's routes exist. The colours below are the plan for that; in
range is drawn white rather than green, because green does not read on a
green.*

The route is discovered by aiming at it. No buttons.

```python
def read_mark(self, player, at, off):
    """What the golfer is aiming at, and whether they can get there."""
    → {"kind": "fairway|green|rough|sand|water|obstruction|route",
       "reach": bool, "route": "seawall"|None,
       "says": "the bay — 245 to carry"}
```

| Colour | Means |
|---|---|
| green | fairway or green |
| sand | in a bunker |
| blue | water — **always**, never gold |
| red | obstruction, or beyond reach |
| gold, red ring | a shortcut or trick shot |

**Reach is judged against the selected club**, so the marker teaches
clubbing, and repaints on a club change.

**Water is never gold.** Gold is only ever a curated route from a card. The
skip is never presented as a play.

**The colour is never alone.** The project's own rule from the band palette.
`_mark_title()` already writes `aiming 255, 18 left`; it gains the reading,
so the strip is legible to somebody who cannot separate the red from the
gold.

Pure arithmetic over the hole's hazard list, no I/O — it runs on every tap.

| Failure | Level | Log says | Falls back to |
|---|---|---|---|
| tap nearly hit a route | `debug` | player, distance from the mark | nothing, but tunes the catch radius from real play |
| route chosen from the wrong lie | `debug` | player, lie, route stroke | ignored, plays normally |
| human picks a route, hole advances | `debug` | player, stale route | mark cleared |

**Catch radius** starts at ±15 yards along, ±8 off. A tap on an 8rem strip
covering 500 yards is worth ±10 yards, so gold needs a generous target or it
is unhittable.

---

## Stage 5 — nerve, and the chooser

`BOT_SWINGS` gains a third trait:

```python
"Listener": ((0.78, 0.92), (1.3, 2.0), (0.1, 0.9)),   # power, wild, nerve
"Elmer":    ((0.95, 1.08), (0.5, 0.9), (0.3, 0.8)),
```

Nerve independent of power is what makes the cast worth watching: **Pileup**
is a short wild hitter with high nerve who *tries the seawall and finds the
bay*; **Dipole** is long and straight with low nerve, lays up all day, and
wins anyway.

```
can_carry = reach(player, club) · downwind_help >= route.carry
takes_it  = nerve >= boldness · (1.0 if can_carry else OVERREACH)
```

The failure case is the point, and it falls out: nerve without the club
finds the cove. The new wind model feeds this for free — a downwind hole
genuinely brings the carry into reach, which is the real decision.

**Testable with:** forced talent, many rounds, counting attempts and
failures. No UI, no audio.

---

## Stage 6 — the strip

`read_mark()` rendered into `golfmap.hole_svg()`, which already draws the
mark as a cross and already knows where the hazards are.

| Failure | Level | Log says | Resolution |
|---|---|---|---|
| strip cached by `k`, colour stale | `debug` | the key | `k` includes the mark and its reading |

---

## Stage 7 — difficulty, measured two ways

### What already exists, and stays

`difficulty.py` measures hardness 0..1 from **time** (log-ms against that
person's own median *that sitting*) and **miss rate**, weighted `0.5/0.5`,
over **first exposures only**, with `MIN_N = 3` before a question is ranked
at all. `golf.LIE_HARDNESS` already asks a harder question from a worse lie,
and `_choose()` already leans toward it with a Gaussian of width
`CHOOSE_WIDTH = 0.25`. `ADEPT_HARDNESS = 0.6` already makes a hard question
earn a flair.

**Per-unit by construction.** It reads this unit's own `answer_log` and this
unit's hall log, and nothing else. Nothing ships, nothing is fetched,
nothing is shared. Two ELMERs in one room genuinely build different models
of the same 409 questions — an agreed feature, not an accident, and the
reason no authored ratings are wanted.

### What changes

**Shot hardness replaces lie hardness.** The tee is `0.25` today whether you
are laying up or carrying 245 yards of Carmel Bay.

```python
LIE_HARDNESS[lie]  →  shot_hardness(lie, route, carry_needed, reach, hazards_in_play)
```

Aiming at gold raises the question difficulty. That is the honest price of
the shortcut.

**A floor, not a target.** A shot asks for *4 or above*, not exactly a 4 —
truer to "the shot is hard, so the question is hard", and cheaper, since the
draw already leans rather than forces.

**Segments, per class — both display and targeting.**

| Class | Segments | Questions |
|---|---|---|
| Technician | 5 | 409 |
| General | 8 | 423 |
| Amateur Extra | 10 | 599 |

The scales run against the data — Extra gets the finest scale on the
thinnest evidence, since it is the biggest pool met by the same lone
operator. Handled by shrinking toward the unmeasured state by how much
evidence exists, with `K` rising by class, which is also the *slower
response* the bigger pools were asked to have. Ten segments off three
sightings is noise with a decimal point, and the program says `unrated`
instead.

**Reading time out, thinking time in.** Today length is deliberately unused,
on the grounds that a long question genuinely is harder under a clock. That
is amended: length now *permits* reading time so the remainder is thinking
time.

```
think_ms = ms − words · reading_rate(player)
```

`reading_rate` is estimated **per player** from their own answers, so a
young or slow reader is not charged for reading — and because the rate is
re-estimated as they play, improvement shows up as *their baseline moving*
rather than as questions inflating in difficulty. That is the point: keep
reading.

| Failure | Level | Log says | Falls back to |
|---|---|---|---|
| too few answers to fit a player's rate | `debug` | player, how many | the unit's rate |
| unit has too few | `debug` | how many | a default words-per-minute, labelled |
| `think_ms` goes negative | `warning` | player, ms, words, rate | floored, and the rate re-fitted |

### Two measures, side by side

Counting every attempt measures a different thing from counting first
exposures, and the class report must not quietly change meaning. So both
are kept, named apart, until play tells us which is worth having:

| Measure | Window | Answers | Used by |
|---|---|---|---|
| **pool hardness** | first exposures, everyone on the unit | *How hard is this question?* | class report, tournament ramp |
| **player hardness** | every attempt, recency-weighted | *How hard is this for this player now?* | golf shot-matching |

**Agreed consequence:** on a fresh unit nothing is rated, the gold shot's
question is drawn at random, and the coupling is inert for the first few
evenings. That matches `ramped: False` elsewhere. It sharpens fastest after
a club night, since the hall log carries twenty tables' worth of first
exposures in an evening.

---

## Stage 8 — the records

- **Scorecard:** the route taken, on the stroke.
- **Clubhouse / pro shop board:** who on this machine has taken each route —
  **and who tried and failed**, which is the better wall and the consequence
  worth showing.
- The skip goes on the board with the routes. *"Three have skipped one
  across the bay on the 18th"* is the best line on it.

**Open:** do practice players appear on the board? They are not people.
Listed separately, or left off — undecided.

---

## Stage 9 — narration

Generic tokens, recorded once and reused:

```
the-bold-play-is      "The bold play is,"
going-for-it          "He's going for it."
took-the-safe-line    "Laid up, the sensible way."
made-the-carry        "That's got it."
didnt-make-the-carry  "He didn't get all of it."
skipped-it            "Skipped it! That's still dry."
```

Per-hole colour, following the existing `hole-<course>-<n>-<where>-<k>`
convention, optional and silent until recorded:

```
route-pebble-beach-18-seawall-1.mp3
route-pebble-beach-6-cliff-1.mp3
route-pebble-beach-8-chasm-1.mp3
```

Hole 7's lore lives here and nowhere else.

---

## Order and dependencies

| # | Stage | Needs | Audio? |
|---|---|---|---|
| ~~1~~ | ~~Weather peak~~ **landed** | — | no |
| ~~2~~ | ~~Landing model + skip + `golf_roll.py`~~ **landed** | — | no |
| 3 | Route data + hole tilt | — | no |
| 4 | `read_mark()` | 3 | no |
| 5 | Nerve + chooser | 3 | no |
| 6 | Strip colours | 4 | no |
| 7 | Difficulty: think-time, segments, shot floor | 3 | no |
| 8 | Records | 5, 7 | no |
| 9 | Narration | 3, 5 | **yes** |

The landing model comes before routes on purpose: whether a ball holds the
plateau green on the 6th or runs through the 18th into the bay is decided by
the run, so routes tuned against the old flat model would need retuning the
moment it lands.

**Playable and worth testing from stage 5.** Recordings are needed only at 9.

---

## Still undecided

1. `fringe` friction — intermediate, or fairway-equal. Revisit with
   `tools/golf_roll.py` in hand.
2. Practice players on the clubhouse board — separately, or not at all.
3. Whether a right answer should always leave a playable ball. Today it does
   not: `test_golf.py` pins a fair driver into a creek as *in the creek*. A
   right answer buys a fair swing, not a fair lie. Routes with real
   penalties only mean something if that stays true, so this is worth
   stating outright before stage 3.
