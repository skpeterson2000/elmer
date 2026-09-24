#!/usr/bin/env python3
"""An inverted V is not a dipole hung crooked.

    python3 tests/test_v_feedpoint.py

The lab drew the heights table from a flat half-wave's feedpoint and put it
under a heading that said inverted V. Two places in this program already
said that was wrong - patterns.py, "the droop pulls the feedpoint down to
about 50 ohms", and the Lab's own note, "the droop changes the pattern and
the feedpoint" - and the table went on printing 73 ohms beside them.

Two things move when the legs come down. The free-space resistance falls,
and the wire hangs below its own apex: the pattern follows the
current-weighted mean height, which sits part way out along each sloping
leg. So the heights are the apex, which is what somebody hauls up and can
measure from the ground, and the ohms and the angle belong to the wire,
which is lower.

The free-space figures are a fit through published values - 73 flat, 50 at
45 degrees, 40 at 60 - in the same spirit as radialZ() in the Lab, and the
test holds it to those three.

Nothing here touches the network or the browser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import antenna_advice as A  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the droop brings the free-space feedpoint down --")
    check("flat is the dipole's own figure",
          round(A.v_free_space_ohms(0)), round(A.FREE_SPACE_OHMS))
    check("  45 degrees is near 50, which is why people tie it there",
          round(A.v_free_space_ohms(45)), 50)
    check("  60 degrees near 40", round(A.v_free_space_ohms(60)), 40)
    check("  and it only ever falls",
          all(A.v_free_space_ohms(d) > A.v_free_space_ohms(d + 5)
              for d in range(0, 60, 5)), True)

    print("\n-- and hangs the wire below its own apex --")
    check("flat drops nothing", A.v_centroid_drop_wl(0), 0.0)
    check("  35 degrees drops about a twentieth of a wave",
          round(A.v_centroid_drop_wl(35), 2), 0.05)
    lam = A.wavelength_ft(3.535)
    check("  which on 80 m is about fourteen feet",
          round(A.v_centroid_drop_wl(35) * lam), 14)
    check("  so a 50 ft apex is a wire at about 36 ft",
          round(50 - A.v_centroid_drop_wl(35) * lam), 36)

    print("\n-- so the table is the V's, not a dipole's --")
    flat = A.matching_heights(3.535, None, 0)
    vee = A.matching_heights(3.535, None, 35)
    check("the flat wire matches 50 ohms at 45 ft",
          next(r["ft"] for r in flat if r["what"] == "match"), 45)
    check("  the V wants a higher apex for the same thing",
          next(r["ft"] for r in vee if r["what"] == "match") > 45, True)
    check("  because its wire is where the flat one's was",
          round(next(r["wire_ft"] for r in vee if r["what"] == "match")), 55)
    check("  the flat wire's 73 ohm landmark exists",
          any("73 ohms" in r["note"] for r in flat), True)
    check("  and the V has no such height, being 56 ohms at most",
          any("73 ohms" in r["note"] for r in vee), False)
    check("  it names its own instead",
          any("56 ohms" in r["note"] for r in vee), True)

    print("\n-- the angle belongs to the wire, not to the apex --")
    row = next(r for r in vee if r["what"] == "match")
    check("the row carries both heights", row["ft"] > row["wire_ft"], True)
    check("  and the takeoff is worked out at the wire",
          row["takeoff"], round(A.takeoff_deg(row["wire_ft"], 3.535)))

    print("\n-- the curve follows the droop too --")
    c0 = A.height_curve(3.535, top_ft=70, droop_deg=0)
    c35 = A.height_curve(3.535, top_ft=70, droop_deg=35)
    check("a flat wire and a V do not draw the same curve",
          c0[0]["ohms"] == c35[0]["ohms"], False)
    check("  the V's points carry the wire height as well as the apex",
          "wire_ft" in c35[0], True)
    check("  and the apex is the higher of the two",
          c35[0]["ft"] > c35[0]["wire_ft"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
