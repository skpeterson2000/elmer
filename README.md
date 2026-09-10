# ELMER

A study assistant, progress tracker and game for radio theory, built around the
current US license question pools — amateur (NCVEC) and commercial (FCC) — with
a live propagation dashboard and a lab of the calculators the exams actually
test.

It also runs a **tournament**: the same questions as a race, for one person
against practice opponents, for a table of eight joining by QR code from their
own phones, or for a hall of up to a hundred tables scored against each other
from one additional Raspberry Pi.

Runs as a small local web app. Open it on the Pi itself, or from a phone or
laptop on the same network.

```
git clone https://github.com/skpeterson2000/elmer.git
cd elmer
pip install -r requirements.txt
./elmer.py             # serve; open it from anywhere on the network
./elmer.py --kiosk     # serve, and open full screen on this machine
#   ELMER is on http://192.168.1.5:5000
```

The pools ship built, so it runs straight from a clone — no build step. The
only dependencies are Flask, Pillow and reportlab; everything else, including
the QR encoder, is the standard library.


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

**Forgetting something costs a setback, not a restart.** A lapse used to zero
the interval, throwing away every day of spacing a card had earned and sending
a question known at thirty days back to the bottom of the ladder beside one
never seen. Maintaining knowledge is far cheaper than acquiring it and the
schedule now says so: a lapse keeps a share of the spacing as a record of how
well the card was known, brings it back within ten minutes, and resumes near
where it was on the next correct answer. A card at thirty days that slips
recovers to about ten; a brand-new card answered wrongly still starts at one.

**The next date is jittered.** With fixed intervals everything answered in one
sitting comes due in one sitting for ever, which is why a day's load used to
look like a copy of the day before. Sixty mature cards answered together used
to land on a single day; they now spread across eight, and a long-interval
batch across forty or more. The spread grows with the interval, and short
intervals get at least a day of scatter once there is room for it, because that
is where the daily volume actually comes from. Variable schedules are also the
better arrangement for retention, and for wanting to come back.

**The day can be finished.** Drill budgets learning and remembering apart,
because they cost differently: meeting a question for the first time buys a
steep curve and several sightings this week, while maintaining one already
known is a single glance at a long interval. Twenty new and a hundred and
twenty reviews are separate allowances rather than competing for one pot, and
when both are spent ELMER says what was done and that tomorrow is when the rest
will do the most good. Only drill is rationed — weak spots, new, lapses and
contest are deliberate choices to work on something specific, and somebody who
wants to keep going should not have to argue with the program about it.

**A rest day is earned for every seven studied.** Missing a single day spends
one if the bank holds any, and the streak carries on; missing two ends it
regardless, because the bank covers a day off rather than a lapse in the habit.
A three-day streak still resets — the slack has to be earned before it can be
spent. A streak that one missed evening destroys stops being a reason to study
and becomes a reason to dread missing one.

### Where a newcomer starts

Somebody who has just downloaded this and holds no license is looking at 2,475
questions across six pools, most of which are not their exam and three of which
are not amateur radio at all. That is not a library, it is a wall. So the
amateur ladder starts at Technician and opens as there is reason to.

A license class opens everything up to it and the pool above — everything at or
below, not a two-rung window, because this program is named after the people
who run Technician classes and a General reviewing the basics needs the lower
pools. The class can be typed in as well as looked up, since callook serves the
FCC ULS and nothing else, and a Canadian or British operator has a perfectly
good callsign that resolves to nothing.

Taking Technician to Elmer opens General with no callsign at all. The rank
ladder already demands exam evidence at that tier, so it is demonstrated
mastery rather than an assertion, and it is the honest route for somebody
studying hard before they have ever sat an exam.

And the gate can simply be switched off from the dashboard. Its purpose is to
keep a first evening from being overwhelming, not to rule on what a licensed
operator may read — so a closed pool is shown rather than hidden, dimmed, with
a sentence saying what opens it and a button that opens everything. The
commercial pools are not gated on an amateur license at all: an Extra ticket
says nothing whatever about readiness for a GROL.

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

- **Privileges are law**, and they come from your actual license. Enter your
  callsign once and ELMER reads the FCC record through callook.info: license
  class, grant and expiry dates, and the grid square. The band plan then shows
  *your* privileges rather than a class you picked from a list, and the page
  tells you how long the license has left — flagging the last 90 days, and the
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

  Convention and law do not share their edges, so each segment is answered with
  three states rather than two, and the reason is written beside the row. The
  IARU Region 2 plan puts SSB on 20 m from 14.112 while 97.305 permits no phone
  below 14.150, so an Extra is told **14.150–14.230** and, in words, *"no license
  may use phone below 14.150 MHz"*.

  That last distinction is the one worth having. Two quite different rules
  produce the same shape on the page: below the emission sub-band **nobody** may
  use that mode however far they upgrade, while above it the license class is
  the only thing in the way. So they are said separately. A General on the same
  row reads *"no license may use phone below 14.150 MHz; from there to 14.225 it
  needs Advanced or Extra"* — one half is physics of the rulebook, the other half
  is a reason to study.
- **Regional plans come from your frequency coordinator.** Minnesota is wired
  up: 80 coordinated segments across 6 m, 2 m, 1.25 m, 70 cm and 23 cm, fetched
  from the Minnesota Repeater Council and cached for 30 days. Coordinator plans
  are somebody else's work, so they are fetched rather than bundled; adding
  another state means adding one entry with a parser to
  `elmer/regional.py`.

The bar is a way in rather than only a picture. Hovering a segment says what
happens there and whether the band is open right now, from the same space
weather feed the dashboard uses. Clicking one keeps that on screen and offers to
carry the frequency into the antenna designer — with the *intention* attached,
read from what the segment is for: a repeater segment means local FM, 40 m means
regional, 20 m means DX.

What arrives at the other end is not a blank calculator. **`/lab?f=…&use=…`**
answers the question a new licensee is actually asking — what should I put up,
how high, which way round — and then sets the calculator to that answer, so the
dimensions below are the dimensions of the thing being recommended:

- **146.52 MHz** → *"146.52 MHz is FM national simplex calling on 2 m. Taking it
  that you want local FM — change that above if not."* Then a vertical, 20 ft,
  because *FM is vertically polarised and a horizontal antenna hearing a vertical
  one loses around 20 dB.*
- **144.200 MHz** → a **horizontal** beam instead, because that is SSB calling and
  weak-signal work on VHF is horizontal by convention. Same band, opposite
  polarisation, and getting it backwards is the 20 dB that explains why the
  vertical on the roof hears nothing there while the repeaters boom in.
- **145.900 MHz** → a small beam you can point and twist, mounted low. A satellite
  is overhead, and a fixed vertical has its null exactly there.
- **7.200 MHz, regional** → an inverted-V at 25 ft, deliberately low. *The one
  case where a low antenna is the right answer rather than a compromise, worth
  knowing before somebody talks you into a tower.*
- **14.200 MHz, DX** → a dipole at half a wavelength, 35 ft, hung broadside to
  where you want to work, with a 1:1 choke balun at the feedpoint.

Each comes with what usually goes wrong — the ends of a dipole are the
high-voltage points, an end-fed will use your coax braid as a counterpoise if you
do not give it one, digital modes are 100% duty cycle so turn the power down and
redo the exposure evaluation — and an alternative for when the garden is too
small. It is a starting point rather than a rule: good enough to make contacts
with, which is what somebody needs before they have the experience to disagree
with it.

**60 m is five channels, and the page draws five channels.** 47 CFR 97.303(h)
permits 2.8 kHz on each of five fixed frequencies and nothing at all between
them, so a bar filled from 5.3305 to 5.4065 says, in the only language a chart
has, that the whole range is yours. It is drawn as what it is: five slivers,
hatched between, numbered 1 to 5 and labelled with the dial setting.

