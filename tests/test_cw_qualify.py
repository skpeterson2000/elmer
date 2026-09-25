#!/usr/bin/env python3
"""The qualifying run: five minutes sent, one clean minute asked for.

    python3 tests/test_cw_qualify.py

Somebody who already knows the code - a tester who reset their profile to see
what a beginner sees, an operator coming back after years - owed eight hundred
flawless sends before the last character opened, one at a time, for letters
they had copied since before this program existed. The program was being shown
proficiency repeatedly and failing to notice.

So: the operator names the speed they think they can hold, and gets the run the
old code tests gave - five minutes of plain language, with one contiguous
minute of perfect copy as the bar. It ends the moment that minute lands, because
making somebody sit through four more after they have proved the thing is the
program collecting evidence for its own sake. What was copied counts: the run is
practice, its sends are real sends, and a clean minute at speed is a great deal
of evidence arriving at once.

Two things have to be right or it is a lottery. When each character went out is
computed from the code at that speed rather than guessed. And what was typed is
aligned against what was sent, properly - a copyist who drops one character and
carries on is a character behind for the rest of the run, and scored position by
position that reads as everything after the slip being wrong.

And nobody is told they failed. Somebody who reached too high is given the speed
the run just measured for them; somebody whose characters are not there yet is
told that, and where it starts.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import app as appmod, cw, db  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\nthe run is real traffic, and it exercises the whole order")
# Plain words alone leave fourteen of the forty characters unsent - every
# digit, the punctuation, and Q, Z, X and J, which are exactly the ones a
# proficient operator would most like credit for.
text = cw.qualifying_text(20, seed=4)
have = set(text.replace(" ", ""))
covered = sum(1 for c in cw.KOCH_ORDER if c in have)
check("most of the order is sent at a working speed", covered >= 34, True)
# Five minutes cannot give twelve clean reps of forty characters, so a run
# places rather than proves: it says which characters this operator has met
# and copies, and the solidity accrues from there. A faster run sends more and
# therefore settles more of them.
slow = cw.qualifying_text(20, cw.QUALIFY_SECONDS, seed=3)
fast = cw.qualifying_text(40, cw.QUALIFY_SECONDS, seed=3)
enough = lambda t: sum(1 for c in cw.KOCH_ORDER if t.count(c) >= cw.CLEAN_RUN)  # noqa: E731
check("  a faster run settles more of them", enough(fast) > enough(slow), True)
check("  including digits", any(c.isdigit() for c in have), True)
check("  and a callsign with a slant in it somewhere",
      any("/" in w for w in cw.qualifying_text(25, seed=11).split()), True)
check("the run is about as long as the time it fills",
      abs(len(text) - 20 * 5 * cw.QUALIFY_SECONDS / 60) < 60, True)
check("a slower run is shorter, and says less about the far end",
      len(cw.qualifying_text(5, seed=4)) < len(text), True)

print("\na speed is a number until you know who is up there")
# Facts worth knowing, written down once and read wherever a speed is
# chosen or measured. The two records at the top are reported rather than
# asserted, and named, because this program cannot verify a world record
# and should not sound as though it can.
check("every speed lands on a rung", all(cw.speed_note(w) for w in (1, 5, 13, 22, 45, 80, 200)), True)
check("  the rungs do not overlap or leave gaps",
      all(cw.SPEED_LADDER[i]["to"] + 1 == cw.SPEED_LADDER[i + 1]["from"]
          for i in range(len(cw.SPEED_LADDER) - 1)), True)
check("  nonsense lands somewhere rather than raising",
      bool(cw.speed_note("quick")["name"]), True)
check("thirteen is where the old tests were",
      "Novice" in cw.speed_note(13)["note"], True)
check("head copy is named where it happens",
      "head" in cw.speed_note(32)["note"], True)
check("past seventy it is machine work, and says so",
      "software" in cw.speed_note(75)["note"], True)
# A world record is published - that is the point of one - so it is named,
# dated, and linked to somewhere anybody can check it. The figure that gets
# repeated second-hand (140 wpm "plain text") is wrong twice over: it came
# from RufzXP, which sends single callsigns, and the holder himself calls the
# plain-text framing misleading.
top = cw.speed_note(200)
check("the record is attributed to a person", "YO8YNS" in top["note"], True)
check("  with the figure and where it was set",
      "311,192" in top["note"] and "Tunisia" in top["note"], True)
check("  and says what RufzXP actually sends",
      "Single callsigns, not prose" in top["note"], True)
check("  and carries a source anybody can follow",
      top["source"].startswith("http") and bool(top["source_name"]), True)
check("  and is not held up as a target", "not a target" in top["note"], True)
check("every rung with a claim in it carries its source",
      all(r.get("source", "").startswith("http")
          for r in cw.SPEED_LADDER if "record" in r["note"] or "championship" in r["note"]), True)
check("the run's own format is cited too",
      cw.QUALIFY_SOURCE.startswith("https://") and bool(cw.QUALIFY_SOURCE_NAME), True)
check("there is always a rung above, until the top",
      (bool(cw.speed_above(20)), cw.speed_above(500)), (True, None))

print("\nwhen each character went out is computed, not guessed")
marks = cw.run_marks("PARIS", "PARIS", 20)
check("five characters, five marks", len(marks), 5)
check("  all copied", all(m["ok"] for m in marks), True)
# PARIS at 20 wpm is one word in three seconds, by definition of the standard.
check("  and PARIS takes about three seconds at 20 wpm",
      2.4 < marks[-1]["at"] < 3.2, True)

print("\nthe alignment survives a dropped character, which is the whole point")
long_text = cw.qualifying_text(28, seed=2)
whole = cw.run_marks(long_text, long_text, 28)
slipped = cw.run_marks(long_text, long_text[:40] + long_text[41:], 28)
check("a perfect copy scores perfect",
      sum(1 for m in whole if m["ok"]), len(whole))
check("  and one dropped character still does",
      sum(1 for m in slipped if m["ok"]) >= len(slipped) - 2, True)
check("  so the clean minute survives it", cw.clean_stretch(slipped)["passed"], True)
# Scored position by position, that same run reads as a disaster - which is
# what difflib's longest-block-first instinct produced on a real one.
naive = sum(1 for a, b in zip(long_text, long_text[:40] + long_text[41:]) if a == b)
check("  where naive position matching would have thrown it away",
      naive < len(whole) / 2, True)
rough = "".join(c if (i % 3) else "X" for i, c in enumerate(long_text))
scored = cw.run_marks(long_text, rough, 28)
hit = sum(1 for m in scored if m["ok"]) / len(scored)
check("two thirds right is scored as about two thirds", 0.6 < hit < 0.75, True)
started = time.perf_counter()
cw.run_marks(long_text, rough, 28)
check("  and it is quick enough to do on a page load",
      (time.perf_counter() - started) < 0.5, True)

print("\none contiguous minute, and a miss ends the stretch")
check("nothing copied is no stretch at all",
      cw.clean_stretch([{"ok": False, "at": i} for i in range(200)])["seconds"], 0.0)
steady = [{"ok": True, "at": i * 0.5} for i in range(200)]
check("a long clean run passes", cw.clean_stretch(steady)["passed"], True)
broken = [{"ok": True, "at": i * 0.5} for i in range(100)]
broken[50]["ok"] = False
check("  a miss in the middle breaks it in two",
      cw.clean_stretch(broken)["passed"], False)
check("  and what is left is measured honestly",
      24 < cw.clean_stretch(broken)["seconds"] < 26, True)
# The scramble at the start is not held against anybody: the stretch is the
# best one anywhere in the run, which is what settling looks like.
settles = [{"ok": i % 3 != 0, "at": i * 0.6} for i in range(40)]
settles += [{"ok": True, "at": 24 + i * 0.6} for i in range(150)]
check("a scrambled start then a clean stretch passes",
      cw.clean_stretch(settles)["passed"], True)

print("\nnobody is told they failed")
passed = cw.qualify_advice(22, [{"ok": True}] * 100, True)
check("a clean run is called one", "qualifying run" in passed["head"], True)
reached = cw.qualify_advice(28, [{"ok": i % 4 != 0} for i in range(200)], False)
check("reaching too high is given the speed it measured",
      reached["suggest_wpm"] < 28 and reached["suggest_wpm"] >= cw.QUALIFY_LEAST_WPM, True)
check("  and is not told it failed", "fail" in reached["words"].lower(), False)
check("  it is told the copying was real", "real copying" in reached["words"], True)
early = cw.qualify_advice(18, [{"ok": i < 5} for i in range(200)], False)
check("somebody whose characters are not there is told where it starts",
      early.get("start_here"), True)
check("  kindly, and with a horizon on it",
      "learnable" in early["words"] or "by the spring" in early["words"], True)
check("  and no speed is suggested, because no speed would fix it",
      early["suggest_wpm"], None)
check("nothing copied at all is a fine place to be",
      "everybody starts" in cw.qualify_advice(20, [], False)["words"], True)

print("\na run that lands is evidence, and the record takes it")
client = appmod.app.test_client()
local = {"REMOTE_ADDR": "127.0.0.1"}
before = client.get("/api/cw/plan", environ_base=local).get_json()["plan"]
got = client.get("/api/cw/qualify?wpm=22", environ_base=local).get_json()
check("the run comes with its timing", got["wpm"] and got["clean"], 22.0 and cw.QUALIFY_CLEAN)
# The material the endpoint hands out is different every time, by design - so
# the run this check scores is a seeded one. Asked for a random run and told to
# expect a particular amount of the order to open, this passed alone and failed
# in the suite, which is the worst way for a test to behave.
run_text = cw.qualifying_text(22, cw.QUALIFY_SECONDS, seed=20260925)
result = client.post("/api/cw/qualify",
                     json={"wpm": 22, "text": run_text, "typed": run_text},
                     environ_base=local).get_json()
check("a clean run passes", result["clean"]["passed"], True)
check("  and characters are written down", result["characters"] >= 30, True)
# What a run buys is placement, not a certificate. The lesson opens to what
# was met and copied - measured across a dozen seeded runs, no fewer than
# twenty-six of the forty and usually all of them - so a returning operator
# drills the whole alphabet instead of crawling out of K and M one character
# at a time. Being *solid* still has to be earned, and the run barely starts
# that: it is five minutes, and twelve clean reps of forty characters is not
# in five minutes at any speed.
check("  the lesson opens on the strength of it",
      result["plan"]["lesson"] >= 26, True)
check("  which is a long way past where it started",
      result["plan"]["lesson"] > before["lesson"] + 20, True)
check("  but nobody is declared solid on the whole order for five minutes' work",
      result["plan"]["solid"] < result["plan"]["total"], True)
# It is evidence, not a switch: what was not copied is not credited.
progress = db.cw_progress(db.connect())
check("  but only for what was actually copied",
      all(row["sent"] >= row["copied"] for row in progress.values()), True)

print("\nthe speed asked for is held to something sendable")
for asked, want in ((0, cw.QUALIFY_LEAST_WPM), (999, cw.QUALIFY_MOST_WPM)):
    d = client.get("/api/cw/qualify?wpm=%d" % asked, environ_base=local).get_json()
    check("  %s wpm becomes %s" % (asked, want), d["wpm"], float(want))
check("  and nonsense does not raise",
      client.get("/api/cw/qualify?wpm=fast", environ_base=local).status_code, 200)
check("a run with nothing typed is scored, not refused",
      client.post("/api/cw/qualify", json={"wpm": 20, "text": "PARIS", "typed": ""},
                  environ_base=local).get_json()["clean"]["passed"], False)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
