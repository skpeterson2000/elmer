"""How hard a question is - measured from how it went, not guessed from its look.

ELMER had no measure of difficulty. The tournament's draw could not be
ordered easiest-first, and the Elmer running a class had no way to see which
twelve questions were where the room got lost. Inventing one from a
question's length or whether it has a formula in it would be a guess wearing
the clothes of data, and this program's credibility is that its numbers are
measured.

So it is measured, from the unit's own answer log, the way KC9SP put it:
"How long did they take? How long did they average across the span of
questions answered - adjusts for reading level and declined cognition -
that is difficulty." Two things go into it, because either alone lies:

**Time, normalised per person per sitting.** A question's time is compared
with what the *same person* took on the other questions they answered *that
day*: log(ms) minus that sitting's median log(ms). Dividing out the person is
what makes a seventeen-year-old's answers and a seventy-four-year-old's
comparable in one table, and doing it per sitting absorbs a tired evening
without anybody having to model it. Reading length is deliberately not
corrected for: the normalisation handles the reader, not the question, and a
sixty-word question genuinely is harder under a clock.

**Whether they got it.** A guess is fast. "No idea, click" and "I know this
cold" are the same milliseconds, so time alone would rank every question
nobody knows as easy. Miss rate stops that. It saturates - once everybody
has learned a question it reads as easy however many tries it took - which is
why it is not used alone either.

**First exposures only.** Spaced repetition shows a question again on
purpose, and the fourth sighting is fast whatever the question. The first
time a person meets a question is the clean measurement, and every person on
the unit contributes one per question - which is why showing every question
at least once is the tournament's quiet objective.

**Unmeasured is a state, not a zero.** A question fewer than MIN_N people
have met is not ranked. On a fresh unit that is every question, the draw
stays in blueprint order, and the flag that says so is `ramped: False` - the
same honesty as the monitoring module saying it has not read your state's
law, or the path tool saying it is blind without a sonde.

Study answers carry a time; exam answers do not and contribute only to the
miss rate; answers given on phones at a table are not in this log at all.
A hall's reports would be a second source, later.
"""
import math
from statistics import median

# How many first exposures a question needs before it is ranked at all.
# Three is the fewest that can disagree with each other.
MIN_N = 3

# How much of the draw must be measured before the order is called a ramp.
# A ramp built from a quarter of the questions is three quarters of the
# tournament in an order chosen by where the gaps fell.
RAMP_COVERAGE = 0.6

# The two halves, weighted equally. Both are on [0, 1]: the miss rate as it
# is, and the normalised time squashed so that "typical for that person" sits
# at 0.5. Equal weights are a judgement and are labelled as one.
W_MISS = 0.5
W_TIME = 0.5


def _first_exposures(rows):
    """One row per (user, question): the earliest. Rows come sorted by ts."""
    seen = {}
    for r in rows:
        key = (r["user_id"], r["question_id"])
        if key not in seen:
            seen[key] = r
    return list(seen.values())


def _sitting_medians(rows):
    """Median log(ms) per (user, day), over every answer that had a time."""
    by_sitting = {}
    for r in rows:
        ms = r.get("ms")
        if ms and ms > 0:
            by_sitting.setdefault((r["user_id"], r["day"]), []).append(math.log(ms))
    return {k: median(v) for k, v in by_sitting.items() if v}


def measure(rows):
    """Per question: how it went for the people who met it for the first time.

    `rows` are answer_log rows for one pool, oldest first, with user_id, day,
    question_id, correct and ms. Returns {question_id: {...}}; questions
    nobody has met are simply absent, and ones too few have met are present
    with measured=False.
    """
    rows = sorted(rows, key=lambda r: r["ts"])
    medians = _sitting_medians(rows)          # every answer, not only firsts
    firsts = _first_exposures(rows)
    per = {}
    for r in firsts:
        q = per.setdefault(r["question_id"], {"n": 0, "wrong": 0, "z": []})
        q["n"] += 1
        if not r["correct"]:
            q["wrong"] += 1
        ms = r.get("ms")
        m = medians.get((r["user_id"], r["day"]))
        if ms and ms > 0 and m is not None:
            q["z"].append(math.log(ms) - m)
    out = {}
    for qid, q in per.items():
        miss = q["wrong"] / q["n"]
        z = median(q["z"]) if q["z"] else None
        time_part = 0.5 + 0.5 * math.tanh(z) if z is not None else 0.5
        out[qid] = {
            "n": q["n"], "miss_rate": round(miss, 3),
            "median_z": round(z, 3) if z is not None else None,
            "timed": len(q["z"]),
            "hardness": round(W_MISS * miss + W_TIME * time_part, 3),
            "measured": q["n"] >= MIN_N,
        }
    return out


def ranker(measured):
    """A callable for tournament.ordered(): hardness, or None if unmeasured."""
    def difficulty_of(question):
        m = measured.get(question["id"])
        return m["hardness"] if m and m["measured"] else None
    return difficulty_of


def coverage(measured, question_ids):
    """What fraction of these questions is ranked - the honest summary."""
    ids = list(question_ids)
    if not ids:
        return 0.0
    return sum(1 for q in ids if measured.get(q, {}).get("measured")) / len(ids)


def hardest(measured, limit=12):
    """The questions the people on this unit found hardest, best-known first."""
    ranked = [(qid, m) for qid, m in measured.items() if m["measured"]]
    ranked.sort(key=lambda km: (-km[1]["hardness"], -km[1]["n"], km[0]))
    return [{"question_id": qid, **m} for qid, m in ranked[:limit]]


def load(conn, pool_id):
    """The rows this needs, from the unit's own log, every user."""
    return [dict(r) for r in conn.execute(
        "SELECT user_id, ts, day, question_id, correct, ms FROM answer_log "
        "WHERE pool_id = ? ORDER BY ts", (pool_id,))]
