#!/usr/bin/env python3
"""The plan view shows both slices, and stops calling a round pattern deaf.

    python3 tests/test_plan_slices.py

A 30 ft inverted V on 80 m was drawn as a pinched figure-of-eight and
described, flatly, as "deaf toward 90 E and 270 W". Both were true of the
slice being drawn and false of the antenna: that slice was cut along the
ground, at nought degrees, and a wire radiating from about a sixteenth of a
wavelength up puts almost nothing along the ground. At the angle it does
work at - straight up, for that antenna - it is within a tenth of a decibel
of the same in every direction.

The deep nulls everybody knows a dipole has are a ground-level phenomenon.
They fill in as the takeoff angle rises because the angle from the wire's
axis opens up, and by the zenith there is no direction left at all.

So the page draws both: the slice at the antenna's own main lobe, filled,
and the ground slice as a dashed outline behind it. The gap between them is
the lesson, and the words no longer name nulls that the operator's radio
cannot find.

The same fault was one layer deeper, in the towns on the compass. Every one
of them was scored along the ground, so a town off the end of the wire came
out sixty decibels down and was drawn in red as unworkable. Duluth was called
unreachable from a hundred miles away because the wire happened to point at
it. A place a hundred miles off is reached by a ray leaving at about seventy
five degrees, and at seventy five degrees there is no null. Each place is now
scored at the angle that actually gets to it.

Reciprocity makes the receiving case the same case: a signal from Duluth goes
up steeply, turns, and comes down on the antenna at that same steep angle. An
antenna has one pattern and uses it both ways, so a null that is absent
transmitting is absent listening.

What must not move: a repeater, or any line-of-sight contact, really does
travel along the ground, and there the end null is real. Only the reaches
that leave the ground are scored at an angle.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
LAB = ROOT / "elmer" / "static" / "lab.js"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import patterns as P

    print("\n-- a slice is cut at an angle, and the angle decides everything --")
    ground = P.azimuth("invertedv", 90, elev_deg=0)
    zenith = P.azimuth("invertedv", 90, elev_deg=90)
    check("along the ground the V is half way to round off its ends",
          ground[90]["field"], 0.5)
    check("  and broadside is full", ground[0]["field"], 1.0)
    check("at the zenith there is no direction at all",
          (zenith[0]["field"], zenith[90]["field"]), (1.0, 1.0))
    # The null does not vanish suddenly; it fills as the angle rises.
    ends = [P.azimuth("invertedv", 90, elev_deg=e)[90]["field"] for e in (0, 30, 60, 90)]
    check("  filling in all the way up, never stepping back",
          ends == sorted(ends) and ends[0] < ends[-1], True)

    print("\n-- a flat dipole's ground null is deep, and fills the same way --")
    check("nothing off the ends along the ground",
          P.azimuth("dipole", 90, elev_deg=0)[90]["field"], 0.0)
    check("  and everything at the zenith",
          P.azimuth("dipole", 90, elev_deg=90)[90]["field"], 1.0)

    print("\n-- the reported antenna: 30 ft inverted V on 80 m --")
    from elmer import antenna_advice as A
    wl_ft = 983.571 / 3.695
    leg = wl_ft / 4
    eff = 30.0 - A.V_CENTROID * leg * math.sin(math.radians(A.DEFAULT_DROOP_DEG))
    hwl = eff / wl_ft
    lobe = P.main_lobe("invertedv", hwl)
    check("it radiates from well under its apex", round(eff, 1), 16.1)
    check("  which is a sixteenth of a wavelength", round(hwl, 3), 0.061)
    check("  and its main lobe is straight up", lobe, 90.0)
    rows = P.azimuth("invertedv", 90, elev_deg=lobe)
    worst = min(r["field"] for r in rows)
    down_db = -20 * math.log10(worst)
    print(f"    deepest point of the working slice: {worst:.4f}  ({down_db:.2f} dB down)")
    check("  so at the angle it works at there is no null to find",
          down_db < 0.5, True)

    print("\n-- both slices are served, and the page draws both --")
    from elmer.app import app
    from elmer import db
    conn = db.connect()
    db.save_settings(conn, {"location": {"lat": 46.6, "lon": -94.3, "grid": "EN26"}})
    client = app.test_client()
    client.set_cookie("elmer_user", str(conn.user_id))
    r = client.get("/api/pattern?type=invertedv&mhz=3.695&height=30&heading=90",
                   environ_base={"REMOTE_ADDR": "127.0.0.1"})
    if r.status_code != 200:
        check("the pattern endpoint answers", r.status_code, 200)
    else:
        d = r.get_json()
        check("the ground slice is there", len(d.get("azimuth") or []), 361)
        check("  and the working slice beside it", len(d.get("azimuth_lobe") or []), 361)
        check("  cut at the main lobe, not at nought",
              d["azimuth_lobe"][90]["field"] > d["azimuth"][90]["field"], True)

    source = LAB.read_text(encoding="utf-8")
    check("the plot draws the working slice filled", "poly(lobe)" in source, True)
    check("  and the ground slice as an outline behind it", "poly(ground)" in source, True)
    check("  with a legend saying which is which", "where it works" in source, True)
    check("nothing is called deaf any more", "deaf toward" in source, False)
    # An ELMER updated but not restarted serves no working slice. That used to
    # draw the old figure-of-eight with the new words under it, which reads as
    # the fix not having worked - it cost a round trip once already.
    check("  a page newer than its program says so rather than guessing",
          "restart ELMER" in source, True)
    check("  and a near-round pattern says so instead",
          "of the same in every direction" in source, True)

    print("\n-- a place is scored at the angle that reaches it --")
    check("a hundred miles off is a steep ray",
          round(P._reach_angle(160, 314.3, True)), 75)
    check("  a thousand is a shallow one",
          P._reach_angle(2000, 314.3, True) < 20, True)
    check("  and a line-of-sight path is along the ground, where the null is real",
          P._reach_angle(160, 314.3, False), 0.0)

    print("\n-- so the town off the end of the wire is not a null --")
    # The reported case: wire laid 67 ENE, Duluth 82 ENE at about 169 km.
    end_on = P.field_toward("efhw", P._reach_angle(169, 314.3, True), 82, 67)
    check("Duluth is within a decibel, not sixty",
          round(-20 * math.log10(end_on), 1) < 1.0, True)
    check("  where scoring it along the ground made it a dead null",
          P.field_at("efhw", 67, 67), 0.0)

    print("\n-- an antenna has one pattern and uses it both ways --")
    # Reciprocity. The angle a signal arrives at is the angle it would leave
    # at, so transmitting and receiving cannot disagree. Nothing may treat
    # them as two questions, and this is the statement of that.
    for ang in (12.5, 45.0, 75.0):
        there = P.field_toward("efhw", ang, 82, 67)
        back = P.field_toward("efhw", ang, 82 - 180, 67 - 180)
        check(f"  at {ang} deg it is the same number either way", there, back)

    print("\n-- the compass rows carry the angle they were scored at --")
    rows = P.targets(46.6, -94.3, "efhw", 67,
                     {"kind": "regional", "radius_km": 586}, hmf2=314.3)
    check("every town got one", all("takeoff_deg" in r for r in rows), True)
    check("  and none of them is red on an NVIS wire",
          [r["name"] for r in rows if r["db"] < -6], [])
    ground = P.targets(46.6, -94.3, "efhw", 67,
                       {"kind": "line_of_sight", "radius_km": 100})
    check("  while a line-of-sight reach is still scored along the ground",
          all(r["takeoff_deg"] == 0.0 for r in ground), True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
