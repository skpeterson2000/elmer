#!/usr/bin/env python3
"""Golf: the golfer's own hand in the shot.

    python3 tests/test_golf_hand.py

A golfer sets the shot up before the question - its shape and its spin -
and after choosing an answer swings at a meter, stopping it where the swing
should be. The answer still decides the shot: a right one does what was set
up, a wrong one does it too much. This holds the meter's notch and sweet
zone, what shape and spin do to a right answer and to a wrong one, and the
room carrying all of it from the phone to the stroke. The shot with none of
it - the practice players' - is test_golf.py's, and is unchanged.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import app as appmod, autoplay, golf, party  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def course(par=4, yards=400, hazards=(), wind="across", green=30):
    return {"id": "flat", "name": "Flat", "pool": "technician", "par": par,
            "wind": {"typical_mph": 0},
            "holes": [{"n": 1, "par": par, "yards": yards, "name": "", "wind": wind,
                       "green": green, "hazards": list(hazards)}]}


def stroke(g, **answer):
    return g.play_one("a", {"correct": True, "ms": 2000, **answer})["shots"]["a"]


def run():
    # The ground's life off, as test_golf.py pins it, so a carry is a number.
    SPREAD, LEAK, RUN = dict(golf.CLUB_SPREAD), dict(golf.CLUB_LEAK), golf.ROLL_BASE
    GUST, KICK = golf.Day.GUST, golf.KICK_ODDS
    golf.CLUB_SPREAD = {c: 0 for c in SPREAD}
    golf.CLUB_LEAK = {c: 0.0 for c in LEAK}
    golf.ROLL_BASE = 0.0
    golf.Day.GUST, golf.KICK_ODDS = (1.0, 1.0), 0.0

    print("\n-- the notch --")
    g = golf.Golf(["a"], course(), seed=1)
    check("a driver that cannot reach the pin: the notch is at the top", g.meter_need("a", "driver"), 1.0)
    g.set_aim("a", 200, 0)
    need = g.meter_need("a", "driver")
    # The ball is flown, so the notch is the swing that carries 200, not
    # 200 over 250: carry does not go in a straight line with the swing.
    check("  a mark at 200 wants most of a 250 driver - more than four fifths, as a flown ball does",
          0.8 < need < 0.95, True)
    check("  and it is the swing that carries it there", round(golf.flight("driver", need)["carry"]), 200)
    check("  the reading carries it, with its sweet zone", (g.read_mark("a", "driver")["need"],
                                                             g.read_mark("a", "driver")["sweet"]),
          (need, golf.METER_SWEET))
    check("  none on the green, where it is a putt", golf.Golf(["a"], course(), seed=1).meter_need("a", "putter"), None)

    def at_200():
        g = golf.Golf(["a"], course(), seed=1)
        g.set_aim("a", 200, 0)
        return g

    print("\n-- where the meter is stopped is the strength of the swing --")
    s = stroke(at_200(), club="driver", meter=need)
    check("stopped on the notch: at the mark", (s["carry"], s["meter_off"]), (200, 0.0))
    pure = stroke(at_200(), club="driver", meter=need + golf.METER_PURE * 0.9)
    check("  inside the pure window is dead on, and said so", (pure["carry"], pure["strike"]), (200, "pure"))
    # Graded, a thousandth at a time: inside the sweet zone a miss counts
    # for half, past it in full. The next decimal place is a distinction.
    edge = stroke(at_200(), club="driver", meter=need + golf.METER_SWEET)
    check("  at the sweet zone's edge, a miss counts for half",
          edge["meter_off"], round((golf.METER_SWEET - golf.METER_PURE) * golf.METER_HALF, 3))
    long_ = stroke(at_200(), club="driver", meter=need + 0.08)
    short = stroke(at_200(), club="driver", meter=need - 0.08)
    check("  past it, the rest counts in full",
          long_["meter_off"], round((golf.METER_SWEET - golf.METER_PURE) * golf.METER_HALF + 0.08 - golf.METER_SWEET, 3))
    check("  so it goes long, and under it short", (long_["carry"] > 205, short["carry"] < 195), (True, True))
    check("  the screens get the stop and the notch to the next decimal place",
          (long_["meter"], long_["meter_need"], long_["strike"]), (round(need + 0.08, 4), round(need, 4), "past the notch"))
    check("a hard question answered right is a wider window, not a swing made for you",
          stroke(at_200(), club="driver", meter=need + golf.METER_PURE_ADEPT * 0.9, adept=True)["carry"], 200)
    plain = stroke(at_200(), club="driver", meter=need + 0.07)["carry"]
    sharp = stroke(at_200(), club="driver", meter=need + 0.07, adept=True)["carry"]
    check("  and the same miss costs it less", 200 < sharp < plain, True)
    g = golf.Golf(["a"], course(), seed=1)
    check("the page's number is held to its range", stroke(g, club="driver", meter=7)["meter"], 1.0)
    g = golf.Golf(["a"], course(), seed=1)
    check("  and nonsense is the shot as it always was", "meter" in stroke(g, club="driver", meter="hard"), False)

    print("\n-- shape: a right answer still lands at the mark --")
    for shape in (-1.0, 1.0):
        g = at_200()
        g.set_setup("a", shape, None)
        s = stroke(g, club="driver", meter=g.meter_need("a", "driver"), shape=shape)
        check(f"  shape {shape:+}: 200 yards, on the line", (s["carry"], s["off"]), (200, 0))
        check("    and said out loud", ("drawn in" if shape < 0 else "faded in") in s["words"], True)
    check("  it curves in the air: the golfer aims for it", golf.flight("7-iron", shape=1.0)["lateral"] > 10, True)

    golf.ROLL_BASE = RUN
    rolls = {}
    for shape in (-1.0, 0.0, 1.0):
        g = golf.Golf(["a"], course(yards=450), seed=3)
        g.set_aim("a", 200, 0)
        g.set_setup("a", shape, None)
        s = stroke(g, club="driver", meter=g.meter_need("a", "driver"), shape=shape)
        rolls[shape] = s["at"] - 200
    check("a draw runs further than straight, and a fade less", rolls[-1.0] > rolls[0.0] > rolls[1.0], True)

    print("\n-- the wind, flown --")
    check("into ten miles an hour a 7-iron loses a caddie's share - near a percent a mile an hour",
          -0.12 < golf.wind_on_carry("7-iron", 1.0, 12, 10) / 165 < -0.06, True)
    check("  and the same wind behind gives back less than that",
          0 < golf.wind_on_carry("7-iron", 1.0, 6, 10) < -golf.wind_on_carry("7-iron", 1.0, 12, 10), True)
    check("  all the spin balloons it into the wind; none bores through",
          golf.wind_on_carry("7-iron", 1.0, 12, 10, spin=1.0) < golf.wind_on_carry("7-iron", 1.0, 12, 10, spin=0.0) - 4,
          True)
    check("  a crosswind of ten moves a driver ten yards and more",
          abs(golf.wind_across("driver", 1.0, 9, 10)) > 10, True)
    check("  and a wedge laid up forty yards is barely touched",
          abs(golf.wind_across("sand-wedge", golf.swing_for("sand-wedge", 40), 9, 10)) < 3, True)
    # 135, not 150: into fifteen a full 7-iron carries about 145, and a mark
    # it cannot reach puts the notch at the top, which is a different claim.
    g = golf.Golf(["a"], course(wind="into"), seed=1)
    g.wind_mph = 15
    g.set_aim("a", 135, 0)
    need_calm = golf.swing_for("7-iron", 135)
    check("the notch reads the wind: into it, the same mark wants more swing",
          g.meter_need("a", "7-iron") > need_calm + 0.03, True)
    s = stroke(g, club="7-iron", meter=g.meter_need("a", "7-iron"))
    check("  and swung on it, the ball gets there anyway, give or take the thin scatter left",
          abs(s["carry"] - 135) <= 4, True)
    g = golf.Golf(["a"], course(wind="into"), seed=1)
    g.wind_mph = 15
    g.set_aim("a", 135, 0)
    check("  where the calm day's swing comes up short", stroke(g, club="7-iron", meter=need_calm)["carry"] < 132, True)

    print("\n-- spin, as much as the club's loft gives --")
    check("the sand wedge has all of it, the driver next to none",
          (golf.SPIN_CAP["sand-wedge"], golf.SPIN_CAP["driver"] < 0.1), (1.0, True))
    green = course(par=3, yards=100)
    g = golf.Golf(["a"], green, seed=2)
    s = stroke(g, club="sand-wedge", meter=g.meter_need("a", "sand-wedge"), spin=1.0)
    check("a sand wedge with all the spin, onto the green, comes back", "spun back" in s["words"], True)
    g = golf.Golf(["a"], green, seed=2)
    s = stroke(g, club="sand-wedge", meter=g.meter_need("a", "sand-wedge"), spin=0.0)
    check("  with none it does not", "spun back" in s["words"], False)

    print("\n-- a wrong answer does the shot too much --")
    both = [{"kind": "bunker", "from": 180, "to": 220, "side": "left", "name": "the left bunker"},
            {"kind": "bunker", "from": 180, "to": 220, "side": "right", "name": "the right bunker"}]
    for shape, side, word in ((1.0, "right", "sliced it"), (-1.0, "left", "hooked it")):
        found = []
        for seed in range(40):
            g = golf.Golf(["a"], course(hazards=both), seed=seed)
            g.set_aim("a", 200, 0)
            found.append(g.play_one("a", {"correct": False, "ms": 2000, "club": "driver",
                                          "meter": 0.8, "shape": shape})["shots"]["a"])
        mine = sum(1 for s in found if s.get("hazard") == f"the {side} bunker")
        check(f"  shaped {side}: the {side} trouble, nearly every time", mine >= 32, True)
        check(f"    and it is called what it is: {word}", all(word in s["words"] for s in found), True)
    g = golf.Golf(["a"], course(hazards=[{"kind": "water", "from": 150, "to": 170, "side": "across",
                                          "name": "the pond"}]), seed=1)
    g.set_aim("a", 200, 0)
    s = g.play_one("a", {"correct": False, "ms": 2000, "club": "driver", "meter": 0.4})["shots"]["a"]
    check("a soft swing cannot find trouble past where it could reach", s["kind"], "rough")

    golf.CLUB_SPREAD, golf.CLUB_LEAK, golf.ROLL_BASE = SPREAD, LEAK, RUN
    golf.Day.GUST, golf.KICK_ODDS = GUST, KICK

    print("\n-- the putting meter --")

    def green(falls="front", grade=0.0, features=()):
        c = course(par=3, yards=150)
        c["holes"][0]["slope"] = {"falls": falls, "grade": grade, "features": list(features)}
        return c

    def on_green(c, feet_short, seed=1):
        g = golf.Golf(["a"], c, seed=seed)
        b = g.balls["a"]
        b.at, b.off, b.lie, b.strokes = 150 - feet_short / 3.0, 0, "green", 2
        return g

    g = on_green(green(), 15)
    m = g.putt_meter("a", "putter")
    check("a fifteen-foot putt reads on a twenty-foot meter, notch at three quarters",
          (m["feet"], m["range"], m["need"]), (15, 20, 0.75))
    check("  no meter with a wedge in hand", g.putt_meter("a", "sand-wedge"), None)
    g.balls["a"].at = 150 - 0.3
    check("  nor for a tap-in", g.putt_meter("a", "putter"), None)
    holed = sum(on_green(green(), 15, seed).play_one("a", {"correct": True, "ms": 2000, "club": "putter",
                                                             "meter": 0.75})["shots"]["a"]["kind"] == "holed"
                for seed in range(30))
    check("on a flat green a right answer stroked on the notch drops, nearly every time", holed >= 27, True)
    holed = sum(on_green(green(), 15, seed).play_one("a", {"correct": False, "ms": 2000, "club": "putter",
                                                             "meter": 0.75})["shots"]["a"]["kind"] == "holed"
                for seed in range(30))
    check("  and a wrong one never does, however well it was stroked", holed, 0)
    up = [on_green(green("front", 3.0), 15, seed).play_one("a", {"correct": True, "ms": 2000, "club": "putter",
                                                                    "meter": 0.75})["shots"]["a"] for seed in range(20)]
    check("uphill, on the notch, it comes up short - the notch is flat pace, the read is yours",
          sum(s["kind"] == "holed" for s in up) <= 4 and any("short" in s["words"] for s in up), True)
    firm = sum(on_green(green("front", 3.0), 15, seed).play_one("a", {"correct": True, "ms": 2000, "club": "putter",
                                                                        "meter": 0.86})["shots"]["a"]["kind"] == "holed"
               for seed in range(20))
    check("  given more, it gets there", firm >= 14, True)

    print("\n-- the green is not one tilt --")
    tier = [{"kind": "tier", "at": -6, "grade": 4.0, "width": 3.0, "up": "back"}]
    flat_x, _ = golf.green_fall(green()["holes"][0], {"falls": "front", "grade": 0.0}, tier, -30, 0)
    face_x, _ = golf.green_fall(green()["holes"][0], {"falls": "front", "grade": 0.0}, tier, -6, 0)
    check("a tier is flat away from its face and steep on it", (round(flat_x, 2), round(face_x, 1)), (-0.0, -4.0))
    ridge = [{"kind": "ridge", "across": 0, "grade": 2.0, "width": 6.0}]
    _, left = golf.green_fall({}, {"falls": "front", "grade": 0.0}, ridge, 0, -6)
    _, right = golf.green_fall({}, {"falls": "front", "grade": 0.0}, ridge, 0, 6)
    check("  a ridge sheds a ball off either flank", (left < 0, right > 0), (True, True))
    check("  a card can name its own, and none means none", golf.green_features(green()["holes"][0]), [])
    card = course()["holes"][0]
    check("  and without one it is drawn from the hole - the same green every round",
          golf.green_features(card) == golf.green_features(dict(card)), True)
    check("the collar is six feet now, not nine", golf.FRINGE, 2)

    print("\n-- the break, previewed: which way, not how much --")
    g = on_green(green("left", 3.0), 24)
    prev = g.putt_preview("a", "putter")
    full = golf.roll_putt(g.hole(), g.slope(g.hole()), [], -24, 0, 1, 0, 24, capture=False)["path"]
    check("it starts at the ball", prev[0], (-24.0, 0.0))
    check("  and bends toward the fall", prev[-1][1] < 0, True)
    check("  a part of the roll, not all of it",
          prev[-1][0] < full[-1][0] - 8 and abs(prev[-1][1]) < abs(full[-1][1]), True)

    print("\n-- the green, drawn --")
    from elmer import golfmap
    h = green("left", 3.0, tier)["holes"][0]
    whole = golfmap.green_geometry(h)
    framed = golfmap.green_geometry(h, (-9.0, 3.0))
    check("a nine-foot putt is framed close: the view zooms in", framed["px_per_ft"] > whole["px_per_ft"] * 2, True)
    check("  and a ball outside the frame's reach is still in the view",
          golfmap.green_geometry(h, (-60.0, 0.0))["px_per_ft"] >= whole["px_per_ft"], True)
    svg = golfmap.green_svg(h, [], None, None, {"falls": "left", "grade": 3.0}, focus=(-24.0, 0.0), preview=prev)
    check("  the fall is a field of arrows, not one", svg.count("<polygon") > 20, True)
    check("  the tier is named in the corner", "a tier short of the cup" in svg, True)
    check("  and the start of the roll is drawn", "how it starts to roll" in svg, True)

    print("\n-- the room carries it from the phone to the stroke --")
    client = appmod.app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    from elmer import db, gating
    conn = db.connect()
    settings = db.get_profile(conn)["settings"]
    settings[gating.SETTING] = "off"
    db.save_settings(conn, settings)
    conn.commit()
    party.close_room()
    room = party.room(create=True, cohorts=1)
    ann = room.join("KC9SP")[0].id
    client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "back",
                                         "seconds": 30, "level": "Elmer"}, environ_base=local)
    autoplay.stop()
    room.round = None
    r = client.post("/api/party/shape", json={"player": ann, "shape": -0.6, "spin": 3},
                    environ_base=local)
    check("the shot is set up, held to its range", (r.status_code, r.get_json()["shape"]),
          (200, {"shape": -0.6, "spin": 1.0}))
    r = client.post("/api/party/shape", json={"player": ann, "shape": "left"}, environ_base=local)
    check("  and a shape that is not a number is refused", r.status_code, 409)
    v = client.get(f"/api/party/state?player={ann}", environ_base=local).get_json()["golf"]
    check("the phone reads it back", v["your_shape"], {"shape": -0.6, "spin": 1.0})
    check("  and the notch for the club in hand", 0 < v["you"]["reading"]["need"] <= 1, True)
    rnd = appmod._ask_party("general", None, 30)
    r = client.post("/api/party/answer", json={"player": ann, "chosen": rnd.answer_index, "ms": 5000,
                                               "meter": 0.5}, environ_base=local)
    check("the answer goes with the swing", r.status_code, 200)
    r = client.post("/api/party/shape", json={"player": ann, "shape": 1}, environ_base=local)
    check("  and once the ball is away the shot cannot change", r.status_code, 409)
    shot = room.close_round()["golf"]["shots"][ann]
    check("the stroke was swung at the meter", shot.get("meter"), 0.5)
    check("  and the shot stays set up for the next one", room.shapes[ann], {"shape": -0.6, "spin": 1.0})
    party.close_room()


run()
print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
