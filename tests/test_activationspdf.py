#!/usr/bin/env python3
"""The parks and summits sheet that goes in the vehicle.

    python3 tests/test_activationspdf.py

A printed list is read where the screen is not: at a trailhead, with no
signal, by somebody deciding which way to drive. That is what decides what is
on it - coordinates, because the next thing anybody does with a reference is
type it into something that wants numbers - and what it has to be honest
about.

The count is the part worth testing. A sheet listing thirty parks where four
hundred are held must say so, because a list that looks complete and is not
sends somebody past the nearer thing they would have chosen.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import activationspdf  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def park(n):
    return {"kind": "park", "ref": "US-%04d" % n, "name": "Park %d" % n,
            "km": n, "bearing": (n * 7) % 360, "lat": 46.0 + n / 100,
            "lon": -94.0 - n / 100, "where": "US-MN"}


def summit(n):
    return {"kind": "summit", "ref": "W0M/XX-%03d" % n, "name": "Hill %d" % n,
            "km": n * 3, "bearing": (n * 13) % 360, "lat": 45.0 + n / 100,
            "lon": -93.0 - n / 100, "alt_m": 400 + n, "points": n % 10}


PARKS = [park(n) for n in range(1, 61)]
SUMMITS = [summit(n) for n in range(1, 9)]
STATION = {"grid": "EN26uo", "place": "Brainerd", "callsign": "KC9SP"}


def said(shown, held):
    """The line a section puts over its table.

    Asked of the function rather than of the finished PDF: reportlab
    compresses its text streams, so grepping the bytes for a sentence finds
    nothing whether or not the sentence is there - which is a test that passes
    for the wrong reason in one direction and fails for the wrong reason in
    the other.
    """
    from reportlab.lib import colors
    para = activationspdf._section("Parks on the Air", shown, held,
                                   colors.black, activationspdf._styles())
    return para.text


print("\nall three sheets build, and they are PDFs")
sheets = {}
for want in ("parks", "summits", "both"):
    pdf = activationspdf.build(PARKS, SUMMITS, want=want, station=STATION,
                               radius_km=350)
    sheets[want] = pdf
    check(f"{want}: is a PDF", pdf[:4], b"%PDF")
    check(f"{want}: has some size", len(pdf) > 1200, True)

print("\neach sheet carries what it says on the tin, and not the other")
check("parks-only is smaller than both",
      len(sheets["parks"]) < len(sheets["both"]), True)
check("summits-only is smaller than both",
      len(sheets["summits"]) < len(sheets["both"]), True)

print("\nthe count is honest about being a selection")
# Thirty printed where sixty are held: the sheet has to say which of those it
# is, or somebody drives past the nearer park it did not have room for.
check("it says how many were held", "Nearest 30 of 60 held" in said(30, 60),
      True)
check("and how many are on the page", "30 listed" in said(30, 60), True)
# Eight printed where eight are held: nothing to disclaim, so it does not.
check("and stays quiet when it is showing everything",
      "Nearest" in said(8, 8), False)
check("even at the boundary", "Nearest" in said(30, 30), False)

print("\na band is a band, and the sheet says which one")
banded = activationspdf.build(PARKS, SUMMITS, want="both", station=STATION,
                              inner_km=48.3, outer_km=64.4)
check("still a PDF", banded[:4], b"%PDF")
check("0-50 miles reads as a ceiling",
      activationspdf._band(0, 80.5), "Out to 50 miles.")
check("30-40 reads as a band",
      activationspdf._band(48.3, 64.4), "Between 30 and 40 miles out.")
check("no band, nothing said", activationspdf._band(0, None), "")
# Both units against every distance. The screen counts in kilometres, and a
# sheet that quietly switched would have somebody comparing two numbers that
# are not the same number.
check("distances carry both units", activationspdf._away({"km": 21}),
      "21 mi \u00b7 21 km".replace("21 mi", "13 mi"))
check("and a missing one is not invented", activationspdf._away({}), "\u2014")

print("\nnothing held is a sheet that says so, not a crash")
empty = activationspdf.build([], [], want="both", station=STATION)
check("still a PDF", empty[:4], b"%PDF")
check("and it is the short one", len(empty) < len(sheets["both"]), True)

print("\nthe limit is a sheet, not a directory")
check("default is a page or two of each",
      10 <= activationspdf.DEFAULT_LIMIT <= 60, True)
one = activationspdf.build(PARKS, SUMMITS, want="parks", station=STATION,
                           limit=3)
check("and it is honoured", len(one) < len(sheets["parks"]), True)

print("\na station with nothing on it still prints")
bare = activationspdf.build(PARKS[:2], SUMMITS[:2], want="both")
check("no grid, no callsign, no radius", bare[:4], b"%PDF")

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
