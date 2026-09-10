#!/usr/bin/env python3
"""A host that runs the hall, and tables that are not there.

    python3 tests/test_hall.py

Two things are checked, and they are the two that decide whether an evening
works.

A round starts because a table reported it has people at it, not because a
clock went off.  A timer firing into an empty hall starts a game nobody is
playing; one that has not fired yet holds up a room that is ready.  Check-in
already carries the count, so the host is told rather than guessing.

And a person arriving takes a machine's place.  Simulated tables let a hall be
seen working before there is a hall, which is what an instructor setting up an
evening needs - but the moment a real unit checks in, one of them stands down.

The flag travels with them everywhere the code can see it, and that is what is
tested here.  Whether a screen draws it is the screen's business - the big
board deliberately does not - but displacement depends on it, the host's panel
shows it, and a name somebody adopts has to be known to have been free.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import hall, netcontrol  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def asker(net, seconds=1.0):
    """Somewhere to keep count of the questions this hall was asked."""
    asked = []

    def ask():
        asked.append(len(asked) + 1)
        net.start_round("technician", f"T{len(asked):03d}", 0,
                        {"text": f"question {len(asked)}",
                         "choices": ["a", "b", "c", "d"]}, seconds=seconds)
    ask.asked = asked
    return ask


def wait_until(what, seconds=25.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if what():
            return True
        time.sleep(0.1)
    return False


print("\na hall with nobody in it is not waiting on a clock, it is empty")
net = netcontrol.Net()
ask = asker(net)
conductor = hall.start(net, ask, reveal=0.5)
time.sleep(1.0)
check("no round was started", len(ask.asked), 0)
check("and it says what it is short of", conductor.waiting_for(),
      "waiting for a table with somebody at it")
check("which is not an error", conductor.as_dict()["state"], "waiting")

print("\na table checking in empty is present, but is not a game")
net.check_in("bench-1", "Bench", players=0)
time.sleep(0.8)
check("still nothing asked", len(ask.asked), 0)
check("though the table is counted", net.health()["units"], 1)

print("\nsomebody sits down, and that is what starts it")
net.check_in("bench-1", "Bench", players=3)
check("a round went up", wait_until(lambda: len(ask.asked) >= 1, 5.0), True)
check("the hall knows it is under way", conductor.waiting_for(), None)
hall.halt()

print("\nsimulated tables fill a hall that has none, and play")
net = netcontrol.Net()
made = net.add_simulated(3)
check("three stood up", len(made), 3)
check("named for stations, not people",
      all(u.name in netcontrol.SIMULATED_NAMES for u in made), True)
check("and they are seated", net.health()["ready"], 3)

ask = asker(net)
conductor = hall.start(net, ask, reveal=0.3)
check("the hall started itself", wait_until(lambda: len(ask.asked) >= 1, 5.0),
      True)
check("a round closed and was scored",
      wait_until(lambda: conductor.played >= 1, 12.0), True)
# everyone_reported() is only true while the round is still open, and the
# conductor closes it the instant it becomes true - so what is asked for here
# is what the closed round recorded, which is the part that lasts.
last = net.history[-1] if net.history else {}
check("all three handed answers in", last.get("units_reported"), 3)
check("and their players are in the count", (last.get("answers") or 0) > 0, True)
scored = [u for u in net.board()["units"] if u["score"] > 0]
check("somebody is winning", bool(scored), True)

print("\nthe flag travels, whatever a screen chooses to draw")
board = net.board()
check("every simulated table is known to be one",
      all(u["simulated"] for u in board["units"]), True)
check("and the count is on the health line", board["health"]["simulated"], 3)

print("\na real table displaces one of them, one for one")
before = len(net.units)
unit, why = net.check_in("real-1", "Kitchen", players=4)
check("the person was admitted", why, None)
check("the hall is the same size", len(net.units), before)
check("one fewer machine", len(net.simulated_units()), 2)
check("and the real one is not flagged", unit.as_dict()["simulated"], False)
check("the weakest stood down, not the leader",
      board["units"][0]["name"] in [u.name for u in net.simulated_units()]
      or board["units"][0]["score"] == 0, True)
hall.halt()

print("\nthe hall's patience follows the clock the tables are showing")
# A fixed grace has to be wrong at one end or the other: shorter than the
# round it closes under the people still answering, and much longer it leaves
# a hall of short rounds stalled on one table that went off the air.
for seconds in (10.0, 30.0, 60.0):
    net3 = netcontrol.Net()
    net3.check_in("gone", "Gone", players=4)     # checks in, never reports
    net3.start_round("technician", "T001", 0,
                     {"text": "q", "choices": ["a", "b"]}, seconds=seconds)
    net3.opened_at -= seconds - 1.0
    check(f"{seconds:.0f}s round: not overdue with a second left",
          net3.overdue(), False)
    net3.opened_at -= (netcontrol.GRACE_AFTER_TIME + 2.0)
    check(f"{seconds:.0f}s round: overdue once the grace is gone",
          net3.overdue(), True)

print("\nnobody is disguised in the round summary either")
net2 = netcontrol.Net()
net2.add_simulated(2)
net2.start_round("technician", "T001", 0,
                 {"text": "q", "choices": ["a", "b"]}, seconds=1.0)
wait_until(lambda: net2.tick_simulated() or net2.everyone_reported(), 6.0)
for _ in range(20):
    net2.tick_simulated()
    if net2.everyone_reported():
        break
    time.sleep(0.2)
summary = net2.close_round() or {}
top = summary.get("top") or []
check("the fastest were recorded", bool(top), True)
check("and every one of them is known to be practice",
      all(r.get("bot") for r in top), True)

print("\nthe hall stops when it is told to")
check("stopped", hall.conductor(), None)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
