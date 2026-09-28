#!/usr/bin/env python3
"""Which MUF, and what is near: the numbers named for what they are.

    python3 tests/test_muf_labels.py

A night of MUF 8.3 MHz over a foF2 of 2.7 was read as "40 m works" - the
tile said only "MUF", the reach map's header "MUF here", and the headline
"expect the action on 40m and below". All true a thousand miles out; none
of it true for the next county, where 40 m goes straight up and through. What
is held here:

  - the headline, when 40 m cannot come back from overhead, names the band
    that can, from the same door the reach map draws its near zone by;
  - the tile says MUF(3000), and foF2 says it is the one straight up;
  - the reach map's header gives both numbers, named;
  - the antenna line no longer says a low wire has no low-angle way out -
    its own figure at 20 degrees says otherwise, and the map shows it.
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import propagation as P

    print("\n-- the headline says what is near --")
    night = P.verdict(97, 1.67, 6, fof2=2.7)
    check("foF2 2.7: the headline names the band for near, and why 40 m is not it",
          ("160m is the band now" in night, "foF2 is 2.7 MHz, so 40m goes straight up and through" in night),
          (True, True))
    check("  foF2 4.0: 80 m comes back from overhead, and is named", "80m is the band now" in P.verdict(97, 1, 5, fof2=4.0), True)
    check("  foF2 7.5: 40 m comes back too, and the headline is as it was",
          P.verdict(97, 1, 5, fof2=7.5), P.verdict(97, 1, 5))
    check("  no foF2 known: nothing is claimed", P.verdict(97, 1, 5), P._verdict(97, 1, 5))
    check("  CB is never offered as the band for near", P.nvis_band(27.5) in ("10m", "12m"), True)

    snap = {"ok": True, "sfi": 97, "k_index": 1.67, "hmf2": 300, "fof2": 2.7, "muf": 8.3, "calibration": None}
    when = datetime.datetime(2026, 9, 28, 6, 0, tzinfo=datetime.timezone.utc)
    made = P.reach_map(7.074, 46.6, -94.3, snap, step=10.0, when=when)
    check("the headline's door is the reach map's own", round(P.nvis_door(2.7, 300), 1),
          made["nvis"]["door_mhz"])
    check("  and the band it names is the one the map names",
          P.nvis_band(P.nvis_door(2.7, 300)), made["nvis"]["band"])

    print("\n-- the numbers named --")
    prop = (ROOT / "elmer" / "static" / "propagation.js").read_text(encoding="utf-8")
    check("the tile says MUF(3000), measured or estimated",
          ("'MUF(3000)'" in prop, "'Est. MUF(3000)'" in prop, "'a 3,000 km hop; '" in prop), (True, True, True))
    check("  and foF2 says it is the one straight up", "'straight up - what near needs; '" in prop, True)
    band = (ROOT / "elmer" / "static" / "bandplan.js").read_text(encoding="utf-8")
    check("the reach map's header gives both, named",
          ("' · MUF(3000) here '" in band, "' · foF2 ' + d.fof2_here" in band, "' · MUF here '" in band),
          (True, True, False))
    check("the antenna line does not say a low wire has no low-angle way out",
          ("no low-angle way out" in band, "low angles are weak (' + sgn(g.low_db)" in band), (False, True))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
