#!/usr/bin/env python3
"""The duel: two operators, code that gets longer and faster, first to miss is out.

    python3 tests/test_duel.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401
from elmer import duel  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run():
    print("\n-- the shape of it --")
    d = duel.Duel(1, 3, {1: "Ann", 3: "Cy"}, base_wpm=10, seed=1)
    check("round one is a copy of two characters at the base speed", (d.round, d.kind, len(d.text), d.wpm), (1, "copy", 2, 10.0))
    v = d.as_dict(1)
    check("  the runner hears it and is not shown it", (v["role"], v["text"], bool(v["groups"])), ("runner", None, True))
    check("  the room sees the round, the length and the speed, and no text", (d.as_dict(9)["you"], d.as_dict(9)["text"], "2 characters at 10 wpm" in d.words()), (False, None, True))
    check("a stranger cannot answer", "error" in d.act(9, d.text), True)
    r = d.act(1, d.text)
    check("the runner copies clean", (r["ok"], r["clean"]), (True, True))
    check("  and cannot answer twice", "error" in d.act(1, d.text), True)
    check("  the round waits for the baseman", (d.round, d.over()), (1, False))
    d.act(3, d.text)
    check("both clean: round two is a send of the same text", (d.round, d.kind, d.as_dict(3)["text"] == d.text), (2, "send", True))
    check("  logged", (d.log[0]["round"], d.log[0]["kind"], d.log[0]["a"], d.log[0]["b"]), (1, "copy", 100, 100))
    d.act(1, d.text); d.act(3, d.text)
    check("round three is a character longer and two words a minute faster", (d.round, d.kind, len(d.text), d.wpm), (3, "copy", 3, 12.0))

    print("\n-- first to miss is out --")
    d.act(1, d.text)
    d.act(3, d.text[:-1] + "?")
    check("the baseman misses: the runner wins", (d.over(), d.winner, d.as_dict(1)["winner_name"]), (True, 1, "Ann"))
    check("  and the words say so", d.words(), "Ann wins the duel in 3 rounds")
    check("  nothing more is taken", "error" in d.act(1, "x"), True)
    d2 = duel.Duel(1, 3, {1: "Ann", 3: "Cy"}, base_wpm=10, seed=2)
    d2.act(1, "??"); d2.act(3, d2.text)
    check("the runner misses: the baseman wins in one", (d2.winner, len(d2.log)), (3, 1))
    d3 = duel.Duel(1, 3, {1: "Ann", 3: "Cy"}, base_wpm=10, seed=3)
    d3.act(1, "??"); d3.act(3, "??")
    check("a round both miss goes to the runner", d3.winner, 1)

    print("\n-- the clock, and the practice players --")
    d4 = duel.Duel(1, 3, {1: "Ann", 3: "Cy"}, base_wpm=10, seed=4)
    d4.act(1, d4.text)
    d4.tick(d4.deadline + 1)
    check("the baseman who never answered has missed - the runner wins", (d4.over(), d4.winner), (True, 1))
    d5 = duel.Duel(1, 9, {1: "Ann", 9: "Sparks"}, base_wpm=10, seed=5, bots={9: "Elmer"})
    d5.act(1, d5.text)
    d5.tick(d5.deadline + 1)
    check("a practice player answers on its own, and the round resolves", (d5.round >= 1, len(d5.log) >= 1), (True, True))
    wins = 0
    for sd in range(40):
        dd = duel.Duel(1, 9, {1: "Ann", 9: "Sparks"}, base_wpm=10, seed=sd, bots={9: "Listener"})
        while not dd.over():
            dd.act(1, dd.text)
            dd.tick(dd.deadline + 1)
        wins += dd.winner == 1
    check("against a Listener who fades, a runner who never misses wins nearly always", wins >= 36, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
