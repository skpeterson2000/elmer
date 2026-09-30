#!/usr/bin/env python3
"""One real wind over the course, felt by each shot along its own line.

    python3 tests/test_golf_true_wind.py

Each hole's wind was its card's word - with, into, across - fixed to the
hole's tee-to-green line. So a dogleg's second shot felt the drive's wind,
and the front holes at the Old Course, whose card says "with", were
downwind every round whatever the day. Now the round has a wind with a
bearing - the forecast's where the unit has one, else the course's
prevailing wind drawn around - and each shot feels it along the line it is
played on, from the hole's real line on the course map. What is held here:

  - the day's wind has a bearing: the forecast's own, the course's
    prevailing drawn around, or anywhere for a course that has none;
  - drawing it moves no other draw in the round;
  - the hour on a shot is the wind's bearing against the shot's: dead
    ahead is twelve, behind is six, off the right is three;
  - holes that run different ways feel the same wind differently;
  - on a dogleg the second shot is played along the second leg;
  - a swirling hole keeps its swirl; a course with no map keeps its card;
  - the screens are handed each ball's own wind.
"""
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import golf as G, golfmap  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("\n-- the day's wind has a bearing --")
    check("a forecast's compass point is its bearing", G.compass_deg("WNW"), 292.5)
    d = G.Day(random.Random(1), 10, {"wind_mph": 12, "wind_from": "SW"}, 300)
    check("  and the forecast's own wins over the course's prevailing", d.wind_deg, 225.0)
    near = [G.Day(random.Random(s), 10, None, 225).wind_deg for s in range(40)]
    off = [((w - 225 + 180) % 360) - 180 for w in near]
    check("the course's prevailing, drawn around: never more than 50 degrees off it, and not all the same",
          (max(abs(o) for o in off) <= G.Day.DIR_MOST + 1e-9, len({round(w) for w in near}) > 5), (True, True))
    r1, r2 = random.Random(5), random.Random(5)
    G.Day(r1, 10, None, 225)
    G.Day(r2, 10, None, None)
    check("drawing the direction moves no other draw in the round", r1.random(), r2.random())

    print("\n-- felt along the line it is played --")
    g = G.Golf([1], G.course("pebble-beach"), seed=4)
    h18 = next(h for h in g.course["holes"] if h["n"] == 18)
    line = g.shot_bearing(h18)
    check("the 18th at Pebble plays north-west, from its map", 280 < line < 320, True)
    g.day.wind_deg = line
    check("  a wind from dead ahead of it is twelve o'clock", g.wind_clock(h18), 12)
    g.day.wind_deg = (line + 180) % 360
    check("  from behind, six", g.wind_clock(h18), 6)
    g.day.wind_deg = (line + 90) % 360
    check("  off the right, three - and the words say so", (g.wind_clock(h18), g.wind_words(h18)),
          (3, "across off the right"))
    h9 = next(h for h in g.course["holes"] if h["n"] == 9)
    g.day.wind_deg = 300.0
    check("one wind, holes running different ways: the 18th into it, the 9th with it",
          (g.wind_words(h18), g.wind_words(h9)), ("into", "with"))

    print("\n-- a dogleg's second shot --")
    bent = None
    for cid in ("st-andrews-old", "pebble-beach", "augusta-national"):
        gg = G.Golf([1], G.course(cid), seed=2)
        for h in gg.course["holes"]:
            pts = gg._lines.get(str(h["n"])) or []
            if len(pts) >= 3:
                a = math.degrees(math.atan2(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]))
                b = math.degrees(math.atan2(pts[2][0] - pts[1][0], pts[2][1] - pts[1][1]))
                if abs(((b - a + 180) % 360) - 180) > 25:
                    bent = (gg, h)
                    break
        if bent:
            break
    check("a mapped hole that bends is there to test", bent is not None, True)
    if bent:
        gg, h = bent
        pts = gg._lines[str(h["n"])]
        first = math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
        whole = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:]))
        tee = gg.shot_bearing(h, 1)
        gg.balls[1].at = h["yards"] * (first / whole) + 10          # past the bend
        second = gg.shot_bearing(h, 1)
        check(f"  the {h['n']} at {gg.course['name']}: the second shot's line is not the drive's",
              abs(((second - tee + 180) % 360) - 180) > 20, True)

    # A shot's line runs to the pin of the hole it is asked about, not of
    # whichever hole the round is on - asked about the 18th from a round on
    # the 1st, it pointed backwards.
    one = G.Golf([1], G.course("pebble-beach"), holes=[1], seed=4)
    eighteen = G.Golf([1], G.course("pebble-beach"), holes=[18], seed=4)
    one.day.wind_deg = eighteen.day.wind_deg = 300.0
    one.balls[1].at = eighteen.balls[1].at = h18["yards"] - 90
    check("a shot's line runs to its own hole's pin, whichever hole the round is on",
          one.wind_clock(h18, player=1), eighteen.wind_clock(h18, player=1))

    print("\n-- what keeps its old rule --")
    aug = G.Golf([1], G.course("augusta-national"), seed=1)
    swirl = next(h for h in aug.course["holes"] if h.get("wind") == "swirling")
    check("a swirling hole keeps its swirl: the shot drawn as 'into' is into", aug.wind_clock(swirl, "into"), 12)
    plain = G.Golf([1], G.course("pebble-beach"), seed=1)
    plain._lines = {}
    hole = plain.course["holes"][0]
    check("a course with no map keeps its card's arc",
          plain.wind_clock(hole) in G.WIND_ARC[hole["wind"] if hole["wind"] != "across" else "across-left"], True)

    print("\n-- the screens --")
    state = g.as_dict()
    balls = state.get("balls") or {}
    one = balls.get(1) or balls.get("1") or {}
    check("each ball carries the wind on its own next shot", ("wind" in one, "wind_hour" in one), (True, True))
    # compared, not printed: a Windows console cannot show the arrows
    check("the diagram draws which side a crosswind comes off",
          (golfmap.WIND_ARROW["across off the left"] == "\u2192", golfmap.WIND_ARROW["across off the right"] == "\u2190"),
          (True, True))


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
