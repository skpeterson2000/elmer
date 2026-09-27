#!/usr/bin/env python3
"""The Lab's page draws the earth the way elmer/geo.py measures it.

    python3 tests/test_lab_geo.py

The Lab's ionospheric hop simulator and its path tool run in the browser,
so lab.js carries its own copy of the earth's radius and of the hop
geometry: JavaScript cannot import Python. Everything on the Python side
asks elmer/geo.py, and this test holds the page's copy to it:

  - lab.js's EARTH_R is geo.EARTH_R_KM;
  - lab.js's own hopKm(), run in a real browser over takeoff angles from 0
    to 90 degrees and layer heights from 80 to 500 km, lands where
    geo.hop_km() does, to a millimeter.

Change the geometry in one place and not the other, and this fails.
"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402

FAILS = []
ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "elmer" / "static" / "lab.js"
ANGLES = [a / 2 for a in range(0, 181, 3)]           # 0 to 90 degrees
HEIGHTS = [80.0, 110.0, 200.0, 260.0, 300.0, 350.0, 420.0, 500.0]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def function_source(src, name):
    """The whole of `function name(...) {...}` from src, by counting braces."""
    start = src.find(f"function {name}(")
    if start < 0:
        return ""
    depth, i = 0, src.index("{", start)
    while i < len(src):
        depth += {"{": 1, "}": -1}.get(src[i], 0)
        i += 1
        if depth == 0:
            return src[start:i]
    return ""


def main():
    from elmer import geo

    src = LAB.read_text(encoding="utf-8")

    print("\n-- the radius --")
    m = re.search(r"^const EARTH_R = ([0-9.]+);", src, re.M)
    check("lab.js declares EARTH_R", bool(m), True)
    radius = float(m.group(1)) if m else None
    check("  and it is geo.EARTH_R_KM", radius, geo.EARTH_R_KM)

    print("\n-- the hop, as the page works it out --")
    parts = [function_source(src, "mufFactor"), function_source(src, "hopKm")]
    check("lab.js has mufFactor() and hopKm()", all(parts), True)
    if not (m and all(parts)):
        return 1
    if not _browser.available():
        check("chromium is on this machine", False, True)
        print("\nFAILED: this test needs chromium")
        return 1

    grid = [[a, h] for h in HEIGHTS for a in ANGLES]
    page_js = m.group(0) + "\n" + "\n".join(parts) + "\n"
    scratch = Path(tempfile.mkdtemp(prefix="elmer-labgeo-"))
    try:
        page = scratch / "hop.html"
        page.write_text("<!doctype html><html><body><script>\n" + page_js + "</script></body></html>",
                        encoding="utf-8")
        got = _browser.evaluate(page.resolve().as_uri(),
                                "JSON.stringify(%s.map(([a, h]) => hopKm(a, h)))" % json.dumps(grid),
                                settle=0.3)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    try:
        page_km = json.loads(got)
    except (TypeError, ValueError):
        check("the page's hopKm ran", got, "a list of distances")
        return 1

    worst = max(abs(k - geo.hop_km(a, h)) for (a, h), k in zip(grid, page_km))
    print(f"     {len(grid)} hops compared; the largest difference is {worst:.2e} km")
    check("lab.js's hopKm matches geo.hop_km to a millimeter everywhere", worst < 1e-6, True)
    check("  including the long hop off the horizon (0 deg, 300 km layer)",
          round(page_km[grid.index([0.0, 300.0])]), round(geo.hop_km(0.0, 300.0)))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
