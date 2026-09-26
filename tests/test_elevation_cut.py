#!/usr/bin/env python3
"""An elevation pattern is a slice through the whole vertical plane.

    python3 tests/test_elevation_cut.py

The plot drew a quadrant: nought to ninety degrees, one side only. So every
antenna on the page looked like it fired one way, and an operator looking at
a vertical said so - a vertical radiates a doughnut, the same in every
direction round it, and the side view of a doughnut is two lobes.

It is not only verticals. A wire radiates broadside both ways and its two
lobes are mirror images; there is as much behind a dipole as in front of it,
which is why turning one does not aim it. The single antenna on the list
where the two halves genuinely differ is a beam - and that difference, the
front-to-back, is the number somebody buys a beam for. Drawing one lobe
threw away the only case worth drawing and misrepresented all the others.

Drawing the back of the cut also put a claim on the screen that had been
hiding in the plan view, where everything is drawn against the pattern's own
maximum and sixty decibels down looks the same as twenty. The cosine shape
used for a beam goes to exactly nothing at 180 degrees. No beam has ever
measured nothing. It is held to a real front-to-back now.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import patterns  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
WL = 983.571 / 14.25


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def lobes(cut, floor=0.2):
    """The peaks of a cut, by angle - what somebody would count looking at it."""
    out = []
    for n in range(1, len(cut) - 1):
        if (cut[n]["field"] >= cut[n - 1]["field"] and cut[n]["field"] > cut[n + 1]["field"]
                and cut[n]["field"] >= floor):
            out.append(cut[n]["deg"])
    return out


def at(cut, deg):
    return min(cut, key=lambda p: abs(p["deg"] - deg))["field"]


print("\nthe cut is the whole plane, horizon to horizon over the top")
cut = patterns.elevation_slice("whip", 9 / WL, mhz=14.25, heading=0)
check("it starts at the horizon in front", cut[0]["deg"], 0.0)
check("  goes over the top", any(p["deg"] == 90.0 for p in cut), True)
check("  and ends at the horizon behind", cut[-1]["deg"], 180.0)
check("  rising to a peak and falling once on each side", len(lobes(cut)), 2)

print("\na vertical is a doughnut, so the side view is two lobes")
for kind in ("whip", "quarter", "groundplane", "fiveeighth"):
    cut = patterns.elevation_slice(kind, 12 / WL, mhz=14.25, heading=0)
    pair = lobes(cut)
    check(f"{kind}: two lobes", len(pair), 2)
    check(f"  {kind}: mirror images about the zenith",
          round(pair[0] + pair[1], 1) if len(pair) == 2 else None, 180.0)
    check(f"  {kind}: and as strong behind as in front",
          round(at(cut, pair[1]) - at(cut, pair[0]), 4) if len(pair) == 2 else None, 0.0)
# Which is the same thing the plan view says, from the other side.
check("  and the plan view agrees there is no front to it",
      len({round(p["field"], 3) for p in patterns.azimuth("quarter", 0)}), 1)

print("\na wire radiates broadside, both ways")
for kind in ("dipole", "efhw", "invertedv"):
    cut = patterns.elevation_slice(kind, 35 / WL, mhz=14.25, heading=45)
    front = max(p["field"] for p in cut if p["deg"] < 90)
    back = max(p["field"] for p in cut if p["deg"] > 90)
    check(f"{kind}: as much behind it as in front", round(back - front, 4), 0.0)
# Turning a wire moves its nulls; it does not aim it. The cut is taken
# broadside for exactly that reason - along the wire it would be a slice
# through the null and would say the antenna does nothing at all.
check("the cut of a wire is taken across it, not along it",
      patterns.boresight("dipole", 0), 90.0)
check("  and a beam's is where the boom points", patterns.boresight("yagi", 0), 0.0)

print("\na beam is the one that differs, and it differs by a real number")
cut = patterns.elevation_slice("yagi", 45 / WL, mhz=14.25, heading=0)
front = max(p["field"] for p in cut if p["deg"] < 90)
back = max(p["field"] for p in cut if p["deg"] > 90)
check("there is a forward lobe and something behind it", back > 0.0, True)
check("  held at the front-to-back the model claims",
      round(20 * math.log10(front / back), 1), patterns.YAGI_FB_DB)
check("  which is a beam somebody could own, not a hole",
      15.0 <= patterns.YAGI_FB_DB <= 25.0, True)
# The floor must not flatter the front of the pattern into being round.
check("  and the front is still a beam",
      patterns.field_at("yagi", 90, 0) < 0.5, True)

print("\nthe page is handed the whole cut, and knows which lobes to mark")
client = app.test_client()
for kind, height, want_back in (("whip", 9, True), ("dipole", 35, True),
                                ("yagi", 45, False)):
    d = client.get("/api/pattern?type=%s&mhz=14.25&height=%s&heading=0" % (kind, height),
                   environ_base=LOCAL).get_json()
    cut = d["elevation_cut"]
    check(f"{kind}: the cut spans the plane", (cut[0]["deg"], cut[-1]["deg"]), (0.0, 180.0))
    # The marker goes on every lobe that is actually at the takeoff angle -
    # both for anything symmetric, the front alone for a beam.
    mirrored = at(cut, 180 - d["main_lobe_deg"]) >= at(cut, d["main_lobe_deg"]) * 0.89
    check(f"  {kind}: the takeoff angle is marked on both lobes" if want_back
          else f"  {kind}: only the forward lobe carries the mark", mirrored, want_back)
    check(f"  {kind}: the quadrant is still there for the figures that read it",
          len(d["elevation"]), 181)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
