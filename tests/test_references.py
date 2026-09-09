#!/usr/bin/env python3
"""Checks on what "near" means, which is the only thing this module claims.

    python3 tests/test_references.py

Nothing here touches the network - that is deliberate, and it is also the
point. Fetching is somebody else's data on somebody else's day; what has to
hold regardless is the arithmetic done to it afterwards.

Two of these earn their keep. The first is that a distance is recomputed
against wherever the operator is standing now, because the whole reason for
holding a list is that they were going to drive somewhere, and a kilometre
figure worked out at the kitchen table is wrong the moment they leave it.

The second is that a reference is measured on its own coordinates and never
on the coordinates of the list it came in. POTA's location list is wrong about
some of its own centres - when this was written it placed South Africa's North
West province in Indiana - so a program that trusted a centre would offer
somebody a park on another continent. The centre may decide who to ask. It may
not decide what is close.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import references as R  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def hold(areas):
    """Put a synthetic set of areas in front of the module."""
    R.STORE.write_text(json.dumps({"areas": areas}))


def main():
    # Never the operator's real file: this writes, and what it would overwrite
    # is a record of where somebody has been.
    with tempfile.TemporaryDirectory() as tmp:
        R.STORE = Path(tmp) / "references.json"
        return run()


def run():
    print("\n-- nothing held is not the same as nothing there --")
    hold([])
    check("no areas at all", R.coverage(46.6, -94.3)["reason"], "none")
    check("  and it does not claim to know", R.coverage(46.6, -94.3)["known"],
          False)

    # Duluth, 180 km away, prepared to 350. Brainerd is inside it; Denver is
    # a long way outside and must not be reported as covered.
    hold([{"label": "Duluth", "lat": 46.79, "lon": -92.10, "radius_km": 350,
           "parks": [{"kind": "park", "ref": "US-0001", "name": "A park",
                      "lat": 46.79, "lon": -92.10, "km": 0}],
           "summits": []}])
    print("\n-- and held elsewhere is not the same as held here --")
    check("inside the circle", R.coverage(46.6, -94.3)["reason"], "here")
    check("far outside it", R.coverage(39.74, -104.99)["reason"], "elsewhere")
    check("  which still says how far the nearest prepared place is",
          R.coverage(39.74, -104.99)["nearest_km"] > 1000, True)

    print("\n-- a distance is worked out from where the operator is now --")
    # The stored figure is deliberately a lie: it is what the distance was
    # from somewhere else, and trusting it is the bug this guards.
    hold([{"label": "home", "lat": 46.60, "lon": -94.31, "radius_km": 350,
           "parks": [{"kind": "park", "ref": "US-4792", "name": "Crow Wing",
                      "lat": 46.44, "lon": -94.09, "km": 9999}],
           "summits": [{"kind": "summit", "ref": "W9/WI-025", "name": "Summit",
                        "lat": 46.05, "lon": -91.35, "km": 0, "points": 2}]}])
    park = R.nearby(46.60, -94.31, kind="park")[0]
    check("the stored figure is not believed", park["km"] < 100, True)
    check("  and the real one is used", park["km"], 24)

    print("\n-- and on the reference's own coordinates, not the list's --")
    # The area is labelled as being in Minnesota and one of its parks is in
    # South Africa, which is exactly the shape of the upstream error.
    hold([{"label": "home", "lat": 46.60, "lon": -94.31, "radius_km": 350,
           "parks": [{"kind": "park", "ref": "ZA-0001", "name": "Far away",
                      "lat": -25.75, "lon": 25.50, "km": 12},
                     {"kind": "park", "ref": "US-4792", "name": "Crow Wing",
                      "lat": 46.44, "lon": -94.09, "km": 24}],
           "summits": []}])
    close = R.nearby(46.60, -94.31, radius_km=350)
    check("the far one is not offered as near", [r["ref"] for r in close],
          ["US-4792"])
    check("  though it is still held", len(R.nearby(46.60, -94.31)), 2)

    print("\n-- and the two programmes are told apart and not repeated --")
    hold([{"label": "home", "lat": 46.6, "lon": -94.3, "radius_km": 350,
           "parks": [{"kind": "park", "ref": "US-4792", "name": "P",
                      "lat": 46.44, "lon": -94.09}],
           "summits": [{"kind": "summit", "ref": "W9/WI-025", "name": "S",
                        "lat": 46.05, "lon": -91.35, "points": 2}]},
          {"label": "trip", "lat": 46.7, "lon": -94.2, "radius_km": 350,
           "parks": [{"kind": "park", "ref": "US-4792", "name": "P",
                      "lat": 46.44, "lon": -94.09}],
           "summits": []}])
    check("parks only", [r["ref"] for r in R.nearby(46.6, -94.3, kind="park")],
          ["US-4792"])
    check("summits only",
          [r["ref"] for r in R.nearby(46.6, -94.3, kind="summit")],
          ["W9/WI-025"])
    check("and a reference held twice is listed once",
          len(R.nearby(46.6, -94.3)), 2)

    print("\n-- a bounding box is zero away when you are inside it --")
    box = {"minLat": 45.0, "maxLat": 47.0, "minLong": -95.0, "maxLong": -93.0}
    check("inside", round(R._box_km(46.0, -94.0, box)), 0)
    check("just north of it", round(R._box_km(48.0, -94.0, box)), 111)
    check("a box with no corners is unanswerable",
          R._box_km(46.0, -94.0, {"minLat": None}), None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
