# Golf: the ball in the air and on the ground

A plan for review, written 2026-09-27. Nothing in it is built. It follows
`docs/golf-plan.md` and keeps to its rules: one fact, one rendering; failure
is a state; unmeasured is a state; nothing is authored that can be measured.
Where this plan changes something that file or DESIGN.md says, it says so.
As each phase lands it goes into DESIGN.md ("Carry, then roll", "The bag,
and the mark that reads it") and this file gets shorter.

Every number below was measured by running `elmer/golf.py` as it stands at
f512b73, from scratch scripts outside the repository, on an Intel Core
Ultra 9 275HX under Python 3.12.10. Published figures carry their source.
A figure this plan could not check directly is marked **(unverified)**.

---

## Scope

In:

- The ball's flight: drag, lift from backspin, spin decay, the wind as it
  blows at the height the ball is, and the density of the air on the day.
- What the flight hands the ground: the landing speed, the descent angle
  and the spin the ball actually has when it comes down.
- The ground's answer: bounce, check, and roll, on each surface, on the
  day's firmness.
- What the screens show of it, and the tools and tests that hold it.

Out:

- The swing. The meter, the sweet zone, the spread and the leak stay as
  they are. The physics decides what a struck ball does, not how well it
  was struck.
- The question side of golf: the draw, hardness and flairs. Nothing here
  changes how a question is chosen or what a right answer earns.
- Putting, except as an open question (see the end). The green's rolling
  model was built in the last week and its kindness is on purpose.
- Anything that leaves the unit. This plan needs no new network fetch.

---

## 1. What the model does now, and where it falls short

### What it is

The ball is already flown. `golf._fly` is a point mass in three dimensions
with drag, Magnus lift and spin decay, stepped with the explicit Euler
method at 20 ms (`FLIGHT_DT`). The constants:

| Constant | Value | Meaning |
|---|---|---|
| `BALL_DRAG`, `SPIN_DRAG` | 0.21, 0.30 | CD = 0.21 + 0.30·S, where S = rω/v is the spin ratio |
| `LIFT_MOST`, `LIFT_RISE` | 0.42, 3.0 | CL = 0.42·(1 − e^(−3S)) |
| `SPIN_DECAY_S` | 22 s | spin falls by e in 22 s |
| `AIR_DENSITY` | 1.225 kg/m³ | always; sea level at 15 °C |
| `WIND_SHEAR`, `WIND_REF_M` | 0.15, 10 m | power law, held to 0.55–1.35 of the 10 m wind |
| `LAUNCH` | per club | launch angle and spin from the TrackMan PGA Tour sheet (section 3) |

Drag does not depend on the Reynolds number. `_launch_speed` bisects 40
times for the launch speed that makes each club's calm carry equal the
bag's (`BAG`, driver 250 yd to sand wedge 105 yd). `flight()` flies it in a
wind and `wind_on_carry` and `wind_across` subtract calm. `swing_for`
bisects 18 times for the meter's notch.

The ground is not flown. `run_yards` is the formula stage 2 of
`golf-plan.md` agreed:
run = 9.838 · v² · cos(descent) · spin check / friction · firmness · wind,
with the descent (`BAG` column 3), landing speed (column 4) and hang time
(column 8) read from the bag, **not** from the flight. The putt is a
separate rolling model in feet (`roll_putt`).

### Shortfall 1: the air holds the ball up too little, so the bag needs too much ball speed

Flying TrackMan's own PGA Tour launch conditions (ball speed, launch angle,
spin) through `_fly` at 1.225 kg/m³, calm:

| Club | Ball speed, mph | Model carry, yd | TrackMan carry | Model apex, yd | TrackMan apex | Model land, ° | TrackMan land |
|---|---|---|---|---|---|---|---|
| Driver | 167 | 228.9 | 275 (−16.8%) | 19.6 | 32 | 27.5 | 38 |
| 3-wood | 158 | 220.2 | 243 (−9.4%) | 18.3 | 30 | 27.8 | 43 |
| 5-wood | 152 | 217.5 | 230 (−5.4%) | 20.2 | 31 | 30.9 | 47 |
| 5-iron | 132 | 190.9 | 194 (−1.6%) | 22.3 | 31 | 35.7 | 49 |
| 7-iron | 120 | 169.6 | 172 (−1.4%) | 27.9 | 32 | 43.6 | 50 |
| 9-iron | 109 | 144.3 | 148 (−2.5%) | 29.1 | 30 | 47.9 | 51 |
| PW | 102 | 128.8 | 136 (−5.3%) | 29.9 | 29 | 50.7 | 52 |

The irons are near; the long clubs are not. At the driver's spin ratio
(S = 0.075) the model's lift coefficient is 0.085. A scratch fit of the
same model form to the TrackMan table needed about 0.17 there, twice as
much. With too little lift, the launch solve makes up the carry with speed:
ELMER's 250-yard driver leaves at 179.2 mph, 12 mph faster than the tour
average that carries 275. A 7-iron at 165 yd needs 117.4 mph, which is
about right.

### Shortfall 2: one fact, two renderings

The descent angle and the hang time exist twice, and they disagree:

