#!/usr/bin/env python3
"""The icon in the corner keys ELMER's name again, and only the icon.

    python3 tests/test_say_name.py

Asked for plainly: it would be cool if ELMER said its name when you click
the icon. It is - and it fits the machinery better than it looks, because
browsers keep audio silent until a page has been touched and a press on the
icon is a touch.

What is held here:

  - a press on the icon keys the name, and does not leave the page: the
    wordmark beside it is still the way home, so are the words Dashboard
    in the bar, and turning the logo into something that leaves would take
    a habit away from everybody for one person's sake;
  - a second press restarts it rather than keying two names at once;
  - with the announcement switched off in the Station panel, the icon is a
    plain link and keys nothing, because the room where the announcement
    is unwelcome is exactly the room where a stray click must not sound;
  - a page that has already announced does not announce again just
    because the script now also serves the icon.

This test requires Chromium and fails - not skips - without it.
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

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ("--autoplay-policy=no-user-gesture-required",)
FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


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

# Let the opening announcement finish, then press the icon and see what
# happens to the keyer and to the page.
PRESS_JS = r"""(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const out = {};
  await sleep(3500);                              // the opening one is done
  const icon = document.querySelector('.brand-icon') || document.querySelector('.brand-mark');
  out.bound = icon ? icon.dataset.cwBound : null;
  out.title = icon ? icon.title : null;
  out.exposed = typeof window.elmerSayName;
  const before = player.playingUntil;
  const wasAt = location.pathname;
  icon.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
  await sleep(250);
  out.first = {keyed: player.playingUntil > before, hold: toneHold,
               stillHere: location.pathname === wasAt};
  const mid = player.playingUntil;
  icon.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
  await sleep(250);
  // A restart schedules a fresh send from now, so the end moves later;
  // two overlapping sends would leave it where the first one put it.
  out.second = {restarted: player.playingUntil > mid};
  await sleep(3500);
  out.after = {hold: toneHold};
  // The wordmark is not bound; it is the link it always was.
  const mark = document.querySelector('.brand-mark');
  out.mark = {bound: mark ? (mark.dataset.cwBound || null) : null,
              inLink: !!(mark && mark.closest('a.brand[href="/"]'))};
  return JSON.stringify(out);
})()"""

# Switched off: the icon has not been touched by the script at all.
QUIET_JS = r"""JSON.stringify((() => {
  const icon = document.querySelector('.brand-icon') || document.querySelector('.brand-mark');
  return {flag: window.ELMER_ANNOUNCE.on, bound: icon ? (icon.dataset.cwBound || null) : null,
          title: icon ? icon.title : null, exposed: typeof window.elmerSayName,
          ctx: player.ctx ? player.ctx.state : null};
})())"""


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

    print("\n-- the icon keys the name, and stays on the page --")
    got = json.loads(_browser.evaluate(HOME, PRESS_JS, settle=1.0, flags=FLAGS,
                                       cookies={'elmer_user': '1'}))
    check("the icon is wired", got["bound"], "1")
    check("  and says so on hover", got["title"], "ELMER, in code")
    check("  and the sender is reachable by name too", got["exposed"], "function")
    check("a press keys it", got["first"]["keyed"], True)
    check("  on the program's pitch", got["first"]["hold"], 1020)
    check("  without leaving the page", got["first"]["stillHere"], True)
    check("a second press restarts rather than overlapping", got["second"]["restarted"], True)
    check("and the pitch is put back when it is done", got["after"]["hold"], None)
    check("the wordmark is not wired - it is still the way home",
          (got["mark"]["bound"], got["mark"]["inLink"]), (None, True))

    print("\n-- switched off, the icon is a plain link --")
    check("the switch saves", settings(announce=False), 200)
    got = json.loads(_browser.evaluate(HOME, QUIET_JS, settle=1.5, flags=FLAGS,
                                       cookies={'elmer_user': '1'}))
    check("the page is told not to", got["flag"], False)
    check("  the icon is untouched", (got["bound"], got["title"]), (None, ""))
    check("  nothing is exposed to press", got["exposed"], "undefined")
    check("  and nothing was opened to sound with", got["ctx"], None)
    check("switched back on", settings(announce=True), 200)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


try:
    code = main()
finally:
    server.terminate()
sys.exit(code)
