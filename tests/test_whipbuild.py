#!/usr/bin/env python3
"""The loaded vertical that goes on a vehicle, and what it costs you.

    python3 tests/test_whipbuild.py

A short vertical has a radiation resistance of a couple of ohms, and every
other resistance in the circuit is in series with those two ohms and takes its
share of the power in the same proportion. That one fact decides the whole
design, so it is the one tested hardest here.

The numbers are checked against what the bands are actually like rather than
only against each other: 10 m mobile works, 20 m mobile is a few dB down and
perfectly usable, and 80 m mobile is a famously terrible antenna that people
make contacts on anyway. A model that does not reproduce that is wrong however
tidy its algebra.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import whipbuild as w  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\na quarter wave is what it is, and it does not fit on a truck")
check("40 m is about 34 ft", round(w.plan(7.2, 8)["quarter_wave_ft"]), 34)
check("80 m is about 63 ft", round(w.plan(3.9, 8)["quarter_wave_ft"]), 63)

print("\nradiation resistance goes as the square of the height")
tall = w.radiation_resistance(7.2, 8.0)
half = w.radiation_resistance(7.2, 4.0)
check("half the whip radiates a quarter as well",
      round(tall / half, 1), 4.0)
check("and it is a couple of ohms on 40 m, not fifty",
      1.0 < tall < 2.0, True)

print("\nthe bands come out the way the bands actually are")
def eff(mhz, loss=12.0):
    return round(w.efficiency(mhz, 8.0, loss) * 100)
check("10 m mobile works", eff(28.4) > 55, True)
check("20 m mobile is usable", 20 < eff(14.2) < 45, True)
check("40 m mobile is hard", 5 < eff(7.2) < 20, True)
check("80 m mobile is famously awful", eff(3.9) < 6, True)
check("and awful is still only about 15 dB down, which people work",
      -17 < w.db_down(3.9, 8.0, 12.0) < -12, True)

print("\nthe loss is the whole game, which is the point of the module")
# Halving the loss resistance is worth more than anything done to the rod.
better = w.efficiency(7.2, 8.0, 6.0)
worse = w.efficiency(7.2, 8.0, 12.0)
check("halving the loss nearly doubles the radiated power",
      1.7 < better / worse < 2.0, True)
# A foot of extra whip against six ohms of better bonding, on 40 m.
check("and it beats a foot of extra rod",
      better > w.efficiency(7.2, 9.0, 12.0), True)

print("\nthe coil is the size it is because the whip is that short")
p40 = w.plan(7.2, 8.0)
check("40 m wants tens of microhenries", 15 < p40["base_uh"] < 40, True)
check("and tens of turns on a 1.5 in form", 25 < p40["base_turns"] < 70, True)
p10 = w.plan(28.4, 8.0)
check("10 m wants almost nothing", p10["base_uh"] < 1.0, True)
check("centre loading wants more inductance than base",
      p40["centre_uh"] > p40["base_uh"], True)
check("and it sits up the rod, not at the bottom",
      0 < p40["centre_at_ft"] < 8.0, True)

print("\na whip already long enough needs no coil at all")
check("a full quarter wave has nothing to cancel",
      w.base_reactance(28.4, 9.0), 0.0)
check("so no inductance is asked for", w.base_loading_uh(28.4, 9.0), 0.0)

print("\nWheeler's formula, against a coil whose answer is known")
# 1 in radius, 4 in long, 30 turns: L = r^2 N^2 / (9r + 10l) = 900/49 = 18.4 uH
check("solved for turns, it comes back", w.turns_for(900.0 / 49.0, 1.0, 4.0),
      30)
check("nothing silly from nothing", w.turns_for(0, 1.0, 4.0), 0)

print("\nthe build says what it is worth, including when it is not")
check("it names the commercial one",
      "HamStick" in w.COMMERCIAL["what"], True)
# The honest part: this is not a way to save money, and it says so.
check("and says building to save money is a poor trade",
      "poor trade" in w.COMMERCIAL["why_bother_building"], True)
check("the bond comes before the coil, and the rod is last",
      [p["key"] for p in w.PARTS], ["ground", "coil", "where", "rod"])
check("every part says why it matters",
      all(p["matters"] and p["do"] for p in w.PARTS), True)

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
