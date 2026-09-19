#!/usr/bin/env python3
"""ELMER says its own name in code when it opens, and stops when told to.

    python3 tests/test_announce.py

Five characters at twenty words a minute on 1020 Hz: the station
identifying itself, and a plain way of hearing that the unit is up and the
sound works before anybody goes looking for a volume control.

Three things are worth holding down, and none of them can be checked
without a JavaScript engine and a running audio clock.

It happens once when the program opens, not once a page. The announcement
marks this tab's session storage, and the guard on that mark is what keeps
walking round the pages quiet.

It uses the program's own pitch. The operator's practice tone is theirs to
set and is left alone: the announcement holds 1020 Hz for the length of the
sending and puts the pitch back afterwards, so nothing else on the page
inherits it.

It can be switched off, and off means silent rather than quiet - with the
switch off no audio context is opened at all. A net in progress, a
classroom, a field site at night: being quiet is sometimes what being in a
community asks of a station.

This test requires Chromium and fails - not skips - without it, and asks
for the autoplay policy that lets an audio clock run without a click.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402

FAILS = []
ROOT = Path(__file__).resolve().parents[1]
FLAGS = ("--autoplay-policy=no-user-gesture-required",)


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


check("chromium is on this machine", bool(_browser.available()), True)
if not _browser.available():
    print("\nFAILED: this test needs chromium")
    sys.exit(1)

PORT = _browser._free_port()
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\n"
     "from elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
     % (str(ROOT), PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

HOME = f"http://127.0.0.1:{PORT}/"

# Caught while it is still sending, then again once it has finished, and
# then the script is handed back its own guard: loaded a second time in a
# page that has already announced, it must do nothing at all.
SPEAKING_JS = r"""(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const out = {};
  out.sending = {flag: window.ELMER_ANNOUNCE.on, hold: toneHold, tone: cwPrefs().tone,
                 state: player.ctx ? player.ctx.state : null,
                 playing: !!player.playingUntil,
                 marked: sessionStorage.getItem('elmer.announced')};
  await sleep(4000);
  out.finished = {hold: toneHold, tone: cwPrefs().tone};
  const was = player.playingUntil;
  const again = document.createElement('script');
  again.src = document.querySelector('script[src*="announce"]').src;
  document.body.appendChild(again);
  await sleep(1500);
  out.second_time = {same: player.playingUntil === was};
  return JSON.stringify(out);
})()"""

# With the switch off there is nothing to hear and nothing opened to hear
# it with.
QUIET_JS = r"""JSON.stringify({flag: window.ELMER_ANNOUNCE.on,
                               ctx: player.ctx ? player.ctx.state : null,
                               playing: !!player.playingUntil,
                               marked: sessionStorage.getItem('elmer.announced'),
                               box: document.getElementById('setup-announce').checked})"""


LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def told(page):
    """What the page tells announce.js to do: {on, de}."""
    found = re.search(r"window[.]ELMER_ANNOUNCE = ([{].*?[}]);", page)
    return json.loads(found.group(1)) if found else {}


def settings(**body):
    req = urllib.request.Request(
        HOME + "api/settings", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req, timeout=10).status


def main():
    for _ in range(100):
        try:
            urllib.request.urlopen(HOME, timeout=1).read()
            break
        except Exception:
            time.sleep(0.2)

    print("\n-- it says its name when it opens --")
    got = json.loads(_browser.evaluate(HOME, SPEAKING_JS, settle=1.0, flags=FLAGS, cookies={'elmer_user': '1'}))
    check("a station with nothing set announces - it is on unless turned off",
          got["sending"]["flag"], True)
    check("  and it is keying while the page is still new",
          (got["sending"]["state"], got["sending"]["playing"]), ("running", True))
    check("  on the program's own pitch, not the operator's practice tone",
          (got["sending"]["hold"], got["sending"]["tone"]), (1020, 1020))
    check("  with this opening marked, which is what keeps it to one",
          got["sending"]["marked"], "1")
    check("the pitch is put back when the sending is done",
          (got["finished"]["hold"], got["finished"]["tone"]), (None, 1020))
    check("and a page that has announced does not announce again",
          got["second_time"]["same"], True)

    print("\n-- and stops when the station asks for quiet --")
    check("the switch saves", settings(announce=False), 200)
    got = json.loads(_browser.evaluate(HOME, QUIET_JS, settle=1.5, flags=FLAGS, cookies={'elmer_user': '1'}))
    check("the page is told not to", got["flag"], False)
    check("  nothing sounds, and nothing is opened to sound it with",
          (got["ctx"], got["playing"], got["marked"]), (None, False, None))
    check("  and the Station panel shows it off", got["box"], False)
    check("switched back on", settings(announce=True), 200)
    got = json.loads(_browser.evaluate(HOME, QUIET_JS, settle=1.5, flags=FLAGS, cookies={'elmer_user': '1'}))
    check("it speaks again", (got["flag"], got["playing"], got["box"]), (True, True, True))

    print("\n-- a supporter's own callsign goes out with it --")
    from elmer import cw, supporter
    import elmer.app as appmod
    check("a callsign is keyable as it stands", cw.keyable("KC9SP"), "KC9SP")
    check("  lower case is raised", cw.keyable("kc9sp"), "KC9SP")
    check("  a portable callsign keeps its slant", cw.keyable("KC9SP/M"), "KC9SP/M")
    check("  what the code has no letter for is dropped", cw.keyable("K.C9-SP!"), "KC9SP")
    # Whole words only. A club name cut off in the middle is worse than a
    # short one: this is somebody's name being read out to a room.
    check("  a club name is kept whole while it fits", cw.keyable("PINE COUNTY ARC"), "PINE COUNTY")
    check("  and a name with nothing keyable in it is left out", cw.keyable("..."), "")

    client = appmod.app.test_client()
    # ELMER's own pages ask who is at the controls first; a test driving one
    # says so, the same as a person would.
    client.post("/api/users/switch", json={"id": 1}, environ_base=LOCAL)
    check("a station that is nobody in particular keys ELMER alone",
          told(client.get("/", environ_base=LOCAL).data.decode("utf-8")).get("de"), "")
    real = supporter.named_holder
    try:
        supporter.named_holder = lambda conn: "KC9SP"
        page = client.get("/", environ_base=LOCAL).data.decode("utf-8")
        check("a supporter who asked to be named has their callsign keyed after DE",
              told(page).get("de"), "KC9SP")
        check("  and the Station panel says what will go out",
              "ELMER DE KC9SP" in page, True)
        # The same consent the hall's thanks card keeps: a supporter who
        # would rather not be named is not named, here as anywhere else.
        supporter.named_holder = lambda conn: ""
        check("a supporter who would rather not be named is not",
              told(client.get("/", environ_base=LOCAL).data.decode("utf-8")).get("de"), "")
    finally:
        supporter.named_holder = real

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


try:
    code = main()
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()
sys.exit(code)
