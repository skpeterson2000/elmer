#!/usr/bin/env python3
"""Answering the drill out of the network tab, and ELMER noticing.

    python3 tests/test_peeking.py

The drill sends the shuffle with every question and deliberately always
will - it is about to give the answer away for free, and the card comes back
until it is actually known - so this is not a hole that gets defended. It is
one that gets remarked upon.

The properties worth holding: an honest answer never trips it, whatever the
combination of fast, correct and new taken two at a time; one lucky stab is
not enough to be accused of anything; the badge is not on the achievements
wall until it has been earned, because a hollow star naming the trick is an
instruction to everybody who has not thought of it; and the answer still
counts as correct, which is the whole joke - the scheduler believes it and
spaces the card out to somebody who has never read the question.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, game, peeking as P  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def card(seen=0):
    """A card row, or None for a question never met."""
    return {"seen": seen, "correct": seen, "lapses": 0, "interval": 1.0} if seen else None


print("\nthe three things together are what cannot happen honestly")
check("correct, unseen, 80 ms", P.impossible(True, 80, None), True)
check("  and at the floor it is already plausible",
      P.impossible(True, P.FLOOR_MS, None), False)

print("\n  any two of the three is an ordinary evening")
check("fast and new, but wrong", P.impossible(False, 80, None), False)
check("fast and correct, on a card met before",
      P.impossible(True, 80, card(seen=9)), False)
check("correct and new, at reading speed",
      P.impossible(True, 4200, None), False)

print("\n  and nothing trips on a missing or nonsense timing")
check("no timing at all", P.impossible(True, None, None), False)
check("  a negative one", P.impossible(True, -5, None), False)
check("  something that is not a number", P.impossible(True, "fast", None), False)


conn = db.connect()
db.get_profile(conn)

print("\nnothing is said for a lucky stab, or two")
for n in range(1, P.TRIP):
    check(f"answer {n} says nothing", P.note(conn, True, 60, None), None)
check("  but it is being counted", P.seen(conn), P.TRIP - 1)

print("\nthe third one gets the whole speech")
said = P.note(conn, True, 60, None)
check("something is said", bool(said), True)
check("  and it is the first time", said["first"], True)
check("  several paragraphs of it", len(said["lines"]), len(P.FIRST))

print("\n  and it makes the four points worth making")
words = " ".join(said["lines"]).lower()
check("that the shuffle is there on purpose", "not an oversight" in words, True)
check("  that the answer was about to be free", "for nothing" in words, True)
check("  that the card is coming back anyway", "coming back" in words, True)
check("  that the exam is the one that is sealed", "sealed" in words, True)
check("  and nowhere does it tell anybody to stop",
      "stop" in words.replace("make it stop", ""), False)

print("\nafterwards it is a line, and it moves through them")
notes = [P.note(conn, True, 60, None) for _ in range(len(P.AGAIN))]
later = [n["lines"][0] for n in notes]
check("one line each time", [len(n["lines"]) for n in notes], [1] * len(P.AGAIN))
check("  and none of them claims to be the first", [n["first"] for n in notes],
      [False] * len(P.AGAIN))
check("  none of them repeats within the set", len(set(later)), len(P.AGAIN))
check("  and none of them is the first speech again",
      any(line in P.FIRST for line in later), False)

print("\n  an honest answer in the middle of all that says nothing")
check("right, but read", P.note(conn, True, 3000, None), None)
check("  and is not counted against anybody",
      P.seen(conn), P.TRIP + len(P.AGAIN))

conn.close()


print("\nthe badge is not on the wall until it is earned")
codes = [row[0] for row in game.wall({})]
check("it is in the full list", P.BADGE in [r[0] for r in game.ACHIEVEMENTS], True)
check("  and not on an empty wall", P.BADGE in codes, False)
check("  which is one shorter than the list",
      len(codes), len(game.ACHIEVEMENTS) - len(game.SECRET))
check("  so the count beside the wall gives nothing away",
      len(game.wall({})) == len(game.wall(None)), True)

held = [row[0] for row in game.wall({P.BADGE: "2026-09-22"})]
check("once earned it is there", P.BADGE in held, True)
check("  and every ordinary badge is on the wall either way",
      len(held), len(game.ACHIEVEMENTS))

print("\nand it has a name and a description like any other")
name, desc = game.ACHIEVEMENT_INDEX[P.BADGE]
check("named", name, "Read the Wire")
check("  described", bool(desc), True)


print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
