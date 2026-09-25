#!/usr/bin/env python3
"""Sleeping on it, and the character that will not settle.

    python3 tests/test_cw_overnight.py

A cold rep a minute after the last one and a cold rep after a night are the
same entry in most records, and they are not the same evidence. Hearing the
whole code in an afternoon proves the ear works. Still having it tomorrow is
the learning.

It is also the one measure that serves both ends of the range. A set can be a
couple of hours or a couple of days: somebody who tears through the order in
an afternoon and somebody who has been on the same five letters for five days
are asking the record the same question the next morning, and it answers both
without flattering either. So the record keeps which days a character was met
cold and landed - one entry a day, however many sittings there were - and
reads two things off it: that a character survived a night, which is the
loudest thing the card can say, and that a character has been coming round
for days and has not settled, which is said plainly and is not a verdict on
anybody.

The two must never be said about the same character in the same breath. A
letter met on five separate days and still missed half the time has survived
nothing, and congratulating it while also saying it will not settle is the
program talking over itself.
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


# The clock is the only thing that has to be pretended about here: a test
# cannot wait a night. Everything else is the real recorder and the real
# reader, asked about days it is told are today.
DAY = {"is": "2026-09-01"}
db.today = lambda: DAY["is"]


def sitting(conn, ch, day, sent=6, copied=6, cold_hit=True, cold_ms=1800, confused=None):
    """One sitting of one character on a named day, folded in as the page folds it."""
    DAY["is"] = day
    db.cw_record(conn, {ch: {"sent": sent, "copied": copied,
                             "confused": confused or {}, "repeats": 0,
                             "ms": [1000] * copied,
                             "outcomes": "1" * copied + "0" * (sent - copied),
                             "cold_hit": cold_hit, "cold_ms": cold_ms}})
    return dict(db.cw_progress(conn)[ch])


conn = db.connect()

print("\nthe record keeps the days, one entry a day")
row = sitting(conn, "K", "2026-09-01")
check("one sitting is one day", cw.days_held(row), ["2026-09-01"])
row = sitting(conn, "K", "2026-09-01")
check("  a second sitting the same evening is still one day",
      cw.days_held(row), ["2026-09-01"])
check("  which is an afternoon, not a night", cw.held_overnight(row), False)
check("  and the cold reps themselves are both kept",
      len(str(row["cold"])), 2)
row = sitting(conn, "K", "2026-09-02")
check("the next morning is the second day", cw.slept_on(row), 2)
check("  and that is the thing", cw.held_overnight(row), True)

print("\na cold rep that missed is not a day survived")
row = sitting(conn, "M", "2026-09-01", sent=6, copied=5, cold_hit=False, cold_ms=None)
check("nothing to show for it", cw.days_held(row), [])
check("  so it has slept on nothing", cw.slept_on(row), 0)
row = sitting(conn, "M", "2026-09-02", sent=6, copied=5, cold_hit=False, cold_ms=None)
check("  and a second day of missing it changes nothing",
      cw.held_overnight(row), False)

print("\nthe days do not pile up forever")
for i in range(1, 21):
    row = sitting(conn, "R", "2026-10-%02d" % i)
check("a fortnight of them is kept", cw.slept_on(row), db.DAYS_KEEP)
check("  and it is the most recent fortnight",
      cw.days_held(row)[-1], "2026-10-20")

print("\nthe character that will not settle is named, with what it is heard as")
# Not solid, met cold on day after day: the record has something to say and
# saying nothing would leave somebody grinding at it.
settled = {"recent": "1" * 30, "cold": "1" * 5, "sent": 30, "copied": 30,
           "cold_days": ",".join("2026-09-%02d" % d for d in range(1, 6))}
check("a solid character is never called stuck", cw.stuck(settled), None)
shaky = {"recent": "1010010110" * 3, "cold": "10101", "sent": 30, "copied": 14,
         "cold_days": ",".join("2026-09-%02d" % d for d in range(1, 6)),
         "confused": {"S": 7}}
got = cw.stuck(shaky)
check("five days and not settled is said", bool(got), True)
check("  with the days counted", got["days"], 5)
check("  and the pair it is being confused with", got["heard_as"], ["S"])
early = dict(shaky, cold_days="2026-09-01,2026-09-02")
check("two days is not stuck, it is Tuesday", cw.stuck(early), None)
check("  and neither is a shaky character met once",
      cw.stuck(dict(shaky, cold_days="2026-09-01")), None)

print("\nthe card says the night, loudly")
prog = {"K": {"recent": "1" * 12, "cold": "11", "sent": 12, "copied": 12,
              "cold_days": "2026-09-01,2026-09-02"},
        "M": {"recent": "1" * 12, "cold": "11", "sent": 12, "copied": 12,
              "cold_days": "2026-09-01"}}
the_plan = cw.plan(prog)
lines = cw.wins(prog, the_plan, was=the_plan)
night = [w for w in lines if "night's sleep" in w]
check("the character that survived a night is named", len(night), 1)
check("  and only that one", "M" in night[0], False)
check("  in the words that say why it matters",
      "hearing it today proves the ear works" in night[0], True)
check("  loudly - it is not left to the bottom of the card",
      lines.index(night[0]) < 2, True)

print("\nand never in the same breath as saying it will not settle")
# The contradiction this exists to prevent: a letter met on five days,
# copied half the time. It has survived nothing.
both = {"K": {"recent": "1010010110" * 3, "cold": "10101", "sent": 30, "copied": 14,
              "cold_days": ",".join("2026-09-%02d" % d for d in range(1, 6)),
              "confused": {"S": 7}}}
p = cw.plan(both)
lines = cw.wins(both, p, was=p)
check("it is called what it is", any("has not settled yet" in w for w in lines), True)
check("  and not congratulated for surviving a night",
      any("night's sleep" in w for w in lines), False)
check("  the advice is the pair, not more of the same",
      any("hearing the pair against each other" in w for w in lines), True)
check("  and only one character is named that way at a time",
      len([w for w in lines if "has not settled" in w]), 1)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
