#!/usr/bin/env python3
"""The run of right answers, the bar it is measured against, and the breaks.

    python3 tests/test_runladder.py

The properties worth holding: the bar only ever goes up, and a miss never
lowers it; ten in a row once is recorded but is not the same as having it,
which takes SETTLED times; the breaks are kept in order so the progression
from four to six to eight is visible; a miss with no run behind it is not a
break and must not be recorded as one; each pool keeps its own ladder, so a
run in General cannot be fed by Technician answers; and the ladder survives
a stored shape from an older build rather than taking a page down.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, runladder as R  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run(conn, pool, pattern):
    """Feed a string of 'o' (right) and 'x' (wrong); return the last event."""
    event = None
    for mark in pattern:
        event = R.record(conn, pool, mark == "o")
    return event


conn = db.connect()
db.get_profile(conn)                      # the account the ladder hangs on


print("\na fresh pool starts at the first rung with nothing behind it")
blank = R.view(conn, "tech2026")
check("run", blank["run"], 0)
check("bar is the first rung", blank["bar"], R.RUNGS[0])
check("no best yet", blank["best"], 0)
check("no breaks yet", blank["breaks"], [])
check("ten in a row is not settled", blank["settled"], False)


print("\nreaching the bar moves it to the next rung, and says so")
event = run(conn, "tech2026", "ooo")
check("three right", event["run"], 3)
check("the rung just reached", event["reached"], 3)
check("the bar has moved up", event["bar"], 5)
check("and that is a new best", event["new_best"], True)
check("two more answers for the new bar", event["to_bar"], 2)


print("\na run that breaks short of the bar leaves the bar where it is")
event = R.record(conn, "tech2026", False)
check("the run is gone", event["run"], 0)
check("it broke at three", event["broke"], 3)
check("nothing came before it", event["previous_break"], None)
check("the bar did not retreat", event["bar"], 5)
check("and the best is remembered", event["best"], 3)


print("\nthe breaks are kept in the order they happened")
run(conn, "tech2026", "oooo" + "x")        # broke at 4
run(conn, "tech2026", "oooooo" + "x")      # broke at 6
event = run(conn, "tech2026", "oooooooo" + "x")   # broke at 8
check("four, then six, then eight", event["breaks"], [3, 4, 6, 8])
check("this one went further than the last", event["improved"], True)
check("the one before it", event["previous_break"], 6)
check("the trend is named", R.trend(event["breaks"]), "rising")

print("\n  and a break that does not get as far says nothing false")
event = run(conn, "tech2026", "oo" + "x")
check("broke at two", event["broke"], 2)
check("not an improvement", event["improved"], False)


print("\na miss with no run behind it is not a break")
before = R.view(conn, "tech2026")["breaks"]
event = R.record(conn, "tech2026", False)
check("nothing broke", event["broke"], None)
check("and nothing was recorded", event["breaks"], before)


print("\nten in a row is counted, and three of them settle it")
tenths = []
for _ in range(R.SETTLED):
    run(conn, "gen2023", "o" * (R.TARGET - 1))
    tenths.append(R.record(conn, "gen2023", True))     # the tenth answer itself
    event = R.record(conn, "gen2023", False)
check("ten reached three times", event["hits"], R.SETTLED)
check("which is what having it means", event["settled"], True)
check("and nothing more is needed", event["hits_needed"], 0)

print("\n  and every one of them is announced, not only the first")
check("all three say the target was hit",
      [t["hit_target"] for t in tenths], [True] * R.SETTLED)
check("  but only the first reaches a rung, because the bar moved past ten",
      [t["reached"] for t in tenths], [R.TARGET] + [None] * (R.SETTLED - 1))
check("  the third is the one that settles it", tenths[-1]["settled"], True)
check("  an ordinary right answer hits nothing",
      R.record(conn, "gen2023", True)["hit_target"], False)

print("\n  one clean run of ten is recorded but is not the same thing")
event = run(conn, "extra2024", "o" * R.TARGET)
check("ten in a row", event["run"], 10)
check("counted once", event["hits"], 1)
check("not settled on one", event["settled"], False)
check("two more to go", event["hits_needed"], R.SETTLED - 1)
check("and ten was a rung, so the bar moved past it", event["bar"], 15)

print("\n  a longer run counts the ten it passed through exactly once")
run(conn, "element1", "x")                 # a pool with a ladder but no run
event = run(conn, "element1", "o" * 15)
check("fifteen in a row", event["run"], 15)
check("ten was passed through once", event["hits"], 1)


print("\neach pool keeps its own ladder")
tech = R.view(conn, "tech2026")
extra = R.view(conn, "extra2024")
check("technician's best is its own", tech["best"], 8)
check("extra's best is its own", extra["best"], 10)
check("and their bars are their own", (tech["bar"], extra["bar"]), (10, 15))


print("\nthe bar keeps climbing past the printed table")
bar = R.RUNGS[-1]
check("past the last rung it goes up by BEYOND",
      R.next_bar(bar), R.RUNGS[-1] + R.BEYOND)
check("and inside the table it is the next rung", R.next_bar(3), 5)


print("\na ladder stored by an older build is read, not raised on")
db.kv_set(conn, R.KEY, {"tech2026": {"run": 2}})
old = R.view(conn, "tech2026")
check("what was stored is kept", old["run"], 2)
check("what was missing is filled in", old["bar"], R.RUNGS[0])
check("including the list", old["breaks"], [])

db.kv_set(conn, R.KEY, {"tech2026": {"run": "seven", "breaks": "nonsense"}})
junk = R.view(conn, "tech2026")
check("a value of the wrong type falls back", junk["run"], 0)
check("and so does a list that is not one", junk["breaks"], [])

db.kv_set(conn, R.KEY, "not a dict at all")
check("and a stored value that is not a map at all reads blank",
      R.view(conn, "tech2026")["run"], 0)


print("\nthe trend needs enough breaks before it says anything")
check("two breaks say nothing", R.trend([3, 9]), None)
check("four level ones are level", R.trend([5, 5, 5, 5]), "level")
check("and going backwards is named too", R.trend([9, 8, 3, 2]), "falling")
check("an empty record says nothing", R.trend([]), None)


conn.close()
print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
