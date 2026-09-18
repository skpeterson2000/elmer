# ELMER — design notes

This is the long document: why ELMER works the way it does, section by
section, with the numbers checked and the decisions argued. It began as the
README and outgrew the job; the [README](README.md) is now the one-screen
version - what it is, what it looks like, how to install it, what it needs,
its license and its status - and everything here is linked from it as *the
reasoning*. Nothing was cut in the move. If a section here disagrees with
the program, the program is right and this is a bug: say so with **Report a
problem** on the dashboard.

A study assistant, progress tracker and game for the radio operator
examinations of the United States — built for the amateur radio community
first, and serving the commercial operator community with the same program.

For the amateur: the current NCVEC pools for **Technician, General and Amateur
Extra**, every question and every figure, with the FCC's own rule quoted
wherever a question turns on one. For the commercial operator: the FCC's
**Element 1** (Marine Radio Operator Permit), **Element 3** (General
Radiotelephone Operator License) and **Element 8** (Ship Radar Endorsement)
pools, complete and on the same footing — the same study engine, the same mock
exams built to the real blueprint, the same explanations, the same game and
the same hall. Alongside both, a live propagation dashboard and a lab of the
calculators the exams actually test.

It also runs a **tournament**: the same questions as a race, for one person
against practice opponents, for a table of eight joining by QR code from their
own phones, or for a hall of up to a hundred tables scored against each other
from one additional Raspberry Pi.

The browser is the display, not the destination: ELMER is a program running on
the Pi, drawing its screens there. Open it on the Pi itself, or reach the same
running program from a phone or laptop on the same network.

```
git clone https://github.com/skpeterson2000/elmer.git
cd elmer
./install.sh           # installs what is missing and nothing that is not
./elmer.py             # serve; open it from anywhere on the network
./elmer.py --kiosk     # serve, and open full screen on this machine
#   ELMER is on http://192.168.1.5:5000
```

(`install.sh` uses apt on Raspberry Pi OS, which refuses `pip install` under
PEP 668, and a virtual environment elsewhere. On Windows, see *ELMER on
Windows* below.) The pools ship built, so it runs straight from a clone — no
build step. The dependencies are Flask, Pillow and reportlab; everything
else, including the QR encoder, is the standard library. poppler-utils is
wanted only to rebuild the pools or read PDFs on the library shelf, pyserial
only to talk to a NanoVNA, and the self-check says which is missing.

**License:** [PolyForm Noncommercial 1.0.0](LICENSE) — free for personal
study, clubs, schools and other noncommercial use; not for commercial use;
deliberately not an OSI open-source license. Details at the foot of the page.

## Fidelity

The word carries different weights in different places. Here it means three
things, and each is checked rather than promised.

**Accuracy.** The pools are the released documents, reproduced verbatim — the
NCVEC's `.docx` and the FCC's `.pdf`, parsed by the program and validated on
every build: the question counts must match the published syllabus, every
question must have four choices and exactly one keyed answer, every section
must be populated and every referenced figure must exist, or the build stops
rather than ship a pool with a hole in it. The amateur pools carry every
correction the Question Pool Committee has issued since release, because that
is what is on the test. Where a question cites a rule, the rule is quoted from
47 CFR, not paraphrased. Every explanation is written by hand or quoted from
the regulation; no explanation is machine-generated, and where none exists
the program says so and invites your own rather than inventing one. What the
program measures — your mastery, your exam odds, a question's difficulty, the
propagation forecast's own error against the ionosondes — it reports with the
sample size beside it, and says when it does not yet know.

**Thoroughness.** All 2,475 questions across the six pools; all 43 diagrams; a
concept note for every one of the 294 syllabus sections; the rule text for
every citation; the band plan in full; the calculators the exams test; a
library of your own manuals, indexed to the page; the repeaters, parks and
summits of a region packed for somewhere the internet is not — on one
Raspberry Pi, with no network needed once it is installed. Both communities
get the whole of it. The commercial pools are not a bolt-on: they are the same
program pointed at a different examination, gated by nothing an amateur
licence says, because an Extra ticket says nothing about readiness for a GROL.

**Usability.** It runs from a clone with no build step and no configuration,
opens the same way on every board whatever the hardware is doing underneath,
and puts a phone in the game by pointing it at a screen. A club evening needs
one Pi and nobody to set anything up; a hall needs one more, and the tables
find it by themselves. What the program has to say about its own working goes
to the log — the dashboard shows the tail of it — not onto the study screens.

**What leaves a unit.** Your progress lives in `data/elmer.db` on the unit and
nowhere else. The program reaches out for what it needs to stay current — space
weather, the ionosonde record, the rule text, the pools, its own updates, the
local coordinator's band plan for the QTH's state, the weather at a golf
course from the National Weather Service (the course's, not yours), the POTA
spot feed sampled every twenty minutes while the unit is on, and a park's or
summit's record from POTA and SOTA when one is picked — and for what you ask
it to look up, a callsign or a place; nothing about you travels with those
requests beyond the thing asked. The moon, the meteor calendar and the sun come
from a clock and arithmetic, and fetch nothing. Two things can be sent
*from* a unit, and both are entirely voluntary: a **problem report**, when you
press for it, and a **weekly field report**, when you switch it on — each
written to disk and shown to you before it goes, each redacted of callsign,
QTH and addresses, each to KC9SP@arrl.net — by the drop, with nothing of
yours on it, or through your own outgoing-mail settings if you would rather.
Nothing is sent that you have not either pressed for or switched on and been
shown the contents of. See *Mail home*, below.


---

## What's in it

### The question pools — 2,475 questions, all of them

| Pool | Element | Questions | Exam | Pass | Release |
|---|---|---|---|---|---|
| Technician | 2 | 409 | 35 | 26 | 2026–2030 pool, current to the NCVEC's revision of 19 Feb 2026 |
| General | 3 | 423 | 35 | 26 | 2023–2027 pool, current to the NCVEC's 6th revision, 4 Feb 2026 |
| Amateur Extra | 4 | 599 | 50 | 37 | 2024–2028 pool, current to the NCVEC's 4th revision, 4 Feb 2026 |
| Marine Radio Operator Permit | 1 | 144 | 24 | 18 | FCC pool of 2009, the one in use |
| **GROL** — General Radiotelephone | 3 | 600 | 100 | 75 | FCC pool of 2009, the one in use |
| Ship Radar Endorsement | 8 | 300 | 50 | 38 | FCC pool of 2009, as revised 6 Mar 2024 |

All 43 diagrams are included and pinned to the questions that reference them —
the Technician and General schematics, the Extra figures as vector SVG, and the
FCC circuit and radar drawings extracted from the official PDFs.

The amateur examinations are given under **47 CFR Part 97**, and the pools
cite it question by question. The commercial ones are given under **47 CFR
Part 13**, *Commercial Radio Operators* — which licence is needed for what, and
what each examination element covers — with the subject matter drawn from
**Part 80**, *Stations in the Maritime Services* (the ship stations an MROP
operates and a GROL maintains, watchkeeping, distress, the radar of Element 8)
and **Part 87**, *Aviation Services* (the aeronautical stations the GROL is
also the licence for). The FCC's commercial pools carry no citations of their
own, so where a commercial question turns on a rule the concept note for its
section names the part, rather than a paragraph being quoted beside the
question as it is for the amateur pools.

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
pools. The class can be typed in as well as looked up, since the FCC's files
hold the FCC's licences and nothing else, and a Canadian or British operator
has a perfectly good callsign that resolves to nothing.

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
   to mistrust, and each one links through to the full section. The citations
   are the NCVEC's own, printed in the amateur pools; the FCC prints none in
   the commercial pools, so for those the rule lives in the section's concept
   note (Parts 13, 80 and 87) rather than beside the question.
3. **A concept note per syllabus section.** All 294 sections across the six
   pools have one: a short explanation of the underlying idea plus the key facts
   and formulas, written by hand. Sections whose concept is interactive link
   straight into the matching Lab tab.
4. **The syllabus context**, always &mdash; which section and subelement the
   question belongs to.

No explanation is machine-generated. A subtly wrong explanation teaches the wrong
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
  callsign once and ELMER reads the FCC's record: license class, grant and
  expiry dates. The band plan then shows *your* privileges rather than a
  class you picked from a list, and the page tells you how long the license
  has left — flagging the last 90 days, and the two-year grace period after
  expiry during which you may not transmit but can still renew without
  re-testing. Only the class, the dates, the FRN and the town are kept; the
  name and street address on the record are public but ELMER has no use for
  them, so they are discarded. 47 CFR 97.301 and 97.305 per class. Anything
  outside your class is hatched out on the bar and marked "no" in the table,
  so the legal picture is never in doubt.

  Where the record comes from: the FCC itself. Its lookup API is gone, but
  the Universal Licensing System still publishes the whole database every
  Sunday, one zip per service — amateur, GMRS, the commercial operator
  licences — for anyone who will go and get it, and `elmer/uls.py` does.
  The first time a call of a service is saved, that service's file is
  fetched and read into an index on the unit (the amateur one is 200 MB;
  a unit that never meets a GMRS call never fetches the GMRS file), and
  from then on every callsign of that service is answered from the FCC's
  own record with no network at all. The file is fetched again only when
  the FCC has posted a newer one, checked by asking its date. Until the
  amateur file has been read, callook.info — which reads the same file —
  answers amateur calls; GMRS and commercial calls have no stand-in and
  say the file is on its way. `ELMER_ULS=off` stops the fetching on a
  metered connection; the Station panel says which files the unit holds.

  The same door answers every licence a person holds: a GMRS call
  (WRxx000) gets its dates and the fact that GMRS has no grace period; a
  commercial call gets its class — GROL, MROP, GMDSS, the Radiotelegraph
  certificates — and whether the Ship Radar endorsement is on it, and a
  GROL is for life. And because the files carry the FRN, the record for
  one call lists the other tickets under the same FRN, which is what the
  dead API used to be asked for.
- **Activity is convention.** 160 segments across sixteen bands, coloured by
  what happens there — CW, digital, phone, image, beacons, satellite,
  repeaters, FM simplex, calling frequencies. None of it is enforceable, but a
  signal in the wrong place is what people complain about.
- **The reach map knows your antenna.** It used to score every cell by the
  sky alone, and so a low inverted V and a dipole half a wavelength up
  drew the same map, which is not what a log book says. The difference is
  the takeoff angle: a path 300 km out leaves at about 70 degrees, one
  2500 km out at about 8, and a low horizontal wire puts almost all of its
  power straight up while a high one has a lobe near 25 degrees and a hole
  overhead. So each cell is scaled by the antenna's own elevation pattern
  (`patterns.elevation`) at the angle its first hop needs (`patterns.hop_km`
  inverted), in decibels against the antenna's best angle, 18 dB down being
  nothing (`propagation.takeoff_weights`). The map opens on the antenna
  the Lab remembers - kind, height and power ride along in the Lab's own
  memory of the last design - with the panel's controls to look at another;
  nothing is stored twice. The ground is real: where the frequency is
  known, `patterns.elevation` adds the image with the Fresnel reflection
  coefficient of the soil named - average pastoral ground by default, poor,
  good or salt water by choice - so a ground-mounted vertical over ordinary
  soil peaks fifteen to thirty degrees up, the pseudo-Brewster angle every
  measurement shows, and reaches the horizon only over the sea; a low wire
  keeps its null at the horizon. And where the wire's heading is known, the
  element's own pattern toward each bearing is in the weight too
  (`patterns.field_toward`): the half-wave dipole's pattern in three
  dimensions, nothing off the ends along the ground and everything
  overhead, which is what makes a low wire an all-round NVIS antenna; an
  inverted V half way to round; a Yagi its forward lobe. The Lab's own
  elevation plot draws over the same average ground at the frequency on
  screen, so the two agree. It is the two-ray model with a real reflection
  coefficient, not a full model of the wire over the soil - the shape and
  the trend a log book agrees with, which is what the map is for, and real
  terrain still moves the lobes.

  NVIS is decided by one number that the antenna cannot change: the
  critical frequency straight up over the station. A band above it gets
  nothing back from overhead whatever the wire, and the near zone is a
  hole out to the skip - which is what a low inverted V on 40 m at three
  in the morning finds, foF2 near 3 MHz and the skip twelve hundred
  kilometres, and looked, on the map alone, like the antenna being
  ignored. So the map now says it in words whenever the antenna is a low
  one or the NVIS switch is on: the critical frequency over you, whether
  this band comes back from overhead, the skip if it does not, and the
  highest band that is under the door now (1.15 times foF2, the secant of
  a near-vertical angle). The switch itself sets a wire a tenth of a
  wavelength up and brings the map in to the one-hop window round the
  station, where NVIS lives - a way of asking the question; the line is
  the answer. On the round trip the panel also says what
  the far end needs to answer: the gear in a sentence, and in the US the
  lowest class for phone and for CW on that band (`bandplan.far_end`);
  outside the US the licence line is silent, because the map does not know
  whose country a cell is in and must not guess.
- **One colour a band, everywhere.** 20 m is the same green on the band
  buttons, on the heading, on the reach map's ramp, on the Lab's chips and
  its frequency meter, in the propagation outlook, on the home page's
  "good now", on the path ladder, and on the printed chart — so that the
  colour comes to mean the band the way a callsign comes to mean a person.
  The hues run with frequency, red at 160 m through yellow and green to
  blue at 10 m, then violet and pink for VHF and UHF, so a band not yet
  learnt can be placed by its neighbours; 11 m (CB) is grey and borrows no
  amateur band's hue. Nobody publishes such a scheme — the FCC's rules
  carry no colours and the ARRL chart colours by emission, not by band —
  so this one is ELMER's own. The colour is never the only cue: the name
  is always printed beside it.

  The palette lives in `elmer/palette.py` and nowhere else. The page head
  writes it out as CSS custom properties (`--band-20m`, `--band-20m-rgb`)
  and as `window.BAND_PALETTE`; a page prints a band with `bandTag()`,
  `bandSwatch()` or `bandStyle()` from `elmer.js`, and the PDFs take the
  same hue darkened for paper from `band_colour(name, ink=True)`.

  Four families, one a kind of thing, so a colour says what it is about
  before its label is read. **Bands** each have a colour of their own, chosen
  so that neighbours are far apart - warm beside cool, light beside dark,
  the way a box of coloured pencils is told apart, with no order in the
  hues to be read as anything. They used to run the rainbow in frequency
  order, which put the nearest colours on the adjacent bands, the very
  ones that have to be told apart, and made the row of band buttons read
  as a pride flag on the dashboard. Chosen against simulated red-green
  and blue-yellow colour blindness so that the eight bands everyone uses
  (160, 80, 40, 20, 15, 10, 2 m, 70 cm) stay apart by hue and lightness
  both, every adjacent pair close to 30 units apart in CIELAB or more, and every
  one reads on the dark panel at 4.5:1 or better. **Modes** — what happens on a band, CW
  the same colour on every band — are the pastel family: the same hues
  lightened and softened, so a mode reads as a softer thing than a band
  even before the label. **Licence classes** are the earth tones, the
  strata a person climbs through. And one **attention** colour, the
  safety orange of ANSI Z535 — the one published convention here — for
  the thing that must be found at once and nothing else: the "you are
  here" on the reach map. Fluorescent is not a family; seventeen neon
  hues on a dark screen tire the eye and lose the lightness differences
  the colour-blind depend on.

  Convention and law do not share their edges, so each segment is answered with
  three states rather than two, and the reason is written beside the row. The
  IARU Region 2 plan puts SSB on 20 m from 14.112 while 97.305 permits no phone
  below 14.150, so an Extra is told **14.150–14.230** - the part of that SSB
segment that lies inside Extra phone privileges - and, in words, *"no license
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

**The other radios in America.** Most two-way radios in the country are not
amateur radios, and below the amateur bands the page gives FRS, GMRS, MURS
and CB the same treatment: the channels exactly (the 22 shared FRS/GMRS
channels with each service's power on each, the eight GMRS repeater inputs,
the five MURS channels, all forty CB channels with 23-25 in their historical
order), who may use them and under what — no license at all for FRS, MURS
and CB, authorised by rule under 47 CFR 95.305; GMRS's $35 no-exam license
that covers the whole immediate family and asks for a call sign every
fifteen minutes — and the conventions marked as conventions (channel 19,
462.675 with the travel tone) apart from the one that is law (CB channel 9,
95.931). Every figure is copied from the section of Part 95 cited beside it
and `tests/test_personal.py` pins them to the rule, not to the module.

Below the tables is the paragraph an amateur with a dual-band handheld is
owed and rarely given. The radio will tune 462.675; the rules say it may
not transmit there — Part 95 is equipment-certified (95.335), no radio that
can also do amateur frequencies will be certified for GMRS (95.1761(c)),
and 95.935 names amateur transmitters on CB as a violation in so many
words. Listening is legal and always was. In an emergency, 97.403 and 97.405
apply completely, and the services meet you halfway: every FRS, GMRS and CB
channel must give emergency traffic priority. Then the order to try things
in, which the rules permit but do not give: your own bands with your own
license; then the personal-radio channels where the humans are — channel 9
and 19, 462.675, FRS 1; and a public-safety frequency last, for immediate
danger to life when nothing else has answered, because a dispatch channel is
somebody's working frequency and a call on channel 19 reaches a person with a
telephone without stepping on a response already under way. Carry a radio
licensed for the service you mean to use it in; extenuating circumstances
are exactly that.

**Two whips as a dipole.** The Lab's antenna calculator knows the hamstick
dipole — two mobile whips back to back on a dipole mount, the antenna of the
paved car park, the condo balcony and the attic, because it needs no ground,
no radials and no car body. It works the pair's efficiency out from the same
short-monopole arithmetic the single whip uses (twice the radiation
resistance, the two coils in series, nothing else) and prints beside it what
Virginia RACES measured in 2001–02: a pair at 20 ft about 10 dB below a
full-size dipole on 40 m, 18 dB on 75 m, 6 dB below a G5RV on 20 m, and
2:1 bandwidths near 100/40/20 kHz — the Q in `patterns.py` is worked back from
those, so the SWR curve comes out where the air did. It also says the
uncomfortable thing plainly: the feedpoint is the radiation resistance plus
the loss, so a pair that matches 50 Ω coax with nothing in between is telling
you the loss is most of the feedpoint. The mast-isolation and coax-choke
recipe from the same sheet is in the notes, the printed sheet carries it, and
Make Contact offers the pair to anyone who ticks a whip and no wire. The
fan-dipole step is there too: four pairs at 45° on one hub and one coax — the
Octopus, N1GY's QST design of December 2007 as built and documented by KE0CP
— with the hub wiring (hot elements on shoulder washers, grounded ones to the
box), why it needs no switching, and the reminder that each pair points its
own way.

A bought whip has no length to cut, but it has a stinger to slide, and the
maker printed a chart. `whipbuild.LAKEVIEW_CHARTS` holds Lakeview's exposed-
whip-length charts for the nine HF Hamstick models, read off their instruction
sheet, and the Lab's advice panel and the printed sheet say where to start:
"the #9140 at about 37.8 in for 7.200 MHz, 1.5 in per 100 kHz, shorter for
higher" — between the plotted points only, never past the edge of the chart,
and always with the sheet's own rule in front: *do not cut the whip first*;
find resonance fully extended, then slide it in; never let the whip run into
the close-wound coil, where it shears the wire through the rod. The same
sheet's shunt-capacitor matching table (450–600 pF on 40 m, and so on) is
there for the single whip on a vehicle that will not come under 1.5:1, and its
mounting rules — high and central, bumper poorest — are in the whip's advice.

The rest of the program knows these channels too. The Lab's "may I?" and RF
exposure answers name the channel rather than doubting the number — 462.55
MHz is "FRS/GMRS channel 15, FRS 2 W ERP (no license) / GMRS 50 W (GMRS
license)", not "check the frequency" — and the antenna designer will cut a
J-pole for channel 20 or a whip for channel 19, assuming local FM or a few
miles of road rather than DX.


