#!/usr/bin/env python3
"""Golf's launch speeds and notches are solved in a handful of flights, to the
same answers, and the club yardages are worked out when something moves.

    python3 tests/test_golf_solve.py

A club's launch speed is the one that carries it the bag's length on a calm
day, and the meter's notch is the swing that carries it to the mark. Both
were found by halving a bracket - forty flights for a launch speed, eighteen
for a notch - and a golfer moving the spin slider paid forty flights for
each of eleven clubs, on the unit, before the picker could show its yards.
On a Pi that is most of a second. What is held here:

  - every club, at every spin and shape, still carries the bag's length on
    a calm day, to a millimeter, and its launch speed is the one the halving
    found;
  - a cold launch speed takes no more than 12 flights, and a notch no more
    than 12;
  - a notch carries the ball to its mark and the thousandth below it does
    not: it is the first swing that gets there;
  - club_yards gives what plays() gives, keeps it while nothing moves, and
    works it out again when the lie, the set-up or the wind does.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import golf

    flights = [0]
    real_fly = golf._fly

    def counting(*a, **k):
        flights[0] += 1
        return real_fly(*a, **k)
    golf._fly = counting

    def halving(club, spin_q, shape_q):
        """The forty halvings the launch speed used to take, as a reference."""
        angle, rpm = golf.LAUNCH[club]
        rpm *= golf._spin_mult(spin_q)
        want = golf.CLUBS[club] * golf.YARD
        lo, hi = 5.0, 120.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if real_fly(mid, angle, rpm, tilt_deg=golf.SHAPE_TILT * shape_q)[0] < want:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    print("\n-- the launch speed: the bag's length, in a handful of flights --")
    golf._launch_speed.cache_clear()
    golf._flight.cache_clear()
    worst_carry, worst_speed, most = 0.0, 0.0, 0
    for club in golf.LAUNCH:
        for spin in (None, 0.0, 0.5, 1.0):
            for shape in (-1.0, 0.0, 1.0):
                flights[0] = 0
                v = golf._launch_speed(club, spin, shape)
                most = max(most, flights[0])
                angle, rpm = golf.LAUNCH[club]
                carry = real_fly(v, angle, rpm * golf._spin_mult(spin), tilt_deg=golf.SHAPE_TILT * shape)[0]
                worst_carry = max(worst_carry, abs(carry - golf.CLUBS[club] * golf.YARD))
                if spin in (None, 1.0) and shape == 0.0:
                    worst_speed = max(worst_speed, abs(v - halving(club, spin, shape)))
    print(f"     worst carry miss {worst_carry * 1000:.3f} mm; worst speed against the halving "
          f"{worst_speed:.1e} m/s; most flights for one {most}")
    check("every club at every spin and shape carries the bag's length to a millimeter",
          worst_carry < 0.001, True)
    check("  at the launch speed the forty halvings found, within 0.001 m/s", worst_speed < 0.001, True)
    check("  and no solve took more than 12 flights", most <= 12, True)

    print("\n-- the notch: the first swing that gets there --")
    golf._flight.cache_clear()
    short, first, most, n = 0, 0, 0, 0
    for club in golf.LAUNCH:
        for share in (0.2, 0.45, 0.7, 0.9, 0.99):
            for hour, mph in ((None, 0.0), (0, 12.0), (6, 12.0), (3, 20.0)):
                want = golf.CLUBS[club] * share
                golf._flight.cache_clear()
                golf.flight(club, 1.0, hour, mph)          # the full swing, which the notch starts from
                flights[0] = 0
                f = golf.swing_for(club, want, hour, mph)
                most = max(most, flights[0])
                if f > 1.0:
                    continue
                n += 1
                short += golf.flight(club, f, hour, mph)["carry"] < want
                below = round(f, 3) - 0.001
                first += below < 0.05 or golf.flight(club, below, hour, mph)["carry"] < want
    print(f"     {n} notches; most flights for one {most}")
    check("no notch carries short of its mark", short, 0)
    check("  and the thousandth below each one does", first, n)
    check("  and none took more than 12 flights", most <= 12, True)
    check("a mark past the full swing says so", golf.swing_for("sand-wedge", 400.0) > 1.0, True)
    check("a mark at nothing is the least swing", golf.swing_for("7-iron", 0.0), 0.05)
    golf._fly = real_fly

    print("\n-- club_yards: worked out when something moves --")
    # One hole with a breeze into it, so the wind has something to change.
    course = {"id": "flat", "name": "Flat", "pool": "technician", "par": 4,
              "wind": {"typical_mph": 12},
              "holes": [{"n": 1, "par": 4, "yards": 400, "name": "", "wind": "into",
                         "green": 30, "hazards": []}]}
    g = golf.Golf(["ann", "bob"], course, seed=7, seconds=30)
    calls = [0]
    real_plays = g.plays

    def counting_plays(*a, **k):
        calls[0] += 1
        return real_plays(*a, **k)
    g.plays = counting_plays
    direct = {c: int(round(real_plays("ann", c))) for c in g.clubs_for("ann") if c != "putter"}
    first_yards = g.club_yards("ann")
    check("club_yards gives what plays() gives", first_yards, direct)
    g.club_yards("bob")
    before = calls[0]
    g.club_yards("ann")
    g.as_dict()
    g.as_dict()
    check("  and a second read, and two reads of the table's state, work nothing out again",
          calls[0] - before, 0)
    before = calls[0]
    g.set_setup("ann", shape=1.0, spin=1.0)
    g.club_yards("ann")
    check("a new set-up works her yards out again", calls[0] - before, len(direct))
    before = calls[0]
    g.wind_mph = float(g.wind_mph or 0) + 5
    g.club_yards("ann")
    check("  and so does the wind", calls[0] - before, len(direct))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
