#!/usr/bin/env python3
"""Checks for the sextant tool: the sun, the sight, and the fix.

    python3 tests/test_celestial.py

This is the one part of ELMER where being approximately right is not a
teaching-grade compromise but a wrong answer: an arcminute of error is a
nautical mile of position, and somebody using this at all may be using it
because nothing else is working. So the sun is checked against real ephemeris
values, and the fix is checked by inventing sights from a known place and
seeing whether that place comes back.

The reference declinations below came from pyephem (VSOP87). They are written
down rather than computed so that this test needs nothing but the standard
library, the same as the program does.
"""
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import celestial as C  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def utc(y, m, d, h=0, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def main():
    print("\n-- the sun, against a real ephemeris --")
    # Declination in degrees, from pyephem. An arcminute is a nautical mile.
    for (y, m, d, h, mi), want in {
            (2026, 3, 20, 9, 0): -0.0949,
            (2026, 6, 21, 12, 0): 23.4379,
            (2026, 9, 23, 0, 0): 0.0014,
            (2026, 12, 21, 18, 0): -23.4374}.items():
        got = C.sun_position(utc(y, m, d, h, mi))["dec"]
        check(f"declination on {y}-{m:02d}-{d:02d} is within half an arcminute",
              abs(got - want) * 60 < 0.5, True)
    alt, _ = C.altitude_azimuth(46.6, -94.3, utc(2026, 6, 21, 18, 0))
    check("and an altitude at a known place, within an arcminute",
          abs(alt - 66.5207) * 60 < 1.0, True)

    print("\n-- Julian day --")
    check("J2000 is noon on 2000-01-01", C.julian_day(utc(2000, 1, 1, 12)),
          2451545.0)
    check("  and a day later is one more",
          C.julian_day(utc(2000, 1, 2, 12)) - C.julian_day(utc(2000, 1, 1, 12)),
          1.0)

    print("\n-- working a sight up --")
    when = utc(2026, 6, 21, 18, 0)
    plain = C.reduce_sight(45.0, when)["ho"]
    # Each correction has to move the answer the way the physics moves it.
    check("dip pulls the altitude down",
          C.reduce_sight(45.0, when, height_ft=25)["ho"] < plain, True)
    check("  and further from higher up",
          C.reduce_sight(45.0, when, height_ft=100)["ho"]
          < C.reduce_sight(45.0, when, height_ft=25)["ho"], True)
    check("the lower limb reads low, so the correction is up",
          C.reduce_sight(45.0, when, limb="lower")["ho"]
          > C.reduce_sight(45.0, when, limb="upper")["ho"], True)
    check("refraction bites hardest near the horizon",
          C.refraction_arcmin(2.0) > 5 * C.refraction_arcmin(45.0), True)
    check("  and is small overhead", C.refraction_arcmin(80.0) < 0.3, True)
    # An artificial horizon is how anybody inland takes a sight at all.
    doubled = C.reduce_sight(90.0, when, horizon="artificial")["ho"]
    check("an artificial horizon halves the reading",
          abs(doubled - 45.0) < 0.5, True)
    check("  and takes no dip, because there is no horizon in it",
          C.reduce_sight(90.0, when, horizon="artificial", height_ft=100)["ho"],
          C.reduce_sight(90.0, when, horizon="artificial", height_ft=0)["ho"])
    check("every step of the working is shown",
          len(C.reduce_sight(45.0, when, height_ft=9,
                             index_error_arcmin=-2)["steps"]) >= 5, True)

    print("\n-- a stick and its shadow, for people with no sextant --")
    # altitude = atan(height / shadow). No instrument, so no instrument error.
    check("a stick as tall as its shadow is the sun at 45 degrees",
          round(C.altitude_from_shadow(1.0, 1.0), 6), 45.0)
    check("  a long shadow means a low sun",
          C.altitude_from_shadow(1.0, 3.0) < C.altitude_from_shadow(1.0, 1.0), True)
    check("  and only the ratio matters, not the size of the stick",
          C.altitude_from_shadow(2.0, 3.0), C.altitude_from_shadow(4.0, 6.0))
    check("nothing sensible comes of a stick with no height",
          C.altitude_from_shadow(0, 3.0), None)
    stick = C.reduce_sight(50.0, utc(2026, 6, 21, 18), horizon="shadow")
    check("a shadow takes no dip and no semi-diameter",
          any("none" in why for _, _, why in stick["steps"]), True)
    # It is worse than a sextant, and it has to say so - a stick sight dressed
    # up with a sextant's confidence is the one way this tool could mislead.
    check("a shadow sight knows it is worse than a sextant",
          stick["sigma_arcmin"] > 5 * C.SIGHT_SIGMA_ARCMIN, True)
    check("  and is at its best with the sun low, unlike a sextant",
          C.shadow_sigma_arcmin(20) < C.shadow_sigma_arcmin(70), True)

    print("\n-- finding a place that was not given --")
    # Invent sights from a known position and see whether it comes back. No
    # assumed position is passed: the solver sweeps the whole earth.
    home = (46.5984, -94.3154)
    base = utc(2026, 6, 21, 16, 0)

    def sights(count, gap_min, noise=None):
        out = []
        for i in range(count):
            w = base + timedelta(minutes=gap_min * i)
            alt, _ = C.altitude_azimuth(home[0], home[1], w)
            if noise:
                alt += noise[i] / 60.0
            out.append({"ho": alt, "when": w})
        return out

    got = C.fix(sights(3, 45))
    check("three sights find it to within a tenth of a mile",
          C._separation_nm(home[0], home[1], got["lat"], got["lon"]) < 0.1, True)
    check("  and say the fit is good", got["rms_arcmin"] < 0.1, True)
    check("one sight is a circle, not a place", C.fix(sights(1, 45))["ok"], False)

    print("\n-- two sights of one body are genuinely ambiguous --")
    # Two circles cross twice and both fit perfectly. Guessing silently here
    # would be the worst thing this tool could do.
    two = C.fix(sights(2, 60))
    check("it says so rather than picking one", two["ambiguous"], True)
    check("  and offers the other place", len(two["alternatives"]) >= 1, True)
    check("a rough idea of where you are settles it",
          C._separation_nm(home[0], home[1],
                           *(lambda f: (f["lat"], f["lon"]))(
                               C.fix(sights(2, 60), hint=(45.0, -95.0)))) < 0.1,
          True)
    check("  and so does a third sight", C.fix(sights(3, 45))["ambiguous"], False)

    print("\n-- geometry is reported, because it decides the error --")
    # Sights close together in time share a bearing, cross at a shallow angle,
    # and turn a small error in the sight into a large one in the position.
    tight, wide = C.fix(sights(3, 12)), C.fix(sights(3, 60))
    check("sights taken close together are flagged as poor",
          tight["geometry"], "poor")
    check("  and spread ones are not", wide["geometry"] in ("usable", "good"),
          True)
    # That rating has to earn its place. One sight out by two arcminutes - the
    # ordinary way a sight goes wrong - and the crossing angle decides how far
    # that pushes the answer.
    bad = [2.0, 0.0, 0.0]
    near = C._separation_nm(home[0], home[1],
                            *(lambda f: (f["lat"], f["lon"]))(
                                C.fix(sights(3, 12, bad))))
    far = C._separation_nm(home[0], home[1],
                           *(lambda f: (f["lat"], f["lon"]))(
                               C.fix(sights(3, 60, bad))))
    check("one bad sight costs several times more on tight geometry",
          near > 3 * far, True)
    print(f"       (one sight out by 2': {near:.1f} nm on tight sights, "
          f"{far:.1f} nm on spread ones)")

    print("\n-- and the residual is not the safety check --")
    # This is the trap. Two unknowns and three sights taken minutes apart can
    # agree beautifully with each other and with the wrong place. Anything
    # reporting that residual as a quality score would be lying to somebody who
    # may be lost.
    trap = C.fix(sights(3, 12, [0.0, 2.0, 0.0]))
    off = C._separation_nm(home[0], home[1], trap["lat"], trap["lon"])
    check("a badly wrong fix can still show a tiny residual",
          trap["rms_arcmin"] < 1.0 and off > 100, True)
    check("  so the uncertainty comes from the geometry instead",
          trap["uncertainty_nm"] > 5, True)
    check("  and the ambiguity is flagged", trap["ambiguous"], True)
    print(f"       (out by {off:.0f} nm, residual {trap['rms_arcmin']:.2f}', "
          f"uncertainty +/-{trap['uncertainty_nm']} nm)")
    check("spread sights are reported as more certain than tight ones",
          C.fix(sights(3, 120))["uncertainty_nm"]
          < C.fix(sights(3, 12))["uncertainty_nm"], True)

    print("\n-- the moon, against Meeus example 47.a --")
    # 1992 April 12, 0h TD: apparent RA 134.688470, Dec 13.768368, distance
    # 368409.7 km. The low-precision series is promised to a third of a
    # degree and a few hundred kilometers, and that is what it delivers.
    moon = C.moon_position(datetime(1992, 4, 12, 0, 0, tzinfo=timezone.utc))
    check("right ascension within 0.2 degrees", abs(moon["ra"] - 134.688) < 0.2, True)
    check("declination within 0.2 degrees", abs(moon["dec"] - 13.768) < 0.2, True)
    check("distance within half a percent", abs(moon["distance_km"] / 368409.7 - 1) < 0.005, True)
    print(f"       (RA {moon['ra']:.2f}, Dec {moon['dec']:.2f}, {moon['distance_km']:.0f} km)")
    # A full moon in 2026 (May 31, 08:45 UTC per the almanacs) is opposite
    # the sun; the phase must say so.
    full = C.moon_phase(datetime(2026, 5, 31, 8, 45, tzinfo=timezone.utc))
    check("a known full moon is called full", full["name"], "full")
    check("  and is lit", full["lit"] > 0.98, True)
    new = C.moon_phase(datetime(2026, 6, 15, 2, 54, tzinfo=timezone.utc))
    check("a known new moon is called new", new["name"], "new")

    print("\n-- the moon from a place --")
    home = (46.66, -94.34)
    when = datetime(2026, 9, 15, 19, 0, tzinfo=timezone.utc)
    look = C.eme_outlook(*home, when)
    check("the outlook says up or down and why", look["verdict"] in ("good", "fair", "poor", "down"), True)
    check("  with reasons in words", len(look["reasons"]) >= 1, True)
    check("  a rise and a set within thirty hours", bool(look["rise"] and look["set"]), True)
    check("  the loss is within 2 dB of the average either way", abs(look["loss_db"]) < 2.0, True)
    # rise and set bracket "up": if the moon is up now, the set comes first
    rise, sett = (datetime.fromisoformat(look[k]) for k in ("rise", "set"))
    check("  the next event is the right one for the state", (sett < rise) == look["up"], True)
    track = C.moon_track(when, hours=24, step_minutes=15)
    check("a day's track at a quarter hour is 97 samples", len(track), 97)
    check("  each carries the moon and the sun",
          all(k in track[0] for k in ("gha", "dec", "distance_km", "sun_gha", "sun_dec")), True)
    # the antipode never shares a window with home; a neighbour always does
    anti = (-home[0], home[1] + 180)
    check("no common window with the antipode", C.common_window(*home, *anti, when, hours=24), [])
    near = C.common_window(*home, home[0] + 1, home[1] + 1, when, hours=24)
    check("a neighbour shares the whole moon-up span", len(near) >= 1, True)
    spans = [(b - a).total_seconds() / 3600 for a, b in near]
    check("  and a moon-up span is hours long", max(spans) > 6, True)
    euro = C.common_window(*home, 52.0, 5.0, when, hours=24)
    check("Minnesota and the Netherlands share a window some hours a day", len(euro) >= 1, True)

    print("\n-- the meteor calendar --")
    met = C.meteor_outlook(datetime(2026, 8, 12, 12, tzinfo=timezone.utc))
    check("the Perseids are on at their peak", met["now"]["name"], "Perseids")
    check("  and the next one after them is the Orionids", met["next"]["name"], "Orionids")
    met = C.meteor_outlook(datetime(2026, 12, 30, tzinfo=timezone.utc))
    check("the year wraps: after the Ursids come the Quadrantids", met["next"]["name"], "Quadrantids")
    check("  nothing is on at the end of December", "now" in met, False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
