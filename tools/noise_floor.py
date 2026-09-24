#!/usr/bin/env python3
"""What the bands sound like, according to the link budget.

    python3 tools/noise_floor.py
    python3 tools/noise_floor.py --site quiet --winter
    python3 tools/noise_floor.py --compare        # with and without the sky's own noise

The noise floor decides everything downstream - what "solid" means on the
reach map, what Make Contact will promise, how much power the band plan says
a path wants. It is also the one number in here an operator can check against
their own receiver in ten seconds, which is why this prints it in S-units as
well as dBm.

If these do not match what you hear, the constants to move are
ATMOSPHERIC_NIGHT and ATMOSPHERIC_DAY in elmer/linkbudget.py. They are a
straight line fitted to the shape of ITU-R P.372's atmospheric maps for a
mid-latitude station, not the maps themselves, and they are meant to be
argued with.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import linkbudget  # noqa: E402

BANDS = [("160 m", 1.9), ("80 m", 3.7), ("60 m", 5.35), ("40 m", 7.15),
         ("30 m", 10.12), ("20 m", 14.2), ("17 m", 18.1), ("15 m", 21.2),
         ("12 m", 24.9), ("10 m", 28.5)]


def s_units(dbm):
    """S9 is -73 dBm on HF and an S-unit is 6 dB. Over S9 it is said in dB
    over, the way a signal report is."""
    over = dbm - (-73.0)
    if over >= 0:
        return f"S9+{over:.0f}"
    s = 9.0 + over / 6.0
    return f"S{max(0.0, s):.0f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--site", default="residential",
                    choices=["quiet", "rural", "residential", "city"])
    ap.add_argument("--mode", default="ssb")
    ap.add_argument("--winter", action="store_true", help="the quiet half of the year")
    ap.add_argument("--compare", action="store_true",
                    help="show what it was before the sky's own noise was counted")
    args = ap.parse_args(argv)

    when = datetime(2026, 1, 15) if args.winter else datetime(2026, 7, 15)
    season = "winter" if args.winter else "summer"
    band_w = linkbudget.groundwave.mode_of(args.mode)["bandwidth_hz"]

    print(f"\nnoise floor, {args.site} site, {args.mode.upper()} "
          f"({band_w:.0f} Hz), {season}\n")
    head = f"  {'band':<7} {'MHz':>6}   {'night':>16}   {'day':>16}"
    if args.compare:
        head += f"   {'man-made only':>16}"
    print(head)
    for name, mhz in BANDS:
        night = linkbudget.noise_floor_dbm(mhz, band_w, args.site, sun_deg=-30.0, when=when)
        day = linkbudget.noise_floor_dbm(mhz, band_w, args.site, sun_deg=40.0, when=when)
        row = (f"  {name:<7} {mhz:>6.2f}   {night:>8.1f} dBm {s_units(night):>6}"
               f"   {day:>8.1f} dBm {s_units(day):>6}")
        if args.compare:
            # the floor with the atmospheric term taken out again
            was = linkbudget.noise_floor_dbm(1e9, band_w, args.site)     # never, above 30 MHz
            c, d, _ = linkbudget.groundwave.NOISE_SITES[args.site]
            import math
            fa = c - d * math.log10(max(1.0, mhz))
            ext = 10.0 ** (max(0.0, fa) / 10.0) + 10.0 ** (linkbudget.NOISE_FIGURE_DB / 10.0)
            was = -174.0 + 10.0 * math.log10(band_w) + 10.0 * math.log10(ext)
            row += f"   {was:>8.1f} dBm {s_units(was):>6}"
        print(row)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