Two frequencies belong to each channel and they are not the same number. The
rules name the channel by its centre — 5332.0 kHz and the rest. The operator
types the suppressed carrier, 1.5 kHz below that, and *that* is the number
printed on every 60 m chart in a go-bag. Both are held, both answer "yes", and
the page shows the one you dial with the one the rules name behind it, because
an operator who knows only one of them is the one who ends up 1.5 kHz off and
certain the chart is wrong.

The privileges are generated from the channels rather than written out beside
them, so being permitted on 60 m and being on a channel are now the same fact
everywhere in the program: the antenna designer, the exposure evaluation and
the printed sheet all refuse 5.340 MHz for the reason that is actually true of
it. Only upper sideband, CW and data are permitted there — an AM carrier on a
60 m channel is refused where the same carrier on 80 m is somebody's ordinary
evening.

**A second bar, under the first.** The top bar is where you may transmit. The
one under it is whether it is worth it: one number for that band at this hour,
what it means for the mode, and the shape of the next day beside it.

    Conditions on 40 m now   [ Fair · 50/100 ]   wall chart says Poor
    ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░
    CW and FT8 comfortably; SSB will be a struggle
    7 MHz is 0.42 of the 16.8 MHz MUF; daylight D-layer absorption is what
    limits it. MUF measured at Idaho Natl Lab, 1468 km away, 27 min ago.

    The next 24 hours
    ▁▁▁▃▅▇▇▇▇▇▇▇▇▅▃▁▁▁▁▁▁▁▁▁
    now      22       04       10       16
    Worth using right through the day, local time — best from 22:00 to
    05:00 at 83/100 — 7 hours of it.

The peak is given as a stretch because that is what it is. A band sits within
a point or two of its own maximum for hours at a time, and naming one of them
sends somebody to the radio at an hour that was never special while implying
the rest are worse. The hours either side of the top that are as good as it is
— within three points, which is well inside the error of a rating that is an
estimate — are the peak, and the strip marks that run along its top edge. On
40 m here that is seven hours; on 20 m it is one, which is the contrast worth
having.

A wall chart rates a *group* of bands Poor, Fair or Good, twice a day. That
answers whether to turn the radio on. It does not answer the question actually
in hand, which is whether to call CQ on SSB now or come back at eight o'clock
and use CW — and the difference between those two is most of an evening. So the
number is worked per band per hour, out of the three things that decide it and
can be known here: the band against the MUF, daytime D-layer absorption, and
the state of the geomagnetic field. The mode line comes from the same number,
because FT8 and CW get through some 10 to 15 dB below where SSB gives up, and a
band that is shut for one is open for the other.

The forecast is the sun. Where the sun will be tomorrow is the one thing about
tomorrow that is known exactly, and on HF it is most of the answer: it sets the
MUF and it switches the D layer on and off. So the flux and the field are held
where they are now — they move slowly, and pretending to forecast them would be
inventing numbers — and the sun is allowed to do what it is going to do anyway.
Where an ionosonde is reporting within 2000 km, its measured MUF sets the level
and the model supplies only the shape, so the meter and the curve are anchored
to a measurement rather than to a flux figure. It is a model and says so on the
page: it knows nothing about your antenna, your power, or the far end.

Two things about that sun are worth stating, because both were wrong and both
were wrong in the same direction — against the low bands after dark.

The layer chases the sun rather than following it. Production switches on with
sunlight and stops with it, but loss at F2 heights is slow, so electron density
goes on building after the sun starts down and foF2 peaks in the early
afternoon rather than at local noon. It is driven by the sun over the hours
behind, exponentially weighted, which is the first-order form of
*dN/dt = production − N/τ*; at a two-hour time constant the peak lands about an
hour and a half after noon, the evening decays slowly and the deep night is
untouched. One honest cost, written into the constants: they were fitted
against the unlagged drive, so they are no longer that fit's optimum — the peak
comes out about 3% lower — which is well inside the model's own 1.11 MHz error
and is systematic rather than random. Where a sonde is in reach it does not
arise, because calibration measures the model against what was observed and
scales it, and the lag is applied on both sides of that comparison.

And a band well below the MUF is not charged twice. The penalty for sitting far
under it is absorption, and absorption is the D layer's — which is charged for
separately. In daylight that is one thing said twice and roughly right; after
dark the separate term correctly falls to nothing while the other did not, so
80 m read "Good" through the hours it is at its best. The shape relaxes as the
layer goes, by exactly as much as that band was being absorbed and no more —
so 80 m gets nearly all of it back and 10 m essentially none, which is right,
because 10 m well under a high MUF is not being held down by the D layer and
does not improve at nightfall.

Above about 30 MHz none of it applies, and the bands above HF say so instead of
showing a meter that would read *closed* every day of the year. There is no MUF
to be under: what opens 6 m and 2 m is sporadic E, tropospheric ducting and
aurora, which are local, short-lived and not predictable from a solar flux
number. Those bands get what is actually known — what the network is reporting
at this moment — and a sentence about why there is no curve.

Two printouts. **One page (PDF)** is the picture: every band drawn to scale on a
single landscape sheet, your privileges filled in and coloured by what you may
send there — voice, CW and data, or CW only — and everything you may not
transmit on left grey. Power ceilings below 1500 W are written into the segment
they apply to, 60 m is drawn as the five fixed channels it actually is rather
than a continuous band, and every privilege edge on the sheet is labelled. It is
drawn from the allocations themselves rather than modelled on anybody's chart.
**Full chart (PDF)** is the reference behind it: every activity segment in a
table per band, with the regional segments folded in.

**Whose chart it is.** The band plan draws any class for anybody, which is how
somebody decides whether an upgrade is worth sitting for. On paper that becomes
a different object: a sheet headed "US Amateur Bands — Extra — KC9SP" is read as
a claim to hold Extra, by anybody who reads it, whatever the page that made it
meant. So a callsign goes on a chart only when the chart is of that station's
own privileges — taken from the FCC record where there is one, not from the
class being browsed — and anything else is drawn without it and says on its
face that it is a study sheet, not a licence, and not a statement of what any
station holds. Other operators would know and the one waving it would be
caught; that is not the point. The door reflects on the community whose licence
this program exists to teach people to respect.

**Where a printout goes.** Nowhere, is the answer that was wrong. A PDF built
here used to be handed to the browser, which put it in a downloads folder — and
on a Pi running full screen, with no tabs, no address bar and no file manager
in reach, that is behind the application. The one thing on the unit that is
meant to end up on paper was the one thing you had to leave the unit to get at.

So the unit keeps what it prints. Building a chart now opens it, in the page,
with **Print** beside it; every printout is listed under **Printouts** in the
top bar, and can be opened, printed, saved out as a file or thrown away from
there. The last thirty are kept and the oldest drop off by themselves — nothing
on the shelf is the only copy of anything, since each one is rebuilt by the
button that made it from the rules and pools on this unit.

Print goes to whatever printer the machine has set up, and the same dialog will
save it as a file when there is no printer. What is shown is the PDF itself
rather than a picture of it, so what comes out of the printer is the document.

The page also points at the **NIFOG** — the National Interoperability Field
Operations Guide, published by CISA at the Department of Homeland Security and
revised most years. It is the pocket reference that the standard interoperability
channel names, and a fair number of the band charts in circulation, are copied
out of, and it is oddly missing from the amateur study material. ELMER says where
to get it, what is in it for an amateur and on which page, what it is actually
for — programming a radio and filling in an ICS 205 — and, at least as
importantly, that nearly nothing in it is amateur spectrum. Monitoring is free;
transmitting on those channels needs an authorisation a license does not give
you, and owning the book is not it. Being a work of the US government it carries
no copyright and can be printed and handed out freely.


## When it goes wrong

Both halves of ELMER report faults into one place. The server logs unhandled
exceptions with tracebacks; the browser catches JavaScript errors and unhandled
promise rejections and beacons them to the same log, so a fault in a page does
not stay in that page. The log rotates at 2 MB, keeping three. Every start
stamps the build, the python and the platform into it, because a log that does
not name its version costs whoever reads it the first hour.

