#!/usr/bin/env python3
"""A ball through the back of the green lies where it stopped.

    python3 tests/test_golf_behind.py

A ball that ran through the green used to be filed at the pin's own
yardage. Everything downstream believed it: the plan drew it on top of the
cup, the board said it had nothing left to play, and the hole measured it
as the nearest ball there was - so a player sixty yards into the rough
behind the green watched somebody ten feet from the cup putt first.

Who is away is decided by who is farthest from the hole, which can only be
as good as where the balls are said to be. So the properties held here are
that the ball keeps its real yards, that the yards it has left are read as
a distance and not as a negative, that away() picks it over a ball on the
green, that the club it is handed is the club for the shot it has, and that
both pictures - the strip down the hole and the zoomed green - draw it
behind the green rather than at the flag.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import golf, golfmap  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def course(yards=400, green=30, par=4):
    return {"id": "flat", "name": "Flat", "pool": "technician", "par": par,
            "wind": {"typical_mph": 0},
            "holes": [{"n": 1, "par": par, "yards": yards, "name": "",
                       "wind": "across", "green": green, "hazards": []}]}


def circles(svg):
    """Every ball drawn, as (x, y, title)."""
    return [(float(x), float(y), t) for x, y, t in
            re.findall(r'<circle cx="([-\d.]+)" cy="([-\d.]+)"[^>]*>'
                       r'(?:<title>([^<]*)</title>)?', svg)]


print("\nthe shot that runs through the green")
g = golf.Golf(["long", "close"], course(), seed=3, seconds=30)
h = g.hole()
edge = golf.green_edge(h)
long_ball, close_ball = g.balls["long"], g.balls["close"]
long_ball.at, long_ball.off, long_ball.lie, long_ball.strokes = 250, 0, "fairway", 1
close_ball.at, close_ball.off, close_ball.lie, close_ball.strokes = 397, 1, "green", 2
# Flushed well through the back: the carry is forced, because the engine
# aims every club at the pin and getting there by luck takes a thousand
# rounds. What is under test is where the ball is said to be afterwards.
g._carry = lambda *a, **k: 215
shot = g._stroke(h, "long", long_ball, {"correct": True, "ms": 2000, "club": "driver"})

check("it is called long", shot["kind"], "long")
check("  the ball is in the rough", long_ball.lie, "rough")
check("  and it lies where it stopped, not at the pin",
      (long_ball.at, long_ball.at > h["yards"] + edge), (487, True))
check("  the words carry the yards back to the pin", "87 back to the pin" in shot["words"], True)
check("  and so does the shot, for the board", shot["left"], 87)

print("\nwho is away: the farthest from the hole, whichever side of it")
check("the ball in the rough behind is 87 yards from the hole",
      int(round(((h["yards"] - long_ball.at) ** 2 + long_ball.off ** 2) ** 0.5)), 87)
check("  the ball on the green is a few",
      int(round(((h["yards"] - close_ball.at) ** 2 + close_ball.off ** 2) ** 0.5)), 3)
check("  so the rough plays first", g.away(), "long")
# The bug it replaces: filed at the pin, the long ball measured its offset
# alone and the man on the green was sent to putt.
was = long_ball.at
long_ball.at = h["yards"]
check("  filed at the pin it was the nearest ball on the hole - the old bug",
      g.away(), "close")
long_ball.at = was

print("\nwhat the board is told")
row = g.as_dict()["balls"]["long"]
check("the yards left are a distance, not a negative", row["left"], 87)
check("  and not the nothing a ball at the pin had", row["left"] != 0, True)

print("\nthe club for a shot played back toward the pin")
check("it is not handed the putter from 87 yards",
      g.default_club("long") != "putter", True)
g.aims["long"] = {"at": h["yards"], "off": 0, "set": True}
check("  aiming at the pin from behind asks for an 87-yard club, not a 0-yard one",
      g.default_club("long") != "putter", True)
del g.aims["long"]
check("a full swing played from behind the green goes toward it",
      golf.Golf(["a"], course(), seed=1, seconds=30)._carry(long_ball, "driver", None, -300) < 0, True)

print("\na foul ball from behind the green goes toward it, not away")
gf = golf.Golf(["a"], course(), seed=7, seconds=30)
hf = gf.hole()
b = gf.balls["a"]
b.at, b.off, b.lie, b.strokes = hf["yards"] + 60, -4, "rough", 2
was = b.at
foul = gf._foul(hf, b, "pitching-wedge")
check("a topped one from behind still moves toward the pin",
      (b.at < was, foul["kind"]), (True, "rough"))
check("  and does not end further away than it started",
      abs(hf["yards"] - b.at) < abs(hf["yards"] - was), True)
# The same swing from in front still goes forward, as it always did.
g2 = golf.Golf(["a"], course(), seed=7, seconds=30)
h2 = g2.hole()
b2 = g2.balls["a"]
b2.at, b2.off, b2.lie, b2.strokes = 150, 0, "fairway", 1
g2._foul(h2, b2, "pitching-wedge")
check("from in front of the pin it still goes forward", b2.at > 150, True)

print("\nthe strip down the hole draws it behind the green")
deep = dict(course(green=44)["holes"][0])          # the deepest green on these courses
collar = golf.green_edge(deep)
balls = [{"name": "at the pin", "at": deep["yards"], "off": 0},
         {"name": "on the back collar", "at": deep["yards"] + collar, "off": 0},
         {"name": "in the rough behind", "at": deep["yards"] + 35, "off": -3},
         {"name": "well through", "at": deep["yards"] + 87, "off": -2}]
drawn = {t: y for _, y, t in circles(golfmap.hole_svg(deep, balls=balls)) if t}
check("four balls drawn, each with its name", sorted(drawn),
      ["at the pin", "in the rough behind", "on the back collar", "well through"])
check("  the back collar is above the pin on the page",
      drawn["on the back collar"] < drawn["at the pin"], True)
check("  the rough behind is above the collar",
      drawn["in the rough behind"] < drawn["on the back collar"], True)
check("  and none of them is drawn at the pin",
      [t for t, y in drawn.items() if t != "at the pin" and y == drawn["at the pin"]], [])
check("  a ball past what the picture holds sits at its edge, not on the cup",
      0 < drawn["well through"] <= 8.0, True)

print("\nthe zoomed green draws it behind the green too")
on = [{"name": "behind", "feet_along": 35 * 3, "feet_across": -9, "feet": 105},
      {"name": "ten feet short", "feet_along": -10, "feet_across": 2, "feet": 10}]
green_drawn = {t.split(",")[0]: y for _, y, t in circles(golfmap.green_svg(deep, balls=on)) if t}
cup_y = golfmap.GH / 2
check("the ball behind is above the cup", green_drawn["behind"] < cup_y, True)
check("  the ball short is below it", green_drawn["ten feet short"] > cup_y, True)
check("  and the one behind is not on the cup", green_drawn["behind"] != cup_y, True)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
