#!/usr/bin/env python3
"""Checks for the held landmarks: the spots inside a place that resolve with
no network - a beach's mile markers, a summit, a visitor center.

    python3 tests/test_landmarks.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import geocode, landmarks as L, pathto  # noqa: E402
from elmer.terrain import great_circle  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the beach, mile by mile --")
    miles = {s["mile"]: s for s in L.spots() if s.get("mile") is not None}
    check("markers every five miles from 0 to 60", sorted(miles), list(range(0, 61, 5)))
    m0, m60 = miles[0], miles[60]
    check("mile 0 is at the end of the pavement, just south of Malaquite",
          abs(m0["lat"] - 27.4145) < 0.001 and abs(m0["lon"] + 97.3015) < 0.001, True)
    check("mile 60 is the Mansfield Channel", abs(m60["lat"] - 26.564) < 0.001, True)
    steps = [great_circle(miles[n]["lat"], miles[n]["lon"], miles[n + 5]["lat"], miles[n + 5]["lon"])[0] / 1.609
             for n in range(0, 60, 5)]
    check("each step is about five miles", all(4.3 < s < 5.7 for s in steps), True)
    print(f"       (steps {min(steps):.1f} to {max(steps):.1f} miles)")
    check("the beach bows west in the middle", miles[30]["lon"] < min(m0["lon"], m60["lon"]) - 0.05, True)
    check("every marker says it is approximate", all(s["about"] for s in miles.values()), True)
    check("  and which park it is in", miles[55]["pota"], "US-0690")

    print("\n-- finding them by name --")
    hit = L.resolve("mile 55")
    check("'mile 55' is one spot", hit and hit["short"], "Padre Island mile 55")
    check("  with a grid square", bool(hit and hit["grid"]), True)
    check("'mile 5' is mile 5, not mile 50", L.search("mile 5")[0]["short"], "Padre Island mile 5")
    check("  and resolves to it, the whole word beating the prefix", L.resolve("mile 5")["short"], "Padre Island mile 5")
    check("'Padre Island mile' alone is not one spot", L.resolve("Padre Island mile"), None)
    check("'park office' is the visitor center", L.resolve("park office")["short"], "Malaquite Visitor Center")
    check("'Harney Peak' is the summit", L.resolve("Harney Peak")["short"], "Black Elk Peak summit")
    check("  carrying its SOTA reference", L.resolve("Harney Peak")["sota"], "W0D/BB-001")
    check("  at SOTA's own fix, not an eyeballed one", L.resolve("Harney Peak")["about"], False)
    check("'padre' lists the named spots before the markers",
          L.search("padre")[0]["kind"] != "mile marker", True)
    check("nonsense finds nothing", L.search("zzq"), [])
    check("  and resolves to nothing", L.resolve("zzq"), None)

    print("\n-- and the rest of the program can ask --")
    check("the geocoder answers without a lookup", geocode.resolve("mile 55", allow_lookup=False)["short"],
          "Padre Island mile 55")
    check("  a grid square still wins", geocode.resolve("EN26", allow_lookup=False)["kind"], "grid")
    far = pathto.resolve_to("Malaquite")
    check("the far end of a path can be the visitor center", far and far["short"], "Malaquite Visitor Center")
    km = great_circle(hit["lat"], hit["lon"], far["lat"], far["lon"])[0]
    check("mile 55 to the office is a little under 55 miles in a straight line", 48 < km / 1.609 < 55, True)
    print(f"       ({km / 1.609:.1f} miles, {km:.0f} km)")
    group = L.group_for(ref="US-0690")
    check("a park reference finds its spots", group and len(group["spots"]) > 10, True)
    check("  and a summit reference its own", L.group_for(ref="W0D/BB-001")["name"], "Black Elk Peak")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
