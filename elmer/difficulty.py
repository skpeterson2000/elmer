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

Two sources, one measure. The unit's own answer log is one person studying
here, a line at a time. The hall log is every answer the room gave when this
unit ran a net - twenty tables' worth in an evening, each with a time, and
the reason a club night sharpens the class report faster than a month of
study. A person in the hall is their callsign if they played under one, so
KC9SP at two tables is one pace, and otherwise the table and the name. Study
answers and hall answers carry a time; exam answers do not and contribute
only to the miss rate.
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
# at 0.5. Equal weights are a judgment and are labelled as one.
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


# --- how long it takes, and how long it lasts --------------------------------
# Hardness is one sighting. These two are the other time scales the ledger can
# measure: how many sightings a question takes before a person answers it
# without having to think, and how fast a right answer wears off afterwards.

# An answer is automatic when it is right and quick. Six seconds is where the
# scheduler already draws "fast" (srs.FAST_MS): long enough to read the
# question, too short to work it out.
AUTOMATIC_MS = 6000
# Answers inside one sitting are not forgetting - the question was on screen
# minutes ago. Only gaps longer than this count toward the decay rate.
DECAY_MIN_GAP_DAYS = 0.25


def _by_person(rows):
    """{(person, question): [answers, oldest first]}."""
    out = {}
    for r in sorted(rows, key=lambda r: r["ts"]):
        out.setdefault((r["user_id"], r["question_id"]), []).append(r)
    return out


def _days_between(a, b):
    from datetime import datetime
    try:
        return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 86400
    except (TypeError, ValueError):
        return None


def automaticity(rows):
    """Per question: how many sightings, and how many days, to automatic.

    Walks each person's answers to each question in order and stops at the
    first one that is right and under AUTOMATIC_MS. `reached` is how many of
    the people who met it got there at all; the medians are over those who
    did. A question with a high `sightings` and a low share reached is one
    that does not stick, whatever its first-exposure miss rate says.
    """
    per = {}
    for (_, qid), answers in _by_person(rows).items():
        q = per.setdefault(qid, {"people": 0, "reached": 0, "sightings": [], "days": []})
        q["people"] += 1
        for i, a in enumerate(answers, 1):
            if a["correct"] and a.get("ms") and a["ms"] <= AUTOMATIC_MS:
                q["reached"] += 1
                q["sightings"].append(i)
                days = _days_between(answers[0]["ts"], a["ts"])
                if days is not None:
                    q["days"].append(days)
                break
    out = {}
    for qid, q in per.items():
        out[qid] = {
            "people": q["people"], "reached": q["reached"],
            "sightings": median(q["sightings"]) if q["sightings"] else None,
            "days": round(median(q["days"]), 2) if q["days"] else None,
            "measured": q["reached"] >= MIN_N,
        }
    return out


def forgetting(rows):
    """How fast a right answer wears off: per question and over the pool.

    Every pair of consecutive answers by one person to one question, where
    the first was right and the gap is longer than a sitting, is a trial: did
    it survive the gap? Treated as a constant hazard, the rate is misses over
    total days of gap - the estimate for an exponential with the survivors
    counted as still running - and a half-life is ln 2 over that.

    It is a floor, not a truth: a right answer at the far end of the gap can
    be a lucky guess among four, so the real forgetting is somewhat faster.
    The comparison between questions is what it is for.
    """
    def summarise(pairs, forgot, days):
        rate = forgot / days if days > 0 else None
        return {"pairs": pairs, "forgot": forgot, "days": round(days, 2),
                "per_day": round(rate, 4) if rate is not None else None,
                "half_life_days": round(math.log(2) / rate, 1) if rate else None,
                "measured": pairs >= MIN_N}

    per, total = {}, [0, 0, 0.0]
    for (_, qid), answers in _by_person(rows).items():
        for a, b in zip(answers, answers[1:]):
            if not a["correct"]:
                continue
            gap = _days_between(a["ts"], b["ts"])
            if gap is None or gap < DECAY_MIN_GAP_DAYS:
                continue
            q = per.setdefault(qid, [0, 0, 0.0])
            lost = 0 if b["correct"] else 1
            for t in (q, total):
                t[0] += 1
                t[1] += lost
                t[2] += gap
    return ({qid: summarise(*q) for qid, q in per.items()}, summarise(*total))


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
    """The rows this needs, from the question ledger (ledger.py).

    The ledger holds every answer given on this unit - studying, on a mock
    exam, at a table in a hall - and, unlike the database, survives a
    developer reset: what has been learned about the questions is not thrown
    away with the people's cards. `conn` is only used to bring in, once,
    whatever this unit's database recorded before the ledger existed.

    A person is the ledger's opaque tag; a hall person's is prefixed "hall:"
    so the two can never collide, and the measure treats them exactly alike -
    a person, a day, a question, right or not, how long. Each row carries the
    license class the person held when they answered, or "" for not said.
    """
    from . import ledger
    ledger.backfill(conn)
    rows = []
    for r in ledger.answers(pool_id):
        rows.append({"user_id": r["person"], "ts": r["answered_ts"] or r["ts"],
                     "day": r["day"], "question_id": r["question_id"],
                     "correct": r["correct"], "ms": r["ms"], "source": r["source"],
                     "license": r["license"] or ""})
    rows.sort(key=lambda r: r["ts"])
    return rows