| Club | Flown descent, ° | `BAG` descent (roll, skip), ° | Flown hang, s | `BAG` hang, s |
|---|---|---|---|---|
| Driver | 29.5 | 38.0 | 5.38 | 6.0 |
| 7-iron | 42.8 | 48.0 | 5.75 | 4.6 |
| Pitching wedge | 50.1 | 53.0 | 5.54 | 3.85 |
| Sand wedge | 51.2 | 55.0 | 5.10 | 3.6 |

The flight drifts the ball using its own hang. The roll and the skip use
the bag's angle. `wind_drift` and `flight_seconds` read the bag's hang, and
no game path calls them now; only `tests/test_golf_wind.py` does. The
stinger is not flown at all: its descent is the bag's times 0.35 and its
drift is the flown drift times 0.4. This is the bug class `golf-plan.md`
names first.

### Shortfall 3: the wind is weaker than the guide says

The User Guide says a headwind "costs roughly a percent of carry for each
mile an hour". Measured, full swing, yards against calm:

| Club | 10 mph into | 10 mph with | 20 mph into | 20 mph with | 10 mph across, drift |
|---|---|---|---|---|---|
| Driver (250) | −14.1 (−5.7%) | +12.1 (+4.8%) | −30.3 (−12.1%) | +22.3 (+8.9%) | 11.9 yd |
| 7-iron (165) | −14.1 (−8.6%) | +9.1 (+5.5%) | −33.8 (−20.5%) | +13.9 (+8.4%) | 12.7 yd |
| PW (126) | −14.6 (−11.6%) | +9.9 (+7.8%) | −34.8 (−27.6%) | +15.9 (+12.6%) | 12.3 yd |

The driver loses 0.57% a mile an hour into the wind, about half the
guide's figure. TrackMan's own example, as a search summary of a Golf
Digest article gave it, is a tour 7-iron carrying 166 yd calm, 13 yd more
with a 10 mph tailwind and 17 yd less into one **(unverified: the article
refused the fetch)**. The model gives +9.1 and −14.1. The scratch fit in
section 2 gives +12.5 and −17.3.

### Shortfall 4: the ground does not know about spin at landing

Full swing, calm, firmness 1.0, before the dice (`ROLL_NOISE` multiplies by
0.7–1.3):

| Club | Fairway, yd | Green, yd | Fringe, yd | Rough, yd |
|---|---|---|---|---|
| Driver | 24.0 | 32.0 | 16.8 | 8.5 |
| 5-wood | 19.0 | 25.4 | 13.3 | 6.8 |
| 7-iron | 11.0 | 14.7 | 7.7 | 3.9 |
| 9-iron | 8.3 | 11.0 | 5.8 | 2.9 |
| Pitching wedge | 7.0 | 1.9 | 4.9 | 2.5 |
| Sand wedge | 6.0 | 1.6 | 4.2 | 2.1 |

The day's firmness runs from 0.65 to 1.35, so a driver runs 15.6 to 32.4
yd on the fairway. That range is a fair game and was calibrated on
purpose (24/19/11/6). What it cannot do is the green. A full 9-iron lands
on a green and releases 7.7 to 14.3 yd seven times in ten, and spins back
0 to 2 yd the other three. The wedges get a flat 0.2 multiplier
(`WEDGE_CHECK`). The published models run the other way. Haake's model of
a 9-iron landing on a firm green with 148 rev/s (8,880 rpm) of backspin
bounces forward twice and then rolls back about 7 m. Penner's model gives a
9-iron on a firm green with 129, 159 or 191 rev/s a forward bounce and then
a check or a spin back (Penner 2003, section 3.3.1 and figure 8). A tour
9-iron is launched at 8,647 rpm. The model's spin is a per-club figure
(`SPIN_RATE`, 0.05 to 0.62) with no link to the rpm the flight used.

### Shortfall 5: the greens putt slow for their slope

`roll_putt` slows the ball at a constant rate on the flat, and the slope
adds `ROLL_G` = 0.07 of that rate per percent of grade. A rolling ball on a
green whose stimpmeter reading is S feet slows at v₀²/2S, with v₀ = 6.00
ft/s, the stimpmeter's release speed. The slope adds (5/7)·g·sin θ. Put
side by side, the game's slope response matches a stimpmeter reading of
**5.5 ft**. Measured, and worked from that rolling model:

| Putt struck for, ft | Game, 2% uphill | Game, 2% downhill | Game, 2% cross break | Stimp 10, uphill | Stimp 10, downhill | Stimp 10, break |
|---|---|---|---|---|---|---|
| 10 | 8.8 | 11.7 | 0.72 | 8.0 | 13.4 | 1.37 |
| 20 | 17.6 | 23.4 | 1.44 | 15.9 | 26.9 | 2.73 |

The "stimp 10" columns are this plan's own arithmetic from the USGA
definition, not a published table. Average courses run 8 to 12 ft. The
game breaks about half as much as a medium green. DESIGN.md says the odds
on the green are "kinder than a tour's" on purpose, so this is recorded,
not scheduled.

### Shortfall 6: the air is always 59 °F at sea level

