#!/usr/bin/env python3
"""NVIS is a height, not a setting.

    python3 tests/test_nvis_height.py

An inverted V at 35 feet is an eighth of a wavelength up on 80 m and puts
its whole lobe straight overhead. The operator has no say in that: it is an
NVIS antenna, and the only thing that would change it is climbing. The same
wire is a wavelength up on 10 m and is a DX antenna. One wire, three bands,
three different antennas - which is the whole reason the ground reflection
is modelled at all, so somebody setting up a first station can read it off
a page instead of finding it out over a season.

So the band plan's switch has to follow the height and the band rather than
sit there as a mode somebody picked, and the page has to name the height
that would change it. This checks the facts that sit under that.

Nothing here touches the network or the browser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import antenna_advice as aa  # noqa: E402
from elmer import patterns, propagation  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def wl(ft, mhz):
    return ft / aa.wavelength_ft(mhz)


def main():
    print("\n-- one wire at 35 feet, read on three bands --")
    check("80 m: an eighth of a wave up, and an NVIS antenna",
          patterns.is_nvis("invertedv", wl(35, 3.7), mhz=3.7), True)
    check("  40 m: a quarter wave up, still one",
          patterns.is_nvis("invertedv", wl(35, 7.15), mhz=7.15), True)
    check("  10 m: a wavelength up, and not one",
          patterns.is_nvis("invertedv", wl(35, 28.5), mhz=28.5), False)
    check("  the lobe on 80 m is straight up",
          patterns.height_gains("invertedv", wl(35, 3.7), mhz=3.7)["best_deg"], 90)

    print("\n-- and the height that would change it is nameable --")
    low = patterns.low_angle_height_wl("invertedv", mhz=3.7)
    check("80 m: the lobe leaves the zenith somewhere above a quarter wave",
          0.2 < low < 0.5, True)
    check("  which is higher than the wire is now", low > wl(35, 3.7), True)
    check("  and the antenna is not NVIS once it is there",
          patterns.is_nvis("invertedv", low, mhz=3.7), False)
    check("  while just below it, it still is",
          patterns.is_nvis("invertedv", low - 0.02, mhz=3.7), True)

    print("\n-- a vertical is never an NVIS antenna, at any height --")
    check("ground mounted", patterns.is_nvis("quarter", 0.0, mhz=3.7), False)
    check("  and up in the air", patterns.is_nvis("quarter", 0.3, mhz=3.7), False)

    print("\n-- the map says all of it, in feet as well as wavelengths --")
    snap = {"ok": True, "sfi": 120.0, "k_index": 2.0, "hmf2": 300.0,
            "fof2": 6.0, "calibration": {}}
    d = propagation.reach_map(3.7, 46.358, -94.201, snap, step=10.0, watts=100.0,
                              antenna={"kind": "invertedv", "height_wl": wl(35, 3.7)})
    a = d["antenna"]
    # The page prints "This antenna at N ft"; N came from a key the payload
    # did not carry, so it read "at 0 ft" for as long as the line existed.
    check("the height in feet is there at all", a.get("height_ft") is not None, True)
    check("  and it is the height that went in", round(a["height_ft"]), 35)
    check("  it says this is an NVIS antenna", a["nvis"], True)
    # 69 ft on 80 m, as it happens: a quarter wave and a bit. The bound is
    # loose on purpose - the exact figure moves with the ground model, and
    # what matters is that it is well above the wire and reachable.
    check("  names the height that would change it",
          a["height_ft"] < a["low_angle_ft"] < 140, True)
    check("  and the ideal NVIS height, which is lower",
          a["nvis_ft"] < a["low_angle_ft"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
