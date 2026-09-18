#!/usr/bin/env python3
"""CW Baseball: the rules. Catching is receiving, throwing is sending.

    python3 tests/test_cwball.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401
from elmer import cwball  # noqa: E402
from elmer.cw import plain  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def game(innings=1, seed=1, **kw):
    g = cwball.Baseball({"A": [1, 2], "B": [3, 4, 5]}, {1: "Ann", 2: "Bob", 3: "Cy", 4: "Di", 5: "Ed"},
                        innings=innings, base_wpm=10, seed=seed, **kw)
    g.tick(g.deadline + 1)               # the first pitch
    return g


def people(seed=1, league="little", lineups=None, **kw):
    g = cwball.Baseball(lineups or {"A": [1], "B": [3, 4, 5]}, {1: "Ann", 2: "Bob", 3: "Cy", 4: "Di", 5: "Ed"},
                        innings=1, base_wpm=10, seed=seed, league=league, pitcher="people", **kw)
    g.tick(g.deadline + 1)
    return g


def chain_out(g):
    """Run a clean chain from the fielder's catch to the tag."""
    while g.phase == "field":
        if g.link == "catch":
            g.catch(g.fielder, g.pitch["want"])
        elif g.link == "throw":
            g.throw(g.fielder, g.pitch["key"])
        elif g.link == "tag":
            g.tag(g.fielder, g.pitch.get("throw") or g.pitch["key"])
    return g.last