`./elmer.py --report`, or **Report a problem** on the dashboard, writes a
single file: versions, what this install holds, every recent error and warning,
and the tail of the log. It takes out the callsign, the town, the last two
characters of the grid square, any coordinates and the addresses of machines on
the home network - and says so. Versions, timings, tracebacks and the sequence
of requests stay, because those are what find a fault.

Nothing is sent anywhere. It is a file, and where it goes is the operator's
decision, made after reading it. `--report-with-station` leaves the
identifying detail in for somebody who would rather include it.

The report says what *kind* of place ELMER is installed in - a home directory,
removable storage, the downloads folder - and never the path, because an
account name is often somebody's actual name, and which folder they keep their
radio software in is nobody's business.

### Where to keep it

Nothing in Raspberry Pi OS stops a program running from the downloads folder,
or from the wastebasket. Both were tested; both run perfectly well. That is the
problem: nothing stops you, and then one day the folder is emptied and `data/`
goes with it - every answer logged, every setting, the lot.

So `./install.sh` looks at where it has been put. Removable, temporary or
downloads storage gets a warning and a question; the wastebasket is refused
outright. `--doctor` says the same at any time. ELMER keeps everything in
`data/` beside itself, so the fix is always to move the whole folder somewhere
permanent - `~/ELMER` does nicely - and the data comes with it.

One thing moving does break: a `.desktop` entry holds an absolute path, so the
menu icon keeps pointing at where ELMER used to be and quietly does nothing.
`--doctor` now says so plainly instead of reporting "installed", and
`./install.sh` offers to repoint it. `./elmer.py --install-launcher` does it
directly. The entry declares `Categories=Education;HamRadio;`, which is why it
turns up under both.

Install without sudo. The menu entry goes in the invoking user's own share
directory and `data/` takes the ownership of whoever writes it, so a root
install puts the icon in a menu nobody uses and leaves ELMER unable to save
anything when the desktop user runs it. The installer asks for sudo only when
a system package is genuinely needed.

## Packing for somewhere the internet is not

ELMER runs with no network - that is the design - but several of the things
that make it useful *about a place* are looked up once and then remembered.
Off the grid it can only remember what it was told before you left.

So name where you are going while you still have a signal:

```
./elmer.py --prepare "Moab, Utah"      # a town, a grid square, or lat,lon
./elmer.py --trips                     # what is packed
```

It fetches the towns around that destination and keeps them, then says plainly
what no preparation can carry: live solar numbers need the network at the time,
repeaters come from TowerWitch and are its to fetch (`--import-repeaters`
before you leave), and ground profiles are per-path with more paths than
anybody could cache. Set the QTH to the destination's grid square and every
answer - who is in reach, which way to point, what to try - is about there.

This works because a cached area now answers for anything inside it: a fetch
covering 800 km serves a question about 300. It used to match the radius
exactly, which meant a trip prepared before leaving was never found again,
since ELMER asks with a different radius for every band and antenna.

## Showing the working

ELMER does not ship antenna plans. There are plenty of those, and a plan
somebody follows teaches them one antenna. Under every dimensions table is a
fold marked *where these numbers come from - so you can do it without ELMER*,
and inside it the arithmetic is done in front of you:

```
983.6 / 14.200 MHz     69.27 ft   one wavelength; 983.6 is c in feet per microsecond
69.27 / 2              34.63 ft   a dipole is half a wave, fed in the middle
x 0.949                32.85 ft   velocity factor - a wire is not free space
468 / 14.200 x 0.998   32.91 ft   what the table prints, and why it differs
```

Three steps produce every wire length in amateur radio, on any band. The last
row exists because being caught out by your own program is worse than not
being taught: 468 is 983.6 / 2 x 0.95 rounded up, it lands 0.7 in from the
line above it, and saying so is worth more than hiding it. Every figure shown
can be checked on a pocket calculator - the constants displayed are the
constants used.

The aim is the operator who is up a hill with a tape measure and no Pi, and
still has an antenna.

## What it is made of

The lab now asks what the element is actually made of - #18 flex, house wire,
fence wire, a coat hanger, a tape measure blade, aluminium tube, EMT conduit,
copper pipe in three sizes - and the answer changes the numbers, because it
changes the antenna.

The rule runs opposite to most people's intuition, so it is shown rather than
asserted: **a fatter conductor has a *lower* Q, and a lower Q is a *wider*
band.** A thin wire is the high-Q, narrow case. On 20 m a #18 wire dipole
holds 2:1 across about 504 kHz; the same dipole in 1 in copper pipe holds it
across 767 - and on 2 m the difference is nearly 1.7 to 1. It is the same
reason a bowtie or a cage dipole covers a whole band where thin wire covers
part of one, and why commercial VHF antennas are tube rather than wire.

Being fatter also resonates shorter, so the element wants cutting to about
0.935 of a half wavelength instead of 0.95 - the dimensions follow the choice.
The number underneath is the thickness factor, 2 ln(4L/d), and it is labelled
as the approximation it is. Steel choices carry their own warning: fence wire,
conduit and coat hangers conduct about a tenth as well as copper, which a
full-size resonant element mostly forgives and a loaded one does not.

The bowtie is also drawn at the shape it actually is. It was being drawn as a
slender dart about a fifth as wide as it is long, when the dimensions beside
it said the tips are *wider* than each half is long - so the picture argued
against the number and against the whole reason for building one.

## How far, and toward whom

The plan view is a map now, not just a compass. Every antenna other than a
satellite one gets its reachable places plotted at their real bearing *and*
their real distance, with the pattern's own strength toward each - so a dipole
strung the wrong way shows Hartford sitting at -20 dB off the end of the wire,
which is an unforced error you can see rather than one you discover.

On HF the reach is worked out from the antenna's own takeoff angle rather than
waved at. The main lobe is turned into one ionospheric hop, and the half-power
edges of that lobe into a band of distance - so a 20 m dipole at 35 ft reaches
roughly 450-1,570 km, and the same wire at 70 ft reaches 1,140-2,270 km. Raise
it and you gain the far edge and *lose* the near one: the skip zone is drawn as
a dashed circle, because a high wire cannot work the next county and nobody
believes that until they see it.

Two figures are given for every case and labelled separately: what the geometry
says, and what the day says. The first is a calculation and the second is a
warning, and running them together is how a calculation gets mistaken for a
promise.

When nothing at all is in range, that is a fixable problem and it is rarely
fixed with the power knob. ELMER says which knob does move it - drop a band,
lower the antenna, work the ring rather than the middle, try a weak-signal or
digital mode, come back at a different hour - and, when the place list is the
bundled North American one, says so first, because an empty compass in Bavaria
is a gap in the data rather than an answer about an antenna.

## Getting a message out

The **Make Contact** page answers the question somebody a long way up a forest
road actually has: not "what is the best antenna", but "what might work now,
with what I brought". Tick what you have on hand and it lists every avenue in
the order worth trying - the repeater you cannot hear from the valley floor,
the calling channels, APRS, the ISS digipeater passing overhead twice a day,
NVIS on a wire eight feet off the ground, ten metres if you are a Technician
who has been told they have no HF.

Under the list is the other half of that inventory. The tick boxes are radios,
and a radio somebody did not bring is not going to appear - but the antenna is
the part of the station that can still be built out of what is standing
around: fence wire, a coat hanger, a tape measure blade, house wire stripped
out of twin-and-earth, the coil of soft copper an ice maker is plumbed with.
Those are the entries `conductors` already has real numbers for, and the page
says out loud that they are examples rather than the list, because a list
presented as complete would do the opposite of what it is for. What settles a
candidate is whether it conducts, whether it can be got up and clear, and
whether it is the right length - and a piece of metal that fails all three can
still be the ground, the counterpoise, the reflector or the mast, which is
where most of what is lying about turns out to be useful. With a NanoVNA on
hand none of it has to be guessed at: anything conductive can be swept and
asked directly, and reading the answer is a skill rather than a purchase, so
the page hands that question to the Lab, which teaches it with an instrument
or without one.

