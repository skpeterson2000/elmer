"""When somebody studying here is ready to go and be examined for real.

ELMER can say, with a Monte Carlo over the actual pool and a run of mock
exams behind it, that a person would very probably pass. What it had no way
of saying was the next thing: go and do it. The program would happily have
let somebody drill a pool to ninety-five per cent for a year.

So when there is no licence on this account's record and a pool's evidence
says ready, the dashboard says so, and says what the day actually involves -
an FRN before you go, a session to book, a team that sets its own fee, and
the Commission's application fee afterwards. Those are the four things that
stop people, and none of them is the exam.

**Two stages, because "nearly" is worth hearing too.** *Approaching* is a
pool where the odds are good and at least one mock exam has been passed -
the point where it is worth finding out when the local team next sits.
*Ready* is the class tier in :mod:`elmer.ranks`, which already asks for
ninety per cent of the pool seen, eighty-five per cent odds, and two of the
last three mock exams passed. That is evidence, not encouragement.

**What is said about the licence itself.** Not "you are unlicensed" - ELMER
does not know that, it knows only that no licence is on record for this
account, which is a different sentence and the only one it is entitled to.
The same care :mod:`elmer.ranks` takes in the other direction: nothing here
may leave anybody with the impression that the program has licensed them, or
that it has judged them unlicensed.

**And what the ticket is.** The operator's own words, kept because they are
the reason the feature exists rather than a nag: it is more than a privilege
that incurs legal and ethical obligations; it is knowledge, and that carries
the imperative to be a generous ambassador for the craft who demonstrates
competence, and a willingness to share that competence with the developing
operator in kindness. A person who has just been told they will pass is the
right person to hear it, because they are about to become the operator a
newcomer asks.
"""
import logging

from . import callsign, gating, ranks

log = logging.getLogger("elmer")

# Approaching: good odds and a mock exam actually sat and passed. The odds
# alone are not enough - a pool half seen can read high, and the exam is the
# part with the nerves in it.
NEARLY_ODDS = 0.75

# Where a session is found, an FRN is got, and the fee is paid. Checked
# rather than trusted: fees and forms change, and a study tool that prints a
# stale number is worse than one that prints none, so the figure here is
# shown as something to confirm before anybody relies on it.
SESSION_FINDER = "https://www.arrl.org/find-an-amateur-radio-license-exam-session"
CORES = "https://apps.fcc.gov/cores/"
FCC_FEE = 35                   # dollars, on application, after a pass
FEE_NOTE = "worth confirming on the FCC's own fee schedule before you go"

STEPS = [
    ("Get an FRN first",
     "An FCC Registration Number, free from the Commission's CORES system. "
     "You need it before you sit down, not after - the team asks for it on "
     "the form, and a session is a poor place to be registering for the "
     "first time.", CORES, "FCC CORES"),
    ("Find a session",
     "Volunteer Examiner teams run them at clubs, hamfests, libraries and "
     "over video. The ARRL's search lists sessions by place and date; other "
     "VECs run their own, and remote sessions are sat from home.",
     SESSION_FINDER, "ARRL session search"),
    ("Take what the team asks for",
     "Photo identification, your FRN, and the team's own test fee - each "
     "team sets that itself, and some charge nothing. Ask when you book.",
     None, None),
    ("The Commission's fee comes after",
     "Pass, and the VEC files for you; the FCC then emails a link to pay its "
     "application fee, with a short window to do it in. Miss that and the "
     "application lapses, which is a sad way to lose an exam you passed.",
     None, None),
]

# The paragraph that is the point of the panel. Said once, on the screen
# where somebody has just been told they are ready.
CHARGE = (
    "A licence is more than a privilege that carries legal and ethical "
    "obligations. It is knowledge, and knowledge carries its own imperative: "
    "to be a generous ambassador for the craft, to demonstrate competence, "
    "and to share that competence with the developing operator in kindness. "
    "The person who helps you at your first session was helped at theirs."
)

CLASS_NAMES = {"tech2026": "Technician", "gen2023": "General",
               "extra2024": "Amateur Extra"}


def on_record(settings):
    """Whether a licence class is known for this account, and whose word it is.

    Deliberately not named ``licensed``. The answer is about ELMER's record,
    not about the person: an operator licensed for thirty years who has never
    typed their callsign in is not unlicensed, they are unrecorded, and the
    panel this drives must never confuse the two.
    """
    return bool(callsign.held(settings)["class"])


def _stage(standing):
    """Where one pool's evidence sits: "ready", "approaching", or None."""
    if standing.get("step", 0) >= ranks.CLASS:
        return "ready"
    if (standing.get("pass_probability") or 0) >= NEARLY_ODDS \
            and (standing.get("exams") or {}).get("passed", 0) >= 1:
        return "approaching"
    return None


def call_to_action(settings, standings):
    """The dashboard panel, or None when there is nothing to say.

    Nothing is said when a licence class is already on record, and nothing is
    said until a pool's own evidence has reached at least "approaching" - so
    the panel arrives once, at the moment it is true, rather than sitting on
    the dashboard from the first evening as one more thing to read past.
    """
    if on_record(settings):
        return None

    best = None
    for standing in standings or []:
        if standing.get("pool_id") not in gating.AMATEUR_LADDER:
            continue
        stage = _stage(standing)
        if not stage:
            continue
        # The highest class whose evidence holds up, and "ready" outranks
        # "approaching" whatever the class: being ready for Technician is
        # better news than nearly being ready for General.
        rank = (stage == "ready", gating.AMATEUR_LADDER.index(standing["pool_id"]))
        if best is None or rank > best[0]:
            best = (rank, stage, standing)

    if best is None:
        return None

    _, stage, standing = best
    pool_id = standing["pool_id"]
    name = CLASS_NAMES.get(pool_id, standing.get("class_name") or pool_id)
    odds = standing.get("pass_probability") or 0.0
    passed = (standing.get("exams") or {}).get("passed", 0)
    plural = "" if passed == 1 else "s"
    log.info("ticket: %s evidence says %s for %s (odds %.0f%%, %d mock "
             "exams passed)", pool_id, stage, name, 100 * odds, passed)

    if stage == "ready":
        headline = f"You are ready to sit {name} for real"
        reading = (
            f"ELMER puts your odds on a real {name} paper at "
            f"{round(100 * odds)}%, on {passed} mock exam{plural} passed and "
            f"the part of the pool you have actually seen. That is this "
            f"program's estimate against its own copy of the question pool, "
            f"not a promise - but it is the point at which another month of "
            f"drilling buys less than booking a seat.")
    else:
        headline = f"{name} is within reach"
        reading = (
            f"Your odds on a real {name} paper are around "
            f"{round(100 * odds)}%, with {passed} mock exam{plural} passed. "
            f"Worth finding out when the nearest team next sits - sessions "
            f"book up, and having the date in the diary is what turns "
            f"studying into sitting.")

    return {
        "stage": stage, "pool_id": pool_id, "class_name": name,
        "odds": odds, "exams_passed": passed,
        "headline": headline, "reading": reading,
        "steps": [{"title": t, "detail": d, "url": u, "link": l}
                  for t, d, u, l in STEPS],
        "charge": CHARGE,
        "fee": FCC_FEE, "fee_note": FEE_NOTE,
        "finder": SESSION_FINDER, "cores": CORES,
        # Said on the panel itself, so the one sentence ELMER is entitled to
        # about somebody's licence is the one printed.
        "record_note": ("No licence is on record for this account. If you "
                        "hold one, put your callsign in and this goes away."),
    }
