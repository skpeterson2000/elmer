#!/usr/bin/env python3
"""The hall's other games: a CutThroat and a round of golf, tables for players.

    python3 tests/test_net_games.py

A table is right when anybody at it was right. In the hall's CutThroat a
table that was not right is out, last table standing wins; in the hall's
golf every table has a ball and hits at once - a scramble - and the card
is the tables'. A table checking in late takes a chair or a ball; one
that leaves loses its chair and picks up its ball. The mode button starts
either, the conductor ends the hall when the game is over, and the
check-in reply carries the game to each table.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import app as appmod, golf, hall, netcontrol  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def table_in(net, uid, name, players=3):
    unit, why = net.check_in(uid, name, players, ready=True)
    assert unit is not None, why
    return unit.id


def ask(net, n):
    return net.start_round("tech2026", f"Q{n}", 0,
                           {"text": "?", "choices": ["a", "b", "c", "d"], "section": "T1A"}, seconds=30)


def report(net, uid, rnd, rights):
    """`rights`: a list of booleans, one person each."""
    net.report(uid, rnd["number"], [{"name": f"p{i}", "correct": r, "ms": 2000 + i * 100}
                                    for i, r in enumerate(rights)])


def run():
    print("\n-- a CutThroat across three tables --")
    netcontrol.close_net()
    net = netcontrol.net(create=True, name="Test Net")
    a, b, c = (table_in(net, "unit-a", "Poldhu"), table_in(net, "unit-b", "Clifden"),
               table_in(net, "unit-c", "Nauen"))
    started, why = net.begin_cutthroat()
    check("three tables take chairs", (started is not None, net.mode), (True, "cutthroat"))
    rnd = ask(net, 1)
    report(net, a, rnd, [True, False, False])      # one right at Poldhu: the table is right
    report(net, b, rnd, [False, False])            # nobody right at Clifden
    report(net, c, rnd, [True, True])
    summary = net.close_round()
    ct = summary["cutthroat"]
    check("a table is right when anybody at it was", sorted(ct["right"]), sorted([a, c]))
    check("  and Clifden is out, by name", ct["out_names"], ["Clifden"])
    view = net.cutthroat_view(b)
    check("  the view says so to Clifden", (view["you_in"], view["remaining"]), (False, 2))
    check("  two left: the final", view["phase"], "final")
    check("the board carries it", net.board()["cutthroat"]["on"], True)
    check("  and the conductor knows it is not over", net.game_over(), False)

    print("\n-- a table checking in late takes a chair; one leaving loses it --")
    d = table_in(net, "unit-d", "Rugby")
    check("Rugby is seated", d in net.cutthroat.order, True)
    net._forget_unit(d)
    check("  and gone when it leaves", net.cutthroat.alive().count(d), 0)

    print("\n-- a round of golf across the hall: a scramble --")
    netcontrol.close_net()
    net = netcontrol.net(create=True, name="Test Net")
    a, b = table_in(net, "unit-a", "Poldhu"), table_in(net, "unit-b", "Clifden")
    started, why = net.begin_golf(golf.course("pebble-beach"), holes=[1, 2])
    check("two balls on the first tee", (net.mode, sorted(net.golf.balls)), ("golf", sorted([a, b])))
    rnd = ask(net, 1)
    report(net, a, rnd, [True, False])
    report(net, b, rnd, [False, False])
    summary = net.close_round()
    g = summary["golf"]
    check("every table hit at once", sorted(g["shots"]), sorted([a, b]))
    check("  Poldhu's ball flew", g["shots"][a]["kind"] in ("fairway", "green", "sand", "water", "long"), True)
    check("  Clifden's was a foul ball", "foul" in g["shots"][b]["words"], True)
    check("  with the table's name on the shot", g["shots"][a]["name"], "Poldhu")
    view = net.golf_view(a)
    check("the view has the hole and this table's ball", (view["hole"], view["you"]["name"]), (1, "Poldhu"))
    check("  and the card by table", [r["name"] for r in view["leaderboard"]], ["Poldhu", "Clifden"])
    rnd = ask(net, 2)
    report(net, a, rnd, [True])                    # Clifden does not report: a foul ball
    summary = net.close_round()
    check("a table that did not report played a foul ball", "foul" in summary["golf"]["shots"][b]["words"], True)
    check("the board carries it", net.board()["golf"]["on"], True)

    print("\n-- the mode button, and what the conductor does --")
    client = appmod.app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    netcontrol.close_net()
    r = client.post("/api/net/open", json={"name": "Test Net", "difficulty": "technician"}, environ_base=local)
    running = netcontrol.net()
    check("a net", running is not None, True)
    a, b = table_in(running, "unit-a", "Poldhu"), table_in(running, "unit-b", "Clifden")
    r = client.post("/api/net/mode", json={"mode": "golf", "difficulty": "technician", "holes": "front"},
                    environ_base=local)
    check("golf from the host", (r.status_code, r.get_json()["mode"]), (200, "golf"))
    check("  on the pool's course", r.get_json()["golf"]["course"], "pebble-beach")
    check("  the hall is conducting", hall.conductor() is not None, True)
    hall.halt()
    if running.round:
        running.round = None
    r = client.post("/api/net/mode", json={"mode": "cutthroat", "difficulty": "technician"}, environ_base=local)
    check("CutThroat from the host", (r.status_code, r.get_json()["mode"]), (200, "cutthroat"))
    check("  the golf is put away", r.get_json()["golf"], None)
    hall.halt()
    if running.round:
        running.round = None
    r = client.post("/api/net/mode", json={"mode": "tournament"}, environ_base=local)
    check("back to a tournament", (r.get_json()["mode"], r.get_json()["cutthroat"]), ("tournament", None))
    r = client.post("/api/net/mode", json={"mode": "bingo"}, environ_base=local)
    check("a game nobody wrote", r.status_code, 400)

    print("\n-- the check-in reply carries the game --")
    running.begin_cutthroat()
    r = client.post("/api/net/checkin", json={"unit": "unit-a", "name": "Poldhu", "players": 3, "ready": True},
                    environ_base=local)
    d = r.get_json()
    check("the hall's CutThroat, as this table sees it", ((d.get("cutthroat") or {}).get("on"),
                                                          (d.get("cutthroat") or {}).get("phase")), (True, "final"))
    check("  and no ball, since this is not golf", d.get("golf"), None)
    netcontrol.close_net()
    hall.halt()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(run())