Under that again are the tools, because a fence somebody cannot cut is
scenery. Same shape a third time: the tool each job wants - cutting, joining,
getting it up there, finding out whether it works - and then what has stood in
for that tool when it was forty miles away. A bare hacksaw blade with a rag
wrapped round one end. A nick from a file and then metal fatigue - the same
crack that took the roof off Aloha 243 and broke two Comets apart in 1954, run
deliberately and in one spot, with the nick standing in for the rivet hole
that started the real one. Hose clamps, which are already holding every heater
hose in the vehicle. A rock on a line over a branch, and a water bottle that
throws further and does not stick in the tree. The one
that carries the most weight is the joint, because that is where scavenged
antennas die: every mating face has to be clean to bright metal, and a
corroded joint can read like a short on a meter and still rectify at RF.

And yes, a vehicle is also a welder. `fieldkit.ARC` says how - two or three
batteries in series, heavy cables, a rod - with the hydrogen, the cornea, the
cable insulation and the zinc fumes all named, because the half-remembered
version of that trick is the dangerous one. It ends by saying not to: for an
antenna a bolted joint is as good electrically, comes apart when the first
guess was the wrong length, and asks nothing of anybody but a spanner.
`tests/test_fieldkit.py` keeps both halves honest - no entry that is not
copper may recommend solder, and the warnings cannot be quietly trimmed out
later.

The odds are words rather than numbers, because numbers there would be
invented. And the last entry is 47 CFR 97.403: when life or property is in
immediate danger and normal systems are not available, an amateur station may
use any means of radiocommunication at its disposal. It is pinned to the
bottom on purpose - answering "how do I get a message out" with "declare an
emergency" is wrong for a flat tire, and the entry has to keep its force for
the day it is needed.

## Parks and summits

Parks on the Air and Summits on the Air are what get most people to carry a
radio somewhere, and almost every wasted trip is a planning failure rather than
a radio one — the wrong kit, or the wrong side of a contour. That is fixable at
a table days early, for nothing, which is what the page is for.

**What is within a day's drive.** Four hours of road is about 350 km in a
straight line, and the parks and summits inside that are fetched once while
there is a signal and then held. POTA answers per state and province, SOTA per
region — and SOTA publishes a bounding box for every association, so both can
be asked only about ground that matters rather than downloading a 24 MB list of
all 179,000 summits. From here that is thirteen location lists and four
associations: 486 parks and 32 summits, in about fourteen seconds. After that
it answers in a valley with no bars, which is the whole point of fetching it in
advance.

A centre decides who to ask and never decides what is near. POTA's own location
list is wrong about some of its centres — as this was written it placed South
Africa's North West province in Indiana — so every reference is measured on its
own coordinates instead, and the distance is recomputed from wherever the
operator is standing rather than from where the list was fetched.

**What counts.** Both rule sets, each carrying the document it was read from
and the day somebody read it, because these change by another body's decision
rather than by physics. POTA wants ten QSOs inside one UTC day with the
activator and all the equipment inside the boundary. SOTA takes one QSO to be
an activation and four different stations for the summit's points, from inside
the activation zone — typically 25 vertical metres, though each Association
sets its own. Neither counts a terrestrial repeater. Both count a satellite,
which means the ISS digipeater on the Make Contact list earns credit in both.

**What you would be carrying**, judged against each programme from the same
gear list Make Contact uses, worst news first. A whip on the car is a park
antenna and a disqualification on a summit — SOTA rule 3.7.1 forbids the
station being in or near a motor vehicle or connected to one in any way — and
the trailhead is an expensive place to find that out.

**The operator's own POTA record**, once they have said so. The panel names
what it would send, to whom, and what comes back before it sends anything: a
callsign leaving this unit for somebody else's server is a decision, not a
detail of how a page is built. What is kept is the awards and the counts; the
name, the town and the avatar the endpoint also returns are thrown away, the
same choice `callsign` already makes about the FCC record it reads.

## Where the station is

Every answer about reach, bearings and RF exposure is an answer about a place.
ELMER asks for a QTH so it works in a field with no network, and that typed
square stays the fallback - but where a GPS is reachable, the live fix wins,
because a Pi in a vehicle is not where it was last winter. `--gps` says what it
can see; `--gpsd HOST` points it at another machine, which is how a second Pi
reads the one with the antenna on it. `--gpsd off` goes back to the typed QTH.
The page says which of the two the figures came from.

Above 50 MHz "what can I reach" is answered by repeaters, not by towns. ELMER
does not look repeaters up itself - TowerWitch does that, against a data source
that is its subscription to hold - so ELMER reads what TowerWitch writes and
merges it with its own saved copy. Neither replaces the other: the saved copy
is what makes a machine without TowerWitch work, and TowerWitch is what makes
anywhere work.

`--import-repeaters` keeps a copy of what TowerWitch has. Copying
`data/repeaters.json` to another install works too. And ELMER tells the two
kinds of empty apart: no repeaters near you is a fact, no repeater data for
where you are is an errand, and it says which one it is looking at.

### Asking a TowerWitch over the network

Two Pis in one vehicle: only one has TowerWitch and the credentials. Point the
other at it with `./elmer.py --towerwitch-url http://192.168.1.5:8137/api/repeaters`
and ELMER will ask - but only when it has nothing for where it is, and at most
every few minutes, so a machine that is switched off is not a tax on every page.

The endpoint it expects is deliberately the smallest thing that could work:

```
GET /api/repeaters?lat=46.59836&lon=-94.31539&radius_km=100

{"data": [
  {"call": "W0UJ", "output": 146.955, "input": 146.355, "offset": -0.6,
   "tone": "141.3", "location": "Nisswa", "lat": 46.5216, "lon": -94.2883}
]}
```

That is the row shape TowerWitch already writes into `radio_cache`, so the
endpoint can return a cached payload unchanged. A bare list is accepted instead
of `{"data": ...}`; `frequency` works as an alias for `output` and `pl_tone`
for `tone`. Anything without a callsign and a coordinate is dropped. A machine
that is off, busy or not listening is not an error - the answer is then
whatever is already on disk.

TowerWitch answers this with `repeater_service.py`, which serves the cached
lookups and RepeaterBook exports it already has. It looks nothing up: the
subscription and the credentials are TowerWitch's to hold, not this endpoint's
to spend on behalf of whoever asks. `./elmer.py --doctor` reports whether the
service answered, so a Pi that has stopped talking says so in one command.

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
- **The whole code** as a chart, drawn as dits and dahs at their real lengths
  rather than printed as dots and dashes — a dah is three times a dit, and the
  gap inside a character is one dit, which is what the spacing shows. Click
  anything to hear it. The eighteen Q signals are on it too, each with its name
  over its own code and the meaning beside them, because three letters of code
  will not share a line with a definition and leave either readable. A space in
  a code means the gap between two letters, drawn as silence of the right width
  and sounded as silence of the right length: that is the whole difference
  between the Q signal QRM and a prosign, which has no gaps inside it at all
  and is one sound. And a question mark makes one a question — QRL? asks
  whether the frequency is busy, QRL answers that it is.
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

### One ELMER knows another

Two Pis on a bench, or four on a club table, and neither knowing the other is
there. That is a waste twice over: one of them may have a GPS antenna and a
lock while the other has been guessing for ten minutes, and either could have
been running a tournament against the other all evening.

Each unit says hello on the network every few seconds and listens for the rest.
Nothing is configured at either end, and a unit that goes quiet drops off the
list by itself. The dashboard grows a panel at its foot when there is company,
and none when there is not.

The panel says how many and not who. A hall with nine units in it would put
nine names, nine addresses and nine version strings on the screen, and none of
them answer the only question the operator actually has — which is what *this*
unit should do about the others. There are three answers, and the panel is
those three:

    Another ELMER is on the network.
    Technician net is running out there, and this unit can take a table in it.

    A tournament here can be run three ways:
      Independently   run one for the players in front of this unit
      Host  [General ▾]   run a net from here for everyone who reports in
      Join Technician net   3 tables · hand the scores to whoever runs it

