#!/usr/bin/env python3
"""Golf between two units: one round, players at both.

    python3 tests/test_golf_between_units.py

Two ELMERs on one network heard each other perfectly well and still could
not play golf together: the golf was the table's, and nothing offered one
unit's round to the other. Now a unit playing golf says so when it says
hello - the course, where the group is, whether there is room - and another
unit's table screen offers to become a screen onto that round. One round on
one unit, so there is only ever one account of where a ball is; the second
screen has its own seats and its own phones, and plays in it.

This holds the three parts: what a unit announces about its golf, what the
other unit makes of what it hears, and the screen - offering the round, and
behaving as a visitor once it is on the other unit's table.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402
from elmer import app as appmod, autoplay, discovery, party  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


print("\n-- a unit playing golf says so when it says hello --")
client = appmod.app.test_client()
from elmer import db, gating  # noqa: E402
conn = db.connect()
settings = db.get_profile(conn)["settings"]
settings[gating.SETTING] = "off"
db.save_settings(conn, settings)
conn.commit()
party.close_room()
room = party.room(create=True, cohorts=1)
room.join("KC9SP")
check("no golf, nothing about golf", appmod._golf_open(room), None)
client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "holes": "front",
                                     "seconds": 30, "level": "Elmer"}, environ_base=LOCAL)
autoplay.stop()
said = appmod._golf_open(room)
check("a round in play is announced with its course", bool(said and said["course"]), True)
check("  where the group is", (said["clubhouse"], said["hole"], said["holes"]), (False, 1, 9))
check("  and how many people, not practice players", said["people"], 1)
check("  and that a foursome has room", said["full"], False)
hello = json.loads(discovery._payload("u1", "b0uNc3r-T", "http://10.0.0.5:5000", "abc", None,
                                      {"running": True, "golf": said}).decode())
check("it travels in the hello", hello["party"]["golf"]["course"], said["course"])
party.close_room()

print("\n-- the other unit makes an offer of it --")
hood = discovery.Neighbourhood()
now = time.time()
hood.peers = {
    "u1": {**discovery.parse(json.dumps(hello).encode(), "10.0.0.5"), "heard_at": now},
    "u2": {**discovery.parse(json.dumps({"elmer": discovery.MAGIC, "unit": "u2", "name": "quiet",
                                         "url": "http://10.0.0.6:5000", "party": {"running": False}}).encode(),
                             "10.0.0.6"), "heard_at": now},
    "u3": {**discovery.parse(json.dumps({"elmer": discovery.MAGIC, "unit": "u3", "name": "in a net",
                                         "url": "http://10.0.0.7:5000", "net": {"table_of": "x"},
                                         "party": {"golf": said}}).encode(), "10.0.0.7"), "heard_at": now},
    "u4": {**discovery.parse(json.dumps({"elmer": discovery.MAGIC, "unit": "u4", "name": "gone",
                                         "url": "http://10.0.0.8:5000", "party": {"golf": said}}).encode(),
                             "10.0.0.8"), "heard_at": now - 600},
}
rounds = hood.golf_rounds()
check("the round is offered, with where to find it", [(r["name"], r["url"]) for r in rounds],
      [("b0uNc3r-T", "http://10.0.0.5:5000")])
check("  a unit with no golf is not, nor one that is a table in a net, nor one gone quiet", len(rounds), 1)
real = discovery.neighbourhood
discovery.neighbourhood = lambda: hood
try:
    got = client.get("/api/party/nearby-golf", environ_base=LOCAL).get_json()
    check("the table screen can ask for it", [r["name"] for r in got["rounds"]], ["b0uNc3r-T"])
finally:
    discovery.neighbourhood = real

print("\n-- the host ending it is said as that, not as the network --")
party.close_room()
room = party.room(create=True, cohorts=1)
room.join("KC9SP")
client.post("/api/party/mode", json={"mode": "golf", "difficulty": "technician", "holes": "front",
                                     "seconds": 30, "level": "Elmer"}, environ_base=LOCAL)
autoplay.stop()
check("a round in play is not ended", client.get("/api/party/state", environ_base=LOCAL).get_json().get("ended"), None)
client.post("/api/party/mode", json={"mode": "tournament"}, environ_base=LOCAL)
ended = client.get("/api/party/state", environ_base=LOCAL).get_json().get("ended")
check("the host stopping the golf early leaves a note on the table", (ended or {}).get("what"), "golf")
check("  saying where it stopped", ((ended or {}).get("hole"), bool((ended or {}).get("course"))), (1, True))
client.post("/api/party/end", json={}, environ_base=LOCAL)
r = client.get("/api/party/state", environ_base=LOCAL)
check("a table its host closed answers 410, not 404", r.status_code, 410)
check("  with the host's note", (r.get_json().get("ended") or {}).get("what"), "table")
party.room(create=True, cohorts=1)
check("a new table puts the note away", client.get("/api/party/state", environ_base=LOCAL).status_code, 200)
party.close_room()
check("  and a table that simply is not there is 404", client.get("/api/party/state", environ_base=LOCAL).status_code, 404)

import io  # noqa: E402
import urllib.error  # noqa: E402
from elmer import cohort, netcontrol  # noqa: E402
appmod._net_closed_note = {"what": "net", "name": "Technician", "why": "the host closed the net", "at": time.time()}
real_net = netcontrol.net
netcontrol.net = lambda: None
try:
    r = client.post("/api/net/checkin", json={"unit": "t1"}, environ_base=LOCAL)
    check("a net its host closed answers a table's check-in with 410", (r.status_code, r.get_json()["ended"]["name"]),
          (410, "Technician"))
finally:
    netcontrol.net = real_net
    appmod._net_closed_note = None
gone = urllib.error.HTTPError("http://x/api/net/checkin", 410, "Gone", {},
                              io.BytesIO(json.dumps({"ended": {"what": "net", "name": "Technician"}}).encode()))
check("the table reads it as the host closing the net", cohort.Bridge._ended_note(gone)["name"], "Technician")
check("  and anything else as a fault to back off from",
      cohort.Bridge._ended_note(urllib.error.HTTPError("http://x", 503, "Busy", {}, io.BytesIO(b""))), None)

print("\n-- the screen offers it, and visits it --")
check("chromium is on this machine", bool(_browser.available()), True)
PORT = _browser._free_port()
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    offer_js = """new Promise(async r => {
      const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
      await until(() => typeof nearbyGolf === 'function', 8000);
      api = async path => path.includes('nearby-golf')
        ? {ok: true, data: {rounds: [{name: 'b0uNc3r-T', url: 'http://10.0.0.5:5000', course: 'Pebble Beach',
                                      clubhouse: false, hole: 3, holes: 9, people: 2, full: false}]}}
        : {ok: true, data: {}};
      lastTableState = {};
      await nearbyGolf();
      const box = document.getElementById('nearby-golf');
      const a = box.querySelector('a');
      r(JSON.stringify({shown: !box.hidden, text: box.textContent.replace(/\\s+/g, ' ').trim(), href: a && a.href}));
    })"""
    got = json.loads(_browser.evaluate(f"http://127.0.0.1:{PORT}/party", offer_js, settle=0.5,
                                       cookies={"elmer_user": "1"}) or "{}")
    check("a unit with no golf of its own shows the round nearby", got.get("shown"), True)
    check("  named, with its course and where the group is",
          all(w in (got.get("text") or "") for w in ("b0uNc3r-T", "Pebble Beach", "3rd of 9", "2 playing")), True)
    href = got.get("href") or ""
    check("  and the button opens that unit's table as a visitor",
          (href.startswith("http://10.0.0.5:5000/party/1?visit="), "from=" in href), (True, True))

    visit_js = """new Promise(async r => {
      const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
      await until(() => typeof nearbyGolf === 'function', 8000);
      const back = document.querySelector('.head a.btn');
      const gc = document.querySelector('.gc'), end = document.getElementById('endtable');
      r(JSON.stringify({visiting: document.body.classList.contains('visiting'), back: back.textContent.trim(),
                        href: back.getAttribute('href'),
                        gc_hidden: getComputedStyle(gc).display === 'none',
                        end_hidden: getComputedStyle(end).display === 'none'}));
    })"""
    url = f"http://127.0.0.1:{PORT}/party/1?visit=" + urllib.request.quote("http://10.0.0.6:5000/party/1") + "&from=Table%20B"
    got = json.loads(_browser.evaluate(url, visit_js, settle=0.5, cookies={"elmer_user": "1"}) or "{}")
    check("opened as a visitor, it knows it", got.get("visiting"), True)
    # The words after the arrow: a Windows console cannot print the arrow.
    check("  and goes home, by name", ((got.get("back") or "")[1:].strip(), got.get("href")),
          ("Back to Table B", "http://10.0.0.6:5000/party/1"))
    check("  the host's controls are put away - a visitor cannot end or change the round",
          (got.get("gc_hidden"), got.get("end_hidden")), (True, True))

    ended_js = """new Promise(async r => {
      const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
      await until(() => typeof visitGone === 'function', 8000);
      const out = {};
      visitWatch({golf: {hole: 3}});
      visitWatch({ended: {what: 'golf', course: 'Pebble Beach', hole: 3, at: Date.now() / 1000}});
      let box = document.querySelector('.host-ended');
      out.stopped = box ? box.textContent.replace(/\\s+/g, ' ') : '';
      document.getElementById('host-ended-stay').click();
      out.stayed = !document.querySelector('.host-ended');
      visitEnded = false;
      visitGone({what: 'table', at: Date.now() / 1000});
      box = document.querySelector('.host-ended');
      out.closed = box ? box.textContent.replace(/\\s+/g, ' ') : '';
      out.home = (document.getElementById('host-ended-home') || {}).getAttribute
        ? document.getElementById('host-ended-home').getAttribute('href') : '';
      r(JSON.stringify(out));
    })"""
    got = json.loads(_browser.evaluate(url, ended_js, settle=0.5, cookies={"elmer_user": "1"}) or "{}")
    check("the host stopping the golf reads as that, with where",
          all(w in (got.get("stopped") or "") for w in ("The round is over", "The host stopped the round",
                                                        "Pebble Beach", "3rd", "before the last hole")), True)
    check("  never as a lost connection", "connection" in (got.get("stopped") or "").lower(), False)
    check("  and whoever is there can stay to read the card", got.get("stayed"), True)
    check("the host closing the table reads as that",
          "The host closed the table" in (got.get("closed") or ""), True)
    check("  and the screen is taken home by name",
          ("goes home to Table B" in (got.get("closed") or ""), got.get("home")), (True, "http://10.0.0.6:5000/party/1"))
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
