# The antenna solver: working the wire out instead of looking it up

A plan for review, written 2026-09-27, before any code. It is here rather
than in DESIGN.md because DESIGN.md describes what ELMER *is*; this describes
what the antenna tab would become. Each phase folds into DESIGN.md as it
lands, and this file shrinks as that happens.

numpy and scipy came in on 2026-09-27 for numerical work of exactly this kind.
The question this plan answers is what an antenna solver would change for the
person at the Lab, the band plan and the build sheet, and whether it is worth
what it costs a Raspberry Pi.

Every number below says where it came from. Three kinds appear:

- **ELMER today**: what the current code returns, run on this machine.
- **Published**: a figure from a named document, with where to find it.
- **Prototype**: a throwaway thin-wire solver written in a scratch directory
  to measure costs and try the method. It is not a reference and nothing
  is checked against it. Where it agrees with a published figure, that is
  some evidence the method is sound. It is not in the repository.

---

## 1. What the current model does, and where it falls short

### What it is

- **Patterns** (`patterns.py`): a fixed element shape (the half-wave dipole's
  cos(π/2·cosθ)/sinθ, or the same shape turned vertical) times a two-ray
  ground factor |1 + Γ·e^(−j4πh·sinΔ)|. Γ is the Fresnel coefficient for the
  soil in `GROUNDS`. An inverted V and a loop get "half way to round"
  (`0.5 + 0.5·factor`). A Yagi gets a cosine lobe with its back held at
  `YAGI_FB_DB` = 20 dB. The terminated wires are the one closed-form model
  derived from the geometry: a travelling wave summed over straight legs,
  built once into a 1° × 5° table.
- **Feed impedance against height** (`antenna_advice.feedpoint_resistance`):
  73.13 Ω less the mutual resistance of the wire and its image, from Kraus's
  thin-dipole formula with a cosine integral written out by hand. The ground
  is perfect, and only resistance is computed; reactance is not.
- **SWR and bandwidth** (`patterns.swr_curve`): a series RLC,
  Z = R + jRQ(f/f₀ − f₀/f), with R and Q taken from the `ANTENNA_Q` table
  (dipole: Q 13, R 73 Ω). R does not change with height. The conductor
  scales Q.
- **Gain and build numbers** (`lab.js ANTENNAS`, `yagiGain`, `radialZ`):
  typed figures and fits. A Yagi's gain is interpolated from its boom length.
  The ground plane's feed is a curve through 36, 50 and 72 Ω. The inverted V
  is a curve through 73, 50 and 40 Ω (`v_free_space_ohms`).

This model is honest about the shape and the trend, and it runs on nothing.
It falls short wherever the shape of the current matters: at low heights,
where the antenna couples to its own image and to the soil; in a parasitic
array; at a junction of wires; and wherever the page prints reactance or SWR.

### Measured shortfalls

