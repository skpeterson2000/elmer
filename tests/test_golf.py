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
    # The roll is taken out at its root now rather than club by club: it
    # used to be a yards-per-club table, and is the one scale factor on
    # the arrival-against-friction model that replaced it. Same intent -
    # no run, so a carry can be asserted exactly.
    SPREAD, LEAK, RUN = dict(golf.CLUB_SPREAD), dict(golf.CLUB_LEAK), golf.ROLL_BASE
    golf.CLUB_SPREAD = {c: 0 for c in SPREAD}
    golf.CLUB_LEAK = {c: 0.0 for c in LEAK}
    golf.ROLL_BASE = 0.0
    # And the day's life - the gust, the kick, the spin - off with them,
    # and on again for the section about the ground.
    GUST, KICK, SPIN = golf.Day.GUST, golf.KICK_ODDS, dict(golf.SPIN_ODDS)
    golf.Day.GUST, golf.KICK_ODDS, golf.SPIN_ODDS = (1.0, 1.0), 0.0, {}

    print("\n-- the shot --")
    g = golf.Golf(["a"], flat_course(), seed=1, seconds=30)
    check("from the tee, every club", g.clubs_for("a"), list(golf.CLUB_ORDER))
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
    # Flown, not reckoned: a driver into ten miles an hour now loses what a
    # caddie would tell you, about five percent, where the old table took
    # eight yards off everything.
    check("ten into the wind takes twelve yards off a driver", row["shots"]["a"]["carry"], 238)
    g = golf.Golf(["a"], flat_course(wind="with"), seed=1, seconds=30)
    g.wind_mph = 10
    row = g.play({"a": R(True, ms=1000, club="5-wood")})
    check("ten behind gives a 5-wood seven", row["shots"]["a"]["carry"], 217)
    check("  and the wind in the face costs more than the same wind behind gives",
          -golf.wind_on_carry("driver", 1.0, 12, 10) > golf.wind_on_carry("driver", 1.0, 6, 10), True)

    print("\n-- the course has its say --")
    creek = golf.Golf(["a"], flat_course(hazards=[{"kind": "water", "from": 240, "to": 260,
                                                     "side": "across", "name": "the creek"}]), seed=1)
    row = creek.play({"a": R(True, ms=1000, club="driver")})
    check("a fast driver into a creek across the fairway is in the creek", row["shots"]["a"]["kind"], "water")
    check("  a drop short of it and a penalty: two strokes, on the fairway three yards short of the creek",
          (creek.balls["a"].strokes, creek.balls["a"].at, creek.balls["a"].lie, "dropped short of the creek" in row["shots"]["a"]["words"]),
          (2, 237, "fairway", True))
    side = golf.Golf(["a"], flat_course(hazards=[{"kind": "bunker", "from": 240, "to": 260,
                                                    "side": "right", "name": "a bunker"}]), seed=1)
    row = side.play({"a": R(True, ms=1000, club="driver")})
    check("a bunker off to the right does not catch a fair ball down the middle", row["shots"]["a"]["kind"], "fairway")
    side = golf.Golf(["a"], flat_course(hazards=[{"kind": "bunker", "from": 240, "to": 260,
                                                    "side": "right", "name": "a bunker"}]), seed=1)
    row = side.play({"a": R(False, club="5-wood")})
    check("a foul wood cannot reach a bunker at 240", row["shots"]["a"]["kind"], "rough")
    side = golf.Golf(["a"], flat_course(hazards=[{"kind": "bunker", "from": 240, "to": 260,
                                                    "side": "right", "name": "a bunker"}]), seed=1)
    row = side.play({"a": R(False, club="driver")})
    check("but a foul driver finds it", (row["shots"]["a"]["kind"], side.balls["a"].lie), ("sand", "sand"))
    check("  from where only a wedge is allowed", side.clubs_for("a"), ["pitching-wedge", "sand-wedge"])
    row = side.play({"a": R(True, ms=1000, club="sand-wedge")})
    check("  and a wedge from sand is sixty percent of one", row["shots"]["a"]["carry"], 63)
    far = golf.Golf(["a"], flat_course(hazards=[{"kind": "water", "from": 300, "to": 320,
                                                   "side": "across", "name": "a pond"}]), seed=1)
    row = far.play({"a": R(False, club="sand-wedge")})
    check("a foul wedge cannot find a pond two hundred yards on", row["shots"]["a"]["kind"], "rough")
    check("  it went forward a little", far.balls["a"].at > 0, True)

    print("\n-- the green, and holing out --")
    g = golf.Golf(["a"], flat_course(par=3, yards=150, green=30), seed=1)
    row = g.play({"a": R(True, ms=1000, club="7-iron")})
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
        row = g.play({"a": R(False, club="sand-wedge")})
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
    # Nor the gusts: each stroke meets its own, and since the ball is flown
    # through the wind rather than reckoned from a table, a gust moves an
    # aimed shot as much as a full one.
    GUSTS = golf.Day.GUST
    golf.Day.GUST = (1.0, 1.0)
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
    if ann["gross"] != bob["gross"]:
        print("  board:", board)
        for p in ("ann", "bob"):
            print("  ", p, g.logs.get(p))
    check("  gross is the same, so the net leads", (ann["gross"] == bob["gross"], board[0]["player"]), (True, "bob"))
    golf.HOLE_OUT_ODDS = HOLE_OUT
    golf.Day.GUST = GUSTS
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
    row = g.play({"a": R(True, ms=3000, club="7-iron")})        # the iron can reach: aimed at the pin
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
    side = golf.Golf(["a", "b"], flat_course(), seed=1)
    side.balls["a"].at, side.balls["a"].off, side.balls["a"].lie, side.balls["a"].strokes = 399, 15, "fringe", 2
    side.balls["b"].at, side.balls["b"].off, side.balls["b"].lie, side.balls["b"].strokes = 397, 0, "green", 2
    check("  as the crow flies: pin-high on the collar fifteen yards out is farther than three yards short on the green", side.away(), "a")
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
    g2.play_one("a", {"correct": False, "club": "7-iron"})      # a into the rough
    g2.play_one("b", {"correct": True, "club": "7-iron"})       # b on the green
    while g2.hole() and g2.hole()["n"] == 1:
        g2.play_one(g2.away(), {"correct": True})
    check("the honor on the next tee goes to the better score", (g2.cards["a"][1] > g2.cards["b"][1], g2.away()), (True, "b"))

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
    g.play_one("a", {"correct": False, "club": "7-iron", "question_id": q1})     # a miss, into the rough
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
    tee = [g.hardness[g.choose(list(g.hardness), "a")] for _ in range(300)]
    check("from the tee, the draw leans easy", sum(tee) / len(tee) < 0.45, True)
    g.balls["a"].lie = "sand"
    sand = [g.hardness[g.choose(list(g.hardness), "a")] for _ in range(300)]
    check("from the sand, it leans hard", sum(sand) / len(sand) > 0.6, True)
    g.balls["a"].lie = "fairway"
    check("  but every question can come - the three nearest were all it used to show",
          len({g.choose(list(g.hardness), "a") for _ in range(400)}), 11)
    check("a question nobody here has met comes first", g.choose(list(g.hardness), "a", seen=set(g.hardness) - {"Q0"}), "Q0")
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
    row = g.play_one("a", {"correct": True, "club": "5-wood", "adept": True})
    check("from the rough, adept: worked out of it, the lie not costing, the sand not catching",
          (row["shots"]["a"].get("flair"), row["shots"]["a"]["kind"]), ("worked", "fairway"))
    g = golf.Golf(["a"], flat_course(par=4, yards=400), seed=2)
    g.balls["a"].at = 370; g.balls["a"].lie = "fairway"; g.balls["a"].strokes = 2
    row = g.play_one("a", {"correct": True, "club": "sand-wedge", "adept": True})
    check("a wedge from thirty out, adept: a flop to a tap-in, or holed",
          row["shots"]["a"].get("flair") in ("flop", "holed-out"), True)
    holed = 0
    for seed in range(40):
        g = golf.Golf(["a"], flat_course(par=4, yards=400), seed=seed)
        g.balls["a"].at = 300; g.balls["a"].lie = "fairway"; g.balls["a"].strokes = 1
        if g.play_one("a", {"correct": True, "club": "7-iron", "adept": True})["shots"]["a"].get("flair") == "holed-out":
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
    # A hazard is somewhere across the hole as well as along it, and the
    # ball has to be at both. A side hazard's stated offset is measured from
    # the fairway's edge, so this trap sits twelve yards into the left rough
    # - thirty yards off the line, on a fairway eighteen yards to a side.
    trap = [{"kind": "bunker", "from": 230, "to": 260, "side": "left",
             "off": -12, "name": "the left trap"}]
    check("a side hazard's offset is read from the fairway's edge",
          [(round(c), round(w)) for c, w in golf.hazard_spans(flat_course()["holes"][0], trap[0])],
          [(-30, 8)])
    bunker = golf.Golf(["a"], flat_course(hazards=trap), seed=1)
    bunker.set_aim("a", 250, -30)
    s = bunker.play_one("a", {"correct": True, "club": "driver"})["shots"]["a"]
    check("  aimed at it: in the sand", (s["kind"], s["hazard"], bunker.balls["a"].off), ("sand", "the left trap", -30))
    # The bug this was reported as: a drive down the middle, called on the
    # fairway, drawn in the bunker - because the rule asked only which side
    # of the line the ball was on and every left-hand hazard caught it.
    middle = golf.Golf(["a"], flat_course(hazards=trap), seed=1)
    middle.set_aim("a", 250, -10)
    s = middle.play_one("a", {"correct": True, "club": "driver"})["shots"]["a"]
    check("  ten yards left of the line, inside the fairway, past nothing: the fairway",
          (s["kind"], middle.balls["a"].lie), ("fairway", "fairway"))
    # And the other half of it: a ball far wider than the trap is wider than
    # the trap, and used to be called into it anyway.
    past = golf.Golf(["a"], flat_course(hazards=trap), seed=1)
    past.set_aim("a", 250, -46)
    s = past.play_one("a", {"correct": True, "club": "driver"})["shots"]["a"]
    check("  forty-six yards left, well past it: the rough, not the sand",
          (s["kind"], past.balls["a"].lie), ("rough", "rough"))
    wide = golf.Golf(["a"], flat_course(), seed=1)
    wide.set_aim("a", 250, 30)
    s = wide.play_one("a", {"correct": True, "club": "driver"})["shots"]["a"]
    check("aimed thirty right with nothing there: the first cut", (s["kind"], wide.balls["a"].lie, wide.balls["a"].off), ("rough", "rough", 30))
    check("  and the next club is the rough's longest", wide.clubs_for("a")[0], "5-wood")
    wide.set_aim("a", 400, 0)
    s = wide.play_one("a", {"correct": True, "club": "5-wood"})["shots"]["a"]
    check("  back at the pin: on the line, and the wood reaches from there", (s["off"], s["kind"]), (0, "green"))
    edge = golf.Golf(["a"], flat_course(), seed=1)
    edge.balls["a"].at, edge.balls["a"].lie, edge.balls["a"].strokes = 300, "fairway", 1
    edge.set_aim("a", 400, 20)
    s = edge.play_one("a", {"correct": True, "club": "7-iron"})["shots"]["a"]
    check("pin-high but twenty yards wide of a green fourteen wide: not on it", s["kind"] != "green", True)
    check("a mark behind the ball is moved ahead of it", golf.Golf(["a"], flat_course(), seed=1).set_aim("a", -50, 0)["at"], 10)
    check("  and one off the property is brought in", golf.Golf(["a"], flat_course(), seed=1).set_aim("a", 200, 900)["off"], golf.OFF_MOST)
    check("a mark on the green is kept in feet - a yard past the cup", (lambda g: (setattr(g.balls["a"], "lie", "green"), g.set_aim("a", 401, 0))[1])(golf.Golf(["a"], flat_course(), seed=1)), {"at": 401.0, "off": 0.0})
    foul = golf.Golf(["a"], flat_course(hazards=[{"kind": "bunker", "from": 230, "to": 260, "side": "right", "name": "the right trap"}]), seed=3)
    s = foul.play_one("a", {"correct": False, "club": "driver"})["shots"]["a"]
    check("a foul ball into a side trap is off on that side", (s["kind"], foul.balls["a"].off > golf.FAIRWAY_HALF), ("sand", True))
    short = golf.Golf(["a"], flat_course(), seed=5)
    s = short.play_one("a", {"correct": False, "club": "sand-wedge"})["shots"]["a"]
    check("a foul ball short into the rough is beside the fairway, not down the middle of it",
          (s["kind"], abs(short.balls["a"].off) > golf.FAIRWAY_HALF, ("left" in s["words"]) != ("right" in s["words"])), ("rough", True, True))

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
          (h2.default_club("a"), h2.default_club("b")), ("5-wood", "driver"))
    from elmer import party as party_mod
    check("a spread of levels around the one chosen", [party_mod.spread_level("Operator", i) for i in range(4)],
          ["Operator", "Learner", "Elmer", "Listener"])
    check("  clamped at the ends", [party_mod.spread_level("Elmer", i) for i in range(3)], ["Elmer", "Operator", "Elmer"])

    print("\n-- carry, then roll: a ball does not stick where it lands --")
    golf.ROLL_BASE = RUN
    def rolled(club, lie="fairway", at=0, wind="with", mph=10, seed=1, aim=None):
        g = golf.Golf(["a"], flat_course(wind=wind), seed=seed)
        g.wind_mph = mph
        g.balls["a"].at, g.balls["a"].lie, g.balls["a"].strokes = at, lie, (1 if at else 0)
        if aim:
            g.set_aim("a", *aim)
        return g.play_one("a", {"correct": True, "club": club, "ms": 1000 * seed})["shots"]["a"]
    runs = {club: [rolled(club, seed=s)["roll"] for s in range(1, 21)] for club in ("driver", "5-wood", "7-iron", "sand-wedge")}
    avg = {c: sum(v) / len(v) for c, v in runs.items()}
    check("a driver runs on after it lands", avg["driver"] > 15, True)
    check("  a wood a little less, an iron less again, a wedge hardly at all",
          avg["driver"] > avg["5-wood"] > avg["7-iron"] > avg["sand-wedge"], True)
    check("  and the words say so", "ran" in rolled("driver")["words"], True)
    check("  the ball lies where it stopped, not where it came down", rolled("driver")["at"] - rolled("driver")["carry"] == rolled("driver")["roll"], True)
    d_with = sum(rolled("driver", wind="with", seed=s)["roll"] for s in range(1, 21))
    d_into = sum(rolled("driver", wind="into", seed=s)["roll"] for s in range(1, 21))
    check("downwind it runs further, into the wind it sits down", d_with > d_into, True)
    r = golf.Golf(["a"], flat_course(hazards=[{"kind": "rough", "from": 200, "to": 300, "side": "across", "name": "long grass"}]), seed=1)
    r.wind_mph = 0
    s = r.play_one("a", {"correct": True, "club": "driver", "ms": 1000})["shots"]["a"]
    check("into the rough it stops quickly", s["roll"] < 12, True)
    green = rolled("sand-wedge", lie="fairway", at=310, wind="across", mph=0)
    check("a wedge onto the green releases a little, or bites and comes back - a green is clipped to nothing", (green["kind"], -5 <= green["roll"] <= 8), ("green", True))
    fast = golf.Golf(["a"], flat_course(), seed=1)
    check("  the green runs faster than the fairway, and the fringe is between",
          (fast.expected_roll("5-wood", "green") > fast.expected_roll("5-wood", "fairway") > fast.expected_roll("5-wood", "fringe") > fast.expected_roll("5-wood", "rough")), True)
    golf.CLUB_SPREAD, golf.KICK_ODDS = {c: 0 for c in SPREAD}, 0.0
    beside = golf.Golf(["a"], flat_course(), seed=1)
    beside.day.wind_mph = 0
    beside.balls["a"].at, beside.balls["a"].lie, beside.balls["a"].strokes = 320, "fairway", 1
    beside.set_aim("a", 395, 18)
    b = beside.play_one("a", {"correct": True, "club": "sand-wedge", "ms": 3})["shots"]["a"]
    golf.CLUB_SPREAD, golf.KICK_ODDS = SPREAD, KICK
    check("  beside the green, off its collar, is rough - the fringe is bordered by it", (b["kind"], beside.balls["a"].lie), ("rough", "rough"))
    bumps = [rolled("7-iron", lie="fairway", at=240, wind="across", mph=0, seed=sd, aim=(371, 0)) for sd in range(1, 13)]
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
    golf.ROLL_BASE = 0.0

    print("\n-- the club's say: a right answer still varies --")
    golf.CLUB_SPREAD, golf.CLUB_LEAK, golf.ROLL_BASE = SPREAD, LEAK, RUN
    golf.Day.GUST, golf.KICK_ODDS, golf.SPIN_ODDS = GUST, KICK, SPIN
    pb = golf.course("pebble-beach")
    def tee_shots(club, n=300):
        out = []
        for seed in range(n):
            g = golf.Golf(["a"], pb, holes=[1], seed=seed)
            out.append(g.play_one("a", {"correct": True, "club": club})["shots"]["a"])
        return out
    drives, irons = tee_shots("driver"), tee_shots("7-iron")
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
    # Across rounds, not in one: three drives spread over thirty-odd yards
    # and read in whole yards tie now and then, and one round's tie is
    # chance, not a fault. What matters is that it is rare.
    apart = 0
    for seed in range(20):
        g = golf.Golf(["a", "b", "c"], pb, holes=[1], seed=seed)
        for p in ("a", "b", "c"):
            g.play_one(p, {"correct": True, "club": "driver"})
        apart += len({g.balls[p].at for p in ("a", "b", "c")}) == 3
    check("three right answers off the tee land in three places, so somebody is away", apart >= 15, True)
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
    h8 = next(x for x in pb["holes"] if x["n"] == 8)
    plan8 = golfmap.Plan(h8)
    before, turn, after = plan8.at(100, 0), plan8.at(h8["bend"]["at"], 0), plan8.at(h8["yards"], 0)
    import math as _math
    leg1 = _math.degrees(_math.atan2(turn[0] - before[0], before[1] - turn[1]))
    leg2 = _math.degrees(_math.atan2(after[0] - turn[0], turn[1] - after[1]))
    check("the 8th bends right past the corner, at the card's angle, and the plan draws it so",
          (golfmap.bend_of(h8)["dir"], round(leg2 - leg1)), (1, h8["bend"]["degrees"]))
    check("  the same yard both ways: a yard off the line is a yard along it",
          round(_math.hypot(*(a - b for a, b in zip(plan8.at(200, 10), plan8.at(200, 0)))), 1) == round(_math.hypot(*(a - b for a, b in zip(plan8.at(210, 0), plan8.at(200, 0)))), 1), True)
    check("  and a tap's yards come back: the legs a screen projects onto are on the page",
          (golfmap.geometry(h8)["view"], len(golfmap.geometry(h8)["legs"]), golfmap.geometry(h8)["legs"][1]["at0"]), ("plan", 2, h8["bend"]["at"]))
    check("  and the geometry a screen turns a tap with carries the bend", golfmap.geometry(h8)["bend"]["at"], h8["bend"]["at"])
    narrow = golf.Golf(["a"], flat_course(), seed=1)
    narrow.hole()["width"] = 10
    narrow.set_aim("a", 250, 14)
    # read with the spread and the kick off: this is about the width
    golf.CLUB_SPREAD, golf.KICK_ODDS = {c: 0 for c in SPREAD}, 0.0
    s = narrow.play_one("a", {"correct": True, "club": "driver"})["shots"]["a"]
    golf.CLUB_SPREAD, golf.KICK_ODDS = SPREAD, KICK
    check("a hole's own width is the rules' width: fourteen yards off on a ten-yard lane is the first cut", s["kind"], "rough")

    print("\n-- the fringe: the collar brakes a ball, and can be putted from --")
    golf.CLUB_SPREAD, golf.KICK_ODDS, LEAK = {c: 0 for c in SPREAD}, 0.0, dict(golf.CLUB_LEAK)
    golf.CLUB_LEAK = {c: 0 for c in LEAK}
    check("the green's edge is its half depth and a bit; the fringe three yards more",
          (golf.green_edge({"green": 30}), golf.on_the_green({"yards": 400, "green": 30}, 380, 0), golf.on_the_green({"yards": 400, "green": 30}, 378, 0),
           golf.on_the_green({"yards": 400, "green": 30}, 376, 0), golf.on_the_green({"yards": 400, "green": 30}, 390, 16), golf.on_the_green({"yards": 400, "green": 30}, 390, 18)),
          (20.0, "green", "fringe", None, "fringe", None))
    def from_(at, club, mark, ms=1):
        g = golf.Golf(["a"], flat_course(), seed=2)
        g.day.wind_mph = 0
        g.balls["a"].at, g.balls["a"].lie, g.balls["a"].strokes = at, "fairway", 1
        g.set_aim("a", *mark)
        return g, g.play_one("a", {"correct": True, "club": club, "ms": ms})["shots"]["a"]
    g, s = from_(320, "sand-wedge", (378, 0))
    check("a wedge chipped onto the collar stops on it, in feet from the cup", (s["kind"], g.balls["a"].lie, s["feet"] > 0, "fringe" in s["words"]), ("fringe", "fringe", True, True))
    check("  from there: bump a 7-iron, chip a wedge, or putt", g.clubs_for("a"),
          ["7-iron", "8-iron", "9-iron", "pitching-wedge", "sand-wedge", "putter"])
    check("  and the putter, through the collar, is the sensible one", g.default_club("a"), "putter")
    check("  and the hazards in the line are nobody's business from there", g.ahead("a"), [])
    rolls = {}
    for ms in (1, 2, 3):
        _, on = from_(210, "5-wood", (378, 0), ms)
        _, short = from_(210, "5-wood", (374, 0), ms)
        rolls[ms] = (on["roll"], short["roll"], on["kind"], on.get("via"))
    check("a wood landed on the fringe runs less than one landed on the fairway just short of it",
          all(a < b for a, b, _k, _v in rolls.values()), True)
    check("  and trickles through the collar onto the green, which the words say", all(k == "green" and v == "fringe" for _a, _b, k, v in rolls.values()), True)
    golf.CLUB_SPREAD, golf.KICK_ODDS, golf.CLUB_LEAK = SPREAD, KICK, LEAK
    putt = golf.Golf(["a"], flat_course(), seed=2)
    putt.balls["a"].at, putt.balls["a"].off, putt.balls["a"].lie, putt.balls["a"].strokes = 379, 0, "fringe", 2
    s = putt.play_one("a", {"correct": True, "club": "putter", "ms": 7})["shots"]["a"]
    check("a putt from the fringe is a putt from the fringe", ("from the fringe" in s["words"], s["putt"], putt.balls["a"].lie in ("green", "fringe")), (True, True, True))
    check("  the ball on the collar is in feet in the state", golf.Golf(["a"], flat_course(), seed=2).as_dict()["balls"]["a"]["feet"], None)
    putt.balls["a"].at, putt.balls["a"].off, putt.balls["a"].lie = 379, 0, "fringe"
    check("  and so it is", putt.as_dict()["balls"]["a"]["feet"], 63)

    print("\n-- the approach: the map zooms when the green is the target --")
    app = golf.Golf(["a"], flat_course(), seed=2)
    check("off the tee, no", app.approaching("a"), False)
    app.balls["a"].at, app.balls["a"].lie = 240, "fairway"
    check("  an iron's length out, with the iron in hand: yes", (app.default_club("a"), app.approaching("a")), ("7-iron", True))
    app.balls["a"].at = 100
    check("  three hundred out, a full swing: no", app.approaching("a"), False)
    app.balls["a"].at, app.balls["a"].lie = 330, "rough"
    check("  seventy out from the rough, whatever the club: yes", app.approaching("a"), True)
    check("  and it travels with the ball's state", app.as_dict()["balls"]["a"]["approaching"], True)
    from elmer import golfmap
    geo = golfmap.geometry_for(app, app.hole(), app.as_dict()["balls"]["a"])
    check("the geometry a screen turns a tap with is the approach's, a yard a yard", (geo["view"], geo["px_per_yard"] > 3, geo["top"]), ("approach", True, 430.0))
    app.balls["a"].lie = "fringe"
    check("  on the fringe it is the green's", golfmap.geometry_for(app, app.hole(), app.as_dict()["balls"]["a"])["view"], "green")
    app.balls["a"].at, app.balls["a"].lie = 100, "fairway"
    check("  from three hundred, the whole hole in plan", golfmap.geometry_for(app, app.hole(), app.as_dict()["balls"]["a"])["view"], "plan")
    svg = golfmap.approach_svg(pb["holes"][6], "into", 9, [{"name": "Scott", "at": 0, "off": 0, "lie": "tee", "you": True}], {"at": 96, "off": -4}, None)
    h7 = pb["holes"][6]
    check("the approach draws the green, the fringe, the sand and the ocean beyond the 7th",
          all(w in svg for w in ["the fringe", "aiming 10 short of the pin, 4 left"] + [z["name"] for z in h7["hazards"]]), True)
    check("  a ball short of the view stands at its foot with its yards", f"you, {h7['yards']} out" in svg, True)
    gsvg = golfmap.green_svg(pb["holes"][0], [], None, None, {"falls": "left", "grade": 2})
    check("the green is drawn with its fall and its sand, not a bullseye", ("falls left" in gsvg, "greenside bunker" in gsvg, "linearGradient" in gsvg, "stroke-dasharray=\"3 3\"" in gsvg), (True, True, True, False))
    check("  and the one green in every view: the same outline seeds them all", golfmap._outline(golfmap._seed(pb["holes"][1], "green")) == golfmap._outline(golfmap._seed(pb["holes"][1], "green")), True)
    check("  a drawn green is never smaller than the rules' green", min(golfmap._outline(1)) >= 1.0, True)
    check("  and a drawn bunker never bigger than its band", max(golfmap._outline(1, inward=True)) <= 1.0, True)

    print("\n-- the mulligan: a foul ball taken back, once a hole --")
    mg = golf.Golf(["a", "b"], flat_course(), seed=3)
    check("nothing to take back before a stroke", mg.can_mulligan("a"), False)
    mg.play_one("a", {"correct": True, "club": "driver"})
    check("  nor after a fair one", mg.can_mulligan("a"), False)
    mg.set_aim("b", 240, -5)
    mg.play_one("b", {"correct": False, "club": "driver"})
    was = (mg.balls["b"].strokes, mg.balls["b"].at, mg.balls["b"].lie)
    check("a foul ball can be", (mg.can_mulligan("b"), was[0] >= 1, was[2]), (True, True, "rough"))
    words = mg.mulligan("b")
    check("  taken back: the ball on the tee, no stroke counted, the mark restored, and the card says so",
          (mg.balls["b"].strokes, mg.balls["b"].at, mg.balls["b"].lie, mg.aim("b")["at"], mg.balls["b"].log, "mulligan" in (words or "")),
          (0, 0, "tee", 240, ["mulligan - a fresh ball from the tee"], True))
    check("  written on the foul ball's row of the history", mg.history[-1]["shots"]["b"].get("mulligan"), words)
    check("  and not twice on a hole", (mg.can_mulligan("b"), mg.mulligan("b")), (False, None))
    mg.play_one("b", {"correct": False, "club": "driver"})
    check("  a second foul ball on the hole stands", mg.can_mulligan("b"), False)
    check("  the state carries whether one may be had", mg.as_dict()["balls"]["b"]["can_mulligan"], False)

    print("\n-- luck, earned by answering along: the near half of the spread, and no leak --")
    def drives(lucky, n=30):
        outs = []
        for sd in range(1, n + 1):
            lk = golf.Golf(["a"], flat_course(), seed=sd)
            lk.day.wind_mph = 0
            if lucky:
                lk.grant_luck("a")
            s = lk.play_one("a", {"correct": True, "club": "driver", "ms": sd * 7})["shots"]["a"]
            outs.append((abs(s["carry"] - golf.CLUBS["driver"]), bool(s.get("leak")), s.get("luck", False)))
        return outs
    plain, lucky = drives(False), drives(True)
    check("luck is spent on the stroke and written on it", (all(l for _c, _k, l in lucky), any(l for _c, _k, l in plain)), (True, False))
    check("  a lucky drive lands nearer its length than a plain one", sum(c for c, _k, _l in lucky) < sum(c for c, _k, _l in plain), True)
    check("  and never leaks", any(k for _c, k, _l in lucky), False)
    lk = golf.Golf(["a"], flat_course(), seed=1)
    lk.grant_luck("a")
    lk.play_one("a", {"correct": True, "club": "driver"})
    check("  one stroke, then it is gone", ("a" in lk.luck, lk.as_dict()["balls"]["a"]["luck"]), (False, False))
    wet = golf.Golf(["a"], flat_course(hazards=[{"kind": "water", "from": 100, "to": 130, "side": "across", "name": "the pond"},
                                               {"kind": "bunker", "from": 140, "to": 160, "side": "left", "name": "a trap"}]), seed=2)
    dry = [wet.balls["a"].lie for _ in range(1)]
    kinds = set()
    for sd in range(1, 16):
        w = golf.Golf(["a"], flat_course(hazards=[{"kind": "water", "from": 100, "to": 130, "side": "across", "name": "the pond"},
                                                 {"kind": "bunker", "from": 140, "to": 160, "side": "left", "name": "a trap"}]), seed=sd)
        w.grant_luck("a")
        kinds.add(w.play_one("a", {"correct": False, "club": "driver"})["shots"]["a"]["kind"])
    check("  on a foul ball, luck keeps it out of the water", "water" in kinds, False)

    print("\n-- a hole in one, rare and real --")
    par3 = flat_course(par=3, yards=150, green=30)
    had = golf.ACE_ODDS
    golf.ACE_ODDS = 1.0
    g = golf.Golf(["a"], par3, seed=1)
    row = g.play_one("a", {"correct": True, "club": "7-iron"})
    check("from the tee of a par 3, a right answer can drop", (row["shots"]["a"]["holed"], row["shots"]["a"].get("ace")), (True, True))
    check("  and the call says so", row["shots"]["a"]["call"], "A hole in one!")
    g = golf.Golf(["a"], flat_course(par=4, yards=400), seed=1)
    row = g.play_one("a", {"correct": True, "club": "driver"})
    check("never on a par 4", row["shots"]["a"].get("ace"), None)
    golf.ACE_ODDS = 0.0
    g = golf.Golf(["a"], par3, seed=1)
    row = g.play_one("a", {"correct": True, "club": "7-iron"})
    check("and at no odds, none", row["shots"]["a"].get("ace"), None)
    golf.ACE_ODDS = had

    print("\n-- arranging a tee time --")
    two = {**flat_course(par=3, yards=150), "holes": [
        {"n": n, "par": 3, "yards": 150, "name": "", "wind": "across", "green": 30, "hazards": []}
        for n in (1, 2)]}
    g = golf.Golf(["a", "b"], two, holes=[1, 2], seed=3)
    g.add_player("early")
    check("arriving while the group is still on the tee: in it now", "early" in g.balls, True)
    g.play_one("a", {"correct": True, "club": "7-iron"})
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

    print("\n-- what lies in the line, at address --")
    from elmer import voice
    pb = golf.course("pebble-beach")
    g = golf.Golf(["a"], pb, seed=1)
    g.holes = [x["n"] for x in pb["holes"]]
    g.hole_index, g.balls["a"] = 0, golf.Ball()
    line = g.ahead("a")
    # The card is measured from GolfTraxx's map of the hole: the tee-shot
    # bunkers are on the left of the 1st, two of them.
    check("from the first tee with the driver, the first fairway bunker on the left is in play",
          [(z["name"], z["side"], z["where"]) for z in line][:1], [("the 1st fairway bunker, left", "left", "in-play")])
    check("  said with its yards", "at 245 yards, on the left, in play" in voice.ahead_words(line), True)
    check("  and the wedge, which cannot spray that far, sees nothing", g.ahead("a", "sand-wedge"), [])
    g.hole_index, g.balls["a"] = 6, golf.Ball()
    line = g.ahead("a")
    check("the seventh: the bunker in front in play, and the Pacific beyond the green on the card",
          ([(z["kind"], z["side"], z["where"]) for z in line][:1], any(z["kind"] == "water" and z["side"] == "beyond" for z in g.hole()["hazards"])),
          ([("bunker", "front", "in-play")], True))
    check("  the narrator has pieces for it", voice.ahead(line)[:2], ["ahead", "a-bunker"])
    g.balls["a"].lie = "green"
    check("on the green there is nothing ahead", g.ahead("a"), [])
    check("nothing ahead is nothing said", (voice.ahead([]), voice.ahead_words([])), ([], ""))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
