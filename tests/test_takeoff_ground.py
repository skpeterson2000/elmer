#!/usr/bin/env python3
"""The takeoff angle has to come off the same ground the picture is drawn on.

    python3 tests/test_takeoff_ground.py

An operator looked at a mobile whip's elevation pattern and said the lobe
did not match the number beside it. They were right, and the mismatch was
worth more than the number: the plot was drawn over average earth and every
figure taken from it - the angle in words, the marker laid across the plot,
the azimuth cut, the reach ring, the skip zone - was read off perfect
ground, because `mhz` never reached `main_lobe` or `lobe_edges` and without
a frequency there is no real ground to model.

For a horizontal wire that was a couple of degrees. For a vertical it was
the whole answer. A vertical's element is strongest out along the ground and
nulls straight up, so over perfect ground its pattern peaks at zero degrees;
real earth turns the reflection against the direct wave at grazing angles,
the field falls to nothing at the horizon, and the lobe sits twenty-odd
degrees up. So every vertical in the program was reported as strongest at
zero degrees - along the horizon, where the plot beside it plainly showed
nothing at all - and a zero-degree hop is the longest one geometry allows,
so the reach ring was the furthest a signal could ever go rather than where
this antenna puts one.

What is held here is the agreement: whatever ground is asked for, the number
and the curve are read off the same one. And the two facts a vertical owes
anybody who looks at it - null along its own axis, nothing at the horizon
over real earth.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import patterns  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def peak_of(curve):
    return max(curve, key=lambda p: p["field"])["deg"]


VERTICALS = [k for k, v in patterns.ANTENNA_Q.items() if v.get("shape") == "vertical"]
HORIZONTALS = ["dipole", "invertedv"]

print("\na vertical is strongest broadside to itself and dead along its own axis")
# The element on its own, before any ground: the two things anybody who has
# seen a vertical expects, and the reason the null is where it is.
for kind in VERTICALS[:4]:
    curve = patterns.elevation(kind, 0.25)          # no mhz: the element and a perfect image
    by = {p["deg"]: p["field"] for p in curve}
    check(f"{kind}: nothing straight up, along the element", round(by[90.0], 3), 0.0)
    check(f"  {kind}: strongest along the ground, over perfect ground",
          peak_of(curve), 0.0)

print("\nover real earth the horizon goes too, and the lobe lifts off it")
for mhz, height_ft in ((14.25, 9), (7.15, 9), (28.4, 20)):
    wl = 983.571 / mhz
    curve = patterns.elevation("whip", height_ft / wl, mhz=mhz, ground="average")
    by = {p["deg"]: p["field"] for p in curve}
    check(f"{mhz} MHz: nothing at the horizon", round(by[0.0], 3), 0.0)
    check("  nothing straight up either", round(by[90.0], 3), 0.0)
    check("  and the lobe sits between ten and thirty-five degrees",
          10.0 < peak_of(curve) < 35.0, True)

print("\nthe number and the curve are read off the same ground")
for kind in VERTICALS + HORIZONTALS:
    for mhz, height_ft in ((14.25, 9), (14.25, 35), (7.15, 20)):
        wl = 983.571 / mhz
        hwl = height_ft / wl
        said = patterns.main_lobe(kind, hwl, mhz=mhz)
        drawn = peak_of(patterns.elevation(kind, hwl, mhz=mhz))
        if said != drawn:
            check(f"{kind} at {mhz} MHz, {height_ft} ft", said, drawn)
check("every antenna at every height agrees with its own plot",
      [f for f in FAILS if " MHz, " in f], [])
# And asked without a frequency it still answers, about perfect ground,
# because a caller with no frequency has no ground to be real about.
check("  asked with no frequency, a vertical still peaks along the ground",
      patterns.main_lobe("quarter", 0.25), 0.0)
check("  and the lobe edges answer the same way", patterns.lobe_edges("quarter", 0.25)[1], 0.0)

print("\nand the reach is measured from the angle the antenna actually has")
# A zero-degree takeoff is the longest hop the geometry allows. Reading it
# off perfect ground put every vertical's ring at that maximum.
wl = 983.571 / 14.25
real = patterns.hop_ring("whip", 9 / wl, mhz=14.25)
ideal = patterns.hop_ring("whip", 9 / wl)
check("the ring comes from the lobe, not from the horizon",
      real["takeoff_deg"] > 10.0, True)
check("  which is a good deal nearer than the perfect-ground answer",
      real["far_km"] < ideal["far_km"] * 0.8, True)
check("  and the perfect-ground answer was the geometric maximum",
      ideal["takeoff_deg"], 0.0)

print("\nand the page ships one answer, not two")
client = app.test_client()
for kind, mhz, height in (("whip", 14.25, 9), ("quarter", 14.25, 20),
                          ("dipole", 14.25, 35), ("invertedv", 7.15, 35)):
    d = client.get("/api/pattern?type=%s&mhz=%s&height=%s&heading=0" % (kind, mhz, height),
                   environ_base=LOCAL).get_json()
    check(f"{kind}: the angle in words is the peak of the curve beside it",
          d["main_lobe_deg"], peak_of(d["elevation"]))
    if d["shape"] == "vertical":
        check("  and it is not the horizon, which is where the curve is empty",
              d["main_lobe_deg"] > 5.0, True)
        check("  the reach agrees with it",
              (d["reach"] or {}).get("takeoff_deg"), d["main_lobe_deg"])

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
