#!/usr/bin/env python3
"""Every question gets seen before anything answered right comes back.

    python3 tests/test_coverage_first.py

The schedule owes a learner two things, in this order: to show them the
whole pool, and to get them answering all of it correctly. A question last
answered right has nothing to teach while there are questions nobody has met,
so until the pool is covered the only cards that come back are the misses -
and those always do.

This is the evening that broke it. A mock exam, the misses put right in Needs
review, then the drill - which handed back the very questions just answered,
over and over. Two faults did it: the exam's answers were charged to the
drill's daily new-question allowance, so the drill had no new material to
offer, and it then fell through to working ahead on cards that were not due.
Needs review, meanwhile, filtered on a lapse count that never goes down, so a
question stayed on it after being put right and the list went round again.
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


def answer(mode, qid, order, right):
    key = get_pool(POOL).by_id[qid]["answer"]
    shown = next(i for i, orig in enumerate(order) if (orig == key) == right)
    client.post("/api/answer", json={
        "pool": POOL, "question_id": qid, "chosen": shown,
        "order": order, "ms": 4000, "mode": mode}, environ_base=LOCAL)


def serve(mode, exclude):
    return client.get("/api/next?pool=%s&mode=%s&exclude=%s"
                      % (POOL, mode, ",".join(exclude)), environ_base=LOCAL).get_json()


print("\na mock exam, answered mostly right")
WRONG = [2, 7, 13, 20, 29]
start = client.post("/api/exam/start", json={"pool": POOL}, environ_base=LOCAL).get_json()
exam_id = start["exam_id"]
items = json.loads(db.connect().execute(
    "SELECT detail FROM exam WHERE id = ?", (exam_id,)).fetchone()["detail"])["exam"]["items"]
responses = {str(i): (it["answer"] + 1) % len(it["choices"]) if i in WRONG else it["answer"]
             for i, it in enumerate(items)}
client.post("/api/exam/%d/submit" % exam_id,
            json={"responses": responses, "seconds": 900}, environ_base=LOCAL)
on_paper = {it["question_id"] for it in items}
missed = {items[i]["question_id"] for i in WRONG}
check("the paper reached the record", len(db.cards_for_pool(db.connect(), POOL)), len(items))

print("\nthe exam does not spend the drill's new material")
plan = srs.day_plan(db.connect(), POOL)
check("no new questions charged", plan["new_done"], 0)
check("  the whole allowance is left", plan["new_left"], srs.DAILY_NEW)

print("\nNeeds review holds the misses, and lets go of each one once it is right")
check("the count is the misses", sum(1 for c in db.cards_for_pool(db.connect(), POOL).values()
                                     if srs.missed_last(c)), len(missed))
fixed = []
for _ in range(len(missed) + 3):
    got = serve("review", fixed)
    if got.get("done"):
        break
    answer("review", got["question_id"], got["order"], True)
    fixed.append(got["question_id"])
check("each miss was offered once", sorted(fixed), sorted(missed))
got = serve("review", fixed)
check("  and the list is then empty, not starting over", got.get("done"), True)
got = serve("review", [])
check("  even in a new session", got.get("done"), True)

print("\nthe drill then goes to what has never been seen")
drilled = []
for _ in range(15):
    got = serve("drill", drilled)
    if got.get("done"):
        break
    drilled.append(got["question_id"])
    answer("drill", got["question_id"], got["order"], True)
check("the drill kept going", len(drilled), 15)
check("  and nothing from the paper came back", sorted(set(drilled) & on_paper), [])
check("  and nothing was asked twice", len(set(drilled)), len(drilled))

print("\na miss comes back; something right does not")
cards = db.cards_for_pool(db.connect(), POOL)
wrong_now = drilled[0]
answer("drill", wrong_now, list(range(4)), False)
right_now = drilled[1]
cards = db.cards_for_pool(db.connect(), POOL)
pool = get_pool(POOL)
queue = srs.due_queue(pool, cards, now=db.utcnow().replace(year=db.utcnow().year + 1))
check("a year later the miss is in the queue", wrong_now in queue, True)
check("  the right answer is not, while the pool is unseen", right_now in queue, False)
check("  and every other entry is unseen or a miss",
      all(not cards.get(q) or srs.missed_last(cards[q]) for q in queue), True)

print("\nonce everything has been seen, the right answers are reviewed again")
everything = {q["id"]: {"seen": 1, "correct": 1, "reps": 2, "lapses": 0,
                        "interval": 4.0, "ease": 2.5, "run": 1,
                        "due": "2000-01-01T00:00:00+00:00",
                        "last_seen": "1999-12-28T00:00:00+00:00"}
              for q in pool.questions}
queue = srs.due_queue(pool, everything)
check("the whole pool is due", len(queue), len(pool.questions))

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