| What | ELMER today | Reference | Gap | Source of reference |
|---|---|---|---|---|
| Ground plane, 4 horizontal radials, feed R | 36 Ω (`radialZ(0)`) | 21.38 − j0.66 Ω | +68 % | Cebik, *On Ground Planes, Part 3: Planes in Space* (NEC, free space), antentop.org/w4rnl.001/gp3.html. Prototype: 21.7 Ω |
| Ground plane, radials drooped 45° | 50 Ω | 48.33 + j0.51 Ω | +3 % | same |
| 3-el 20 m Yagi, "medium boom" (19.84 ft), free-space gain | 7.2 dBi (`yagiGain`, boom 0.286 λ) | 7.78 dBi | −0.6 dB | Cebik, *Build a 3-Element Yagi Part 1*, NEC-4, 14.175 MHz, 1 in elements, antenna2.github.io/cebik/content/yagi/3lyg1.html |
| same, "long boom" (22.55 ft) | 7.6 dBi | 8.11 dBi | −0.5 dB | same |
| same, "short boom" (15.08 ft) | 6.1 dBi (spacing penalty 0.5 dB) | 7.13 dBi | −1.0 dB | same |
| same three, front-to-back | 20 dB, fixed | 27.3 / 35.5 / 41.4 dB at design frequency | −7 to −21 dB | same |
| same three, driven-element feed | 22 Ω | 25.7 − j0.9 / 27.0 + j0.5 / 27.5 + j0.0 Ω | −4 to −5.5 Ω | same |
| Dipole, 75 m, 35 ft up (0.139 λ), feed R | 38.6 Ω (perfect ground) | "close to 50 Ω over the worst soil to nearly 70 Ω over the best" | −11 to −31 Ω | Cebik, *Basic NVIS Antennas: Dipoles, Loops, and Vs*, NEC-4 Sommerfeld, #14 wire, antenna2.github.io/cebik/content/wire/nvis2.pdf |
| Dipole, 40 m, height of greatest zenith gain over average ground | 0.22 λ (`height_gains`, overhead peak) | about 0.195 λ | +0.025 λ (3.4 ft) | same, 40 m section |
| Quarter-wave monopole over perfect ground, peak gain | 8.15 dBi (`height_gains` +6.0 dB over a dipole) | 5.16 dBi (directivity 3.28) | +3.0 dB | Textbook: the monopole's image makes a half-wave dipole radiating into half the sphere, so 2 × 1.64. Balanis, *Antenna Theory*, ch. 4, image theory (section number not checked). Prototype: 5.13 dBi |
| Horizontal dipole at 0.1 λ over **perfect** ground, peak gain | 3.55 dBi | 8.8 dBi (prototype, lossless) | −5.3 dB | The current model holds the current fixed as height changes. Fed with fixed power, the current rises as R falls to 22 Ω. Over real ground most of that comes back as ground loss, and that figure needs the Sommerfeld phase to measure. |
| same at 0.35 λ | 8.15 dBi | 6.89 dBi (prototype) | +1.3 dB | same cause, the other way: R is 96 Ω there |
| Dipole SWR at the "50 Ω match" height (0.16 λ) | 1.0 in the heights table, 1.46 in the SWR curve beside it | 2.1 (prototype: 49.6 + j37.5 Ω for a wire cut to free-space resonance) | The same page gives two answers, and neither accounts for reactance | Prototype |
| 2:1 bandwidth, #14 dipole, free space | 532 / 268 / 141 kHz on 14.2 / 7.15 / 3.75 MHz (Q 13 on every band) | 653 / 307 / 150 kHz (Q 10.5 / 11.4 / 12.3) | −19 % / −13 % / −6 % | Prototype. Q grows as the wire gets thinner in wavelengths, and the table has one Q for all bands. |
| Inverted V, free-space R at resonance, legs 45° and 60° below horizontal | 49.9 Ω, 39.8 Ω | 41.2 Ω, 22.6 Ω (prototype) | +8.7, +17.2 Ω | **Not verified against a published figure.** Cebik's *The Multi-Band Inverted-V from Many Angles* has the tables, but only as images, which could not be read. |
| Lab dipole, 468/f of #14 wire, 14.2 MHz, free space | "73 Ω" | 67.5 − j31.1 Ω, SWR 1.8 (prototype; #14 resonates at 478/f in free space) | reactance not shown | Prototype. 468/f includes end effects and nearby ground, so the free-space figure overstates the error. The real-ground figure needs the Sommerfeld phase. |

What holds up: over perfect ground the resistance-against-height curve is
right. The prototype gives 21.8 Ω at 0.1 λ where ELMER gives 21.7, and a
peak of 96.4 Ω where ELMER gives 98.0. Cebik's NEC-4 figures put the
all-soils convergence at about 75 Ω near 0.205 λ, where ELMER gives 69 Ω.
Elevation angles agree to a degree. The takeoff geometry, the reach map and
the hop arithmetic are not in question here.

Two of these do not need a solver. The +3.0 dB on verticals is the element
factor counted as a dipole when it is a monopole: one line of `patterns.py`,
shown on the band plan's "what this height buys" (`bandplan.js` line 1548).
The two SWR answers for one height is one page contradicting itself. Both
belong in phase 1 below whether or not the solver is built.

---

## 2. The method

**A thin-wire method-of-moments solver in the mixed-potential form of the
electric-field integral equation: triangle basis functions, Galerkin testing,
the reduced kernel.** This is the Pocklington family, not Hallén, and it is
not NEC-2's own formulation.