`AIR_DENSITY` is fixed. The forecast already fetched for the course carries
`temperature_f`, and nothing reads it for the ball. In the current model,
lower density at the same launch carries a driver 250.0 yd at 1.225 kg/m³,
253.6 at 1.16 and 262.0 at 1.00. A 95 °F afternoon at sea level is about
1.146 kg/m³, and 40 °F is 1.272. All three shipped courses are near sea
level. So on these courses the air is a few yards, not tens.

### What it costs now

| Operation | Time here |
|---|---|
| One `_fly`, driver (about 270 Euler steps) | 0.18 ms |
| Euler bias at 20 ms steps | driver 250.00 yd, against 251.72 yd at 2 ms. The launch solve absorbs it |
| `_launch_speed`, 40 bisections | 7.5 ms |
| `swing_for`, cold | 9.6 ms |
| `swing_for`, launch speed cached | 0.8–1.7 ms |
| `club_yards` for one player, after a spin or shape change (11 launch solves) | **85.9 ms** |
| the same, new wind, same set-up | 2.4 ms |
| the same, cached | 0.02 ms |

`as_dict()` builds `club_yards` for every player on every state read, and
the caches (`lru_cache`, 512 and 8,192 entries) make that cheap until
someone moves a slider. On a Pi 4 the 86 ms is probably most of a second
(section 5). That is a Pi-budget problem today, before any change.

---

## 2. The method

### What stays

- **The bag's calm carry is still the truth.** The table says what each
  club carries on a calm day, the launch speed is solved to match it, and
  the physics adds only what the day does differently. This keeps
  "on a calm day every club carries what its button says" and every
  clubbing decision the game has taught. It is the same discipline stage 2
  used.
- The dice: the spread, the leak, `ROLL_NOISE`, the kick, the foul ball. The
  physics gives the mean. The dice give the day's luck around it, drawn from
  the same `random.Random` in the same order, so seeded tests stay seeded.
  The physics itself never draws.
- `LAUNCH`: launch angle and backspin per club, from TrackMan.
- The putting model, until Scott says otherwise.

### The flight

- **Equations.** A point mass in three dimensions: gravity, drag along the
  air-relative velocity, and lift along ω̂ × v̂_air. The spin axis is tilted
  for shape, as now. The state is (x, y, z, vx, vy, vz), and ω is a closed
  form of time.
- **Coefficients.** CD(S, Re) and CL(S) from a published wind-tunnel fit,
  not fitted freely here. The candidate is Smits & Smith (1994). Penner's
  review says their lift depends on spin and "approximately independent of
  Reynolds numbers", and their drag rises with spin and with Reynolds
  number up to 2.0 × 10⁵. Bearman & Harvey (1976), measured from 14 to 90
  m/s and up to about 104 rev/s, is the cross-check. **The constants of
  both fits are unverified here.** Neither paper was reachable, and this
  plan does not quote their numbers from memory. Phase 1 starts by getting
  the papers.
- **Why not fit to TrackMan.** A scratch fit of CD = a + b·S + c·(1.5 −
  Re/10⁵), CL = d·S^e and a spin time constant to the 12-club TrackMan
  table got within 4.9 yd of carry, 4.5 yd of apex and 7.0° of landing
  angle. It got there by driving the spin decay to 3 s, the lower bound
  allowed. That value is not physical. With the spin time constant held
  near 25 s and no Reynolds term, it missed the driver by 14.5 yd. Nine
  numbers per club and six free constants will fit anything. TrackMan is
  the check, not the source.
- **Spin decay.** Exponential in time, ω = ω₀·e^(−t/τ). τ comes from the
  published source that gives the coefficients. Smits & Smith give a decay
  rate, per Penner's review. Tavares et al. (1999) found dimple patterns
  change it by about 30% at iron spin rates, so the value carries a
  tolerance, not a claim. The current 22 s stays until the source is in
  hand.
- **Wind with height.** Replace the clamped power law with a log profile,
  u(z) = u₁₀ · ln(z/z₀) / ln(10 m/z₀), held at its value at 1 m below 1 m.
  z₀, the roughness length, can go on the course card, which makes it a
  course fact: open links against tree-lined parkland. At the height that
  matters the two laws barely differ. With z₀ = 0.03 m **(unverified; the
  usual open-terrain value)**, the log law gives 1.19× the 10 m wind at 30
  m, and the power law gives 1.18×. At 2 m they give 0.72× and 0.79×. This
  is a small, honest change, not a fix. It is last in its phase.
- **Air density.** ρ = p/(R_d·T), from the forecast's `temperature_f` and a
  standard-atmosphere pressure at the course's elevation. Elevation is a new
  static field on the card. No new fetch. Humidity is left out: it changes ρ
  by under 1% **(unverified figure; standard psychrometrics)**. The bag's
  carry becomes the calm carry at 15 °C at sea level, stated as such. Other
  air moves it.
- **Integrator.** Fixed-step classical RK4 in plain Python, with the
  landing found by interpolating the last step. In a two-dimensional
  prototype, RK4 carries the driver to within 0.01 yd at 50 ms steps of
  what it does at 1 ms. So 20 ms is conservative, and 50 ms is probably
  enough (phase 1 settles it in three dimensions, with wind). RK4 at 50 ms
  is about 136 steps, or 544 evaluations of the right-hand side.
