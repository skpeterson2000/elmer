#!/usr/bin/env python3
"""The drawn band on the full chart: what it labels, and what it leaves out.

    python3 tests/test_bandpdf.py

The picture exists to answer a question the table cannot - what is this band
for, and how much of it is mine - so what is checked here is that it keeps
saying that as the band plan changes underneath it.

Labels are the part with judgement in them. Every boundary cannot be numbered
without the numbers colliding, and a number that collides with its neighbour
is worse than one that is absent: the reader cannot tell which tick either
belongs to. So there is a ranking, and these checks pin down what it is for -
the edges of your own privileges first, because that is why somebody printed
the chart for their class rather than a generic one.

The one that is easy to get wrong is 60 m. Both edges of a 2.8 kHz channel is
two numbers where the operator wants one, and neither of them is the number
they type into the radio.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reportlab.graphics.shapes import String                    # noqa: E402

from elmer import bandpdf                                       # noqa: E402
from elmer.bandplan import BANDS, CHANNELS_60M                  # noqa: E402

FAILS = []
WIDTH = 720.0


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def labels(name, license_class, width=WIDTH):
    drawing = bandpdf.activity_bar(name, license_class, width)
    return [s.text for s in drawing.contents if isinstance(s, String)]


def places(name, license_class, width=WIDTH):
    drawing = bandpdf.activity_bar(name, license_class, width)
    return sorted(s.x for s in drawing.contents if isinstance(s, String))


def main():
    print("-- a bar with no scale on it is a picture of nothing --")
    got = labels("40 m", "Extra")
    check("the band edges are always numbered",
          (got[0], got[1]), ("7", "7.3"))
    check("  and some of the inside is too", len(got) > 3, True)

    print("\n-- your own edges go first, because that is why you printed it --")
    # A Technician on 80 m has one CW window, 3.525 to 3.56. Where the hatching
    # stops is the number they came for, and it sits close enough to the band
    # edge that an even-handed rule would have dropped it - it did, once.
    tech = labels("80 m", "Technician")
    check("the start of the licence's own window is numbered",
          "3.525" in tech, True)
    check("  and the end of it", "3.56" in tech, True)
    check("  with the band edges still there",
          ("3.5" in tech, "4" in tech), (True, True))

    print("\n-- numbers that would collide are dropped, not overlapped --")
    for name in [b["name"] for b in BANDS]:
        xs = places(name, "Extra")
        tight = [round(b - a, 1) for a, b in zip(xs, xs[1:])
                 if b - a < bandpdf.CHART_CLOSE_GAP - 0.01]
        check(f"{name}: nothing closer than the close gap", tight, [])

    print("\n-- and there is a sensible number of them --")
    for name, cls in (("2 m", "Technician"), ("20 m", "General"),
                      ("10 m", "Technician"), ("160 m", "Extra")):
        n = len(labels(name, cls))
        check(f"{name} ({cls}): between 3 and 14 labels", 3 <= n <= 14, True)

    print("\n-- 60 m is channels, and a channel has one useful number --")
    sixty = labels("60 m", "Extra")
    check("one label per channel", len(sixty), len(CHANNELS_60M))
    check("  and it is the dial setting, not the channel edges",
          sixty, [bandpdf._mhz(c["dial"]) for c in CHANNELS_60M])
    # 5.3334 is the top edge of channel 1. It is in the table, where somebody
    # can read it; it is not what you tune to and does not belong on the map.
    check("  the far edge of a channel is not offered as a frequency",
          "5.3334" in sixty, False)

    print("\n-- every band draws, and a narrow segment survives being drawn --")
    for name in [b["name"] for b in BANDS]:
        for cls in ("Technician", "Extra"):
            d = bandpdf.activity_bar(name, cls, WIDTH)
            if not d.contents:
                check(f"{name}/{cls} drew something", len(d.contents) > 0, True)
    check("all 16 bands draw for both classes", True, True)
    # A calling frequency is a point. It is drawn a shade over a point wide,
    # and it lost its own fill to a white outline until the outline was
    # dropped on anything that narrow.
    from reportlab.graphics.shapes import Rect
    narrow = [r for r in bandpdf.activity_bar("160 m", "Extra", WIDTH).contents
              if isinstance(r, Rect) and r.width < 2.5]
    check("a point-wide segment is drawn", len(narrow) > 0, True)
    check("  without an outline that would erase it",
          [r.strokeColor for r in narrow], [None] * len(narrow))

    print("\n-- the whole chart still builds --")
    names = [b["name"] for b in BANDS]
    for cls in ("Technician", "General", "Extra"):
        pdf = bandpdf.build(names, cls)
        check(f"{cls}: a PDF comes out", pdf[:4], b"%PDF")
        # It printed in eight pages before the drawings were added and has to
        # keep printing in eight: the pictures are paid for by letting the
        # tables break, not by the reader.
        pages = pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")
        check(f"  in {pages} pages, still under ten", pages < 10, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
