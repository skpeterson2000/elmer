#!/usr/bin/env python3
"""How hard a question is, measured from how it went.

    python3 tests/test_difficulty.py

The properties worth holding: time is normalised per person per sitting, so
a slow reader and a quick one can be compared; a guess is fast, so
correctness is in the measure too; only a person's first sight of a question
counts, because the fourth sighting is fast whatever the question; a question
too few have met is unmeasured, not easy; and the tournament's draw is
ordered easiest-first only when enough of it is measured, and says so.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, difficulty as D, tournament  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def row(u, day, q, correct, ms, t):
    return {"user_id": u, "day": day, "question_id": q, "correct": correct, "ms": ms, "ts": t}


print("\na slow reader and a quick one agree about which question is hard")
rows = [
    row(1, "d1", "Q1", 1, 2000, 1), row(1, "d1", "Q2", 0, 9000, 2), row(1, "d1", "Q3", 1, 2200, 3),
    row(2, "d1", "Q1", 1, 6000, 4), row(2, "d1", "Q2", 0, 20000, 5), row(2, "d1", "Q3", 1, 5500, 6),
    row(3, "d2", "Q1", 1, 3000, 7), row(3, "d2", "Q2", 1, 12000, 8), row(3, "d2", "Q3", 1, 2800, 9),
]
m = D.measure(rows)
check("the question everybody laboured over and most missed is hardest",
      max(m, key=lambda q: m[q]["hardness"]), "Q2")
check("  the two easy ones are close to each other",
      abs(m["Q1"]["hardness"] - m["Q3"]["hardness"]) < 0.05, True)
check("  Bob being three times slower than Ann across the board did not tilt it",
      abs(m["Q1"]["median_z"]) < 0.1, True)
check("  Q2 took everybody longer than their own usual",
      m["Q2"]["median_z"] > 1.0, True)

print("\nonly the first sight of a question counts")
again = rows + [row(1, "d3", "Q2", 1, 1500, 10), row(2, "d3", "Q2", 1, 1200, 11)]
m2 = D.measure(again)
check("a fast second look changes nothing about Q2", m2["Q2"], m["Q2"])

print("\na guess is fast, and is not read as easy")
guessers = [row(u, "d1", "Q9", 0, 1500, 20 + u) for u in (1, 2, 3)] + \
           [row(u, "d1", "Q8", 1, 4000, 30 + u) for u in (1, 2, 3)]
m3 = D.measure(guessers)
check("the question three people clicked through fast and got wrong is harder "
      "than the one they took their time over and got right",
      m3["Q9"]["hardness"] > m3["Q8"]["hardness"], True)

print("\nunmeasured is a state, not a zero")
thin = D.measure([row(1, "d1", "Q1", 0, 9000, 1), row(2, "d1", "Q1", 0, 9000, 2)])
check("two people is not enough to rank", thin["Q1"]["measured"], False)
check("  and it is not offered to the draw", D.ranker(thin)({"id": "Q1"}), None)
check("  a question nobody met is simply absent", "Q7" in thin, False)
check("coverage counts only the measured", D.coverage(m, ["Q1", "Q2", "Q3", "Q7"]), 0.75)

print("\nexam answers have no time and still count towards the miss rate")
exams = [row(u, "d1", "Q5", u != 1, None, 40 + u) for u in (1, 2, 3)]
m4 = D.measure(exams)
check("three exam answers rank the question", m4["Q5"]["measured"], True)
check("  with a miss rate", m4["Q5"]["miss_rate"], 0.333)
check("  and no time part beyond the neutral half", m4["Q5"]["median_z"], None)

print("\nthe draw is ramped only when enough of it is measured")
items = [{"id": f"Q{i}"} for i in range(12)]
few = {f"Q{i}": {"hardness": i / 12, "measured": True} for i in range(4)}
ordered, ramped = tournament.ordered(items, D.ranker(few))
check("four of twelve measured: blueprint order, no ramp claimed", ramped, False)
most = {f"Q{i}": {"hardness": (11 - i) / 12, "measured": True} for i in range(9)}
ordered, ramped = tournament.ordered(items, D.ranker(most))
check("nine of twelve: ramped", ramped, True)
check("  easiest first", [q["id"] for q in ordered][:3], ["Q8", "Q7", "Q6"])
# The three nobody has met yet go in the middle: not first, where "easy"
# would be a claim, and not last, where "hard" would be one.
places = [q["id"] for q in ordered]
check("  and the unmeasured three sit in the middle, claimed neither easy nor hard",
      [places.index(q) for q in ("Q9", "Q10", "Q11")] == [4, 5, 6] or
      all(2 < places.index(q) < 9 for q in ("Q9", "Q10", "Q11")), True)
check("  with the hardest last", places[-1], "Q0")

print("\nand it reads its rows from the unit's own log")
spare = tempfile.NamedTemporaryFile(suffix=".db", delete=False); spare.close()
conn = db.connect(spare.name)
for u, q, ok, ms in ((1, "T1A01", 1, 3000), (1, "T1A02", 0, 8000)):
    conn.user_id = u
    db.log_answer(conn, "tech2026", q, "T1A", ok, 0, ms, "study")
conn.commit()
got = D.load(conn, "tech2026")
check("two rows back", len(got), 2)
check("  with what the measure needs", sorted(got[0]), ["correct", "day", "ms", "question_id", "ts", "user_id"])
check("  and none from another pool", D.load(conn, "gen2023"), [])

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
