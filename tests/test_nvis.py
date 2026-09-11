#!/usr/bin/env python3
"""Checks for the near-vertical-incidence footprint.

    python3 tests/test_nvis.py

NVIS is the one case where the antenna is not what decides the answer. A wire
at twenty feet works the whole county or none of it depending on a number
measured 300 km overhead, and the failure is not a gentle fade: the near
stations the antenna was put up for are the exact ones that disappear. So what
is tested here is the crossing, not the arithmetic either side of it.

Nothing here touches the network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import patterns as P  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    NIGHT, DAY = 330.0, 270.0

    print("\n-- the rule of thumb, when there is nothing better --")
    plain = P.nvis_reach(3.5)
    check("no reading falls back to the 300-mile average", plain["radius_km"], 500)
    check("  and says that is what it is doing", plain["modelled"], False)
    check("  without claiming to know", "works" in plain, False)

    print("\n-- under the critical frequency it works --")
    good = P.nvis_reach(3.5, 4.5, NIGHT)
    check("80m under a 4.5 MHz critical frequency works", good["works"], True)
    check("  with no hole in the middle", "inner_km" in good, False)
    check("  and the headroom is stated", good["headroom_mhz"], 1.0)
    # A daytime layer is lower, so the same 45 degrees lands nearer.
    check("a lower layer gives a smaller footprint",
          P.nvis_reach(3.5, 4.5, DAY)["radius_km"] < good["radius_km"], True)
    check("  and the classic 300 miles is roughly what daylight gives",
          260 < P.nvis_reach(3.5, 4.5, DAY)["radius_km"] / 1.609 < 340, True)

    print("\n-- over it, the middle drops out --")
    # This is the whole point. The rule of thumb cannot say it.
    bad = P.nvis_reach(3.5, 3.2, NIGHT)
    check("80m over a 3.2 MHz critical frequency does not", bad["works"], False)
    check("  and the hole is where the near stations were", bad["skip_km"] > 0, True)
    check("  reported as an inner edge, so nothing is drawn inside it",
          bad["inner_km"], bad["skip_km"])
    check("the hole grows as the critical frequency falls",
          P.nvis_reach(3.5, 2.6, NIGHT)["skip_km"] > bad["skip_km"], True)

    print("\n-- far enough over and the antenna works nothing at all --")
    # Not a degraded NVIS: the steepest ray that still returns already lands
    # past anything a wire at that height can reach.
    hopeless = P.nvis_reach(14.2, 4.5, NIGHT)
    check("20m off an NVIS wire reaches nobody", hopeless["radius_km"], 0)
    check("  and says so rather than drawing a huge ring",
          "no NVIS here" in hopeless["note"], True)
    check("  while 40m at the same hour is already gone too",
          P.nvis_reach(7.1, 4.5, NIGHT)["radius_km"], 0)

    print("\n-- the crossing is where it should be --")
    # Right at foF2 it still works; a whisker over and it does not.
    check("at the critical frequency exactly, it still returns",
          P.nvis_reach(4.5, 4.5, NIGHT)["works"], True)
    check("  and just above it, it does not",
          P.nvis_reach(4.51, 4.5, NIGHT)["works"], False)

    print("\n-- a measured layer is labelled as one --")
    check("a measured height says measured",
          "measured at" in P.nvis_reach(3.5, 4.5, 295.0)["note"], True)
    check("  and an assumed one says assumed",
          "assumed at" in P.nvis_reach(3.5, 4.5, None, day=True)["note"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
