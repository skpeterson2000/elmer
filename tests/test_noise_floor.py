#!/usr/bin/env python3
"""The sky's own noise, and what it does to the floor.

    python3 tests/test_noise_floor.py

The link budget counted the receiver's own noise and the man-made noise of
the street it stands in, both from ITU-R P.372, and stopped there. It left
out the lightning - which on the low bands is the one that decides, and
which is the whole reason a rural station does not hear 80 m at S4 on a
summer night however far it is from a power line.

What is checked here is the shape rather than the exact figures, because
the figures are a straight line fitted to P.372's atmospheric maps for a
mid-latitude station and are meant to be argued with. The shape is not:
noise falls with frequency, night is worse than day, winter is quieter
than summer, a quiet site is dominated by it and a city site is not, and
above 30 MHz there is none of it because the storms are below the horizon.

Nothing here touches the network or the browser.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import linkbudget  # noqa: E402

FAILS = []
SSB = 2400.0
SUMMER, WINTER = datetime(2026, 7, 15), datetime(2026, 1, 15)
NIGHT, DAY = -30.0, 40.0


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def floor(mhz, site="quiet", sun=NIGHT, when=SUMMER):
    return linkbudget.noise_floor_dbm(mhz, SSB, site, sun_deg=sun, when=when)


def main():
    print("\n-- the sky's noise falls away as the frequency rises --")
    fa = [round(linkbudget.atmospheric_fa(f, NIGHT, SUMMER)) for f in (1.9, 3.7, 7.15, 14.2, 28.5)]
    check("160, 80, 40, 20, 10 m", fa, sorted(fa, reverse=True))
    check("  160 m carries more of it than 10 m", fa[0] > fa[-1] + 30, True)

    print("\n-- night is the noisy half, and summer the noisy season --")
    check("80 m is noisier after dark",
          round(floor(3.7, sun=NIGHT) - floor(3.7, sun=DAY)) > 5, True)
    check("  and noisier in summer than in winter",
          round(floor(3.7, when=SUMMER) - floor(3.7, when=WINTER)) > 5, True)
    check("  an unknown hour takes the middle, not the worst",
          floor(3.7, sun=DAY) < floor(3.7, sun=None) < floor(3.7, sun=NIGHT), True)

    print("\n-- you cannot get away from lightning by leaving town --")
    quiet_80 = floor(3.7, "quiet")
    city_80 = floor(3.7, "city")
    check("a quiet site is within 15 dB of a city one on 80 m at night",
          round(city_80 - quiet_80) < 15, True)
    # the old floor, man-made and receiver only, is what tools/noise_floor.py
    # prints in its --compare column
    import math
    c, d, _ = linkbudget.groundwave.NOISE_SITES["quiet"]
    fa_man = c - d * math.log10(3.7)
    ext = 10 ** (fa_man / 10.0) + 10 ** (linkbudget.NOISE_FIGURE_DB / 10.0)
    was = -174.0 + 10 * math.log10(SSB) + 10 * math.log10(ext)
    check("  and it is a lot noisier than it used to be told it was",
          round(quiet_80 - was) >= 10, True)

    print("\n-- in town the power lines still win --")
    city_was_ext = 10 ** ((linkbudget.groundwave.NOISE_SITES["city"][0]
                           - linkbudget.groundwave.NOISE_SITES["city"][1] * math.log10(3.7)) / 10.0)
    city_was = -174.0 + 10 * math.log10(SSB) + 10 * math.log10(
        city_was_ext + 10 ** (linkbudget.NOISE_FIGURE_DB / 10.0))
    check("a city site on 80 m barely moves", round(city_80 - city_was) <= 3, True)

    print("\n-- above 30 MHz the storms are below the horizon --")
    check("2 m has no atmospheric term",
          floor(144.0, sun=NIGHT) == linkbudget.noise_floor_dbm(144.0, SSB, "quiet"), True)
    check("  and 10 m, just under the line, still has some",
          floor(28.5, sun=NIGHT) > linkbudget.noise_floor_dbm(1e9, SSB, "quiet"), True)

    print("\n-- it reaches what asks the budget a question --")
    from elmer import propagation

    def margin(site, sun):
        return propagation.sky_budget(3.7, 800.0, 1, 100.0, "ssb", elevation=-20.0,
                                      site=site, noise_sun_deg=sun,
                                      when=SUMMER)["margin_db"]
    check("the same 80 m path is worth less into a dark quiet receiver",
          round(margin("quiet", DAY) - margin("quiet", NIGHT)) > 5, True)
    # And in town it is not, which is the same fact from the other side: the
    # street's own noise is already louder than the weather, so the hour of
    # the day barely moves the floor. A test that only looked at a quiet site
    # would pass just as well with the site forgotten altogether.
    check("  but in town the hour hardly matters",
          round(margin("city", DAY) - margin("city", NIGHT)) <= 2, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