Two things come of it. **Position**: a unit with a receiver announces its fix
and a unit without one takes it, so a second Pi never needs a second antenna.
**Company**: a tournament can be suggested rather than remembered, and joined
in one press. The suggestion is all it is — a unit never starts a round on
another unit's say-so, and *not now* makes the panel go away.

**One network, several tournaments.** Technician in this corner, General in
that one, Extra in the next room. A net is named for what it is studying,
because that is what somebody choosing between them is choosing on, and the
name follows the material if the hall moves on to something harder. A unit that
is only a table passes on the address of the net it reports to, which is how a
late arrival finds a master it cannot hear directly — across a subnet, or on
the end of a wire.

What is announced is what a neighbour needs to be useful: who this is, where to
reach it, whether it has a position, whether a game is on, and which net it is
running or reporting to. Not the operator's name, not their progress, not their
callsign. It goes to the local broadcast address and nowhere else, and position
sharing can be switched off without switching discovery off.

### One receiver, every unit

A station with more than one Pi does not need more than one GPS. TowerWitch
broadcasts the station's position over UDP, and ELMER listens for it - on by
default, configured at neither end. A unit with no receiver of its own picks
the fix off the network:

```
[  ok  ] GPS  -  3D fix from TowerWitch at 192.168.1.5 - EN26uo (46.5984, -94.3154)
```

The broadcaster lives in `TowerWitch-P.py`. If the machine with the receiver is
running a different build of TowerWitch, or none, `tools/gps_broadcast.py`
sends the same packet from the local gpsd instead:

```bash
python3 tools/gps_broadcast.py            # every 5 seconds
python3 tools/gps_broadcast.py --once     # send one and stop
```

`systemd/elmer-gps-broadcast.service` makes that survive a reboot. It sends
only when gpsd actually has a fix, because a station that does not know where
it is should say nothing rather than announce its last guess to every device in
the vehicle.

A receiver wired to the machine still wins wherever there is one; this sits
between that and a phone. `--doctor` names which answered, so "no GPS on this
unit" and "the GPS is on the other Pi" stop looking alike.

### The GPS already in your pocket

A receiver on a USB lead is one more item on a list nobody reads before they
leave, and the day it is forgotten is the day the position mattered. Almost
everybody is already carrying a GPS, so ELMER will listen to one.

Switch it on, point any NMEA-forwarding app on the phone at this Pi, and the
position arrives - no receiver, no antenna, no pairing:

```
./elmer.py --doctor
[  ok  ] GPS  -  2D fix from a phone at 192.168.1.42 - EN36ws (46.7750, -92.1017)
```

A hardware receiver still wins wherever there is one; the phone fills in when
there is not, which is the case it exists for, and `--doctor` and the location
itself both say which is being used. The listener is remembered across a
reboot, since a station whose only GPS is somebody's phone should not have to
be told again every morning.

**Not Bluetooth Low Energy**, which is the obvious guess and the one route that
does not work. The Bluetooth SIG defines a Location and Navigation Service, but
phones implement it as a *client* - to read a bike computer - and neither
Android nor iOS will serve its own fix over GATT. Getting at it that way means
writing and installing a phone application, which is exactly the "one more
thing to remember" this exists to avoid. Plain UDP over the wifi the phone is
already on needs nothing that is not already there. Classic Bluetooth SPP works
too, if the wifi does not suit, since that carries NMEA the same way.

The sentences are ordinary NMEA 0183, so anything that speaks GPS speaks this.
Only RMC and GGA are read, and both are checked: the checksum must match, a
void RMC is refused, and a GGA reporting fix quality zero is refused. A
position is not a value that announces when it is wrong - a corrupted sentence
produces a plausible number in the wrong ocean rather than an error - so the
parser's job is mostly refusing things.

### Locate me

There is a **locate me** button, and it asks the station's own GPS first.

That is the right order, and it used to be the wrong one. The button called the
browser's geolocation, which on Raspberry Pi OS resolves through a network
lookup service Chromium has no key for and which never consults gpsd at all —
so on the one machine with a receiver plugged into it, the browser was the
source least able to answer, and the button failed while gpsd was reporting a
3D fix half a metre away. It now takes the fix from the server, reverse-geocoded
to a name where one is known, and falls back to the browser only when the
station has nothing.

It also used to be hidden entirely on the LAN address, because browsers permit
geolocation only in a secure context and that check gated whether the button
was drawn at all. The server's GPS has no such objection over plain HTTP, so a
phone on the network can now locate the station even though its own browser
would refuse to.

### Live propagation

Real solar and geomagnetic data from N0NBH (hamqsl.com) and NOAA SWPC: flux, K
and A indices, sunspots, solar wind, X-ray background, aurora, band-by-band
ratings for day and night, and an estimated MUF and foF2. Set your grid square
and it works out your local solar elevation to pick the right day/night ratings
and tell you when you're near the grey line.

Every indicator is annotated with what it means and why the exams care, with
one-click links into the matching pool sections — reading about the MUF while
the MUF is on screen sticks much better than reading an answer key.

