"""Which pools a newcomer is shown first, and what opens them.

Somebody who has just downloaded this and has no licence yet is looking at
2,475 questions across six pools, most of which are not their exam and three
of which are not even amateur radio. That is not a library, it is a wall. So
the amateur ladder starts at Technician and opens as there is reason to.

What opens it:

* **A licence class.** From the callsign lookup where that works, or typed in
  where it does not - callook serves the FCC ULS and nothing else, so a
  Canadian or British operator has a perfectly good callsign that resolves to
  nothing, and must not be walled in by that.
* **Earning Technician Elmer.** The rank ladder already requires exam evidence
  at that tier, so this is demonstrated mastery rather than an assertion, and
  it is the honest answer for somebody studying hard before they ever sit an
  exam.
* **Asking.** The gate can be switched off. Somebody holding an Extra who
  would rather not type a callsign into a program is not going to be argued
  with; the point is to not overwhelm a beginner, not to police anybody.

Two rules follow from what people actually do with this:

Everything at or below your class stays open, not just your own pool. The
program is named after the people who teach Technician classes, and a General
reviewing the basics, or an Extra helping their child study, needs the lower
pools. A window that locks a General out of Technician would be exactly wrong.

The commercial pools are not gated on an amateur licence at all. An Extra
ticket says nothing whatever about whether somebody is ready for a GROL, and
the two ladders are already separate in `ranks.TRACKS`. Gating a marine radio
permit behind an amateur class would be a category error.
"""
from . import ranks

# The amateur ladder, in order. Everything at or below the reached rung is
# open, plus the next one up as the thing worth working toward.
AMATEUR_LADDER = ["tech2026", "gen2023", "extra2024"]

# What a licence class entitles the holder to see. Novice and Advanced are no
# longer issued but plenty are still held and still renewed, so they map onto
# the modern pool whose privileges they most nearly resemble.
CLASS_RUNG = {
    "Novice": 0, "Technician": 0, "General": 1, "Advanced": 2, "Extra": 2,
}

SETTING = "pool_gate"          # "on" (default) or "off"


def gate_on(settings):
    """Whether the gate applies. Absent means on: the default is the newcomer."""
    return str((settings or {}).get(SETTING, "on")).lower() != "off"


def _rung_from_class(licence_class):
    return CLASS_RUNG.get((licence_class or "").strip().title())


def _rung_from_standings(standings):
    """The highest amateur pool taken to Elmer, as a rung.

    Elmer is the top of the ladder and needs exam evidence, so reaching it on
    Technician is a real demonstration that the next pool is the right place
    to be - and it is the route open to somebody who has not sat a real exam
    yet, which is precisely the person this gate is for.
    """
    best = None
    for standing in standings or []:
        pool_id = standing.get("pool_id")
        if pool_id not in AMATEUR_LADDER:
            continue
        if standing.get("step", 0) >= ranks.ELMER:
            rung = AMATEUR_LADDER.index(pool_id)
            best = rung if best is None else max(best, rung)
    return best


def reach(settings=None, standings=None):
    """How far up the amateur ladder this user has opened, and why.

    Returns the highest rung *reached*; the pool above it is also offered, as
    the next thing to work toward.
    """
    settings = settings or {}
    if not gate_on(settings):
        return {"rung": len(AMATEUR_LADDER) - 1, "reason": "off", "gated": False}

    licence = (settings.get("licence_class")
               or (settings.get("licence") or {}).get("licence_class"))
    from_class = _rung_from_class(licence)
    from_rank = _rung_from_standings(standings)

    if from_class is not None and (from_rank is None or from_class >= from_rank):
        return {"rung": from_class, "reason": "licence", "licence": licence,
                "gated": True}
    if from_rank is not None:
        return {"rung": from_rank, "reason": "rank", "gated": True}
    return {"rung": 0, "reason": "start", "gated": True}


def open_pools(settings=None, standings=None, all_pool_ids=None):
    """The pool ids this user may study right now."""
    state = reach(settings, standings)
    allowed = set(AMATEUR_LADDER[:_top(state) + 1])
    # Everything that is not on the amateur ladder is not gated by it.
    for pool_id in all_pool_ids or []:
        if pool_id not in AMATEUR_LADDER:
            allowed.add(pool_id)
    return allowed, state


def _top(state):
    """The highest rung open, given how far the ladder has been climbed.

    One above the rung reached, as the thing worth working toward - but only
    once something has actually been reached. Somebody who has just arrived
    gets Technician and nothing else, which is the whole point: the next pool
    is a reward for a reason, not the opening position.
    """
    if state["reason"] == "start":
        return 0
    return min(state["rung"] + 1, len(AMATEUR_LADDER) - 1)


def why_closed(pool_id, state):
    """A sentence for a pool that is not open yet, or None if it is."""
    if pool_id not in AMATEUR_LADDER:
        return None
    rung = AMATEUR_LADDER.index(pool_id)
    if rung <= _top(state):
        return None
    needed = AMATEUR_LADDER[max(0, rung - 1)]
    names = {"tech2026": "Technician", "gen2023": "General",
             "extra2024": "Amateur Extra"}
    return (f"{names.get(pool_id, pool_id)} opens when you hold a licence that "
            f"reaches it, or take {names.get(needed, needed)} to Elmer. "
            f"You can also open everything from Settings.")
