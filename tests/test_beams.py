#!/usr/bin/env python3
"""The Moxon, the hexbeam and the quad: beams beside the Yagi, on published figures.

    python3 tests/test_beams.py

A beam's gain comes from its elements coupling to one another, which the
Lab's wire sum cannot work out - that takes a full antenna model. So these
three carry their designers' published figures, cited in their advice: L. B.
Cebik's for the Moxon and the two-element quad, S. Hunt G3TXQ's for the
broadband hexbeam. What is held here:

  - each fires one way, with its own published front to back, not the Yagi's;
  - the Yagi's own pattern is unchanged by the generalisation;
  - the hexbeam's dimensions are G3TXQ's, inch for inch, band by band, and the
    Lab shows them as published rather than rescaling them for the wire;
  - each has advice with its source, a balanced feed, and a printed sheet;
  - and each is offered in the Lab, on the reach map and on the analyzer.
"""
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import antenna_advice as A, antennapdf, patterns as P  # noqa: E402

FAILS = []
NEW = ("moxon", "hexbeam", "quad")


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def fb(kind):
    return round(20 * math.log10(P.field_at(kind, 0, 0) / P.field_at(kind, 180, 0)), 1)


def main():
    print("-- one way, each with its own published back --")
    check("the Moxon's back is over 30 dB down, as Cebik's #14 wire models give", fb("moxon"), 30.0)
    check("the quad's about 24 dB, Cebik's 0.125 wavelength design", fb("quad"), 24.0)
    check("the hexbeam's 20 dB, G3TXQ's peak on 20 m about there", fb("hexbeam"), 20.0)
    check("the Yagi's is still the generic three-element beam's", fb("yagi"), P.YAGI_FB_DB)
    check("the Moxon's front lobe is broader than the Yagi's - 'nearly cardioidal'",
          P.field_at("moxon", 60, 0) > P.field_at("yagi", 60, 0), True)
    check("all four fire along the boom", [P.boresight(k, 30) for k in ("yagi",) + NEW], [30.0] * 4)

    print("\n-- the hexbeam is G3TXQ's, as published --")
    js = (ROOT / "elmer" / "static" / "lab.js").read_text(encoding="utf-8")
    rows = re.findall(r"\{band: '(\d+) m', mhz: [\d.]+, driver: ([\d.]+), reflector: ([\d.]+), tips: ([\d.]+)", js)
    check("his five bands, inch for inch",
          rows, [("20", "218", "412", "24"), ("17", "169.5", "321", "18.5"), ("15", "144.5", "274.4", "16"),
                 ("12", "121.7", "232", "13.5"), ("10", "106.8", "204.4", "12")])
    check("and a beam's published dimensions are not rescaled for the wire",
          "if (!isBeam(type) && Math.abs(k - 0.95) > 0.0005) {" in js, True)

    print("\n-- advice, feed and sheet --")
    for k in NEW:
        spec = A.TYPES[k]
        check(f"{k}: its advice names its source", bool(spec.get("source")), True)
        check(f"  is horizontal, fired one way", (spec["polarisation"], P.is_beam(k)), ("horizontal", True))
        check(f"  has its own note on the printed sheet", k in antennapdf.NOT_CUT, True)
    check("all three are balanced, so the Lab calls for a choke",
          all(f"'{k}'" in js.split("const BALANCED = [")[1].split("]")[0] for k in NEW), True)

    print("\n-- offered wherever an antenna is chosen --")
    for page in ("elmer/templates/lab.html", "elmer/templates/bandplan.html", "elmer/templates/tools.html"):
        html = (ROOT / page).read_text(encoding="utf-8")
        check(f"{page.split('/')[-1]} offers all three",
              [k for k in NEW if f'<option value="{k}"' in html], list(NEW))
    station = (ROOT / "elmer" / "static" / "elmer.js").read_text(encoding="utf-8")
    check("and the station antenna remembers them", all(f"'{k}'" in station for k in NEW), True)

    print("\n-- the verticals with a direction, and the one with gain all round --")
    check("two phased verticals fire one way, a cardioid with a 20 dB back", fb("phased2"), 20.0)
    check("the 4-square is narrower than the pair",
          P.field_at("foursquare", 60, 0) < P.field_at("phased2", 60, 0), True)
    half = next(b for b in range(0, 181) if P.field_at("foursquare", b, 0) < 0.7071)
    check("  its half-power width is near Comtek's 92 degrees", 84 <= 2 * half <= 100, True)
    check("a delta loop fires through its face, both ways, as a wire fires broadside",
          (round(P.field_at("deltaloop", 90, 0), 2), fb("deltaloop"), P.boresight("deltaloop", 0)),
          (1.0, 0.0, 90.0))
    check("the collinear is all round", (P.field_at("collinear", 0, 0), P.field_at("collinear", 137, 0)),
          (1.0, 1.0))
    lobe = lambda k: max(P.elevation(k, 0.0, mhz=146.52), key=lambda p: p["field"])["deg"]  # noqa: E731
    check("  and flatter than a single vertical - its gain is the pattern pulled down",
          lobe("collinear") < lobe("quarter"), True)
    check("the arrays and the loop keep a vertical's low angle over ground",
          [lobe(k) <= lobe("quarter") + 0.5 for k in ("phased2", "foursquare", "deltaloop")], [True] * 3)
    for k in ("phased2", "foursquare", "deltaloop", "collinear"):
        check(f"{k}: vertically polarised, with its source named, and a sheet note",
              (A.TYPES[k]["polarisation"], bool(A.TYPES[k].get("source")), k in antennapdf.NOT_CUT),
              ("vertical", True, True))
    for page in ("elmer/templates/lab.html", "elmer/templates/bandplan.html", "elmer/templates/tools.html"):
        html = (ROOT / page).read_text(encoding="utf-8")
        check(f"{page.split('/')[-1]} offers the four",
              [k for k in ("phased2", "foursquare", "deltaloop", "collinear") if f'<option value="{k}"' in html],
              ["phased2", "foursquare", "deltaloop", "collinear"])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
