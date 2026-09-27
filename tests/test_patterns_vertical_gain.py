#!/usr/bin/env python3
"""A quarter-wave vertical on the ground is 5.16 dBi over perfect ground, not 8.15.

    python3 tests/test_patterns_vertical_gain.py

The pattern model draws a vertical as a half-wave element and its image,
which is exactly a monopole and its image at the same current. But a
monopole takes half a dipole's feed resistance, so the same power drives it
with more current, and its field against a free-space dipole's is sqrt(2),
not 2: +3.0 dB, not +6.0. The band plan's "what this height buys" printed
+6.0 for every vertical. What is held here:

  - a quarter wave, a 5/8 wave, a ground plane, a whip and a screwdriver
    with the base on the ground read 5.16 dBi over perfect ground, to a
    tenth of a decibel;
  - a vertical up on a mast with its own radials is left as it was: the
    earth images the whole of it, and the heights in between are the
    antenna solver's to settle;
  - the J-pole, a half wave and not a monopole, and every horizontal wire
    are left as they were;
  - the pattern's shape is untouched: the correction is a level, so the
    takeoff angle and the lobe do not move.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
DIPOLE_DBI = 2.15
QUARTER_WAVE_DBI = 5.16        # 10 log10(2 x 1.64): a half-wave dipole into half the sphere


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def dbi(kind, height_wl, mhz=None, ground="perfect"):
    from elmer import patterns
    return patterns.height_gains(kind, height_wl, mhz=mhz, ground=ground)["best_db"] + DIPOLE_DBI


def main():
    from elmer import patterns

    print("\n-- fed against the ground --")
    for kind in ("quarter", "fiveeighth", "groundplane", "whip", "screwdriver"):
        got = dbi(kind, 0.0)
        check(f"{kind} with its base on the ground: 5.16 dBi over perfect ground",
              abs(got - QUARTER_WAVE_DBI) <= 0.1, True)
    check("  and so it is a hair above the ground", abs(dbi("quarter", 0.019) - QUARTER_WAVE_DBI) <= 0.1, True)

    print("\n-- up on a mast, and the antennas that are not monopoles --")
    check("a ground plane a third of a wave up is as it was: 8.15 dBi at the peak",
          round(dbi("groundplane", 0.3), 2), 8.15)
    check("a J-pole on the ground is a half wave, not a monopole, and is as it was",
          round(dbi("jpole", 0.0), 2), 8.15)
    check("a dipole half a wave up is as it was", round(dbi("dipole", 0.5), 2), 8.15)

    print("\n-- a level, not a shape --")
    for mhz, ground in ((None, "perfect"), (7.1, "average"), (3.6, "poor")):
        shape = patterns.elevation("quarter", 0.0, mhz=mhz, ground=ground)
        lobe = max(shape, key=lambda p: p["field"])["deg"]
        raw = patterns.elevation_raw("quarter", 0.0, mhz=mhz, ground=ground)
        check(f"the quarter wave's lobe and shape still come out whole ({ground})",
              (round(max(p["field"] for p in shape), 6), lobe == max(raw, key=lambda p: p["field"])["deg"]),
              (1.0, True))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
