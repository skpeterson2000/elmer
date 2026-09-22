#!/usr/bin/env python3
"""How the ball arrives, and what the ground does about it.

    python3 tests/test_golf_landing.py

The roll used to be a yards-per-club table times a per-surface multiplier,
and between them there was nowhere to put the question that matters: what
if it arrives shallow and fast? A thinned iron and a flushed one landed the
same way, and a ball could not skip off water because nothing knew the
angle it hit at.

Now the arrival is the club's - a landing speed, a descent angle, a spin
check - and the ground's answer is a friction, and the run falls out of the
two. The properties worth holding: the model reproduces exactly what it
replaced at the calibration point, so this stage changed the shape and not
the game; the landing speeds are physically ordered; a part swing runs
less because it arrives slower; the surfaces keep the order they had; and
the skip is reachable only by a shot that was earned, never by an ordinary
one, and never by a ball too slow to plane.
"""
import logging
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import golf  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def near(label, got, want, slack=0.05):
    ok = abs(got - want) <= slack
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got:.2f}"
          + ("" if ok else f"  (wanted {want:.2f})"))
    if not ok:
        FAILS.append(label)


class Caught(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())

    def said(self, *words):
        return any(all(w.lower() in m.lower() for w in words) for m in self.lines)


caught = Caught()
logging.getLogger("elmer").addHandler(caught)
logging.getLogger("elmer").setLevel(logging.DEBUG)


print("\nthe calibration point: what this model replaced, exactly")
# The old ROLL table, full swing on a fairway at firmness 1.0.
for club, was in (("driver", 24), ("wood", 19), ("iron", 11), ("wedge", 6)):
    near(f"a {club} runs {was} yards as it always did",
         golf.run_yards(club, "fairway", firmness=1.0), was, 0.06)

print("\n  and the landing speeds that solves for are physically ordered")
speeds = [golf.V_LAND[c] for c in ("driver", "wood", "iron", "wedge")]
check("driver fastest down to wedge slowest", speeds == sorted(speeds, reverse=True), True)
check("  and the descent angles the other way",
      [golf.DESCENT[c] for c in ("driver", "wood", "iron", "wedge")]
      == sorted(golf.DESCENT.values()), True)


print("\nthe surfaces keep the order the game has always had")
run = {lie: golf.run_yards("wood", lie) for lie in
       ("green", "fairway", "fringe", "rough", "sand")}
check("green > fairway > fringe > rough > sand",
      run["green"] > run["fairway"] > run["fringe"] > run["rough"] > run["sand"], True)
check("  and a ball landing in sand stops where it pitched", round(run["sand"]), 0)
near("  the green is still about a third faster than the fairway",
     run["green"] / run["fairway"], 1.333, 0.02)

print("\n  the fringe is the one under argument, and is not changed here")
check("it still brakes harder than the fairway, as it always did",
      run["fringe"] < run["fairway"], True)
check("  and the other reading is kept beside it, unused",
      golf.FRINGE_IF_FAST < golf.FRICTION["fringe"], True)


print("\nfirmness scales the lot")
soaked = golf.run_yards("driver", "fairway", firmness=0.65)
baked = golf.run_yards("driver", "fairway", firmness=1.35)
check("soft ground holds it, bone dry runs it", soaked < 24 < baked, True)
near("  and it is straight proportion", baked / soaked, 1.35 / 0.65, 0.01)


print("\na part swing runs less, because it arrives slower")
full = golf.run_yards("iron", "fairway", carry=165, most=165)
half = golf.run_yards("iron", "fairway", carry=80, most=165)
check("a full iron runs further than a half one", full > half, True)
check("  and the speed is what did it",
      golf.landing_speed("iron", 80, 165) < golf.landing_speed("iron", 165, 165), True)


print("\nthe descent angle is a real quantity now")
check("a stinger comes in far flatter than the same club struck",
      golf.descent_angle("iron", "stinger") < golf.descent_angle("iron"), True)
near("  by the figure that says so",
     golf.descent_angle("iron", "stinger") / golf.descent_angle("iron"),
     golf.STINGER_DESCENT, 0.001)
check("  and no club at all is read as an iron, quietly",
      golf.descent_angle(None), golf.DESCENT["iron"])


print("\nthe skip is never an ordinary shot's")
rng = random.Random(3)
for club in ("driver", "wood", "iron", "wedge"):
    angle, pace = golf.descent_angle(club), golf.landing_speed(club)
    check(f"  a struck {club} never skips",
          any(golf.skips(angle, pace, rng) for _ in range(5000)), False)

