#!/usr/bin/env python3
"""A mock exam is study, and what it catches has to be reachable afterwards.

    python3 tests/test_exam_feeds_study.py

The guide says it plainly - nothing in a mock exam is wasted, every answer in
it feeds the same schedule the drill uses - and on the record that was true:
the questions somebody missed were lapsed, their spacing cut to minutes, their
skill marked down, and the Lapses drill would hand back exactly those.

What was not true was anything a person could see. The one study button on the
result screen said "Drill the weak spots", and that mode sorts the pool by
mastery, where a question nobody has ever answered scores *below* one just got
wrong - because srs.pool_skills estimates an unseen question from its section
and discounts it for having no evidence behind it. So after a mock exam the
button served four hundred questions never met and not one of the ten the exam
had just caught. Take a paper, press the obvious button, and the program
appears to have learned nothing from it.

An unseen question is not a weak spot. It is an unknown. Measured weakness
goes first, and the result screen offers the misses directly.

This holds both halves: that the record takes the exam, and that the routes
out of the result screen lead to what the exam found.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, srs  # noqa: E402
from elmer.app import app, get_pool  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
POOL = "tech2026"
client = app.test_client()


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def walk(mode, most=40):
    """The questions this mode actually offers, in the order it offers them."""
    seen = []
    for _ in range(most):
        got = client.get("/api/next?pool=%s&mode=%s&exclude=%s"
                         % (POOL, mode, ",".join(seen)), environ_base=LOCAL).get_json()
        if got.get("done") or got["question_id"] in seen:
            break
        seen.append(got["question_id"])
    return seen


# A paper answered the way a real one is: mostly right, a few wrong, a few
# never reached at all.
WRONG = [3, 9, 14, 21, 30]
BLANK = [5, 11, 19, 27, 33]

start = client.post("/api/exam/start", json={"pool": POOL}, environ_base=LOCAL).get_json()
exam_id = start["exam_id"]
conn = db.connect()
items = json.loads(conn.execute("SELECT detail FROM exam WHERE id = ?",
                                (exam_id,)).fetchone()["detail"])["exam"]["items"]
responses = {}
for i, item in enumerate(items):
    if i in BLANK:
        continue
    key = item["answer"]
    responses[str(i)] = (key + 1) % len(item["choices"]) if i in WRONG else key

missed = {items[i]["question_id"] for i in WRONG + BLANK}
right = {items[i]["question_id"] for i in range(len(items))
         if i not in WRONG and i not in BLANK}

print("\nthe paper is marked the way the real one is")
result = client.post("/api/exam/%d/submit" % exam_id,
                     json={"responses": responses, "seconds": 900},
                     environ_base=LOCAL).get_json()
check("the score counts the blanks against you", result["score"], len(items) - len(missed))
check("  and every question comes back in the results", len(result["results"]), len(items))
check("  with the misses named", sorted(r["question_id"] for r in result["results"]
                                        if not r["correct"]), sorted(missed))

print("\nthe record takes it - the right cards, and only those")
cards = db.cards_for_pool(db.connect(), POOL)
lapsed = {q for q, c in cards.items() if c and c["lapses"]}
check("every question answered gets a card", len(cards), len(items))
check("  every miss is lapsed", sorted(missed - lapsed), [])
check("  and nothing answered right is", sorted(right & lapsed), [])
check("  a blank counts as a miss, not as unseen",
      all((cards[items[i]['question_id']] or {})["seen"] == 1 for i in BLANK), True)
# A lapse is a setback, not a restart: it comes back within minutes.
soon = [q for q in missed if (cards[q]["due"] or "") <= db.utcnow().isoformat()[:10] + "T99"]
check("  and they are due back the same day", len(soon), len(missed))

print("\nand it is written down as an exam, not disguised as drilling")
log = db.connect().execute(
    "SELECT mode, COUNT(*) n FROM answer_log WHERE user_id = ? GROUP BY mode",
    (db.connect().user_id,)).fetchall()
check("every answer is logged", sum(r["n"] for r in log), len(items))
check("  under its own mode", [r["mode"] for r in log], ["exam"])

print("\nthe weighting moves, which is what the estimates read")
pool = get_pool(POOL)
per_q, _sections, _mastery, _ = srs.pool_skills(pool, cards)
worst = sum(per_q[q] for q in missed) / len(missed)
best = sum(per_q[q] for q in right) / len(right)
check("a missed question is rated below one answered right", worst < best, True)

print("\nand the routes off the result screen lead to what the exam found")
review = walk("review")
check("the Lapses drill offers exactly the misses", sorted(review), sorted(missed))
weak = walk("weak")
lead = weak[:len(missed)]
# The regression this file exists for. An unseen question outranked a question
# just got wrong, so the whole of what the exam caught sat behind four hundred
# questions nobody had met.
check("weak spots leads with what was actually measured", sorted(lead), sorted(missed))
check("  and only then with what has never been seen",
      all(cards.get(q) for q in weak[:len(missed)]), True)

print("\nthe result screen has a way into them")
page = (Path(__file__).resolve().parents[1] / "elmer" / "static" / "exam.js").read_text(encoding="utf-8")
check("the first button goes to the misses", "mode=review" in page, True)
check("  named by how many there are", "you missed" in page, True)
check("  and the screen says they are already in the queue",
      "in your review queue" in page, True)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
