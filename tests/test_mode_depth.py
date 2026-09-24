#!/usr/bin/env python3
"""Why one watt of FT8 draws what a hundred watts of SSB draws.

    python3 tests/test_mode_depth.py

The reach map showed the effect and never said where it came from, which
reads as a fault: the same antenna and a hundredth of the power drawing the
same picture. It comes from the mode. FT8 decodes twenty-eight decibels
below where SSB is readable, and twenty-eight decibels is six hundred odd
times the power - more than an amplifier is allowed to make up.

The figure was on the page already, in the mode selector's hover text,
which is invisible on a touchscreen and unread on any. It is a line on the
page now, and this checks the arithmetic behind it.

Nothing here touches the network or the browser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer.propagation import LEGAL_WATTS, _mode_depth  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- SSB is the reference, and the others are measured from it --")
    check("SSB against itself is nothing", _mode_depth(14.2, "ssb", 1)["vs_ssb_db"], 0.0)
    check("  CW hears deeper", _mode_depth(14.2, "cw", 1)["vs_ssb_db"] > 10, True)
    check("  FT8 deeper still", _mode_depth(14.2, "ft8", 1)["vs_ssb_db"] > 25, True)
    check("  AM needs more, being wider and its watts the carrier",
          _mode_depth(14.2, "am", 1)["vs_ssb_db"] < 0, True)
    check("  and FM more again", _mode_depth(14.2, "fm", 1)["vs_ssb_db"]
          < _mode_depth(14.2, "am", 1)["vs_ssb_db"], True)

    print("\n-- the gap is the mode's own, not the band's --")
    # It is the width a mode is copied in and what it needs above the noise.
    # Neither moves with frequency, so the page may say so plainly.
    gaps = {round(_mode_depth(f, "ft8", 1)["vs_ssb_db"], 1)
            for f in (1.9, 3.7, 7.15, 14.2, 28.5, 146.0)}
    check("FT8's gap is the same on every band, 160 m to 2 m", len(gaps), 1)
    check("  and CW's is too",
          len({round(_mode_depth(f, "cw", 1)["vs_ssb_db"], 1)
               for f in (1.9, 14.2, 146.0)}), 1)

    print("\n-- what the watts on the panel are worth in SSB watts --")
    one_ft8 = _mode_depth(14.2, "ft8", 1)
    check("a watt of FT8 is worth hundreds of watts of SSB",
          one_ft8["as_ssb_watts"] > 500, True)
    check("  which is more than a hundred watts of SSB",
          one_ft8["as_ssb_watts"] > 100, True)
    check("  a hundred watts of FT8 is past what anybody may run",
          _mode_depth(14.2, "ft8", 100)["as_ssb_watts"] > LEGAL_WATTS, True)
    check("  a watt of CW is worth a couple of dozen",
          15 < _mode_depth(14.2, "cw", 1)["as_ssb_watts"] < 40, True)

    print("\n-- the alternatives come too, so a line can name them --")
    ssb = _mode_depth(14.2, "ssb", 100)
    check("SSB is offered both of the deeper modes",
          sorted(ssb["others"]), ["cw", "ft8"])
    check("  and a mode is not offered itself",
          "ft8" in _mode_depth(14.2, "ft8", 1)["others"], False)
    check("  each with its decibels and its multiple",
          sorted(ssb["others"]["cw"]), ["db", "times"])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
