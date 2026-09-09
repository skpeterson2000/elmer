#!/usr/bin/env python3
"""The shape of a match, and the rules that end one.

    python3 tests/test_match.py

A game that cannot declare a winner is a pastime, and the rules that declare
one are exactly the sort of thing that gets argued about at the table. So they
are written down in one place and checked here rather than discovered by
somebody who thinks they have just won.

The lengths are taken from the elements they are practice for: 35 questions
for Technician and General, 50 for Extra. Five rounds of eight is 40 and five
of twelve is 60, and both of those are meant to be near their element rather
than equal to it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import match as M  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the length is the element's, near enough --")
    check("five rounds, always", M.ROUNDS, 5)
    check("Technician is 40 questions", M.length("technician"), 40)
    check("  and General the same", M.length("general"), 40)
    check("Extra is 60", M.length("extra"), 60)
    check("  which is half again as long", M.length("extra"),
          int(M.length("general") * 1.5))
    check("and an unknown class gets the short one", M.length(None), 40)
    check("every match is an odd number of rounds, so it ends",
          M.ROUNDS % 2, 1)

    print("\n-- a round is taken, never drawn --")
    check("most correct takes it",
          M.round_winner({"a": {"correct": 6, "ms": 9000},
                          "b": {"correct": 5, "ms": 1000}}), "a")
    check("  and equal correct goes to the faster",
          M.round_winner({"a": {"correct": 5, "ms": 9000},
                          "b": {"correct": 5, "ms": 1000}}), "b")
    check("  with speed unable to buy a round outright",
          M.round_winner({"a": {"correct": 2, "ms": 100},
                          "b": {"correct": 3, "ms": 99000}}), "b")
    check("a round nobody scored in goes to nobody",
          M.round_winner({"a": {"correct": 0, "ms": 0},
                          "b": {"correct": 0, "ms": 0}}), None)
    check("  and so does an empty room", M.round_winner({}), None)
    check("a dead heat on both is at least stable",
          M.round_winner({"b": {"correct": 4, "ms": 500},
                          "a": {"correct": 4, "ms": 500}}), "a")

    print("\n-- three of five ends it, whenever it happens --")
    early = M.verdict({"a": 3, "b": 1}, 4)
    check("clinched before the rounds run out", early["state"], "won")
    check("  by the player who did it", early["winner"], "a")
    check("  and it is not called overtime", early["overtime"], False)
    check("two apiece with a round to go is still playing",
          M.verdict({"a": 2, "b": 2}, 4)["state"], "playing")

    print("\n-- and with three players it can run past regulation --")
    over = M.verdict({"a": 2, "b": 2, "c": 1}, 5)
    check("nobody has a majority, so it goes on", over["state"], "playing")
    check("  and says it is overtime", over["overtime"], True)
    check("one round clear is not enough",
          M.verdict({"a": 3, "b": 2, "c": 1}, 6)["state"], "playing")
    two = M.verdict({"a": 4, "b": 2, "c": 1}, 7)
    check("two clear takes it", two["state"], "won")
    check("  and says which it was", two["overtime"], True)

    print("\n-- and a deadlock is eventually put out of its misery --")
    for played in (6, 7, 8, 9):
        check(f"{played - M.ROUNDS} overtime rounds is not yet a draw",
              M.verdict({"a": played // 2, "b": played // 2,
                         "c": 0}, played)["state"] != "deadlocked", True)
    stuck = M.verdict({"a": 4, "b": 4, "c": 2}, 10)
    check("five past regulation and a draw is offered",
          stuck["state"], "deadlocked")
    check("  with nobody declared", stuck["winner"], None)
    check("  and the offer said in words", "draw" in stuck["why"], True)

    print("\n-- nothing has happened yet is its own answer --")
    check("no rounds won at all", M.verdict({}, 0)["state"], "playing")
    check("  and it does not pretend to know who is ahead",
          M.verdict({}, 0)["winner"], None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
