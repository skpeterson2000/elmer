#!/usr/bin/env python3
"""A shootout across a hall: the tables are the players.

    python3 tests/test_hallshootout.py

The rules are the same object a single table uses; here the players are the
tables. A table makes its shot if any person at it got the question right,
and its time is its quickest right answer. A table that had nobody right
when the picking table made it takes a letter. Practice players do not make
a real table's shot - a table full of bots that "made it" would be the
program handing itself the pick - and practice tables never keep the pick.

Net control's picker_unit had waited since the first day for a game that
consulted it. This is that game.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import netcontrol  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def question(net, section):
    net.start_round("tech2026", f"{section}01", 0,
                    {"text": "?", "choices": ["a", "b"], "section": section}, seconds=5)


def main():
    net = netcontrol.Net("Test net", 10, "technician")
    net.check_in("poldhu", "Poldhu", players=3)
    net.check_in("clifden", "Clifden", players=2)
    net.add_simulated(1)
    sim = net.simulated_units()[0].id
    sections = ["T1A", "T2B", "T3C", "T5A", "T7B"]
    titles = {"T1A": "Rules", "T5A": "Current and voltage"}

    print("\n-- the shootout seats the real tables first --")
    started, why = net.begin_shootout(sections, titles, pick_seconds=600)
    check("it starts", why, None)
    check("  the hall is in shootout mode", net.mode, netcontrol.SHOOTOUT)
    check("  the first pick is the first real table's", net.shootout.picker, "poldhu")
    check("  and the practice table never keeps it", sim in net.shootout.passers, True)
    view = net.shootout_view("poldhu")
    check("  Poldhu is told it is theirs", view["your_pick"], True)
    check("  Clifden is told it is not", net.shootout_view("clifden")["your_pick"], False)
    check("  the subjects carry their titles",
          next(a["title"] for a in view["available"] if a["section"] == "T5A"),
          "Current and voltage")

    print("\n-- picking --")
    got, why = net.choose("clifden", "T1A")
    check("another table cannot pick", got, None)
    check("  and is told whose it is", "Poldhu" in why, True)
    got, why = net.choose("poldhu", "T1A")
    check("the picking table picks", got, "T1A")
    check("  and the subject is waiting to be asked", net.take_pick(), "T1A")

    print("\n-- the round is a shot, table by table --")
    question(net, "T1A")
    # Poldhu: one person right, one wrong, a bot right. Clifden: nobody right.
    net.report("poldhu", 1, [{"name": "Ann", "correct": True, "ms": 1200},
                              {"name": "Al", "correct": False, "ms": 2000},
                              {"name": "Rig", "correct": True, "ms": 500, "bot": "practice"}])
    net.report("clifden", 1, [{"name": "Bob", "correct": False, "ms": 1500}])
    net.report(sim, 1, [{"name": "Whip", "correct": True, "ms": 900, "bot": "practice"}])
    summary = net.close_round()
    shot = summary["shootout"]
    check("Poldhu made it - a person at it was right", shot["made"], True)
    check("  Clifden took a letter - nobody there was", shot["took"], ["clifden"])
    check("  named for the screens", shot["took_names"], ["Clifden"])
    check("  the practice table matched it with its own answer", sim in shot["took"], False)
    check("  Poldhu keeps the pick", net.shootout.picker, "poldhu")
    check("  the board says so", net.board()["shootout"]["picker_name"], "Poldhu")

    print("\n-- a table's bots do not make its shot --")
    net.choose("poldhu", "T2B"); net.take_pick(); question(net, "T2B")
    net.report("poldhu", 2, [{"name": "Ann", "correct": False, "ms": 1200},
                              {"name": "Rig", "correct": True, "ms": 500, "bot": "practice"}])
    net.report("clifden", 2, [{"name": "Bob", "correct": True, "ms": 1100}])
    net.report(sim, 2, [{"name": "Whip", "correct": True, "ms": 900, "bot": "practice"}])
    shot = net.close_round()["shootout"]
    check("Poldhu missed - only its bot was right", shot["made"], False)
    check("  so nobody takes a letter", shot["took"], [])
    check("  and the pick goes to the quickest right table", net.shootout.picker, "clifden")

    print("\n-- a real table arriving late is dealt in, and the practice table it displaces is out --")
    # A real table checking in stands a practice table down to make room. The
    # first version of this left the departed table in the shootout's
    # seating, handed it the pick, and waited for a choice that never came.
    net.check_in("rugby-real", "Rugby (real)", players=1)
    check("the newcomer is in", "rugby-real" in net.shootout.letters, True)
    check("  level with the best-placed", net.shootout.letters["rugby-real"], 0)
    check("the practice table it displaced has left the hall", sim in net.units, False)
    check("  and is out of the game, not waiting to be handed the pick",
          net.shootout.letters[sim], 5)

    print("\n-- the clock on a real table's pick --")
    net.pick_seconds = 0.05
    check("Clifden is being waited on", net.waiting_for_pick(), True)
    import time; time.sleep(0.08)
    check("  until the clock runs out", net.pick_overdue(), True)
    net.pass_pick()
    check("then it goes round the hall - past the table that left, to the newcomer",
          net.shootout.picker, "rugby-real")
    net.add_simulated(1)
    fresh = net.simulated_units()[0].id
    check("a practice table added mid-game is seated", fresh in net.shootout.letters, True)
    check("  and never keeps the pick", fresh in net.shootout.passers, True)
    net.shootout.picker = fresh
    check("a practice table holding it picks for itself at once",
          net.choose_for_simulated() in sections, True)

    print("\n-- ending it --")
    net.end_shootout()
    check("back to a tournament", net.mode, netcontrol.TOURNAMENT)
    check("  with no shootout on the board", net.board()["shootout"], None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
