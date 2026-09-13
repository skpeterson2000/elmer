#!/usr/bin/env python3
"""A fleet imaged from one SD card does not collapse into one table.

    python3 tests/test_clone_identity.py

KC9SP, 2026-09-13: three Pis and a phone, "the game failed with a pretty
light load." Reproduced on one box: two secondary units never appeared at
net control - the board sat at one table while three were playing.

The cause is identity, not load. `cohort.default_unit_id()` is the hostname
plus four characters of the machine-id hash, and a fleet flashed from one
image shares both - so every unit computes the *same* id, and net control
keyed its tables by id, the second overwriting the first. So each running
unit now sends an instance token, and net control gives colliding ids their
own slots and tells the operator to set real hostnames.

What is proved: colliding ids get separate slots; each keeps its slot and
its score across check-ins and reports; the token, not the address, is what
tells them apart (two clones can share an address); and a genuinely distinct
unit is left alone.
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


CLONE = "raspberrypi-0000"

print("\nthree clones, one claimed id, three tables")
net = netcontrol.Net(difficulty="technician")
# Same address on purpose: two units on one switch, or two processes on one
# box, can present the same source - the token is what must carry the day.
a, _ = net.check_in(CLONE, name="raspberrypi", players=3, instance="aaaa", address="10.0.0.9")
b, _ = net.check_in(CLONE, name="raspberrypi", players=4, instance="bbbb", address="10.0.0.9")
c, _ = net.check_in(CLONE, name="raspberrypi", players=2, instance="cccc", address="10.0.0.9")
check("three slots, not one", len(net.units), 3)
check("  the first keeps the bare id", a.id, CLONE)
check("  the others are disambiguated", sorted([b.id, c.id]),
      [CLONE + "#2", CLONE + "#3"])
check("  named so a board can tell them apart",
      sorted(u.name for u in net.units.values()),
      ["raspberrypi", "raspberrypi (2)", "raspberrypi (3)"])
check("  and the copies are flagged", sum(u.cloned for u in net.units.values()), 2)
check("  all three are ready to be counted",
      net.health()["units"], 3)

print("\neach reports to its own slot, and scores on its own")
net.start_round("technician", "T001", 0,
                {"text": "q", "choices": ["w", "x", "y", "z"]}, seconds=30)
net.report(CLONE, net.round_number, [{"name": "Ann", "correct": True, "ms": 700}],
           instance="aaaa", address="10.0.0.9")
net.report(CLONE, net.round_number, [{"name": "Bo", "correct": True, "ms": 900}],
           instance="bbbb", address="10.0.0.9")
net.report(CLONE, net.round_number, [{"name": "Cy", "correct": False, "ms": 1500}],
           instance="cccc", address="10.0.0.9")
check("three separate reports landed", sorted(net.results.keys()),
      [CLONE, CLONE + "#2", CLONE + "#3"])
check("  the hall saw everyone report", net.everyone_reported(), True)
summary = net.close_round()
check("  three tables in the summary", summary["units_reported"], 3)
scored = {u.name: u.score for u in net.units.values()}
check("  the two who were right scored", sum(1 for v in scored.values() if v > 0), 2)
check("  the one who missed did not", scored["raspberrypi (3)"], 0)

print("\na clone keeps its slot across check-ins - no new table each second")
before = len(net.units)
again, _ = net.check_in(CLONE, players=4, instance="bbbb", address="10.0.0.9")
check("still three", len(net.units), before)
check("  and it is the same slot", again.id, CLONE + "#2")

print("\na genuinely distinct unit is left alone")
d, _ = net.check_in("shack-pi-77ab", name="shack", players=5,
                    instance="dddd", address="10.0.0.10")
check("its own id, untouched", d.id, "shack-pi-77ab")
check("  and not flagged a clone", d.cloned, False)

print("\nwithout a token, the address still tells two apart")
net2 = netcontrol.Net(difficulty="general")
p, _ = net2.check_in("pi", name="pi", players=2, address="10.0.0.20")
q, _ = net2.check_in("pi", name="pi", players=2, address="10.0.0.21")
check("two addresses, two slots", len({p.id, q.id}), 2)
r, _ = net2.check_in("pi", name="pi", players=2, address="10.0.0.20")
check("  and the first address keeps its slot", r.id, p.id)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
