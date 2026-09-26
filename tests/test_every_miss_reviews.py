#!/usr/bin/env python3
"""Every miss, wherever it happened, goes on the review list.

    python3 tests/test_every_miss_reviews.py

The promise the whole program is built on is that it knows what you do not
and drills you on that. It can only keep that promise if a wrong answer
counts wherever it was given - in the drill, in a mode somebody chose for
themselves, in a contest round against a clock, on a mock exam, or at a table
in a hall playing for a hole of golf. A miss that happened somewhere the
scheduler was not watching is a hole in the promise, and the person cannot
see it: their own experience is that they got something wrong and were never
asked it again.

There are three places in this program where an answer is written down, and
this holds all three to the same rule - the card is graded, the miss is a
lapse, and the question comes back. tests/test_exam_feeds_study.py holds the
mock exam in its own right, because that one also has to be reachable from
the screen the exam ends on.

The rule is deliberately stated as "a wrong answer is a lapse, always". There
is no mode in which being wrong is free, including the one where the answer
was revealed on purpose: pressing ? to see the answer counts as a miss,
because guessing right teaches the program something that is not true.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, srs  # noqa: E402
from elmer import app as appmod  # noqa: E402
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


def miss_one(mode, exclude):
    """Ask this mode for a question and get it wrong, the way the page does."""
    got = client.get("/api/next?pool=%s&mode=%s&exclude=%s"
                     % (POOL, mode, ",".join(exclude)), environ_base=LOCAL).get_json()
    if got.get("done"):
        return None
    qid = got["question_id"]
    key = get_pool(POOL).by_id[qid]["answer"]
    order = got["order"]
    # The page sends the index of the choice as shown, and the server maps it
    # back through the shuffle - so a miss is any shown index that is not the
    # one the key landed on.
    wrong_shown = next(i for i, orig in enumerate(order) if orig != key)
    client.post("/api/answer", json={
        "pool": POOL, "question_id": qid, "chosen": wrong_shown,
        "order": order, "ms": 4000, "mode": mode}, environ_base=LOCAL)
    return qid


print("\nevery mode a person can study in")
# Lapses is asked for last on purpose: until something has been missed there
# is nothing in it, which is itself the thing being proved.
missed, order_of_modes = [], ["drill", "new", "weak", "rapid", "review"]
for mode in order_of_modes:
    qid = miss_one(mode, missed)
    check(f"{mode}: a question was served and got wrong", bool(qid), True)
    if qid:
        missed.append(qid)

cards = db.cards_for_pool(db.connect(), POOL)
for mode, qid in zip(order_of_modes, missed):
    card = cards.get(qid)
    check(f"  {mode}: the miss is a lapse on the card",
          bool(card and card["lapses"]), True)
    check(f"  {mode}: and its run is broken", (card or {}).get("run"), 0)

print("\nand each of them is on the review list afterwards")
waiting, guard = [], 0
while guard < 40:
    got = client.get("/api/next?pool=%s&mode=review&exclude=%s"
                     % (POOL, ",".join(waiting)), environ_base=LOCAL).get_json()
    guard += 1
    if got.get("done") or got["question_id"] in waiting:
        break
    waiting.append(got["question_id"])
check("the review list holds every one of them", sorted(set(missed) - set(waiting)), [])
check("  and holds nothing that was never missed",
      sorted(set(waiting) - set(missed)), [])

print("\nrevealing the answer is a miss too, because guessing right is not knowing")
fresh = client.get("/api/next?pool=%s&mode=new&exclude=%s"
                   % (POOL, ",".join(missed + waiting)), environ_base=LOCAL).get_json()
qid = fresh["question_id"]
client.post("/api/answer", json={
    "pool": POOL, "question_id": qid, "chosen": None, "order": fresh["order"],
    "ms": 900, "mode": "drill"}, environ_base=LOCAL)
card = db.cards_for_pool(db.connect(), POOL).get(qid)
check("a revealed answer lapses the card", bool(card and card["lapses"]), True)

print("\na question answered at a table counts as much as one answered alone")
# The path the games use - a hole of golf, a tournament round, a hall of a
# hundred tables. Same person, same question, different room.
connection = db.connect()
table_q = next(q["id"] for q in get_pool(POOL).questions
               if q["id"] not in missed and q["id"] != qid)
appmod._credit_card(connection, POOL, table_q, False, 5200)
connection.commit()
card = db.cards_for_pool(db.connect(), POOL).get(table_q)
check("the card is graded", bool(card), True)
check("  the miss is a lapse", (card or {}).get("lapses"), 1)
check("  and it is due back, not parked", bool((card or {}).get("due")), True)
# Membership, not position. The first version of this asked for the next
# question in the review list and expected it to be this one, which is a
# claim about the order of a queue whose entries all fell due within the same
# second - so it passed alone and failed in a full run, where the timing came
# out differently. What is being held is that the question is on the list.
after, guard = [], 0
while guard < 40:
    got = client.get("/api/next?pool=%s&mode=review&exclude=%s"
                     % (POOL, ",".join(after)), environ_base=LOCAL).get_json()
    guard += 1
    if got.get("done") or got["question_id"] in after:
        break
    after.append(got["question_id"])
check("  and the review list has it", table_q in after, True)
check("  alongside the ones missed alone", set(missed) <= set(after), True)

print("\nthere is no mode in which being wrong is free")
# Stated as the rule rather than as five separate facts: whatever the grade
# works out to, a wrong answer is always below the passing quality, so it
# always lapses. If that stops being true, everything above is a coincidence.
check("every speed of wrong answer grades as a lapse",
      [srs.grade(False, ms) < 3 for ms in (None, 100, 1500, 9000, 60000)],
      [True] * 5)
check("  and every right one does not",
      [srs.grade(True, ms) >= 3 for ms in (None, 100, 1500, 9000, 60000)],
      [True] * 5)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
