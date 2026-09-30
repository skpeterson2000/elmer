#!/usr/bin/env python3
"""Keeping a pool the license already covers, without a treadmill.

    python3 tests/test_keeping.py

The schedule was built for cramming: every pool, for everybody, stepped 1
day, 4 days and on, targeted 90% recall and allowed 120 reviews a day - so a
licensed Extra keeping up the Technician pool was asked for what somebody
sitting it next Saturday needs, and the "due" count on the dashboard grew
every day they did not answer it. Most operators learned the answers for the
test and keep the parts they use; a schedule that treats the rest as a debt
gets switched off. What is held here:

  - a pool at or below the class held is kept by default, and anybody may
    choose to learn it in full instead, and go back;
  - kept, a question right on first sight goes out a month, a right answer
    after a long gap is credited with the gap, and a miss is still a miss;
  - kept, the drill asks one question from each group whose evidence has
    faded - the way the exam samples the pool - and a miss opens only that
    group; when everything held is holding, it asks for nothing;
  - the day's keeping is a short set, and time away does not pile up;
  - Brush up asks what has faded first - all of it - then the weakest, then
    the unmet;
  - no page says "due for review"; the dashboard counts groups worked.
"""
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import random  # noqa: E402
from elmer import db, gating, srs  # noqa: E402
from elmer.app import app, get_pool  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
POOL = "tech2026"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def card(interval, days_ago, reps=2, lapses=0, seen=3, correct=3, now=None):
    now = now or db.utcnow()
    last = now - timedelta(days=days_ago)
    return {"ease": 2.5, "interval": interval, "reps": reps, "lapses": lapses,
            "seen": seen, "correct": correct, "last_seen": last.isoformat(),
            "due": (last + timedelta(days=interval)).isoformat()}


