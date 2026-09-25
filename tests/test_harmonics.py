#!/usr/bin/env python3
"""Where else a wire is resonant, and whether anybody may use it there.

    python3 tests/test_harmonics.py

A wire n half-waves long has a voltage maximum at each end and a current
maximum in the middle of every half-wave, and where the feed sits decides
which multiples are any use. Fed at the end, every multiple is a voltage
maximum and the 49:1 matches all of them - which is the whole case for an
end-fed and the reason people buy them. Fed at the center, the even
multiples put a current null at the feedpoint, so a 40 m dipole gives 15 m
and not 20 m. That one surprises somebody every year.

The other half of the answer is which multiples land in a band at all. A
40 m end-fed is a four-band antenna; a 30 m end-fed is a one-band antenna
with a 6 m curiosity. Same wire, cut differently, and worth knowing before
cutting rather than after.

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


def bands(kind, mhz):
    return [r["band"] for r in A.harmonics(kind, mhz) if r["band"]]


def main():
    print("\n-- fed at the end, every multiple counts --")
    check("a 40 m end-fed is a four-band antenna",
          bands("efhw", 7.1), ["20 m", "15 m", "10 m"])
    check("  the second multiple is there, which is the point",
          [r["n"] for r in A.harmonics("efhw", 7.1) if r["band"]][0], 2)

    print("\n-- fed at the center, only the odd ones --")
    check("a 40 m dipole gives 15 m", bands("dipole", 7.1), ["15 m"])
    check("  and not 20 m - the even multiple is a current null at the feed",
          "20 m" in bands("dipole", 7.1), False)
    check("  an inverted V is a dipole about this", bands("invertedv", 7.1), ["15 m"])
    check("  and a base-fed quarter wave is the same story",
          bands("quarter", 7.1), ["15 m"])

    print("\n-- and which multiples land in a band at all --")
    check("a 30 m end-fed has nothing until 6 m", bands("efhw", 10.125), ["6 m"])
    check("  its second and third fall between bands",
          [r["band"] for r in A.harmonics("efhw", 10.125)][:3], [None, None, None])
    check("  which is the answer somebody needs before cutting",
          A.harmonic_words("efhw", 10.125).startswith("Also resonant in 6 m"), True)

    print("\n-- a harmonic landing near a band edge is flagged --")
    # 3.6 doubles to 7.2, and 40 m ends at 7.3.
    near = [r for r in A.harmonics("efhw", 3.6) if r["band"] == "40 m"]
    check("an 80 m end-fed cut at 3.6 reaches 40 m", bool(near), True)
    check("  and it is close to the top of it", near[0]["near_edge"], True)
    # Cut lower and the harmonic lands in the bottom half, where the creep
    # carries it further in rather than out.
    low = [r for r in A.harmonics("efhw", 3.52) if r["band"] == "40 m"]
    check("  cut at 3.52 it lands low in the band and is not flagged",
          low[0]["near_edge"], False)
    check("  which is 7.04, the bottom half of 7.0 to 7.3", low[0]["mhz"], 7.04)

    print("\n-- what has no orderly series is not given one --")
    check("a loaded whip", A.harmonics("screwdriver", 7.1), [])
    check("  a loop, whose feed depends on where it was tapped",
          A.harmonics("loop", 7.1), [])
    check("  and the words say nothing rather than something",
          A.harmonic_words("screwdriver", 7.1), None)

    print("\n-- the reason given matches the antenna --")
    check("the end-fed is explained by its end",
          "end is a voltage maximum" in A.harmonic_words("efhw", 7.1), True)
    check("  the dipole by its center",
          "fed at the center" in A.harmonic_words("dipole", 7.1), True)
    check("  and the vertical by its base, not by a center it has not got",
          "fed at the base" in A.harmonic_words("quarter", 7.1), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
