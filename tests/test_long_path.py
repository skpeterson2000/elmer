#!/usr/bin/env python3
"""The reach map follows a path the long way round the world.

    python3 tests/test_long_path.py

The map is a flat picture of a globe, and a signal does not stop at its
edge or at the far side of the world: past the antipode it carries on round
the other side, and a place can be reached the long way - off the back of a
beam aimed away from it, across a darker sky. Each cell is now the better of
the short path and the long one, the long one leaving on the opposite
bearing, travelling the rest of the circumference, rated at its own
midpoint and paying for every hop. What is held here:

  - the long way is only ever marked where it is the better path, and never
    for a place near enough that the long way is over seven hops;
  - it is honest about power: 100 W of SSB is not heard 20,000 km away, so
    the long way lights nothing there, where FT8, 28 dB deeper, is;
  - a beam aimed west reaches places to the east the long way round, which
    the same beam aimed east does not need to;
  - the marks are on cells that are lit, and the answer counts them.
"""
import sys
from datetime import datetime, timezone
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
    from elmer import propagation as P
    from elmer.geo import great_circle
    snap = {"sfi": 150.0, "k_index": 1.0, "hmf2": 300.0, "muf": 28.0, "fof2": 8.0, "muf_source": "test",
            "calibration": {"factor": 1.0, "m3000": 3.1}}
    lat, lon = 46.6, -94.31
    when = datetime(2026, 9, 27, 18, 0, tzinfo=timezone.utc)

    def cells_of(m):
        for i in range(m["rows"]):
            for j in range(m["cols"]):
                la, lo = m["lat0"] - i * m["step"], m["lon0"] + j * m["step"]
                k = i * m["cols"] + j
                yield la, lo, m["cells"][k], m["long"][k]

    print("\n-- the long way, only where it is the better path --")
    ssb = P.reach_map(14.0, lat, lon, snap, when=when, step=10)
    ft8 = P.reach_map(14.0, lat, lon, snap, when=when, step=10, emission="ft8")
    check("every cell says whether it is reached the long way", (len(ft8["long"]) == len(ft8["cells"])), True)
    check("  and the answer counts them", ft8["long_cells"], sum(ft8["long"]))
    near = [great_circle(lat, lon, la, lo)[0] for la, lo, _, via in cells_of(ft8) if via]
    check("nothing within 12,000 km is marked long: the long way to it is over seven hops",
          all(km > P.EARTH_CIRCUMFERENCE_KM - P.LONG_PATH_MAX_KM for km in near), True)
    check("  the marks are only on cells that are lit", all(c > 0 for *_, c, via in cells_of(ft8) if via), True)

    print("\n-- honest about power --")
    check("100 W of SSB is not heard the long way round - 20,000 km is past its budget", ssb["long_cells"], 0)
    check("  FT8, 28 dB deeper, is", ft8["long_cells"] > 0, True)

    print("\n-- a beam aimed away from a place reaches it the long way round --")
    west = P.reach_map(14.0, lat, lon, snap, when=when, step=10, emission="ft8",
                       antenna={"kind": "yagi", "height_wl": 0.6, "heading": 270})
    east = P.reach_map(14.0, lat, lon, snap, when=when, step=10, emission="ft8",
                       antenna={"kind": "yagi", "height_wl": 0.6, "heading": 90})

    def long_to_the_east(m):
        return sum(1 for la, lo, c, via in cells_of(m)
                   if via and 45 <= great_circle(lat, lon, la, lo)[1] <= 135)
    check("aimed west, places to the east are reached the long way round", long_to_the_east(west) > 0, True)
    check("  more of them than when it is aimed east, where the short path serves",
          long_to_the_east(west) > long_to_the_east(east), True)


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