## Mail home

Reports go to **KC9SP@arrl.net** — an arrl.net forwarder, chosen for exactly
this: it forwards to its owner's inbox and is filtered on the way. Every
subject a unit sends begins **[ELMER]**, put on by the sending path rather
than left to each caller, so one filter at the far end catches all of them —
the first ones landed in a spam folder. ELMER carries no mail account.

A report leaves a unit by one of three doors, and which one is expressed by
what you set up rather than by a switch beside it:

- **The drop.** With nothing set, a report goes to one public address — a
  Google Apps Script the project's owner deployed from their own account —
  and the script mails it on, or files it in a GitHub folder, or both. Every
  credential for that lives on the script's side; the units know only the
  URL, and the URL can only put things in, which is why it can be public. A
  Pi in a club hall, with nobody to type an app password into it, goes home
  this way. The script and its five-minute setup are in
  [`tools/report_drop.gs`](tools/report_drop.gs); a club running its own
  points its units at it with `data/drop.json`.
- **Your own outgoing mail server** — the SMTP host, port and login you
  would give any mail program — kept in `data/mail.json` on that unit
  alone, readable by nobody else. Filling it in is the choice: reports then
  go through your account and not by the drop, and *Forget* goes back.
- **By hand.** With neither — or when the door that is set refuses — the
  report is still written, and the page gives you *Open it* and *Save it*
  beside the file's name and the address as a mail link, so it can be read,
  copied or attached from the screen it was written on. A path on a kiosk
  with no file manager is a fact; these are things a person can press.

Whichever door, the report is the same text, written to disk first and shown
before it goes. The settings, a test message down whichever door is open,
and both reports live under **Mail home** on the dashboard's update panel,
local screen only.

`data/mail.json` and `data/drop.json` are ignored by git and must stay that
way: one holds a mail password, the other a club's own address. If you fork
this and commit from a unit, check `git status` shows neither. A password
that reaches a public repository is public from that moment, whatever is
done to the history afterwards — revoke it and make another.

Two things can go:

- **A problem report**, when you press for it. The press opens a place to
  say what happened — the one thing the log cannot — and a box to put your
  callsign on it so a reply can reach you; both optional. Then the report is
  written: your words first, then versions, the self-check, the recent errors
  and the tail of the log, with your callsign, QTH and network addresses taken
  out unless you ticked the box — a callsign typed into your own words
  included. It is shown so you can read it, and sent only by a further press,
  with the first line of what you said as its subject.
- **The field report**, once a week, if you switch it on — and it is off until
  you do. The switch says exactly what it carries: which build and machine;
  how the forecast did against the sondes this week, by lead and by sky, with
  persistence beside it as the yardstick; the correction this unit has
  learned and whether it is applying it; how many rounds of each game —
  hall, tournament, shootout, CutThroat, golf — and study answers there
  were, as counts, so the project can see which parts of the program are in
  use; how each question went for the people who met it for the first time
  (its id, how many, the miss rate and a time index — the numbers the
  difficulty measure is made from, so difficulty can be rated across every
  unit rather than one; no names); the errors and warnings, counted, with
  the last few in full — all redacted the same way. Every report is saved under
  `data/reports/` before it goes, *Read what it would send* shows the next one
  now, and *Send one now* does not wait for the week. This is the "report its
  adjustment factor back to us" that the forecast work was built around, done
  the only way it should be: by the operator's hand, with the contents on the
  table first.

## When it goes wrong

Both halves of ELMER report faults into one place. The server logs unhandled
exceptions with tracebacks; the browser catches JavaScript errors and unhandled
promise rejections and beacons them to the same log, so a fault in a page does
not stay in that page. The log rotates at 5 MB, keeping five. Every start
stamps the build, the python and the platform into it, because a log that does
not name its version costs whoever reads it the first hour.

Three things keep it readable on a hall night, when twenty tables and their
phones poll this unit every second or two. **Polls are counted, not written**:
a quick, successful request to one of the state-polling endpoints is a
heartbeat, and eighty thousand heartbeats an hour used to rotate the evening's
real lines away in about forty minutes; they are tallied instead, and one line
every ten minutes says how many, from how many clients, and how slow the
slowest was. Anything that failed or took long is still written as itself.
**Repeats collapse**: a table pointed at a net that is not running is told 404
every fifteen seconds all night; the first is written and the rest of the
minute is one line saying how many — and a refusal one of ELMER's own
components asked for and handles is INFO, not a warning. **A fault gets a
reference**: an unhandled exception is logged as `UNHANDLED … ref e-3f9a`, and
the same tag goes on the page and in the JSON, so "it said e-3f9a at about
nine" finds the traceback in one grep. A thread that dies — the conductor, the
hall bridge, the GPS listener — is logged by name instead of printing to a
console nobody is watching.

A kiosk has no terminal, so the dashboard's Software panel has a **Recent
log** fold: warnings and errors, everything recent, or one fault by its
reference — served to the local screen only, because the log carries
addresses. Net control writes one line per table check-in, departure and
closed round, so the evening is on the record in words as well as numbers.

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
repeaters come from RepeaterBook under your own token or from TowerWitch
(set the QTH there with a token saved, or `--import-repeaters` before you
leave), and ground profiles are per-path with more paths than
anybody could cache. Set the QTH to the destination's grid square and every
answer - who is in reach, which way to point, what to try - is about there.

This works because a cached area now answers for anything inside it: a fetch
covering 800 km serves a question about 300. It used to match the radius
exactly, which meant a trip prepared before leaving was never found again,
since ELMER asks with a different radius for every band and antenna.

## The library: your own manuals, to the page

A radio's manual is three hundred pages and the thing you need from it at a
campsite is one line on one of them — the menu number for the CW pitch, the
range the tuner will match. ELMER cannot ship anybody's manual and would not
want to; they are the makers' and the ARRL's. What it does is read the copies
you already own, once, and afterwards answer *where does it say that?* with
the file, the page and the lines around it — from your copy, on this machine,
with or without a signal.

Copy PDFs into `data/library/` (or hand one over from a phone with *Add a
manual* on the Library page) and the next visit to **Library** indexes them:
`pdftotext` for the words on every page, the publisher's own bookmarks for the
chapters, `pdfinfo` for the title. The search box finds the pages that carry
every word you typed — quote a phrase to keep it whole — and shows each with
its chapter and a snippet, linked to open the book at that page. The book
opens *inside ELMER*, and ELMER draws the page itself — poppler renders it
on the unit, once, and keeps it — under an ELMER bar with **Back** (and
Escape), the page number, arrow keys and the edges of the page to turn it,
the publisher's chapters down the side, and — when you came from a search —
the hits in that book, each a tap away. It used to hand the browser's own
PDF viewer the file with `#page=N` on the end and trust it to open there:
Chromium on the Pi did, the Edge window on Windows loaded the file and
ignored the page, and a phone showed nothing at all. The browser's viewer
is still a button away (*Browser viewer*) for selecting text or searching
inside the file, and is what the reader falls back to on a unit without
poppler. The kiosk's browser has no tab bar, so a PDF opened on its own
would be a wall with no door. Under it,
*ELMER's topics in your books*: antennas, propagation, CW, digital modes,
repeaters, power, safety, rules, satellites, menus, test equipment — each
listing the chapters on the shelf whose bookmark titles use those words, and
the antenna calculator carries the antenna ones under its advice. `./elmer.py
--index-library` does the reading from the terminal; `--doctor` says what is
on the shelf and whether it has been read. Most radio manuals are saved with
the PDF "copying not allowed" flag set — both Yaesu manuals on the first shelf
were — and `pdftohtml` honours it by refusing the whole document, bookmarks
included, while `pdftotext` reads the same file without a murmur. ELMER reads
the bookmarks anyway: the flag is the publisher's request about copying their
text, and reading the chapter titles of a book you own, on your own machine,
to find your own page, is not that. The catalogue tells *no bookmarks in the
file* from *the bookmarks could not be read*, and says which.

Everything about it is deterministic, on purpose. The text is what
`pdftotext` read; the chapters are the bookmarks the publisher put in the
file; a search finds the pages that contain the words. Nothing is stemmed —
*tuner* does not find *tuning* — nothing is summarised, and nothing is
inferred, because a program whose numbers are measured does not start guessing
the moment it opens a book. Bundling a language model to "read the manuals"
was considered and declined for exactly that reason: on a Pi it would be the
first thing in ELMER that answers confidently past what it knows, and a wrong
menu number handed over with confidence is worse than none. A manual with no
bookmarks says so and search still reaches into it; a word that is not in the
text is not found. Page numbers are the file's own — the 47th page of the PDF,
which is not always what the publisher printed in the corner — and are
labelled as such.

The shelf and its index are yours: `data/library/` is ignored by git, so
nothing you own is carried into anybody else's checkout, and an index is
rebuilt whenever the file changes.

**A manual is evidence of a radio.** Nobody keeps the FT-991A's operating
manual for the pleasure of it. So each book on the shelf is matched against a
table of model names (`elmer/rigs.py` — Yaesu, Icom, Kenwood, Elecraft, Xiegu,
the Chinese handhelds, the GMRS and CB sets, and the books and analysers that
are not radios), and **Make Contact** starts from what the shelf says you have
— *"Ticked from the manuals on this unit's Library shelf: a Yaesu FT-991A
(all-mode set, HF, 6 m, 2 m, 70 cm, 100 W), a Yaesu FT5D (handheld, 2 m and
70 cm, 5 W) … Untick what is not with you."* A model the table does not know
is named as unplaced rather than guessed from the maker.

The shelf is one and shared — a manual is useful to everyone at the table —
but whose radio it is for is a fact about a person, so each person marks the
books that are **mine** on the Library page (a manual you add is marked yours
to begin with), and Make Contact reads only those once anyone has marked any
— unless the marked books name no radio, in which case it falls back to the
whole shelf and says so. Nobody's marks are shown to anybody else.

The Library page opens with the search box, then **ELMER's topics in your
books** — the door — and the shelf itself below as the deeper look. Each
topic lists its pointers in columns, whole books first, eight before the rest
fold. A book with no bookmarks — a one-page fact sheet never has any — still
points from there and from the Lab: its title, or failing that its file name,
is read as its one chapter heading, so "Hamstick Dipole Fact Sheet" appears
under Antennas as a whole book, and a sheet whose title and name say nothing
appears nowhere. Search
reaches into every page of every book regardless — except a **scan**. A PDF
whose pages are pictures with no text under them is marked *a scan — nothing
for search to read* on the shelf, so an empty result reads as what it is
rather than as the word not being in the book. It opens and reads like any
other; ELMER does not OCR it.

### The User's Guide, on the same shelf

ELMER's own manual is a book on the operator's shelf, not a file somewhere
a kiosk cannot reach - and a file at the top of the checkout too, beside
the README, for the person who has just unzipped it and would not think to
look on a shelf: built from `USER-GUIDE.md` by `elmer/manual.py`
into a PDF with real bookmarks, one a chapter, a table of contents with
page numbers, the screenshots in `docs/screenshots/guide/`, and the build
in the footer, and placed at `data/library/ELMER-Users-Guide.pdf` when
ELMER starts if it is missing or the text has changed. The Library indexes
it as it would any book, so the search finds it, the topic map places its
chapters, and the reader opens it to the page. The markdown is a small
subset - title, chapters, sections, paragraphs, bullets, notes, pictures,
bold, italic, code - so the file reads plainly on GitHub and renders here
with reportlab alone.

It can be taken off the shelf like any other book, and it comes back when
ELMER next starts; the doctor has a line for it and a *Fix* that puts it
back sooner, because a guide deleted by accident on a kiosk is a guide
nobody can find again. An operator who does not want it ticks *I decline
the User's Guide and any future updates to it* on the Library page, and it
is taken off and never put back until they untick it. That is a setting of
the unit (`manual_declined`), not of whoever is signed in, because the
shelf is shared. The README says the same in a paragraph, and the guide's
front matter carries the pre-release notice: features will continue to
appear and be refined, and what a feature does today may not be precisely
what the final version does, where that latitude exists.

## Showing the working

ELMER does not ship antenna plans. There are plenty of those, and a plan
somebody follows teaches them one antenna. Under every dimensions table is a
fold marked *where these numbers come from - so you can do it without ELMER*,
and inside it the arithmetic is done in front of you:

```
983.6 / 14.200 MHz     69.27 ft   one wavelength; 983.6 is c in feet per microsecond
69.27 / 2              34.63 ft   a dipole is half a wave, fed in the middle
x 0.9485               32.85 ft   velocity factor - a wire is not free space
468 / 14.200 x 0.9984  32.91 ft   what the table prints, and why it differs
```

