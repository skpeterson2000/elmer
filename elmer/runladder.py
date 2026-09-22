"""The run of right answers, and the bar it is measured against.

A person drilling a pool breaks their run at four, then at six, then at
eight, and one evening they do not break it at all. That progression is the
learning, and until now nothing showed it: the HUD counted the run up and
then quietly put it back to nought, so the only thing a miss said was that
the number was gone.

So the run is kept per pool, with three things beside it - the longest ever,
the bar currently being worked toward, and where the last few runs actually
broke. Ten in a row from one pool is the thing being aimed at, because ten
consecutive right answers drawn from the whole pool is roughly what sitting
the real exam feels like, and it is a number a person can hold in their head.

**The bar only ever goes up.** It starts at three, which almost anybody
clears in their first sitting, and it moves to the next rung each time it is
reached. A run that breaks below the bar does not lower it and costs
nothing. That is deliberate: this is meant to be a reason to keep answering,
and a bar that retreats when you miss is a bar that teaches you to stop while
you are ahead.

**The bar is visible, and fixed.** A hidden schedule that pays out on a
varying number of answers holds attention better - that is the whole finding
- but a study tool that does that to somebody is manipulating them rather
than teaching them. The rungs are printed, the next one is named, and a
person can aim at it.

**Ten once is not ten reliably.** ``TARGET`` reached ``SETTLED`` separate
times is what counts as having it, because a single clean run of ten is
partly the draw. Until then the ladder says how many times it has happened.

Per pool, and not global: a run built by bouncing between Technician and
General says nothing about readiness in either, and "ten in a row from a
selected pool" is the claim worth being able to make. The global run that
:mod:`elmer.game` keeps is a different measure and stays where it is - it is
what the Clean Run, Pileup and Solid Copy badges are cut from.

**A mock exam does not touch this.** The exam feeds the schedule and the
rank ladder, because those are measurements, but it is deliberately kept
away from the run ladder: this is a practice instrument, its whole job is to
shape what happens while somebody is drilling, and an exam that moved the
bar would be the measurement changing the instrument. It is also the one
place in the program that gives nothing back until it is handed in, and a
run counter ticking along behind a paper would be feedback.
"""
import logging

from . import db

log = logging.getLogger("elmer")

KEY = "run_ladder"

# The rungs, in order. Three is a first sitting; ten is the goal; the rest
# are there so somebody who has the goal still has somewhere to go.
RUNGS = (3, 5, 10, 15, 20, 25, 35, 50)
BEYOND = 25                    # how far the bar climbs once the table is spent

TARGET = 10                    # ten in a row, from one pool
SETTLED = 3                    # times the target must be reached to count as regular
KEEP_BREAKS = 8                # how many recent breaks are remembered, for the trend


def blank():
    return {"run": 0, "best": 0, "bar": RUNGS[0], "last_break": None,
            "breaks": [], "hits": 0}


def next_bar(bar):
    """The rung above ``bar``. Past the printed table it keeps climbing."""
    for rung in RUNGS:
        if rung > bar:
            return rung
    return bar + BEYOND


def _all(conn):
    stored = db.kv_get(conn, KEY, {}) or {}
    return stored if isinstance(stored, dict) else {}


def state(conn, pool_id):
    """One pool's ladder, with anything missing filled in.

    Read-only, and tolerant of a stored shape from an older build: a key that
    is not there is taken from :func:`blank` rather than raising on a page
    somebody opened to look at their progress.
    """
    kept = _all(conn).get(pool_id)
    ladder = blank()
    if isinstance(kept, dict):
        for field, default in blank().items():
            value = kept.get(field, default)
            ladder[field] = value if isinstance(value, type(default)) or default is None else default
    ladder["breaks"] = [int(b) for b in (ladder.get("breaks") or []) if isinstance(b, int)]
    return ladder


def view(conn, pool_id):
    """The ladder as a page wants it: the state plus what it means."""
    return _event(pool_id, state(conn, pool_id))


def _event(pool_id, ladder, reached=None, new_best=False, broke=None,
           previous_break=None, hit_target=False):
    """What just happened, in the shape the study page renders.

    ``reached`` and ``hit_target`` are not the same thing and both are
    needed. A rung is reached once - the bar moves past ten the first time
    somebody gets there, so the second and third ten in a row reach nothing
    at all. Those are exactly the ones that turn a lucky draw into having it,
    so they are reported on their own flag rather than being silent.
    """
    return {
        "pool_id": pool_id,
        "run": ladder["run"], "best": ladder["best"], "bar": ladder["bar"],
        "to_bar": max(0, ladder["bar"] - ladder["run"]),
        "target": TARGET, "rungs": list(RUNGS),
        "reached": reached, "hit_target": hit_target, "new_best": new_best,
        "broke": broke, "previous_break": previous_break,
        # A break further along than the one before it is the progression
        # this whole module exists to show.
        "improved": bool(broke and previous_break and broke > previous_break),
        "breaks": list(ladder["breaks"]),
        "hits": ladder["hits"], "settled": ladder["hits"] >= SETTLED,
        "hits_needed": max(0, SETTLED - ladder["hits"]),
    }


def record(conn, pool_id, correct):
    """Roll one pool's run forward by a single answer, and say what happened.

    Returns the event dict :func:`_event` builds. The caller commits; this
    writes through :func:`elmer.db.kv_set`, which commits on its own, so a
    ladder is never left half-moved by a failure later in the request.
    """
    stored = _all(conn)
    ladder = state(conn, pool_id)
    reached = None
    new_best = hit_target = False
    broke = previous_break = None

    if correct:
        ladder["run"] += 1
        new_best = ladder["run"] > ladder["best"]
        ladder["best"] = max(ladder["best"], ladder["run"])
        # A run can clear more than one rung only if the rungs are adjacent,
        # which they are not - but the loop costs nothing and means the table
        # can be retuned without this going wrong.
        while ladder["run"] >= ladder["bar"]:
            reached = ladder["bar"]
            ladder["bar"] = next_bar(ladder["bar"])
        if ladder["run"] == TARGET:
            hit_target = True
            ladder["hits"] += 1
            if ladder["hits"] == 1:
                log.info("run ladder: first ten in a row in %s", pool_id)
            elif ladder["hits"] == SETTLED:
                log.info("run ladder: %s has ten in a row %d times - settled",
                         pool_id, ladder["hits"])
    else:
        # A miss with no run behind it is not a break, and recording it as a
        # nought would bury the trend the breaks are kept for.
        if ladder["run"]:
            broke = ladder["run"]
            previous_break = ladder["last_break"]
            ladder["last_break"] = broke
            ladder["breaks"] = (ladder["breaks"] + [broke])[-KEEP_BREAKS:]
        ladder["run"] = 0

    stored[pool_id] = ladder
    db.kv_set(conn, KEY, stored)
    return _event(pool_id, ladder, reached=reached, new_best=new_best,
                  broke=broke, previous_break=previous_break,
                  hit_target=hit_target)


def trend(breaks):
    """Whether the recent breaks are landing further along than they were.

    Compares the mean of the older half against the newer half, which is
    steadier than "is the last one bigger" over a handful of numbers. Returns
    "rising", "level", "falling", or None when there is not enough to say.
    """
    kept = [b for b in (breaks or []) if b]
    if len(kept) < 4:
        return None
    half = len(kept) // 2
    older = sum(kept[:half]) / half
    newer = sum(kept[half:]) / (len(kept) - half)
    if newer >= older + 1:
        return "rising"
    if newer <= older - 1:
        return "falling"
    return "level"
