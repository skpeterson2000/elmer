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
import json
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
    """The rows this needs: the unit's own log and the hall's, as one list.

    A hall person is keyed "hall:<who>" so they can never collide with a
    study user's integer id, and the measure treats them exactly alike - a
    person, a day, a question, right or not, how long.

    Each row carries the license class the person holds, or "" for not
    said: the hall's from what they told the table when they sat down, a
    study user's from their own profile as it stands now - which is the
    class they hold today, not necessarily the one they held when they
    answered, and close enough for a report about how knowledge wears.
    """
    from .db import _modernise, license_of
    held = {}
    for p in conn.execute("SELECT id, settings FROM profile"):
        try:
            s = _modernise(json.loads(p["settings"] or "{}"))
        except ValueError:
            s = {}
        held[p["id"]] = license_of(s.get("license_class")
                                   or (s.get("license") or {}).get("license_class"))
    rows = [dict(r) for r in conn.execute(
        "SELECT user_id, ts, day, question_id, correct, ms FROM answer_log "
        "WHERE pool_id = ? ORDER BY ts", (pool_id,))]
    for r in rows:
        r["source"] = "study"
        r["license"] = held.get(r["user_id"], "")
    try:
        hall = conn.execute(
            "SELECT who, ts, day, question_id, correct, ms, license FROM hall_log "
            "WHERE pool_id = ? ORDER BY ts", (pool_id,)).fetchall()
    except Exception:                    # a database from before the hall log
        hall = []
    for h in hall:
        rows.append({"user_id": "hall:" + h["who"], "ts": h["ts"], "day": h["day"],
                     "question_id": h["question_id"], "correct": h["correct"],
                     "ms": h["ms"], "source": "hall", "license": h["license"] or ""})
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
