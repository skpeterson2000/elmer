#!/usr/bin/env python3
"""Checks for the ground wave - the part of the signal that never leaves.

    python3 tests/test_groundwave.py

Two things are being tested. That the physics comes out where the published
curves put it, because a ground-wave range is a number somebody plans a net
around. And that the model knows where it stops being true: Sommerfeld's answer
is for a flat earth, and over sea water - which barely attenuates anything -
nothing in the flat model stops the wave at all. It was claiming a readable
160m signal three thousand miles out, which is a skywave answer arrived at by
accident.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import groundwave as G  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def miles(mhz, ground, watts=100.0):
    km = G.useful_range_km(mhz, watts, ground)
    return None if km is None else km / 1.609


def main():
    print("\n-- against the broadcast curves everybody works from --")
    # 1 MHz, 1 kW, average ground: the published figures are about 20 mV/m at
    # 10 km, 1 at 50 and 0.15 at 100.
    for km, want in ((10, 20.0), (50, 1.0), (100, 0.15)):
        got = 300.0 / km * G.attenuation(km, 1.0)
        check(f"1 MHz over average ground at {km} km is near {want} mV/m",
              0.5 * want < got < 2.0 * want, True)

    print("\n-- the ground is the biggest thing in it --")
    check("sea water beats dry sand by a mile, many times over",
          miles(7.1, "sea") > 4 * miles(7.1, "sand"), True)
    check("wet ground beats average", miles(7.1, "wet") > miles(7.1, "average"), True)
    check("  which beats poor", miles(7.1, "average") > miles(7.1, "poor"), True)
    check("every named ground is usable at 100 W on 80m",
          all(miles(3.6, g) for g in G.GROUND), True)

    print("\n-- and frequency is the next biggest --")
    check("160m reaches further than 40m over the same ground",
          miles(1.9, "average") > miles(7.1, "average"), True)
    check("  which reaches further than 10m",
          miles(7.1, "average") > miles(28.4, "average"), True)
    check("the soil looks less like a conductor the higher you go",
          G.complex_permittivity(28.4)[1] < G.complex_permittivity(1.9)[1], True)

    print("\n-- where the flat earth stops being true --")
    # Over sea the attenuation function is still 0.84 at a thousand km, so
    # curvature is the only thing that ends it.
    check("over sea the ground itself barely attenuates at 300 km",
          G.flat_attenuation(300, 1.9, "sea") > 0.9, True)
    check("  so curvature has to be what stops it",
          G.curvature_loss_db(300, 1.9) > 10, True)
    check("and over land curvature is irrelevant at working range",
          G.curvature_loss_db(60, 3.6) < 0.5, True)
    # The bug this was written after: with curvature removed, the surviving
    # fraction of the wave over sea is still substantial five thousand
    # kilometres out, so nothing ended it and the model said 160m was readable
    # across the Atlantic by ground wave.
    check("a flat-earth model alone would carry a sea path across an ocean",
          G.flat_attenuation(5000, 1.9, "sea") > 0.35, True)
    check("  and with curvature it does not",
          G.attenuation(5000, 1.9, "sea") < 1e-6, True)

    print("\n-- calibrated against the ranges these services are built around --")
    for mhz, want, name in ((1.9, 300, "MF coast station"), (7.1, 150, "40m"),
                            (14.2, 100, "20m")):
        got = miles(mhz, "sea")
        check(f"{name} over sea lands near {want} miles",
              abs(got - want) / want < 0.15, True)

    print("\n-- polarization is the one thing the antenna decides --")
    check("a horizontal antenna has no ground wave to speak of",
          G.useful_range_km(7.1, 100, "average", polarization="horizontal"), None)
    check("  and it is explained as a cancellation, not a loss",
          "cancel" in G.HORIZONTAL_NOTE, True)
    check("  so power does not buy it back",
          G.useful_range_km(7.1, 1500, "average", polarization="horizontal"), None)

    print("\n-- power helps, and helps slowly --")
    # Field goes as the square root of power: four times the power is twice the
    # field, which on a curve this steep is not four times the distance.
    low, high = miles(7.1, "average", 100), miles(7.1, "average", 1500)
    check("fifteen times the power is not fifteen times the range",
          high < 2.0 * low, True)
    check("  but it is more than none", high > low, True)
    print(f"       (100 W reaches {low:.0f} mi, 1500 W reaches {high:.0f} mi)")

    print("\n-- noise decides as much as the transmitter --")
    check("a city site hears less far than a quiet one",
          G.useful_range_km(7.1, 100, "average", site="city")
          < G.useful_range_km(7.1, 100, "average", site="quiet"), True)
    check("CW gets through where SSB does not",
          G.useful_range_km(7.1, 100, "average", mode="cw")
          > G.useful_range_km(7.1, 100, "average", mode="ssb"), True)
    check("  and FT8 further still",
          G.useful_range_km(7.1, 100, "average", mode="ft8")
          > G.useful_range_km(7.1, 100, "average", mode="cw"), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
