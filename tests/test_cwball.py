#!/usr/bin/env python3
"""CW Baseball: the rules. Batting is copying, fielding is sending.

    python3 tests/test_cwball.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401
from elmer import cwball  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def game(innings=1, seed=1, **kw):
    g = cwball.Baseball({"A": [1, 2], "B": [3, 4]}, {1: "Ann", 2: "Bob", 3: "Cy", 4: "Di"},
                        innings=innings, base_wpm=10, seed=seed, **kw)
    g.tick(g.deadline + 1)               # the first pitch
    return g


def run():
    print("\n-- the pitch --")
    g = game()
    p = g.pitch
    check("the first inning pitches letters, three of them, at the base speed", (p["kind"], len(p["plain"]), p["wpm"]), ("letters", 3, 10.0))
    check("  to A's first batter, in the top of the first", (g.batter, g.half, g.batting()), (1, "top", "A"))
    check("  with the code to sound it and a window to type it", (bool(p["groups"]), p["window"] >= cwball.COPY_LEAST), (True, True))
    check("  the screens are not told the text while it is in the air", "plain" in g.as_dict()["pitch"], False)
    check("accuracy is characters right in order", (cwball.accuracy("ESZ", "ESZ"), cwball.accuracy("ESZ", "ESX"), cwball.accuracy("ESZ", "")), (100, 67, 0))

    print("\n-- batting is copying --")
    play = g.swing(1, p["plain"])
    check("a clean copy is in play, and the fielding side has it", (play["result"], g.phase, g.fielder in (3, 4)), ("in play", "field", True))
    check("  a stranger cannot swing", "error" in g.swing(2, "x"), True)
    check("  and the fielder is told the text to key back", g.as_dict()["pitch"]["plain"], p["plain"])
    g2 = game()
    text = g2.pitch["plain"]
    play = g2.swing(1, text[:2] + "?")
    check("two of three is a foul: a strike, the count stands at one", (play["result"], g2.strikes, g2.phase), ("foul", 1, "reveal"))
    g2.tick(g2.deadline + 1)
    play = g2.swing(1, "")
    check("  nothing typed is a strike", (play["result"], g2.strikes), ("strike", 2))
    g2.tick(g2.deadline + 1)
    play = g2.swing(1, g2.pitch["plain"][:2] + "?")
    check("  with two strikes a foul is not free: strike three, out", (play["result"], g2.outs, g2.strikes), ("strikeout", 1, 0))
    check("  and the next batter is up", g2.batter is None or g2.phase == "reveal", True)

    print("\n-- fielding is sending --")
    g = game()
    g.swing(1, g.pitch["plain"])
    f = g.fielder
    play = g.field(f, g.pitch["plain"])
    check("a clean send makes the out", (play["result"], g.outs, g.bases), ("out", 1, [None, None, None]))
    g = game(seed=2)
    g.swing(1, g.pitch["plain"])
    play = g.field(g.fielder, g.pitch["plain"][:-1] + "?")
    check("a rough send and the runner is safe on first", (play["result"], g.bases[0], g.runs["A"]), ("safe", 1, 0))
    g = game(seed=3)
    g.swing(1, g.pitch["plain"])
    play = g.field(g.fielder, "?")
    check("a botched send is an error: an extra base", (play["result"], g.bases[1], g.errors["B"]), ("error", 1, 1))
    g = game(seed=4)
    g.swing(1, g.pitch["plain"])
    check("  the wrong fielder cannot throw", "error" in g.field(1, "x"), True)
    g.tick(g.deadline + 1)
    check("  and a throw never made is the runner safe", (g.last["result"], g.bases[0]), ("safe", 1))

    print("\n-- runs, innings, the game --")
    g = game(innings=1, seed=5)
    for _ in range(3):                        # three runners on: three safe hits
        g.swing(g.batter, g.pitch["plain"]); g.field(g.fielder, g.pitch["plain"][:-1] + "?"); g.tick(g.deadline + 1)
    check("three singles load the bases", all(b is not None for b in g.bases), True)
    g.swing(g.batter, g.pitch["plain"]); g.field(g.fielder, g.pitch["plain"][:-1] + "?")
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
    check("the second inning pitches groups, faster; the fifth the exchange",
          (cwball.LEVELS[1]["kind"], cwball.LEVELS[4]["kind"], cwball.LEVELS[4]["bases"]), ("group", "exchange", 4))
    g.inning = 3
    g.new_pitch()
    check("  the third inning of six: a word, two bases, three wpm faster", (g.pitch["kind"], g.pitch["bases"], g.pitch["wpm"]), ("word", 2, 13.0))

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
    check("  the pitcher calls CQ", p["plain"].startswith("CQ CQ CQ DE "), True)
    called = p["plain"].split()[3]
    check("  the batter has only to copy the call", p["want"], called)
    play = g.swing(1, called)
    check("  and a clean copy of it is in play", play["result"], "in play")
    check("  the fielder answers the call with their own: W1AW DE - and, in this game, the caller first",
          g.pitch["key"], f"{called} DE W1AW")
    play = g.field(3, f"{called} DE W1AW")
    check("  a clean answer is the out", play["result"], "out")
    h = cwball.Baseball({"A": [1], "B": [4]}, {1: "KC9SP", 4: "Ann"}, innings=2, seed=3)
    h.inning = 2
    h.new_pitch()
    while h.pitch["kind"] != "contact":
        h.new_pitch()
    h.swing(1, h.pitch["want"])
    check("  a fielder without a callsign answers as ELMER", h.pitch["key"].endswith(" DE ELMER"), True)

    print("\n-- practice players play their part --")
    g = cwball.Baseball({"A": [1], "B": [9]}, {1: "Ann", 9: "Sparks"}, innings=1, seed=7, bots={9: "Elmer"})
    g.tick(g.deadline + 1)
    g.swing(1, g.pitch["plain"])
    check("a practice fielder's throw is planned, not thrown at once", (g.phase, g._bot_at is not None), ("field", True))
    g.tick(g._bot_at + 0.1)
    check("  and comes when its moment does", g.last["result"] in ("out", "safe", "error"), True)

    print("\n-- at the table: the Gaming Center's tile, and the two presses --")
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
    r = client.post("/api/party/mode", json={"mode": "baseball", "innings": 1, "wpm": 12}, environ_base=local)
    st = r.get_json()
    check("the mode starts a game, the two people on opposite sides, practice players filling in",
          (r.status_code, st["mode"], a in [p["player"] for p in st["baseball"]["lineups"]["A"]],
           b in [p["player"] for p in st["baseball"]["lineups"]["B"]]), (200, "baseball", True, True))
    check("  at the speed asked for", st["baseball"]["wpm"], 12.0)
    check("  and it counts as a game in progress - no countdown starts over it", room.waiting_to_start(), False)
    room.baseball.tick(room.baseball.deadline + 1)          # play ball
    st = client.get(f"/api/party/state?player={a}", environ_base=local).get_json()["baseball"]
    check("the first pitch is to KC9SP, whose phone is told it is their swing", (st["batter"], st["your_swing"], st["phase"]), (a, True, "pitch"))
    check("  and hears the code, not the text", ("groups" in st["pitch"], "plain" in st["pitch"]), (True, False))
    text = room.baseball.pitch["plain"]
    r = client.post("/api/party/ball/swing", json={"player": b, "typed": text}, environ_base=local)
    check("the other side cannot swing at it", r.status_code, 409)
    r = client.post("/api/party/ball/swing", json={"player": a, "typed": text}, environ_base=local)
    check("a clean copy is in play", (r.status_code, r.get_json()["play"]["result"]), (200, "in play"))
    fielder = room.baseball.fielder
    st = client.get(f"/api/party/state?player={fielder}", environ_base=local).get_json()["baseball"]
    check("  the fielder's phone is told it is their throw, and what to key", (st["your_throw"], st["pitch"]["plain"]), (True, text))
    r = client.post("/api/party/ball/field", json={"player": fielder, "keyed": text}, environ_base=local)
    check("  a clean send is the out", (r.status_code, r.get_json()["play"]["result"], room.baseball.outs), (200, "out", 1))
    client.post("/api/party/mode", json={"mode": "tournament"}, environ_base=local)
    check("back to a tournament puts the game away", room.baseball, None)
    party.close_room()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
