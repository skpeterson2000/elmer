#!/usr/bin/env python3
"""Looking for a game, rather than waiting to overhear one.

    python3 tests/test_scan.py

KC9SP, 2026-09-12: "We need a button to scan for active waiting rooms or
games to join. If a person misses the first opportunity, it's gone (without
the terminal - we're in kiosk mode)." Hearing is passive and can fail - the
same evening a unit was found announcing down its other interface - and the
offer to join appears once. So there is a button that looks: every address
on the unit's own subnets is asked on ELMER's port, and what answers is
remembered for a minute so the offer, the dashboard's panel and auto-join all
see it as if it had been heard.

What is proved here: which addresses a sweep asks; how a unit's answer
becomes a roster entry; that heard and found merge without doubling a net;
that a find ages out; that the route and both views carry it; and, in the
Chromium the kiosk runs, that the button brings the offer back on a table
that had been cut loose by hand.
"""
import ipaddress
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
from elmer import app as appmod, cohort, db, discovery  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


I = ipaddress.IPv4Interface

print("\nwhich addresses a sweep asks")
hosts = discovery.hosts_to_sweep([I("192.168.1.119/24")])
check("a /24, less this unit", len(hosts), 253)
check("  and not this unit's own address", "192.168.1.119" in hosts, False)
check("  first and last", (hosts[0], hosts[-1]), ("192.168.1.1", "192.168.1.254"))
hosts = discovery.hosts_to_sweep([I("10.20.30.40/16")])
check("a /16 is cut to the /24 around us", len(hosts), 253)
check("  in the right block", hosts[0], "10.20.30.1")
hosts = discovery.hosts_to_sweep([I("192.168.1.119/24"), I("192.168.1.120/24")])
check("two interfaces on one subnet ask it once", len(hosts), 252)
hosts = discovery.hosts_to_sweep([I("192.168.1.5/24"), I("10.42.0.7/24")])
check("two subnets, both asked", len(hosts), 506)

print("\nwhat an answering unit becomes on the roster")
rec = discovery._net_record("http://10.0.0.5:5000",
                            {"hosting": True, "name": "General net", "token": "tok-g",
                             "difficulty": "general", "units": 4, "round": 7,
                             "mode": "play"})
check("a host is a net", (rec["name"], rec["token"], rec["units"], rec["round"], rec["mode"]),
      ("General net", "tok-g", 4, 7, "play"))
rec = discovery._net_record("http://10.0.0.6:5000",
                            {"table_of": "http://10.0.0.5:5000", "table_in": "General net",
                             "table_token": "tok-g"})
check("a table points at its host", (rec["url"], rec["via"]),
      ("http://10.0.0.5:5000", "http://10.0.0.6:5000"))
check("a unit on its own is not a net",
      discovery._net_record("http://10.0.0.7:5000", {"playing_here": True}), None)

print("\nheard and found merge without doubling a net")
heard = [{"url": "http://10.0.0.5:5000", "name": "General net", "token": "tok-g",
          "difficulty": "general", "units": 4, "round": 7, "mode": "play"}]
found = [{"url": "http://10.0.0.5:5000/", "name": "General net", "token": "tok-g",
          "difficulty": "general", "units": 4, "round": 7, "mode": "play"},
         {"url": "http://10.0.0.9:5000", "name": "Technician net", "token": "tok-t",
          "difficulty": "technician", "units": 1, "round": 0, "mode": ""}]
merged = discovery.merge_nets(heard, found)
check("two nets, not three", [n["name"] for n in merged], ["General net", "Technician net"])
moved = [{"url": "http://10.0.0.77:5000", "name": "General net", "token": "tok-g",
          "difficulty": "general", "units": 4, "round": 7, "mode": "play"}]
check("the same token at a new address is the same net",
      len(discovery.merge_nets(heard, moved)), 1)

print("\na find ages out")
with discovery._found_lock:
    discovery._found.clear()
    discovery._found["http://10.0.0.9:5000"] = (found[1], time.time() - discovery.SWEEP_KEEP + 5)
check("fresh, it is on the list", [n["name"] for n in discovery.found_nets()], ["Technician net"])
check("  stale, it is gone", discovery.found_nets(now=time.time() + 10), [])

print("\nthe route, and both views, carry what was found")
appmod.app.config["TESTING"] = True
connection = db.connect()
was_sweep = discovery.sweep
was_auto = db.unit_get(connection, cohort.AUTO_SETTING)
TECH = {"url": "http://10.0.0.9:5000", "name": "Technician net", "token": "tok-t",
        "difficulty": "technician", "units": 1, "round": 0, "mode": ""}


def fake_sweep(port=5000, extra_urls=(), interfaces=None):
    with discovery._found_lock:
        discovery._found[TECH["url"]] = (dict(TECH), time.time())
    return {"nets": [dict(TECH)], "asked": 253, "answered": 1, "seconds": 1.4,
            "extra": list(extra_urls)}


