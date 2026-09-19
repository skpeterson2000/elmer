#!/usr/bin/env python3
"""An inverted-V is not a dipole with a different label.

    python3 tests/test_vee_pattern.py

Asked, reasonably: if the two draw the same pattern, what is the inverted-V
for besides fitting in a smaller garden? Most of the answer was already
modelled - the azimuth nulls fill in, the peak gain is a decibel down, the
feedpoint falls from seventy-odd ohms toward fifty, the wire comes out about
five per cent shorter. The part that was not modelled is the part the
question was really about.

The ground reflection that sets the takeoff angle was being computed from
the apex. An inverted-V does not radiate from its apex: the current is
greatest at the centre and falls away down each sloping leg, so the pattern
follows the current-weighted mean height, which sits (pi - 2) / pi of the way
out along a leg. The page has shown that number in its NVIS panel all along,
and antenna_advice.py picks an NVIS apex with it, and the pattern plot never
asked for it - so the droop slider moved the picture of the antenna and the
NVIS figures while the radiation pattern sat perfectly still.

This holds down both halves: that the two antennas differ where they should,
and that the droop reaches the elevation pattern.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import patterns  # noqa: E402

FAILS = []
V_CENTROID = (math.pi - 2) / math.pi


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def peak_deg(kind, height_ft, mhz):
    curve = patterns.elevation(kind, height_ft / (983.571 / mhz))
    return round(max(curve, key=lambda p: p["field"])["deg"])


def effective_ft(apex_ft, mhz, droop_deg):
    """What the V radiates from: the current-weighted mean height."""
    leg = 234.0 / mhz
    return apex_ft - V_CENTROID * leg * math.sin(math.radians(droop_deg))


def main():
    print("\n-- across the compass they already differed --")
    # Off the ends of the wire is where a dipole has its nulls and where a V
    # does not, because its legs no longer lie along one straight line.
    ends = (patterns.field_toward("dipole", 30, 0, 0),
            patterns.field_toward("invertedv", 30, 0, 0))
    check("off the wire's ends the V is the stronger of the two", ends[1] > ends[0] + 0.2, True)
    check("  broadside they are the same, which is where a dipole is at its best",
          (round(patterns.field_toward("dipole", 30, 90, 0), 3),
           round(patterns.field_toward("invertedv", 30, 90, 0), 3)), (1.0, 1.0))

    print("\n-- and now they differ up and down, which is the point of the droop --")
    # Same apex, different droop: the effective height falls and the lobe
    # lifts. Flat is a dipole and must come out as one.
    for mhz, apex in ((14.2, 35), (14.2, 50), (7.1, 50), (7.1, 70)):
        flat = peak_deg("invertedv", effective_ft(apex, mhz, 0), mhz)
        drooped = peak_deg("invertedv", effective_ft(apex, mhz, 35), mhz)
        check(f"{mhz} MHz, {apex} ft apex: 35 degrees of droop lifts the lobe",
              drooped > flat, True)
        check(f"  and at no droop it is the dipole at {apex} ft",
              flat, peak_deg("dipole", apex, mhz))

    print("\n-- the number the page now draws from --")
    check("a 40 m V at 50 ft radiates from 43 ft, not 50",
          round(effective_ft(50, 7.1, 35)), 43)
    check("  which is 54 degrees up rather than 44",
          (peak_deg("invertedv", effective_ft(50, 7.1, 35), 7.1),
           peak_deg("invertedv", 50, 7.1)), (54, 44))
    # Always the same direction: the old reading made the antenna look better
    # for distance than it is.
    worse = [peak_deg("invertedv", effective_ft(a, m, 35), m) >= peak_deg("invertedv", a, m)
             for m, a in ((14.2, 35), (14.2, 50), (7.1, 50), (7.1, 70), (3.6, 50))]
    check("  and the correction never flatters the antenna", worse, [True] * 5)

    print("\n-- the page asks for it --")
    js = (Path(__file__).resolve().parents[1] / "elmer" / "static" / "lab.js").read_text(encoding="utf-8")
    block = js.split("const effHeight =")[1][:200]
    check("the pattern's height is the drooped one, not the apex",
          "vDrop" in block, True)
    check("  and the droop is what makes it", "an-droop" in js.split("const vDrop")[1][:200], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
