#!/usr/bin/env python3
"""The printed antenna sheet carries the antenna as it goes up, and its patterns.

    python3 tests/test_sheet_drawings.py

The Lab draws both on the screen; the sheet that goes out to the garden had
only tables. Now it has a build sketch beside "What to cut" and the two
pattern views beside "How high" (antennadraw.py). What is held here:

  - every antenna the Lab offers prints, with a sketch and a pattern pair;
  - the sketch's numbers are the cut table's: the leg it labels is the leg
    the table prints, in the operator's own units;
  - the patterns are the Lab's, from the same model, so a beam's plan view
    is strong ahead and weak behind and a wire's is strong broadside;
  - and a drawing that cannot be made leaves the sheet whole, not broken.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from reportlab.graphics.shapes import Drawing, Polygon, String  # noqa: E402

from elmer import antenna_advice as A, antennadraw, antennapdf  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def texts(d):
    return [g.text for g in d.contents if isinstance(g, String)]


def band_for(kind):
    return (146.52 if kind in ("jpole", "collinear") else
            14.2 if kind in ("yagi", "moxon", "hexbeam", "quad", "vbeam", "rhombic") else 7.15)


def main():
    print("-- every antenna prints, with both drawings --")
    no_sketch, no_plot, broke = [], [], []
    for kind in A.TYPES:
        mhz = band_for(kind)
        say = antennapdf._feet_inches
        if not isinstance(antennadraw.sketch(kind, mhz, 35, say, dims=antennapdf.dimensions(kind, mhz, "wire14")),
                          Drawing):
            no_sketch.append(kind)
        if not isinstance(antennadraw.pattern_pair(kind, mhz, 35), Drawing):
            no_plot.append(kind)
        try:
            pdf = antennapdf.build(kind, mhz, 35, "wire14", "house")
            if not pdf.startswith(b"%PDF"):
                broke.append(kind)
        except Exception as exc:  # noqa: BLE001 - any failure here is the finding
            broke.append(f"{kind}: {exc!r}")
    check("every antenna has a build sketch", no_sketch, [])
    check("every antenna has its two pattern views", no_plot, [])
    check("every antenna's sheet prints", broke, [])

    print("\n-- the sketch says what the table says --")
    dims = antennapdf.dimensions("invertedv", 7.15, "wire14")
    words = " ".join(texts(antennadraw.sketch("invertedv", 7.15, 35, antennapdf._feet_inches, dims=dims)))
    check("the inverted V's leg is the table's leg", antennapdf._feet_inches(dims["leg_ft"]) in words, True)
    check("  and its apex is the planned height", "35 ft 0.0 in up" in words, True)
    metric = " ".join(texts(antennadraw.sketch("dipole", 7.15, 35, lambda ft: f"{ft * 0.3048:.2f} m",
                                               dims=antennapdf.dimensions("dipole", 7.15, "wire14"))))
    check("in metres for an operator in metres", " m each leg" in metric and " ft " not in metric, True)

    print("\n-- the patterns are the Lab's --")

    def lobe(kind):
        d = antennadraw.pattern_pair(kind, band_for(kind), 35)
        return [g for g in d.contents if isinstance(g, Polygon)][0]

    def reach(poly, ox, oy, dx, dy):
        """How far the plan view's outline reaches along one direction from its centre."""
        pts = list(zip(poly.points[::2], poly.points[1::2]))
        return max((x - ox) * dx + (y - oy) * dy for x, y in pts)
    w = 7.1 * 72
    h = 2.5 * 72
    ox, oy = w * 0.25, h / 2 - 4
    beam = lobe("yagi")
    check("a Yagi laid north reaches further north than south", reach(beam, ox, oy, 0, 1) > 2 * reach(beam, ox, oy, 0, -1),
          True)
    wire = lobe("dipole")
    check("a dipole laid north reaches further east than north - broadside",
          reach(wire, ox, oy, 1, 0) > reach(wire, ox, oy, 0, 1), True)

    print("\n-- by day and by night, against a typical sky, not geometry alone --")
    # A solar flux of 100 and a mid-latitude: what a unit with no reading
    # assumes. 20 m at night was drawn landing 400 to 1,300 miles out, which
    # is where it would come down if the layer turned it back - it does not.
    s20, s40, s80 = (antennadraw.typical_sky(f) for f in (14.2, 7.15, 3.6))
    check("20 m is open by day and shut at night", (s20["day"]["open"], s20["night"]["open"]), (True, False))
    check("40 m is open both, its skip much longer at night",
          (s40["day"]["open"], s40["night"]["open"], s40["night"]["skip_km"] > 2 * s40["day"]["skip_km"]),
          (True, True, True))
    check("80 m comes back from overhead day and night", (s80["day"]["skip_km"], s80["night"]["skip_km"]), (0.0, 0.0))
    night20 = " ".join(texts(antennadraw.footprint_pair("yagi", 14.2, 35)))
    check("the 20 m sheet says nothing comes back at night", "nothing comes back on this band" in night20, True)
    night40 = " ".join(texts(antennadraw.footprint_pair("dipole", 7.15, 35, lat=46.6)))
    check("the 40 m dipole's night lobe falls in the skip, and says its low edge does the work",
          "the lobe's low edge" in night40, True)
    check("a VHF antenna has no skywave footprint", antennadraw.footprint_pair("jpole", 146.52, 20), None)
    check("the sky is the cached reading or a stated typical one, never a fetch",
          "typical figure" in night20 or "solar flux" in night20, True)

    print("\n-- a drawing that cannot be made does not break the sheet --")
    check("an unknown antenna gets no sketch rather than an error",
          antennadraw.sketch("nonesuch", 7.15, 35, antennapdf._feet_inches), None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
