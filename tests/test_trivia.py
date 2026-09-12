#!/usr/bin/env python3
"""The cards for the wait.

    python3 tests/test_trivia.py

Every card must be checkable and must say where it comes from, because a
program whose numbers are measured cannot start handing out folklore the
moment it changes the subject. What is checked here is the shape of that
promise: every card has text and an attribution, no card is a duplicate, and
a draw does not hand back the card just shown when there is any other.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import trivia  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\nevery card is a card")
check("there is a deck", trivia.count() >= 20, True)
check("every card has text", all(t.strip() for t, _ in trivia.CARDS), True)
check("  and says where it comes from", all(a.strip() for _, a in trivia.CARDS), True)
check("  none of them twice", len({t for t, _ in trivia.CARDS}), trivia.count())
check("  and none of them a wall", max(len(t) for t, _ in trivia.CARDS) <= 320, True)

print("\na draw is a card, and not the one just shown")
card = trivia.draw(random.Random(1))
check("a draw has the two parts, and says which deck", sorted(card), ["about", "deck", "text"])
again = [trivia.draw(random.Random(n), avoid=card["text"])["text"] for n in range(40)]
check("forty draws avoiding it never hand it back", card["text"] in again, False)

print("\nthree decks, each card with its provenance")
for deck, cards in trivia.DECKS.items():
    check(f"{deck}: every card has text and a source", all(t and a for t, a in cards), True)
    check(f"  none twice", len({t for t, _ in cards}), len(cards))
check("a quote is drawn from the quotes", trivia.draw(random.Random(3), deck="quotes")["deck"], "quotes")
check("  a ham from the hams", trivia.draw(random.Random(3), deck="hams")["deck"], "hams")
check("  an unknown deck falls back to history", trivia.draw(random.Random(3), deck="nope")["deck"], "history")
check("every ham card carries a callsign",
      all(any(ch.isdigit() for ch in t.split(" - ")[-1]) for t, _ in trivia.HAMS), True)
check("  and a dead one is marked SK", any("(SK)" in t for t, _ in trivia.HAMS), True)
check("the folklore-prone quotes say so",
      all(any(w in a for w in ("attributed", "story", "varies", "unattributed", "proverb", "reported", "quoted widely"))
          for t, a in trivia.QUOTES if "Segal" not in a and "Collier" not in a), True)

print("\nthe disputed ones are said to be disputed")
soft = [t for t, _ in trivia.CARDS if "Fessenden" in t or "Marconi reported" in t]
check("Marconi's S and Fessenden's broadcast are both here", len(soft), 2)
check("  and both are phrased as claims, not facts",
      all(("reported" in t or "his own" in t or "argued" in t) for t in soft), True)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
