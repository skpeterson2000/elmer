#!/usr/bin/env python3
"""Q-code bingo: the cards, the calls, the marks and the checking of a call.

    python3 tests/test_qbingo.py

The engine on its own, then in a room through the routes the screens use:
a card each for the people (none for practice players), calls keyed in
order, a call of bingo checked against what was keyed - a line marked and
all called stands, a line with an uncalled square does not and says which -
and the table never told the code it is keying until the next one is out.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import cw, party, qbingo  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def engine():
    print("-- the engine --")
    g = qbingo.QBingo([(1, "Ann"), (2, "Bob")], rng=random.Random(4))
    check("a card each, sixteen different Q signals",
          [len(set(g.cards[p])) for p in (1, 2)], [16, 16])
    check("the calls are every Q signal, once each, in an order fixed at the start",
          sorted(g.order), sorted(cw.Q_SIGNALS))
    check("ten lines: four rows, four columns, two diagonals", len(qbingo.LINES), 10)

    card = g.cards[1]
    top = qbingo.LINES[0]
    for sq in top:
        g.mark(1, sq)
    check("a marked line with nothing called does not stand, and says what is missing",
          (g.claim(1)[0], "not been called" in g.claim(1)[1]), (False, True))
    # Call until the top row's four codes are all out.
    want = {card[sq] for sq in top}
    while not want <= set(g.called):
        g.call()
    check("once all four have been keyed, the call stands", g.claim(1), (True, "bingo - " + ", ".join(card[sq] for sq in top)))
    check("  the game is over, and a second call is told who won", (g.over(), g.claim(2)[1]), (True, "Ann has already won"))
    check("  no more calls", g.call(), None)

    late = qbingo.QBingo([(1, "Ann")], rng=random.Random(5))
    while late.call():
        pass
    check("every code keyed is not the end: no more calls, but not over", (late.call(), late.over(), late.all_called()),
          (None, False, True))
    for sq in qbingo.LINES[4]:
        late.mark(1, sq)
    check("  and the last line can still be called", late.claim(1)[0], True)

    g2 = qbingo.QBingo([(1, "Ann")], rng=random.Random(9))
    check("nothing marked: not yet, no line", g2.claim(1), (False, "not yet - no line of four is marked"))
    check("a square off the card is refused", g2.mark(1, 16), (False, "not a square"))
    check("a stranger has no card", g2.mark(7, 0), (False, "you have no card in this game"))
    g2.mark(1, 3)
    g2.mark(1, 3, on=False)
    check("a mark can be taken back", g2.marks[1], set())
    g2.seat(5, "Cat")
    check("somebody who sits down mid-game gets a card", len(g2.cards[5]), 16)

    v = qbingo.QBingo([(1, "Ann")], rng=random.Random(2))
    v.call()
    first = v.called[0]
    view = v.view()
    check("the table is not told the code it is keying", (view["earlier"], first in str(view)), ([], False))
    check("  but has what to key: groups and timing", (bool(view["sound"]["groups"]), view["sound"]["timing"]["wpm"]),
          (True, 15.0))
    v.call()
    check("once the next is out, the last one is written, with its meaning",
          v.view()["earlier"], [{"code": first, "meaning": cw.Q_SIGNALS[first]}])
    check("a phone sees its card as meanings, not codes",
          (v.view(1)["card"][0], "card_codes" in v.view(1)), (cw.Q_SIGNALS[v.cards[1][0]], False))


def room():
    print("\n-- in a room --")
    r = party.Room() if hasattr(party, "Room") else None
    ann, _ = r.join("Ann")
    bob, _ = r.join("Bob")
    r.join("Practice", bot=1)
    g, why = r.begin_qbingo()
    check("people get cards, practice players do not", (why, sorted(g.cards)), (None, sorted([ann.id, bob.id])))
    check("the room says it is playing bingo", (r.mode, r.state(ann.id)["qbingo"]["players"]), (party.QBINGO, 2))
    code, _ = r.qbingo_call()
    check("a call keys a Q signal", code in cw.Q_SIGNALS, True)
    cara, _ = r.join("Cara")
    check("somebody arriving mid-game is dealt in", cara.id in g.cards, True)
    r.leave(bob.id)
    check("somebody leaving takes their card with them", bob.id in g.cards, False)
    check("marks go through the room", r.qbingo_mark(ann.id, 0), (True, None))
    r.end_qbingo()
    check("ending it puts the table back to a tournament", (r.qbingo, r.mode), (None, party.TOURNAMENT))
    empty = party.Room()
    check("bingo with nobody seated is refused", empty.begin_qbingo(), (None, "Q-code bingo needs somebody at the table"))


def main():
    engine()
    room()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
