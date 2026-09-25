#!/usr/bin/env python3
"""A cold rep and a warm one, and the baseline a new learner builds.

    python3 tests/test_cw_cold.py

Every reaction time went into one pile. The baseline was the mean of the
first few recognitions whether they came at the start of a sitting or in the
middle of a ninety-second drill where the character had just been heard eight
times, and those are not the same measurement. The one worth keeping is the
cold rep: the first time a character comes round in a sitting, or the first
after a pronounced break, with no warm-up behind it.

It is how a dog is judged on "sit" - not the tenth in a row with a treat
already in the air, but the first one of the walk. That rep says the
expectation is achievable from cold, and it is the rep that earns the fuss.

So: a brand-new learner has no baseline and is not given one, but builds one
a character at a time, and the first cold rep that lands is where a character
joins it. Whether the cold rep landed is kept as well as how long it took.
The clock reads cold against cold and never against a warm drill. And the
reward is front-loaded - loudest for gross replication, quiet and rationed
for the refined state - because a reward that keeps arriving for the polished
thing teaches somebody to perform for the reward.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import cw, db  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def sitting(conn, ch, sent, copied, ms, cold_hit=None, cold_ms=None):
    """One sitting's worth of one character, folded in the way the page folds it."""
    db.cw_record(conn, {ch: {"sent": sent, "copied": copied, "confused": {},
                             "repeats": 0, "ms": ms,
                             "outcomes": "1" * copied + "0" * (sent - copied),
                             "cold_hit": cold_hit, "cold_ms": cold_ms}})


conn = db.connect()

print("\na brand-new learner has no baseline, and is not handed one")
check("nothing learned yet", cw.learned(None), False)
check("  a record with warm times only is still not learned",
      cw.learned({"times": "900,880", "first_ms": 2600, "cold": ""}), False)
check("  and the plan says so", cw.plan({})["learned"], [])
check("  the card says what it is for, not that it is too early",
      "gets set the first time you name a character cold" in cw.baseline_words(cw.plan({})), True)
check("  the clock has nothing to say yet", cw.cold_pace({"cold_first_ms": None}), None)
check("  nor does the rate", cw.cold_rate({}), None)

print("\nthe first cold rep that lands is where the baseline starts")
# Sitting one: K came round cold and was missed, then landed warm eight times.
sitting(conn, "K", sent=9, copied=8, ms=[1200] * 8, cold_hit=False, cold_ms=None)
row = dict(db.cw_progress(conn)["K"])
check("a cold rep that missed is recorded as a miss", row["cold"], "0")
check("  and sets no landmark", row["cold_first_ms"], None)
check("  so the character is not learned, whatever the warm drill did",
      (cw.learned(row), row["copied"]), (False, 8))
check("  the rate knows it was nought for one", cw.cold_rate(row), 0.0)
# Sitting two: it landed cold, at 2.8 s - slower than any warm rep, which is
# the whole point of keeping the two apart.
sitting(conn, "K", sent=9, copied=9, ms=[1100] * 9, cold_hit=True, cold_ms=2800)
row = dict(db.cw_progress(conn)["K"])
check("the cold rep that landed sets the landmark", row["cold_first_ms"], 2800.0)
check("  the character is learned", cw.learned(row), True)
check("  and the landmark is the cold time, not the warm one",
      (row["cold_first_ms"], row["first_ms"]), (2800.0, 1200.0))
check("  one of two cold tries", cw.cold_rate(row), 0.5)

print("\nthe clock reads cold against cold, and waits for enough of them")
check("two cold reps is not enough to speak", cw.cold_pace(row), None)
for ms in (2200, 1500, 1300):
    sitting(conn, "K", sent=9, copied=9, ms=[1000] * 9, cold_hit=True, cold_ms=ms)
row = dict(db.cw_progress(conn)["K"])
got = cw.cold_pace(row)
check("with four past the landmark it speaks", bool(got), True)
check("  the before is the landmark", got["first_s"], 2.8)
check("  the after is the recent cold reps, landmark left out",
      got["now_s"], round((2200 + 1500 + 1300) / 3 / 1000.0, 1))
check("  and it is faster", (got["faster"], got["by"] > 0), (True, True))
check("the landmark never moves", dict(db.cw_progress(conn)["K"])["cold_first_ms"], 2800.0)

print("\nthe warm pile is still there, and still says something different")
check("the warm clock reads warm", cw.pace(row)["first_s"], 1.2)
check("  which is not the cold reading", cw.pace(row)["first_s"] != got["first_s"], True)

print("\nthe reward is loudest for gross replication")
prog = db.cw_progress(conn)
the_plan = cw.plan(prog)
# The sitting in which K was first named cold: before it, nothing was learned.
first_time = cw.wins(prog, the_plan, was=dict(the_plan, learned=[]))
check("the first cold naming is the first thing said", "is yours" in first_time[0], True)
check("  and it says what made it count",
      "nothing warmed up in front of it" in first_time[0], True)
# The same record with K already learned: no repeat of the loud line.
later = cw.wins(prog, the_plan, was=the_plan)
check("it is not said twice", any("is yours" in w for w in later), False)
check("  the refined state is still reported, quietly",
      any("cold:" in w and "s now" in w for w in later), True)
check("  and it is read off the cold rep, not the warm drill",
      any("when you learned it" in w for w in later), True)

print("\nthe refined state is rationed, so the card cannot become a wall of praise")
many = {}
for i, ch in enumerate(cw.KOCH_ORDER[:6]):
    many[ch] = {"sent": 40, "copied": 40, "recent": "1" * 30,
                "times": "900,900,900,900", "first_ms": 2600,
                "cold": "1" * 6, "cold_times": "3000,1400,1200,1100,1000,900",
                "cold_first_ms": 3000.0}
p6 = cw.plan(many)
lines = cw.wins(many, p6, was=p6)
check("six characters all improving give at most two quiet lines", len(lines), 2)
check("  and the loudest is left for something that is actually new",
      any("is yours" in w for w in lines), False)

print("\nreliability is reported once it turns round, not every sitting")
turned = {"K": {"sent": 40, "copied": 38, "recent": "1" * 30,
                "times": "900,900,900,900", "first_ms": 2600,
                "cold": "0010011111", "cold_times": "2800,2000,1500,1300,1200,1100",
                "cold_first_ms": 2800.0}}
pt = cw.plan(turned)
lines = cw.wins(turned, pt, was=pt)
check("a character that used to be hit and miss and now lands cold is said so",
      any("lands cold now" in w for w in lines), True)
check("  in a count somebody can picture, not a percentage",
      any("of the last 5 first-of-the-day tries" in w for w in lines), True)
always = {"K": dict(turned["K"], cold="1111111111")}
pa = cw.plan(always)
check("a character that always landed cold is not congratulated for it",
      any("lands cold now" in w for w in cw.wins(always, pa, was=pa)), False)

print("\nnothing is claimed when the cold clock went the other way")
worse = {"K": {"sent": 40, "copied": 38, "recent": "1" * 30, "times": "900,900,900,900",
               "first_ms": 2600, "cold": "11111", "cold_times": "900,2000,2400,2600,2800",
               "cold_first_ms": 900.0}}
pw = cw.plan(worse)
check("getting slower cold is not dressed up as getting faster",
      any("s now" in w for w in cw.wins(worse, pw, was=pw)), False)
check("  and the reading says slower, plainly", cw.cold_pace(worse["K"])["slower"], True)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