- **Launch-speed solve.** A secant solve from the club's stock launch speed,
  in place of 40 bisections. MacDonald and Hanzely found carry nearly
  linear in launch speed (Penner 2003, section 3.2), so the secant should
  land within 0.1 yd in 3 to 4 flights. `swing_for` does the same, from the
  linear guess frac = carry / full carry.
- **Why not `scipy.integrate.solve_ivp`.** In the prototype it cost 0.57 ms
  a flight (RK45, 98 evaluations, a terminal ground event) against 0.27 ms
  for RK4 at 50 ms. Importing `scipy.integrate` took 327 ms here, and a Pi
  pays more. It would also need a pure-Python twin for a unit without scipy.
  Two integrators that must agree are two renderings of one fact. The game
  flies with RK4, and scipy is the reference that checks it (section 4).
- **Where it lives.** A new module, `elmer/golfball.py`: pure functions, no
  I/O, no clock, no random numbers. It takes launch conditions, the wind,
  the air and the ground and returns the flight and the run. `golf.py` keeps
  the game and calls it. `golf.py` is 2,858 lines, and the physics is
  easier to test and to read on its own.

### What the flight returns

One record per flight: carry, lateral, apex, hang, descent angle, landing
speed, spin at landing, and up to 32 sampled points (x, y, z) for drawing.
The roll, the skip, the drift and the drawing all read this one record. The
bag's `descent`, `v_land` and `hang` columns stop being inputs. They stay
in the table for one release as the check the tests compare against, and
then go.

### The ground

A bounce-and-roll model after Penner (2002b), as his 2003 review describes
it:

1. **Impact.** Normal and tangential speeds and backspin at landing. The
   coefficient of restitution falls with normal impact speed: about 0.5
   below 1 m/s, toward 0.12 near 20 m/s (Penner's measurement, as the
   review states it). The tangential impulse is limited by kinetic friction
   μ. If μ is above Daish's critical value μ_min = 2(v_x + rω)/(7(1 + e)v_y),
   the ball leaves rolling or with topspin. Below it, the ball keeps some
   backspin.
2. **The crater.** Turf gives, so the ball rebounds as if from a rigid
   surface tilted toward it. Penner takes the tilt as linear in the impact
   speed and the angle of incidence. The two slopes are **unverified here**
   and come from the paper.
