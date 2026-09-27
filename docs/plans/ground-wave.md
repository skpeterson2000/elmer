# Ground wave by the ITU's method: a plan

A plan for review, written 2026-09-27, before any code. It is here rather
than in DESIGN.md because DESIGN.md describes what ELMER *is*, and this
describes what it might become. Each phase folds into DESIGN.md as it lands.

numpy and scipy are now dependencies "for the numerical work ahead", and the
ground wave is one of the three pieces of work named. This plan measures the
model ELMER ships today against the ITU's own ground-wave method, says where
the two disagree and by how much, and proposes a replacement that disagrees
with the ITU by less than a tenth of a decibel. Where the answer on screen
would not change, the plan says so too.

---

## 1. What the model does now, and where it falls short

### What it does

`elmer/groundwave.py` works out a field strength in four steps:

1. **The ground's pull.** Sommerfeld's numerical distance
   `p = pi * d / (lambda * |eps_r - j*60*lambda*sigma|)`, then the standard
   rational approximation to the flat-earth attenuation function,
   `A = (2 + 0.3p) / (2 + p + 0.6p^2)`. That approximation uses only the
   magnitude of the ground constant and drops its phase angle.
2. **The curve of the earth.** A fitted loss:
   `0.050 * f_MHz^(2/3)` dB per km, starting `90 / f_MHz^(1/3)` km out. The
   coefficient and both exponents were fitted so that a sea path lands on
   three service ranges: 300 miles at 1.9 MHz, 150 at 7.1 and 100 at 14.2
   (100 W SSB, rural noise). The module comment says so, and `describe()`
   returns `fitted: True`.
3. **The field.** 300 mV/m at 1 km for 1 kW, scaled by power and by
   `gain_dbi - 1.76`.
4. **The range.** Bisection for the distance where the field drops to the
   noise (ITU-R P.372 man-made noise, `c - d log10 f`) plus the mode's
   signal-to-noise ratio.

The ground comes from eight named types in `GROUND`. `siteground.py` rates a
spot from the soil and water surveys into one of those eight, and the reach
map uses that rating, but only to weight the antenna pattern
(`PATTERN_OF`). **The ground-wave range itself is always worked over
"average" ground.** `propagation.path_bands()`, `propagation.reach_map()`,
the band plan's skip-zone line (`app.py`, `now["ground_wave"]`) and
`antenna_advice` all call `groundwave.describe()` or `useful_range_km()`
with the default ground. The path tool gets its ground-wave rows from
`path_bands()`, so it is on average ground too. `linkbudget.py` borrows only
the noise table and the modes. Its two-ray and diffraction budget is a VHF
matter and is out of scope here.

### The reference it was measured against

- **ITU-R P.368-10 (08/2022)**, the recommendation in force. It is no longer
  a book of curves. It is a method whose "software implementation … is an
  integral part of this Recommendation", shipped as
  `R-REC-P.368-10-202208-I!!ZIP-E.zip`: NTIA/ITS's LFMF program (W. Kozma
  Jr, 2021), C++. It covers a smooth homogeneous earth, 10 kHz to 30 MHz, an
  effective radius from the surface refractivity N_s, and a reference short
  monopole that makes 300 mV/m at 1 km for 1 kW.
- For this plan the ITU's LFMF source was compiled unchanged in a scratch
  directory. The only edit was portability: `std::` math overloads for g++,
  because without them the program gave nonsense. It was run with
  N_s = 315 N-units and both terminals at 0 m.
- The compiled program was checked against **P.368-10 Figure 2** (sea,
  sigma = 5 S/m, eps_r = 70), read by eye:
  - The 30 MHz curve crosses -30 dB(uV/m) at about 370 km. LFMF gives
    -30.5 dB(uV/m) at 370 km.
  - The 1.5 MHz curve reaches -30 dB(uV/m) near 2,000 km. LFMF gives -28.6
    at 2,000 km.
  - All curves start at 109.5 dB(uV/m) at 1 km. LFMF gives 109.54.
  - Agreement is within reading accuracy, about 2 dB.