def run():
    print("\n-- the pitch, from the machine --")
    g = game()
    p = g.pitch
    check("the first inning pitches letters, three of them, at the base speed", (p["kind"], len(p["sent"]), p["thrown_wpm"]), ("letters", 3, 10.0))
    check("  to A's first batter, in the top of the first", (g.batter, g.half, g.batting()), (1, "top", "A"))
    check("  the machine in the little league is a competent pitcher: in the zone", p["call"], "zone")
    check("  with the code to sound it and a window to type it", (bool(p["groups"]), p["window"] >= cwball.COPY_LEAST), (True, True))
    d = g.as_dict(1)
    check("  the screens are not told the text or the call while it is in the air", ("sent" in d["pitch"], "call" in d["pitch"], "text" in d["pitch"]), (False, False, False))
    check("  the batter's device is told it is their swing; everybody holds the pitch", (d["your_link"], d["hold"], g.as_dict(4)["your_link"], g.as_dict(4)["hold"]), ("swing", 1, None, 1))
    check("accuracy is characters right in order", (cwball.accuracy("ESZ", "ESZ"), cwball.accuracy("ESZ", "ESX"), cwball.accuracy("ESZ", "")), (100, 67, 0))
    check("cut numbers read either way: 5NN is 599", (cwball.accuracy_any("W1AW 5NN", "W1AW 599"), cwball.accuracy_any("W1AW 599", "W1AW 5NN"), cwball.uncut("5NN TU")), (100, 100, "599 TU"))
    check("positions: the pitcher turns with the inning, the rest fill in, infield first", g.positions(), {"P": 3, "SS": 4, "1B": 5})
    check("  a short side covers an empty base with the nearest", (g.fielder_at("2B"), g.fielder_at("CF")), (4, 4))

    print("\n-- batting is copying; the take --")
    play = g.swing(1, p["want"])
    check("a clean copy is in play, and the ball goes somewhere by position", (play["result"], g.phase, play["position"] in cwball.INFIELD, g.link), ("in play", "field", True, "catch"))
    check("  a stranger cannot swing", "error" in g.swing(2, "x"), True)
    g2 = game()
    text = g2.pitch["want"]
    play = g2.swing(1, text[:2] + "?")
    check("two of three is a foul: a strike, the count stands at one", (play["result"], g2.strikes, g2.phase), ("foul", 1, "reveal"))
    g2.tick(g2.deadline + 1)
    play = g2.take(1)
    check("  the take, in the little league, is free: no strike", (play["result"], g2.strikes, g2.balls), ("taken", 1, 0))
    g2.tick(g2.deadline + 1)
    play = g2.swing(1, "")
    check("  nothing typed and swung is a strike", (play["result"], g2.strikes), ("strike", 2))
    g2.tick(g2.deadline + 1)
    play = g2.swing(1, g2.pitch["want"][:2] + "?")
    check("  with two strikes a foul is not free: strike three, out", (play["result"], g2.outs, g2.strikes), ("strikeout", 1, 0))
    g3 = game(league="major")
    g3.tick(g3.deadline + 1) if g3.phase != "pitch" else None
    while g3.pitch["call"] != "zone":
        g3.take(1); g3.tick(g3.deadline + 1)
    play = g3.take(1)
    check("in the majors a strike taken is a called strike", (play["result"], g3.strikes, "looking" in play["words"]), ("strike", 1, True))
    g4 = game()
    g4.tick(g4.deadline + 1) if g4.phase != "pitch" else None
    play = g4.tick(g4.deadline + 1)
    check("  a pitch nobody swung at is taken, not swung at", g4.last["result"], "taken")

    print("\n-- fielding: the catch, the throw, the tag --")
    g = game(seed=1)
    g.swing(1, g.pitch["want"])
    f = g.fielder
    play = g.catch(f, g.pitch["want"])
    check("a grounder caught clean goes to the throw, by the same fielder", (g.link, g.fielder, "throw" in play["words"]), ("throw", f, True))
    check("  the wrong player cannot catch or throw", ("error" in g.catch(1, "x"), "error" in g.throw(1, "x")), (True, True))
    play = g.throw(f, g.pitch["key"])
    baseman = g.fielder
    check("  a clean throw goes to the tag, by somebody else, at first", (g.link, baseman != f, g.last["to"]), ("tag", True, "1B"))
    check("  the baseman's device is told it is their tag, and hears the throw - never shown it", (g.as_dict(baseman)["your_link"], bool(g.as_dict(baseman)["pitch"]["throw_groups"]), "throw" in g.as_dict(baseman)["pitch"]), ("tag", True, False))
    play = g.tag(baseman, g.pitch["key"])
    check("  the tag copied clean is the out", (play["result"], g.outs, g.bases), ("out", 1, [None, None, None]))
    g = game(seed=2)
    g.swing(1, g.pitch["want"])
    play = g.catch(g.fielder, g.pitch["want"][:-1] + "?")
    check("a bobbled catch and the runner is safe on first", (play["result"], g.bases[0], g.runs["A"]), ("safe", 1, 0))
    g = game(seed=3)
    g.swing(1, g.pitch["want"])
    play = g.catch(g.fielder, "?")
    check("a catch never made is an error: an extra base", (play["result"], g.bases[1], g.errors["B"]), ("error", 1, 1))
    g = game(seed=4)
    g.swing(1, g.pitch["want"])
    g.catch(g.fielder, g.pitch["want"])
    play = g.throw(g.fielder, g.pitch["key"][:-1] + "?")
    check("a rough throw and the runner is safe", (play["result"], g.bases[0]), ("safe", 1))
    g = game(seed=4)
    g.swing(1, g.pitch["want"])
    g.catch(g.fielder, g.pitch["want"])
    g.throw(g.fielder, g.pitch["key"])
    play = g.tag(g.fielder, "?")
    check("a bobbled tag is the baseman's error, the runner safe", (play["result"], g.errors["B"], g.bases[0]), ("error", 1, 1))
    g = game(seed=4)
    g.swing(1, g.pitch["want"])
    g.tick(g.deadline + 1)
    check("  a catch never made in time is the runner safe", (g.last["result"], g.bases[0]), ("safe", 1))
    g = cwball.Baseball({"A": [1], "B": [3, 4, 5]}, {1: "Ann", 3: "Cy", 4: "Di", 5: "Ed"}, innings=4, base_wpm=10, seed=9)
    g.inning = 4
    g.tick(g.deadline + 1)
    while g.pitch["kind"] not in cwball.FLIES:
        g.new_pitch()
    g.swing(1, g.pitch["want"])
    check("a big pitch is a fly to the outfield, and the catch is the whole play", (g.last["fly"], g.last["position"] in cwball.OUTFIELD, g.link), (True, True, "catch"))
    play = g.catch(g.fielder, g.pitch["want"])
    check("  caught clean is the out, no throw needed", (play["result"], g.outs), ("out", 1))
    check("  the fielder's copies are counted toward a fielding record", g.stats[g.last["fielder"]]["caught"], 1)

    print("\n-- the force at second, and two --")
    g = game(seed=1)
    g.swing(1, g.pitch["want"]); g.catch(g.fielder, g.pitch["want"][:-1] + "?")     # Ann safe on first
    g.tick(g.deadline + 1)
    while g.last.get("fly") is not False or g.phase != "field":
        g.swing(g.batter, g.pitch["want"])
        if g.phase != "field":
            g.tick(g.deadline + 1)
    check("with a runner on first a grounder is a force at second", g.last["to"], "2B")
    g.catch(g.fielder, g.pitch["want"]); g.throw(g.fielder, g.pitch["key"])
    play = g.tag(g.fielder, g.pitch["key"])
    check("  the tag there is the lead runner out, and with time to spare the throw goes on to first", (play["forced_out"], g.outs, g.link, g.last["to"]), (1, 1, "throw", "1B"))
    g.throw(g.fielder, g.pitch["key"])
    play = g.tag(g.fielder, g.pitch["key"])
    check("  and a clean tag at first is two", (play["result"], g.outs, g.bases), ("double play", 2, [None, None, None]))

    print("\n-- readiness: everybody copies every pitch --")
    g = game(seed=1)
    r = g.readiness(5, g.pitch["n"], g.pitch["want"])
    check("a fielder's copy handed up with a poll counts, and is never the play", (r["pct"], g.phase, g.stats[5]["copies"], g.stats[5]["clean"]), (100, "pitch", 1, 1))
    check("  a copy of no pitch of this game is not taken", "error" in g.readiness(5, 99, "x"), True)
    r = g.readiness(5, g.pitch["n"], g.pitch["want"])
    check("  and the same pitch is not counted twice for one player", (r["counted"], g.stats[5]["copies"]), (False, 1))
    n, want = g.pitch["n"], g.pitch["want"]
    g.swing(1, want); g.catch(g.fielder, want)
    catcher = g.last["fielder"]
    check("  the catch already counted that fielder's copy", g.readiness(catcher, n, want)["counted"], False)
    g.tick(g.deadline + 1); g.tick(g.deadline + 1)
    r = g.readiness(2, n, want[:-1] + "?")
    check("a wrong copy held to the break is still taken, graded against that pitch", (g.pitch["n"] != n, r["ok"], r["pct"] < 100, g.stats[2]["copies"]), (True, True, True, 1))

    print("\n-- a person on the mound --")
    g = people(seed=2)
    check("the fielding side's pitcher is on the mound, choosing", (g.phase, g.link, g.pitcher, g.as_dict(3)["your_link"]), ("windup", "pick", 3, "pick"))
    check("  the batter is told nothing yet", (g.as_dict(1)["your_link"], g.as_dict(1)["pitch"].get("text")), (None, None))
    r = g.choose(3, "normal")
    check("a normal pitch is plain code at the level's speed, shown to the pitcher alone", (r["ok"], r["wpm"], g.as_dict(3)["pitch"]["text"], g.as_dict(1)["pitch"].get("text")), (True, 10.0, r["text"], None))
    check("  the batter cannot choose", "error" in g.choose(1, "hard"), True)
    text = plain(g.pitch["text"])
    r = g.deliver(3, text, 10)
    check("keyed clean at speed: the pitch is in the air, its call kept from the screens", (r["ok"], g.phase, g.pitch["call"], "call" in g.as_dict(1)["pitch"]), (True, "pitch", "zone", False))
    check("  the pitch sounds as keyed, at the speed it was keyed", (g.pitch["sent"], g.pitch["thrown_wpm"]), (text, 10.0))
    play = g.swing(1, text)
    check("  and a clean copy is a hit sized by the level", (play["result"], play["hit_bases"]), ("in play", 1))
    g = people(seed=3)
    g.choose(3, "normal")
    text = plain(g.pitch["text"])
    wrong = text[:-1] + ("X" if text[-1] != "X" else "Y")
    g.deliver(3, wrong, 10)
    check("keyed clean but the wrong text is a ball", g.pitch["call"], "ball")
    play = g.swing(1, wrong)
    check("  swing at a ball and connect - copy what was keyed, wrong letter and all - a hit one base bigger", (play["result"], play["hit_bases"], play["asked"] == text), ("in play", 2, True))
    g = people(seed=3)
    g.choose(3, "normal"); text = plain(g.pitch["text"]); wrong = text[:-1] + ("X" if text[-1] != "X" else "Y")
    g.deliver(3, wrong, 10)
    play = g.swing(1, text)
    check("  swing at a ball and miss: only a ball, no strike", (play["result"], g.balls, g.strikes), ("ball", 1, 0))
    g.tick(g.deadline + 1)
    g.choose(3, "normal"); text = plain(g.pitch["text"]); wrong = text[:-1] + ("X" if text[-1] != "X" else "Y")
    g.deliver(3, wrong, 10)
    play = g.take(1)
    check("  take a ball and it is a ball", (play["result"], g.balls), ("ball", 2))
    for _ in range(2):
        g.tick(g.deadline + 1)
        g.choose(3, "normal"); text = plain(g.pitch["text"]); wrong = text[:-1] + ("X" if text[-1] != "X" else "Y")
        g.deliver(3, wrong, 10); play = g.take(1)
    check("  four balls is a walk", (play["result"], g.bases[0], g.balls), ("walk", 1, 0))
    g = people(seed=4)
    g.choose(3, "normal")
    play = g.deliver(3, "??", 10)
    check("a pitch that does not decode is wild: a ball, and the runners move up", (play["result"], g.balls, g.phase), ("wild pitch", 1, "reveal"))
    g = people(seed=5)
    g.tick(g.deadline + 1)
    check("  a pitcher who never throws has thrown a ball - the pitch clock", (g.last["result"], g.balls), ("delay", 1))
    g = people(seed=6, league="major")
    g.choose(3, "normal")
    text = plain(g.pitch["text"])
    g.deliver(3, text, 14)
    check("in the majors the speed is held to a tenth: too fast is a ball", g.pitch["call"], "ball")
    g = people(seed=6)
    g.choose(3, "normal"); text = plain(g.pitch["text"]); g.deliver(3, text, 14)
    check("  the little league does not judge speed", g.pitch["call"], "zone")

    print("\n-- the pitcher chooses the pitch by how hard a thing to send --")
    g = people(seed=7, league="major")
    r = g.choose(3, "hard")
    check("a hard pitch is harder code at the top of the band", (r["wpm"], any(c.isdigit() for c in r["text"])), (11.5, True))
    text = plain(g.pitch["text"])
    g.deliver(3, text, 11.5)
    play = g.swing(1, text)
    check("  and pays the batter one base more when it is hit", play["hit_bases"], 2)
    g = people(seed=7, league="major")
    check("composing your own is the majors at the exchange and above", "error" in g.choose(3, "own", "CQ CQ DE W1AW K"), True)
    g = cwball.Baseball({"A": [1], "B": [3, 4]}, {1: "Ann", 3: "Cy", 4: "Di"}, innings=5, base_wpm=10, seed=8, league="major", pitcher="people")
    g.inning = 5
    g.tick(g.deadline + 1)
    while g.pitch["level"] < 4:
        g.new_pitch()
    r = g.choose(3, "own", "cq cq de w1aw w1aw qth el16hq <ar> k")
    check("  a composed pitch is the pitcher's text, upper case, prosigns kept", (r["ok"], r["text"]), (True, "CQ CQ DE W1AW W1AW QTH EL16HQ <AR> K"))
    check("  and gibberish is refused", "error" in g.choose(3, "own", "!!!"), True)
    g = people(seed=7, league="major")
    g.choose(3, "hard")
    check("a call and report as a hard pitch is sent 5NN, and copied either way", cwball.accuracy_any("K3AB 5NN BT", "K3AB 599 BT"), 100)

    print("\n-- the machine in the majors throws the odd ball on purpose --")
    calls = set()
    for sd in range(40):
        g = cwball.Baseball({"A": [1], "B": [3]}, {1: "Ann", 3: "Cy"}, innings=3, base_wpm=10, seed=sd, league="major")
        g.inning = 3
        g.tick(g.deadline + 1)
        calls.add(g.pitch["call"])
    check("by the third inning both calls have been seen", calls, {"zone", "ball"})
    calls = set()
    for sd in range(40):
        g = cwball.Baseball({"A": [1], "B": [3]}, {1: "Ann", 3: "Cy"}, innings=3, base_wpm=10, seed=sd)
        g.inning = 3
        g.tick(g.deadline + 1)
        calls.add(g.pitch["call"])
    check("  and in the little league never a ball", calls, {"zone"})

    print("\n-- runs, innings, the game --")
    g = game(innings=1, seed=5)
    for _ in range(3):                        # three runners on: three bobbled catches
        g.swing(g.batter, g.pitch["want"]); g.catch(g.fielder, g.pitch["want"][:-1] + "?"); g.tick(g.deadline + 1)
    check("three singles load the bases", all(b is not None for b in g.bases), True)
    g.swing(g.batter, g.pitch["want"]); g.catch(g.fielder, g.pitch["want"][:-1] + "?")
    check("  a fourth brings one home", (g.runs["A"], g.last["scored"]), (1, 1))
    g.tick(g.deadline + 1)
    for _ in range(3):
        g.swing(g.batter, ""); g.tick(g.deadline + 1); g.swing(g.batter, ""); g.tick(g.deadline + 1); g.swing(g.batter, "")
        if g.phase == "reveal":
            g.tick(g.deadline + 1)
    check("three strikeouts retire the side: bottom of the first, B batting", (g.half, g.batting(), g.outs, g.line["A"]), ("bottom", "B", 0, [1]))
    check("  and the bases are cleared", g.bases, [None, None, None])
    g.tick(g.deadline + 1)
    for _ in range(3):
        g.swing(g.batter, ""); g.tick(g.deadline + 1); g.swing(g.batter, ""); g.tick(g.deadline + 1); g.swing(g.batter, "")
        if g.phase == "reveal":
            g.tick(g.deadline + 1)
    check("B goes down in order in a one-inning game: A wins 1-0", (g.over(), g.winner, g.runs), (True, "A", {"A": 1, "B": 0}))
    g = game(innings=6, seed=6)
    g.inning = 3
    g.new_pitch()
    check("the third inning of six: a word, two bases, three wpm faster", (g.pitch["kind"], g.pitch["bases"], g.pitch["thrown_wpm"]), ("word", 2, 13.0))

    print("\n-- the contact: the top pitch of the last inning --")
    g = cwball.Baseball({"A": [1], "B": [3]}, {1: "KC9SP", 3: "W1AW"}, innings=2, seed=11)
    g.inning = 2
    kinds = set()
    for sd in range(30):
        g.rng.seed(sd)
        g.new_pitch()
        kinds.add(g.pitch["kind"])
    check("the last inning pitches the contact now and then, groups the rest of the time", kinds, {"contact", "group"})
    while g.pitch["kind"] != "contact":
        g.new_pitch()
    p = g.pitch
    check("  the pitcher calls CQ", p["sent"].startswith("CQ CQ CQ DE "), True)
    called = p["sent"].split()[3]
    check("  the batter has only to copy the call", p["want"], called)
    play = g.swing(1, called)
    check("  and a clean copy of it is in play - a fly, to the outfield", (play["result"], play["fly"]), ("in play", True))
    check("  the fielder answers the call with their own: W1AW DE - and, in this game, the caller first", g.pitch["key"], f"{called} DE W1AW")

    print("\n-- practice players play every part --")
    g = cwball.Baseball({"A": [1, 2], "B": [3, 4, 5]}, {}, innings=1, seed=5, pitcher="people", league="major",
                        bots={1: "Elmer", 2: "Elmer", 3: "Elmer", 4: "Elmer", 5: "Elmer"})
    n = 0
    while not g.over() and n < 4000:
        g.tick((g._bot_at if g._bot_at else g.deadline) + 0.01)
        n += 1
    check("a game of practice players pitches, bats, fields and finishes", (g.over(), n < 4000, len(g.plays) > 5), (True, True, True))
    g = cwball.Baseball({"A": [1], "B": [9]}, {1: "Ann", 9: "Sparks"}, innings=1, seed=7, bots={9: "Elmer"})
    g.tick(g.deadline + 1)
    g.swing(1, g.pitch["want"])
    check("a practice fielder's catch is planned, not made at once", (g.phase, g.link, g._bot_at is not None), ("field", "catch", True))
    g.tick(g._bot_at + 0.1)
    check("  and comes when its moment does", g.last["result"] in ("out", "safe", "error") or g.link in ("throw", "tag"), True)

    print("\n-- at the table: the Gaming Center's tile, and the presses --")
    from elmer.app import app
    from elmer import party
    from elmer.content import load_pools
    load_pools()
    client = app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    party.close_room()
    room = party.room(create=True, cohorts=1)
    a = room.join("KC9SP")[0].id
    b = room.join("W1AW")[0].id
    r = client.post("/api/party/mode", json={"mode": "baseball", "innings": 1, "wpm": 12, "league": "major", "pitcher": "people"}, environ_base=local)
    st = r.get_json()
    check("the mode starts a game, the two people on opposite sides, practice players filling in",
          (r.status_code, st["mode"], a in [p["player"] for p in st["baseball"]["lineups"]["A"]],
           b in [p["player"] for p in st["baseball"]["lineups"]["B"]]), (200, "baseball", True, True))
    check("  at the speed asked for, in the league asked for, with people pitching", (st["baseball"]["wpm"], st["baseball"]["league"], st["baseball"]["pitcher_mode"]), (12.0, "major", "people"))
    check("  and it counts as a game in progress - no countdown starts over it", room.waiting_to_start(), False)
    room.baseball.tick(room.baseball.deadline + 1)          # play ball
    bb = room.baseball
    pitcher = bb.pitcher
    st = client.get(f"/api/party/state?player={pitcher}", environ_base=local).get_json()["baseball"]
    check("the first pitch: somebody on B is on the mound, told to choose", (st["phase"], st["your_link"]), ("windup", "pick"))
    r = client.post("/api/party/ball/pick", json={"player": pitcher, "difficulty": "normal"}, environ_base=local)
    check("  the choice hands the pitcher the text, and nobody else", (r.status_code, r.get_json()["play"]["text"] == bb.pitch["text"],
          "text" in (client.get(f"/api/party/state?player={a}", environ_base=local).get_json()["baseball"]["pitch"] or {})), (200, True, False))
    text = plain(bb.pitch["text"])
    r = client.post("/api/party/ball/pitch", json={"player": pitcher, "keyed": text, "wpm": 12}, environ_base=local)
    check("  keyed clean, the pitch is in the air", (r.status_code, bb.phase), (200, "pitch"))
    st = client.get(f"/api/party/state?player={a}", environ_base=local).get_json()["baseball"]
    check("the batter's phone is told it is their swing, and hears the code, not the text", (st["your_link"], "groups" in st["pitch"], "sent" in st["pitch"]), ("swing", True, False))
    r = client.post("/api/party/ball/swing", json={"player": b, "typed": text}, environ_base=local)
    check("the other side cannot swing at it", r.status_code, 409)
    r = client.post("/api/party/ball/take", json={"player": a}, environ_base=local)
    check("the take, in the majors, on a strike: called", (r.status_code, r.get_json()["play"]["result"], bb.strikes), (200, "strike", 1))
    bb.tick(bb.deadline + 1)
    client.post("/api/party/ball/pick", json={"player": bb.pitcher, "difficulty": "normal"}, environ_base=local)
    text = plain(bb.pitch["text"])
    client.post("/api/party/ball/pitch", json={"player": bb.pitcher, "keyed": text, "wpm": 12}, environ_base=local)
    r = client.post("/api/party/ball/copy", json={"player": b, "n": bb.pitch["n"], "typed": text}, environ_base=local)
    check("anybody's copy of the pitch is taken as readiness", (r.status_code, r.get_json()["play"]["pct"]), (200, 100))
    r = client.post("/api/party/ball/swing", json={"player": a, "typed": text}, environ_base=local)
    check("a clean copy is in play", (r.status_code, r.get_json()["play"]["result"]), (200, "in play"))
    fielder = bb.fielder
    st = client.get(f"/api/party/state?player={fielder}", environ_base=local).get_json()["baseball"]
    check("  the fielder's device is told it is their catch", st["your_link"], "catch")
    r = client.post("/api/party/ball/catch", json={"player": fielder, "typed": text}, environ_base=local)
    check("  the held copy handed up clean is the catch", r.status_code, 200)
    if bb.link == "throw":
        r = client.post("/api/party/ball/field", json={"player": bb.fielder, "keyed": bb.pitch["key"], "wpm": 12}, environ_base=local)
        check("  the throw, keyed clean, goes to the tag", (r.status_code, bb.link), (200, "tag"))
        r = client.post("/api/party/ball/tag", json={"player": bb.fielder, "typed": bb.pitch["key"]}, environ_base=local)
        check("  and the tag copied clean is the out", (r.status_code, r.get_json()["play"]["result"], bb.outs), (200, "out", 1))
    else:
        check("  a fly caught clean is the out", (bb.last["result"], bb.outs), ("out", 1))
    client.post("/api/party/mode", json={"mode": "tournament"}, environ_base=local)
    check("back to a tournament puts the game away", room.baseball, None)
    party.close_room()

    print("\n-- the little league's again: ? or AGN, and the machine pitches it again --")
    g = game(seed=3)
    n0, deadline0 = g.pitch["n"], g.deadline
    r = g.again(1)
    check("the batter asks and is answered", (r.get("ok"), r["again"], r["left"]), (True, 1, cwball.AGAIN_MOST - 1))
    check("  the same pitch, sounded again: the count on it moves, the number does not", (g.pitch["n"], g.pitch["again"]), (n0, 1))
    check("  the clock restarts", g.deadline >= deadline0, True)
    check("  and the ask is on the batter's record", g.stat(1)["agains"], 1)
    r = g.again(1, keyed=True)
    check("asked in code, it says the machine answered", "in code, and the machine answered" in r["words"], True)
    check("  and that is remembered apart", (g.pitch["again_keyed"], g.stat(1)["agains_keyed"]), (1, 1))
    check("somebody else cannot ask for it", "not your at-bat" in g.again(3)["error"], True)
    d = g.as_dict(1)
    check("the phone is told how many it may ask for", d["again_most"], cwball.AGAIN_MOST)
    check("  and how many it has", d["pitch"]["again"], 2)
    g.again(1)
    check("three is the most", "the umpire says play ball" in g.again(1)["error"], True)
    play = g.swing(1, g.pitch["want"])
    check("the play says how it was asked for", play["words"].endswith("after asking for it 3 times, in code"), True)
    g2 = game(seed=4)
    play = g2.take(1)
    check("a take with no asking says nothing of it", "asking" in play["words"], False)
    g3 = game(seed=5, league="major")
    check("the majors pitch it once", g3.again(g3.batter)["error"], "the majors pitch it once")
    check("  and the phone is not offered it", g3.as_dict(g3.batter)["again_most"], 0)
    g4 = people(seed=6)
    g4.choose(g4.pitcher, "normal")
    g4.deliver(g4.pitcher, g4.pitch["text"])
    check("a person on the mound is not asked to key it twice",
          "not asked to key it twice" in (g4.again(g4.batter).get("error") or "") if g4.phase == "pitch" else True, True)

    print("\n-- the machine knows CW: QRS and QRQ at the plate --")
    g = game(seed=12)
    was = g.pitch["thrown_wpm"]
    r = g.again(1, keyed=True, ask="slower")
    check("QRS: the same pitch comes again, slower", (r["ask"], r["wpm"] < was, g.pitch["thrown_wpm"] == r["wpm"], g.pitch["n"]), ("slower", True, True, 1))
    check("  re-encoded at that speed", g.pitch["timing"]["wpm"] == r["wpm"], True)
    check("  and said so", "QRS - the machine sends it again, slower" in r["words"] and "in code" in r["words"], True)
    r = g.again(1, ask="faster")
    check("QRQ: faster than that", (r["ask"], r["wpm"] > g.pitch["thrown_wpm"] * 0.9), ("faster", True))
    check("  both counted as asks", (g.pitch["again"], g.stat(1)["agains"], g.stat(1)["agains_keyed"]), (2, 2, 1))
    check("an ask the game does not know is a plain again", g.again(1, ask="louder")["ask"], "again")
    g5 = game(seed=13)
    for _ in range(12):
        if g5.again(1, ask="slower").get("error"):
            break
    check("slower has a floor", g5.pitch["thrown_wpm"] >= cwball.WPM_LEAST, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
