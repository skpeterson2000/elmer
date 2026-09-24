#!/usr/bin/env python3
"""The heights offered are heights somebody can reach.

    python3 tests/test_reachable_height.py

The lab drew the feedpoint against height from the ground to a full
wavelength and listed every landmark on the way. On 80 m that is two
hundred and seventy-eight feet, so the table offered 276 ft as an ordinary
choice and the graph spent four fifths of its width above anything anybody
builds, squeezing the part that matters into the first inch.

Reported as: start at normal people's heights. Twelve to sixteen feet is
what most get between two supports, and there is no reason to measure
higher than a person in the field can establish. A grain bin, a silo, a
rooftop in Manhattan - those exist, and somebody has them, and they are a
lucky employment rather than a choice this reader has.

So there is one ceiling with nothing said, and it is the project's own
figure for the far edge of what tall trees give. The exceptions are
reached by saying so: the mast site has no ceiling, and a flat's floor
picker puts the tenth storey near a hundred feet.

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
    print("\n-- with nothing said, the ceiling is what trees give --")
    check("no site named", A.reach_for("", None), A.DIPOLE_REACH_FT)
    check("  which is seventy feet", A.DIPOLE_REACH_FT, 70)
    check("  a house and garden is lower", A.reach_for("house"), 35)
    check("  a short garden lower again", A.reach_for("small"), 22)
    check("  and going out portable, lower still", A.reach_for("portable"), 30)

    print("\n-- the exceptions are had by asking for them --")
    check("a mast or tower has no ceiling", A.reach_for("tower"), None)
    check("  a flat with no floor named is not the sky",
          A.reach_for("apartment", None), A.DIPOLE_REACH_FT)
    check("  and the tenth storey is a real height",
          A.reach_for("apartment", 10) > 80, True)

    print("\n-- so the table stops offering what cannot be built --")
    rows = A.matching_heights(3.535, A.reach_for("", None))
    reachable = [r["ft"] for r in rows if r["reachable"]]
    beyond = [r["ft"] for r in rows if not r["reachable"]]
    check("on 80 m, the reachable landmarks", reachable, [45, 60])
    check("  and 276 ft is not one of them", 276 in beyond, True)
    check("  every landmark is still listed, none hidden",
          len(reachable) + len(beyond), len(rows))
    check("  with a tower, they all come back",
          all(r["reachable"] for r in A.matching_heights(3.535, A.reach_for("tower"))), True)

    print("\n-- and the graph is drawn over the range somebody has --")
    plain = A.height_curve(3.535, top_ft=A.reach_for("", None))
    check("80 m, nothing said: it ends near the reach, not at a wavelength",
          plain[-1]["ft"] < 100, True)
    check("  a little above it, so the ground beyond can be seen to be shaded",
          plain[-1]["ft"] > A.DIPOLE_REACH_FT, True)
    check("  it starts at the lowest height worth hanging",
          plain[0]["ft"] >= A.LOWEST_WORTH_HANGING_FT, True)
    small = A.height_curve(3.535, top_ft=A.reach_for("small"))
    check("a short garden gets a curve, not six points",
          len(small) >= 20, True)
    check("  ending at its own ceiling", small[-1]["ft"] < 35, True)
    check("a wire on the car draws at all, low as it is",
          len(A.height_curve(3.535, top_ft=A.reach_for("mobile"))) > 4, True)
    tower = A.height_curve(3.535, top_ft=A.reach_for("tower"))
    check("and a tower still sees the whole wavelength",
          tower[-1]["wavelengths"], 1.0)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
