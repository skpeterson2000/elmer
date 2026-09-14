#!/usr/bin/env python3
"""CutThroat: musical chairs with questions, as rules with no clock in them.

    python3 tests/test_cutthroat.py

KC9SP's game: miss and you are out, every correct answer keeps its seat, a
round nobody got eliminates nobody; two left get fifteen questions where a
miss no longer removes anybody and the better count wins; level after
fifteen and it is sudden death - one right wins, both right the faster
wins, both wrong another question. The seated watch, placed by the order
they went out. Leaving is losing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import cutthroat  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def R(**who):
    """A round: R(a=True, b=False) - correct or not, with a time if given as (bool, ms)."""
    out = {}
    for p, v in who.items():
        if isinstance(v, tuple):
            out[p] = {"correct": v[0], "ms": v[1]}
        else:
            out[p] = {"correct": v, "ms": 1000}
    return out


def run():
    print("\n-- the field --")
    g = cutthroat.CutThroat(["a", "b", "c", "d"], passers=["d"])
    check("four in, playing the field", (g.phase(), len(g.alive())), ("field", 4))
    row = g.play(R(a=True, b=False, c=True))       # d answered nothing
    check("the two who missed are out - no answer is a miss", sorted(row["out"]), ["b", "d"])
    check("  the two who had it stay", row["remaining"], ["a", "c"])
    check("  which is the final, at once", g.phase(), "final")
    g2 = cutthroat.CutThroat(["a", "b", "c"])
    row = g2.play(R(a=False, b=False, c=False))
    check("a round nobody got eliminates nobody", (row["out"], row["note"]), ([], "nobody had it - nobody is out"))
    row = g2.play(R(a=True, b=False, c=False))
    check("a field of three can end in one round", (row["winner"], row["over"]), ("a", True))
    check("  with no final", g2.phase(), "over")

    print("\n-- the final: fifteen questions, misses do not remove --")
    g = cutthroat.CutThroat(["a", "b"])
    check("a table of two starts in the final", g.phase(), "final")
    for i in range(14):
        row = g.play(R(a=(i % 2 == 0), b=False))
        check(f"  question {i + 1}: nobody out", row["out"], [])
    check("  fourteen played", g.final["round"], 14)
    row = g.play(R(a=False, b=True))
    check("after fifteen the better count wins", (row["winner"], row["over"]), ("a", True))
    check("  seven to one", (g.final["correct"]["a"], g.final["correct"]["b"]), (7, 1))
    check("  the loser placed second", [(r["player"], r["place"]) for r in g.standing()], [("a", 1), ("b", 2)])

    print("\n-- sudden death --")
    g = cutthroat.CutThroat(["a", "b"])
    for i in range(15):
        g.play(R(a=True, b=True))
    check("level after fifteen: sudden death", (g.phase(), g.history[-1]["note"]),
          ("sudden", "level after 15 - sudden death"))
    row = g.play(R(a=False, b=False))
    check("both wrong: another question", (row["winner"], row["note"]), (None, "still level - another question"))
    row = g.play(R(a=(True, 2400), b=(True, 1900)))
    check("both right: the faster wins", row["winner"], "b")
    g = cutthroat.CutThroat(["a", "b"])
    for i in range(15):
        g.play(R(a=True, b=True))
    row = g.play(R(a=True, b=False))
    check("one right, one wrong: the right one wins", row["winner"], "a")

    print("\n-- the seated watch, and are placed --")
    g = cutthroat.CutThroat(["a", "b", "c", "d", "e"])
    g.play(R(a=True, b=True, c=True, d=False, e=False))     # d, e out in round 1
    g.play(R(a=True, b=True, c=False))                       # c out in round 2
    st = {r["player"]: r for r in g.standing()}
    check("the living lead", (st["a"]["in"], st["b"]["in"]), (True, True))
    check("last out places highest", (st["c"]["place"], st["d"]["place"], st["e"]["place"]), (3, 4, 5))
    check("  and knows the round it went out", st["c"]["out_round"], 2)
    g.seat("f")
    check("a late arrival during the final is seated, watching", g.standing()[-1]["in"], False)
    g3 = cutthroat.CutThroat(["a", "b", "c"])
    g3.seat("z")
    check("but during the field takes a chair", len(g3.alive()), 4)

    print("\n-- leaving is losing --")
    g = cutthroat.CutThroat(["a", "b", "c"])
    g.withdraw("b")
    check("gone, and out", ("b" in g.out_at, g.standing()[-1]["left"]), (True, True))
    check("  two left: the final", g.phase(), "final")
    g.withdraw("c")
    check("one left: the winner", (g.winner(), g.over()), ("a", True))
    check("as a dict, for the screens", g.as_dict()["phase"], "over")

    print("\n-- at a table: a person at the screen is in it, and their answer counts --")
    from elmer import party
    party.close_room()
    room = party.room(create=True, cohorts=1)
    me = room.join("KC9SP", device="screen")[0].id
    room.fill_bots("Listener")
    started, why = room.begin_cutthroat()
    check("the person and the practice players take chairs", (started is not None, me in room.cutthroat.order), (True, True))
    room.start_round("tech2026", "T1A01", 0, seconds=30, payload={"text": "?", "choices": ["a", "b", "c", "d"], "section": "T1A"})
    got, why = room.submit(me, 0, 1500)
    check("the person's answer is taken", (got is not None, why), (True, None))
    for b in [p for p in room.players.values() if p.bot]:
        room.submit(b.id, 1, 2000)                    # every practice player misses
    row = room.close_round()["cutthroat"]
    check("  and counts: the person is right, and in", (me in row["right"], me in row["remaining"]), (True, True))
    check("  the practice players that missed are out", all(b.id in row["out"] for b in room.players.values() if b.bot), True)
    check("  which makes the person the winner", (row["winner"], row["over"]), (me, True))
    party.close_room()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
