#!/usr/bin/env python3
"""The mock exam gives nothing back until it is handed in.

    python3 tests/test_exam_silence.py

Everywhere else in ELMER the program is generous: a verdict on every answer,
an explanation, a run counter that moves, a rank ladder, badges, a sound.
The mock exam is the one place that deliberately withholds all of it,
because it is meant to be as near a facsimile of sitting in front of a VE
team as a program can manage, and the real paper tells you nothing until it
is marked.

That is an easy thing to break by accident - one helpful line in a shared
template, one chime script moved into base.html - and the breakage would be
invisible, because the exam would still work. So it is held here:

* the questions handed to the browser carry no answer key, so nothing on the
  page can be read to find out how a question went;
* starting an exam moves nothing a person would see - no XP, no streak, no
  run ladder, no badge;
* the answer endpoint that does give a verdict is not the one the exam uses;
* the exam page loads no sound;
* and the result, when it does come, is complete.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import app as appmod, db, runladder  # noqa: E402

FAILS = []
ROOT = Path(__file__).resolve().parents[1]
POOL = "tech2026"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


client = appmod.app.test_client()

print("\nthe exam handed to the browser carries no answer key")
started = client.post("/api/exam/start", json={"pool": POOL}).get_json()
check("an exam was built", started["total"] > 0, True)
check("no item carries an answer",
      any("answer" in item for item in started["items"]), False)
check("  nor the order the choices were shuffled into",
      any("order" in item for item in started["items"]), False)
check("  the questions and choices are there, which is the point",
      all(item.get("text") and item.get("choices") for item in started["items"]), True)

raw = json.dumps(started)
check("and the word 'answer' is nowhere in the payload at all",
      '"answer"' in raw, False)


print("\nstarting an exam moves nothing a person would see")
conn = db.connect()
profile = db.get_profile(conn)
before = {"xp": profile["xp"], "streak": profile["streak_days"],
          "ladder": runladder.view(conn, POOL),
          "badges": sorted(appmod.game.earned(conn))}
conn.close()

client.post("/api/exam/start", json={"pool": POOL})

conn = db.connect()
profile = db.get_profile(conn)
check("no XP was paid", profile["xp"], before["xp"])
check("the daily streak did not move", profile["streak_days"], before["streak"])
check("the run ladder did not move",
      runladder.view(conn, POOL), before["ladder"])
check("and no badge was handed out",
      sorted(appmod.game.earned(conn)), before["badges"])
conn.close()


print("\nthe endpoint that gives a verdict is not the one the exam uses")
exam_js = (ROOT / "elmer" / "static" / "exam.js").read_text(encoding="utf-8")
check("exam.js never calls /api/answer", "/api/answer" in exam_js, False)
check("  it submits, and that is all", "/api/exam/" in exam_js, True)
check("  nothing in it renders a verdict", "verdict" in exam_js, False)
check("  and nothing in it plays a sound", "Chime" in exam_js, False)


print("\nthe exam page loads no sound")
page = client.get(f"/exam/{POOL}").get_data(as_text=True)
check("chime.js is not on the exam page", "chime.js" in page, False)
check("  it is on the study page, where feedback belongs",
      "chime.js" in client.get(f"/study/{POOL}").get_data(as_text=True), True)
check("  and the exam page says plainly that nothing is marked until submit",
      "Nothing is marked until you submit" in page, True)


print("\nand when the paper is handed in, the marking is complete")
exam = client.post("/api/exam/start", json={"pool": POOL}).get_json()
result = client.post(f"/api/exam/{exam['exam_id']}/submit",
                     json={"responses": {}, "seconds": 120}).get_json()
check("every question was marked", len(result["results"]), exam["total"])
check("  a blank paper scores nothing", result["score"], 0)
check("  which is not a pass", result["passed"], False)
check("  the right answer is shown for each one",
      all(r.get("answer_text") for r in result["results"]), True)
check("  broken down by subelement", len(result["breakdown"]) > 0, True)
check("  and the exam is study too, so it paid XP", result["xp"] > 0, True)

conn = db.connect()
check("but still moved no run ladder",
      runladder.view(conn, POOL)["best"], 0)
conn.close()


print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