try:
    cohort.disconnect(connection)
    discovery.sweep = fake_sweep
    with discovery._found_lock:
        discovery._found.clear()
    with appmod.app.test_client() as client:
        r = client.post("/api/nets/scan", json={})
        body = r.get_json()
        check("the scan answers", r.status_code, 200)
        check("  with the net", [n["name"] for n in body["nets"]], ["Technician net"])
        check("  and what it did", (body["asked"], body["answered"]), (253, 1))
        check("the table's view now hears it",
              [n["name"] for n in client.get("/api/party/net").get_json()["heard"]],
              ["Technician net"])
        check("and so does the dashboard's",
              [n["name"] for n in client.get("/api/peers").get_json()["summary"]["nets"]],
              ["Technician net"])
        # The remembered net is asked by address even when it is off the
        # unit's own subnets: a host on the other side of a router.
        db.unit_set(connection, cohort.URL_SETTING, "http://172.16.9.9:5000")
        body = client.post("/api/nets/scan", json={}).get_json()
        check("the remembered net is asked as well", body.get("extra"),
              ["http://172.16.9.9:5000"])
        db.unit_set(connection, cohort.URL_SETTING, "")
finally:
    discovery.sweep = was_sweep
    cohort.disconnect(connection)
    db.unit_set(connection, cohort.AUTO_SETTING, was_auto)
    with discovery._found_lock:
        discovery._found.clear()

# --------------------------------------------------------------- the screen
print("\nthe button brings the offer back on a table cut loose by hand")
check("chromium is on this machine", bool(_browser.available()), True)
ROOT = Path(__file__).resolve().parents[1]
PORT = _browser._free_port()
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys, time; sys.path.insert(0, %r)\n"
     "from elmer import discovery\n"
     "TECH = %r\n"
     "def fake_sweep(port=5000, extra_urls=(), interfaces=None):\n"
     "    with discovery._found_lock:\n"
     "        discovery._found[TECH['url']] = (dict(TECH), time.time())\n"
     "    return {'nets': [dict(TECH)], 'asked': 253, 'answered': 1, 'seconds': 1.4}\n"
     "discovery.sweep = fake_sweep\n"
     "from elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
     % (str(ROOT), TECH, PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def settle_then(js, wait_for):
    return (f"new Promise(res => {{ const t0 = Date.now(); const f = () => {{"
            f" if (({wait_for}) || Date.now() - t0 > 12000) res({js});"
            f" else setTimeout(f, 200); }}; f(); }})")


SHAPE = ("JSON.stringify({offer: !offer.hidden, own: !owncontrols.hidden,"
         " byaddress: !netbyaddress.hidden,"
         " scanButtons: document.querySelectorAll('[data-scan]').length,"
         " said: (document.getElementById('scansaid') || {}).textContent,"
         " offerText: document.getElementById('offer').textContent.replace(/\\\\s+/g, ' ').trim().slice(0, 400)})")

try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        raise SystemExit("the throwaway server never answered")
    # Cut loose by hand first: auto-join off, nothing heard, nothing offered.
    urllib.request.urlopen(urllib.request.Request(
        f"http://127.0.0.1:{PORT}/api/party/net", data=b'{"join": false}',
        headers={"Content-Type": "application/json"}), timeout=5).read()
    url = f"http://127.0.0.1:{PORT}/party"
    got = json.loads(_browser.evaluate(
        url, settle_then(SHAPE, "!owncontrols.hidden && !netbyaddress.hidden"),
        settle=0.5, cookies={'elmer_user': '1'}) or "{}")
    check("on its own: the host's controls", got.get("own"), True)
    check("  no offer", got.get("offer"), False)
    check("  and a button to look", got.get("scanButtons", 0) >= 1, True)

    got = json.loads(_browser.evaluate(
        url,
        "new Promise(res => { const t0 = Date.now(); const f = () => {"
        "  const b = document.querySelector('#netbyaddress [data-scan]');"
        "  if (b && typeof scanForGames === 'function') { b.click(); res(true); } else if (Date.now() - t0 > 12000) res(false);"
        "  else setTimeout(f, 200); }; f(); }).then(() => " +
        settle_then(SHAPE, "!offer.hidden") + ")", settle=0.5, cookies={'elmer_user': '1'}) or "{}")
    check("after looking: the offer is back", got.get("offer"), True)
    check("  naming the net found", "Technician net" in got.get("offerText", ""), True)
    check("  and saying what it is doing",
          "waiting for players" in got.get("offerText", ""), True)
    check("  the button said how many", "1 net found" in (got.get("said") or ""), True)

    # The dashboard has the same button, and the panel it brings up.
    got = json.loads(_browser.evaluate(
        f"http://127.0.0.1:{PORT}/",
        "new Promise(res => { const t0 = Date.now(); const f = () => {"
        "  const b = document.querySelector('[data-scan-games]');"
        "  if (b && typeof scanForGames === 'function') { b.click(); res(true); } else if (Date.now() - t0 > 12000) res(false);"
        "  else setTimeout(f, 200); }; f(); }).then(() => " +
        settle_then("JSON.stringify({panel: !!document.querySelector('#peers [data-role=table]'),"
                    " said: (document.getElementById('scan-said') || {}).textContent,"
                    " text: (document.getElementById('peers') || {}).textContent.replace(/\\\\s+/g, ' ').slice(0, 800)})",
                    # The panel may already be up from the page's own poll - the
                    # table screen's look a moment ago is remembered - so the
                    # wait is on the button's own word, not on the panel.
                    "/found/.test((document.getElementById('scan-said') || {}).textContent || '')") + ")",
        settle=2.5, cookies={'elmer_user': '1'}) or "{}")
    check("the dashboard's button brings the panel up", got.get("panel"), True)
    check("  with a Join button for the net",
          "Join Technician net" in (got.get("text") or ""), True)
    check("  and says so", "1 net found" in (got.get("said") or ""), True)
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
