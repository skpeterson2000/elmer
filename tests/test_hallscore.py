#!/usr/bin/env python3
"""The hall's running totals, and what a big board can be asked to leave out.

    python3 tests/test_hallscore.py

A hall scores by table, so that a table of eight cannot beat a table of three
by arithmetic. That is the right way to decide who won, and it is not what the
person sitting at one wants to look at: they want to find their own name. The
board could only ever show the table totals and the last question, so a player
had no way to see whether they were having a good evening or a bad one.

Practice players count and are flagged rather than dropped, because a board
with the practice tables edited out of it is not the game that was played -
but a club night with three real tables among six can ask for the three. That
choice belongs to the screen; the totals underneath it are the same either
way, which is what stops two boards watching one net disagreeing about who is
winning.

Every answer counts towards a person's total, not only the ones that scored:
two right out of three and two right out of twenty are different evenings and
a points column cannot tell them apart.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import netcontrol  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def a_round(net, number, rows_by_unit):
    """Put a question, take everybody's answers, score it."""
    net.start_round("tech2026", f"T1A{number:02d}", 0,
                    {"text": "?", "choices": ["a", "b"], "section": "T1A"},
                    seconds=5)
    for unit_id, rows in rows_by_unit.items():
        net.report(unit_id, net.round_number, rows)
    return net.close_round()


def main():
    net = netcontrol.Net("Test net", 10, "technician")
    net.check_in("u1", "Poldhu", players=2)
    net.check_in("u2", "Clifden", players=1)
    # The flag that matters here is the one on the player's own row. A table
    # says which of its players were practice when it reports, and a real Pi
    # with bots sitting at it says the same thing - so the hall never has to
    # infer it from whether the whole table was simulated.

    print("\n-- nothing has happened yet --")
    check("no totals before a round", net.people_board(), [])

    print("\n-- one round, scored --")
    a_round(net, 1, {
        "u1": [{"name": "Ann", "correct": True, "ms": 1000},
               {"name": "Bob", "correct": False, "ms": 4000}],
        "u2": [{"name": "Rig", "correct": True, "ms": 2000, "bot": "practice"}],
    })
    people = {p["name"]: p for p in net.people_board()}
    check("everybody who answered is counted", sorted(people), ["Ann", "Bob", "Rig"])
    check("the quickest correct leads", net.people_board()[0]["name"], "Ann")
    check("  and carries their table", people["Ann"]["unit_name"], "Poldhu")
    check("a wrong answer still counts as answered",
          [people["Bob"]["correct"], people["Bob"]["answered"]], [0, 1])
    check("  and scores nothing", people["Bob"]["score"], 0)
    check("a practice player is flagged", people["Rig"]["bot"], True)
    check("  and a real one is not", people["Ann"]["bot"], False)

    print("\n-- a second round adds to the first --")
    a_round(net, 2, {
        "u1": [{"name": "Ann", "correct": False, "ms": 3000},
               {"name": "Bob", "correct": True, "ms": 1200}],
        "u2": [{"name": "Rig", "correct": True, "ms": 900, "bot": "practice"}],
    })
    people = {p["name"]: p for p in net.people_board()}
    check("totals accumulate rather than reset",
          [people["Ann"]["answered"], people["Bob"]["answered"]], [2, 2])
    check("  correct counts follow the answers",
          [people["Ann"]["correct"], people["Bob"]["correct"]], [1, 1])
    check("  and points only come from the right ones",
          people["Bob"]["score"] > 0, True)

    print("\n-- the same person at two tables is two players --")
    # Names are not unique across a hall and never were: two clubs can both
    # have a Dave. Keying on the table as well is what stops one of them
    # collecting the other's points.
    net.check_in("u3", "Nauen", players=1)
    a_round(net, 3, {
        "u1": [{"name": "Dave", "correct": True, "ms": 1000}],
        "u3": [{"name": "Dave", "correct": True, "ms": 1100}],
    })
    daves = [p for p in net.people_board() if p["name"] == "Dave"]
    check("two Daves, not one", len(daves), 2)
    check("  at different tables",
          sorted(p["unit_name"] for p in daves), ["Nauen", "Poldhu"])

    print("\n-- the totals do not change when a screen filters them --")
    # The filtering is the board's, on the board. What the net reports is the
    # hall as it was played, so two screens cannot disagree about the score.
    everybody = net.people_board()
    check("practice players are in what the net reports",
          any(p["bot"] for p in everybody), True)
    check("  and so are the real ones",
          any(not p["bot"] for p in everybody), True)
    check("the board payload carries them",
          [p["name"] for p in net.board()["people"]],
          [p["name"] for p in everybody])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
