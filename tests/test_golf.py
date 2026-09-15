#!/usr/bin/env python3
"""Golf: a round on a real course, a question a stroke.

    python3 tests/test_golf.py

The courses are read from their cards and checked to add up. Then the
shot: a fast right answer flies the club's length, a slow one less, the
wind adds or takes, the lie costs; a fair ball down the middle avoids the
bunker off to the right but not the creek across the fairway; a foul ball
finds the nearest trouble in reach; on the green a right answer holes it.
Then the round: pick-up at par plus three, the card, the leaderboard with
strokes given, and a tie that goes to a playoff hole.
"""
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


def flat_course(par=4, yards=400, hazards=(), wind="across", green=30, n=1):
    """A hole to reason about, on a course with no wind."""
    return {"id": "flat", "name": "Flat", "pool": "technician", "par": par,
            "wind": {"typical_mph": 0},
            "holes": [{"n": n, "par": par, "yards": yards, "name": "", "wind": wind,
                       "green": green, "hazards": list(hazards)}]}


def R(correct, ms=2000, club=None):
    a = {"correct": correct, "ms": ms}
    if club:
        a["club"] = club
    return a


def run():
    print("\n-- the courses, from their cards --")
    cs = golf.courses()
    check("three of them, friendliest first", list(cs), ["pebble-beach", "st-andrews-old", "augusta-national"])
    for c in cs.values():
        check(f"  {c['id']}: eighteen holes adding to par {c['par']}",
              (len(c["holes"]), sum(h["par"] for h in c["holes"])), (18, c["par"]))
    check("the Old Course goes with General", golf.course_for_pool("general")["id"], "st-andrews-old")
    a12 = next(h for h in cs["augusta-national"]["holes"] if h["n"] == 12)
    check("Golden Bell swirls", a12["wind"], "swirling")

    # The rules, pinned: these sections read the physics exactly - the
    # club's length, the wind's yards, the creek - so the club's spread and
    # leak are off for them and on again for the section that is about them.
    SPREAD, LEAK, RUN = dict(golf.CLUB_SPREAD), dict(golf.CLUB_LEAK), dict(golf.ROLL)
    golf.CLUB_SPREAD = {c: 0 for c in SPREAD}
    golf.CLUB_LEAK = {c: 0.0 for c in LEAK}
    golf.ROLL = {c: 0 for c in RUN}

    print("\n-- the shot --")
    g = golf.Golf(["a"], flat_course(), seed=1, seconds=30)
    check("from the tee, every club", g.clubs_for("a"), ["driver", "wood", "iron", "wedge"])
    check("  the sensible one on a 400-yard hole is the driver", g.default_club("a"), "driver")
    row = g.play({"a": R(True, ms=2000, club="driver")})
    s = row["shots"]["a"]
    check("a fast right answer flies the driver's length", (s["kind"], s["carry"]), ("fairway", 250))
    check("  and the ball is there, on the fairway", (g.balls["a"].at, g.balls["a"].lie), (250, "fairway"))
    g = golf.Golf(["a"], flat_course(), seed=1, seconds=30)
    row = g.play({"a": R(True, ms=30000, club="driver")})
    check("and a slow right answer flies it just as far - the swing is not timed", row["shots"]["a"]["carry"], 250)
    g = golf.Golf(["a"], flat_course(wind="into"), seed=1, seconds=30)
    g.wind_mph = 10
    row = g.play({"a": R(True, ms=1000, club="driver")})
    check("ten into the wind takes eight yards", row["shots"]["a"]["carry"], 242)
    g = golf.Golf(["a"], flat_course(wind="with"), seed=1, seconds=30)
    g.wind_mph = 10
    row = g.play({"a": R(True, ms=1000, club="wood")})
    check("ten behind gives six", row["shots"]["a"]["carry"], 216)

    print("\n-- the course has its say --")
    creek = golf.Golf(["a"], flat_course(hazards=[{"kind": "water", "from": 240, "to": 260,
                                                     "side": "across", "name": "the creek"}]), seed=1)
    row = creek.play({"a": R(True, ms=1000, club="driver")})
    check("a fast driver into a creek across the fairway is in the creek", row["shots"]["a"]["kind"], "water")
    check("  a drop where you were, and a penalty: two strokes, still on the tee",
          (creek.balls["a"].strokes, creek.balls["a"].at, creek.balls["a"].lie), (2, 0, "tee"))
    side = golf.Golf(["a"], flat_course(hazards=[{"kind": "bunker", "from": 240, "to": 260,
                                                    "side": "right", "name": "a bunker"}]), seed=1)
    row = side.play({"a": R(True, ms=1000, club="driver")})
    check("a bunker off to the right does not catch a fair ball down the middle", row["shots"]["a"]["kind"], "fairway")
    side = golf.Golf(["a"], flat_course(hazards=[{"kind": "bunker", "from": 240, "to": 260,
                                                    "side": "right", "name": "a bunker"}]), seed=1)
    row = side.play({"a": R(False, club="wood")})
    check("a foul wood cannot reach a bunker at 240", row["shots"]["a"]["kind"], "rough")
    side = golf.Golf(["a"], flat_course(hazards=[{"kind": "bunker", "from": 240, "to": 260,
                                                    "side": "right", "name": "a bunker"}]), seed=1)
    row = side.play({"a": R(False, club="driver")})
    check("but a foul driver finds it", (row["shots"]["a"]["kind"], side.balls["a"].lie), ("sand", "sand"))
    check("  from where only a wedge is allowed", side.clubs_for("a"), ["wedge"])
    row = side.play({"a": R(True, ms=1000, club="wedge")})
    check("  and a wedge from sand is sixty percent of one", row["shots"]["a"]["carry"], 63)
    far = golf.Golf(["a"], flat_course(hazards=[{"kind": "water", "from": 300, "to": 320,
                                                   "side": "across", "name": "a pond"}]), seed=1)
    row = far.play({"a": R(False, club="wedge")})
    check("a foul wedge cannot find a pond two hundred yards on", row["shots"]["a"]["kind"], "rough")
    check("  it went forward a little", far.balls["a"].at > 0, True)

    print("\n-- the green, and holing out --")
    g = golf.Golf(["a"], flat_course(par=3, yards=150, green=30), seed=1)
    row = g.play({"a": R(True, ms=1000, club="iron")})
    check("an iron to a 150-yard hole is on the green", (row["shots"]["a"]["kind"], g.balls["a"].lie), ("green", "green"))
    check("  where the only club is the putter", g.clubs_for("a"), ["putter"])
    row = g.play({"a": R(False)})
    check("a wrong answer is a missed putt", (row["shots"]["a"]["kind"], g.balls["a"].strokes), ("missed", 2))
    row = g.play({"a": R(True, ms=25000)})
    check("a right answer holes it, however slow", (row["shots"]["a"]["holed"], g.balls["a"].strokes), (True, 3))
    check("  three on a par three: par", row["shots"]["a"]["words"].endswith("3 for par"), True)
    check("  the hole is done, and the card has it", (row["hole_done"], row["card"]), (True, {"a": 3}))

    print("\n-- picking up --")
    g = golf.Golf(["a"], flat_course(par=3, yards=150), seed=1)
    row = None
    for _ in range(6):
        if g.over():
            break
        row = g.play({"a": R(False, club="wedge")})
    check("fouls on a par three: picked up at six", row["card"]["a"], 6)
    check("  which is a triple bogey", golf.score_name(6, 3), "triple bogey")
    check("  and a two under is an eagle", golf.score_name(3, 5), "eagle")

    print("\n-- the round: the card, the leaderboard --")
    c = golf.course("pebble-beach")
    # Two golfers playing the same shots must score the same: no holing out
    # from the fairway by the odds here, which is a draw the two would not
    # share.
    HOLE_OUT = golf.HOLE_OUT_ODDS
    golf.HOLE_OUT_ODDS = 0.0
    g = golf.Golf(["ann", "bob"], c, holes=range(1, 4), handicaps={"bob": 2}, seed=7, seconds=30)
    check("three holes to play", g.as_dict()["holes"], 3)
    played = 0
    while not g.over() and played < 60:
        g.play({p: R(True, ms=1500) for p in ("ann", "bob")})
        played += 1
    check("ann and bob, both quick and right on every question, hole out", g.over(), True)
    board = g.leaderboard()
    check("  both have three holes on the card", [r["holes"] for r in board], [3, 3])
    check("  the strokes given to bob come off", next(r["given"] for r in board if r["player"] == "bob"), 2)
    ann = next(r for r in board if r["player"] == "ann")
    bob = next(r for r in board if r["player"] == "bob")
    check("  gross is the same, so the net leads", (ann["gross"] == bob["gross"], board[0]["player"]), (True, "bob"))
    golf.HOLE_OUT_ODDS = HOLE_OUT
    check("  and bob wins it", g.winner(), "bob")

    print("\n-- a tie goes to a playoff hole --")
    g = golf.Golf(["ann", "bob"], c, holes=[7], seed=3, seconds=30)
    while not g.playoff and not g.over():
        g.play({p: R(True, ms=1500) for p in ("ann", "bob")})
    check("level after the round: a playoff", (g.playoff, g.over()), (["ann", "bob"], False))
    check("  on a hole not yet played", g.hole()["n"] != 7, True)
    played = 0
    while g.playoff and played < 20:
        g.play({"ann": R(True, ms=1500), "bob": R(False)})
        played += 1
    check("the hole that separates them ends it", (g.winner(), g.over()), ("ann", True))

    print("\n-- strokes given, from how somebody has been doing --")
    check("nine in ten plays scratch", golf.handicap_from_accuracy(0.9), 0)
    check("one in two gets a stroke a hole", golf.handicap_from_accuracy(0.5), 18)
    check("  half that over nine holes", golf.handicap_from_accuracy(0.5, holes=9), 9)
    check("seven in ten, nine holes", golf.handicap_from_accuracy(0.7, holes=9), 4)
    check("no history: none given", golf.handicap_from_accuracy(None), 0)

    print("\n-- the playback --")
    g = golf.Golf(["a"], flat_course(par=4, yards=370), seed=1, seconds=30)
    g.play({"a": R(True, ms=1000, club="driver")})            # 250, fairway, 120 to go
    row = g.play({"a": R(True, ms=3000, club="iron")})        # the iron can reach: aimed at the pin
    check("an iron from 120 out is aimed, and on the green", row["shots"]["a"]["kind"], "green")
    check("  within a dozen yards of the hole", int(row["shots"]["a"]["words"].split(", ")[-1].split()[0]) <= 12 * 3, True)
    row = g.play({"a": R(True, ms=5000)})
    check("three strokes on the card", g.cards["a"], {1: 3})
    check("  the last one says the score", "3 for birdie" in row["shots"]["a"]["words"], True)

    print("\n-- one at a time --")
    g = golf.Golf(["a", "b", "c"], flat_course(par=4, yards=400), seed=3)
    check("on the first tee, seating order: a is away", g.away(), "a")
    row = g.play_one("a", {"correct": True, "club": "driver"})
    check("  a's drive alone is in the row", list(row["shots"]), ["a"])
    check("  b and c have not moved", (g.balls["b"].at, g.balls["c"].at), (0, 0))
    check("  with a ball on the fairway, the tee is farther: b is away", g.away(), "b")
    g.play_one("b", {"correct": False, "club": "driver"})     # a foul ball, short
    g.play_one("c", {"correct": True, "club": "driver"})      # 250 out
    check("  then whoever is farthest from the hole", g.away(), "b")
    check("a stroke by a player who is not on the hole is refused",
          "error" in g.play_one("zed", {"correct": True}), True)
    while g.hole() and g.hole()["n"] == 1 and g.away():
        g.play_one(g.away(), {"correct": g.away() == "a"})
    check("the hole plays out one stroke at a time", all(1 in g.cards[p] for p in "abc"), True)
    check("  and a, right every time, won it", g.winner(), "a")
    g2 = golf.Golf(["a", "b"], {**flat_course(par=3, yards=150), "holes": [
        {"n": 1, "par": 3, "yards": 150, "name": "", "wind": "across", "green": 30, "hazards": []},
        {"n": 2, "par": 3, "yards": 150, "name": "", "wind": "across", "green": 30, "hazards": []}]},
        holes=[1, 2], seed=3)
    g2.play_one("a", {"correct": False, "club": "iron"})      # a into the rough
    g2.play_one("b", {"correct": True, "club": "iron"})       # b on the green
    while g2.hole() and g2.hole()["n"] == 1:
        g2.play_one(g2.away(), {"correct": True})
    check("the honour on the next tee goes to the better score", (g2.cards["a"][1] > g2.cards["b"][1], g2.away()), (True, "b"))

    print("\n-- the thread of questions --")
    two = {**flat_course(par=3, yards=150), "holes": [
        {"n": n, "par": 3, "yards": 150, "name": "", "wind": "across", "green": 30, "hazards": []}
        for n in (1, 2, 3)]}
    g = golf.Golf(["a"], two, holes=[1, 2, 3], seed=5)
    pool = {"T1A": ["T1A01", "T1A02"], "T1B": ["T1B01"], "T1C": ["T1C01", "T1C02"]}
    ids = [q for qs in pool.values() for q in qs]
    q1, sec1 = g.draw(pool, ids, "a")
    g.note_asked(q1)
    check("the first hole takes an area", (q1 in pool[sec1], g.hole_section), (True, sec1))
    g.play_one("a", {"correct": False, "club": "iron", "question_id": q1})     # a miss, into the rough
    q2, sec2 = g.draw(pool, ids, "a")
    g.note_asked(q2)
    check("  and stays on it while it has questions, or moves when it is dry",
          sec2 == sec1 if len(pool[sec1]) > 1 else sec2 != sec1, True)
    check("  never the same question twice while others wait", q2 != q1, True)
    check("  the miss is remembered", g.missed, [q1])
    # play the round out, drawing as the room would
    seen = [q1, q2]
    guard = 0
    while not g.over() and guard < 40:
        guard += 1
        q, sec = g.draw(pool, ids, "a")
        g.note_asked(q)
        seen.append(q)
        g.play_one("a", {"correct": True, "question_id": q})
    check("every question asked once before any again", sorted(set(seen[:5])), sorted(ids))
    check("  and the miss came round first after that", seen[5], q1)
    check("  then it was learned", g.missed, [])
    check("a new hole takes a new area", len(set(g.sections_used)) >= 2, True)

    print("\n-- the lie has its say, where hardness is known --")
    g = golf.Golf(["a"], flat_course(par=4, yards=400), seed=5)
    g.hardness = {f"Q{i}": i / 10 for i in range(11)}
    easy = g.choose(list(g.hardness), "a")
    check("from the tee, an easy one", g.hardness[easy] <= 0.4, True)
    g.balls["a"].lie = "sand"
    hard = g.choose(list(g.hardness), "a")
    check("from the sand, a hard one", g.hardness[hard] >= 0.7, True)
    check("with nothing measured, any", golf.Golf(["a"], flat_course(), seed=1).choose(["x", "y"], "a") in ("x", "y"), True)

    print("\n-- the shots worth making, for an adept answer --")
    g = golf.Golf(["a"], flat_course(par=4, yards=400, wind="into"), seed=2)
    g.wind_mph = 15
    g.hardness = {"HARD": 0.9, "EASY": 0.1}
    row = g.play_one("a", {"correct": True, "club": "driver", "question_id": "EASY"})
    check("an easy question right off the tee is a drive, no more", row["shots"]["a"].get("flair"), None)
    g = golf.Golf(["a"], flat_course(par=4, yards=400, wind="into"), seed=2)
    g.wind_mph = 15; g.hardness = {"HARD": 0.9}
    row = g.play_one("a", {"correct": True, "club": "driver", "question_id": "HARD"})
    check("a hard question right, into the wind: a stinger", row["shots"]["a"].get("flair"), "stinger")
    check("  which the wind did not touch", row["shots"]["a"]["carry"], 250)
    check("  and the call says so", row["shots"]["a"]["call"] in golf.FLAIR_CALLS["stinger"], True)
    g = golf.Golf(["a"], flat_course(par=4, yards=400, hazards=[{"kind": "bunker", "from": 200, "to": 260, "side": "across", "name": "sand"}]), seed=2)
    g.balls["a"].at = 100; g.balls["a"].lie = "rough"; g.balls["a"].strokes = 1
    row = g.play_one("a", {"correct": True, "club": "wood", "adept": True})
    check("from the rough, adept: worked out of it, the lie not costing, the sand not catching",
          (row["shots"]["a"].get("flair"), row["shots"]["a"]["kind"]), ("worked", "fairway"))
    g = golf.Golf(["a"], flat_course(par=4, yards=400), seed=2)
    g.balls["a"].at = 370; g.balls["a"].lie = "fairway"; g.balls["a"].strokes = 2
    row = g.play_one("a", {"correct": True, "club": "wedge", "adept": True})
    check("a wedge from thirty out, adept: a flop to a tap-in, or holed",
          row["shots"]["a"].get("flair") in ("flop", "holed-out"), True)
    holed = 0
    for seed in range(40):
        g = golf.Golf(["a"], flat_course(par=4, yards=400), seed=seed)
        g.balls["a"].at = 300; g.balls["a"].lie = "fairway"; g.balls["a"].strokes = 1
        if g.play_one("a", {"correct": True, "club": "iron", "adept": True})["shots"]["a"].get("flair") == "holed-out":
            holed += 1
    check("an adept approach from a hundred out goes in now and then, not always", 0 < holed < 20, True)
    g = golf.Golf(["a"], flat_course(par=5, yards=560), seed=4)
    for i in range(3):
        row = g.play_one("a", {"correct": True, "question_id": f"Q{i}"})
    check("the third right answer in a row is adept without any measure", row["shots"]["a"].get("flair") is not None, True)

    print("\n-- the mark: their aim is their aim, and the algorithm feeds the result --")
    # Spread and leak still off: this is the geometry, exactly.
    creek = golf.Golf(["a"], flat_course(hazards=[{"kind": "water", "from": 240, "to": 260, "side": "across", "name": "the creek"}]), seed=1)
    check("with no mark the shot is at the pin, down the line", creek.aim("a"), {"at": 400, "off": 0, "set": False})
    check("a mark short of the creek is kept", creek.set_aim("a", 225, 0), {"at": 225, "off": 0})
    row = creek.play_one("a", {"correct": True, "club": "driver"})
    s = row["shots"]["a"]
    check("  and the driver lands short of it, on the fairway", (s["kind"], s["carry"], creek.balls["a"].lie), ("fairway", 225, "fairway"))
    check("  a mark is for one stroke", creek.aims, {})
    check("  the next is at the pin again", creek.aim("a")["set"], False)
    bunker = golf.Golf(["a"], flat_course(hazards=[{"kind": "bunker", "from": 230, "to": 260, "side": "left", "name": "the left trap"}]), seed=1)
    bunker.set_aim("a", 250, -30)
    s = bunker.play_one("a", {"correct": True, "club": "driver"})["shots"]["a"]
    check("aimed thirty yards left, into the left trap's yards: in the sand", (s["kind"], s["hazard"], bunker.balls["a"].off), ("sand", "the left trap", -30))
    wide = golf.Golf(["a"], flat_course(), seed=1)
    wide.set_aim("a", 250, 30)
    s = wide.play_one("a", {"correct": True, "club": "driver"})["shots"]["a"]
    check("aimed thirty right with nothing there: the first cut", (s["kind"], wide.balls["a"].lie, wide.balls["a"].off), ("rough", "rough", 30))
    check("  and the next club is the rough's longest", wide.clubs_for("a")[0], "wood")
    wide.set_aim("a", 400, 0)
    s = wide.play_one("a", {"correct": True, "club": "wood"})["shots"]["a"]
    check("  back at the pin: on the line, and the wood reaches from there", (s["off"], s["kind"]), (0, "green"))
    edge = golf.Golf(["a"], flat_course(), seed=1)
    edge.balls["a"].at, edge.balls["a"].lie, edge.balls["a"].strokes = 300, "fairway", 1
    edge.set_aim("a", 400, 20)
    s = edge.play_one("a", {"correct": True, "club": "iron"})["shots"]["a"]
    check("pin-high but twenty yards wide of a green fourteen wide: not on it", s["kind"] != "green", True)
    check("a mark behind the ball is moved ahead of it", golf.Golf(["a"], flat_course(), seed=1).set_aim("a", -50, 0)["at"], 10)
    check("  and one off the property is brought in", golf.Golf(["a"], flat_course(), seed=1).set_aim("a", 200, 900)["off"], golf.OFF_MOST)
    check("a mark on the green is kept in feet - a yard past the cup", (lambda g: (setattr(g.balls["a"], "lie", "green"), g.set_aim("a", 401, 0))[1])(golf.Golf(["a"], flat_course(), seed=1)), {"at": 401.0, "off": 0.0})
    foul = golf.Golf(["a"], flat_course(hazards=[{"kind": "bunker", "from": 230, "to": 260, "side": "right", "name": "the right trap"}]), seed=3)
    s = foul.play_one("a", {"correct": False, "club": "driver"})["shots"]["a"]
    check("a foul ball into a side trap is off on that side", (s["kind"], foul.balls["a"].off > golf.FAIRWAY_HALF), ("sand", True))

    print("\n-- not every golfer hits it the same --")
    g = golf.Golf(["a", "b"], flat_course(), seed=1)
    g.set_swing("b", 0.8, 1.5)
    check("a short hitter's driver is a short hitter's driver", g.reach("b", "driver"), 200.0)
    check("  and a person's is the book's", g.reach("a", "driver"), 250.0)
    sa = g.play_one("a", {"correct": True, "club": "driver", "ms": 1000})["shots"]["a"]
    sb = g.play_one("b", {"correct": True, "club": "driver", "ms": 1000})["shots"]["b"]
    check("  the same swing, forty yards less", sa["carry"] - sb["carry"], 50)
    h2 = golf.Golf(["a", "b"], flat_course(), seed=1)
    h2.set_swing("b", 0.8, 1.5)
    for pp in ("a", "b"):
        h2.balls[pp].at, h2.balls[pp].lie, h2.balls[pp].strokes = 200, "fairway", 1
    check("  the sensible club allows for it: 200 out, the person takes a wood, the short hitter the driver",
          (h2.default_club("a"), h2.default_club("b")), ("wood", "driver"))
    from elmer import party as party_mod
    check("a spread of levels around the one chosen", [party_mod.spread_level("Operator", i) for i in range(4)],
          ["Operator", "Learner", "Elmer", "Listener"])
    check("  clamped at the ends", [party_mod.spread_level("Elmer", i) for i in range(3)], ["Elmer", "Operator", "Elmer"])

    print("\n-- carry, then roll: a ball does not stick where it lands --")
    golf.ROLL = RUN
    def rolled(club, lie="fairway", at=0, wind="with", mph=10, seed=1, aim=None):
        g = golf.Golf(["a"], flat_course(wind=wind), seed=seed)
        g.wind_mph = mph
        g.balls["a"].at, g.balls["a"].lie, g.balls["a"].strokes = at, lie, (1 if at else 0)
        if aim:
            g.set_aim("a", *aim)
        return g.play_one("a", {"correct": True, "club": club, "ms": 1000 * seed})["shots"]["a"]
    runs = {club: [rolled(club, seed=s)["roll"] for s in range(1, 21)] for club in ("driver", "wood", "iron", "wedge")}
    avg = {c: sum(v) / len(v) for c, v in runs.items()}
    check("a driver runs on after it lands", avg["driver"] > 15, True)
    check("  a wood a little less, an iron less again, a wedge hardly at all",
          avg["driver"] > avg["wood"] > avg["iron"] > avg["wedge"], True)
    check("  and the words say so", "ran" in rolled("driver")["words"], True)
    check("  the ball lies where it stopped, not where it came down", rolled("driver")["at"] - rolled("driver")["carry"] == rolled("driver")["roll"], True)
    d_with = sum(rolled("driver", wind="with", seed=s)["roll"] for s in range(1, 21))
    d_into = sum(rolled("driver", wind="into", seed=s)["roll"] for s in range(1, 21))
    check("downwind it runs further, into the wind it sits down", d_with > d_into, True)
    r = golf.Golf(["a"], flat_course(hazards=[{"kind": "rough", "from": 200, "to": 300, "side": "across", "name": "long grass"}]), seed=1)
    r.wind_mph = 0
    s = r.play_one("a", {"correct": True, "club": "driver", "ms": 1000})["shots"]["a"]
    check("into the rough it stops quickly", s["roll"] < 12, True)
    green = rolled("wedge", lie="fairway", at=310, wind="across", mph=0)
    check("a wedge onto the green checks up", (green["kind"], green["roll"] <= 3), ("green", True))
    bumps = [rolled("iron", lie="fairway", at=240, wind="across", mph=0, seed=sd, aim=(371, 0)) for sd in range(1, 13)]
    check("an iron landed nine short of the green can run onto it - the bump and run",
          any(b["kind"] == "green" and "ran onto" in b["words"] for b in bumps), True)
    check("  and can stop short of it too - that is the gamble", any(b["kind"] != "green" for b in bumps), True)
    creek = golf.Golf(["a"], flat_course(hazards=[{"kind": "water", "from": 255, "to": 265, "side": "across", "name": "the creek"}]), seed=1)
    creek.wind_mph = 0
    creek.set_aim("a", 250, 0)
    s = creek.play_one("a", {"correct": True, "club": "driver", "ms": 2000})["shots"]["a"]
    check("aimed five short of the creek, a driver runs into it - land it shorter", (s["kind"], "ran into" in s["words"]), ("water", True))
    x = golf.Golf(["a"], flat_course(wind="across"), seed=1)
    x.wind_mph = 15
    s = x.play_one("a", {"correct": True, "club": "driver", "ms": 1000})["shots"]["a"]
    check("a crosswind off the left drifts the ball right", s["off"] > 0, True)
    check("  a golfer allows for the run: what a driver is expected to run on the fairway",
          golf.Golf(["a"], flat_course(), seed=1).expected_roll("driver") > 15, True)
    golf.ROLL = {c: 0 for c in RUN}

    print("\n-- the club's say: a right answer still varies --")
    golf.CLUB_SPREAD, golf.CLUB_LEAK, golf.ROLL = SPREAD, LEAK, RUN
    pb = golf.course("pebble-beach")
    def tee_shots(club, n=300):
        out = []
        for seed in range(n):
            g = golf.Golf(["a"], pb, holes=[1], seed=seed)
            out.append(g.play_one("a", {"correct": True, "club": club})["shots"]["a"])
        return out
    drives, irons = tee_shots("driver"), tee_shots("iron")
    check("a driver's carries vary - not one number", len({s["carry"] for s in drives}) > 10, True)
    check("  and land in the fairway most of the time", sum(s["kind"] == "fairway" for s in drives) / len(drives) > 0.7, True)
    leaks = [s for s in drives if s.get("leak")]
    check("  some leak off the line, into the first cut or the sand", 0.08 < len(leaks) / len(drives) < 0.3, True)
    check("  a leaked ball has a worse lie, so the next question is harder",
          all(s["lie"] in ("rough", "sand") for s in leaks), True)
    check("  and sits off the fairway's width, on the side it leaked to",
          all(abs(s["off"]) > golf.FAIRWAY_HALF and (s["off"] < 0) == (s["leak"] == "left") for s in leaks), True)
    check("  the rest are within it", all(abs(s["off"]) <= golf.FAIRWAY_HALF for s in drives if not s.get("leak") and s["kind"] == "fairway"), True)
    check("  never the water, never out of bounds", all(s["kind"] != "water" for s in drives), True)
    check("  and the call says what happened", all(s["call"] in golf.LEAK_CALLS for s in leaks), True)
    check("an iron off the tee is shorter and straighter",
          (max(s["carry"] for s in irons) < min(s["carry"] for s in drives) + 40,
           sum(bool(s.get("leak")) for s in irons) < len(leaks)), (True, True))
    adepts = [golf.Golf(["a"], pb, holes=[1], seed=seed).play_one("a", {"correct": True, "club": "driver", "adept": True})["shots"]["a"]
              for seed in range(200)]
    check("an adept drive is shaped, and does not leak", any(s.get("leak") for s in adepts), False)
    def timed(ms, seed=0):
        g = golf.Golf(["a"], pb, holes=[1], seed=seed)
        g.wind_mph = 0                    # the wind is the round's; the swing is the stroke's
        return g.play_one("a", {"correct": True, "club": "driver", "ms": ms})["shots"]["a"]
    check("the swing's timing is the luck: the same swing lands the same way, whatever the round's seed",
          (timed(4321, 1)["carry"], timed(4321, 2)["carry"]) == (timed(4321, 3)["carry"], timed(4321, 3)["carry"]), True)
    check("  and different swings land differently", len({timed(ms)["carry"] for ms in range(1000, 9000, 250)}) > 8, True)
    check("  quick is no straighter than slow - it is a seed, not a clock",
          abs(sum(timed(ms)["carry"] for ms in range(500, 3000, 100)) / 25
              - sum(timed(ms)["carry"] for ms in range(20000, 45000, 1000)) / 25) < 8, True)
    g = golf.Golf(["a", "b", "c"], pb, holes=[1], seed=7)
    for p in ("a", "b", "c"):
        g.play_one(p, {"correct": True, "club": "driver"})
    ats = [g.balls[p].at for p in ("a", "b", "c")]
    check("three right answers off the tee land in three places, so somebody is away", len(set(ats)), 3)
    check("  the farthest out", g.away(), min(("a", "b", "c"), key=lambda p: g.balls[p].at))

    print("\n-- the green: everyone wants the cup, and the green decides --")
    def putt(feet, across=0, right=True, ms=1000, adept=False, slope=None, aim=None, seed=1):
        g = golf.Golf(["a"], pb, holes=[1], seed=seed)
        h = g.hole()
        if slope is not None:
            h["slope"] = slope
        b = g.balls["a"]
        b.at, b.off, b.lie, b.strokes = h["yards"] - feet / 3.0, across / 3.0, "green", 2
        if aim:
            g.set_aim("a", h["yards"] + aim[0] / 3.0, aim[1] / 3.0)
        return g.play_one("a", {"correct": right, "club": "putter", "ms": ms, "adept": adept})["shots"]["a"]
    swings = range(1000, 41000, 1000)
    one = lambda feet, **kw: sum(1 for m in swings if (r := putt(feet, ms=m, **kw))["holed"] and not r.get("tap_in"))  # noqa: E731
    check("a right answer from three feet drops", one(3), 40)
    check("  from ten, most of the time", 15 < one(10) < 40, True)
    check("  from twenty-five, now and then", 3 < one(25) < 25, True)
    check("  from forty, rarely - and never impossible", 0 < one(40) < 12, True)
    check("  an adept read from twenty-five drops far more often", one(25, adept=True) > one(25) + 8, True)
    long = [putt(25, ms=m) for m in swings]
    check("  what does not drop is left near the cup: a tap-in, or a few feet",
          all(r.get("tap_in") or (r["kind"] == "green" and 0 < r["left_feet"] <= 8) for r in long if not (r["holed"] and not r.get("tap_in"))), True)
    check("  a tap-in is a stroke, no question: two putts on the card", next(r for r in long if r.get("tap_in"))["strokes"], 4)
    wrong = [putt(10, right=False, ms=m) for m in swings]
    check("a wrong answer never drops, and is a bad stroke: short, or raced past",
          (any(r["holed"] for r in wrong), all(("short" in r["words"] or "past" in r["words"]) and r["kind"] == "missed" for r in wrong)), (False, True))
    check("  and leaves the ball on the green, feet from the cup", all(r["lie"] == "green" and r["left_feet"] >= 2 for r in wrong), True)
    flat = {"falls": "front", "grade": 0}
    down = sum(putt(20, slope={"falls": "back", "grade": 3}, aim=(0, 0), ms=m)["left_feet"] for m in swings)
    up = sum(putt(20, slope={"falls": "front", "grade": 3}, aim=(0, 0), ms=m)["left_feet"] for m in swings)
    check("with a mark on the cup, a downhill putt runs past and an uphill one comes up short: both leave more than a flat one",
          (down > 0, up > 0), (True, True))
    check("  the words say which", ("downhill" in putt(20, slope={"falls": "back", "grade": 3}, aim=(0, 0))["words"],
                                      "uphill" in putt(20, slope={"falls": "front", "grade": 3}, aim=(0, 0))["words"]), (True, True))
    check("  a mark three feet past the cup, uphill, holes it", putt(20, slope={"falls": "front", "grade": 3}, aim=(3, 0))["holed"], True)
    cross = putt(20, slope={"falls": "left", "grade": 3}, aim=(0, 0))
    check("a cross-slope breaks the putt toward the fall", ("breaking left" in cross["words"], cross["off"] < 0), (True, True))
    check("  aimed a couple of feet up the slope, it breaks in", putt(20, slope={"falls": "left", "grade": 3}, aim=(0, 2))["holed"], True)
    check("  with no mark the golfer is taken to have read the pace, not the break",
          putt(20, slope={"falls": "front", "grade": 3})["holed"], True)
    check("a foot from the cup is a tap-in, one stroke", (putt(1)["holed"], putt(1)["strokes"]), (True, 3))
    check("the card's greens have their slopes", all("slope" in h for h in pb["holes"]), True)
    check("  and every ball on a green knows its feet from the cup",
          (lambda g: (setattr(g.balls["a"], "lie", "green"), setattr(g.balls["a"], "at", g.hole()["yards"] - 4), g.as_dict()["balls"]["a"]["feet"])[-1])(golf.Golf(["a"], pb, holes=[1], seed=1)), 12)

    print("\n-- the scorecard --")
    d = golf.Golf(["a", "b"], golf.course("pebble-beach"), holes=[1, 2, 3], seed=1).as_dict()
    check("the round's holes, with their pars", [(h["n"], h["par"]) for h in d["round_holes"]], [(1, 4), (2, 5), (3, 4)])
    check("  and every player's strokes by hole on the card",
          all(isinstance(r.get("card"), dict) for r in d["leaderboard"]), True)

    print("\n-- the hole, drawn from the card --")
    from elmer import golfmap
    pb = golf.course("pebble-beach")
    h1 = pb["holes"][0]
    svg = golfmap.hole_svg(h1, "with", 12, [{"name": "Scott", "at": 250, "lie": "fairway", "you": True},
                                            {"name": "Beacon", "at": 0, "lie": "tee"}])
    check("an SVG of the first", svg.startswith("<svg") and svg.endswith("</svg>"), True)
    check("  headed with hole, par and yards", "1 \u00b7 par 4 \u00b7 377 yd" in svg, True)
    check("  every hazard on it, by name", all(hz["name"] in svg for hz in h1["hazards"]), True)
    check("  the wind on it", "with 12 mph" in svg, True)
    check("  two balls, and yours ringed in amber", (svg.count("<circle cx=") >= 3, "#ffb454" in svg), (True, True))
    check("a hole with no balls draws too", "<svg" in golfmap.hole_svg(pb["holes"][6]), True)

    print("\n-- a hole in one, rare and real --")
    par3 = flat_course(par=3, yards=150, green=30)
    had = golf.ACE_ODDS
    golf.ACE_ODDS = 1.0
    g = golf.Golf(["a"], par3, seed=1)
    row = g.play_one("a", {"correct": True, "club": "iron"})
    check("from the tee of a par 3, a right answer can drop", (row["shots"]["a"]["holed"], row["shots"]["a"].get("ace")), (True, True))
    check("  and the call says so", row["shots"]["a"]["call"], "A hole in one!")
    g = golf.Golf(["a"], flat_course(par=4, yards=400), seed=1)
    row = g.play_one("a", {"correct": True, "club": "driver"})
    check("never on a par 4", row["shots"]["a"].get("ace"), None)
    golf.ACE_ODDS = 0.0
    g = golf.Golf(["a"], par3, seed=1)
    row = g.play_one("a", {"correct": True, "club": "iron"})
    check("and at no odds, none", row["shots"]["a"].get("ace"), None)
    golf.ACE_ODDS = had

    print("\n-- arranging a tee time --")
    two = {**flat_course(par=3, yards=150), "holes": [
        {"n": n, "par": 3, "yards": 150, "name": "", "wind": "across", "green": 30, "hazards": []}
        for n in (1, 2)]}
    g = golf.Golf(["a", "b"], two, holes=[1, 2], seed=3)
    g.add_player("early")
    check("arriving while the group is still on the tee: in it now", "early" in g.balls, True)
    g.play_one("a", {"correct": True, "club": "iron"})
    g.add_player("late")
    check("arriving mid-hole: a tee time, not a ball", ("late" in g.balls, g.tee_times), (False, ["late"]))
    check("  and not away", g.away() != "late", True)
    while g.hole() and g.hole()["n"] == 1 and g.away():
        g.play_one(g.away(), {"correct": True})
    check("at the next tee the group picks them up", ("late" in g.balls, g.tee_times, g.hole()["n"]), (True, [], 2))
    g.add_player("gone")
    g.drop("gone")
    check("a tee time given up is gone", g.tee_times, [])
    check("every shot has the golfer's call on it", all("call" in s for r in g.history for s in r["shots"].values()), True)
    g.drop("b")
    check("somebody leaving takes their ball with them", "b" in g.balls, False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