print("\n  and is reachable only through a shot that was earned")
hits = sum(golf.skips(golf.descent_angle("driver", "stinger"),
                      golf.landing_speed("driver"), rng) for _ in range(5000))
check("a stinger driver skips sometimes", 0 < hits < 5000, True)
check("  but not often", hits / 5000 < 0.30, True)

print("\n  a ball too slow to plane never does, however flat")
check("a stinger wedge is under the angle",
      golf.descent_angle("wedge", "stinger") < golf.SKIP_ANGLE, True)
check("  and still cannot, being too slow",
      any(golf.skips(golf.descent_angle("wedge", "stinger"),
                     golf.landing_speed("wedge"), rng) for _ in range(5000)), False)


print("\nand it is wired into the water, loudly")
caught.lines.clear()
hole = {"id": "flat", "name": "Flat", "pool": "technician", "par": 4,
        "wind": {"typical_mph": 0},
        "holes": [{"n": 1, "par": 4, "yards": 400, "name": "", "wind": "across",
                   "green": 30,
                   "hazards": [{"kind": "water", "from": 240, "to": 262,
                                "side": "across", "name": "the creek"}]}]}
# The same hole with water too wide to clear: a skip carries eighteen to
# thirty-four yards, so a sixty-yard carry across a lake is still wet, and
# the trick shot cannot be used to walk on water.
lake = {**hole, "holes": [{**hole["holes"][0],
        "hazards": [{"kind": "water", "from": 240, "to": 320,
                     "side": "across", "name": "the lake"}]}]}
# The physics is tested above; this is the wiring. The spread and the leak
# go off with it, or the ball is pushed out to the side every time and
# never reaches water that lies across the fairway - which is itself the
# right behaviour, and not what is being checked here.
was, spread, leak = golf.skips, dict(golf.CLUB_SPREAD), dict(golf.CLUB_LEAK)
golf.skips = lambda *a, **k: True
golf.CLUB_SPREAD = {c: 0 for c in spread}
golf.CLUB_LEAK = {c: 0.0 for c in leak}
try:
    g = golf.Golf(["a"], hole, seed=1, seconds=30)
    g.wind_mph = 0
    shot = g.play({"a": {"correct": True, "ms": 1000, "club": "driver"}})["shots"]["a"]
finally:
    golf.skips, golf.CLUB_SPREAD, golf.CLUB_LEAK = was, spread, leak
check("the ball came out of the water", shot["kind"] != "water", True)
check("  and it is called a skip", shot.get("flair"), "skipped")
check("  the words say so, so it does not read as a fault",
      "skipped off" in shot["words"], True)
check("  it carried on some yards", golf.SKIP_RUN[0] <= shot["skipped"] <= golf.SKIP_RUN[1], True)
check("  and the log recorded it", caught.said("skipped one off", "the creek"), True)
check("  there is a call for it at contact", "skipped" in golf.FLAIR_CALLS, True)

print("\n  but a skip is not a way to walk on water")
caught.lines.clear()
was, spread, leak = golf.skips, dict(golf.CLUB_SPREAD), dict(golf.CLUB_LEAK)
golf.skips = lambda *a, **k: True
golf.CLUB_SPREAD = {c: 0 for c in spread}
golf.CLUB_LEAK = {c: 0.0 for c in leak}
try:
    g = golf.Golf(["a"], lake, seed=1, seconds=30)
    g.wind_mph = 0
    wet = g.play({"a": {"correct": True, "ms": 1000, "club": "driver"}})["shots"]["a"]
finally:
    golf.skips, golf.CLUB_SPREAD, golf.CLUB_LEAK = was, spread, leak
check("water too wide to clear is still water", wet["kind"], "water")
check("  and the log says the skip came down in it again",
      caught.said("wet after all"), True)


print("\nnothing unknown takes a round down")
caught.lines.clear()
near("a surface nobody has heard of is charged the fairway's",
     golf.run_yards("driver", "casual water"),
     golf.run_yards("driver", "fairway"), 0.01)
check("  and says so", caught.said("no friction", "casual water"), True)
caught.lines.clear()
near("a club nobody has heard of is read as an iron",
     golf.run_yards("mashie", "fairway"), golf.run_yards("iron", "fairway"), 0.01)
check("  and says so", caught.said("no descent angle", "mashie"), True)

caught.lines.clear()
check("a run that works out absurd is held, and named",
      golf.run_yards("driver", "fairway", firmness=500) <= golf.RUN_MOST, True)
check("  with the figure in the line", caught.said("holding it to"), True)


print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