Why this form:

- **Junctions come free.** A triangle basis spans two segments that meet at
  a node, so a ground plane's five wires or an inverted V's apex is one more
  basis function per extra wire. That is Kirchhoff's current law, exactly.
  NEC-2's three-term expansion (constant, sine, cosine on each segment,
  matched at segment centers: NEC-2 Manual Part I) handles junctions with
  special rules. Hallén's form has a constant of integration for every
  straight wire and becomes awkward at bends and junctions.
- **Small enough to own.** The prototype is about 200 lines of numpy. The
  fill is two matrix products per potential. The self-term uses the
  standard singularity subtraction: the 1/R part is integrated in closed
  form (asinh) and the rest by 6-point Gauss–Legendre.
- **Evidence it works.** On the published cases it reproduced NEC-2's
  Example 2 (a 0.5 m wire of radius 10⁻⁵ m) to within 4 %: 77.9 + j43.8 Ω
  at 299.8 MHz against NEC's 80.55 + j45.71 Ω, 45.5 − j261.9 against
  47.14 − j272.37 at 250 MHz, and 25.6 − j608 against 26.58 − j632.06 at
  200 MHz. On Cebik's NEC-4 Yagis it gave 8.11 dBi, 25.9 − j3.1 Ω and
  28.5 dB F/B for the long boom (published: 8.11, 25.71 − j0.93, 27.31), and
  7.81 dBi, 27.05 − j0.43 Ω and 34.0 dB for the medium boom (7.78,
  27.02 + j0.50, 35.50). The short boom's gain agreed (7.14 against 7.13 dBi)
  but its reactance came out j28 Ω off. That case has to be understood
  before phase 2 closes.

**Segment rules**, taken from the NEC-2 Manual Part III, section II, and
enforced by the geometry builder rather than left to the operator:

- Segment length under 0.1 λ, and 0.05 λ within a quarter wave of a feed,
  a junction or a load. Never under 10⁻³ λ.
- Segment length at least 8 times the wire radius. Part III gives that
  limit for the thin-wire kernel at better than 1 % error. The reduced
  kernel used here is the same approximation, so the same limit holds.
  Thick elements get fewer, longer segments, not an extended kernel.
- Adjacent segments differ in length by no more than 2:1 at junctions.
  That rule is ELMER's own, not Part III's.
- Odd counts on parasitic elements and even counts on a driven element, so
  a node falls at the feed.

For the antennas in scope, that is 21 to 41 segments a wire and 40 to 130
unknowns a model.

**Ground**, in three grades:

1. *Perfect*: an exact image (Part III: "results in solution accuracy
   comparable to that for a free-space model").
2. *Real ground, reflection-coefficient approximation* (NEC-2's `GN 0`):
   the image scaled by the Fresnel coefficients `patterns.fresnel` already
   computes. Part III says it "should not be used for structures close to
   the ground" and is reasonable at "several tenths of a wavelength" and
   above. So the solver's impedance over real ground is only reported from
   0.2 λ up. Below that, the page says the figure is the perfect-ground one
   and why.
3. *Real ground, Sommerfeld*: the exact half-space fields, interpolated from
   a grid built once per soil and frequency, the way NEC-2's SOMNEC does.
   This is the phase where scipy earns its place (`scipy.special` Bessel
   and Hankel functions, `scipy.integrate.quad`), imported inside the
   function that builds the grid. It is the only grade that gets NVIS
   heights right, and NVIS heights are where the current model is furthest
   off. Part III puts the cost at "about four times longer than for free
   space" for the fill.

The far field over real ground always uses the Fresnel coefficients, as
`patterns.py` does now. For the space wave over a flat earth that is exact.

**Soil** comes from `GROUNDS` (average, poor, good, sea), or from
`siteground` when the operator has rated their own ground. That already
gives εr and σ; the solver needs nothing more.

**Losses and loads**: wire resistance per segment from `conductors.py`
(skin depth, from the conductor's σ), which gives efficiency on the fence
wire. Lumped R, L and C at a node: the TEFV's 600 Ω resistor, a whip's
loading coil, a trap. **Source**: a delta-gap voltage at a node.

**Outputs**, all from one solve per frequency:

- feed impedance R + jX
- the current on every segment, magnitude and phase
- the far field on the same 1° elevation × 5° azimuth grid the
  travelling-wave table uses, in dBi, split into horizontal and vertical
  polarization
- peak gain, takeoff angle, front-to-back and front-to-rear
- efficiency, once losses are in
- an SWR sweep against 50 Ω (or whatever the feed is)

**What stays analytic**: the ionosphere, hop geometry, the reach map's
arithmetic (it reads the solver's table exactly as it reads the
travelling-wave one now), the takeoff-angle formula in words, the power
notes, and the short-whip efficiency. The mobile whip stays analytic
because its loss is the vehicle and the coil, not the wire. The terminated
wires stay on their closed form. Part III warns that the reflection-coefficient
ground "should not be used for structures having a large horizontal extent
over the ground such as some traveling-wave antennas", and a 500 ft vee is
15 λ on 10 m. The analytic model also stays as the fallback for everything
(section 4).

---

## 3. The published figures it is checked against

Each check is a standalone test with the reference typed into the test and
the source in its docstring. No test fetches anything.

| # | Case | Reference figure | Tolerance | Source | Verified? |
|---|---|---|---|---|---|
| 1 | 0.5 m wire, radius 10⁻⁵ m, 8 segments, at 200 / 250 / 300 MHz | 26.58 − j632.06; 47.14 − j272.37; 80.55 + j45.71 Ω | R ±5 %, X ±5 % or ±5 Ω, whichever is larger | NEC-2 Manual Part III, Example 2 (Burke & Poggio, LLNL, Jan 1981), www.nec2.org/other/nec2prt3.pdf, p. 86 of the WDBN edition | Yes: read from the manual's printed output |
| 2 | 0.5 m wire, radius 0.001 m, 7 segments, 299.8 MHz | 82.70 + j46.31 Ω | as #1 | Part III, Example 1 | Yes. Seven segments put the source mid-segment, so ELMER's run uses 8 and the test says so. |
| 3 | Power conservation | average power gain 1.00 in free space, 2.00 over perfect ground (NEC gets 2.028 with 10° steps) | ±2 % on a 2° grid | Part III, Examples 1–4 commentary | Yes |
| 4 | Thin half-wave dipole | directivity 1.64 (2.15 dBi); induced-EMF impedance 73.1 + j42.5 Ω | gain ±0.05 dB. The impedance is shown, not tested: 73 + j42.5 assumes a sinusoidal current that MoM does not. | Balanis, *Antenna Theory*, 3rd/4th ed., §4.6; Kraus, *Antennas* | Figures standard. Equation and section numbers from memory, not checked. |
| 5 | λ/4 monopole on perfect ground | 36.5 Ω at exact λ/4; 5.16 dBi | R ±2 Ω at resonance; gain ±0.1 dB | Half of #4 by image theory | Standard. Not checked against a page. |
| 6 | Horizontal λ/2 over perfect ground, R against height 0.05–1.0 λ | ELMER's own Kraus curve, which is right over perfect ground | ±3 Ω | Kraus mutual-impedance formula (`_mutual_r`) | The formula is ELMER's. Kraus chapter number not checked. |
| 7 | Ground plane, 4 radials, free space: flat and 45° | 21.38 − j0.66; 48.33 + j0.51 Ω | ±2 Ω | Cebik, *On Ground Planes Part 3*, antentop.org/w4rnl.001/gp3.html | Yes, but read through a web summary. The element sizes (2 in main element, 0.25 in radials) were given; the frequency is inferred from 33.25 ft. Confirm against the page. |
| 8 | Three 3-el 20 m Yagis at 14.175 MHz, 1 in elements | gain 8.11 / 7.78 / 7.13 dBi; F/B 27.31 / 35.50 / 41.35 dB; Z 25.71 − j0.93 / 27.02 + j0.50 / 27.46 + j0.01 Ω | gain ±0.15 dB; Z ±2 Ω; F/B ±3 dB where it is under 30 dB, and "over 30 dB" above that, because a deep rear null moves by several dB with segmentation (prototype: 29.4 → 35.0 dB going from 11 to 41 segments an element) | Cebik, *Build a 3-Element Yagi Part 1*, NEC-4, antenna2.github.io/cebik/content/yagi/3lyg1.html | Read through a web summary, which **mislabeled the 15 m table as 20 m on the first reading**. Retype the dimensions from the page before the test is written. |
| 9 | 40 m dipole, #14, 0.4806 λ, over average ground (εr 13, σ 5 mS/m), 0.075–0.255 λ | greatest zenith gain near 0.195 λ; feed R converging on about 75 Ω (±j10) near 0.205 λ over every soil | ±0.02 λ; ±5 Ω | Cebik, *Basic NVIS Antennas: Dipoles, Loops, and Vs*, NEC-4 Sommerfeld, antenna2.github.io/cebik/content/wire/nvis2.pdf | Yes for the sentences quoted. **The table values (Table 1) are images and were not read**; they are wanted for phase 3. |
| 10 | 75 m dipole at 35 ft | 50 Ω (worst soil) to 70 Ω (best) | ±5 Ω | same, 75 m section | Yes, as a sentence |
| 11 | NEC-2 Example 3: vertical wire from 2 to 7 m, radius 0.3 m, 30 MHz; perfect ground and εr 6, σ 1 mS/m | 106.44 + j9.91 Ω; 111.12 + j11.01 Ω; average gain 2.028, 0.721 | ±5 % | Part III, Example 3 | Read from the manual. The model uses NEC's extended kernel on a very thick wire (segment/radius ≈ 1.9), so the reduced kernel may not meet ±5 %. It is a known-hard case, recorded rather than required. |

**Not verified and not used as checks until they are:** the ARRL Antenna
Book's feed-resistance-against-height figure over real ground (chapter and
figure number not seen); the free-space R of an inverted V against its angle
(Cebik's tables are images); the EFHW's end impedance, which published
sources give only as a wide range and which depends on the counterpoise; and
the peak gain of a ground-mounted quarter wave over average ground. Where no
check exists, the page labels the figure as a model and says it has not been
checked.

---

## 4. When numpy or scipy is missing

A unit updated with a plain `git pull` has the new code and none of the new
packages. `--doctor` already says so. The page has to keep working.

- **`elmer/wiresolver.py`** (name open) imports nothing numerical at module
  level. `available()` asks `importlib.util.find_spec("numpy")` once and
  caches the answer. `solve()` imports numpy inside itself. The Sommerfeld
  grid builder imports scipy inside itself, and only that function does.
  Neither app startup nor `patterns.py` ever imports either.
- **If numpy is missing**, the analytic model answers every request as it
  does today. One `log.warning("no numpy (%s): the antenna tab uses the
  analytic model", exc)` per process, not per request.
- **If scipy is missing**, the solver runs with perfect or
  reflection-coefficient ground and never Sommerfeld. Below 0.2 λ over real
  ground the page falls back to the analytic figure and says why. One
  warning line, as above.
- **If a solve fails** (a singular matrix from a degenerate geometry,
  `numpy.linalg.LinAlgError`, or a model over the size cap), the route
  catches that narrow exception, calls `log.exception` with the antenna's
  key, and returns the analytic answer. Nothing on the study screens.
- **Every answer says which model gave it.** The route's JSON carries
  `"model": "solver" | "analytic"`, the ground grade used, the segment
  count, and a one-line reason when it fell back. The page prints it under
  the numbers: *worked out by the wire solver: 61 segments, free space*,
  or *the textbook model: numpy is not installed on this unit*. The
  dashboard's log tail shows why.
- A test runs the app with `sys.modules["numpy"] = None` set before
  `import elmer`, and checks that `/api/pattern` and the build sheet still
  answer, with `"model": "analytic"`.

---

## 5. What it costs on a Raspberry Pi

**Measured on this machine**: Intel Core Ultra 9 275HX, numpy 2.5.3 with
OpenBLAS 0.3.34, Python 3.12. Medians.

| Dense complex solve, N unknowns | 1 BLAS thread | 4 threads | Matrix memory |
|---|---|---|---|
| 100 | 0.09 ms | 1.2 ms | 0.16 MB |
| 200 | 0.51 ms | 4.3 ms | 0.64 MB |
| 400 | 4.6 ms | 6.0 ms | 2.6 MB |
| 800 | 26 ms | 13 ms | 10 MB |
| 1,600 | 174 ms | 70 ms | 41 MB |

Below about 500 unknowns, extra threads make it slower: they cost more to
start than they save. The solver should run single-threaded
(`threadpoolctl` is not a dependency, so `OPENBLAS_NUM_THREADS=1` is set at
launch on the Pi, or the solver works within that).

**Filling the matrix costs more than solving it.** The prototype over
perfect ground: 12 ms at 40 segments, 78 ms at 80, 279 ms at 160 and 926 ms
at 320 (plus 96 and 175 ms to solve at the last two). A 3-element Yagi at 61
unknowns took 27–30 ms in all. The prototype puts 6 Gauss points on every
segment pair and builds every interaction at once, so it holds several
(6·segments)² complex arrays at a time: about 60 MB at 160 segments and about
240 MB at 320. Production code fills in row blocks, and uses 2 points for
pairs more than a few segments apart. The target is a third of the prototype's
fill time and a peak under 32 MB. That is a target, not a measurement.

**Scaling to a Pi is an estimate, and it is labeled as one.** No Pi has run
this yet. The assumption is that a Pi 4 (Cortex-A72, 1.5 GHz) is 10 to 25
times slower than this machine single-threaded for dense complex arithmetic,
and a Pi 5 (Cortex-A76, 2.4 GHz) is 4 to 10 times slower. On that assumption,
one frequency takes:

| Model | Here | Pi 4 (estimate) | Pi 5 (estimate) |
|---|---|---|---|
| Dipole, 41 segments, perfect ground | 12 ms | 0.12–0.3 s | 0.05–0.12 s |
| 3-el Yagi, 61 unknowns, free space | 30 ms | 0.3–0.75 s | 0.12–0.3 s |
| Ground plane, 100 unknowns | about 60 ms (not measured separately) | 0.6–1.5 s | 0.25–0.6 s |
| Sommerfeld fill (×4 the fill, per Part III) | — | 0.5–6 s | 0.2–2.5 s |
| Sommerfeld grid, once per soil and frequency | not built yet | unknown | unknown |

Phase 0 measures these on a real Pi 4 and Pi 5 before any segment count is
fixed.

**What that means for the page**, under the Pi budget rule (compute only what
the page asked for; read stores once per change):

- **One solve per change, never one per slider step.** The analytic answer
  comes back from `/api/pattern` at once, as it does today. The page then
  asks a separate `/api/antenna/solve` for the antenna it is showing, after
  the slider has been still for 400 ms. The solver's answer replaces the
  analytic one when it arrives, with its label.
- **The SWR sweep is not 121 solves.** The solver solves at the design
  frequency and at ±3 %. From those three it gets R, the resonant frequency
  and a measured Q, and hands them to the existing `swr_curve`. So the
  series-RLC curve keeps drawing, but with the solver's R, f₀ and Q instead
  of the table's. That is 3 solves, about 1–2 s on a Pi 4. A full sweep
  (21 points) runs only when the operator asks for it.
- **Cache** keyed on (kind, dimensions rounded to 0.1 ft, height to 0.5 ft,
  droop to 1°, conductor, frequency to 1 kHz, ground grade and soil):
  an in-memory LRU of 32 entries, like `_TRAVELLING_TABLES`. The pattern
  table on the 1° × 5° grid is part of the entry, so the reach map and the
  DX bearings read it without solving again.
- **No precomputing.** Nothing is solved for antennas, bands or heights
  nobody has asked about, and nothing runs in the background at startup.
  The Sommerfeld grid is built when the first real-ground solve below 0.2 λ
  needs it. It is kept per (soil, frequency) in memory and, if phase 0 shows
  it is slow, on disk under `paths.STATE`.
- **A cap.** 400 unknowns a model. Past that, the analytic model answers
  and the log says why. Nothing in scope comes near it.

---

## 6. What changes on screen

Model figures say they are models. The solver's figures carry *modeled*, the
segment count and the ground grade, and, where a published check covers the
case, how closely the solver agreed with it: *within 0.05 dB and 2 Ω of the
NEC-4 figures for three published 20 m Yagis*. Measured figures, such as
Virginia RACES' whip-pair results, stay labeled as measured, and their sample
stays beside them. Nothing the solver says is presented as a measurement.

| Where | Today | With the solver | How much it moves |
|---|---|---|---|
| Lab, dipole feed | "73 Ω" | R + jX at the height and length entered | e.g. 67.5 − j31 Ω in free space for 468/f of #14 (prototype). Over ground it depends on the height. |
| Lab, SWR across the band | min 1.46 at every height; Q 13 on every band | the solver's R, f₀ and Q | 2:1 width +23 % on 20 m, +15 % on 40 m, +6 % on 80 m for #14 in free space (prototype). The curve's minimum follows the height. |
| Lab and build sheet, "Heights where the feed matches" | R over perfect ground; SWR from R alone | R + jX; SWR including X; real ground from 0.2 λ (phase 2) and below it (phase 3) | 0.16 λ: SWR 1.0 becomes about 2.1 for a wire cut to free-space resonance (prototype). 75 m at 35 ft: 38.6 Ω becomes 50–70 Ω depending on soil (Cebik). |
| Lab, Yagi | boom-length gain; F/B 20 dB; 22 Ω | gain, F/B and Z for the elements the Lab prints, across the band | gain +0.5 to +1.0 dB (Cebik's three designs); F/B 27–41 dB at their design frequency. The Lab's own 3-element rows (0.20 λ spacing, 3/4 in tubing) give 36 − j3 Ω, 8.1 dBi, and F/B 14.7 dB at 14.0 MHz, 18.5 at 14.2 and 17.8 at 14.35 (prototype) |
| Lab, ground plane | `radialZ`: 36 / 50 / 72 Ω | solver R at the droop set | flat radials 36 → about 22 Ω |
| Lab, inverted V | 56 Ω at the default 35° droop | solver R | about −3 Ω at 35°, −9 Ω at 45° (prototype, unverified) |
| Band plan, "what this height buys" (dB against a free-space dipole) | +6.0 dB over perfect ground at every height; verticals 3 dB high | fixed-power gain at the height and ground | verticals −3.0 dB (phase 1, no solver). Horizontal wires within 1.3 dB above 0.25 λ; at NVIS heights, whatever Sommerfeld says (phase 3). |
| Build sheet | build rows, gain, "73 Ω" | the same build rows, plus one line: *modeled resonance of this length at this height: 14.05 MHz* | The cut lengths do not change (see risks). |

**New on screen:**

- **Current along the wire**: a strip under the antenna drawing, one bar
  per segment, magnitude by height and phase by shade. It shows why an
  inverted V behaves lower than its apex, and why a reflector is a
  reflector: its current runs behind the driven element's in phase.
- **R and X against frequency**: a small plot beside the SWR curve, from
  the same three solves. The sign of X is what tells somebody which way to
  cut. The VNA page already teaches that, and the Lab would then agree
  with it.
- **Front-to-back across the band** for a Yagi, because a single F/B
  figure hides that it holds only in the middle of the band.
- **Later, and only when asked**: a VNA sweep the operator kept
  (`sweeps.keep`) drawn over the solver's curve for the same antenna. That
  would be a measurement beside a model, each labeled as what it is.

---

## Scope: which antennas first

1. **Dipole** (flat and sloping) and **inverted V**: the most common, the
   worst-served at low height, and the ones the heights table is about.
2. **Quarter-wave vertical over radials** and the **ground plane**, flat
   and drooped: the +3 dB and the 36-against-22 Ω.
3. **Yagi**, 2 to 6 elements, from the Lab's own element rows.
4. **Full-wave loop** and the **EFHW** with a stated counterpoise.

Later or never: bowtie (a solid triangle as a wire outline), J-pole (its
stub is a transmission line), 5/8 wave (a base coil, phase 2 loads), whips
and the screwdriver (the loss is not in the wire), and the terminated wires
(analytic by design; see section 2).

---

## Phases, each with its tests

**Phase 0: prove the costs on a Pi.** The prototype's benchmark runs on a
Pi 4 and a Pi 5, with the matrix filled in row blocks. The output is a table
that replaces the estimates in section 5. No ELMER code changes.
*Test*: none. It is a measurement, and it is recorded in this file.

**Phase 1: fix what needs no solver.** The monopole's element factor
(−3.0 dB on verticals). One SWR answer for one height: the heights table
and the SWR curve read the same R. `radialZ` is refit through Cebik's
21.4 Ω flat and 48.3 Ω at 45°, and 72 Ω at 90°.
*Tests*: `test_patterns_vertical_gain.py`: a quarter wave over perfect
ground reads 5.16 dBi ±0.1. `test_heights_one_answer.py`: at every landmark
height, the table's SWR equals the curve's minimum.

**Phase 2: the solver, free space and perfect ground and
reflection-coefficient ground, with the fallback.** `wiresolver.py`, the
geometry builders for the scope list, `/api/antenna/solve`, the model label
on the Lab.
*Tests*: `test_wiresolver_nec2.py` (checks 1–3, 11 recorded);
`test_wiresolver_yagi.py` (check 8); `test_wiresolver_groundplane.py`
(check 7); `test_wiresolver_image.py` (checks 5–6); `test_wiresolver_rules.py`
(the segment rules refuse a model that breaks them, and the 400-unknown cap
falls back); `test_wiresolver_fallback.py` (numpy blocked: every antenna
route answers with `"model": "analytic"` and one log line);
`test_wiresolver_cache.py` (a second identical request does not solve, and
a height change solves once). Each imports `_isolate` first and fetches
nothing. The Lab's browser test gains a check that the model label is on
the page.

**Phase 3: Sommerfeld ground.** The grid builder, with scipy imported
inside it; real-ground impedance below 0.2 λ; the band plan's height gains
from the solver.
*Tests*: `test_wiresolver_sommerfeld.py` (checks 9–10, and check 11's
finite-ground figures); `test_wiresolver_noscipy.py` (scipy blocked: below
0.2 λ the analytic figure answers, with its reason).

**Phase 4: loads and losses.** Conductor loss from `conductors.py`, lumped
loads, efficiency; the loop and the EFHW; the current strip and the R/X
plot.
*Tests*: power budget (input = radiated + dissipated, ±1 %); a lossy dipole
of fence wire shows the efficiency drop `conductors.py` already describes.

Each phase updates USER-GUIDE.md and its figures, README's "Since v1.0" and
"What does not work yet", DESIGN.md's Lab section and CHANGELOG.md in the
same commit. Nothing leaves a unit, so the *What leaves a unit* list does
not change.

---

## Risks and open questions for Scott

- **468/f.** The pools teach it, and the build sheet uses it. The prototype
  puts #14's free-space resonance at 478/f. Over real ground and with
  insulators the answer differs, and it is not known yet by how much. The
  proposal keeps 468/f as the cut length and adds the modeled resonance as
  a line beside it, rather than changing the build. Is that right?
- **A second answer on the page.** For a second or so on a Pi 4 the page
  shows the analytic figure, then the solver's. Is a visible swap
  acceptable, or should the numbers wait, with *working it out* in their
  place?
- **The Yagi's F/B at 20 dB** was a deliberate "no beam measures nothing".
  The solver will print 27–41 dB at the design frequency for good designs.
  Do we print what the model says, or cap it at 30 dB as "over 30 dB", since
  a real rear null does not survive a mast, a feedline and a neighbor's
  gutter?
- **Real-ground impedance below 0.2 λ is phase 3**, and that is exactly
  where NVIS operators hang wire. Phase 2 will be honest that it cannot
  answer there. Is it worth shipping before phase 3?
- **The prototype's short-boom Yagi reactance** is j28 Ω off Cebik's. Until
  that is understood, check 8 covers the long and medium booms only.
- **The Sommerfeld grid's cost on a Pi is unknown.** If it is minutes, it is
  built only on request, and the page says it is working.
- **Name**: `wiresolver.py`, or `nec.py`? It is not NEC, and the name
  should not suggest it is.
- **Pinning BLAS to one thread** on the Pi touches the launcher. Acceptable?
