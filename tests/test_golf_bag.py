#!/usr/bin/env python3
"""The bag, the wedge that checks, and the aiming mark that reads the shot.

    python3 tests/test_golf_bag.py

Four clubs became eleven and the putter. The four that were - driver, wood,
iron, wedge - are kept number for number as the driver, the 5-wood, the
7-iron and the sand wedge, because the landing model was solved against
them; the rest are laid in between, and each step down the bag is shorter,
steeper, straighter and spins more.

A wedge pitched onto a green checks - that is what it is for - and an iron
landed short runs on, so a golfer chooses the shot by choosing the club.

The mark reads the shot with the club in hand: the club the yards want,
whether the one held gets there, where it comes down when it does not, and
how wide a fair ball lands - wider for a club too many, which costs in play
exactly what the mark says it will. The map draws the same reading.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import golf, golfmap, voice  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def flat_course(par=4, yards=400, hazards=(), wind="across", green=30):
    return {"id": "flat", "name": "Flat", "pool": "technician", "par": par,
            "wind": {"typical_mph": 0},
            "holes": [{"n": 1, "par": par, "yards": yards, "name": "", "wind": wind,
                       "green": green, "hazards": list(hazards)}]}


def calm(yards=400, **kw):
    g = golf.Golf(["a"], flat_course(yards=yards, **kw), seed=1, seconds=30)
    g.wind_mph = 0
    return g


print("\n-- the bag --")
check("eleven clubs and the putter, longest first", len(golf.CLUB_ORDER), 11)
col = lambda i: [row[i] for row in golf.BAG]  # noqa: E731
check("  each carries less than the one before", col(1) == sorted(col(1), reverse=True) and len(set(col(1))) == 11, True)
check("  comes down steeper", col(2) == sorted(col(2)), True)
check("  lands slower", col(3) == sorted(col(3), reverse=True), True)
check("  spins more", col(4) == sorted(col(4)), True)
check("  and lands tighter", col(5) == sorted(col(5), reverse=True), True)
old = {"driver": (250, 38.0, 1.000, 0.05, 18, 0.18, 6.0), "5-wood": (210, 43.0, 0.930, 0.12, 14, 0.12, 5.4),
       "7-iron": (165, 48.0, 0.756, 0.34, 9, 0.06, 4.6), "sand-wedge": (105, 55.0, 0.620, 0.62, 5, 0.02, 3.6)}
check("the four there were are kept exactly, as the driver, 5-wood, 7-iron and sand wedge",
      {c: tuple(next(r for r in golf.BAG if r[0] == c)[1:]) for c in old}, old)
check("  so a full swing on a fairway still runs 24, 19, 11 and 6",
      [round(golf.run_yards(c, "fairway")) for c in old], [24, 19, 11, 6])
check("named in words the way a golfer says them",
      [golf.club_name(c) for c in ("3-wood", "7-iron", "pitching-wedge", "sand-wedge")],
      ["3-wood", "7-iron", "pitching wedge", "sand wedge"])
check("  and every club has a line in the narrator's script",
      [c for c in list(golf.CLUB_ORDER) + ["putter"] if f"the-{c}" not in voice.VOCABULARY], [])

g = calm()
check("from the rough, nothing longer than the 5-wood", golf.Golf(["a"], flat_course(), seed=1).clubs_for("a")[0], "driver")
g.balls["a"].lie = "rough"
check("  (from the rough the bag starts at the 5-wood)", g.clubs_for("a")[0], "5-wood")
g.balls["a"].lie = "sand"
check("  from the sand, the wedges", g.clubs_for("a"), ["pitching-wedge", "sand-wedge"])
g.balls["a"].lie = "fringe"
check("  from the fringe, something to bump, a wedge to chip, or the putter",
      g.clubs_for("a"), ["7-iron", "8-iron", "9-iron", "pitching-wedge", "sand-wedge", "putter"])

print("\n-- a wedge checks; an iron runs on --")
green_run = {c: golf.run_yards(c, "green") for c in golf.CLUB_ORDER}
check("a wedge pitched onto the green runs two yards or less",
      all(green_run[c] <= 2.0 for c in golf.WEDGES), True)
check("  a 9-iron runs on more than a wedge, a 5-iron more again",
      green_run["pitching-wedge"] < green_run["9-iron"] < green_run["5-iron"], True)
check("  and a wedge still runs its full way on a fairway - it is the green it bites on",
      round(golf.run_yards("sand-wedge", "fairway")), 6)


def approach(club, mark_at, n=200, left=100):
    """n approaches from `left` yards, the mark set on the green; returns
    (how many finished on the green, the rolls, how many spun back)."""
    on, rolls, spun = 0, [], 0
    for seed in range(n):
        g = golf.Golf(["a"], flat_course(yards=400, green=40), seed=seed, seconds=30)
        g.wind_mph = 0
        g.balls["a"].at, g.balls["a"].lie, g.balls["a"].strokes = 400 - left, "fairway", 1
        g.set_aim("a", mark_at, 0)
        row = g.play({"a": {"correct": True, "ms": 1000 + seed, "club": club}})
        s = row["shots"]["a"]
        if s["kind"] == "green" and s.get("flair") is None:
            on += 1
            rolls.append(s.get("roll") or 0)
            spun += "spun back" in s["words"]
    return on, rolls, spun


on, rolls, spun = approach("pitching-wedge", 400)
check("a pitching wedge at the flag from 100: it stops - no roll of more than three yards",
      max(rolls) <= 3, True)
check("  and it spins back often - it is a wedge", spun >= len(rolls) // 4, True)
on7, rolls7, _ = approach("7-iron", 385)
check("a 7-iron landed fifteen short of the flag runs on to it: most roll five or more",
      sum(r >= 5 for r in rolls7) > len(rolls7) // 2, True)
check("  where the wedge's median roll is none at all, or back", statistics.median(rolls) <= 0, True)

print("\n-- the mark reads the shot --")
g = calm()
g.set_aim("a", 160, 0)
r = g.read_mark("a", "7-iron")
check("160 out with the 7-iron: in range, and the 7-iron is the club",
      (r["reaches"], r["suggest"], r["over"], r["yards"]), (True, "7-iron", 0, 160))
check("  the landing patch is the 7-iron's spread", (r["long"], r["wide"]), (9, 5.4))
r = g.read_mark("a", "sand-wedge")
check("with the sand wedge: short, by fifty-five, and it says what to take",
      (r["reaches"], r["short"], r["suggest"]), (False, 55, "7-iron"))
check("  and where it comes down instead - along the line, at the wedge's length",
      r["comes_down"], {"at": 105, "off": 0})
check("  in words", r["says"], "160 to the mark - the sand wedge gets 105, 55 short; it is a 7-iron")
r = g.read_mark("a", "driver")
check("with the driver at 160 - a long club at two thirds of itself - the patch widens a little",
      (r["reaches"], r["widen"], r["long"]), (True, 1.24, 22.3))
g.set_aim("a", 50, 0)
check("  and never more than the cap, however short it is swung", g.read_mark("a", "driver")["long"],
      round(18 * golf.OVERCLUB_MOST, 1))
g.set_aim("a", 160, 0)
check("a long club at seven tenths of itself or more costs nothing: a 4-iron at 160",
      (g.overclub("a", "7-iron", 160), g.overclub("a", "4-iron", 160), round(g.overclub("a", "driver", 100), 2)), (1.0, 1.0, 2.2))

print("\n-- more club, softer: a shot, not a mistake --")
k = calm()
k.balls["a"].at, k.balls["a"].strokes = 335, 1
k.set_aim("a", 400, 0)
nine = k.read_mark("a", "9-iron")
check("a 9-iron at 65 yards is a soft swing - nothing wider, and said as a shot",
      (nine["reaches"], nine["soft"], nine["widen"], nine["says"].startswith("65 to the mark - a soft 9-iron")),
      (True, True, 1.0, True))
check("  the scoring clubs are never too much club, however soft",
      [k.overclub("a", c, 65) for c in ("6-iron", "8-iron", "9-iron", "pitching-wedge")], [1.0, 1.0, 1.0, 1.0])
full, soft = golf.run_yards("9-iron", "fairway"), golf.run_yards("9-iron", "fairway", carry=65, most=141)
check("a soft 9-iron comes down flatter, spins less, and keeps its pace: it runs most of a full one's way",
      (golf.descent_angle("9-iron", carry=65, most=141) < golf.descent_angle("9-iron") - 10, soft > 0.75 * full),
      (True, True))
check("  where a wedge's part swing is high and soft as ever - its loft is the point",
      golf.descent_angle("sand-wedge", carry=40, most=105), golf.descent_angle("sand-wedge"))


def roll_up(club, mark_at, n=200, frm=335):
    """n strokes from `frm` at a mark short of a 400-yard hole's green;
    how many end on the green."""
    on = 0
    for seed in range(n):
        g = golf.Golf(["a"], flat_course(yards=400, green=30), seed=seed, seconds=30)
        g.wind_mph = 0
        g.balls["a"].at, g.balls["a"].strokes = frm, 1
        g.set_aim("a", mark_at, 0)
        s = g.play({"a": {"correct": True, "ms": 9000 + seed, "club": club}})["shots"]["a"]
        on += s["kind"] == "green"
    return on


edge = golf.green_edge(flat_course(green=30)["holes"][0])
# Seven yards short of the green: the mark is about the green, not the collar, which
# narrowed from three yards to two and would otherwise have walked the mark with it.
short_of_green = int(400 - edge - 7)
nine_on = roll_up("9-iron", short_of_green, frm=short_of_green - 65)
check("from 65 yards, a soft 9-iron landed seven short of the green runs up onto the green most of the time",
      nine_on > 110, True)
check("  where a wedge landed there checks and stays off it",
      roll_up("sand-wedge", short_of_green, frm=short_of_green - 65) < nine_on // 3, True)
c = calm()
c.balls["a"].at = 360
c.set_aim("a", 385, 0)
bump, pitch, wood = c.read_mark("a", "7-iron"), c.read_mark("a", "sand-wedge"), c.read_mark("a", "5-wood")
check("inside fifty yards a 7-iron is a bump and run, and says how far it runs",
      (bump["chip"], bump["widen"], bump["says"].startswith("25 to the mark - a bump and run with the 7-iron; it runs about")),
      (True, 1.0, True))
check("  a wedge there is a chip that checks", pitch["says"], "25 to the mark - a chip with the sand wedge; it checks where it lands")
check("  and a chip lands tighter than a full swing: half the 7-iron's spread at 25 yards",
      (bump["long"], c.spread_for("a", "7-iron", 10)), (4.5, 9 * golf.CHIP_TIGHTEST))
carries = []
for seed in range(200):
    b = calm()
    b.balls["a"].at, b.balls["a"].strokes = 360, 1
    b.set_aim("a", 385, 0)
    carries.append(b.play({"a": {"correct": True, "ms": 7000 + seed, "club": "7-iron"}})["shots"]["a"]["carry"])
check("  and in play it does: every bump carries within the patch the mark drew",
      (min(carries) >= 25 - 5, max(carries) <= 25 + 5), (True, True))
check("  and a 5-wood chipped 25 yards is a long club at a tenth of itself: wide", (wood["chip"], wood["widen"] > 2), (False, True))
g.balls["a"].lie = "green"
check("on the green it is a putt, and there is nothing to read", g.read_mark("a", "putter"), None)
w = golf.Golf(["a"], flat_course(wind="with"), seed=1, seconds=30)
w.wind_mph = 20
w.set_aim("a", 175, 0)
check("downwind the yards shrink: 175 with twenty behind is a 7-iron's, not a 6-iron's",
      w.read_mark("a", "7-iron")["reaches"], True)

m = calm()
check("with no mark the sensible club is the pin's", m.default_club("a"), "driver")
m.set_aim("a", 160, 0)
check("  with a mark at 160 it is the mark's - and that is what an unchosen club is swung with",
      (m.default_club("a"), m.play({"a": {"correct": True, "ms": 3000}})["shots"]["a"]["club"]), ("7-iron", "7-iron"))

print("\n-- a long club swung short costs what the mark said --")


def spread_of(club, mark_at, n=300):
    carries = []
    for seed in range(n):
        g = calm()
        g.set_aim("a", mark_at, 0)
        row = g.play({"a": {"correct": True, "ms": 5000 + seed, "club": club}})
        carries.append(row["shots"]["a"]["carry"])
    return max(carries) - min(carries)


check("a driver dropped 110 yards scatters far wider than the wedge made for it",
      spread_of("driver", 110) > 3 * spread_of("pitching-wedge", 110), True)

print("\n-- a bad swing finds the trouble by the target --")
two_traps = [{"kind": "bunker", "from": 95, "to": 110, "side": "", "name": "the cross bunker"},
             {"kind": "bunker", "from": 225, "to": 245, "side": "", "name": "the greenside bunker"}]
by_green, rest = 0, []
for seed in range(300):
    f = golf.Golf(["a"], flat_course(yards=250, hazards=two_traps, green=24), seed=seed, seconds=30)
    f.wind_mph = 0
    f.set_aim("a", 240, 0)
    s = f.play({"a": {"correct": False, "ms": 4000 + seed, "club": "driver"}})["shots"]["a"]
    if s.get("hazard") == "the greenside bunker":
        by_green += 1
        rest.append(f.balls["a"].at)
check("aimed at the green, a foul ball finds the greenside bunker most of the time, not the one on the way",
      by_green > 0.75 * 300, True)
check("  and comes to rest in the part of it by the mark", (min(rest), max(rest)), (240, 240))

print("\n-- the map draws the reading --")
h = flat_course()["holes"][0]
g = calm()
g.set_aim("a", 160, 0)
svg = golfmap.hole_svg(h, mark={"at": 160, "off": 0}, reading=g.read_mark("a", "7-iron"))
check("in range: the landing patch, in green, and the club and yards beside the mark",
      ('class="landing"' in svg, golfmap.READ_OK in svg, "7i · 160" in svg), (True, True, True))
svg = golfmap.hole_svg(h, mark={"at": 160, "off": 0}, reading=g.read_mark("a", "sand-wedge"))
check("short: the mark in red, a cross where it comes down, and the shortfall in words",
      ('class="landing"' in svg, golfmap.READ_SHORT in svg, 'class="comes-down"' in svg, "SW 105 · 55 short" in svg),
      (False, True, True, True))
svg = golfmap.hole_svg(h, mark={"at": 160, "off": 0}, reading=g.read_mark("a", "driver"))
check("too much club: the patch in amber, dashed, and said", (golfmap.READ_WIDE in svg, "too much club" in svg), (True, True))
g2 = calm()
g2.balls["a"].at = 330
g2.set_aim("a", 392, 0)
svg = golfmap.approach_svg(h, mark={"at": 392, "off": 0}, reading=g2.read_mark("a", "sand-wedge"))
check("the approach view draws it too", ('class="landing"' in svg, "SW · 62" in svg), (True, True))
check("with no reading the mark is drawn as it always was",
      ('class="landing"' in golfmap.hole_svg(h, mark={"at": 160, "off": 0}), 'class="mark"' in golfmap.hole_svg(h, mark={"at": 160, "off": 0})),
      (False, True))

print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
sys.exit(1 if FAILS else 0)