3. **Bounces** until the bounce is under 5 mm (Penner's rule). Each hop is
   flown ballistically, without lift, since it is too short to matter.
4. **Roll** at a constant rolling deceleration per surface. On the green
   it comes from the stimpmeter: a = v₀²/2S, with v₀ = 1.83 m/s and S
   in meters. On the fairway, fringe and rough it is a fixed per-surface
   value, calibrated (below).
5. **Firmness** is the day's moisture. It moves e, μ and the crater slope
   together, one number that the ground words already print ("firm and
   running", "soft underfoot").
6. **Sand** stops a ball where it pitches, as now. **Water** keeps the skip
   rule (below).

**Calibration, the stage 2 way.** The fairway's rolling deceleration and
the fairway μ are solved so that a full driver, 5-wood, 7-iron and sand
wedge on a fairway at firmness 1 still run 24/19/11/6 yd, each within
±1.5 yd. The ordering green > fairway > fringe > rough that
`test_golf_landing.py` pins stays pinned. The fringe argument in
`golf-plan.md` stays open and gets a better tool: its μ and deceleration
are now two physical numbers to argue over, not one.

**What moves on purpose.** A full short iron onto a firm green checks or
comes back; it no longer releases 8 to 14 yd. A long iron or wood onto a
green still releases, because it comes in shallower and spins less. The
wedge's flat `WEDGE_CHECK` and the `SPIN_ODDS` dice are replaced by spin at
landing. The golfer's spin slider becomes a real rpm (0.75× to 1.25× the
club's, as `SPIN_FLIGHT` already says), and a wedge's spin-back comes from
it. `SPIN_BACK_MOST` (4 yd) stays as a cap, so a spin-back is never longer
than today's.

**The skip.** The rule stays the same: under `SKIP_ANGLE` (20°) and faster
than `SKIP_SPEED`, with the same odds. But the angle is now the flown
descent. A stinger must then be flown as a stinger: lower launch, less
spin. That may not come in under 20°. See the open questions: the skip is a
promise in `golf-plan.md`.

---

## 3. The published figures it is checked against

| Check | Source | Tolerance | Status |
|---|---|---|---|
| Carry, apex and land angle, driver to PW, flying TrackMan's launch conditions | TrackMan, "PGA Tour Averages", yards and meters sheets. A TrackMan-made PDF (InDesign, created 2019-01-04), read from https://teeituprva.com/wp-content/uploads/2019/03/PGA-AVERAGES-INTERACTIVE.pdf. Driver: 113 mph club, 167 mph ball, 10.9°, 2,686 rpm, apex 32 yd, land 38°, carry 275 yd; 7-iron: 120 mph, 16.3°, 7,097 rpm, 32 yd, 50°, 172 yd; PW: 102 mph, 24.2°, 9,304 rpm, 29 yd, 52°, 136 yd | carry ±3%, apex ±3 yd, land ±4° per club; mean absolute carry error under 2% | **verified** against that copy. TrackMan's own help-center copy refused the fetch. These are the numbers `LAUNCH` already uses |
| The same, 2024 edition | TrackMan, "Introducing updated Tour Averages", 2 May 2024, https://www.trackman.com/blog/introducing-updated-tour-averages (40+ events and 200+ players, men; 30+ events and 150+ players, women) | same | **unverified**: the tables are images in a media kit and were not read. Phase 0 reads them, and if the numbers moved, the check moves with them, in the open |
| LPGA driver | golf.com, 23 April 2019, quoting TrackMan: 94 mph club, launch 13.2° | as above | **partial**: ball speed, spin and carry not read |
| Wind, tour 7-iron: 166 yd calm, +13 yd at 10 mph behind, −17 yd at 10 mph into | Golf Digest, "We've taken the guesswork out of playing in the wind…", citing TrackMan | ±3 yd each | **unverified**: seen only in a search summary |
| "A percent of carry per mph into, about half with" | Folk rule, repeated in the User Guide | not a test; a sentence to keep true or rewrite | **unverified** |
| Coefficient of restitution, ball on turf: about 0.5 below 1 m/s, falling toward 0.12 near 20 m/s | Penner, A. R., "The physics of golf", *Rep. Prog. Phys.* 66 (2003) 131–171, section 3.3.1, summarizing Penner's measurement | the model's e(v) within ±0.05 at 1, 5, 10 and 20 m/s | **verified** in the review's text. The functional form is in Penner 2002b (below) and is **unverified** |
| Critical friction for checking backspin, μ_min = 2(v_x + rω)/(7(1 + e)v_y) | Daish (1972), as given in Penner 2003, equation 5 | exact, a unit test on the formula | **verified** in the review |
| Run of a 9-iron on a firm green at 129, 159 and 191 rev/s: forward bounce, then check or back | Penner, A. R., "The run of a golf ball", *Can. J. Phys.* 80 (2002) 931–940, figure 8; reproduced as Penner 2003, figure 8 | qualitative: the ball's final motion is backward at 159 and 191 rev/s | caption **verified**; the distances in the figure are **unverified** |
| 9-iron, firm green, 148 rev/s: two forward bounces, then about 7 m back | Haake (1991, 1994), as given in Penner 2003, section 3.3.1 | back between 3 and 10 m on the firmest green | **verified** in the review's text |
| Drives: run depends mostly on impact angle | Penner 2002b, abstract | ordering test: flatter landing runs further at equal speed | **verified** (abstract) |
| Stimpmeter: V-groove bar 36 in long, notch 30 in from the tapered end, raised to about 20°, release speed 6.00 ft/s (1.83 m/s); three balls each way, averaged; slope-corrected as 2·S↑·S↓/(S↑ + S↓) | USGA (the 2013 USGA article on the updated Stimpmeter refused the fetch); read from Wikipedia's "Stimpmeter", which cites the USGA | the roll model's flat distance for a 1.83 m/s start equals S within 2% | **partial**: read second-hand |
| Green speeds: average course 8/10/12 ft slow/medium/fast; U.S. Open 10/12/14 | Wikipedia's "Stimpmeter", attributed to the USGA | range check only | **partial**: second-hand |
| Capture speed at the cup, dead center: 1.63 m/s at most | Holmes, *Am. J. Phys.* 59 (1991) 129–136, as given in Penner 2003, section 3.3.2 | only if putting is opened | **verified** in the review |
| Drag and lift coefficients, spin decay | Smits, A. J. and Smith, D. R., "A new aerodynamic model of a golf ball in flight", *Science and Golf II* (E & FN Spon, 1994), pp. 340–347 (Penner's list says 341–7); Bearman, P. W. and Harvey, J. K., *Aeronaut. Q.* 27 (1976) 112–122 | the source's own curves, to the precision the paper prints | **unverified**: citations confirmed, constants not read. **Phase 1 cannot land without them** |
| Average male amateur: 93.4 mph driver club speed, 214 yd | A search summary citing TrackMan | not used as a test | **unverified**, and it does not say whether 214 is carry or total |
| Log wind profile, z₀ ≈ 0.03 m for open grass | Standard micrometeorology | not a test | **unverified** here |

---

## 4. When numpy or scipy is missing

A unit updated with a plain `git pull` gets the new code without the new
packages. `--doctor` already says so.

**The game needs neither.** The integrator is plain Python (section 2). On
this machine numpy was slower for the sizes golf has: one numpy RK4 batch
of 11 shots, one per club, took 36 ms against about 0.3 ms a shot in
plain Python. A batch of 400 took 106 ms. numpy's cost is per step, not per
shot, so it pays only above a few hundred shots at once, and nothing a page
asks for needs that. Importing numpy took 74 ms. So `elmer/golf.py` and
`elmer/golfball.py` import neither, and a unit without them plays the same
game to the last digit.

scipy is for the tools:

- `tools/golf_flight.py` flies every check in section 3 with
  `solve_ivp` (RK45 at rtol 10⁻⁹) as the reference and prints the game's
  RK4 beside it. It imports scipy inside the function that uses it. When
  the import fails, it prints one line naming the package and the apt
  package (`python3-scipy`), and still prints the game's own numbers.
- Any calibration solve (the fairway's deceleration and μ, for example) is
  `scipy.optimize` in the tool. Its result is written into
  `elmer/golfball.py` as a constant with a comment saying how it was
  derived, which is how `ROLL_BASE` is kept now.
- One test, `tests/test_golf_flight.py`, compares RK4 against `solve_ivp`.
  Like the browser tests, it **fails** with a clear message when scipy is
  missing, rather than skipping. scipy is a declared dependency, and CI has
  it.

If Scott would rather fly with `solve_ivp` at runtime, the fallback shape
is: the import happens inside the function; `ImportError` logs one
`log.warning("golf: scipy missing (%s) - flying with the built-in
integrator", exc)` per process and uses RK4; a test holds the two within
0.1 yd. This plan recommends against it, because it keeps two renderings
of one fact alive for no gain in speed.

The current model is replaced, not kept beside the new one. The new one
needs nothing the old one did not.

---

## 5. What it costs on a Raspberry Pi

**Measured here** (Core Ultra 9 275HX, Python 3.12.10, best of 7):

| Flight | Steps | Time |
|---|---|---|
| Current `_fly`, Euler, 20 ms | ~270 | 0.18 ms |
| Prototype RK4, 2-D, 20 ms | ~340 | 0.68 ms |
| Prototype RK4, 2-D, 50 ms | ~136 | 0.27 ms |
| Prototype `solve_ivp` RK45 with ground event | 98 evaluations | 0.57 ms |

A 3-D RK4 at 50 ms should be about 0.4 ms here (estimate: half again the
2-D cost for the extra state). The bounce and roll is a few hops, each in
closed form, and costs under a tenth of a flight.

**The Pi, estimated, not measured:** single-thread CPython on a Pi 5 is
roughly 3–4× slower than this machine, and on a Pi 4 roughly 8–12×. So one
flight would take about 1.5 ms on a Pi 5 and 4 ms on a Pi 4. Phase 0
measures it on a real Pi before anything else is decided.

**Per stroke**, with the secant solves: the notch (`swing_for`, about 4
flights), the struck ball (1), and the drift against calm (2), plus a launch
solve (3–4) when the set-up is new. That is about 10 flights: roughly 4 ms
here, 15 ms on a Pi 5 and 40 ms on a Pi 4 (estimate). One stroke is
computed once, on the unit running the round, and every screen gets the
result. No page flies anything. A table with four players costs four
strokes, one at a time, as now.

**Per state read.** This is where the budget is spent today.
`club_yards` for one player, after a slider move, is 86 ms here, and
probably 0.7–1 s on a Pi 4. The secant solve cuts its 440 flights to about
55. The caches stay. So the rule holds, compute only what the page asked
for:

- `club_yards` is worked out when the away player's set-up, the hole's wind
  or the lie changes, and is held until one of those changes, not rebuilt
  on every poll. The `lru_cache` does most of this already. The change is
  to stop paying 40 flights per launch solve on a miss.
- The drawn path (section 6) is sampled from the flight the stroke already
  flew. Nothing is flown for drawing.
- Nothing is precomputed at startup, and no table is written to disk. A
  cold cache after a restart costs one set of solves, the first time a
  player sets up.

---

## 6. What changes on screen, and how the promises are kept

**What the player notices:**

- **Carries on a calm day do not change.** Every club still carries what
  its button says, to the yard, at 15 °C at sea level.
- **The wind bites harder**, and harder for the high-spinning clubs. From
  the prototype, a full 7-iron into 10 mph loses about 17 yd, not 14, and
  gains about 12 with it, not 9. A driver into 10 mph loses about 19 yd,
  not 14. These are prototype figures and phase 1 replaces them.
- **Warm days carry a little further.** On the shipped sea-level courses,
  by a few yards at most, going by the current model's density
  sensitivity. The club buttons already show "what each club gets from here
  today". They include the air.
- **Descent and hang become one number each.** A driver comes down at about
  40°, not the 29.5° it is flown at now. Each wedge hangs as long as its
  flight, not 3.6 s.
- **Greens answer spin.** A full short iron onto a firm green checks or
  comes back; a long iron still releases; a soft green takes the spin off
  on the first bounce (Haake's finding). The call words already exist:
  "checked up", "spun back", "released".
- **Apex and hang are said, not just used.** The stroke line can add them:
  "7-iron, 158 yards, 29 yards high, ran 4 more". This is Scott's call
  (open questions).

**The drawing.** Today no screen draws a flight. The strip draws where the
ball lies, the mark and the reading. This plan proposes:

- The **plan-view map** draws the stroke's curve from the flight's sampled
  (x, y) points: the shaped curve, the wind's drift, then the bounces and
  the roll as short dashes to where it rests. It is drawn from the stroke
  record the server kept, so the picture is the ball's path, not a
  sketch of it.
- The **table screen** can draw a small side view of the same stroke: the
  arc to scale from the (x, z) samples, the apex marked with its height,
  the landing angle, the hops. It is optional, and only on the table screen
  (the phone has little room). It follows reduced motion: with it on, the
  finished arc is drawn with no animation.
- **Every drawn thing has words beside it.** The color is never alone.

**The promises:**

- *Golf is a game about exam questions.* The physics decides where a right
  answer's ball goes. It never decides whether an answer was right, and
  never asks a question. A wrong answer is still a foul ball, found by the
  dice as now.
- *Thresholds are printed and never move backward.* The meter's sweet zone,
  `TAP_IN`, `CUP_CAPTURE` and `SKIP_ANGLE` keep their printed values. The
  physics moves what a swing does, not what counts as good. A figure the
  guide prints, such as "a percent a mile an hour", is either made true or
  rewritten in the same commit.
- *One fact, one rendering.* The descent, hang, drift and path come from one
  flight record, which removes the two-renderings cases in shortfall 2.
- *Diagnostics go to the log.* A flight that fails to land, a solve that
  does not converge, a card with no elevation: each logs a line and falls
  back (table below). None reaches a study screen.

| Failure | Level | Log says | Falls back to |
|---|---|---|---|
| launch solve does not converge in 8 steps | `warning` | club, spin, shape, last two carries | bisection, as now |
| flight has not landed after 20 s of flight time | `warning` | club, launch, wind | the carry the table says, and the bag's descent |
| card has no `elevation` | `debug` | course id | sea level |
| forecast has no temperature | `debug` | course id | 15 °C |
| temperature absurd (below −20 °F or above 130 °F) | `warning` | the value | clamped, and says to what |
| run absurd (over `RUN_MOST`) | `warning` | as now | clamped, as now |
| scipy missing, in the tool | printed | the package, the apt name | the game's RK4 numbers alone |

---

## Risks

1. **The coefficients.** The plan's main source is unverified. If Smits &
   Smith cannot be had, Bearman & Harvey or a later published fit (Lyu,
   Kensrud, Smith and Tosaya's ISEA 2018 paper on still-air aerodynamics
   is a candidate, **unverified**) must stand in. A free fit is not an
   option (section 2).
2. **The game gets windier twice.** Stage 1 made rounds start from the
   day's peak wind, on purpose. Stronger wind physics makes that peak cost
   more. A 20 mph afternoon into the wind takes about 40 yd off a 7-iron in
   the prototype.
3. **The skip may become unreachable.** A flown stinger may not come in
   under 20°. The skip is promised in `golf-plan.md` as the one flair
   physics gives.
4. **Seeded tests.** Rounds in the tests are seeded. The physics must not
   add or remove any draw from `rng` or `swing`, or every seeded outcome
   moves. Phase 1 holds the draw order and says so in a test.
5. **Floating point across platforms.** `math.exp` and `math.hypot` can
   differ in the last bit between Windows and a Pi. Tests use tolerances,
   never equality on flown numbers. The two units in a round between units
   do not both fly: the host flies and the visitor shows.
6. **The Pi estimate is only an estimate.** If a Pi 4 is slower than
   thought, the fixed step goes from 20 ms to 50 ms (accuracy allowing), and
   the side view drops before anything else.
7. **The green gets harder to hold with a long iron and easier with a short
   one.** That is realistic, and it changes which club the caddie should
   star. `read_mark`'s expected roll must use the same ground model, or the
   mark and the stroke disagree.

---

## Open questions for Scott

1. Is the bag's calm carry still the truth (recommended), with the air and
   wind changing it on the day? Or should a player's carry come from a ball
   speed?
2. Should the air move the carry on the club buttons, by a few yards
   between a cold morning and a hot afternoon at Pebble?
3. The skip: fly the stinger honestly and let the skip be as rare as
   physics makes it, or keep `STINGER_DESCENT` as an authored flair factor
   and say so in DESIGN.md?
4. Green spin: are you content that a full 9-iron onto a firm green
   comes back instead of releasing?
5. Putting stays at about stimpmeter 5.5 for slope. Keep that as the
   game's kindness, or give each card a stimpmeter reading, printed, and
   roll to it?
6. The side view on the table screen: wanted? And apex and hang in the
   stroke line?
7. Can you get Smits & Smith (1994) and Penner (2002b)? A library copy of
   *Science and Golf II* would do for the first.
8. The 2024 TrackMan tables: if they differ from the 2019 sheet, check
   against the newer one?

---

## Order of work, and the tests for each phase

Each phase is its own commit, with its CHANGELOG paragraph, and runs the
whole suite. Tests follow the house shape: a docstring saying what is
proved and why, `import _isolate` before anything from elmer, then `check`
and `near`, `FAILS`, and `sys.exit(1)`. None touches the network.

| # | Phase | Needs | Changes the game? |
|---|---|---|---|
| 0 | Harness and Pi measurement | — | no |
| 1 | The flight: coefficients, RK4, secant solves | 0, the papers | wind effects, apex, descent |
| 2 | One fact: the ground reads the flight | 1 | no, calibrated back |
| 3 | The air: temperature, elevation, log profile | 1 | a few yards |
| 4 | The ground: bounce, check, roll | 2 | the green |
| 5 | The screens and the docs | 2, 4 | the drawing |

**Phase 0: harness.** `tools/golf_flight.py` prints section 1's tables:
the bag, TrackMan's inputs flown, the wind, the run, and `--bench` for
timing. It imports scipy lazily for its reference column. Run it on a Pi 4
and a Pi 5 and write the timings into this file. Test
(`test_golf_flight.py`, first part): the tool runs with no network and
exits 0, and the game's flight of TrackMan's driver matches the harness's
copy (the harness reads `golf`'s constants, and does not keep its own).

**Phase 1: the flight.** `elmer/golfball.py`, the coefficients from the
source, RK4, the secant solves, and `golf.flight()` calling it. Tests:

- Every club's calm carry equals the bag's within 0.5 yd, at spin 0, 0.5
  and 1 and shape −1, 0 and 1.
- TrackMan's inputs flown: carry ±3%, apex ±3 yd, land ±4°, driver to PW,
  and a mean carry error under 2%.
- RK4 against `solve_ivp`: carry, lateral and apex within 0.1 yd for the
  driver, 7-iron and wedge in calm, 20 mph into and 20 mph across.
- Step convergence: 50 ms against 1 ms, within 0.1 yd.
- The wind is ordered: into costs more than with gives; more spin costs
  more into; a crosswind drifts a full driver 10 yd or more at 10 mph (the
  guide's words).
- Cost, counted and not timed: a cold `club_yards` for one player flies no
  more than 80 flights (a counter on the integrator); `swing_for` no more
  than 8.
- The draw order: a seeded round records the same sequence of `rng` and
  `swing` calls as before the change.
- `test_golf_hand.py`'s headwind bound (−6% to −12% for a 7-iron at 10 mph)
  is checked against the new model. If it moves outside, the bound changes
  in the open, with the reason in its docstring.

**Phase 2: one fact.** `run_yards`, `skips` and the drift read descent,
landing speed and hang from the flight record. `ROLL_BASE` and `V_LAND` are
re-solved so full swings on a fairway still run 24/19/11/6.
`wind_drift` and `flight_seconds` are either routed through the flight or
retired with their tests rewritten. Tests: the calibration point holds
(`test_golf_bag.py`'s `[24, 19, 11, 6]`); the flown descent is what the
roll and the skip receive (one value, asserted identical); a stinger's
descent is below 20° if question 3 says so, or its authored factor is
tested if it does not.

**Phase 3: the air.** `elevation` on the three cards (a number anyone can
check), density from `temperature_f`, the log profile with `z0` on the
card. Tests: a recorded forecast at 95 °F carries a driver further than one
at 40 °F; no temperature means 15 °C, with a `debug` line; an absurd value
is clamped with a `warning`; the 10 m wind is unchanged at 10 m.

**Phase 4: the ground.** Bounce, check and roll per section 2. `FRICTION`
becomes per-surface e, μ and rolling deceleration, and firmness moves them.
The dice stay around the mean. Tests:

- e(v) within ±0.05 of Penner's values at 1, 5, 10 and 20 m/s.
- The μ_min formula against hand-worked cases.
- A 9-iron at 159 rev/s onto the firmest green finishes moving backward; on
  the softest it does not come back.
- A 148 rev/s 9-iron on a firm green comes back 3 to 10 m.
- The fairway calibration point holds within ±1.5 yd.
- The surface order holds.
- Sand stops a ball.
- No run over `RUN_MOST`.
- A seed that holds the spin constant.

The fringe stays where `golf-plan.md` left it, and `tools/golf_roll.py`
gains the new knobs.

**Phase 5: the screens and the docs.** The stroke record carries up to 32
path points, apex and hang. `golfmap.hole_svg` draws the curve and the
hops. The table screen draws the side view if question 6 says so. Tests:
the SVG's path ends where the state says the ball lies (the browser test's
shape, `tests/_browser.py`); the path has no more than 32 points in the
state; reduced motion draws no animation. Docs in the same commit:
USER-GUIDE.md's "The wind" and "Setting up the shot", with new figures from
`tools/guideshots.py`; DESIGN.md's "Carry, then roll" and the bag section;
README's "Since v1.0". This file shrinks to its open questions.

---

## Sources read for this plan

- `elmer/golf.py` at f512b73, `docs/golf-plan.md`, DESIGN.md's golf
  sections, USER-GUIDE.md's golf chapter.
- Penner, A. R., "The physics of golf", *Rep. Prog. Phys.* 66 (2003)
  131–171, read in full from http://raypenner.com/golf-physics.pdf.
  Sections 3.2 and 3.3 and figure 8 are the ones used here.
- TrackMan, "PGA Tour Averages" (yards and meters), a TrackMan-made PDF
  created 2019-01-04, read from the copy at teeituprva.com (URL in
  section 3).
- TrackMan, "Introducing updated Tour Averages", 2 May 2024 (text only; the
  tables are images and were not read).
- Wikipedia, "Stimpmeter", for the USGA's device and procedure.
- golf.com, 23 April 2019, for the LPGA driver's club speed and launch.
- Cited but not read: Smits & Smith (1994); Bearman & Harvey (1976);
  Penner (2002b); Haake (1991, 1994); Holmes (1991); Daish (1972); Tavares
  et al. (1999); the Golf Digest wind article.