Three steps produce every wire length in amateur radio, on any band. The last
row exists because being caught out by your own program is worse than not
being taught: 468 is 983.6 / 2 x 0.95 rounded up, it lands 0.7 in from the
line above it, and saying so is worth more than hiding it. Every figure shown
can be checked on a pocket calculator - the constants are displayed to the
places that reproduce the figures beside them, which was not always so: a
reader who checked the working found the factor shown to three places and
the result computed from four, and the page's own demonstration of rigour
off by a hundredth. It is shown to four now.

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
holds 2:1 across about 504 kHz (#14, the default, 532); the same dipole in 1 in copper pipe holds it
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

**Reaching somewhere in particular.** Most real needs have a destination -
a relative's town, the net's location, the club across the state - so the
page opens with one optional field: a callsign (the FCC record has its
grid), a grid square, or a town and state. Blank, the page is what it
always was. Filled, a card above the list says how far and which way (and
the back bearing), whether each end is in daylight or the dark, and what is
between: within fifty miles or so it asks the ground - the terrain profile
the path tool uses - whether two head-high antennas can see each other, and
names the hill if not; beyond that the path is the ionosphere's, read at
the midpoint where a hop is reflected, and the card says which bands carry
it *right now* and why the others do not ("the skip zone reaches 585 km and
the path is 255 - too close for this band"). Then **the approach**, in the
order an Elmer would try: line of sight or a repeater across town; on HF
the bands that carry it that the license class may key up, fewest hops
first, each with its mode and which way to hang the wire - broadside to the
bearing for a hop, low for straight up and back; a handheld alone across
the state is told so, pointed at a linked system, and shown which HF band
would do it if one can be borrowed. And when, if not now: both ends in the
dark is 80 m and 40 m's hour, both lit is 20 m and up's, one of each is the
awkward case. The words stay measured: what the numbers say is said as
such, and the card ends by noting that the band that carries it is the
science and working it is the art. `elmer/pathto.py`; `tests/test_pathto.py`
stands the ionosphere and the ground in and reads the answers.

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

The gear list is the radios America actually carries. An all-mode VHF/UHF
rig has its own tick — the shelf sets it for an FT-991A, IC-705, IC-9700 and
their kind — and with it comes the card the FM boxes never earn: **144.200
USB**, the 2 m weak-signal calling frequency, with 50.125 and 432.100 beside
it, read from the band plan so the two pages cannot disagree; lay the antenna
horizontal, because the people listening there have beams and a vertical
costs 20 dB against them. The shelf ticks the *antenna* too: a Hamstick
tuning sheet, the whip-dipole fact sheet or the Octopus deck on the shelf is
evidence of mobile whips, so "HF with a vehicle whip" is ticked and the
sentence says "Hamstick whips (mobile whip antennas)" — once, however many
sheets there are. Beside the amateur
kinds are a GMRS or FRS radio, a MURS radio and a CB, each with its own card
when ticked: FRS/GMRS channel 20 with the 141.3 travel tone then 1 and 16,
the repeater input 5 MHz up for a licensee, and "say EMERGENCY, not Mayday"
because 95.1733 reserves the word; MURS 154.570 and 154.600 first, where the
farm base with the antenna on a pole is listening; CB channel 9 then 19, and
38 LSB if the set has sideband. With no gear ticked at all the FRS/GMRS and
CB cards are still offered, because the radio in the next car is one of
those far more often than it is ours. A handheld with no GMRS radio beside
it gets a different card: your radio hears those channels, listening there
is legal and tells you who is within a mile, and transmitting there is
97.403 territory and nothing less. The library shelf ticks these too — a CB
manual ticks CB — and if the books a person marked as theirs name no radio,
the poll falls back to the whole shelf and says so rather than vanishing.

The odds are words rather than numbers, because numbers there would be
invented. And the last entry is 47 CFR 97.403: when life or property is in
immediate danger and normal systems are not available, an amateur station may
use any means of radiocommunication at its disposal. It is pinned to the
bottom on purpose - answering "how do I get a message out" with "declare an
emergency" is wrong for a flat tire, and the entry has to keep its force for
the day it is needed. It now carries the order to try things in — own bands,
then the personal-radio channels, then a public-safety frequency for
immediate danger to life and nothing else — which the rule permits and does
not state.

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

**Whose land it is.** Neither programme can give anybody permission to be
somewhere — POTA's own rules put the park's rules first, and the park's rules
are written by whoever owns the ground. So the page quotes what the
regulations actually say, section by section, from the eCFR with the edition
and the day it was read: the Park Service superintendent's power to close a
park to "a specific use or activity" and the 60 dB(A) rule on radios (36 CFR
1.5, 2.12); the Forest Service's prohibition on placing "communications
equipment ... or other improvement" without authorization, written for the
repeater on the ridge and not for a wire that goes home in your pack, though
the district's reading governs (36 CFR 261.10); the Corps of Engineers' rule
on structures, whose one exception — portable stands "not nailed or screwed
into trees" and gone by the end of the day — is the measure of a portable
station (36 CFR 327.20); and the refuge rule that a refuge is closed except
where it has been opened (50 CFR 26.21). The state codes are not carried and
not guessed at: the property manager is the authority. The pattern through all
of them is one sentence — ask, nothing driven into a tree, no noise, nothing
left behind, and a club outing is an event that needs a permit.

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

Above 50 MHz "what can I reach" is answered by repeaters, not by towns. Three
routes feed one list, and the list says which fed it.

The first is the operator's own RepeaterBook account. RepeaterBook's API is
open to approved programs, in two steps: the program's author applies once,
naming the User-Agent it sends (ELMER's is in `repeaters.py` and must not
drift from the form), and RepeaterBook lists it as an app; then each of its
users can make a token for that app on their own account page under *API
apps*. A person who pastes theirs into the Station panel gets the amateur and
GMRS machines for the state their QTH is in fetched straight from
RepeaterBook, under their account, again when the QTH moves to another state
and no more than once a month otherwise, or on the panel's *Fetch now*. The
token is theirs: it lives in their own settings on the unit, goes out to
RepeaterBook in the header RepeaterBook asks for and to nobody else, is never
written to a log, and a problem report redacts anything of its shape in case.

RepeaterBook's terms draw a line and ELMER stays behind it. Its data is
credited wherever the list is shown. What is fetched is one state's list,
kept on the unit for that operator's own use - RepeaterBook's own "more
likely approved" case is a private, non-commercial, narrowly scoped field
tool - and it is never served on to another unit, offered as a public search,
or bundled into a release; `data/repeaters.json` is ignored by git for that
reason among others. Building or refreshing another repeater directory from
it would need RepeaterBook's written permission, and ELMER does not. This is
the pattern for every service that offers a user-facing pathway: the person's
own credentials, entered by them, kept on the unit, spent only on that
service, within that service's terms; a file import is the fallback, not the
route.

The second is TowerWitch, the station's own repeater tool, which keeps a
RepeaterBook export with coordinates on it; ELMER reads what TowerWitch
writes rather than asking for the same list twice. The third is the saved
copy: `--import-repeaters` keeps what TowerWitch has, and copying
`data/repeaters.json` to another install works too. The saved copy is what
makes a machine without a token or a TowerWitch work; the other two are what
make anywhere work. Copying the saved list between your own units is fine for
what TowerWitch or an import put in it; what RepeaterBook fetched under your
token is for the unit it was fetched to. And ELMER tells the two kinds of
empty apart: no repeaters near you is a fact, no repeater data for where you
are is an errand, and it says which one it is looking at.

### The button to TowerWitch

ELMER and TowerWitch are two programs on one bench. ELMER's dashboard has
**TowerWitch** beside *Band conditions*
and *Lab*: greyed, with the reason in the tooltip, when TowerWitch is not on
the unit (or the page is being read from another machine - a desktop program
is not started from across the network); live when it is, saying *running*
when TowerWitch has announced itself from this machine, and starting it on
the unit's own screen otherwise (`run_towerwitch.sh` where there is one, the
Qt build on Windows). *Running* is read from the process table, not from
the broadcast: TowerWitch announces itself every few seconds and the
listener keeps the last announcement for ninety seconds, so the broadcast
alone would call it running for a minute and a half after it was closed,
and the button would refuse to start it. When the two disagree the log says
so and the process table wins. There is no button the other way. One was tried: it
opened a second copy of ELMER's page beside the window already on the
screen, which is worse than no button. Getting back to ELMER is closing
TowerWitch's window.

On Windows the button starts TowerWitch's Qt build, which wants its packages
(PyQt5 and a few small ones, TowerWitch's `requirements.txt`) in ELMER's own
Python: `install.ps1` installs them when a TowerWitch is found beside ELMER,
and the self-check has a **TowerWitch** line that says whether the button
could start it, with a Fix that installs them when it could not. On a Pi
the Tk build wants `python3-tk`, and the line says so.

**The bridge, the other way.** A laptop has no gpsd, so TowerWitch's Qt
build on Windows found no position at all. Now, when `gpspipe` is not there,
it asks ELMER on the same machine: `/api/gps` answers with ELMER's fix - a
receiver, or a phone streaming to it - and, when there is no fix, with the
QTH typed into ELMER, offered as such. TowerWitch takes the fix as it
comes and the QTH once, and says in its log which it was. One program owns
the position; the other borrows it, on either OS.

**And the two of them sleuth the GPS together.** Every fix says where it
came from - a receiver on the unit, TowerWitch's receiver over the network,
a phone streaming to the unit, another ELMER's receiver - and how good it
is: satellites used and seen, HDOP (gpsd's SKY, or the phone's GGA). ELMER
watches it steadily, a sample every twenty seconds, and reads the last
quarter hour: `/api/gps` carries a `sleuth` - the source in words, the
quality in numbers, how many times the fix has dropped, and advice only
when there is something to do. A phone that keeps dropping is told it is
not seeing enough sky where it sits: the dash or a window first, and if
that does not hold, that a phone is not going to be enough here and a USB
receiver on the dash is the move. A receiver short of satellites is told to
move the puck - roof, away from the metal and the heated glass. A fix that
has gone says whose it was and what will have done it. One weak look is not
a verdict. The self-check's GPS line carries the same words, and TowerWitch
shows them on its Location tab - the source on the status row, the quality
on the fix row, the advice under the table - whether it is reading its own
gpsd or borrowing through ELMER. So when the position goes, either screen
says which antenna to move.

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

**Your rating.** Two numbers a person can watch move: the speed they copy
at and the speed they send at, each the top rung of a ladder they passed.
Copying: five groups of five letters and numbers come at a plain speed - no
Farnsworth, a rating is at the speed it says - they type what they heard
and check; nine in ten right and the next rung is two words a minute
faster, short of that two slower, and the ladder settles when a pass has a
fail two above it (or at the ends, or after eight rungs). Sending: on the
keying pane, a line is shown, they key it on the straight key or the
paddle, the decoder is scored against it, and the speed is their own dit
on a straight key or the keyer's setting on a paddle. Both are kept with
the profile (`cw_rating`), shown on the page, and are what the CW games
set their level from.

**CW Baseball (built 2026-09-15; `elmer/cwball.py`).** In the Gaming
Center beside the others. The machine pitches through the table's speaker
(and into the batter's phone); the rules keep their own clock and the
screens drive them by polling, so there is no director. Two sides - the
cohorts when there are two, one cohort dealt out alternately, practice
players filling in - and innings chosen at the tile, one to nine; the
pitching starts at the operator's copy rating, a little under it, or where
the tile says, and comes a word and a half a minute faster each inning.
Batting: the pitch's text is not in the state while it is in the air; the
batter types what they copied and swings, on the phone or in the seat's
box; nine in ten right is in play, six in ten a foul, less a strike. In
play: the fielding side's next fielder is told the text and keys it back -
on the phone a hold-to-key button, at a seat the space bar as a straight
key, a paddle wired to either works - and Throw sends what the decoder
read; nine in ten clean is the out, a rougher send leaves the runner on,
under half is an error and an extra base; a throw never made in time is
the runner safe. Runners advance the hit's bases, the diamond shows them,
the line score the innings. The late innings pitch groups, words, a call
and a report, and then the exchange, and the full contact - CQ, answer,
reports, 73 - is the next thing to add to the pitching, along with a paddle
on the Pi's GPIO.

**The plan it was built from.** Two teams - the table's cohorts -
and the machine pitches. Batting is copying: a pitch is a transmission,
its speed, length and content rising with the level - letters, groups,
words, a callsign and a report, a full exchange - and copying it right is
a hit sized by the pitch: a group a single, a word a double, a callsign
with a report a triple, a full exchange at speed a home run; a miss is a
strike, three strikes an out, three outs the side. Fielding is sending: a
ball in play is a sending challenge for the fielding side - key the ball
back, or the play, clean and in time, on a paddle wired to two keys or the
Pi's GPIO - and a clean send makes the out, a botched one lets the runner
on, an error gives a base. Innings, runs on the board, a diamond with the
runners on it for the fanatics who will do code to watch a fake ballgame
play out, and the late innings faster and longer. The top pitch is a
contact: CQ from the pitcher, the batter answers with their own call,
report and name both ways, 73. Lives in the Gaming Center with the rest.

**A person on the mound (agreed and built 2026-09-17; `elmer/cwball.py`,
the presses in `elmer/app.py` under `/api/party/ball/`).** The
machine pitches because it was the only pitcher there was. With enough
people it should not be: a pitcher on the other side is given the code
to send and proceeds, and every fielder has a catch and a throw to make,
which is what baseball is. One to one is a turn copying and a turn
sending; with teams it is a batting order and a pitching rotation, and
everyone bats. The rule under all of it: catching is receiving and
throwing is sending. Batting is receiving too. The earlier rules left too
many people at the table with nothing to do on most plays; these give the
outfielder a catch and a throw of their own. If that load proves too much
for the room, the earlier approach is the one to back off to. These rules
supersede the built ones wherever the two differ. The machine stays on
the mound for a table without people enough for a pitcher, and pitches
under the same rules: at the little league levels it is a competent
pitcher, every pitch clean and in the zone, so the take is a thing a
newcomer learns rather than a trap; at the higher levels it adds variety,
the odd ball on purpose and a fist that is not always the same, so the
batter's ear matters against the machine as it does against a person.

*What a pitcher chooses.* A human pitcher chooses the pitch by choosing
how hard a thing they are willing to send. A normal pitch is handed an
easy patch of code - plain letters, a group, at the level's speed - and a
pitcher who wants something more extravagant is handed harder code to
throw it with: numbers and punctuation, cut numbers, 5NN for 599 and T
for a zero, prosigns run together where letters would do, the speed at
the top of the band, the spacing stretched or closed. The pitch's
difficulty is the pitcher's risk and the batter's problem at once, which
is how baseball has it: the nasty pitch is the one that gets away from
the pitcher for a ball or a wild pitch, and the one the batter has never
seen. So the choice needs no declaring; it is declared by what was asked
for, and the umpire judges the pitch against the text the pitcher chose
to be given. A harder pitch pays the batter more when it is hit, the way
the level's bases do now, because a hanging curve gets crushed. At the
top of the ladder the pitcher composes the text - a real exchange, in
their own words, inside the rules - and the batter copies whatever came:
a pitch nobody has seen, theoretically at least, which is the mound's
oldest privilege. The little league offers the normal pitch only, which is
simply sending it; the machine, when it pitches, climbs the same ladder
with the level.

*Pitching.* The prompt goes to the pitcher's phone and nowhere else -
never the big screen, or the batter reads it. "Send *My QTH is EL16hq*
at 18 WPM" is a pitch: a grid square is letters and numbers in one short
group, which is exactly the copy that separates the leagues. The pitch is
thrown, not streamed: the phone records the keying on its own clock, and
when the pitcher lifts off, the table plays it once through the speaker
with the fist exactly as keyed, so nothing on the hall's network can
stutter it. Little league judges content only, at any speed inside a wide
band. Major league prescribes the speed and holds the pitch to it, a tenth
either side; faster is an illegal pitch. The umpire is the decoder, and it
calls the pitch as thrown: clean, the right text, at speed, is in the zone;
clean but the wrong text, or off speed, is a *ball*; a pitch that does not
decode at all is *wild*, nobody can copy it, and the runners advance.

*Batting.* Everyone copies every pitch, fielders included, because a
fielder who was not listening cannot catch. The batter's copy is the
swing, and it is graded against what actually went out, not what the
pitcher was told to send: the pitcher's mistake is the pitcher's. Swing at
a pitch in the zone and copy it clean, and the hit is sized by the level
as now; a near miss is a foul, a strike until there are two, as the built
game already has it; a miss is a strike. Swing at a ball and connect - copy
exactly what the pitcher keyed, wrong letter and all - and it is a hit one
base bigger than the level pays, capped at a home run, because the batter
hit a pitch that was never meant to be hittable; swing at a ball and miss
and it is only a ball, since it was never a strike. The batter may also
*take* the pitch, sending nothing, having heard a stutter or a fist that
was not right, and bet on the umpire's call: take a ball and it is a ball,
four and a walk; take a strike and, in the majors, it is a called strike,
which is what standing there costs in the real game. In the little league
the take is free, so a nervous newcomer can listen to a few before
committing. The batter cannot know which it will be. That is baseball, and
it is the pressure on the pitcher that makes a clean fist worth having.
The phone shows two buttons after the pitch plays, copy it or take it, the
copy box under the first, and no hint of the call until the umpire speaks.

*The ladder, and the season.* The first pitch used to be three letters,
and a first pitch a newcomer cannot copy is a short game and no fun for
anybody. Below the majors a player now climbs a ladder of their own - a
letter, two, three, a group, a word, a call, the exchange, a contact - a
rung after three clean copies in a row, a rung back after three misses,
never in the first inning, which is played where they stand. The tiers cap
it: **T-Ball** is one letter a pitch, always; the **little league**'s
season climbs to a five-character play, a group; its **championship** to
eight, a word; the **majors** pitch by the inning as before and reach the
contact on their own. The rung is the player's, by name, and the unit
keeps it between games in `cwball-season.json` - a season - so proficiency
is built over weeks at the table rather than innings, and a player who
comes back next month starts where they left off. The play says when the
ladder moves; practice players are not remembered.

*Again, and the machine knows CW.* In the little league, from the first
inning, with the machine on the mound, the batter may ask for the pitch
again - three times at most, then the umpire says play ball. A button
asks; so does the phone's key, when what it has heard ends in **?** or
**AGN**, which is how a contact asks - and the machine answers **QRS** by
sending it again slower and **QRQ** by sending it faster, as a contact
would. That is the point of it: somewhere mid-count a newcomer keys a
question mark, hears the machine pitch it again, and has sent their first
thing that was answered; a real fist keys QRS and finds the game knows the
code. The ask is counted on the pitch, so the play says "after asking for
it twice, in code", and on the batter's record. The majors pitch it once,
and a person on the mound is never asked to key it twice.

*The key.* A phone's key is a straight key - hold to key - or a paddle,
two levers, dits left and dahs right, each a made element at the game's
speed, repeating while the lever is held, no squeeze. Chosen once and
remembered on the phone. A hand that has only ever known one should
compete with it, and can try the other here, where nothing is at stake but
the inning; the table's seat has had both since the start, the space bar
and the arrow keys.

*Fielding.* Where the ball goes the machine decides from the hit and a
little chance, and names it by position: a group is a grounder to short
or second, a word a line drive to third or through for a base hit, a call
a fly to the outfield, an exchange over their heads. The catch is that
fielder's copy of the same pitch. A fly ball copied clean is the out, and
the outfielder never has to key. A grounder copied clean is a ball in the
glove that still has to be thrown: the fielder keys the text to a baseman,
judged as a throw by the built game's scale, nine in ten clean - the
wrong text is a throw in the dirt, off speed or undecodable a wild throw
and the runners advance - and the baseman's copy
of that throw is the tag; bobble the copy and the runner is safe on an
error charged to the baseman. The clock is the runner: each base is a set
number of seconds at the level, so a grounder to short has to be fielded,
thrown and caught before the runner reaches first, and with a runner on
the double play is two throws, which is hard, which is right. Small teams
collapse the positions - with three a side one player is the whole
infield - and that is fine so long as the play is still named by position
and the same person is never asked to catch, throw and catch again on one
ball. Everyone copying every pitch gives each player a fielding percentage
for free, and keeps the shy player at second base as busy as the star.

*Innings.* A full play is pitch, copy, throw, copy - close to a minute -
so three innings is the default, and the late innings that already pitch
faster and longer become the seventh, eighth and ninth when a hall wants a
whole game. Between innings is where the wait belongs: the deck from
`elmer/trivia.py`, with a ham-and-baseball deck added for the ballgame,
the way every ballpark fills the break. The pitch itself waits on
nothing.

*The room's load.* A hall of a hundred tables is the design, not yet a
night that has been had; a virtual run was backed off for network load.
The phones poll their own table's Pi, every second during a live question
and every five otherwise, and tables poll the host every five, so the
steady load is phones per Pi, not answers; six phones on a table is
nothing and a hundred tables on the host is twenty requests a second. What
to do, in order: measure a real hall with the pace ledger before building
anything; jitter the polls by a random fraction of a second so a table's
phones do not fall into step; slow the live poll while a pitch is playing,
since nothing changes on the phone until it ends; and only then, if the
ledger says round close creeps, a grading queue that acknowledges a keyed
send at once and scores it behind the three seconds of Scoring that are
already there.

And the player's own device - phone, Pi seat or PC - holds its result
until its part in the play is decided. A play is a series: the pitcher
sends, the batter swings or takes, the ball goes to a fielder, the
fielder throws, the baseman catches for the out. Every device makes its
copy as the pitch plays and stamps it with its own clock, the way the
tournament already times answers; but with the pitch the table sends each
device a silent token - never shown, only held - that says *hold for the
trigger*. A device releases its copy when the trigger for its link comes
down with a poll: the batter's at once, the fielder's when the ball is
sent their way, the baseman's when the throw is made. The play is
complete *for that player* when their link is decided, and that is when
they send. A player whose role never comes up - the seven fielders the
ball did not reach - keeps theirs, and when the reveal shows what the
pitch was, the device grades its own copy by the table's rule and puts
the verdict on the screen at once, no request made: *you had it clean*,
or *you had 67% - the third character went wrong*, which is what a
fielder who never got the ball would otherwise never learn, and is the
proficiency the game is for. Then the right answers go first: a clean
copy is handed up now, toward the fielding record; a wrong one has
nothing urgent to say and waits for the inning break. Whether any of
this shaping was ever needed is the pace ledger's to say after a real
night - the phones learn of the reveal from their own polls, spread
across the polling interval already - and until it says so, nothing
more is built for load. The clock stamp is what keeps holding fair: a
copy held for twenty seconds was still made in the two it took. Two
consequences to build in:
the runner's clock for a link runs from the trigger's arrival on that
device, not from the pitch, so a second of polling is never charged to
the fielder; and a held copy lives in the device's own storage, so a
phone that sleeps and wakes still has it, while a device that never
answers its trigger is a runner safe on the clock, which is the rule
already.

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

The hello goes to every network the unit is on, not just one. The plain
broadcast address leaves by whichever interface holds the default route that
minute, and a Pi with Ethernet and wifi both up — or a phone tethered beside
the wifi — announced itself down the wrong one and was never heard, while it
heard everybody: `--doctor` found one on the bench with its counter climbing by
one every eight seconds and the unit beside it receiving nothing in forty. So
each interface's own broadcast is sent as well, and a table sends a copy by
name to the host it already knows, for the access points that will not carry
broadcast between their clients at all.

**And there is a button that looks.** Hearing is passive, and the offer to
join appears when a net is heard — so a person who was not looking at that
moment, or whose unit heard nothing, had no way back to it in kiosk mode.
**Look for a game** — on the dashboard's game panel, and on the table screen
— asks every address on the unit's own subnets, on ELMER's port, whether an
ELMER is there and what it is doing: one port, one small request to each
answering host, a second or two in all. What it finds is remembered for a
minute and treated as heard, so the same offer comes up, the dashboard's
panel comes back even after *Not now*, and auto-join sees it too. Each net
is shown with what it is doing — *waiting for players*, *in round 4*,
*intermission* — so a waiting room can be told from a game under way. A table
that was cut loose by hand and then goes looking is shown what it finds; the
press is the person changing their mind.

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
in one press.

**A table with people at it joins a net it can hear.** That used to be the
press above and nothing else, which meant a room of Pis each ran its own quiz
unless somebody walked round typing addresses into them — and the fifteen-second
auto-start then committed each one to playing alone before anybody could. So
the order is now the other way round: look for a net, and start one of your own
only when there is nothing to join. The table picks the net studying what this
unit studies, or the busiest one if none matches, and the table picks for
everyone sitting at it — four people at one table racing four different
questions is not a race. A General answering Technician questions is being
asked to recall material they have already passed, at speed, which is practice.

Cutting a table loose by hand keeps it loose. A table that walks straight back
into the net it was just taken out of has not been offered a choice, so
disconnecting turns the joining off until somebody wires it in again.

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

Whichever machine has the receiver, run its gpsd read-only:
`GPSD_OPTIONS="-G -b"` in `/etc/default/gpsd`. The gpsd on Raspberry Pi OS
Bookworm (3.22) otherwise switches a u-blox 7 into binary mode and stops
getting positions from it, re-stamping its last NMEA fix every second — a fix
that looks valid and never moves. `-b` leaves the receiver in NMEA mode, where
it tracks.

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
  pointed straight up that sweeps frequency and times the echo. ELMER fetches
  the sky when it starts — the sonde network and the space-weather feed, in
  the background, cached where every page reads them — so the sliders open on
  the nearest reporting station's current foF2 and hmF2, saying how far away
  and how old they are, rather than on a textbook layer. **Update data** asks
  the network again, for a session that runs on past the reading's
  quarter-hour. The simulator runs on observation from the first second.

  The slider runs 1.8 to 30 MHz and spends most of that travel between bands,
  so a row of **band chips** sits above it: press 40 m and it lands on 7.074,
  the FT8 calling frequency — or on the last antenna you designed for 40 m, if
  there is one, because the point of checking an antenna against the sky is to
  check *that* frequency. The lit chip follows the slider; drag it through
  12 MHz and nothing is lit.
- **Where in the bands** — every frequency input in the Lab, the hop slider
  included, has a meter under it: **● 20 m · FT8** when the number is in a
  band and what is at that spot, or **○ not an amateur band — 30 m ends at
  10.150, 20 m starts at 14.000** when it is not. In a band, the name is a
  link to the band plan opened on that band. Whether *you* may transmit there
  is deliberately not answered here; the band plan does that properly, with a
  class.
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
- **Antennas** — it asks before it tells. What you have to work with comes
  first — a tower, a house, a short garden, an attic, a flat, a vehicle, or
  nothing at home — then what you want to do, then the frequency, and only
  then an antenna, *offered* rather than presumed. It used to open on a
  half-wave dipole at 14.2 MHz, 35 feet up, and asked what you had fourth: a
  person in a flat was shown 69 feet of wire before being asked about the
  balcony. Now the site rules antennas out before the intention rules one in.
  A flat is asked which floor: the tenth is not the first. The rail on the
  ground floor is four feet up and no height at all; on the tenth it is
  ninety-odd feet above the street - a quarter wave on 20 m, the height a
  garden station puts a mast up to get, a takeoff angle in DX territory and
  a VHF horizon most people would envy - and above most of the street's
  noise, though inside all of the building's. The advice says which of those
  it is, and the height it works from is the floor's.
  A flat on 20 m is offered an end-fed out of the window, sloping to wherever
  it can be tied; on 80 m, where even that is too long, a loaded vertical
  clamped to the rail with the rail as counterpoise; an attic gets an
  inverted-V bent to the roof line where it fits and an end-fed folded through
  the space where it does not; a short garden on the low bands gets the end-fed
  as a sloper, tuned to its own ground reflection. A house or a tower leaves
  the choice to what the antenna is for, as before. The suggestion follows the
  questions — change what you have and it changes — until you pick an antenna
  yourself, and then it is yours and stays put. The textbook dipole is one
  click away for anybody who wants it.

  What you have to work with is remembered, and put back before a frequency
  handed in from the band plan is answered — otherwise **Set up an antenna for
  this** on 160 m was answered for nobody's garden at all, and the textbook
  answer for nobody's garden was a dipole half a wavelength up: 266 ft, with
  the physics of why that works explained underneath. Nothing here suggests
  more than a hundred feet now, which is a tall tower; above 200 ft the FAA has
  to be told (14 CFR 77.9) and the structure registered (47 CFR Part 17). And
  on 80 and 160 m, where half a wave is 133 and 266 ft, distance is not a
  dipole at all: it is a **quarter-wave vertical over radials**, which wants
  ground rather than height and is what the people who work DX on those bands
  actually use — with the inverted-L named as the usual shape when the full
  quarter wave is not there either. A wire hung *for* NVIS stops at 60 ft for
  the same reason: its ideal on 160 m is 106, and the lobe is overhead at 40.

  **Heights where the feed matches.** A dipole is 73 Ω in free space and
  something else at every height over the ground, because the wire sees its
  own reflection: about 22 Ω a tenth of a wave up, **50 Ω near 0.16 λ** — the
  one height where coax matches it with nothing in between — a 98 Ω high point
  at 0.35 λ, back through 73 at half a wave, a dip to 58 at 0.6, settling
  toward 73. The period is half a wavelength. The page lists these for the
  band, in feet, marked by whether the site can reach them — on 40 m with a
  35-foot garden the match is at 22 ft and the natural 73 Ω at 30, both in
  reach, and the high point at 46 is not. Worked from the mutual impedance of
  the wire and its image (Kraus) with a cosine integral written out in pure
  Python — it used to be scipy's, and scipy is 30 MB a Pi should not have to
  carry for one function — and checked against the published curve. Perfect-ground figures: real ground damps the
  swings, so these are heights to start looking, not to stop at.

  **And why the height to aim for is not the height where the coax matches**
  — said in numbers, because a page that lists a perfect 50 Ω match at 16 ft
  and then says "aim for 49" looks obtuse unless it says why. The match is
  worth almost nothing: at 49 ft on 30 m the feed is about 68 Ω, SWR 1.4,
  which costs a tenth of a decibel; 1.5:1 costs 0.18 dB and 2:1 half a dB.
  The angle is worth everything: at 16 ft the main lobe points straight up,
  at 49 ft it is 30° — where DX comes from. And an antenna receives exactly
  the way it transmits, so the same height that puts the signal out low
  brings the far ones in. The graph above the table draws both against
  height — resistance wobbling within a decibel of 50 while the takeoff
  angle falls from the zenith — with the height to aim for marked and the
  ground the site cannot reach shaded.

  **What the power asks of it.** Not the antenna — a thicker element does not
  take more power to drive; the RF runs on its skin and a fat wire has *more*
  skin and *less* loss, and QRP operators use thin wire because it is light,
  not because it needs less. What the power decides is what has to survive
  it, and the page says so in numbers: the heat in the wire (#14 at 100 W on
  40 m: 1.9 W, spread along 66 feet), the voltage at the far end of an end-fed
  (500 V at 100 W, nearly 2 kV at the legal limit), the rating of the 49:1
  transformer and the balun's core, the coax above a few hundred watts, the
  heat in a whip's loading coil — which is most of the power — and the people
  nearby, which the RF exposure tool is handed along with the watts.

  Twelve configurations across wire (dipole, inverted-V,
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
  a #14 wire dipole manages 532, a monoband Yagi 447 and a loaded mobile whip
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

The bench rather than the syllabus. Not "things no exam asks about" — RF
safety very much is on the exam — but instruments: the things you reach for
with a radio in front of you rather than a question paper. The Lab next door
holds the material the exams ask about, and the RF safety questions are still
in the pools.

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
- **RF exposure evaluation** — an antenna designed in the Lab's Antennas tab
  can be sent straight here, carrying its frequency, gain and description.
  Those are on different pages now, so the antenna is put down where this
  bench will look for it and picked up once — a row left lying about would
  turn up in the next evaluation somebody opened, days later, as though they
  had typed it. The starting
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

## The Gaming Center

A study tool assumes one person and a quiet evening. A club night is neither.
Every class card on the dashboard has a **Gaming Center** button, and it
opens the table screen with that class chosen and every game the table can
run in one panel: **Tournament**, **Shootout**, **CutThroat**, **Golf** and
**CW Baseball** (its rules are under CW). Pick the class and the pace at the top,
then a game; while one is in play the tiles stand down and the readout says
which. A game pressed with nobody at the table asks first - sit down at a
seat, or scan the code, or start anyway and watch - because a game started
for the practice players alone leaves the person who pressed it outside it
with no way in, which is what happened the first time. Each game is described in its own section below; what they share is
that every question answered at the table counts for the player who
answered it, on that unit, the same as study does.

The panel has a look of its own - one orange, kept to that panel; brackets
on the corners; a ring that breathes while the table stands by. It is a
quiet nod to some friends of the author's, and it says nothing about it.

### Tournament

Tournament mode is the same 2,475 questions run as a race: everybody gets the
same question at the same moment, and the fastest correct answer takes the
round.

### How long a tournament is, and where its questions come from

A tournament is modelled on the examination for the class being played. The
pool is divided into sections, the exam takes one question from each, and the
number of sections in a subelement **is** its weight on the paper — so drawing
the same way gets the proportions right without a second table to maintain and
disagree with the first. The whole draw is made up front and no question is
asked twice.

It runs in blocks of twelve, and a winner is declared at the end of each rather
than once at the end. Twelve questions is about ten minutes, which is roughly
how long a room will hold still, and a table that started badly gets another
chance to be the table that won something.

| Class | Blocks | Questions | Sections in the pool |
|---|---|---|---|
| Technician | 3 | 36 | 35 — every one covered, one asked twice |
| General | 3 | 36 | 35 — the same |
| Extra | 4 | 48 | 50 — 48 of them covered |

Extra gets the fourth block as a perk for sitting the harder ticket, not as an
accident of pool size. The board says where it has got to — `Q18 of 36 · block
2 of 3` — so the room knows both how much longer and when somebody is declared
next.

**Ascending difficulty, where it is measured.** Ordering the draw easiest-first
needs a measure of which questions are hard, and there is one now — measured,
not guessed, from the unit's own answer log, the way KC9SP put it: *how long did
they take, against how long they average across the span of questions they
answered?* Two things go into it, because either alone lies. **Time,
normalised per person per sitting** — log(ms) against that person's own median
that day — so a seventeen-year-old and a seventy-four-year-old are comparable
in one table and a tired evening washes out. And **whether they got it**,
because a guess is fast and time alone would rank every question nobody knows
as easy; the miss rate saturates once everyone has learned a question, which is
why it is not used alone either. **Only a person's first sight of a question
counts** — the fourth sighting is fast whatever the question — so every player
on the unit contributes one measurement per question, which is why showing
every question at least once is the tournament's quiet objective.

A question fewer than three people have met is **unmeasured, not easy**. The
draw is ordered easiest-first only when at least 60% of it is measured — a
ramp built from a quarter of the questions is three quarters of the tournament
in an order chosen by where the gaps fell — and the board says *easiest first*
only then. Unmeasured questions sit in the middle of a ramp, claimed neither
easy nor hard. On a fresh unit that is every question, the draw is in blueprint
order, and it says so. It sharpens every time anyone studies.

**The forecast keeps its own score.** Every hour's outlook is written to a
ledger under `data/forecasts/` with the inputs it was drawn from and the build
that drew it, and every measured MUF is written down as it arrives. From those
two the unit answers three questions on its own. *Skill*: "Yesterday at this
hour ELMER said MUF 12.4; the sondes read 14.2" — kept by lead time and by sky
(lit, grey, dark), so "the model runs 1.8 MHz low at night" is a measured
sentence with an n behind it. *Adjustment*: where the record shows a steady
bias by sky, the unit corrects its own model by that amount — only where no
fresh reading holds, only after twelve measured hours of that sky agree, never
by more than 3 MHz (a bigger bias is a broken station or a different sky, and
is reported rather than applied) — and the strip says so: *the curve is
corrected by that where no reading holds.* The Pi teaches itself the level;
the shape stays the model's. *Drift*: when a new outlook differs from the last
one by more than the inputs moved, the model changed and the sky did not; with
a new build that is logged as explained, without one it is a WARNING. Nothing
in the ledger leaves the unit or names anyone; it is the raw material a field
report would carry home, if the operator ever chose to send one.

**The season, measured.** The sun-angle model had no idea that the F layer
over the middle latitudes is denser on a winter noon than a summer one — the
winter anomaly — or that summer nights hold more than winter ones. Run blind
over a year it was 11 MHz low at noon in December, which is 15 m, 12 m and
10 m called shut on days they were open; nobody saw it because the code was
written in August, when the sun angle happens to be about right. The model
now carries the season as a factor on foF2 by month and by sky, **fitted, not
derived**: from a year of readings at the five Digisondes that reported
between 30 and 45 N (`SEASONAL_FOF2` in `propagation.py`, with its dates and
stations beside it). Held out — fitted on the first half of each month, graded
on the second — the model's error at its own leads fell from 5.0 to 3.1 MHz
over the year, and December from 6.6 to 2.7.

**Past the reading, the record speaks.** "The same as this hour yesterday"
beat the model at 24 hours in every month of the year — 2.0 MHz against 2.7
with the season in — because the ionosphere over a place changes from day to
day by less than any climatology knows about that place, and the ledger holds
yesterday. So as the sonde anchor lets go, the forecast for an hour leans on
what the sondes measured at that hour of day over the last three days, the
most recent counting most (0.5 / 0.3 / 0.2). Over the year, blind: the
24-hour error 2.68 → **1.87 MHz**, better than persistence alone in every
month; the grey line — the weakest sky — 3.58 → 1.97; night 2.57 → 1.62; day
3.04 → 2.09. The model keeps the hours the record cannot speak for and the
shape between, and the strip says when the record is speaking. A unit's first
day has no record and runs on the model; by the fourth it has all three.

**Calibrate my forecast**, on the Propagation page, is the same thing for *this*
place: the nearest sondes' readings, the forecast run blind over them hour by
hour, and a correction fitted by month and by sky and applied where no fresh
reading holds. Three depths — **Quick**, the last quarter, about a minute and
a half; **Normal**, half a year, about two and a half; **Comprehensive**, the
full year, about five — and each refreshes the months it covers while leaving
the rest as the last run that saw them, so a quick run in September keeps the
December a year run measured; the card says which months came from which run.
A season is the unit of variation, which is why the quickest is a quarter and
not a month. The operator watches it
happen — a finding a month ("October: the model ran 1.6 MHz under at the grey
line") between cards from the history deck, the quotations and the hams people
have heard of — because a screen that goes quiet for five minutes reads as
broken. It runs the year again with the correction on and shows what it
bought, month by month, beside "the same as yesterday". It applies only what
is worth applying: a cell within ten percent of the model is left alone and
said to be, because a unit between the stations the season was fitted from
will mostly find the model already fits — and being told so, with an n, is a
measured answer too. Nothing leaves the unit.

**A month in a few minutes.** `./elmer.py --hindcast 30` fetches the last
thirty days from the record — every 15-minute ionosonde reading from the North
American Digisondes (GIRO/DIDBase), every three-hourly Kp (GFZ), the daily
flux (SWPC) — and runs the forecast blind over it: at each hour the model is
handed only what it would have known then, draws its 24 hours, and is graded
against what the sondes went on to read. Seven hundred hours take twenty
seconds on the Pi. The report is the same skill table the live ledger keeps,
plus the yardstick any forecast has to beat: **persistence**, "the same as
this hour yesterday". The first run of it, for Brainerd, 12 August to 11
September 2026: the model ran 2.2 MHz low by day and 3.3 MHz low at the
terminator; its 24-hour MAE was 3.0 MHz; persistence managed 1.8. That is a
measured statement about the model, and from here on a change to
`propagation.py` is judged that way — "August's MAE went from 3.0 to 2.4" —
rather than by whether a curve looks plausible. Sources carry their terms:
GIRO data is CC-BY-NC-SA 4.0 and the report acknowledges each station's data
provider; Kp is CC BY 4.0.

**The Elmer's class report.** The same measure, on the Progress page: *Where
people on this unit get lost* — the twelve questions this unit's students found
hardest, each with how many met it, how many missed it first time, and how long
it took them against their own pace. Honest from a small class because it is
this room's numbers, not a national claim, and it says how much of the pool it
has measured at all. Study answers carry a time; exam answers count towards the
miss rate only.

**The hall is the second source.** When this unit runs net control, every
answer the room gives is written to its own log — each person's, with the
question, whether it was right and how long it took — which is twenty tables'
worth of measurement in an evening where one person studying contributes a
line at a time. Nobody is named in it. Each person is an opaque tag made under
a key the net invents when it opens and never writes down, so one evening's
people can be told apart (which is all the measure needs — it normalises each
person against their own sitting) and nobody can be turned back into a
callsign afterwards, by this program or by whoever ends up with the file.
Practice players are never written: a machine's answer says nothing about how
hard a question is for a person.

The one thing kept about a person is the license class they said they hold,
if they cared to say — a phone's join screen and the seats at a table's screen
ask, and *rather not say* is the default. It is stored beside no name and
shown on no board; the Progress page reports it as a table by class: how many
people, how many answers, the miss rate, and the raw median time. That is how
a room of Generals does on Technician material they passed once, years ago,
beside people meeting it for the first time — which is how fast the knowledge
wears, and the reason an Elmer would want to know. Somebody with no license
plays and competes like anybody else, unless the club's own rules say
otherwise; their answers are the other end of the same measurement.

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

**A second Pi is a node, not a second host.** A unit that can hear a net it is
not in offers it by name — *Technician net · 3 tables* — with one button,
**Check in as ready**, and a smaller way to run the table on its own instead.
Once it is in, the table screen has none of the host's buttons: no start, no
shootout, no asking a question, no closing a round. Those belong to net
control, and the server refuses them from a node in a sentence saying so, so a
stale page cannot start a second game underneath the hall's. What the node
screen has is its standing — which net, as which table, which round — and the
hall arrives on it by itself: the question, the intermission cards, the host's
announcements to the whole table or to one seat by name. A table that was
running its own game when the hall took it stands that game down, scoring the
open round so nobody is left holding a question.

*Ready* is a word apart from *checked in*. Check-in is the machine's doing —
a table hears a net and joins it, or rejoins after a reboot the operator
scheduled for the small hours, with nobody in the room — so it says the Pi is up, not that the people
are. Ready is pressed by somebody at the table and travels up with every
check-in after, and net control's panel shows the two apart: a tick on the
table's chip, and *4 tables · 2 ready* in the corner. Rounds still start on
people actually seated, as before; the host holds the room with Intermission.

A net is known by a **token**, not by its name. The name is only what it is
called tonight — it follows the material when the hall drifts from Technician
to General, and the host can type over it — so the table shows it and never
keys on it. The token is made when the net opens, goes out in the announcement
and comes back with every check-in, and it is what the table remembers. A
different token at the same address is a new net, and the table starts afresh
in it rather than sitting on round twelve of a net that no longer exists; the
same token heard on a different address is the net it was in, back from a
reboot on a new lease, and the table follows it there without anybody typing.

### While the table catches up

Somebody who has answered used to sit looking at their greyed-out choices until
the round closed. That is the one moment in an evening a person is holding a
screen with nothing to do but read it, so they get a **card** — a little of the
history of the art: Hertz saying his waves were no use to anyone, the 92 Code
that gave us 73, Rod Newkirk coining "Elmer" in QST in 1971. Not exam material,
on purpose; the exam is what the game is already made of. Every card is
checkable and says where it comes from, and where the record is disputed the
card says so — Marconi's S "reported", Fessenden's broadcast "by his own
account", the 1943 Supreme Court ruling that is "often summarised as 'Tesla
invented radio', which is more than the court said" — because a program whose
numbers are measured does not start handing out folklore the moment it changes
the subject. The deck is `elmer/trivia.py`, forty-eight cards from Fleming's
valve to Garriott on Columbia; add a card only if you could point somebody at
where it is written down.

Then three seconds of **Scoring…** before the placings come up. It gives the
result a beat to land on, and it means the reveal arrives the same way whether
the round closed on the clock or because everybody was quick.

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

### Two at the screen, phones or no phones

A table with no phones at it can still seat two people at the touchscreen —
which is also how the person running a single-device tournament gets to play
in it. Under **At this table**, two seats: type a name, sit down. During a
round the stage becomes two phones side by side, the question across the top
and each seat with its own column of answers, its own clock and its own
verdict; the rest of the page steps out of the way while they answer and comes
back between rounds. A seat holding the pick in a shootout chooses the subject
in its own column. Under the hood a seat is an ordinary player whose device is
the table — same id, same letters, same certificate — so nothing else has to
know. A third seat would make the buttons too small for thumbs; phones can
still join alongside.

### One callsign, one person

A callsign is an identity and a name is not. Two tables can each have a Bob;
there is one KC9SP. So a callsign joining a table it is already at — a
reloaded phone, a second phone, a seat at the screen after starting on a phone
— is the same player back, with the same score and letters, and the hall
counts a callsign as one person whichever tables it sat at. A plain name is a
person per table, as before, and a phone that reloads remembers who it was and
comes back as that player if the table still has them under that name. Both
were found on the second Pi, where KC9SP had been counted twice.

### Joining, by QR

Each table screen shows a code that carries its own join address. Scanning it
opens the player screen on a phone: type a name, and you are in. The host
screen shows one too, for that machine's own table, so somebody standing in
front of a board with a round on it can join the round they are looking at.

The codes are generated on the Pi, from `elmer/qr.py`, in the standard library.
A hall may have no uplink, Raspberry Pi OS refuses `pip install` under PEP 668,
and there is no apt package — every route out of that ended either in a
dependency ELMER cannot promise or in eight hundred people hand-typing a URL.
So the encoder is written here from ISO/IEC 18004: byte mode, error correction
level M, versions 1 to 10, which covers any join address a table will need.

### Shootout

A tournament asks everybody the same questions and the skill is knowing the
material. Shootout asks a different question: **what do you know that the
person across the table does not?** It is the second game in the Gaming
Center, and the one a net can also run from the host.

One player holds the pick and chooses the *subject* — a section of the pool,
"Feed lines" or "Propagation modes", grouped on the phone under its subelement
so somebody who knows they are good at electrical principles finds all six of
those together. A question is drawn from it and everybody answers, **the
picker included**.

That last part is the whole game, and it is taken from HORSE: the shooter has
to make the shot before anybody has to match it. Miss a question the picker got
right and you take a letter — **E, L, M, E, R**, five and you are out. Miss one
the picker also missed and you take nothing, because the shot was not made.
Without that rule the winning move is to pick the strangest corner of the pool
every time and wait for the room to fail, which is a test of who owns the most
obscure question rather than of who knows the most. The test suite plays eight
bad picks in a row and confirms nobody takes a letter for any of them.

**A subject can only be spent once.** Otherwise the strongest player picks
their best section until everybody else is out, which takes four questions and
teaches nothing. Spending it means a long run of the pick has a natural end:
the picker is working through their good subjects, and when those are gone they
start missing.

The pick stays with a picker who keeps making them. When they miss it passes to
whoever answered that question fastest among those who got it right; if nobody
got it, it goes round the table in order. Somebody who leaves mid-game is out
and the pick moves on without anybody else's turn shifting. Last one standing
wins — there is no fixed length, because with one player left there is nothing
to decide.

Practice players play it too. One holding the pick chooses at random among
what is left: a bot with a strategy would be a bot with an opinion about what
the people at the table are bad at, and it has no basis for one. Between
questions the table says whose pick it is and the phone that holds it shows the
subjects; everyone else's phone says who it is waiting for.

**Across a hall**, the tables are the players. **Shootout** on net control
starts one: the picking table chooses the subject — on its own screen, as big
targets grouped by subelement, and on **every phone at that table**, because
the table screen is not always what anyone is looking at. Anyone at the table
may tap; the first tap is the table's choice, and it goes back to the hall
through the table's own server, since a phone cannot reach the hall itself. Every phone in the hall
answers as usual. A table makes its shot if any *person* at it got the
question right; its practice players do not count towards that, or a table
full of bots that "made it" would be the program handing itself the pick. A
table with nobody right when the picker's table made it takes a letter. The
pick stays with a table that keeps making them, passes to the quickest *real*
table that got it when the picker misses — a right answer from a person beats
a quicker one from furniture, at a table as in a hall — and goes round the
hall when nobody did. Sixty seconds to choose, then it moves on for no letter.
Practice tables never keep the pick; real tables seat first so the opening
pick is the room's; a table that leaves the hall, or is stood down to make
room for a real one, leaves the game with it, or the pick would be handed to
an empty chair. The big board shows the tables' letters in place of points,
and the shot in place of the round winner.

**And one way to lose the pick while making the shot.** KC9SP: the pick
resides with the fastest, *if* the fastest is more than a second faster than
the player with the pick. Somebody who got the picker's own question right
a clear second sooner has out-swum them on their own water, and takes it -
"pack your bags: maybe you can swim here, but others swim better." Under a
second is a near thing, and the picker keeps it. Practice players cannot
out-swim anybody; the pick is for the people.

### CutThroat

Musical chairs with questions, KC9SP's third game, beside the tournament
and the shootout on the table screen. Everybody answers the same drawn
question - no pick; this game is about answering, not choosing - and when
the music stops, anyone still in who did not get it right is out: a wrong
answer, or none, which is the same thing when the chairs are counted. Every
correct answer keeps its seat. One exception, because a question nobody got
is a question and not a chair: a round where *nobody* was right eliminates
nobody.

Two left, and the game changes. Fifteen questions, and a miss no longer
removes anybody: the better count of correct answers over the fifteen wins.
Level after fifteen, and it is sudden death - one right wins; both right,
the faster wins; both wrong, another question.

The seated stay. A player who is out keeps every question and every reveal
on their phone, told plainly that they are watching, with no buttons that
count. Their place is the order they went out in, last out placing highest.
Practice players are in it and out of it like anybody. Somebody who sits
down while the field is still playing takes a chair; during the final they
are seated with the others. Leaving is losing: walk away and you are out
from that moment, and if that leaves one, that one has won.

The rules are `elmer/cutthroat.py`, with no clock or question in them;
`tests/test_cutthroat.py` plays every part of the game through them.

### The whole Gaming Center, across a hall

Net control has every game a table has, with tables for players. Beside
**Shootout** on the host page are **CutThroat** and **Golf** (with the holes
to play), and *End the game* puts the hall back to a tournament. The rule
that makes it work is the shootout's: **a table is right when anybody at it
was right** - its practice players do not make a real table's shot, a
practice table's shot is its own simulated answers - and a table that did
not report in time was not right.

**CutThroat across the hall**: a table where nobody was right is out;
nobody out when no table was right; two tables left get the fifteen-question
final, level after that is sudden death; a table checking in late during the
field takes a chair, one that leaves has lost. **Golf across the hall** is a
*scramble*: one ball a table, every table hits at once with the sensible
club, right if anybody at the table was right, wrong is a foul ball, the
card is by table and lowest wins. A scramble rather than one-at-a-time,
because a hall of twenty tables waiting on one player is not a hall, and a
scramble is how a crowd plays a course. The hall's golf draws its questions
the way a table's does - one area a hole, every question once, the misses
again, then by hardness. A table checking in mid-round gets a ball on the
current tee; one that leaves picks up.

The big board's table panel becomes the chairs (in, or out and when) or the
card (holes, gross, to par), and the round result carries who went out or
where every ball went. Each node table's card says where the hall's game
stands and where *this* table is in it - in or out, its ball's lie - and
every phone in the hall says the same between questions. The conductor ends
the hall when the game ends. `tests/test_net_games.py`.

A different game to each table at once is not built: a round is one
question to every table, which is what keeps the master's load a matter of
tables rather than players. It could be; it waits on a club night wanting it.

### Golf

KC9SP's fourth game, modelled on the real one, on real courses. A stroke is
a question. Answer it right and the ball flies; answer it wrong and it is a
foul ball, into the rough, the sand, the water, or over the cliff for a drop
and a stroke.

**Golf is the slow game.** The others are races; this is the one for
sitting and reasoning an answer through, weighing the alternatives, talking
radio with friends between strokes - and nobody misses a shot to a clock.
Nothing in a round is timed. The player who is *away* - farthest from the
hole; on the tee, the honour, which is the best score on the last hole -
plays, and the rest of the group watches, the question in front of them
too. The screens show no clock and the swing does not know how long the
answer took. (A golfer who has walked off is waited on for ten minutes,
then plays a foul ball and the group moves on; that is the only clock, and
no screen shows it.) A group is a foursome at most: practice players make
it up to four and no further, so one person is not waiting through a queue
of software, and a practice player's stroke is a few seconds and its reveal
short.

The courses are three, from their real cards, one to a pool: **Pebble Beach**
for Technician, **the Old Course at St Andrews** for General, **Augusta
National** for Extra - friendliest to hardest, which is roughly how golf
ranks them too. Each hole has its par and yardage from the card, the famous
hazards along the line placed approximately (`data/golf/*.json`, written by
`tools/build_golf_courses.py`; anyone who knows a hole better is welcome to
move a bunker), and the wind it usually has, drawn afresh each round so no
two play the same. The 12th at Augusta swirls, which means it is drawn for
every shot. Nothing is taken from a video game: real yardages, real hazards
and the real names of real places are facts.

With the question the player chooses a club - driver, wood, iron, wedge;
the putter alone on the green - and may change it up to the swing. A club
that can reach the pin is *aimed* at it and lands within a dozen yards,
either side; one that cannot is a full swing and goes its length. The wind
adds or takes; the lie costs (rough a fifth, sand more, and only a wedge).
Where the ball lands is checked against the course: a correct driver that
carries into Rae's Creek is golf, and the player chose the driver. A foul
ball finds the nearest trouble the club could have reached - water most
often a drop and a penalty stroke - and trouble out of the club's reach is
out of the foul ball's too.

**The other players' strokes are your reading time.** Golfers watch the
others hit, and here that is the point rather than the wait: while a
practice player is away, the question and its choices are on every screen
for everyone to read and weigh. So it is paced for people, who read slowly
compared to computers and comprehend slower still. Before the question, the
*address* stands alone on the screens for a few seconds - who is away, where
the ball lies, how far, the club in hand - so the room knows whose shot it
is before it has anything to read. Then the question goes up and the
practice player takes as long over it as the question takes to read, about
180 words a minute over the question and the choices, never under eight
seconds, and never over the table's pace box - which in golf is the host's
knob for how long the practice players take. Then the stroke stands, the
answer lit and the ball in words, nine seconds before the next player is
up. A person's own stroke is untimed, as before.

**The pro shop.** A door off the clubhouse, on the table and the phone:
the record board on the counter, and the wall. The wall is the
certificates of whoever is at the table - what a radio operator actually
hangs up - and each person's are their own: hung from the Library page
on their account (the picture eQSL or LoTW handed out, sized once to the
wall, with the caption they wrote), kept in `data/awards/<account>/`,
shown under their call whenever they are the one at the table, taken
down only by them, gone with the account. The program carries nobody's
wall: the author's own were the first three on it and are on his units
now the same way as anyone's. An eDX at 50 hangs beside the 29, not over
it, because a wall shows the place you got to and the room beside it.
The certificates ELMER's own games hand out are a different thing and
are said to be - see the tournaments - and a wall of them would be a
wall of a program praising itself.

**The lounge** (`/lounge`) is the same wall as decor rather than subject:
a picture of a room - shelves of silverware, a fire, a window on the
course, a counter - with the operator's own things put into it by the
unit. The blank plates in the picture were measured off it on a pixel
grid once; the signed-in operator's certificates hang in them, newest in
the two beside the window, the rest across the shelves, empty plates
left as painted; the regulars are in the small frames on the mantel and
the far wall; the record board is on the counter; the screen over the
fire shows the sky tonight, or the tee time when the clubhouse has one
booked. The sign is the program's - a unit does not get its own name on
it. Nothing on the page is the main element, which is the point of a
lounge.

**Where the band reaches, as a map** (`propagation.reach_map`, on the
band plan between the coordinator's section and the other radios). The
path model asked for every cell of a ten-degree grid instead of one far
end: for each cell the sky is read at the midpoint of the path - the
sun's angle there, not here, so 20 m fades where the far end is in the
dark and 40 m fills in - the geometry says inside the skip, one hop or
several, and the band's score at that sky is charged for the hops. Ground
wave near, nothing for 6 m and up rather than a made-up map. One hue,
light for good and dark for shut, darker under the night, the QTH marked.
648 cells is a few tens of milliseconds on a laptop and a few hundred on
a Pi, fetched once per band per reading and cached ten minutes. The one
big assumption is the whole model's: one sonde's reading anchoring a
modelled sky, applied everywhere. The footnote says so; what it is right
about is the shape.

**The pace ledger** (`elmer/pace.py`). Every request is timed already; the
ledger keeps, per endpoint, how many times it was asked, its mean, its
slowest and its last forty timings for a ninety-fifth percentile - the
first, cold call of each left out - and writes itself to `data/pace.json`
every few minutes so a restart does not lose the week. A *creeper* is an
endpoint whose p95 is past the budget for its kind (a poll 150 ms, an API
call 400, a page 900, a print 4 s - on a Pi, which is the machine that
matters) or whose mean has doubled since its first hundred calls, which is
what creeping looks like before it crosses any budget. The unit says so in
the log once an hour, the doctor says so, and the weekly field report
carries the table of the slow ones and the creepers home - so a creeper is
caught by the unit and not by somebody looking over their shoulder.

**The standing game.** "I'll go set up a golf game to join" was not a
thing a host could do: the Gaming Center asked for somebody at the table
first, and the moment somebody scanned in the table's own fifteen-second
countdown started a tournament unless they were quick. Now golf chosen on
an empty table is the *standing game*: nothing starts, the screen says
golf at the course is set and what will happen, and the first person to
scan in is met by the clubhouse with the tee time the host chose (five
minutes when none was), practice players filled to a foursome at the
host's level, spread. No countdown, no tournament. "Not golf after all"
clears it. And while golf is the game - set, booked, or under way - the
table is not a table: the screen and the phone are named for the course,
"Pebble Beach", not "Table 1".

**The tempo.** The first rounds at a table were still too fast for the
person who wrote the game, who knew what was coming and could not keep
up - a question arrived while he was still looking at the clubs, with no
word of whose stroke it was. So every beat is set for reading aloud, and
one of them is not a beat at all: **a person's address waits for them.**
Who is away, the lie, the yards, the clubs to hand and a Hit button - on
their seat or their phone - and the question does not come until they
press it (or three minutes pass). A practice player's address stands
twelve seconds, twenty on the tee where the hole is read out first; its
swing takes twenty seconds or the question's reading time, whichever is
longer, within the pace box; its stroke stands twenty seconds on the
screens, in two beats of eight; the card stands thirty when the hole is
done. Every one of those is scaled by the room's `golf_tempo`, one
number, so a speed selector is a knob on it and not a rewrite.

**The club's say.** A right answer flies the ball, and the club decides
how surely. Every club has a spread - the driver eighteen yards long or
short of its mark, the wedge five - and a leak, the chance a fair ball
drifts off the line: a driver's nearly one in five, a wedge's almost
never. A leaked ball takes whatever is out that side, a fairway bunker or
the rough, or the first cut when nothing is; never the water, which it
stops on the bank of, and never out of bounds - those are a wrong
answer's to find. "Less bad luck." An adept shot is shaped and does not
leak. Where in the spread, and whether it leaks, is the swing's timing:
the milliseconds the answer took seed that stroke's draw. Not a clock - a
quick answer is no straighter than a slow one, and the tests say so -
but the same swing lands the same way and every stroke lands a little
differently, which is what a golfer means by luck. It is what puts four
tee shots in four places, and so decides who is away.

**The green.** On the green the wind stops mattering and the slope
starts, and everyone wants the cup. The strip becomes the green: the
whole of it, the cup at the centre, rings every ten feet, every ball on
it at its feet from the cup, an arrow the way it falls and how much (the
card gives each green a slope - Pebble's fall toward the ocean and the
front, placed approximately like the bunkers), and the golfer's mark
wherever they tap. A putt is rolled the distance to the mark, give or
take a pace that grows with the length and a degree or two of line, and
then the green has its say: downhill runs long, uphill comes up short,
a cross-slope breaks the ball toward the fall. A ball that passes over
the cup with pace to spare drops; too much pace and it lips out and runs
on; what stops inside two feet is good - a stroke, no question. A wrong
answer is a bad stroke, never up or raced past, and the ball is still on
the green for the next question. So a green takes one, two or three
questions as it takes putts. A golfer who set no mark is taken to have
allowed for the pace, as anyone who has putted uphill does, and gets the
break as it is; one who set a mark gets the green exactly - which is how
aiming two feet up the slope holes a putt that, aimed at the cup, breaks
below it. The odds are kinder than a tour's: from six feet a right answer
drops, from ten most of the time, from twenty-five now and then, from
forty rarely and never impossible, an adept read far oftener. Real
golfers will miss and appreciate it; this is about radio, and the reward
is one they already find rewarding.

**Not every golfer hits it the same.** Each practice player has a swing
of their own for the round: a power, a factor on every club's length,
and a wildness, a factor on the leak - drawn once from ranges by level,
so a Listener is a short, wild hitter and an Elmer long and straight,
and Sparks is the same Sparks all round. The group is not three copies
either: the practice players are spread around the level the table
chose, one at it, one a step easier, one a step harder. People are 1.0
and 1.0 - their swing is the question. The sensible club allows for the
power: from two hundred out a short hitter needs the driver where a
person takes the wood.

**The card, written as it happens.** The hole being played is pencilled
in on the scorecard stroke by stroke - the strokes so far, in a lighter
hand - and inked when the hole is done. The scores are in a handwriting
face where the machine has one (Segoe Print on Windows, Bradley Hand on
a Mac, whatever cursive a Pi offers), a little askew row by row, because
a scorecard is a thing somebody writes on.

**Carry, then roll.** A ball does not stick where it lands. The club
sets how much life it has when it comes down - a driver's low, running
ball about twenty-four yards of it, a wood eighteen, an iron nine, a
wedge's high spinning ball three - the surface it lands on sets how much
of that it keeps (all of it on the fairway, under half on a green, a
third in the rough, none in sand), and the wind pushes the roll along or
holds it up. A crosswind drifts the ball in flight, off the side the
course says it blows from. The ball is read where it comes to rest, so a
driver landed five yards short of the creek runs into it, an iron landed
nine short of the green can run onto it or stop short - the bump and run,
and the gamble - and a wedge onto the green checks up. The mark is where
the ball comes down; a golfer who wants it to stop short lands it
shorter still, as on a course. An adept "pure" shot is stiff: it lands
and stops. The playback says the carry and the run - "driver, 248 yards,
ran 22 more".

**The hole has a width, and the golfer has a mark.** A ball is yards
along the line and yards off it, left negative, right positive. Inside
eighteen yards either side is the fairway, or whatever band crosses it;
beyond that are the sides, where the card's left and right hazards live
and the first cut where nothing does; a green is fourteen yards wide of
the pin. The strip draws every ball where it sits across the hole, and
the strip takes a tap: the golfer who is away, at their seat or on their
phone, taps where they mean the ball to land, a cross is drawn there, and
the shot is played at the mark instead of the pin - short of the creek,
wide of the trap, over the corner. Their mark is their mark and the
algorithm feeds the result: the club's spread and leak still apply around
it, so aiming at the edge of the trap is a way of finding it. A mark is
for one stroke; with none set the aim is the pin, down the line, and
nobody has to aim who does not want to. The tap's geometry travels in
the state (`golf.map`) so the screens turn a pixel into yards the same
way the strip drew it (`elmer/golfmap.py`).

**The address, on the screens.** While the director addresses the next
stroke the closed round before it is still on the table, and the screens
used to go on drawing that round - so with a person's address waiting on
their Hit, the round stood still for ever after the practice players had
played through. The state now says `addressing`, and the screens draw the
address instead, Hit button and all.

**The scorecard.** During golf the party card - "At this table" - is the
card: a column a hole with its par, a row a player with the strokes
taken, total and to par at the end, holes not yet played blank. The phone
shows the same card under the round. It is the only account of who is
in the party that anybody needs.

**Every hole its own shape.** The card gives a hole a bend - where the
dog-leg turns, which way, how sharply - and a width, and the strip
draws both: the line of play swings past the corner at a third of the
real angle, as a yardage book's does, and the fairway is as wide as the
card says, the 7th a lane and the 2nd a field. Hazards, balls and the
mark follow the line; a tap is read against it. The rules do not bend -
a ball is yards along the line and off it wherever the line goes - but
the width is the rules' width, so the first cut is nearer on a narrow
hole. Pebble's dog-legs are on the card where the course has them,
placed approximately like the bunkers. And between holes the tee shows
the standings after the last, then who has the honour - the best score
on the last hole plays first, practice player or person, as on a course.

**The hole, drawn.** Beside the words, every screen shows the hole as a
yardage-book strip - the tee at the foot, the green at the head, every
hazard as a band at the yards it covers and on the side it sits, the wind
as an arrow, and every ball where it lies, yours ringed. It is drawn from
the card the game plays (`elmer/golfmap.py`), not from a map of the real
course - the club's routing is the club's, and the game does not have it
- which makes it the honest picture: what it draws is exactly what the
ball obeys, so a golfer reading it is reading the game. Anyone who knows
a hole better than the card does is welcome to move a bunker in
`data/golf/*.json`, and the strip follows.

**Prepared while they read.** Nothing is fetched at the moment it is
wanted. When a stroke closes, the next stroke's question is drawn at once
- the rules already know who is away next and where their ball lies, which
is all the draw depends on - and its figure, the one thing a screen has to
fetch, is named on the state so the table and every phone fetch it while
this stroke's result is being read; the next tee's picture the same way.
In the clubhouse, while the tee time counts down, a screen fetches
everything the round will show or say - the pictures from every tee of the
round, the clubhouse, the clips and the voice snippets the unit has - one
file at a time, and keeps them a day, so a Pi hands each out once to each
phone and no stroke waits on the wire. `static/warm.js`.

**One thing to look at.** A stroke at the table screen is laid out for a
person with one focal point: the question and its figure on the left, this
seat's choices on the right, nothing below the fold - and the result the
same way, the answer beside the verdict and the stroke. The tee sheet (the
QR) shrinks to a corner while a round is on. Nothing about a person's
stroke is on a clock, and now neither is its result: after a person's
stroke the reveal stands until they press *Next stroke* on their seat or
their phone (ninety seconds for somebody who has walked off); a practice
player's stroke still stands nine seconds. The reasoning is the
split-attention effect: a learner made to integrate a question above the
fold with answers below it, or a result on one screen with a play-through
on another, spends attention on the integrating rather than the content -
and attention is one spotlight, not several. Clips of the swing, when they
come, will go in the gap between the answer and the next address, not over
the question.

**The narrator.** A stroke is told the way a commentator tells it, in a
line with the golfer's name in it. Before the question: *Halyard addresses
the ball, the iron in hand, 162 to go from the fairway…* with a pulsing cue
beside it - the moment at the tee, theirs to enjoy - and then the question.
After the answer, two beats: first the shot in golfing terms alone - *Halyard…
Topped it. Iron, a foul ball - short and into the rough* - and only then the
answers, theirs and the right one at once, two colours side by side, which
people read fine as long as it is one car of the train at a time. The tee
shot gets the hole read out; every stroke after it gets the narrator alone,
since we were all there for the start of the hole. What is said goes on the
screen - and, when the unit has the recordings, is said aloud.

**The voice is pieced together from snippets**, the way an ATIS reads the
weather from a shelf of recorded words. The game composes every line as a
list of tokens - the stems of sound files in `elmer/static/golf/voice/`:
*name-scott · addresses-the-ball · the-driver · in-hand · three · hundred ·
and · seventy · seven · to-go · from-the-tee* - and the screen plays them in
order, silent for any the unit has not got, so the voice is built up one
snippet at a time and a unit with none says nothing. Numbers are reused
for yards, feet, strokes and the wind; the holes, the clubs, the lies, the
calls and the scores are fixed phrases; a regular's name is one file,
`name-<slug>.mp3`, and a name not on the shelf is said as *the player*. The
composition is `elmer/voice.py`, tested without a speaker in the room; the
script to record - one line a snippet, ready for a voice service - is
`python3 tools/voice_script.py`, and `docs/narration/voice-script.md` is
its printout.

**The shots worth making.** Golf is about the shots - good, bad and
regular - and some are shaped on purpose: a hook worked around the trees, a
stinger punched under the wind, a flop over the sand to a tap-in, the
approach that goes in, the drive that was launched. Here they are earned by
an *adept* answer: a right answer on a question this unit has measured as
hard (the same measure as the class report), or the third right answer in
a row when nothing is measured yet. Which shot depends on where the ball
is: from the rough or the sand it is worked out, the lie not costing and
the trouble it was shaped past not catching; into the wind it is a stinger,
and the wind has no say; off the tee it is launched, a little more of
everything; a wedge from inside forty is flopped to a tap-in; and an
approach from inside a hundred and twenty goes in one time in six. The
call says which, and the record board will count the holed ones. The ball
still obeys the course - it gets the shot a good golfer would have played
from there, and nothing more.

**A hole in one** is real on a par 3 - about one in twelve thousand for an
amateur, which nobody would ever see here - so a right answer from the tee
of a par 3 drops at one in fifty instead: rare, and possible. Never on a par
4 or 5, where the real world says almost never and the game says never.

**Regulars and the record board.** A table remembers who has played at it
- the last two dozen names, offered back to every seat's and phone's name
box so nobody types their own name twice - and keeps a golf record board by
name: rounds played, best to par and the course it was on, aces. It stands
at the end of a round, under the card; practice players are not on it.

**The clubhouse.** A round starts from a tee time: the Golf tile offers
*play now - I'm alone*, or a tee time in two, five or ten minutes, and the
round waits in the clubhouse - the table screen counting down, the code up
big for friends to scan, the group so far by name - until the time is up,
or the group is full (a foursome of people), or somebody says *Play now*;
practice players make up whatever is short when it departs. That is any
time a round is booked with nobody on the course yet, not only the first of
the day. Cancel puts the tee sheet away. The course's clubhouse is the
backdrop when the unit has a picture of it - `elmer/static/golf/clubhouse/
<course>.jpg`; Pebble Beach's is a pro shop looking out over the course,
made by the author, and the other two courses wait for theirs. Each hole can
have its own picture from the tee - `elmer/static/golf/tee/<course>/<hole>.jpg`,
the first at Pebble Beach has one - shown over the address while the group
is on the tee, so *Scott addresses the ball* is said over the view Scott
would be looking at. The picture
is meant to become a place: spots in it to press - the desk to check in,
the door to the lounge, the pro shop for the record board - each opening
its own panel. The rooms, as planned: the *desk* is check-in - the tee
sheet; the *pro shop* holds the record board, the dignified list; the
*lounge* is the personal trophy room, where somebody on the pro shop's list
sits down and sees their own best - the best time on the questions of the
players who hold a place on that list. The picture is served as the
screens need it, not as it was made: the originals stay in artwork/ and the
served copies are resized and recompressed to a few hundred kilobytes,
because a Pi hands them to every phone at the table and the budget is a
Pi's. That is the next step, once the rooms behind the doors exist.

**A round is joined by tee time.** Once a round is on, the table screen is
golf's: the Gaming Center and the round controls stand down, the QR stays
and reads *scan to arrange a tee time*. Somebody arriving while the group
is still on the tee is in it now; arriving mid-hole, they have a tee time
and watch this hole with the group - the questions are worth reading - and
the group picks them up at the next tee. That is golf. A game you can join
any time is one of the trivia modes, and they are a tile away.

**The call.** Every stroke carries what a golfer would say at the moment of
contact - *Pured it. On the dance floor. Topped it. Hooked it into the
water. Lipped out.* - shown big above the club and the yards, so somebody
knows what they hit without reading the coloured answer. And a slot beside
it: put a clip of the swing at `elmer/static/golf/clips/<kind>.gif`
(`fairway`, `green`, `long`, `holed`, `rough`, `sand`, `water`, `missed`)
and the reveal shows it - the unit reads the folder when a round starts, so
the screens ask only for clips that are there. With none, nothing. The idea, the author's: have
them thinking of the golf game while they think of the radio game, so each
recalls the other.

**The questions have a thread.** Each hole takes one test area - a section
of the pool, drawn from those not yet played this round - and stays on it
until its questions run out, then takes another. Once every question in the
pool has been asked once, the ones missed come round again first; after
those, the order is by how hard the questions have measured on this unit
(the same measure as *The Elmer's class report*), matched to the shot at
hand: a ball on the tee or the fairway gets an easier one, a ball in the
rough or the sand a harder one. A bad lie has its say.

On the green, putting is about being right: a correct answer holes it, a
wrong one is a missed putt. Pick up at par plus three, the way casual
golfers do, so a hole has a bounded number of questions. Scoring is real
golf - eagle, birdie, par, bogey - lowest total wins; a tie for the lead is a
playoff hole, sudden death. A **handicap** is a switch: off, everybody plays
scratch; on, strokes are given from each player's share of right answers in
their study history - nine in ten plays scratch, one in two gets a stroke a
hole - and come off at the end, so a poor player and a fair one can play the
same card. Every stroke is written as a line of **playback** - *"wedge, 27
yards - on the green, 6 feet"*, *"driver, a foul ball - into the Swilcan
Burn; drop, and a penalty stroke"* - which is what the reveal becomes.

At the table it is a tile in the Gaming Center - **Golf**, with the holes
to play (front nine, back nine, all eighteen) and the handicap switch - and
the course is the pool's. The table shows the hole as the card gives it,
who is away and where their ball lies, the question, where every ball
lies, the last stroke in words, and the card; a seat at the screen that is
away has its clubs above its choices, and the other seat watches. The phone
shows this player's ball and clubs, *your stroke* or *who is away*, their
own stroke first and then the group's, and the card between strokes.
Somebody who sits down mid-round gets a ball on the current tee; somebody
who leaves takes theirs. One person can just go and play a round: a table
of one, a phone or a seat at the screen, is a round of golf.

The rules are `elmer/golf.py`, with no clock or question in them;
`tests/test_golf.py` plays the shot, the course, the green, the card, the
turns, the thread of questions and the playoff through them, and
`tests/test_golf_table.py` the table around them.

### The figure, and the part it names

A question with a figure shows the figure on every screen - the table's,
the phone's, the big board's, the study page - which the table and the
board did not do. And a question that *names a part* - "What is component 3
in figure T-2?", which is every Technician figure question - shows that
part cut out and enlarged beside the whole figure, ringed in amber and
labelled, the way a finger on the page would show it: a room of people on
phones has thirty seconds, and identifying a symbol is faster with the
symbol in front of you. The whole figure stays beside the cut-out, because
a symbol means what it means from what it is wired to. A question that asks
*which* symbol is the thing - every General and Extra figure question - gets
no cut-out, whatever the map says, since the answer is a place in the
figure. The map is `data/figures/tech2026/highlights.json`: a box per
numbered part, as fractions of the image, read off the figures by eye and
open to correction; `tests/test_figure_highlight.py` checks every
Technician figure question has its part on it.

### The room's mark, and the credit

Every room page - the table, a phone at it, net control, the big board -
carries ELMER's own mark in its head, ringed in the colour of the pool the
room is playing: green for Technician, amber for General, violet for Extra,
cyan for the commercial pools. Beside it, in words, the credit: *made with
Claude Code*. Words rather than a borrowed logo, because the logo is
Anthropic's and a mark in a header reads as an endorsement nobody was asked
for; the NOTICE says the same.

**Credit for the questions, too.** A player who sits down at a table under
their callsign, on a unit where that callsign is a profile, gets every
answer they give there in their own study record - a table's round or a
hall's landing on that table - marked with the game it was. A name that is
not a callsign, or a callsign nobody on the unit holds, is credited nowhere:
the record belongs to the person, and only a callsign says who that is. And
it is everything a study answer earns, because it was the same question
answered by the same person and only the room was different: the card is
graded and rescheduled - a question missed at the table lapses, and comes up
in **Review** with its explanation; one answered right moves on, which is
what readiness is measured from - and the XP, the streak and the run are
theirs. Credit where credit is due. This is the first step towards carrying
a player's questions and awards home to their own machine.

### Certificates for the wall

A club that runs a tournament night had nothing to hand the winner: the score
was on a screen and the screen moved on. **Certificates** on net control, and
on the table screen, prints one page per placing — landscape, large type, the
medal, two signature lines and the date — for the top three *people*. Never a
practice player; a bot on a certificate would be the program awarding itself.

What it says is what the game recorded: the placing, the tournament by class
and length, correct out of answered, how many times the fastest correct answer
was theirs, which blocks they won, which table they sat at — and the name they
asked for. Joining a table asks two things, kept apart: *what should we call
you*, which is what the room sees on every board and phone and can be an alias,
because one never knows who is wandering about a hamfest; and *the name or
callsign you want on any certificate won today*, which is never shown anywhere
— not on a board, not in the board's JSON, not on another phone — and comes out
only when a certificate is printed. Somebody can play the day as "Sparks" and
take home a certificate with their callsign on it. Leave the second blank and
the first is used. The event name is whatever the host types, because a club night has a
name the program cannot know, and it is remembered for the next one. The place
is the station's QTH, if one is set.

The button opens a form, not a print dialog, because a certificate carries
things the program cannot know: the **event** as it should read across the top,
who is **hosting** it, the **date as it should be worded** — "Saturday 17 July
2027", or just "July 2027" — the **place**, and who **signs**, printed under the
signature lines so they only have to sign. Net control starts from the
station's callsign and the place from its QTH when that is a named town; a
bare grid square is left blank, because *EN26uo* on a wall says nothing to
anybody. The details are kept on the unit, so a club sets them once for the
day. Under them, the **names as they will print**, each with its facts. A name
a player gave for the wall is theirs and the form will not change it — nobody
turns a Richard into a Dick but Richard, and the server ignores the attempt
whatever the form sends. A play name standing in for one, because the player
left that field blank, may be corrected — a spelling, not a nickname — since
somebody who typed *bob* on a phone should not get that in 44-point type. Name
fixes are not kept; they were about those people and that print.

What it does not say is anything about a licence. A game played on the
question pools is not an examination, and the foot of every certificate says
so in as many words, because a sheet with *Technician* in large letters will be
read that way by somebody unless the paper itself says otherwise.

The medal renders in `artwork/` were generated with Google Gemini at KC9SP's
direction — they are not hand-drawn, and this document says so because a
certificate is the one page of this program that leaves the building. They
are cut into `elmer/static/medals/` and set on a drawn ribbon; the art's own
ribbon is discarded, which is why the renders need not agree about its colour.
Where the art is missing a drawn medal stands in, so the certificate never
waits on a file. All three were re-made without a callsign on the face —
CHAMPION, FINALIST, BRONZE MEDALIST — so the set is any club's to print.

A shootout has medals of its own, generated the same way: ELMER SHOOTOUT, a
bolt through a crosshair, CHAMPION / RUNNER-UP / THIRD PLACE struck into the
gold, silver and bronze — cut from `artwork/ShootOutBlanks.jpg` into
`elmer/static/medals/shootout-*.png`.
A shootout certificate uses them, and its words match the disc: *Champion is
awarded to … in the Technician shootout, finishing on ELMER*. A game with no
medals of its own falls back to the tournament's.

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

The flag travels the whole way out — to the table, to the net, into the round
summary — because everything downstream needs it: a person joining displaces
one, the host's panel shows which places are being held, and a name somebody
takes over has to be known to have been free.

What a screen does with it is that screen's business, and the big board
deliberately does not mark them, for the reason given under *Tables that are
not there* — which is the same idea one level up, for whole tables rather
than players. Nothing is scored differently either way.

### Cohorts, and who takes the round

Players are seated in cohorts of eight and scored as teams, so eight people
answering steadily beats one answering brilliantly while seven guess. The
winning cohort takes the round, and where two are level it goes to whichever is
behind overall, so a runaway leader does not also collect the consolation.
Where they are level on that too it is drawn, because sorting by name handed
the same table every tie all evening.

The board used to say the winner **chose the next question**, and nothing in
the program ever did: the round drew at random over the whole pool and the
picker it computed was never consulted. In a tournament the questions come from
the blueprint and nobody picks them.

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
net control counts the table as quiet and carries on without it.

**A heavy neighbour is quieted for the game.** OP25 decodes P25 with GNU Radio and takes most of a Pi when it runs - a 3 especially - so a game sharing the machine serves every question and answer from behind it, which reads as latency and is not the network. When this unit opens a net, starts a tournament, or joins one, it stops OP25 first (the `multi_rx.py` decoder itself, matched precisely - a shell or a launch script that merely names it is left alone, and so is ELMER). The operator relaunches it afterwards; ELMER never restarts it, because only the operator knows whether the scanner should come back. Switch it off with `stop_op25` off, or widen what counts as OP25 with `op25_match`; the self-check says whether OP25 is running and what will happen to it.

**A fleet imaged from one SD card still shows as many tables.** Every unit works out an id from its hostname and machine-id, and Pis flashed from one card share both — so they all compute the *same* id, and net control, which keys its tables by id, used to let the second overwrite the first: three units playing, one table on the board, and the game failing for everyone but the host. Each running unit now sends a token made fresh at start, net control gives colliding ids their own slots — *raspberrypi*, *raspberrypi (2)*, *raspberrypi (3)* — and the log says a card was cloned. The board is readable and the scores are each table's own; giving the units their own hostnames makes the names on the board yours rather than a numbered *raspberrypi*. The hall does
not stop because one Pi in the corner lost its wifi. A table also remembers its
net control across a reboot — an operator who reboots the Pis in the small
hours (ELMER never restarts or updates itself; see *Keeping it up to date*) should not have
to walk twenty tables through a form before the doors open.

### The run-up, and the programme keeping time

The first question after a pause does not appear from nowhere. A hall that
has been in intermission for ten minutes and then has a question on every
screen in the same instant has handed the round to whoever happened to be
looking, and the rest will say, rightly, that their time was taken. So the
conductor puts five seconds on every screen first — **Get ready!** until three
seconds are left, then **3**, **2**, **1** — and asks on nought. The same five
seconds whether the host pressed Play or the programme's clock ran out, on the
table screens, the phones and the board together, because the people in the
room cannot tell which it was and should not have to. The seconds are counted
on net control and each screen keeps the earliest reading it has had, so a
slow poll never pushes a three back to a four.

A programme step with minutes on it used to be a note for the host, who
pressed Next when it felt like ten minutes. Now it keeps time: a small clock
sits in the corner of every screen — *Intermission · 4:32* — and when it runs
out the programme moves on by itself. Where a game follows, the hand-over
comes five seconds early so the run-up *is* the intermission's last five
seconds and the clock reaches 0:00 as the question goes up. A rounds step
hands over when its rounds are played, a shootout when it is won; steps with
no natural end — an announcement, the certificates, thanks — still wait for
the host, whose own buttons work throughout. Intermission pressed during a
run-up cancels it, and the screens stop counting.

### The show — what every screen does when it is not asking a question

The host runs the room, and a dead screen at a hamfest is an invitation to
find something else to do. So net control has a hand on every screen in the
hall at once — the board at the front, the table screens, the phones — and
none of it costs the network anything new: it rides the check-in reply each
table already polls for once a second (`elmer/show.py`, drawn everywhere by
`static/hallshow.js`).

**Say it to the room.** One box on the host page, three targets — everyone,
one table, one seat — and two weights. A *notice* stands for twenty seconds;
an *urgent* one stays until the host clears it, or comes back every minute
if asked. "Lost child waiting for parents at the ARRL booth" is urgent and for
everyone. "You won the round" is a notice for one seat and "Skippy won the
round" the same notice for everybody else; the seat's line reaches that
phone and no other screen, because net control addresses it by table and
name and the table hands it to the right device. **Attention** blanks every
table to a message while the host talks, and stays until released. What was
said and when is logged; who saw it is not.

**The deck.** Between rounds every screen shows the same card at the same
moment — net control turns them over, which is what makes it a show rather
than a screensaver. Trivia from five decks (history, quotations, famous hams,
operating technique, the gear — every card checkable, sources named), the
standings, the join code, the programme, and the event's own cards: sponsors
(a name, a line, their image, added from the host page and served from this
unit) and club notices (membership, coming events, a link). A trivia card
sits between every other kind; the host ticks decks on and off and sets the
dwell. Every card has a **presence** — how often it comes round, from three
times a pass down to once every fourth pass, so a partial sponsor can be
sold a quarter of the rotation and get exactly that; sponsors on the same
fraction are staggered so they do not all land on one pass and sit out the
next three. ELMER's own card is in the rotation too — one of the four icons
and one line, every third pass by default, down to off — a little tasteful
self-promotion in the intermission the program itself is providing. A result
stands twenty seconds to be read, then the deck has the screen until the next
question. Sponsors and notices persist under `data/show/` between nets; none
of it leaves the unit.

**Playing, studying, intermission.** The host declares the hall's mode, and
the mode is what the hall does, not a label: *Playing* starts the conductor
on the difficulty and clock the round controls show; *Intermission* and
*Studying* stop it and score whatever question is open, and every table
closes that question within the second — a press that the game rolled over
was the first thing found in the first rehearsal. In
*study* the host names a focus — "everyone: T5 for ten minutes" — and the
focus card leads the deck on every screen; beside the controls the host sees
**where tonight's room is missing most**, by section, from the hall log since
the net opened (a section needs four answers before it is called weak), with
one press to make it the focus and another to put a question from it to the
hall. That is the piece that was not possible before: an instructor who can
see, while the room is still in front of them, which section it did not
understand.

**The programme.** The event as a list — intermission, twelve rounds, ten
minutes' study on what the room missed, an announcement, a shootout,
certificates, thanks — walked with one button. Each step does the thing: the
conductor starts or stops, an open question is scored before the screens
change, the mode follows. **Schedule an event** fills the list in one of the
shapes an event takes — *around the table* for friends and family and one
unit, *a class* a VE team is teaching (study first, then questions, then
study on what the room missed, and again), *a club night*, *a hamfest booth*
(short rounds, the sponsors between, a shootout when the crowd is there) —
and the host edits from there. It is the same program at every size, and the
limit is whether a Pi can be powered where the people are.

**No stale screens.** The first rehearsal found a phone that had joined the
hall from a page its browser had kept since the day before — the QR scanner
handed Firefox the address, Firefox never asked the unit for the page, and
the person sat through an intermission on a screen that predated it. Every
page and every JSON answer is now sent `Cache-Control: no-store` (the static
files are versioned by their own change time and may be cached for ever), and
the table, phone, board and host pages each carry the build they were served
from and reload themselves when a poll says the unit has moved on — the phone
keeps its player across the reload, so nobody has to rejoin. A page from
before any of this — one a browser kept from an earlier day — cannot be
reached by a header it never received, so the one thing it still does is
used: a browser's page that asks to join without the current build is
refused with a reason its old script does display, and a page new enough to
understand the refusal simply reloads itself.

**The host sees the room.** Each table's chip on the host page says what its
screen is showing — *question*, *result*, *card:trivia*, *attention* — carried
up with its check-in, so the host knows what the room sees without walking it.

### Opening a net, and what starts a round

There is one way in, whichever way you ask for one: pressing the button and
simply arriving at `/net` build the same net. A second way of doing a thing is
a second thing to keep working, and when the two drift the difference is
invisible — a hall with no conductor and no table for the people at that
machine looks exactly like a hall nobody has joined yet.

**The host takes a table in its own net.** The people sitting at the
instructor's Pi are in the hall like anybody else's, and they get there down
the same bridge every other table uses rather than a private path. A host whose
own table is the one code path never exercised is a host whose own table is the
one that breaks, and it is the table the instructor is sitting at.

**A round starts because a table said it has people at it.** Check-in has
always carried the count, so this is a report rather than a guess, and it beats
a timer at both ends: a clock firing into an empty hall starts a game nobody is
playing, and one that has not fired yet holds up a room that is ready. A table
that fills up late joins the next round — the hall is asked again every tick,
not once at the beginning.

**Rounds are thirty seconds**, adjustable from ten to sixty. A minute was
generous to the point of slack: the room spends most of it watching a question
everybody has already answered, and a hall moves at the speed of its slowest
clock rather than its slowest reader. In practice a round closes sooner,
because it closes as soon as every table has reported. The hall's patience for
a table that has gone quiet follows the same dial — twenty seconds past the
clock the tables were showing, so the two stay in step whichever way you move
it.

**The code on the host screen is for people; the address beside it is for
Pis.** Scanning puts a phone straight into the round on screen, at that
machine's own table. The bare address would land them on the dashboard, looking
for the game they can see from where they are standing — and a phone is not
what anybody points at a net address anyway, since tables find the net
themselves.

### Tables that are not there

A hall can be filled with tables nobody is sitting at. **Add practice tables**
on the host screen puts four in, named for wireless stations — Poldhu, Glace
Bay, Nauen, Signal Hill — and they play: they answer inside the round, spread
across it rather than all at once, each consistently as good as it is so the
board has a shape worth watching.

They are there because an instructor setting an evening up cannot tell whether
any of it works until eight people have arrived and sat down, and a board with
nothing on it is the least useful thing a screen at the front of a room can
show. A real unit checking in **takes one of their places** — weakest first, so
what gets displaced is the table nobody was watching and the evening's story
survives somebody walking in halfway through it.

The big board does not mark them. A board with a dozen names on it reads as an
evening; the same board with eight struck through as software reads as an empty
room being flattered, and the room is what the screen at the front is for.
Nothing is scored differently — a person beats them or loses to them on the
same terms. The host's own panel does mark them, with a small hollow square,
because whoever is running the net needs to know which places are being held
even when the hall does not.

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

**Three answers, not one.** A hall board carries the tables' running total, the
players' **top 5** overall, and the **top 5** of the round that just closed,
because those are three different questions. Five, not eight: five is a podium
with room on it, eight is a list, and the point of a board is that a name on it
means something. Which table is winning is the hall's. Who was quickest just
now is the moment's. Which *person* is having a good evening is the one somebody
sitting at a table came for, and it was the one the board could not answer.
Every answer counts towards a player's total, not only the ones that scored:
`3/4` beside the points, because two right out of three and two right out of
twenty are different evenings.

Practice tables and practice players are counted and marked rather than left
out — a board with them edited out is not the game that was played — and **P**,
or a tap in the corner opposite the way out, takes them out of the view for a
club night with three real tables among six. That is a switch on the *view*;
net control's "send one home" takes a practice table out of the *game*. The
totals underneath are the same either way, so two boards watching one net
cannot disagree about who is winning. A hall that is all practice says so once
in the heading instead of stamping every row.

Rows that do not fit are dropped whole. How much room the panels get changes —
a long question takes three lines where a short one takes two, and every
twelfth question a block result appears above them — so the rows are measured
once they are on screen and the ones hanging off the bottom are taken out,
rather than slicing somebody's name in half.

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

The Pi running the hall can put the board on its own monitor: **Big board** on
net control walks that screen on to it, and **Escape** walks it back. It backs
out a step at a time — out of one tournament to the wall of them, out of the
wall to net control — and the corner of the board says which step is next, so
the label never promises something the key does not do. The corner is tappable
too, because most of these are touchscreens with no keyboard near them.

Net control is whole again the moment you come back: the tables checked in, the
code people join by, the controls. That is the reason for the round trip. The
host Pi does not have to be a table — in a room full of them there is usually
one easier to sit down at — so its screen is free to show the room, and
whoever is running the net can step off the board to sign somebody in and step
back on.

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
./elmer.py --index-library    read the manuals in data/library/ (all: redo every one)
./elmer.py --hindcast 30      run the forecast blind over the last 30 days and grade it
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

It checks the pools, diagrams, database, templates, network, the neighbours
it can hear, the hall it remembers, the mail path and the port, then prints
every address the server can be reached on. The dashboard's **Self-check**
runs the same checks and shows the same lines.

Where a line has one known remedy, the unit's own screen gets a **Fix**
beside it: a copy that is not connected to the repository is connected
(`--adopt`, from the dashboard); a Start Menu entry that is missing or points
at a copy that has gone is put back; a net this table remembers that no
longer answers is forgotten, and a table that has come to report to itself
is cut loose; poppler missing on Windows is installed with winget; OP25
running before a game is stopped. Each does that one thing when pressed,
says what it did, and the check runs again. The press works from the unit's
own screen only - across the network the line just says what to do. Changed
files stay a terminal matter (`./install.sh --repair` throws edits away, and
nothing on a dashboard should do that by accident).

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

And three lines for an evening with more than one Pi, because the thing most
likely to go wrong in a room is two units that cannot hear each other, and
nothing on either screen says so — each just plays alone:

```
[  ok  ] other ELMERs  -  2 heard - Bench at 192.168.1.119 (running Technician net);
                          Duluth at 192.168.1.31 (reporting to http://192.168.1.119:5000, which has not answered it)
[  ok  ] hall          -  remembers http://192.168.1.119:5000, which is running Technician net (3 tables present)
[  ok  ] mail home     -  kc9sp@yahoo.com via smtp.mail.yahoo.com:465 (ssl), login set - reports go to KC9SP@arrl.net
```

The doctor listens on the discovery port for a whole announce interval — ten
seconds, not four, or a live neighbour is missed half the time — and names
each unit it heard with what that unit says it is doing. A table that names
its net has heard back from it; one that only has an address is pointed at a
net that has not answered, which is how a Pi left pointing at last week's
host shows up. The **hall** line says which net this unit remembers and asks
it whether it is still there — and whether it is still the *same* net, by
token, or a new one at the old address. The **mail home** line says which
door reports would leave by, and, for the providers that refuse an account's
own password, what they will want, before the first refusal rather than after.

Then watch the log while you try to load the page:

```
tail -f data/elmer.log
```

- **A line appears** — the request arrived. The status code on that line says
  what happened, and any error is logged with a full traceback right above it.
- **Nothing appears** — the request never got here. That is a network problem,
  not an ELMER problem: check the device is on the same network as the Pi, that
  you used `http://` and not `https://`, and that you included the `:5000`.

Everything is logged to `data/elmer.log` (rotated at 5 MB, five kept) as well
as to the console: every request with its client address, status, duration and
browser; every unhandled exception with a traceback; and JavaScript errors,
which the page reports back to the server so a browser-side failure does not
vanish into a console nobody has open. When that happens the page also shows a
red banner rather than sitting silently on "Loading…".

Run `--fetch` when a pool is reissued or the committee issues a correction; it re-downloads
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

**The menu entry is not a question the installer asks.** It is how somebody who
does not use a terminal finds the program again tomorrow, it is invisible until
looked for, and one line removes it. The desktop is a different matter — a desk
is a surface people keep deliberately, and an icon put there unasked is a thing
done to somebody's desk. So `./install.sh` asks about that part only:

```
  ELMER goes in the applications menu. And on the desktop?
    1  Menu and desktop
    2  Menu only
    3  Neither — I will start it from the terminal
```

The third is there for a headless box or a tidy desktop, and it says the
command to start it so nobody who picks it is left stranded. Menu-only is
`./elmer.py --install-launcher --no-desktop-icon`, and choosing it having had a
desktop icon before removes the one that is there — the answer is about now,
not about what was picked last time.

The icon is installed into the hicolor theme at 48, 64, 128, 256 and 512 px
from `elmer/static/icon.png`, so replacing the icon and re-running the install
updates the menu too.

### Printing what is near

**Print nearest** on the Parks and summits page builds a sheet of the closest
references — parks, summits, or both — and puts it on the printout shelf like
every other PDF ELMER makes.

The printed one is not the screen one. It goes in the vehicle, so it carries
coordinates: the next thing anybody does with a reference they have chosen is
type it into something that wants numbers, and a phone at a trailhead with no
signal will not look it up. It keeps the screen's colours — green for parks,
blue for summits — so nobody has to learn a second scheme. And it prints the
count held against the count shown, because a sheet listing thirty parks where
four hundred and eighty-five are held must not be mistaken for the whole of
what is within reach.

The search is a **band**, not a radius: *between 0 and 50 miles*, or 30 and 40,
or 0 and 10 — in whatever units you read distances in, set once behind the gear
and used by the filter, the table and the sheet alike. The trips people take are bands — nought to ten miles is an
evening after work, thirty to forty is somewhere worth the drive with nothing
already worked in between — and a list that always starts at the doorstep
buries the second kind under the first. And it can be centred somewhere else — **from where I am now**, or from where
you are going. Type a town, a grid square or coordinates; the last two resolve
without touching the network. Asking about somewhere nothing has been fetched
for says so, and says that rather than "nothing is near there", because those
are different facts and only one of them is about the place.

It prints what is already on the disk and never fetches. Fetching is a
separate press because it is thirty-odd requests and the better part of a
minute, which is not a thing to start by accident from a button marked print.

### The gear

It also holds **Distances in** — metric, imperial or nautical. That preference
is deliberately narrow: it governs how far away a *thing* is, and nothing else.
Nobody calls it the forty yard band. Wavelength stays in metres because the
bands are named in metres, wire stays in feet because that is how wire is sold
and how every handbook table prints it, and hmF2 and skip distance stay in
kilometres because that is what ionosondes report. An operator choosing
imperial is saying how they think about a drive to a park, not asking for 40 m
to be renamed.


A gear at the right-hand end of the top bar opens **Your station**: what ELMER
calls you, your callsign, your licence class, and where you operate from.

None of it is new ground. The callsign is on the Band Plan, the QTH is on the
map, the name is in the account menu, and all of that stays exactly where it is
— that is where each one is wanted in the moment it is wanted. What was missing
was a way back for somebody who said *later* the first time and then could not
remember which page had asked. A gear in the corner is where people already
look for that.

Each field saves through the same endpoint the page it came from uses, so there
is one way of setting a callsign rather than two that can drift apart. Nothing
in it is required: ELMER works with all of it empty, and each entry only lets it
answer something it otherwise has to ask about or guess at.

### Walking into a pool that is not open

The gate refuses with a page rather than the framework's own 403. That page has
the reason on it, **Open every pool anyway** next to the reason, **Esc** bound
to go back, and a clock that goes back on its own after eight seconds.

The word *Forbidden* on a bare error page is a dead end on a kiosk: a
full-screen browser has no back button, and nobody is standing there to type a
URL. Escape is bound because that is what a person presses when something
appears that they did not want; the clock is there for somebody who does not
know that. Any press stops the clock — anything pressed is somebody deciding
for themselves, and the clock exists for when nobody does.

An API asking the same question still gets JSON. Handing a page back to
something fetching `/api` turns a working refusal into a parse error.

## The tests cannot reach your data

Every test imports `tests/_isolate.py` before anything from the program. It
moves the operator's state — the database, the log, the print shelf, every
cache, the notes — to a fresh temporary directory by setting `ELMER_STATE`,
so a test that asks the app a question is asking a blank unit rather than
yours; what ships with the program (the pools, the figures) is still found
where it ships. It also watches, through Python's audit hook, everything the
test process does to the real `data/` — every file opened for writing, every
database connected to even to read, every remove or rename — and fails the run
with **ISOLATION BREACH** if there was any, so a test that reaches your files
by a path the helper did not know about fails loudly instead of leaving a
stranger's club name in your settings, which is what happened, four times in
one day, before this existed. An audit hook rather than a fingerprint of the
directory, because ELMER is usually running on the machine the tests run on
and writes its log and database every second; a fingerprint blamed the tests
for the kiosk. `tests/test_isolation.py` proves the guard against a stand-in
directory, and that another process writing there is not blamed on this one.

`tests/test_pages_run.py` goes further than any of that: it starts a
throwaway ELMER and loads every page in the Chromium the kiosk already runs,
and asks each page whether a function its script defines exists. Twice in one
day a page's inline script had died at parse time and the page ran with no
script at all — once from a stray `});`, once from a `let` beside a function
of the same name — and nothing short of a JavaScript engine can catch the
second. It needs Chromium and fails, not skips, without it.

`ELMER_STATE` is for the tests. Left unset, everything is in `data/` as it
always was.

## Kiosk mode

On a Pi with a monitor, ELMER is an appliance:

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

Starting takes a moment on a cold card — a megabyte of pools comes off it the
first time a page asks for one, which is why the socket can be bound in a tenth
of a second while the first page still takes five. The browser opens straight
away on a splash screen held on disk — the owl tile out of `artwork/Mixed.jpg` —
and the kiosk asks for the first page behind it, so the pools are coming off the
card during the hold rather than after it. The splash lifts once the server
answers and never sooner than four seconds, which is set to about the median
start rather than to the slowest board: a fast machine would otherwise flash the
splash and be gone while a slow one sat on it, and every board should open the
same way.

What that first page actually cost is written down rather than shown — to
`data/elmer.log`, and to `--doctor`, which reports it as **start** and answers
over HTTP at `/api/doctor`. So one unit can read what every other unit on the
network took to come up, and a median can be taken from a chair instead of on
foot. It is the page's own build time that is kept, not the wall clock: a unit
nobody opens until morning would otherwise record an eight hour start.

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
**Back to ELMER** and an option to open the link in an ordinary window that has a
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
the wire in clear, and anybody holding the Pi holds the database - though
since the seal below, not the private fields in it. It is a lock on a
cupboard, not a safe - so use a password you do not use anywhere else.

**A callsign is what ELMER calls you.** Somebody who has one earned it in front
of volunteer examiners, so that is the name the program uses — the same respect
an operator gets on the air. Everyone else is called by their name, which is
theirs and needs no license. Add a callsign later and ELMER starts using it, at
the moment they actually earned it.

Once there are two of you the dashboard grows a **shack** panel: everyone side
by side, their standing in each track, questions answered this week, accuracy,
streak and XP. It sorts by what was answered this week, because that is the
figure anybody can do something about today.

`--stats` prints whoever is first on the unit, plus a roster of everybody;
`--stats --user NAME` prints somebody in particular.

Existing installs need nothing done. The first time ELMER opens a database from
before it could be shared it migrates it in one transaction — every card, answer,
exam, title and achievement carried over — and whoever was using it becomes the
first user on the unit.

### The seal: private data under the password

A password on an account also seals its private data: the QTH, any token
(RepeaterBook's is the first), and the notes on questions. Sealed means the
database file gives them to nobody - not somebody with the disk, not a
backup, not the SD card image passed round a club - because the key is the
password's and ELMER keeps it only in memory while the person is signed in.
The shape is in `elmer/seal.py`: a random data key per account, wrapped
under a key scrypt makes from the password, and wrapped a second time under
a recovery code shown once when the seal is made. Each field is encrypted on
its own under the data key. Changing the password re-wraps the key and
touches no data; taking the password off unseals everything back to plain.

The cipher is HMAC-SHA256 in counter mode with an HMAC tag, because the
standard library has HMAC and not AES, and a cipher dependency on every Pi
in a shack was a worse trade than a construction that is sound as long as
the nonce is fresh - and it is sixteen random bytes every time.

What stays plain, on purpose: the name, the callsign, the rank, the streak
and XP, because the room's boards show them and a callsign is a public
record; and the study record itself, because the streak and the scheduler
count from it, it is the least sensitive thing on the unit, and a forgotten
password should never be able to take it away.

**The moderator opens the account, not the seal.** A moderator reset takes
the password wrap away and leaves the sealed fields behind the recovery
code; the account works, and its QTH and notes wait for the code. That is a
real consequence and the dialog says it in one sentence when the password is
set. It would have been nicer to let the moderator key open the seal too,
and it cannot be done honestly without public-key cryptography, which the
standard library also has not got: the moderator's key is not present when a
member sets their password, so nothing can be wrapped under it then.

**Why not the whole database.** SQLCipher would need a library the standard
install has not got; the key problem would stay exactly as it is, since a
program that runs unattended - the kiosk, the weekly mail, the GPS - must be
able to open its own database with nobody present, which means the key on
the same disk as the data; and the record it would protect is the one whose
loss to a forgotten password matters most. The seal covers what a person
would not want read, at the cost of it being unavailable while they are
away, which is the cost a person choosing a password has chosen.

**The key in flight.** A browser that gives the password gets an HttpOnly
token for the key, held in the server's memory against that token and never
written anywhere. A restart forgets every key; the account menu then offers
**Unlock**, and the password opens the account and the seal together.

### The bank shot off a soft cushion

The reach map banks every ray off the F layer like a ball off a cushion:
the launch angle sets the angle of incidence on a curved earth, the
reflection lands the ball a known distance out. It used to bank off a
mirror at the F2 peak and rate every cell, near or far, against the 3000
km hop's ceiling with the 3000 km hop's absorption, which is right for DX
and wrong for the county: at noon on 40 m under a critical frequency of
8 MHz the near cells went dark, when they are the best on the map.

The cushion is soft. The ionosphere refracts rather than reflects, and
Breit and Tuve's theorem says the ray lands where a mirror at the *virtual*
height would land, Martyn's that the virtual height for an oblique ray is
a vertical ray's at the equivalent frequency f cos(phi). A parabolic layer
has that virtual height in closed form, climbing with frequency and running
away at the critical frequency, and the sonde gives its numbers: the peak
height, the critical frequency, and M(3000)F2. `patterns.py` carries the
layer; its semi-thickness is a third of its height, because fitting it to
the sonde's M(3000) gave absurd layers when a sonde's own two numbers
disagreed slightly, and the sonde's factor is honoured instead by scaling
the curve to pass through 1 straight up and the station's own factor at
3000 km. The shape is the layer's, the level is the sonde's.

So each cell is rated against its own hop's ceiling - foF2 times the factor
for that distance - with the D-layer absorption scaled by how obliquely the
hop crosses it, near-vertical paying a quarter of a long hop. The NVIS door
is the same factor at a few hundred kilometres, so the words and the map
cannot disagree. And the antenna's weighting keeps the level of the two-ray
pattern - 1.0 is the element alone in free space - so a wire a fifth of a
wave up is credited the image's reinforcement overhead, up to the 6 dB it
can give, and a wire half a wave up is charged the dip there, which over
real ground is a seven-decibel dip and not the null perfect ground promised.

What is still not modelled: tilts in the layer at dawn and dusk, the
ordinary and extraordinary rays, sporadic E, and the outlook's band-level
score, which stays against MUF(3000) because that is what a MUF is and
what the DX rating is read for.

### A shared unit asks first

The lock above had a hole in its timing. An open account can be switched
into by anyone and given a password by anyone, and whoever does that first
owns it - and the offer of a password went to whoever held the controls
after a second account was made, which is the second person. So the unit is
now asked whether it is shared, once, the first time a second account is
about to be made, and on a shared unit the person at the controls is asked
to lock their own account before the second one exists. That is the one
moment its owner is certainly the one at the controls. The server refuses
the add until the questions are answered, so no page can skip them; leaving
the account open is a real answer and is not asked again. On a shared unit a
token needs a password on the account, and the self-check names any account
left open.

### The log never holds the station

The problem report used to take the callsign, the grid, the town and the
home folder out of the log on the way out. That protected the report and
nothing else: the log on the disk still said whose unit it was. The same
redaction now runs in the log's formatter, on every line as it is written,
tracebacks included, so the file never holds the station whoever reads it.
A town is an ordinary word no pattern finds, so the names the unit holds -
the QTH's town, a callsign - are registered with the log as they are learned
and taken out by name.

## Running the installer again

`./install.sh` on a machine that already has ELMER does not quietly install it
again. It looks for study data, a virtual environment or a menu entry belonging
to this copy, and if it finds any of them it asks what you came for:

```
ELMER is already installed here
  found: study data, menu entry

    1) Update    fetch the latest ELMER and apply it
    2) Repair    put back anything missing or changed, and re-check
    3) Change    where the icons go: menu, desktop, or neither
    4) Remove    take away the menu entry and the virtualenv
    5) Check     run the self-check and change nothing
    6) Quit
```

**Change** is third because it is the one you come back for. Update and repair
are things that have gone wrong; changing your mind about an icon has not, and
having to run a whole reinstall to be asked again is how somebody ends up
sitting there hunting for the way to do it.

The same five are flags for a scripted run — `--update`, `--repair`, `--change`
(`--icons` means the same), `--check`, `--remove` (`--uninstall` still means the
same). A run with `--yes`, or one with
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

**The short way: the portable zip.** `tools/build_windows_zip.ps1` builds
`ELMER-windows-<build>.zip` on a Windows runner, through
`.github/workflows/release.yml`, for every tag that starts with `v` — and
the first such tag has not been cut yet, so until it appears on the
repository's *Releases* page the way in is the clone below. When it is
there: unzip it anywhere, double-click `elmer.cmd`, and ELMER opens in your
browser. Nothing is installed: the zip
carries its own Python (the official embeddable one from python.org, signed
by the Python Software Foundation, which is why Windows does not put up its
"unrecognized app" screen the way it would for a home-made `.exe`), with
Flask, Pillow, reportlab and pyserial already inside. No administrator
rights, no execution policy, nothing to answer. It cannot update itself -
there is no git in it - and the dashboard says so; to give it that, run
`install.ps1` in the folder once, as below, and say yes when it offers git
and the connect step. From then on it is an ordinary checkout that updates
like every other.

**The other way: from a clone or a download of the source.** Open
PowerShell in the ELMER folder - right-click the folder, *Open in
Terminal* - and:

```
powershell -ExecutionPolicy Bypass -File install.ps1
.\elmer.cmd
```

The execution policy on a Windows client defaults to Restricted, which is why
the first part is not optional; it applies to that one command and changes
nothing about the machine. There is no path in the script to edit: it runs
from wherever the folder is.

The installer looks for Python, git and poppler. Each one that is missing is
named, with what it is for, and offered - and installed with `winget`, which
every Windows 10 and 11 machine has, only when you answer yes. Python is what
ELMER is written in; git is how it updates itself; poppler reads the NIFOG
channel PDF and the manuals on the shelf, and everything else works without
it. `-Yes` answers for you, for a machine you are setting up in one go;
`-NoInstall` only reports, for one somebody else looks after. Then it builds
a virtual environment in `.venv` and puts Flask, Pillow and reportlab in it.
`-Shortcut` adds a Start Menu entry, `-Serial` adds pyserial so the Lab can
talk to a NanoVNA.

**The window, and closing it.** On Windows ELMER opens in a window of its
own - Edge or Chrome as an *app window*, in a profile of ELMER's own, so it
is a process of ELMER's own - and closing that window stops ELMER, the way
the kiosk's Exit button does on a Pi. By the time it has closed nothing can
be said, so the saying is done ahead of time: the window knows it is the
window, asks every few seconds how many real people are on the unit - at
its own table, and at the other tables of a net it is running - and while
there are any, says so across the top and arms the browser's own
leave-page question at close. With nobody on it, it closes like any other.
"Anybody" means people on other devices - phones at the table, other
tables of the net. Somebody seated at the screen itself is looking at the
window, and closing it is their own act; counting them had the banner
warning the one person in the room about themselves, all through a round
of golf played alone. And during golf nothing is said at all: the party
is on the scorecard, in the clubhouse and on the course, and the operator
can see everyone in it. The one warning left is for a net this unit is
hosting with people at other tables - and that one goes too once a
closing host can hand the net to the next unit that can carry it (see the
open threads).
Where neither browser is found the page opens as a tab in the default
browser instead, and the console says the tab will not stop the server.

**The developer's reset, on Windows.** The Developer panel's reset used
to run `git clean` in place and said it had. On Windows it had not: the
running server holds the database and the log, the ELMER window holds its
browser profile, and Windows will not delete an open file - every item
failed with "Invalid argument" and the study was still there. Now the
press marks the reset (`data/reset-pending`) and restarts ELMER the way an
update does; the new process finds the mark before it opens anything and
does the clean then, when nothing is held, retrying for a few seconds
while the closed browser lets go of its profile. The mark is untracked
inside data/, so the clean takes it too.

**The Start Menu, and Exit.** The installer offers to put ELMER on the
Start Menu with its own icon, and a shortcut already there is refreshed to
point at the folder it ran from. The window has an **Exit** button in its
top bar, as the kiosk does - and, as the kiosk's does now too, it asks
first, naming who it would stop: *"3 people at 1 other table of the net
are playing on this unit. Stop ELMER anyway?"*

**The other copies.** A Windows machine collects them - a zip unzipped
twice, a clone, OneDrive's Desktop - and a double-click lands on whichever
one Explorer was showing, usually the one that was never installed. So a
copy that cannot run looks for the others: if an installed ELMER is on the
machine it says where, with its build and how much study is in it, and
offers to start that one instead. `elmer.py --copies` lists every copy the
same way; `--tidy` offers to remove the ones with nothing in them, one
question each, and the installer does that at its end. A copy with study,
settings or reports in it is named and never removed - that is somebody's
progress, and moving it is their decision.

WSL is not the way in. It works, but it wants administrator rights, a reboot
and virtualization turned on in firmware, and the COM ports for a NanoVNA or
a GPS do not reach it - a wall in front of exactly the person the installer
is for. ELMER runs on Windows itself.

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
cannot read its PDF until poppler is here. The installer checks, says so and
offers it; a winget install lands under `%LOCALAPPDATA%\Microsoft\WinGet`
and ELMER looks there, so a shortcut-started ELMER finds it without PATH
having been told.

`tests/test_host.py` passes on both, and forces each machine's rules on the
other - a rule only ever run where it was written is a habit rather than a
rule.

## The cup of coffee

ELMER is a gift to the amateur radio community, which has given its author
a great deal, and it is free for everyone. Some people will want to thank
the developer with a cup of coffee, and the program should notice that
without ever turning into a toll gate. The rules, and why:

**A person who has is thanked; a person who has not is asked once.** A
supporter enters a key under Station and from then on the dashboard says
thank you, once a day, and says what the coffee meant: how many times ELMER
has changed since it was bought, read off the changelog, with the latest
three lines. Watching the thing you fed grow is the reward, and it is true
every time it is shown. Without a key the dashboard offers a coffee once,
after ten hours of actually answering questions - the meter is the answers'
recorded times, each capped at five minutes so a walk-away does not clock an
afternoon - and then not again for a hundred hours more. The card is a panel
in the dashboard's flow, never a modal, never inside a question, an exam or
a hall's show, and it says plainly that ELMER stays free either way. The
wording is an observation, not a bill: the developer has several hobbies
competing for their evenings, and a coffee is how this one wins a few more
of them.

**The meter is the person's, not the machine's.** A club's shared Pi has
accounts on it; each has its own hours and its own answer, so the unit does
not nag every visitor on behalf of the first one.

**The key is eight characters, bound to a name, and real only on the
roster.** `XXXX-XXXX`, from an alphabet with no 0, O, 1 or I. The first
four are the registration part, a tier letter and three characters drawn
at random when the key is cut; the last four are the validation part, a
keyed hash of the first four and the holder's name, so a typo or a key
typed under somebody else's name is caught on the unit before anything is
looked up. The holder is whatever the sponsor asked to have printed - a
callsign, a name, a club - so a supporter with no callsign is no special
case.

Eight characters cannot carry a signature, and a program that verifies
offline cannot keep a secret from whoever reads it, so the first draft of
this - a keyed hash alone - was a lock whose key was in the source. What
makes a key real is the roster: every key the developer cuts goes onto
`supporters.roster` beside the README, a list of hashes of key and name
signed with the developer's private key. The private key never leaves the
developer's machine (`elmer.py --issuer-init` makes it; it lives at
`~/.elmer/issuer.key`, outside the repository); the public key is in
`elmer/roster.py`; a unit accepts a typed key only when it is on a roster
whose signature checks, in plain-Python Ed25519 (`elmer/ed25519.py`,
against the RFC's own test vectors). Reading the source gives a would-be
counterfeiter the typo check and not the signature, so nobody cuts keys
for their friends; a key that was issued can be taken off the roster
again (`--revoke-key`); and the roster names nobody, so it can be public.
Who chose to be named is SUPPORTERS.md, a different list.

A key cut tonight is on tonight's roster, which ships with the next
update. A unit that has not updated fetches the current roster from the
repository once, when a key is typed in and not found here - the one
request ELMER makes that is not the propagation page - and keeps the copy
under its state directory; a unit with no network accepts the key after
its next update, and says so. Only the developer cuts keys, by hand
(`elmer.py --supporter-key "John Doe"`, kept out of `--help`), and sends
them back in reply to the sponsorship note. The key opens nothing and its
absence closes nothing - that is what keeps it a gift.

**In a hall, the thanks is honorary.** A supporter who ticked "name me"
has their callsign carried to net control in the check-in their table
already sends once a second. On that table, ELMER's own card in the
rotation becomes theirs for its dwell - "This shootout is brought to you by
the generous contribution of KC9SP", the game named from what is running -
and a roll-of-thanks card lists the evening's sponsors and the supporters
in the room, net control's own first. The same roll goes on a line under
the certificates and a line on the join page. A supporter who would rather
not be named is not, anywhere, and the host can leave the thanks card out
of the deck like any other.

## Requirements

Python 3.11 or later with Flask, Pillow and reportlab (`requirements.txt`).
Optional: `pdftotext`, `pdftoppm` and `pdfimages` from poppler-utils, to
rebuild the pools and read PDFs on the library shelf; pyserial, to talk to a
NanoVNA; TowerWitch's own packages, only if it sits beside ELMER. All present
or one apt line away on Raspberry Pi OS; on Windows `install.ps1` fetches the
Python side and offers what is missing, and the self-check names the rest.
Serving needs no network; what reaches out is listed under *What leaves a
unit*.

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
question and its keyed answer is exactly what the released document says, with
every correction the committee has issued since release applied, because that
is what you will see on the test.

The GROL and Element 8 pools date from 2009 and the FCC has not reissued them;
they remain the current pools in use. Some formulas in Element 3 lost their
superscripts when the FCC typeset the PDF (`R2+X2` for √(R²+X²)); those are
reproduced as published.

Progress is stored locally in `data/elmer.db` on the unit. What can leave a
unit, and only by your hand, is set out under *Fidelity* and *Mail home*.