This page is the state of the sky. The [band plan](#band-plan) turns it into a
decision about one band: a 0–100 score for the band in front of you, what it
means for the mode, and the next 24 hours hour by hour.

### Lab

Interactive versions of the maths the pools test. Only that: the analyser, the
sextant and the audible-wave demonstrations moved to **Tools** next door,
because no exam element has ever asked how to drive a NanoVNA or take a sun
sight, and a Lab that mixes the two makes the syllabus look bigger than it is.

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
- **Antennas** — twelve configurations across wire (dipole, inverted-V,
  end-fed half wave, bowtie, full-wave loop), vertical (quarter wave, 5/8 wave,
  J-pole, ground plane), the Yagi, and mobile: a loaded whip, and a screwdriver
  whose coil is driven in and out by a motor. That last one is the only antenna
  here without a single Q, because it is defined by covering a decade — its
  figure is anchored at 40 m and scaled, which lands on the tens of kilohertz
  builders measure down there and most of a megahertz on 10 m. Dimensions in feet, metres and
  inches, feed impedance, gain, and for horizontal wire the takeoff angle your
  height above ground actually buys. A short whip reports its radiation
  resistance, efficiency and the loading it needs, which is the honest answer to
  why mobile HF is hard.

  The **build sheet** each of these prints carries the whole band it is cut
  for at the top of it, once: the same coloured segment bar the band chart
  draws, with the slice this antenna holds under 2:1 outlined on it, and
  whatever the licence may not transmit in hatched over. A wire cut for one
  frequency reaches a good deal more of a band than the frequency it was cut
  for, and most of what is up there is a mode rather than a frequency — one
  nobody thinks of is usually only out of mind because it was out of sight.

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
  Every antenna also draws a **plan view**, its **elevation pattern** and its
  **SWR across the band**, because a gain figure answers neither of the questions that decide
  whether an antenna suits you: where does the energy go, and how much of the
  band can you use. The pattern is computed rather than sketched — over ground
  the antenna's image adds a second wave, and where the two add is where you
  radiate, so the lobes fall out of arithmetic. A wire at half a wavelength
  peaks at 30°, at three quarters 19.5°, at a full wavelength 14.5°; that is the
  whole argument about height, drawn. Perfect ground is assumed, so treat the
  shape as right and the last couple of degrees as optimistic.

  The plan view is the one that saves an afternoon of work. A dipole radiates
  *across* itself and is deaf off its ends, so which way you string it decides
  which way it hears — and a wire hung along the fence because the fence was
  there is an unforced error. Set the bearing it runs along and the pattern
  turns with it, with real great-circle bearings laid over the top **from your
  own grid square** — and the places shown are the ones this antenna can
  actually reach. A DX wire on 20 m gets Europe, Japan and Australia; an NVIS
  wire on 80 m gets Bemidji, Duluth, Fargo and Minneapolis with a ring at about
  300 miles, because putting Europe on an NVIS compass is worse than putting
  nothing there — it invites somebody to turn an antenna to chase a contact it
  cannot make. A 2 m vertical gets its radio horizon, and is told plainly that
  the repeater is doing the reaching rather than the antenna.

  The names come from two places, and the better one wins. `./elmer.py
  --fetch-places` asks OpenStreetMap what towns are actually around your QTH,
  ranked by population, and caches them — so it works in Wales or Hokkaido as
  well as in Minnesota, and it finds the small towns no bundled list would ever
  carry. Behind that sits a list of 339 North American cities that ships with
  the program, so a Pi that has never seen a network still has something to say;
  when that is what you are seeing, the page says so and tells you how to do
  better. The QTH is typed in by hand either way, so an off-grid station sets
  its own location and keeps working — the network only buys better names.

  A city takes its suburbs with it. Ranked by population, a town is only listed
  if it is well clear of everything larger already listed, so Minneapolis stands
  for Coon Rapids and Maple Grove — which is how anybody would say it, and
  without it the list fills with dormitory towns that happen to sit a few miles
  nearer than the city they belong to. Strung east–west
  from EN26 the nulls fall on Africa at 87° and Hawaii at 266°, both around
  24 dB down, and it says so in as many words: *turning the antenna is free; the
  decibels are not.* A Yagi behaves the same way with a front and a back; a
  vertical draws a circle and says plainly that there is no wrong way to face
  it, which is what omnidirectional buys and what it costs.

  The bandwidth plot is where the **bowtie** earns its place. Two triangles
  instead of two wires is a lower Q, and Q is what sets how fast the SWR climbs
  as you tune away: on 20 m the bowtie holds under 2:1 across **1960 kHz** where
  a thin-wire dipole manages 532, a monoband Yagi 447 and a loaded mobile whip
  170. Same gain to within a rounding error — the width is the whole point.

  A straight wire can be **slung as a sloper**, which is where the arguing
  starts. Tilting mixes vertical polarisation into a horizontal antenna, and the
  vertical part does not null along the horizon the way the horizontal part
  does — so the low angles fill in, and that is the whole of the sloper's case.
  ELMER draws it and then undercuts it: the model assumes perfect ground, and
  over ordinary soil the vertical component gives up several decibels at exactly
  the low angles it is being credited with. Over salt water it delivers what the
  drawing shows; over dry sand it does not. It also reports the height of the
  wire's *middle* rather than of the mast, which is the figure people quote and
  the reason a sloper disappoints against the dipole they had imagined — and it
  refuses to pretend a 65 ft wire at 35° from a 35 ft support is anything but a
  wire in the ground.

- **Smith chart** — the one piece of the syllabus that a book cannot teach,
  because it is a transformation rather than a picture. Set the antenna's R and
  X, pick a feedline, and drag the length: the point walks around the chart in
  front of you. The grid is labelled in ohms rather than normalised units, since
  "0.5" means nothing to somebody learning and "25 Ω" means everything.

  It is built to make three things land. A full turn of the chart is **half** a
  wavelength of line, not a whole one. The spiral inward is loss, not magic. And
  the trap: 100 ft of RG-58 into a 3:1 mismatch shows **2.0:1 at the shack while
  the antenna sees 3.0:1** — the reflected wave crosses the lossy line twice, so
  a bad feedline flatters the SWR meter by wasting the power it is not showing
  you. Same antenna on LMR-400 reads a worse 2.6:1 and delivers 84 W instead of
  56 W. Feeds the E9 and Element 3 drills.

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
  fine. Modes the license class may not use in that segment are marked, and a
  line under the row names the band, the class and the terms. Nothing is
  blocked, because evaluating a station you cannot yet operate is legitimate,
  but a transmission the license does not permit is written into the record and
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
  it is left out entirely when no license class is known, rather than printing
  somebody else's bands under your callsign.

  The evaluation errs toward safety throughout — full ground
  reflection, the antenna treated as pointing its whole gain at the person, and
  a modelled gain rounded up rather than to nearest — and both the screen and
  the printed sheet say so, in as many words. A more detailed determination may
  well show a shorter compliant distance and still satisfy the rules; that is
  not a license to work inside these distances, because this is the evaluation
  on record. And because antenna gain is the largest single lever on every
  figure, the record distinguishes a gain **modelled** by ELMER from the
  antenna's geometry from one **entered by the operator**, which nothing has
  checked against any antenna. Neither is a measurement, and the record says so.

  **Station record (PDF)** produces a signed one-page document with the inputs,
  the equation used, every intermediate value and the conclusion — meant to be
  printed and posted in the shack. It opens in the page with Print beside it
  and stays under **Printouts**, so posting it in the shack does not begin with
  hunting through a downloads folder.
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

### Tools

The bench rather than the syllabus. Three things that are worth having and are
on no exam paper.

- **VNA** — the modelled trace an analyser would show for an antenna you have
  not built yet, and the real one off an instrument on the bench. It finds the
  port, asks what is on it, and sweeps. It also *drives* it: the span, hold and
  resume, the five calibration standards one at a time, done, apply, bypass,
  and save or recall a slot. What may be sent is one table on the server and
  nothing types through from a browser to a device that runs what it is given.
  Two of those commands destroy work — `cal reset` and `save` — and are refused
  until the caller says it meant it, with the refusal carrying the reason. Most
  of the rest are accepted in silence, so every result shows the instrument's
  own words and reads the span back afterwards: a command this firmware has
  never heard of shows up now rather than three steps later.

  The sweep is held on the unit rather than in the page that took it. It
  survives a reload, it can be read from a phone while the instrument sits by
  the Pi, and the Smith chart in the Lab reads it from there — which is what
  lets those two live on different pages at all. One sweep, not a history:
  there is one instrument and one antenna, and "what did it measure" means the
  last thing it measured.
- **Sextant** — a sun sight reduced to a position line, for when nothing else
  knows where you are. On no exam and useful anyway.
- **Waves you can hear** — the analogy under the arithmetic, at audio, where a
  long wavelength bending round an obstacle is something you listen to rather
  than take on trust.

### Game layer

Titles are earned inside the license class they name. Each class carries a
five-step ladder:

    <Class> Listener -> Learner -> Operator -> <Class> -> <Class> Elmer

The first two steps come from coverage and estimated mastery. The upper three
require mock exam evidence: one pass for Operator, two of your last three for
the class itself, and for the Elmer tier all of your last five passed averaging
90% or better. There is no route to a General title that does not run through
General questions, which is precisely what a single global XP ladder got wrong.

Exam evidence goes stale the way a license does. A tier is **current** for 90
days after a passing exam, then sits in a 90-day **grace period** where it is
shown as lapsed and a single passing exam renews it, exactly as a license in
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
license, and only a real session in front of accredited VEs or a COLEM leads to
one.

XP is kept as a pure effort meter and no longer confers any title. It is
weighted so the answers worth the most are the ones that teach you the
most — a hard, overdue, previously-failed question pays several times what a
question you already own does. Alongside it sit daily streaks, 22 achievements
and a timed contest mode.

---

## Tournament mode

A study tool assumes one person and a quiet evening. A club night is neither.
Tournament mode is the same 2,475 questions run as a race: everybody gets the
same question at the same moment, and the fastest correct answer takes the
round.

It works at three sizes, and the same engine runs all of them.

**One person.** Open a tournament from any pool card on the dashboard. The
table fills with practice opponents so there is a race to be in, and the match
runs itself — question, answers, result, next question — until you stop it.

Nobody has to press it, either. A table with somebody in it starts fifteen
seconds after the first person arrives: long enough for a second and a third
to get in behind them, short enough that nobody is left reading a countdown,
and both screens show it running down rather than saying "waiting" at each
other. The class it asks about is the one the operator is studying. Before
that, a player who scanned the code and got a screen saying "waiting for the
next question" waited for somebody at the table screen to press something —
right for a club night, where the instructor starts the evening, and for one
operator with a Pi and a phone it was a program that did not work and looked
like one that was broken.

Not under a net, because a table in a hall answers what net control put up;
not while a game is running; and not for an empty room, so the last person
leaving takes the countdown off again. A phone alone on an idle table also
gets a Start button, checked on the server rather than trusted from the screen
that offered it: a player may start a game they are alone in and may not start
one in a room with other people in it.

**One table.** Up to eight people join by pointing a phone at the code on the
screen. Nobody installs anything.

**A hall.** One Pi per table, one running net control, and up to a hundred
tables on a single master.

### The race is timed by the player's own clock

The browser reports the interval between painting the question and the button
going down, and that is what the placings are drawn from. Arrival order at the
server would measure network jitter instead: across thirty players answering
at once that spread was 300 to 600 ms, which is longer than the difference in
thinking that the race is supposed to be about.

A number the client supplies is a number the client can invent, so it is
bounded at both ends against the round clock. A stopwatch left running cannot
report longer than the round has been open, and a claim far *under* it is not a
fast finger — the phone cannot have seen the question much before the round
started. That caps what a made-up time is worth at about one poll interval
rather than letting "1 ms" win every round for ever. It does not make the race
unspoofable, which nothing server-side can, and saying so is better than
implying otherwise.

### Joining, by QR

Each table screen shows a code that carries its own join address. Scanning it
opens the player screen on a phone: type a name, and you are in.

The codes are generated on the Pi, from `elmer/qr.py`, in the standard library.
A hall may have no uplink, Raspberry Pi OS refuses `pip install` under PEP 668,
and there is no apt package — every route out of that ended either in a
dependency ELMER cannot promise or in eight hundred people hand-typing a URL.
So the encoder is written here from ISO/IEC 18004: byte mode, error correction
level M, versions 1 to 10, which covers any join address a table will need.

### Practice opponents

A table of one is not a race. Practice opponents fill each cohort to sixty per
cent and no further, so a table of one plays against four, a table of five has
none, and every person who arrives displaces exactly one machine. A person is
never turned away while software holds a seat.

They are named for the rank ladder, so what each represents is legible:

| | Accuracy | Answers in |
|---|---|---|
| Listener | 45% | 6–18 s |
| Learner | 62% | 4.5–14 s |
| Operator | 78% | 3–10 s |
| Elmer | 90% | 2–7 s |

Each decides what it will do when the round opens rather than at the moment of
answering, so the answers arrive spread across the round the way a room of
people does instead of all in the same instant.

They are never disguised. Every one is flagged as a bot the whole way out to
the screen, because a leaderboard that quietly counts software among the
operators is one nobody can trust at a club night.

### Cohorts, and who picks next

Players are seated in cohorts of eight and scored as teams, so eight people
answering steadily beats one answering brilliantly while seven guess. The
winning cohort chooses the next question — difficulty and topic — and where two
are level the pick goes to whichever is behind overall, so a runaway leader
does not also own the question list. Where they are level on that too it is
drawn, because sorting by name handed the same table every tie all evening.

### Net control

For anything larger than one table, a master unit runs the net. The load on it
scales with the number of **tables, not players**: eight players poll the Pi in
front of them and net control never sees any of it. It holds one conversation
per table, which is why a hall fits on one Raspberry Pi.

Measured on a Pi 5 acting as net control, tables checking in once a second:

| Tables | Players | Check-in p95 |
|---|---|---|
| 25 | 200 | 15 ms |
| 100 | 800 | 46 ms |
| 200 | 1,600 | 100 ms |
| 400 | 3,200 | 1,067 ms |

The cap is a hundred tables — eight hundred seats — which keeps roughly a
fourfold margin under the knee, and is well under the limit that actually binds
at a public event, which is not the master but the wireless. Eight hundred
phones is a serious access-point deployment; net control is the one part of the
evening that will not be what breaks.

A table that loses the network keeps working. The round in front of it finishes
on its own clock, the report is held and sent when the master comes back, and
net control counts the table as quiet and carries on without it. The hall does
not stop because one Pi in the corner lost its wifi. A table also remembers its
net control across a reboot — these Pis update and restart in the small hours,
and nobody should have to walk twenty tables through a form before the doors
open.

### What a spectator sees

A big board is watched by people who are not playing — at a club night the
half of the room waiting for a turn, at a hamfest whoever is walking past. Two
things are for them.

**Both scoreboards, along the foot.** A board on a table unit could only ever
show that table's own eight players, which is the half a visitor already knows.
The strip carries the other half: this table on the left, the hall on the
right, each with the score and what it gained in the round that just went.

    THIS TABLE  4 players · 1 practice   TECHNICIAN NET  3 tables · 15 players
    1 Sam 29 +10  2 Dana 28 +9  3 Ola 8  1 Table 1 18 +9  2 Table 2 15 +9

Net control's own screen does not get the second half — the hall standings are
already the thing it is showing, and the same list twice is not a scoreboard.

**The answer, when the winner goes up.** The round closes, the fastest correct
answer is named, and the question is still in everybody's head: that is the one
moment in an evening when a whole room is looking at the same screen wanting to
know the same thing. So the answer goes up with the winner — the answer alone,
not the other three choices and not the explanation, which stays where it
belongs in the pool browser afterwards. It is surface familiarity rather than
teaching, and surface familiarity is how most of this material is first met.

It is held back until then. While a round is open the answer index never leaves
the server, because a poll response is readable in any dev console; once the
round is scored there is nothing left to protect.

### Several tournaments, one board

A network can hold more than one net at a time, and a hamfest usually should:
Technician in one corner, General in another, Extra in the next room. A net is
named for what it is studying, because that is what somebody choosing between
them is choosing on, and the name follows the material if the hall moves on to
something harder.

The big board shows the network, not the Pi it happens to be plugged into. It
lists every tournament it can hear — the nets, and any unit playing a game of
its own — with the size of each, the question on the floor and who is leading
it. Open one and it fills the screen exactly as if it were running here:

    2 tournaments on the network
    ┌───────────────────────────────┐  ┌───────────────────────────────┐
    │ Technician net           33s  │  │ General net              33s  │
    │ 3 tables · 15 players · rd 4  │  │ 2 tables · 9 players  · rd 4  │
    │ 192.168.1.31:5000             │  │ 192.168.1.44:5000             │
    │ What is a grid locator?       │  │ Which is true of SSB?         │
    │ 1 Table 1        5p        12 │  │ 1 Table 1        4p         9 │
    └───────────────────────────────┘  └───────────────────────────────┘

The neighbours' boards are fetched by the unit serving the screen rather than
by the browser: they are on other origins, a board polls about once a second,
and several screens on one Pi should not each cost the hall a round of
requests. A fetch that fails leaves the last board in place and says how long
that tournament has been quiet — a screen at the front of a room must not go
blank because one Pi in the corner lost its wifi.

### What a round costs

A race is exactly the case that arrives all at once, so nothing in a round
touches the database. The ordinary answer path performs about seven separate
commits and SQLite takes the write lock for each, which caps a unit near
forty-six answers a second. Round state is held in memory and written when the
round closes: twenty-four players answering simultaneously are served in 33 ms.

Admission is capped and the cap moves. Sixty players at once took five seconds
on a Pi 5; thirty took 642 ms. A unit stops admitting at twenty-four and lowers
that figure further when it is measurably slow — and says which of the two is
happening, because a party that quietly degrades is worse than one that says
so.

### No explanations

Everywhere else in ELMER the reason an answer is right appears the moment
somebody commits to one, because that is where the learning is. A tournament is
a race, and stopping a hall mid-round to read a paragraph is neither. A round
carries the question, its choices and its figure and nothing else. The
explanations are a click away in the pool browser afterwards, which is when
people actually want to argue about them.

### The screens

| | |
|---|---|
| `/party/1` | the table: join code, roster, tournament controls |
| `/j/1` | where the QR lands — the player's phone |
| `/net` | net control, for running a hall |
| `/net/board` | the big board — every tournament on the network, sized to read from the back of a room |

All six pools can host a tournament — the three amateur classes and the three
commercial elements. They are offered grouped rather than as a flat list of
six, because Technician to Extra really is a difficulty ladder while a marine
permit, a radiotelephone license and a radar endorsement are three different
jobs rather than three degrees of one.

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
./elmer.py --gps              ask the GPS where the station is
./elmer.py --gpsd 192.168.1.5 read the GPS on another machine (off goes back
                              to the typed QTH)
./elmer.py --import-repeaters keep a copy of TowerWitch's repeater list
./elmer.py --towerwitch-url URL   ask a TowerWitch on another machine
./install.sh                  install, or ask: update, repair, remove, check
./install.sh --connect        give a downloaded copy a link, so it can update
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

It also reports on the two things that decide every answer ELMER gives about a
place, because both could be dead while the rest of the self-check printed
all-clear — which is how a GPS that has stopped answering becomes an afternoon
of guessing rather than one command:

```
[  ok  ] GPS         -  3D fix from 127.0.0.1:2947 - EN26uo (46.5983, -94.3154)
[  ok  ] repeaters   -  258 known, from TowerWitch (~/TowerWitch); nearest 9 km
```

The GPS line tells "nothing is listening" apart from "listening, but no lock" —
the first is an address or a wire, the second is the sky, and they are not
fixed the same way. The repeater line reports how far off the nearest machine
is, because a list of 258 repeaters four hundred miles behind you is the
failure that looks like success on a dashboard. A **TowerWitch service** line
appears only when this unit has been pointed at one over the network, since a
single-Pi station should not be told about a thing it does not use. None of
them is fatal: a GPS that is off, silent or not locked yet is an ordinary
Tuesday, and the typed QTH still works. The point is that the screen says so.

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

### Tournament mode, by address

```
/party/1                      the table: join code, roster, tournament controls
/party/1?difficulty=general   open a table already set to one license class
/j/1                          where the QR lands - the player's phone
/net                          net control, for running a hall of tables
/net/board                    the big board
```

There are no new command-line flags: a tournament is started from the dashboard
or from the table screen, because the person running one is standing at a
screen rather than at a terminal.

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

A selection rather than a manifest — the modules a reader of the sections above
would go looking for. There are others.

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
  prints.py           the shelf of PDFs this unit has built, kept where it made them
  terrain.py          ground elevation profiles for the path tool
  explain.py          assembles rule text, concept notes and your own notes
  propagation.py      space weather fetch and band interpretation
  patterns.py         elevation and plan patterns, reach, and what it is worth
  antenna_advice.py   which antenna, how high, and what usually goes wrong
  antennapdf.py       the printable build sheet
  conductors.py       what an element can be made of, and what it costs
  fieldkit.py         what it takes to work the metal, and what stands in
  activations.py      POTA and SOTA rules, with the documents they came from
  references.py       parks and summits within a day's drive, held on the unit
  pota.py             one operator's POTA awards, once they have said so
  nanovna.py          talking to an analyser, and driving one
  sweeps.py           the last sweep, kept where more than one page can see it
  host.py             the few things that differ by machine
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
  prints/             what this unit has printed, newest thirty
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

### An account can be locked

On a club Pi the accounts are a list of names, and until now picking one off
that list was enough to answer questions as that person, rename them, or - at
the unit itself - delete them and everything they had done. Somebody's study
record is the one thing they came here to build.

So an account can carry a password. Set one from the **who** menu and it is
then needed to switch to that account, rename it, or remove it. Accounts
without one carry on exactly as before: somebody studying alone on their own Pi
should not have to invent a password before they can answer a question, and an
existing install upgrades with every account open.

The person whose Pi it is can set a **moderator key**, which opens any account.
That is what makes a forgotten password at a club night a thirty-second problem
rather than an evening with a database editor. It can only be set at the unit
itself, never from a phone at the back of the room.

Passwords are stored as scrypt hashes with a per-account salt, at the standard
16 MiB cost - about 45 ms on a Pi 5, slow enough to make guessing tedious and
fast enough that nobody notices. The hash never leaves the machine: what the
page is told is only whether an account is locked.

**Be clear about what this is.** It stops a clubmate deleting somebody's
progress or answering questions as them. It is not protection against somebody
on the network who means harm: ELMER speaks plain HTTP, so a password crosses
the wire in clear, and anybody holding the Pi holds the database anyway. It is
a lock on a cupboard, not a safe - so use a password you do not use anywhere
else.

**A callsign is what ELMER calls you.** Somebody who has one earned it in front
of volunteer examiners, so that is the name the program uses — the same respect
an operator gets on the air. Everyone else is called by their name, which is
theirs and needs no license. Add a callsign later and ELMER starts using it, at
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
waiting it **asks**, once, before the session has begun — because that is the
moment somebody will say yes. Nothing is in progress, nothing is lost by waiting
half a minute, and the alternative is remembering to run a command later, which
nobody does. On a kiosk the question goes in a dialogue box instead of a
terminal, and it is put before the browser opens, so it interrupts nothing.

The answer is no by default, no on silence, and no when there is nobody there:
a run with no terminal and no screen is never asked and never waits. Decline and
it says so on the console and launches:

```
  An ELMER update is waiting: 1 commit, latest "Read the license instead of asking for it"
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

## On Windows

ELMER is a Python program and almost none of it cares what it runs on. The
handful of things that do now live in one module, `elmer/host.py`, rather than
as platform tests dropped into whichever file needed one - which is how a
program ends up half-ported with nobody able to say what the Windows path
actually does.

```
powershell -ExecutionPolicy Bypass -File install.ps1
.\elmer.cmd
```

The execution policy on a Windows client defaults to Restricted, which is why
the first part is not optional; it applies to that one command and changes
nothing about the machine. The installer builds a virtual environment in
`.venv` and puts Flask, Pillow and reportlab in it. `-Shortcut` adds a Start
Menu entry, `-Serial` adds pyserial so the Lab can talk to a NanoVNA.

Three differences are real, and are named rather than papered over.

**Stopping is not the same operation.** The Exit button and an applied update
both hand control back to `./elmer.py`, which is the only place that decides
between stopping and coming back on the new code. On the Pi that is a SIGINT
to itself. Windows has no such delivery - `os.kill` there does not raise
anything, it terminates the process, which would take the restart decision
with it and leave an update half-applied. So Windows uses
`_thread.interrupt_main`, and because that lands between bytecodes rather than
interrupting a blocked `accept`, one throwaway connection to ELMER's own port
is what wakes the serving loop up to notice.

**A serial port has a different name.** `/dev/ttyACM0` on the Pi, `COM3` on
Windows, `\\.\COM10` once there are ten of them. The endpoint behind the VNA
panel opens whatever it is handed, so it is a gate rather than a hint: it asks
what a port is called on this machine before touching a file.

**The kiosk is not ported.** It finds the browser it started by reading
`/proc`, signals it by pid, and expects an X or Wayland session - a Pi with a
touchscreen bolted to a bench, not a portability gap to be papered over.
`--kiosk` on Windows says which of those it is and serves normally.

Poppler is not on a Windows machine by default, so the NIFOG channel reader
cannot read its PDF until `pdftotext` is on PATH. The installer checks and
says so; everything else works without it.

`tests/test_host.py` passes on both, and forces each machine's rules on the
other - a rule only ever run where it was written is a habit rather than a
rule.

## Requirements

Python 3.11 with Flask and Pillow, plus `pdftotext`, `pdftoppm` and `pdfimages`
from poppler-utils for rebuilding the pools. All present on Raspberry Pi OS;
on Windows `install.ps1` fetches the Python side and names what is missing.
Serving needs no network; only the propagation dashboard reaches out.

## License

ELMER's own code and artwork are under the
[PolyForm Noncommercial License 1.0.0](LICENSE) — free for personal study,
hobby and amateur use, for clubs, schools and other noncommercial
organisations, but not for commercial use. Note that this is deliberately not
an open-source license in the OSI sense.

The question pools and rule text under `data/` are *not* covered by that
license and are not this project's to relicense: the FCC pools and 47 CFR
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