def by_license(rows):
    """How each license class did on this pool - the demographic that says
    how knowledge wears.

    A room of Generals answering Technician questions is people who passed
    this material once, some of them decades ago; a room of people with no
    license yet is the same material met for the first time. First exposures
    only, as the measure itself. The miss rate is the honest number; the
    median time is raw - not normalised per person, because the question here
    is precisely how one class compares with another - and is labelled so.
    Classes nobody stated are under "" and reported as unsaid, not dropped:
    a report that quietly leaves out the people who did not say would read as
    if everybody had.
    """
    firsts = _first_exposures(sorted(rows, key=lambda r: r["ts"]))
    per = {}
    for r in firsts:
        c = per.setdefault(r.get("license") or "", {"n": 0, "wrong": 0,
                                                    "people": set(), "ms": []})
        c["n"] += 1
        c["people"].add(r["user_id"])
        if not r["correct"]:
            c["wrong"] += 1
        ms = r.get("ms")
        if ms and ms > 0:
            c["ms"].append(ms)
    order = {"none": 0, "Novice": 1, "Technician": 2, "General": 3,
             "Advanced": 4, "Extra": 5, "": 6}
    out = []
    for name in sorted(per, key=lambda k: order.get(k, 6)):
        c = per[name]
        out.append({"license": name, "answers": c["n"], "people": len(c["people"]),
                    "miss_rate": round(c["wrong"] / c["n"], 3),
                    "median_ms": round(median(c["ms"])) if c["ms"] else None,
                    "timed": len(c["ms"])})
    return out


def sources(rows):
    """How many answers came from each place - the report says so."""
    out = {"study": 0, "hall": 0}
    for r in rows:
        out[r.get("source", "study")] = out.get(r.get("source", "study"), 0) + 1
    return out


def weak_sections(conn, pool_id, since_ts=0.0, min_n=4, limit=6):
    """Where tonight's room is missing, by section - for the host running it.

    The hall log carries the section beside every answer, so this needs no
    question table: count the answers to each section since the net opened
    and rank by the share missed. A section needs `min_n` answers before it
    is said at all - two people missing one question is not a weak section,
    it is two people - and the list is what an instructor acts on while the
    room is still in front of them: "everyone, ten minutes on T5".
    """
    try:
        rows = conn.execute(
            "SELECT section, correct FROM hall_log WHERE pool_id = ? AND ts >= ?",
            (pool_id, float(since_ts or 0.0))).fetchall()
    except Exception:                    # a database from before the hall log
        return []
    tally = {}
    for r in rows:
        sec = r["section"] or "?"
        slot = tally.setdefault(sec, {"section": sec, "answers": 0, "correct": 0})
        slot["answers"] += 1
        slot["correct"] += 1 if r["correct"] else 0
    out = []
    for slot in tally.values():
        if slot["answers"] < min_n:
            continue
        slot["miss"] = round(1.0 - slot["correct"] / slot["answers"], 2)
        out.append(slot)
    out.sort(key=lambda x: (-x["miss"], -x["answers"], x["section"]))
    return out[:limit]
