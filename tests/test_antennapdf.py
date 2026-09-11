#!/usr/bin/env python3
"""The antenna sheet: the arithmetic on it, and that it builds for everything.

    python3 tests/test_antennapdf.py

What is worth guarding here is not the layout - a PDF that looks wrong is
obvious the moment somebody prints one - but the two things that would be wrong
silently. The first is the cut length, because that is the number somebody acts
on with a saw, and being handed a book's 468/f when they are building out of
copper pipe would send them long. The second is that every antenna in the
program produces a sheet at all: the ones that are not cut to a single length -
a Yagi, a bought whip - have to say so rather than print a confident figure
they made up.

The heights caught a real bug and are checked because of it. The first draft
passed the planned height in as the height the job wanted, so `reality` echoed
it straight back and all three rows of the table read the same number - the
sheet agreed with itself and told nobody anything.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import (antenna_advice, antennapdf, bandplan,   # noqa: E402
                   conductors, patterns)

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def near(label, got, want, tol):
    ok = got is not None and abs(got - want) <= tol
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r} +/- {tol})"))
    if not ok:
        FAILS.append(label)


def main():
    print("-- the number somebody cuts to --")
    # 468/f is the wire half-wave answer everybody has read, and a sheet for
    # #14 wire has to agree with it or it is arguing with every book at once.
    d = antennapdf.dimensions("dipole", 7.1, "wire14")
    near("a 40m wire dipole is 468/f overall", d["overall_ft"], 468.0 / 7.1, 0.5)
    near("  and each leg is half of that", d["leg_ft"], 234.0 / 7.1, 0.3)
    check("  two legs", d["legs"], 2)

    print("\n-- fatter is shorter, which is the whole point of the column --")
    pipe = antennapdf.dimensions("dipole", 7.1, "pipe12")
    check("copper pipe comes out shorter than wire",
          pipe["overall_ft"] < d["overall_ft"], True)
    check("  and the sheet says by how much", round(pipe["shorter_by_in"]) > 0,
          True)
    check("  the wire figure is still printed to compare against",
          round(pipe["wire_reference_ft"], 3), round(d["overall_ft"], 3))
    # The direction is the thing. A fatter conductor is a lower-Q one, and a
    # lower-Q one holds its SWR across more of the band.
    check("  fatter also means more band",
          pipe["conductor"]["band_scale"] > 1.0, True)
    check("  and wire is the reference it is measured against",
          d["conductor"]["reference"], True)

    print("\n-- a quarter wave is a quarter wave --")
    q = antennapdf.dimensions("quarter", 14.2, "wire14")
    near("a 20m quarter-wave radiator", q["overall_ft"], 234.0 / 14.2, 0.3)
    check("  one leg, not two", q["legs"], 1)
    loop = antennapdf.dimensions("loop", 14.2, "wire14")
    near("  a full-wave loop is four times it", loop["overall_ft"],
         4 * q["overall_ft"], 0.5)

    print("\n-- what is not cut to a length says so --")
    for kind in ("yagi", "whip"):
        check(f"{kind}: no single figure", antennapdf.dimensions(kind, 14.2,
                                                                 "wire14"), None)
        check(f"  and there is prose for it instead",
              bool(antennapdf.NOT_CUT.get(kind)), True)

    print("\n-- every antenna in the program produces a sheet --")
    # Two sites at each end of what somebody can actually do, because the site
    # is what caps the height and the capped path is the one with the extra
    # paragraph in it.
    for kind in patterns.ANTENNA_Q:
        sizes = []
        for site in ("tower", "apartment"):
            pdf = antennapdf.build(kind, 14.2, 30, "wire14", site)
            sizes.append(len(pdf))
            if not pdf.startswith(b"%PDF"):
                check(f"{kind}/{site} is a PDF", pdf[:4], b"%PDF")
        check(f"{kind}: builds on a tower and in a flat",
              all(n > 3000 for n in sizes), True)

    print("\n-- the height rows are three different answers --")
    # 40m wants half a wave, which is 69 ft. A house caps at 35. Those are not
    # the same number and the sheet must not print them as though they were.
    wanted = antenna_advice.for_type(7.1, "invertedv")["height_ft"]
    reality = antenna_advice.reality("invertedv", 7.1, wanted, "house")
    check("what the job wants, uncapped", wanted, 69)
    check("  what the site allows", reality["max_ft"], 35)
    check("  and it knows it capped it", reality["capped"], True)
    check("  the takeoff angle is the consequence",
          reality["takeoff_deg"] > 60, True)
    check("  where the wanted height would be much lower",
          round(antenna_advice.takeoff_deg(wanted, 7.1)) < 40, True)

    print("\n-- the sheet does not invent a conductor --")
    # An unknown key falls back to wire rather than crashing or, worse, quietly
    # using a velocity factor from nowhere.
    fallback = antennapdf.dimensions("dipole", 7.1, "unobtainium")
    check("an unknown material becomes the reference",
          fallback["conductor"]["key"], conductors.REFERENCE["key"])

    print("\n-- the band bar that goes at the top of it --")
    band = bandplan.band_at(14.2)
    wide = {"low": 13.9, "high": 14.5, "khz": 600}
    slice_ = {"low": 14.15, "high": 14.25, "khz": 100}
    none_ = {"low": None, "high": None, "khz": 0}
    check("an antenna wider than the band covers the whole of it",
          antennapdf.covers_whole(wide, band), True)
    check("  and one narrower than it does not",
          antennapdf.covers_whole(slice_, band), False)
    check("  and one that never reaches 2:1 certainly does not",
          antennapdf.covers_whole(none_, band), False)
    strip, got = antennapdf._band_strip(14.2, slice_, "General", 400)
    check("a band the operator is on gets a bar", got["name"], "20 m")
    check("  which is drawn", strip is not None, True)
    # 11 MHz is nobody's band. The sheet still has to build - somebody trying
    # a frequency out of curiosity should get a sheet, not a traceback.
    off, none_band = antennapdf._band_strip(11.0, slice_, "General", 400)
    check("a frequency in no band gets no bar", [off, none_band], [None, None])
    check("  and the sheet is built anyway",
          len(antennapdf.build("dipole", 11.0, 33.0, "wire14", "house")) > 2000,
          True)

    print("\n-- and the screwdriver, whose Q is not one number --")
    q40 = patterns.base_q("screwdriver", 7.15)
    q10 = patterns.base_q("screwdriver", 28.4)
    check("it is sharper low than high", q40 > q10 * 3, True)
    check("  and the fixed whip still has the one figure",
          patterns.base_q("whip", 7.15), patterns.base_q("whip", 28.4))
    w40 = patterns.usable_bandwidth("screwdriver", 7.15, q=q40)["khz"]
    w10 = patterns.usable_bandwidth("screwdriver", 28.4, q=q10)["khz"]
    # What builders measure: tens of kilohertz on 40, most of a megahertz on
    # 10. These are wide brackets on purpose - the point is the shape of it.
    check("about 50 kHz on 40 m", 25 <= w40 <= 90, True)
    check("  and most of a megahertz on 10 m", 500 <= w10 <= 1200, True)
    check("a screwdriver sheet builds",
          len(antennapdf.build("screwdriver", 7.19, 5.0, "stainless",
                               "house")) > 2000, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
