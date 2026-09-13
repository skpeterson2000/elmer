#!/usr/bin/env python3
"""A second Pi in a net is a node of the hall, not a second host.

    python3 tests/test_node_table.py

KC9SP, 2026-09-12: a Pi joining the net another Pi is already running should
join as an extension of that table - its screen a node of the one game, its
intermissions the hall's, its cohort and each seat at it something net
control can speak to. The players at it should have no "Start tournament";
they get a "Check in as ready" that puts the Pi in touch with the primary.

Most of that was already wired - the bridge, the show, the addressed
announcements. What was wrong was the screen and the server behind it: the
table screen kept the host's buttons while it was a node, and the routes
under them did not check, so a press on the second Pi started a director
asking its own questions underneath the hall's. This proves the rule at the
server, the word "ready" the whole way from the button to the host's panel,
and - in the Chromium the kiosk runs - that the screen offers the right
buttons in each of its three shapes.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402
from elmer import app as appmod, autoplay, cohort, db, discovery, netcontrol, party  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


TECH = {"url": "http://127.0.0.1:9", "name": "Technician net",
        "token": "tok-tech", "difficulty": "technician", "units": 3}


class Heard:
    def __init__(self, nets):
        self._nets = nets

    def nets(self):
        return self._nets


# ------------------------------------------------------------ net control
print("\nnet control keeps the table's word apart from the machine's check-in")
net = netcontrol.Net(difficulty="technician")
unit, why = net.check_in("pi-2", "Table two", players=3)
check("checked in", why, None)
check("checked in is not ready", unit.ready, False)
unit, _ = net.check_in("pi-2", "Table two", players=3, ready=True)
check("the table says ready", unit.ready, True)
check("  and the board carries it", unit.as_dict()["ready"], True)
check("  and the health line counts it", net.health()["said_ready"], 1)
unit, _ = net.check_in("pi-2", "Table two", players=3)
check("a check-in with no word leaves the word alone", unit.ready, True)
unit, _ = net.check_in("pi-2", "Table two", players=3, ready=False)
check("  and the word can be taken back", unit.ready, False)

# --------------------------------------------------------------- the bridge
print("\nthe bridge carries the word up, and counts people rather than machines")
sent = []


class Quiet(cohort.Bridge):
    def _call(self, path, body):
        sent.append((path, body))
        return {"checked_in": True, "net": {"name": "Technician net",
                                            "difficulty": "technician"}}


link = Quiet("http://127.0.0.1:9", "pi-2", "Table two")
room = party.Room(cohorts=1)
room.join("KC9SP")
room.fill_bots()
check("a person and some practice players", room.people_here() == 1
      and len(room.players) > 1, True)
link._checkin(room)
check("players reported are people", sent[-1][1]["players"], 1)
check("not ready until somebody says so", sent[-1][1]["ready"], False)
link.ready = True
link._checkin(room)
check("  and ready once they have", sent[-1][1]["ready"], True)
check("  which the table's own state says too", link.as_dict()["ready"], True)

# --------------------------------------------------------------- the token
print("\nthe net is known by a token; its name is only what it is called")
net = netcontrol.Net(difficulty="technician", name="Technician net")
check("a net has a token", bool(net.token) and len(net.token) >= 8, True)
check("  which the board carries", net.board()["token"], net.token)
check("  and which is not its name", net.token != net.name, True)

replies = []


class Says(cohort.Bridge):
    def _call(self, path, body):
        return replies[-1]


link = Says("http://10.0.0.5:5000", "pi-2", "Table two", token="tok-one")
link.net_name = "Technician net"            # seeded from the air
link.seen_round = 12
link.pending = {"unit": "pi-2", "round": 12, "players": []}
room = party.Room(cohorts=1)
replies.append({"checked_in": True, "net": {"name": "General net",
                                            "token": "tok-one",
                                            "difficulty": "general"}})
link._checkin(room)
check("a renamed net is the same net", link.seen_round, 12)
check("  the report it owes still stands", link.pending is not None, True)
check("  and the screen gets the new name", link.net_name, "General net")
replies.append({"checked_in": True, "net": {"name": "Technician net",
                                            "token": "tok-two",
                                            "difficulty": "technician"}})
link._checkin(room)
check("a new net at the old address starts the table afresh",
      link.seen_round, 0)
check("  the old net's report is dropped", link.pending, None)
check("  and the table now knows the new token", link.net_token, "tok-two")

print("\na net that moved is followed by its token")
link = Says("http://10.0.0.5:5000", "pi-2", "Table two", token="tok-two")
link.locate = lambda token: ({"url": "http://10.0.0.77:5000/"}
                             if token == "tok-two" else None)
check("followed", link._follow(), True)
check("  to where it is heard now", link.url, "http://10.0.0.77:5000")
check("  and not again while it is there", link._follow(), False)
link.locate = lambda token: None
check("nowhere to go when it is not heard", link._follow(), False)
link.net_token = ""
link.locate = lambda token: {"url": "http://10.0.0.1:5000"}
check("and nothing to follow by without a token", link._follow(), False)

print("\nthe roster tells a moved net from a second one")
live = discovery.Neighbourhood(port=0)
now = time.time()
live.peers = {
    "host": {"unit": "host", "name": "Host", "url": "http://10.0.0.77:5000",
             "heard_at": now, "party": {},
             "net": {"hosting": True, "name": "Technician net",
                     "token": "tok-two", "difficulty": "technician", "units": 2}},
    # A table still pointing at the address the host had before it rebooted.
    "stale": {"unit": "stale", "name": "Stale", "url": "http://10.0.0.6:5000",
              "heard_at": now, "party": {},
              "net": {"table_of": "http://10.0.0.5:5000", "table_in": "Technician net",
                      "table_token": "tok-two"}},
    # A table in a net this unit cannot hear at all.
    "far": {"unit": "far", "name": "Far", "url": "http://10.0.0.8:5000",
            "heard_at": now, "party": {},
            "net": {"table_of": "http://10.9.9.9:5000", "table_in": "Extra net",
                    "table_token": "tok-far"}},
}
nets = live.nets()
check("one net, not two, for the host and its stale table",
      sorted(n["url"] for n in nets),
      ["http://10.0.0.77:5000", "http://10.9.9.9:5000"])
check("  found by token where it is now",
      (live.net_by_token("tok-two") or {}).get("url"), "http://10.0.0.77:5000")
check("  the far net by its token too",
      (live.net_by_token("tok-far") or {}).get("name"), "Extra net")
check("  and an unknown token is nowhere", live.net_by_token("tok-none"), None)

# ----------------------------------------------------------- the server
appmod.app.config["TESTING"] = True
connection = db.connect()
was_auto = db.unit_get(connection, cohort.AUTO_SETTING)
was_hood = discovery.neighbourhood
was_class = appmod._party_class
appmod._party_class = lambda: "technician"
try:
    cohort.disconnect(connection)
    cohort.set_auto_join(connection, True)
    discovery.neighbourhood = lambda: Heard([TECH])

    print("\nthe table's view of the hall, in one answer")
    with appmod.app.test_client() as client:
        view = client.get("/api/party/net").get_json()
    check("not connected", view["connected"], False)
    check("not hosting", view["hosting"], False)
    check("hears the net", [n["name"] for n in view["heard"]],
          ["Technician net"])
    check("auto-join is on", view["auto_join"], True)

    print("\n'check in as ready' with no address joins the net it can hear")
    with appmod.app.test_client() as client:
        r = client.post("/api/party/net", json={"ready": True})
        view = r.get_json()
    check("taken", r.status_code, 200)
    check("connected", view["connected"], True)
    check("to the net heard", (view["bridge"] or {}).get("url"), TECH["url"])
    check("and ready", view["ready"], True)
    check("named as heard, before the first reply",
          (view["bridge"] or {}).get("net_name"), "Technician net")
    check("  and keyed by the token heard, not the name",
          (view["bridge"] or {}).get("net_token"), TECH["token"])
    first = cohort.bridge()

    print("\nready again does not remake the link")
    with appmod.app.test_client() as client:
        client.post("/api/party/net", json={"ready": True})
    check("same bridge", cohort.bridge() is first, True)

    print("\na node has none of the host's buttons, and the server says so")
    with appmod.app.test_client() as client:
        r = client.post("/api/party/auto", json={"on": True,
                                                 "difficulty": "technician"})
        check("start tournament is refused", r.status_code, 409)
        check("  in a sentence naming whose game it is",
              "net control" in r.get_data(as_text=True)
              or "Technician net" in r.get_data(as_text=True), True)
        r = client.post("/api/party/mode", json={"mode": "shootout",
                                                 "difficulty": "technician"})
        check("shootout is refused", r.status_code, 409)
        r = client.post("/api/party/round", json={"difficulty": "technician"})
        check("ask one question is refused", r.status_code, 409)
        r = client.post("/api/party/close", json={})
        check("close the round is refused", r.status_code, 409)
        r = client.post("/api/party/auto", json={"on": False})
        check("stopping is always allowed", r.status_code, 200)
        r = client.post("/api/party/mode", json={"mode": "tournament"})
        check("and so is being a tournament table", r.status_code, 200)
    check("nothing started underneath the hall",
          bool(autoplay.director() and autoplay.director().as_dict()["running"]),
          False)

    print("\nleaving is by hand, and stays left")
    with appmod.app.test_client() as client:
        view = client.post("/api/party/net", json={"join": False}).get_json()
    check("cut loose", view["connected"], False)
    check("  auto-join off", view["auto_join"], False)
    check("  ready is gone with the link", view["ready"], False)
    with appmod.app.test_client() as client:
        r = client.post("/api/party/auto", json={"on": True,
                                                 "difficulty": "technician"})
        check("on its own, the table may start", r.status_code, 200)
        client.post("/api/party/auto", json={"on": False})

    print("\na table that only checked in keeps its own game, and its buttons")
    cohort.set_auto_join(connection, True)
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    autoplay.start(room, lambda: None)
    check("a game of its own is running",
          autoplay.director().as_dict()["running"], True)
    with appmod.app.test_request_context():
        joined = appmod._party_auto_join(room)
    check("it checked in with the hall by itself", joined, True)
    time.sleep(0.05)
    with appmod.app.test_client() as client:
        view = client.get("/api/party/net").get_json()
    check("  linked", view["connected"], True)
    check("  but nobody here said ready", view["ready"], False)
    check("  so its own game runs on",
          bool(autoplay.director() and autoplay.director().as_dict()["running"]),
          True)
    autoplay.stop()
    with appmod.app.test_client() as client:
        r = client.post("/api/party/round", json={"difficulty": "technician"})
        check("  and it may ask its own question", r.status_code, 200)
        client.post("/api/party/close", json={})
    # The hall's round does not land on a table that has not said ready:
    # the bridge is told net control has a round up, and leaves the screen.
    link = cohort.bridge()
    hall_round = {"number": 99, "pool": "technician", "question_id": "x",
                  "answer_index": 0, "question": {"text": "?"}, "seconds": 30}
    link._checkin = lambda room: hall_round
    link._tick()
    check("  the hall's question stays off its screen",
          bool(room.round and not room.round.closed and room.round.tag == 99), False)

    print("\nready is the press that hands the table to the hall")
    autoplay.start(room, lambda: None)
    with appmod.app.test_client() as client:
        r = client.post("/api/party/net", json={"ready": True})
    check("taken", r.status_code, 200)
    time.sleep(0.05)
    check("  and now its own director stopped",
          bool(autoplay.director() and autoplay.director().as_dict()["running"]),
          False)
    link._tick()
    check("  and the hall's question lands",
          bool(room.round and room.round.tag == 99), True)
    room.close_round()
    cohort.disconnect(connection)

    print("\nwith nothing to hear, ready has nowhere to go")
    discovery.neighbourhood = lambda: Heard([])
    cohort.set_auto_join(connection, True)
    with appmod.app.test_client() as client:
        r = client.post("/api/party/net", json={"ready": True})
    check("told so", r.status_code, 409)
    check("  in words", "no net" in (r.get_json() or {}).get("message", ""), True)

    print("\nthe host's own table is in the host's own net")
    with appmod.app.test_client() as client:
        client.post("/api/net/open", json={"difficulty": "technician"})
        view = client.get("/api/party/net").get_json()
        check("hosting", view["hosting"], True)
        check("  hears nothing to join", view["heard"], [])
        r = client.post("/api/party/net", json={"ready": True,
                                                "url": "http://10.0.0.9:5000"})
        check("  and cannot be somebody else's node", r.status_code, 409)
        reply = client.post("/api/net/checkin",
                            json={"unit": "pi-9", "name": "Nine", "players": 2,
                                  "ready": True}).get_json()
        check("a check-in reply carries the net's token",
              reply["net"].get("token"), netcontrol.net().token)
        check("  and the table's word reached the board",
              reply["unit"]["ready"], True)
        with appmod.app.test_request_context():
            role = appmod._net_role()
        check("  and the announcement carries it too", role.get("token"),
              netcontrol.net().token)
        client.post("/api/net/end", json={})
finally:
    from elmer import hall
    hall.halt()
    netcontrol.close_net()
    autoplay.stop()
    discovery.neighbourhood = was_hood
    appmod._party_class = was_class
    cohort.disconnect(connection)
    db.unit_set(connection, cohort.AUTO_SETTING, was_auto)

# ------------------------------------------------------------- the screen
print("\nthe screen offers the right buttons in each of its three shapes")
check("chromium is on this machine", bool(_browser.available()), True)
ROOT = Path(__file__).resolve().parents[1]
PORT = _browser._free_port()
# A throwaway unit that can hear a net it is not in. The roster is stood in
# for inside the server, because two ELMERs on one machine share a unit id
# and filter each other out by design. It is a real Neighbourhood, never
# started, with only what it hears made up: the pages ask it for a borrowed
# fix and the board for its games too, and a stand-in with one method
# answered every page with a 500 - which the wait below read as no server.
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\n"
     "from elmer import discovery\n"
     "class Heard(discovery.Neighbourhood):\n"
     "    def nets(self): return [%r]\n"
     "heard = Heard(port=0)\n"
     "discovery.neighbourhood = lambda: heard\n"
     "from elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
     % (str(ROOT), TECH, PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def shape():
    """Which of the three cards is showing, and what else is on offer."""
    return ("JSON.stringify({offer: !offer.hidden, node: !node.hidden,"
            " own: !owncontrols.hidden, byaddress: !netbyaddress.hidden,"
            " end: !endtable.hidden,"
            " ready: !!document.querySelector('#node .ready'),"
            " tourney: !!document.querySelector('#owncontrols #tourney'),"
            " stage: document.getElementById('stage').textContent.trim().slice(0, 60)})")


def settle_then(js, wait_for):
    """Wait until `wait_for` holds, then answer `js`."""
    return (f"new Promise(res => {{ const t0 = Date.now(); const f = () => {{"
            f" if (({wait_for}) || Date.now() - t0 > 12000) res({js});"
            f" else setTimeout(f, 200); }}; f(); }})")


try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        raise SystemExit("the throwaway server never answered")

    url = f"http://127.0.0.1:{PORT}/party"
    # The cards follow the net poll and the stage follows the state poll,
    # a second apart - so both are waited for, not sampled.
    got = json.loads(_browser.evaluate(
        url, settle_then(shape(), "!offer.hidden && /Check in/.test(stage.textContent)"),
        settle=0.5) or "{}")
    check("hearing a net: the offer is up", got.get("offer"), True)
    check("  and the host's controls are not", got.get("own"), False)
    check("  nor the address box", got.get("byaddress"), False)
    check("  and the stage says to check in",
          "Check in" in got.get("stage", ""), True)

    # Press it. The net is at a dead address, so the link goes "offline" -
    # which is still a node: a table keeps its place in a hall it cannot
    # reach for the moment.
    got = json.loads(_browser.evaluate(
        url,
        "new Promise(res => { const t0 = Date.now(); const f = () => {"
        "  const b = document.querySelector('#offer [data-checkin]');"
        "  if (b) { b.click(); res(true); } else if (Date.now() - t0 > 12000) res(false);"
        "  else setTimeout(f, 200); }; f(); }).then(() => " +
        settle_then(shape(), "!node.hidden && document.querySelector('#node .ready')"
                             " && /net control/.test(stage.textContent)") + ")",
        settle=0.5) or "{}")
    check("checked in: the node card is up", got.get("node"), True)
    check("  marked ready", got.get("ready"), True)
    check("  no Start tournament", got.get("own"), False)
    check("  no End tournament", got.get("end"), False)
    check("  the stage waits on net control",
          "net control" in got.get("stage", ""), True)

    # Leave. The table is on its own now, by hand, and has its controls
    # back - and the offer does not come straight back, because that would
    # be overruling the press.
    got = json.loads(_browser.evaluate(
        url,
        "new Promise(res => { const t0 = Date.now(); const f = () => {"
        "  const b = document.querySelector('#node [data-standalone]');"
        "  if (b) { b.click(); res(true); } else if (Date.now() - t0 > 12000) res(false);"
        "  else setTimeout(f, 200); }; f(); }).then(() => " +
        settle_then(shape(), "!owncontrols.hidden") + ")",
        settle=0.5) or "{}")
    check("left: the host's controls are back", got.get("own"), True)
    check("  with Start tournament", got.get("tourney"), True)
    check("  and the offer stays down", got.get("offer"), False)
    check("  the address box is back", got.get("byaddress"), True)
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