The differences below are **ELMER minus P.368 (LFMF)**, in dB, at 1 kW from
the reference monopole. For this comparison ELMER was given `gain_dbi=1.76`,
the gain at which its reference is 300 mV/m, so both start from the same
field. Negative means ELMER is too pessimistic.

**Average ground (sigma 0.005 S/m, eps_r 13: ELMER's default)**

| MHz | 1 km | 10 km | 50 km | 100 km | 200 km | 300 km |
|---|---|---|---|---|---|---|
| 1.9 | +1.3 | +1.1 | +1.7 | +0.7 | -2.8 | -4.7 |
| 3.6 | +2.6 | +1.4 | +1.4 | -1.4 | -6.8 | -10.2 |
| 7.1 | +3.0 | +0.5 | +0.9 | -5.1 | -14.3 | -21.1 |
| 14.2 | +1.9 | 0.0 | -1.7 | -11.7 | -27.9 | -41.0 |
| 27.185 | +0.9 | -0.2 | -6.1 | -22.2 | -49.4 | -73.0 |

**Sea (sigma 5 S/m, eps_r 70: P.368-10 Figure 2's ground)**

| MHz | 30 km | 50 km | 100 km | 200 km | 300 km | 500 km |
|---|---|---|---|---|---|---|
| 1.0 | +0.2 | +0.4 | +0.5 | -2.7 | -5.5 | -10.1 |
| 1.9 | +0.2 | +0.5 | -0.7 | -6.1 | -10.8 | -19.2 |
| 3.6 | +0.3 | +0.7 | -3.0 | -11.8 | -19.9 | -35.0 |
| 7.1 | +0.5 | +0.3 | -7.6 | -22.7 | -37.1 | -63.9 |
| 14.2 | +0.5 | -3.0 | -16.5 | -40.6 | -62.0 | -101 |
| 27.185 | -0.1 | -8.1 | -26.1 | -58.4 | -87.2 | -126 |

The same pattern holds on ELMER's poor ground and sand, on P.368-9's
"land" (sigma 0.003, eps_r 22) and on medium dry ground (0.001, 15). Two
things are wrong:

- **Close in, over land, ELMER is 1 to 5 dB too strong** at 1 to 3 km. The
  worst case is +4.7 dB at 1 km on 3.6 MHz over sigma 0.003 / eps_r 22. The
  rational approximation drops the phase of the ground constant, and at HF
  over land the phase matters.
- **Past the horizon ELMER is far too weak.** The fitted curvature loss
  grows linearly with distance, but the residue series decays more slowly
  at these distances. The error is 5 dB at 100 km on 40 m over land, 23 dB
  at 200 km on 40 m over sea, and 58 dB at 200 km on 11 m over sea.

### Whether it shows on screen

The screen shows **ranges**, not field strengths, so what counts is where
the field crosses the noise. The table compares the useful range
(`useful_range_km`) at 100 W SSB, rural noise and a vertical antenna, with
ELMER's own power, gain, noise and mode arithmetic in both columns. 11 m
uses the law's power: 12 W PEP SSB, 4 W AM carrier.

| Ground | 160 m | 80 m | 40 m | 20 m | 10 m | 11 m SSB 12 W | 11 m AM 4 W |
|---|---|---|---|---|---|---|---|
| average | 132 / 135 | 85 / 86 | 57 / 57 | 42 / 42 | 33 / 33 | 21 / 21 | 11 / 11 |
| poor | 98 / 95 | 67 / 64 | 49 / 47 | 38 / 37 | 30 / 29 | 18 / 18 | 10 / 10 |
| sand | 73 / 70 | 59 / 56 | 47 / 45 | 38 / 36 | 30 / 29 | 18 / 18 | 10 / 10 |
| city | 76 / 71 | 49 / 48 | 35 / 36 | 27 / 28 | 22 / 23 | 13 / 14 | 7 / 8 |
| ice | 74 / 68 | 45 / 44 | 29 / 31 | 22 / 24 | 17 / 19 | 10 / 12 | 5 / 6 |
| wet | 204 / 230 | 127 / 143 | 81 / 91 | 56 / 62 | 41 / 47 | 32 / 30 | 18 / 17 |
| fresh water | 156 / 163 | 117 / 129 | 88 / 102 | 67 / 81 | 50 / 65 | 40 / 44 | 28 / 26 |
| **sea** | **494 / 834** | **361 / 720** | **247 / 564** | **160 / 360** | **100 / 201** | **88 / 168** | **72 / 126** |

*km, ELMER / P.368-10.*

- **Over land, today's model is already right to within 10%, and mostly
  within 5%.** On ground ELMER calls average, poor, sand or city, the
  field's errors fall where the signal is already 20 to 40 dB under the
  noise, so they never reach the range. P.368-10's own Note 2 puts
  place-to-place variation at about 3.5 dB. On 80 m over average ground
  that is 73 to 101 km around the 86 km figure, a bigger spread than any
  land row's error.
- **Over sea, today's model gives half the range**, 44% to 59% of P.368's.
  The fault is the three anchors the curvature loss was fitted to. Under the
  same noise, mode and power, P.368 gives 513 miles at 1.9 MHz (anchor 300),
  348 at 7.1 (anchor 150) and 221 at 14.2 (anchor 100). The anchors were
  service ranges, which carry margins for night skywave interference,
  fading and reliability. They were not the physics of the ground wave.
- **Wet ground and fresh water run 10% to 22% short**, most on the higher
  bands.
- **ELMER's charge against the antenna.** ELMER's callers pass
  `gain_dbi=0` for a vertical and charge `0 - 1.76 = -1.76` dB against the
  300 mV/m reference. P.368's reference monopole on the ground is the
  vertical, and the ground's losses are already inside the attenuation
  function. That charge costs 8% of range: on 80 m over average ground,
  86 km against 93. This is a convention to decide, not a physics error
  (see Open questions).
- **The ground table** differs from ITU-R P.527-6's Attachment, Figure 24,
  which was read directly:
  - wet ground: P.527 gives 0.01 S/m, ELMER uses 0.02
  - very dry ground: P.527 gives 1e-4 S/m and eps_r 3, ELMER's sand uses
    2e-4 and 10
  - fresh-water ice: P.527 gives roughly 1e-5 to 1e-4 S/m at HF, read by
    eye; ELMER's ice uses 1e-3

  Only the wet-ground difference moves a range much: 80 m, 115 km at P.527's
  value against 143 km at ELMER's. The ice difference barely does: 37 km
  against 45. Ice at eps_r 3 is poor whatever its conductivity.
- **Horizontal polarization.** P.368 agrees with ELMER that there is almost
  none. Over average ground at 7 MHz, LFMF puts horizontal 51 dB under
  vertical at 1, 10 and 30 km. `HORIZONTAL_NOTE` stands.

### Two gaps that are not physics

- **The ground wave ignores the rated ground.** An operator on the coast who
  presses "rate the ground" and gets "sea" still sees the average-ground
  ring. Of everything in this plan, this is the fix that changes the most
  numbers for the least computation.
- **"Labelled as one wherever it is shown" is not met.** `describe()`
  returns `fitted: True`, but no page reads it. DESIGN.md has no ground-wave
  section at all.

---

## 2. The method

Use **P.368-10's own method**, the LFMF formulation, and not GRWAVE. It is
the one the recommendation in force makes normative, it is short (about 300
lines of the C++ carry the physics), and it has been reproduced here in
numpy and scipy to within **0.009 dB of LFMF at all 261 grid points above
-60 dB(uV/m)**. The grid was five grounds, six frequencies from 1 to 27.185
MHz, and 1 to 1,000 km.

- **Effective earth radius** from surface refractivity:
  `a_e = 6370 / (1 - 0.04665 exp(0.005577 N_s))`. At N_s = 315 that is
  8,730 km, which is different from `geo.EFFECTIVE_R_KM` (8,495, the 4/3
  figure). The P.368 figure belongs to P.368. It goes in `geo.py` as a named
  function of N_s, with a comment saying why it is not the VHF radius.
- **Surface impedance**: `eta = eps_r - j*sigma/(omega*eps_0)`, then
  `Delta = sqrt(eta - 1)/eta` for vertical polarization, and
  `q = -j*nu*Delta` with `nu = (a_e*k/2)^(1/3)`.
- **Near: flat earth with a curvature correction** (Wait 1956; DeMinco,
  NTIA Report 99-368, eq. 31, as cited in LFMF), for `d < 80 / f_MHz^(1/3)`
  km. This uses the Sommerfeld-Norton function
  `F(p) = 1 + j*sqrt(pi)*qi*w(qi)` with the full complex argument, and
  `w` is the Faddeeva function, `scipy.special.wofz`. This is the step that
  removes the +1 to +5 dB close in. For `|q| <= 0.1` LFMF has a ten-term
  power series (DeMinco eq. 28), to be ported as it stands. None of ELMER's
  eight grounds reaches it at HF, but a P.527 ground might.
- **Far: the residue series** (Bremmer, Wait, Fock), which is
  `E/E0 = sqrt(pi*x) e^(-j*pi/4) * sum_i e^(-j*x*t_i) / (t_i - q^2)` with
  `x = nu*d/a_e`. The `t_i` are the complex roots of
  `W1'(t) - q W1(t) = 0`, where W1 is Wait's Airy function of the third
  kind: `W1(z) = 2*sqrt(pi) e^(-j*pi/6) Ai(z e^(-j*2pi/3))`.
  `scipy.special.airy` takes the complex argument directly. The roots start
  from the real zeros of Ai or Ai' (NIST DLMF Table 9.9.1 for the first ten,
  DLMF 9.9.6 to 9.9.9 beyond), rotated by `e^(j*2pi/3)`, then Newton
  iteration, `A = (W1' - q W1)/(t W1 - q W1')`. That is 25 iterations at
  most, to a relative 5e-7, done for all roots at once as a numpy array.
- **Convergence.** LFMF stops summing when a term falls below 5e-4 of the
  total, or returns 0 when the sum underflows. The port keeps LFMF's rule so
  that it reproduces LFMF exactly. A root whose Newton iteration does not
  settle is logged once per (frequency, ground) and the curve falls back
  (section 4). It does not return a zero field. Results below about
  -150 dB(uV/m) lose meaning in double precision: LFMF and the port
  disagree by tens of dB there, at 1,000 km on 14 to 27 MHz. They are
  clipped as "nothing". They are 150 dB under any noise floor.
- **Terminal heights.** LFMF carries height-gain terms, a two-term Taylor
  series near and the ratio `W1(t - y)/W1(t)` far. Its validation limits
  heights to 0 to 50 m. ELMER's callers are both at 0 m today, and the first
  phases keep them there. Height is an open question.
- **Mixed paths: Millington**, P.368-10 Annex 2, eqs. (1) to (3). Work the
  field forward and backward over the sections and average the two in dB.
  It needs only the homogeneous curves, so it costs a few more lookups and
  nothing new. An example worked with the port, at 7 MHz and 1 kW over
  100 km:
  - all land: 6.9 dB(uV/m)
  - 90 km land, then 10 km sea: 26.1
  - 50 km land, then 50 km sea: 36.0
  - 10 km land, then 90 km sea: 46.0
  - all sea: 65.2

  This is the coastal recovery effect, and the reason a mixed path cannot
  be approximated by the "average" of its grounds.
- **Not GRWAVE.** GRWAVE (GEC-Marconi, Rotheram, 1985; CCIR PC version
  1989) is the older ITU program. It has an exponential atmosphere, a
  geometric-optics region for raised terminals, and the extended flat earth
  between. Its Fortran is public at github.com/space-physics/grwave. For
  terminals on the ground below 30 MHz, the case ELMER has, the ITU replaced
  it with LFMF in 2022. It was compiled for this plan but **not run**, so no
  GRWAVE figure appears here. A check against it is proposed in section 3.

**What the function returns.** A new `groundwave.curve(mhz, sigma,
epsilon, ns=315)` returns distances and dB(uV/m) at 1 kW. `field_strength`,
`useful_range_km` and `describe` read that curve and scale it for power and
gain. The range becomes a lookup on the curve, with no bisection. `describe`
gains `model` ("P.368-10" or "fitted") and `basis` (a sentence for the
page).

---

## 3. What it will be checked against

| Check | Source | Tolerance | Verified for this plan |
|---|---|---|---|
| Field vs distance, 5 grounds x 6 frequencies x 1 to 1,000 km | ITU-R P.368-10 integral software (LFMF), `R-REC-P.368-10-202208-I!!ZIP-E.zip`, from https://www.itu.int/rec/R-REC-P.368-10-202208-I/en | 0.1 dB where E > -60 dB(uV/m) | Yes. Port within 0.009 dB. |
| Sea curves, 1.5 to 30 MHz | P.368-10 **Figure 2** (sigma 5, eps_r 70), p. 5 | 3 dB, read by eye | Yes, two crossings and the 1 km start, as in section 1 |
| Low-salinity sea | P.368-10 **Figure 1** (sigma 1, eps_r 80), p. 4 | 3 dB, read by eye | Figure seen, **no point read** |
| Land curves (P.368-9's Figures for wet ground, land, medium dry, dry and so on) | ITU-R P.368-9 (02/2007) | 3 dB | **Not verified.** The PDF could not be fetched, so the figure numbers and the land ground's eps_r 22 are from memory. The table for this plan used sigma 0.003 / eps_r 22 on that memory. |
| Ground constants | ITU-R P.527-6 (09/2021), Attachment to Annex 1, **Figure 24** (reproduced from P.527-3 Fig. 1), https://www.itu.int/rec/R-REC-P.527 | Exact values for sea, wet, fresh water, medium dry and very dry. Ice read by eye. | Yes, except ice (curve read by eye) |
| Near-field correction | P.368-10 Annex 1 Note 3: `10 log10(1 - 1/(kr)^2 + 1/(kr)^4)` | Formula | Yes |
| Location variability | P.368-10 Note 2: about 3.5 dB standard deviation | For words on the page | Yes |
| Airy zeros | NIST DLMF Table 9.9.1, https://dlmf.nist.gov/9.9 | 1e-9 | Values as quoted in LFMF, not checked against the DLMF page |
| Flat-earth and residue formulas | DeMinco, NTIA Report 99-368 (1999); Hufford, NTIA Report 87-219 (1987); Wait, J. Res. NBS 56(4), 1956 | Cited in LFMF | **Not read.** Known only through LFMF's comments. |
| GRWAVE cross-check at 0 m terminals | GRWAVE Fortran, github.com/space-physics/grwave (`grwave/src/grwave.for`, `ex.inp`) | 0.5 dB expected | **Not run.** Compiled only. |
| Bremmer, *Terrestrial Radio Waves* (Elsevier, 1949) | The residue series' origin | For the DESIGN.md citation only | **Not consulted** |

The test fixtures are **numbers the ITU's program printed**, stored with the
command that made them (frequency, eps_r, sigma, N_s, heights) and the name
of the zip they came from. A test never runs LFMF itself, and never touches
the network.

---

## 4. When numpy or scipy is missing

A unit updated with a plain `git pull` has neither. The rule is that the
current model keeps answering and the page says which model did.

- **A shipped table first.** `tools/build_groundwave_table.py` computes the
  P.368 curve for every band center in `propagation.BANDS` up to 30 MHz
  (11 bands) on each of the eight grounds, at 120 log-spaced distances from
  0.5 to 3,000 km. It writes `data/groundwave/p368.json`, which is shipped
  content under `paths.CONTENT` and is built like the pools, never at run
  time. The file is 78 KB. Linear interpolation in log-distance stays within
  **0.07 dB** of the full calculation wherever E > -40 dB(uV/m) (60 points
  would be 40 KB and 0.28 dB). Reading it needs only `json` and `bisect`, so
  **a unit without numpy or scipy still gets P.368 on every band ELMER
  names.** The file is read once, on first use, and kept in memory.
- **On demand when the table cannot answer**, for a frequency off the table
  (antenna advice for an arbitrary frequency) or a ground that is not one of
  the eight. The function imports `numpy` and `scipy.special` inside itself,
  not at module top. `groundwave.py` is imported by `app.py` at startup, and
  scipy.special took 278 ms to import on this machine, warm.
- **The fitted model last**, when neither the table nor scipy can answer:
  - the import fails (`ImportError`)
  - the table is missing or unreadable (`OSError`, `json.JSONDecodeError`)
  - a root fails to converge (logged)

  In every case the log gets one warning, naming what failed and saying the
  fitted model answered. The warning is written once per process, not once
  per call, following the project's logging rules. The current code stays
  as `_fitted_attenuation()`.
- **The page says so.** `describe()` returns `model: "P.368-10"` or
  `model: "fitted"`. The note under the reach map and the skip-zone line say
  "the ITU's ground-wave method (P.368)" or "a fitted approximation, because
  this unit lacks scipy; `./install.sh` adds it". `./elmer.py --doctor`
  already names missing numpy or scipy (`diagnostics.py`), and adds one line
  saying the ground wave is on the fitted model.

---

## 5. What it costs on a Raspberry Pi

Measured on the development machine (Intel Core Ultra 9 275HX, Python 3.12,
numpy 2.5.3, scipy 1.18.1):

| Work | Time here | Pi 5, estimated (3 to 4x) | Pi 4, estimated (8 to 10x) |
|---|---|---|---|
| Today's `useful_range_km` (60 bisections) | 0.08 ms | 0.3 ms | 0.8 ms |
| One P.368 curve, 400 distances, 200 residue terms | 2.2 to 2.8 ms | ~10 ms | ~25 ms |
| One P.368 point past the horizon | 0.8 ms | ~3 ms | ~8 ms |
| The whole shipped table (88 curves x 120 points), build only | 0.11 s | ~0.4 s | ~1 s |
| `import scipy.special`, warm cache | 278 ms | ~1 s | 2 to 3 s, more cold |
| `import numpy`, warm | 71 ms | ~0.25 s | ~0.6 s |
| Range lookup on a cached or shipped curve | microseconds | | |

The Pi figures are **estimates**, scaled from single-thread Python
benchmarks and not measured on a Pi. Phase 2 measures them on a Pi 4 and a
Pi 5, and this table gets corrected.

The work per curve is dominated by the residue series:
- 200 complex Airy evaluations for each Newton step, usually 3 to 6 steps
- one `wofz` per near distance
- one 400 x 200 complex exponential for the sum

The operation count is small. On a Pi the cost is scipy's import, not the
arithmetic.

**Pi budget.** Compute only what the page asked for, and read stores once
per change:
- The shipped table answers every band and ground a page asks about today,
  with no scipy import at all.
- The on-demand curve is cached in memory by `(round(mhz, 3), sigma,
  epsilon, ns)`. That key is independent of power, mode, site and gain, so
  moving the watts box never recomputes a curve. The cache is bounded to a
  few dozen curves at about 3 KB each.
- The path tool asks for 12 bands per path. That is 12 table lookups today,
  and at most 12 curve computations on a cold cache off the table.
- Nothing is computed ahead for a page nobody opened.

---

## 6. What changes on screen

Most operators are on ground ELMER calls average, and the model is changed
at the default setting, so **most operators will see almost nothing
change**. The +/-2% on average ground in section 1 rounds away in miles. The
changes are:

- **The rated ground reaches the ground wave** (Phase 3). This is the
  largest change, and it is plumbing, not physics. The reach map's ring and
  the band plan's skip-zone line use the QTH's rating when there is one. For
  a coastal QTH rated "sea", 80 m goes from 86 km (average ground, today) to
  720 km (sea, P.368): the whole difference between the two rows, and the
  ring is drawn eight times wider. A marsh QTH ("wet") goes from 86 to
  143 km on 80 m.
- **Sea paths double.** On 160 m, 494 to 834 km. On 80 m, 361 to 720 km. On
  40 m, 247 to 564 km. On 11 m at the lawful 12 W SSB, 88 to 168 km, and at
  4 W AM, 72 to 126 km. This only shows once the rated ground or a mixed
  path puts sea under the signal.
- **Wet ground and fresh water** grow by 10% to 30%. 40 m over wet ground
  goes from 81 to 91 km. If P.527's 0.01 S/m replaces ELMER's 0.02 for wet
  ground, 80 m settles at 115 km, not 143 km.
- **160 m and 80 m over land:** 132 to 135 km and 85 to 86 km on average
  ground; 98 to 95 km and 67 to 64 km on poor ground. **11 m over land:**
  unchanged to the kilometer, 21 km SSB and 11 km AM. The path tool's CB
  row stays "worth trying" at the distances it offers it.
- **The path tool** gets its ground-wave rows from `path_bands()`, so its
  "ground wave" verdicts follow the same numbers. With Phase 4 it works
  Millington between two rated ends. A 100 km path from a coastal station
  over the sea gains up to 39 dB against the all-land figure, and in words
  that is the difference between "does not carry" and "carries".
- **New words, one line each:**
  - which model answered: "the ITU's ground-wave method (P.368-10)" or
    "fitted approximation"
  - what ground it was worked over, and whether that was rated or assumed
  - the spread: "real ground varies from place to place by about 3.5 dB
    (P.368); on 80 m over average ground that is 73 to 101 km around the
    86 km figure"

  The spread is computed and not written in by hand, because it changes
  with the band and the ground. These are model figures, not measurements,
  and the words say "model". No sample size applies, and no confidence is
  implied beyond the 3.5 dB.
- **Nothing new on the study screens.** Model fallbacks go to the log and
  the doctor, not the page, apart from the one-word model name.

---

## Scope

**In:**
- vertical-polarization ground wave, 10 kHz to 30 MHz, both terminals at 0 m
- the eight named grounds
- the rated ground at the QTH
- Millington mixed paths where both ends are rated
- surface refractivity at the standard 315 N-units

**Out:**
- raised terminals above LFMF's 50 m (open question)
- terrain roughness and irregular terrain (P.368 assumes a smooth earth)
- VHF, which stays with `linkbudget.py`
- the noise model (P.372 atmospheric noise at sea is an open question)
- the skywave model
- editing any note in `data/notes/`

No new network fetch. The table is built from the program's own code, so
the *What leaves a unit* list does not change.

## Risks

- **The anchors.** The sea test in `tests/test_groundwave.py` ("MF coast
  station lands near 300 miles", 40 m 150, 20 m 100) will fail by design.
  Those numbers are the fit, not the physics. Replacing them is Scott's
  call, and the test's docstring has to say why the numbers moved.
- **Bigger sea numbers read as promises.** 834 km of 160 m ground wave at
  100 W is the physics over quiet salt water in a rural noise model. At
  night skywave arrives on top of it and fades against it. The page needs to
  say that the ground wave is a daytime figure over the sea.
- **Numerical edges.** These are the `|q| <= 0.1` branch, Newton failures,
  and underflow past -150 dB(uV/m). Each falls back and logs. Fixtures cover
  the edges: sand at 1.8 MHz, sea at 27 MHz, and 3,000 km.
- **Python 3.11 and scipy 1.10.** These are the bookworm floor. The
  prototype ran on 3.12 with scipy 1.18. It uses only `airy` with complex
  arguments and `wofz`, both long-standing, but CI must prove it on 3.11
  and 1.10.
- **Windows.** A table path through `pathlib`, and the same suite.

## Open questions for Scott

1. **The sea anchors.** Retire 300 / 150 / 100 miles in favor of P.368
   (513 / 348 / 221 under the same noise), or keep a service-range figure
   beside the physics and say which is which?
2. **The -1.76 dB charge.** Should a vertical on real ground be 0 dB against
   P.368's reference monopole? That is 8% more range on land. The ground's
   losses are already inside the attenuation function.
3. **The ground table.** Move wet ground to P.527's 0.01 S/m (80 m 143 to
   115 km) and ice to P.527's 1e-4? Keep "average" (0.005 / 13), which is
   not a P.527 curve but is the textbook default and sits between P.527's
   wet and medium dry?
4. **Noise at sea.** Keep the operator's site noise, or use P.372's quieter
   figure when the path is over water? At 160 m, quiet noise against rural
   is 1,107 km against 838 km.
5. **Terminal heights.** Worth carrying for a mobile whip or a vertical on a
   roof? LFMF moves the field by about 1 dB at 10 m on 40 m, which is under
   the 3.5 dB spread.
6. **Where the sea is on a path.** Is the elevation profile the path tool
   already fetches (SRTM, 0 m over ocean) a good enough guide to where the
   coast is, with the NHD rating at each end? Or should Millington wait for
   a coastline source, which would be a new fetch and a new line under
   *What leaves a unit*?

## Order of work, with the tests for each

Each phase is a commit, with CHANGELOG, and USER-GUIDE / README / DESIGN
where the screen changes. Tests are standalone scripts in the shape of
`tests/test_groundwave.py`: a docstring saying what is proved and why,
`check()`, `FAILS`, `sys.exit(1)`, and `import _isolate` before anything
from elmer.

**Phase 0: fixtures (no behavior change).**
- Add `tests/fixtures/p368_lfmf.json` with LFMF outputs across the section-1
  grid, plus sand, wet, fresh water, city and ice, plus the edge cases.
  Store provenance with them.
- Add the Figure 2 spot readings, marked "read by eye, 3 dB".
- Test: `test_groundwave_reference.py` checks the fixture's own sanity. It
  checks the 1 km value is 109.5 dB(uV/m) +/- 0.1 on sea, and that the field
  falls monotonically with distance.

**Phase 1: the method, beside the old one.**
- Add `groundwave.curve()` with lazy numpy and scipy, with nothing wired to
  the page yet.
- Tests:
  - within 0.1 dB of every fixture point above -60 dB(uV/m)
  - Figure 2 readings within 3 dB
  - horizontal polarization more than 40 dB under vertical at 10 km, 7 MHz,
    average ground
  - a root that fails to converge falls back and logs (forced by a stub)

**Phase 2: the table and the fallback.**
- Add `tools/build_groundwave_table.py` and the shipped table.
- Route `field_strength`, `useful_range_km` and `describe` through table,
  then curve, then fitted.
- Measure the timings on a Pi 4 and a Pi 5 and correct section 5.
- Tests:
  - table interpolation within 0.1 dB of `curve()`
  - with `sys.modules["scipy"] = None` and the table present, still P.368
    and `model == "P.368-10"`
  - with the table also absent, the fitted model, `model == "fitted"`, one
    warning logged, and a range still returned
  - the table is read once for many calls (count the opens)
  - the sea anchor checks are rewritten to P.368's numbers, with the reason
    in the docstring
- Screen: the model name in the reach-map note and the skip-zone line.

**Phase 3: the rated ground reaches the ground wave.**
- `reach_map`, `path_bands` and the band plan's skip-zone line take the
  QTH's rated `ground` (the eight-way kind, not the four-way pattern).
- Settle open question 3 and change `GROUND` to match.
- Tests:
  - seed a kept rating of "sea" in the isolated state and check the ring
    grows to the sea figure
  - no rating falls back to "average", and says "assumed"
  - a rating read back from the stored JSON works after the unit restarts
    (the days-later case the project rules name)
- Screen: the ground's name and "rated" or "assumed" beside the range.

**Phase 4: mixed paths.**
- Add Millington for the path tool between two rated ends, and the sea
  sections along the way if open question 6 allows.
- Tests:
  - the result is reciprocal: the same answer both ways
  - it equals the homogeneous curve when both sections are one ground
  - it matches the three land and sea worked cases in section 2 to 0.1 dB
  - Annex 2's formula is checked by hand on a two-section path

**Phase 5: the words.**
- Add the 3.5 dB spread line, and a DESIGN.md section on ground wave (there
  is none), folding in this plan's reasoning.
- Update USER-GUIDE figures via `tools/guideshots.py`, and the README
  "Since v1.0" section.
- Tests: the browser test for the reach-map note names the model and the
  ground, and the guide test finds its figures.
