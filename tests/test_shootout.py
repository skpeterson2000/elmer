#!/usr/bin/env python3
"""Shootout: the rules of the game where choosing the question is the move.

    python3 tests/test_shootout.py

The property worth testing hardest is the one the whole design turns on: that
picking a question you cannot answer yourself gains you nothing. Without it
the winning strategy is to find the strangest corner of the pool and wait for
the room to fail, which is a test of who owns the most obscure question rather
than of who knows the most - and the game KC9SP described, "pick the question
you know and your opponent does not", would not be the game that got built.

After that: a subject is spent when it is played, so a strong player works
through their good ones rather than picking the same one until everybody is
out; letters only come from a made shot; a player who is out stops taking them
and stops being handed the pick; and the game ends when one player is left
rather than running a fixed length nobody is still playing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer.shootout import Shootout, is_out, letters  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def right(ms):
    return {"correct": True, "ms": ms}


def wrong(ms=9000):
    return {"correct": False, "ms": ms}


def game(sections=8):
    return Shootout(["ann", "bob", "cat"],
                    sections=[f"T{n}A" for n in range(sections)])


def main():
    print("\n-- the word --")
    check("nothing yet", letters(0), "")
    check("three in", letters(3), "ELM")
    check("spelled", letters(5), "ELMER")
    check("and no further", letters(9), "ELMER")
    check("out at five", [is_out(4), is_out(5)], [False, True])

    print("\n-- a made shot costs the people who missed it --")
    g = game()
    played = g.play("T0A", {"ann": right(1000), "bob": wrong(), "cat": right(2000)})
    check("the picker made it", played["made"], True)
    check("  and only the miss took a letter", played["took"], ["bob"])
    check("  the picker keeps the pick", g.picker, "ann")
    check("  nobody is out on one letter", played["out"], [])

    print("\n-- the shot that was not made costs nobody anything --")
    # This is the design. Ann picks something she cannot answer: Bob and Cat
    # both miss it too, and neither of them pays for it.
    g = game()
    before = dict(g.letters)
    played = g.play("T0A", {"ann": wrong(), "bob": wrong(), "cat": wrong()})
    check("the shot was missed", played["made"], False)
    check("  nobody took a letter", played["took"], [])
    check("  and nothing moved", g.letters, before)

    print("\n-- picking what you cannot answer is worth nothing, repeatedly --")
    # Played out rather than argued: Ann picks eight obscure subjects in a row
    # and answers none of them. If the strategy worked, Bob and Cat would be
    # spelling ELMER by now.
    g = game()
    for n in range(8):
        g.play(f"T{n}A", {"ann": wrong(), "bob": wrong(), "cat": wrong()})
    check("eight bad picks later, nobody has a letter",
          [g.letters["bob"], g.letters["cat"]], [0, 0])
    check("  and the game is not over", g.over(), False)

    print("\n-- the pick passes on a miss, to the quickest who got it --")
    g = game()
    played = g.play("T0A", {"ann": wrong(), "bob": right(3000), "cat": right(1200)})
    check("it goes to the faster of them", played["next_picker"], "cat")
    check("  and that is who holds it", g.picker, "cat")

    print("\n-- and goes round the table when nobody got it --")
    g = game()
    g.play("T0A", {"ann": wrong(), "bob": wrong(), "cat": wrong()})
    check("the next seat takes it", g.picker, "bob")

    print("\n-- a subject is spent when it is played --")
    g = game()
    g.play("T0A", {"ann": right(100), "bob": wrong(), "cat": wrong()})
    ok, why = g.may_pick("T0A")
    check("it cannot be picked again", ok, False)
    check("  and it says why", why, "that subject has already been played")
    check("  it is off the list", "T0A" in g.available(), False)
    check("  a subject from another pool is refused too",
          g.may_pick("G9Z")[0], False)
    check("  and playing a spent one changes nothing",
          g.play("T0A", {"ann": right(100)}).get("error") is not None, True)

    print("\n-- five letters and you are out --")
    g = game()
    for n in range(5):
        g.play(f"T{n}A", {"ann": right(100), "bob": wrong(), "cat": right(200)})
    check("bob has spelled it", g.letters["bob"], 5)
    check("  and is out", [p["out"] for p in g.standing()], [False, True, False])
    check("  the game is not over - two are still in", g.over(), False)

    # Out means out: no more letters, and never handed the pick.
    played = g.play("T5A", {"ann": right(100), "bob": wrong(), "cat": wrong()})
    check("an eliminated player takes no more letters", g.letters["bob"], 5)
    check("  and only cat was charged", played["took"], ["cat"])

    print("\n-- last one standing --")
    g = game()
    for n in range(5):
        g.play(f"T{n}A", {"ann": right(100), "bob": wrong(), "cat": wrong()})
    check("both of them are out", [g.letters["bob"], g.letters["cat"]], [5, 5])
    check("the game is over", g.over(), True)
    check("  and ann won it", g.winner(), "ann")
    check("  with nobody left picking", g.picker, None)

    print("\n-- one player is not a game --")
    solo = Shootout(["ann"], sections=["T0A"])
    check("a lone player has not won by default", solo.over(), False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