def main():
    now = db.utcnow()
    pool = get_pool(POOL)

    print("\n-- which pools are kept --")
    check("an Extra keeps all three amateur pools",
          [gating.held_covers(p, "Extra") for p in gating.AMATEUR_LADDER], [True, True, True])
    check("a General keeps Technician and General, and learns Extra",
          [gating.held_covers(p, "General") for p in gating.AMATEUR_LADDER], [True, True, False])
    check("nobody licensed keeps nothing", gating.held_covers(POOL, ""), False)
    check("an amateur class never covers a commercial element", gating.held_covers("element3", "Extra"), False)
    got = gating.study_style(POOL, {"license_class": "Extra"})
    check("kept by default for an Extra", (got["style"], got["chosen"], got["covered"]), ("keep", False, True))
    got = gating.study_style(POOL, {"license_class": "Extra", gating.STYLE: {POOL: "learn"}})
    check("  unless they choose to learn it in full", (got["style"], got["chosen"]), ("learn", True))

    print("\n-- the schedule, kept --")
    check("right on first sight, learning: a day", srs.schedule(None, 5, now, random.Random(1))["interval"], 1.0)
    check("right on first sight, kept: a month",
          srs.schedule(None, 5, now, random.Random(1), keeping=True)["interval"], srs.KEEP_FIRST_DAYS)
    old = card(10.0, 120)
    kept = srs.schedule(old, 4, now, random.Random(1), keeping=True)["interval"]
    learnt = srs.schedule(old, 4, now, random.Random(1))["interval"]
    check("right after four months away, kept: credited with the gap it survived",
          (kept >= 120, learnt < 40), (True, True))
    check("  and never more than a year", srs.schedule(card(300.0, 300), 5, now, keeping=True)["interval"],
          srs.KEEP_MAX_INTERVAL)
    missed = srs.schedule(old, 1, now, random.Random(1), keeping=True)
    check("a miss is still a miss: back within minutes", (missed["reps"], missed["lapses"]), (0, 1))

    print("\n-- the keeping drill samples the groups --")
    groups = [c for c in pool.section_order if pool.by_section.get(c)]
    queue = srs.keeping_queue(pool, {}, now, random.Random(3))
    check("a pool never answered: one question from every group, no more",
          (len(queue), sorted({pool.by_id[q]["section"] for q in queue}) == sorted(groups)),
          (len(groups), True))
    held = {}
    for code in groups:
        q = pool.by_section[code][0]["id"]
        held[q] = card(srs.KEEP_FIRST_DAYS, 3)
    check("every group answered right lately: nothing is asked", srs.keeping_queue(pool, held, now), [])
    faded = dict(held)
    first = groups[0]
    q0 = pool.by_section[first][0]["id"]
    faded[q0] = card(srs.KEEP_FIRST_DAYS, 90)
    got = srs.keeping_queue(pool, faded, now, random.Random(2))
    check("one group's evidence faded: one question, from that group",
          (len(got), pool.by_id[got[0]]["section"] if got else None), (1, first))
    check("  and it is the one least recently met, not the faded one again",
          got and got[0] != q0, True)
    opened = dict(held)
    second = groups[1]
    q1 = pool.by_section[second][0]["id"]
    opened[q1] = dict(card(1.0, 0.1, reps=0, lapses=1, seen=2, correct=1),
                      due=(now - timedelta(minutes=1)).isoformat())
    got = srs.keeping_queue(pool, opened, now, random.Random(2))
    check("a miss: it comes back first", got[:1], [q1])
    check("  and its group opens for closer work, and only its group",
          {pool.by_id[q]["section"] for q in got}, {second})
    check("  closer work is more than the one question",
          len(got) > 2, True)
    check("the day's keeping is a short set", len(srs.keeping_queue(pool, {}, now, left=srs.KEEP_DAILY)),
          srs.KEEP_DAILY)

    print("\n-- Worked All Groups --")
    st = srs.group_state(pool, held, first, now, keeping=True)
    check("a group answered right lately is worked and bright", (st["worked"], st["glow"]), (True, 1.0))
    st = srs.group_state(pool, faded, first, now, keeping=True)
    check("  faded, it dims but stays worked", (st["worked"], 0 < st["glow"] < 1), (True, True))
    gone = {q0: card(2.0, 400)}
    st = srs.group_state(pool, gone, first, now)
    check("  and never below the floor", st["glow"], srs.GLOW_FLOOR)
    st = srs.group_state(pool, opened, second, now, keeping=True)
    check("a group whose last answer was a miss is still worked - like a state for WAS",
          (st["worked"], st["open"]), (True, True))
    check("never answered right: not worked", srs.group_state(pool, {}, first, now)["worked"], False)
    tally = srs.groups(pool, held, now)
    check("the tally", (tally["worked"], tally["total"]), (len(groups), len(groups)))

    print("\n-- Brush up --")
    per_q = {q["id"]: 0.5 for q in pool.questions}
    a, b, c = (pool.questions[i]["id"] for i in (0, 1, 2))
    mix = {a: card(4.0, 1), b: card(4.0, 30), c: card(1.0, 0.1, reps=0, lapses=1, seen=2, correct=1)}
    order = srs.brush_up_order(pool, mix, per_q, now, rng=random.Random(1))
    check("what has faded first, most faded first: the miss, then the long-gone",
          order[:2], [c, b])
    check("  then what is answered and holding", order[2], a)
    check("  then the unmet", all(q not in mix for q in order[3:]), True)

    print("\n-- through the app --")
    client = app.test_client()
    conn = db.connect()
    settings = db.get_profile(conn)["settings"]
    settings["license_class"] = "Extra"
    db.save_settings(conn, settings)
    conn.commit()
    page = client.get(f"/study/{POOL}", environ_base=LOCAL).get_data(as_text=True)
    check("the study page says it is keeping, with a way to learn in full instead",
          ("Keeping" in page, 'data-style="learn"' in page), (True, True))
    check("  the drill is called Keep it fresh, and Brush up is there", ("Keep it fresh" in page, "Brush up" in page),
          (True, True))
    check("  and nothing on it says due", "due review" in page.lower() or "overdue" in page.lower(), False)
    asked, answered = set(), 0
    for _ in range(40):
        got = client.get(f"/api/next?pool={POOL}&mode=drill&exclude={','.join(asked)}", environ_base=LOCAL).get_json()
        if got.get("done"):
            break
        q = pool.by_id[got["question_id"]]
        asked.add(q["id"])
        res = client.post("/api/answer", json={"pool": POOL, "question_id": q["id"],
                                               "chosen": got["order"].index(q["answer"]),
                                               "order": got["order"], "ms": 3000, "mode": "drill"},
                          environ_base=LOCAL).get_json()
        answered += 1
        if answered == 1:
            check("an answer knows it is keeping, and a month out", (res["keeping"], res["interval_days"]),
                  (True, srs.KEEP_FIRST_DAYS))
            check("  and says its group was worked", (res["group"] or {}).get("event"), "worked")
    check("the day's keeping ends after a short set", (answered, got.get("done")), (srs.KEEP_DAILY, True))
    check("  and says there is nothing owed", "Nothing waits on you" in (got.get("reason") or ""), True)
    check("every one of them from a different group",
          len({pool.by_id[q]["section"] for q in asked}), len(asked))
    home = client.get("/", environ_base=LOCAL).get_data(as_text=True)
    check("the dashboard counts groups worked, not reviews due",
          (f"{srs.KEEP_DAILY}/{len(groups)} groups worked" in home, "due for review" in home), (True, False))
    r = client.post("/api/study/style", json={"pool": POOL, "style": "learn"}, environ_base=LOCAL).get_json()
    check("learning it in full instead is a choice that is kept", (r["style"], r["chosen"]), ("learn", True))
    got = client.get(f"/api/next?pool={POOL}&mode=drill", environ_base=LOCAL).get_json()
    check("  and the drill carries on past the keeping set", got.get("done"), False)
    r = client.post("/api/study/style", json={"pool": POOL, "style": "auto"}, environ_base=LOCAL).get_json()
    check("  and going back is keeping again", (r["style"], r["chosen"]), ("keep", False))
    progress = client.get(f"/progress/{POOL}", environ_base=LOCAL).get_data(as_text=True)
    check("the progress page has the Worked All Groups map",
          ("Worked All Groups" in progress, progress.count('class="wag-cell') == len(groups)), (True, True))


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
