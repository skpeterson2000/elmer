#!/usr/bin/env python3
"""A session with an end to it, and a reward that is not another green letter.

    python3 tests/test_cw_session.py

The Koch method decides what to practice and that part was never in doubt.
What was missing was the session: session() returned three or four parts and
the page offered a button for another three or four, so there was no bottom
to reach and never an "enough for now". Two characters drilled for fifteen
minutes is eleven minutes of drilling after the learning stopped, and what
is learned in those eleven minutes is that this is a thing to be endured.

So three things are held here. A session has a length, and the length comes
from how much code there is to hold - three minutes at the two the order
starts with, a quarter of an hour with the order held. It ends on something
already known, the way a trainer finishes on a command the animal has cold.
And the reward is the clock: what got quicker, said out loud, because that
is the learning and it is the one thing a learner cannot see from inside.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import cw  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def record(met, first_ms=2600, now=900, rate=1.0):
    """A record with `met` characters solid, and a clock on each of them.

    Both clocks: the warm one a drill produces, and the cold one - the first
    rep of a sitting - which is what the end-of-session card reads. See
    test_cw_cold.py for the difference and why it matters.
    """
    kept = int(30 * rate)
    return {c: {"sent": 40, "copied": int(40 * rate),
                "recent": ("1" * kept) + ("0" * (30 - kept)),
                "times": ",".join([str(now)] * 6), "first_ms": first_ms,
                "cold": "1" * 6,
                "cold_times": ",".join([str(first_ms)] + [str(now)] * 5),
                "cold_first_ms": float(first_ms)}
            for c in cw.KOCH_ORDER[:met]}


print("\nthe length comes from how much there is to hold")
lengths = {}
for met in (0, 3, 10, 25, 40):
    the_plan = cw.plan(record(met))
    lengths[met] = cw.budget(the_plan)
check("two characters is three minutes, not fifteen", lengths[0], cw.SESSION_LEAST)
check("  the whole order is fifteen", lengths[40], cw.SESSION_MOST)
check("  and it only ever grows in between",
      lengths[0] <= lengths[3] <= lengths[10] <= lengths[25] <= lengths[40], True)
check("  nothing is longer than the top", max(lengths.values()) <= cw.SESSION_MOST, True)
check("  nor shorter than the floor", min(lengths.values()) >= cw.SESSION_LEAST, True)
check("a plan with nothing in it still has a length", cw.budget({}), cw.SESSION_LEAST)
check("  and so does None", cw.budget(None), cw.SESSION_LEAST)

print("\nthe parts are cut to the clock, not to a fixed list")
for met in (0, 3, 10, 25):
    the_plan = cw.plan(record(met))
    steps = cw.session(the_plan)
    asked = cw.budget(the_plan)
    spent = sum(s.get("seconds") or 0 for s in steps)
    slack = abs(spent - asked)
    check(f"{met:2d} met: the parts add up to the clock (asked {asked}s, cut {spent}s)",
          slack <= cw.GROUP_SECONDS, True)
    check("  every part says how long it is",
          all(s.get("seconds") for s in steps), True)
# A longer clock buys more of the work, not a longer single drill.
short = cw.session(cw.plan(record(3)))
long_ = cw.session(cw.plan(record(25)))
groups = lambda ss: next((s["count"] for s in ss if s["kind"] == "koch"), 0)  # noqa: E731
check("more time means more groups", groups(long_) > groups(short), True)
check("  and a caller may name the length",
      sum(s.get("seconds") or 0 for s in cw.session(cw.plan(record(10)), seconds=300)) <= 320, True)

print("\na day is passes through the lesson, never one block")
# "Fifteen minutes a day beats two hours on Sunday" is not a slogan sitting
# beside a three minute session - it is the same claim. Fifteen minutes is
# five passes of three, and what is learned is learned in the coming back:
# the character has to be fetched again from cold, after the mind has been
# somewhere else. A session that grew to fill the whole quarter of an hour
# would be the one shape the line exists to argue against, and that is what
# it used to do - SESSION_MOST was 900 seconds, the whole day in one sitting.
for met in (0, 3, 10, 25, 40):
    the_plan = cw.plan(record(met))
    each, times = cw.budget(the_plan), cw.passes(the_plan)
    day = each * times
    check(f"{met:2d} met: {times} passes of {each}s is a day of {round(day/60)} min",
          (times >= cw.PASSES_FEWEST, 840 <= day <= 1150), (True, True))
check("no session is a day on its own", cw.SESSION_MOST < cw.DAY_TARGET, True)
check("  the longest is well under half of one",
      cw.SESSION_MOST <= cw.DAY_TARGET / 2, True)
check("two characters is five passes of three minutes",
      (cw.passes(cw.plan({})), cw.budget(cw.plan({}))), (5, 180))
check("holding the order it is fewer and longer, still not one",
      cw.passes(cw.plan(record(40))) >= cw.PASSES_FEWEST, True)
check("a plan with nothing in it still makes a day", cw.passes({}) >= cw.PASSES_FEWEST, True)

print("\na set of passes keeps - tomorrow still counts")
# Five passes is what a day comes to, not a quota with a clock on it.
# Somebody who got three in before the evening went sideways has done three
# of a five-pass set, and the honest thing tomorrow is to offer them the
# last two. The argument for this shape is that it fits into the gaps in a
# day; a version that only works on a clear day is a different claim.
from datetime import date as _date, timedelta as _td
mon = _date(2026, 9, 21)
tue, wed, fri = mon + _td(days=1), mon + _td(days=2), mon + _td(days=4)
held = None
for _ in range(3):
    held = cw.add_pass(held, mon, 5)
check("three passes in on the day", cw.set_state(held, mon, 5)["passes"], 3)
check("  and two still to go", cw.set_state(held, mon, 5)["left"], 2)
st = cw.set_state(held, tue, 5)
check("tomorrow the same set is offered", (st["passes"], st["left"]), (3, 2))
check("  and it says it was carried", st["carried"], True)
held = cw.add_pass(cw.add_pass(held, tue, 5), tue, 5)
st = cw.set_state(held, tue, 5)
check("finished on the carry day, it stands", (st["passes"], st["complete"]), (5, True))
check("  and the next day starts clean", cw.set_state(held, wed, 5)["passes"], 0)
# Past the window it is a new set: one that never closes is not a set.
stale = {"opened": mon.isoformat(), "last": mon.isoformat(), "passes": 3, "target": 5}
check("a set left four days is not still open", cw.set_state(stale, fri, 5)["passes"], 0)
check("  and carries nothing with it", cw.set_state(stale, fri, 5)["carried"], False)
# Going again after finishing opens a new one rather than being refused.
again = cw.add_pass(held, tue, 5)
check("more is welcome once the set is done", cw.set_state(again, tue, 5)["passes"], 1)
check("nothing written down yet is simply a fresh set",
      cw.set_state(None, mon, 5)["left"], 5)
check("  and so is a record that makes no sense",
      cw.set_state({"opened": "not-a-date", "passes": 4}, mon, 5)["passes"], 0)

print("\nit ends on something that already goes right")
steps = cw.session(cw.plan(record(10)))
check("the last part is a lap", bool(steps[-1].get("lap")), True)
check("  on characters, named", bool(steps[-1].get("only")), True)
check("  and it is not a test, which it says",
      "not a test" in steps[-1]["why"], True)
solid = set(cw.KOCH_ORDER[:10])
check("  only ones already known are in it", set(steps[-1]["only"]) <= solid, True)
# Nothing known yet, so there is nothing to end on and none is invented.
fresh = cw.session(cw.plan({}))
check("a first-ever session has no lap to take", any(s.get("lap") for s in fresh), False)
# A character that is shaky is not what a session ends on.
shaky = record(10)
shaky[cw.KOCH_ORDER[4]] = {"sent": 40, "copied": 16, "recent": "0" * 20 + "1" * 10,
                           "times": "1800,1700,1900,1750", "first_ms": 2600}
lap = [s for s in cw.session(cw.plan(shaky)) if s.get("lap")]
check("the shaky one is left out of the lap",
      cw.KOCH_ORDER[4] in (lap[0]["only"] if lap else []), False)

print("\nthe stopping signal: slowing down is a reason to come back, not to push on")
check("nothing to say with a handful of answers", cw.flagging([900] * 5), None)
check("  nor with none at all", cw.flagging([]), None)
steady = [900, 880, 910, 890, 900] * 5
check("a steady session is not stopped", cw.flagging(steady)["stop"], False)
tiring = [800] * 15 + [1500, 1600, 1550, 1700, 1650]
reading = cw.flagging(tiring)
check("one that has slowed a third is", reading["stop"], True)
check("  and it carries the person's own best, not a standard",
      (reading["best_s"], reading["now_s"]), (0.8, 1.6))
check("  said as a percentage they can check", reading["by"], 100)
# A slow day throughout is a slow day, not a decline: the comparison is
# against this session's own best, so nothing is cut short for being tired
# on arrival.
slow_all_through = [2000, 2100, 1950, 2050, 2000] * 5
check("a slow day is not read as a decline", cw.flagging(slow_all_through)["stop"], False)

print("\nthe reward is the clock, not another green letter")
progress = record(10, first_ms=3000, now=900)
the_plan = cw.plan(progress)
# The plan as it stood at the start of the sitting: the same characters,
# none of them yet heard without their shape, and one character fewer
# earned. Nothing is claimed against a baseline that does not exist -
# see the first-sitting case below.
before = dict(the_plan, weaned=[], earned=the_plan["earned"] - 1)
moved = cw.wins(progress, the_plan, was=before)
check("something is said about what got quicker", len(moved) >= 1, True)
check("  the before and after are in it, read off the cold rep",
      any("3.0 s when you learned it" in m and "0.9 s now" in m for m in moved), True)
check("  a character heard by ear now is worth saying",
      any("without the shape drawn" in m for m in moved), True)
check("  so is the order opening up",
      any("new character opened up" in m for m in moved), True)
# No before, no boast.
first_day = {cw.KOCH_ORDER[0]: {"sent": 4, "copied": 3, "recent": "1101", "times": "", "first_ms": None}}
check("a first sitting has nothing to compare and says nothing",
      cw.wins(first_day, cw.plan(first_day), was=cw.plan(first_day)), [])
check("  and an empty record likewise", cw.wins({}, cw.plan({}), was={}), [])
# Getting slower is not dressed up as getting faster.
slower = record(10, first_ms=900, now=2600)
check("nothing is claimed when the clock went the other way",
      cw.wins(slower, cw.plan(slower), was=cw.plan(slower)), [])

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
