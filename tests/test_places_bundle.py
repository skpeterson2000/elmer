#!/usr/bin/env python3
"""Every bundled place is in the state it says it is in.

    python3 tests/test_places_bundle.py

The list names what an antenna reaches when a unit has no network, and it
once had Mobile in New South Wales and Sheridan on a London street - twenty
of them - because the geocoder was asked for "Mobile AL" with no country.
A reach list that says Sheridan is 4,000 miles off is worse than none.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import regions  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the bundled places --")
    places = json.loads((Path(__file__).resolve().parents[1] / "data" / "places.json").read_text())["places"]
    check("a few hundred of them", len(places) > 300, True)
    outside = [f"{p['name']} {p['region']}" for p in places if not regions.inside(p["region"], p["lat"], p["lon"])]
    check("every one inside its region's box", outside, [])
    check("  and every region has a box", sorted({p["region"] for p in places} - set(regions.BOXES)), [])
    check("Mobile is on the Gulf", next(p["lat"] for p in places if p["name"] == "Mobile") > 30, True)
    check("the box is generous, not a boundary", regions.inside("MN", 43.5, -96.0), True)
    check("  but not that generous", regions.inside("MN", 51.5, -0.1), False)
    check("an unknown region is not judged", regions.inside("ZZ", 0, 0), True)
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
