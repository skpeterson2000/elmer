#!/usr/bin/env python3
"""What the drill hears has to reach the record, and the page has to say so.

    python3 tests/test_cw_record_lands.py

Everything else in the CW work - what is solid, what was named cold, which
days a character survived, whether the lesson opens - is read off the record,
and the record is written by one POST at the end of a one-at-a-time step. A
session that runs beautifully and never sends it is indistinguishable from a
session that never happened, and it looks fine from the outside: the drill
scores on the screen, the letters go green, and nothing is kept.

It had stopped. The paragraph that says "K took 2.6 s when you started and
0.9 s now" reads the server's answer, and it had been written above the line
that fetches it - `res` is a const, so reaching for it there threw before the
POST was ever made. Two days of drills went into nothing, silently, because
the throw happened after the score was already on the screen.

So: run a real pass of the one-at-a-time drill in a browser, answer it, and
insist that the record comes back changed. The drill is narrowed to one
character so the answers can be given without decoding anything.

This test requires Chromium and fails - not skips - without it. The audio
policy is asked for, because a drill that will not sound never asks anything.
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
     "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

JS = r"""(async () => {
  const out = {errors: []};
  window.addEventListener('error', e => out.errors.push(String(e.message)));
  window.addEventListener('unhandledrejection',
    e => out.errors.push(String((e.reason && e.reason.message) || e.reason)));
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);

  document.querySelector('#cw-modes [data-mode=today]').click();
  await sleep(600);
  out.before = JSON.parse(JSON.stringify((CWS.progress || {}).K || {sent: 0}));

  /* One step, one character, a few seconds of it: the same code path a
     whole session runs, short enough to sit through. */
  todaySession = [{kind: 'flash', seconds: 6, only: ['K'], chars: ['K'],
                   why: 'one character at a time'}];
  todayBudget = 6;
  /* The answer, given the way the drill takes one. Narrowed to K, so it is
     always right and the record has something unambiguous to show. */
  const tick = setInterval(() => { if (flashKey) flashKey('K'); }, 120);
  $('cw-today-start').click();
  await sleep(13000);
  clearInterval(tick);

  out.after = JSON.parse(JSON.stringify((CWS.progress || {}).K || {sent: 0}));
  out.said = ($('cw-today-result').textContent || '').slice(0, 300);
  out.score = ($('cw-flash-score').textContent || '');
  return out;
})()"""

try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/ping", timeout=1).close()
            break
        except Exception:
            time.sleep(0.2)
    else:
        print("\nFAILED: the server did not come up")
        sys.exit(1)

    got = _browser.evaluate(f"http://127.0.0.1:{PORT}/cw", JS, settle=3.0, flags=FLAGS)
    if isinstance(got, str):
        got = json.loads(got)

    print("\nthe drill runs")
    check("no javascript error", got.get("errors"), [])
    check("  and nothing was reached before it existed",
          [e for e in got.get("errors") or [] if "before initialization" in e], [])
    check("  the drill asked and was answered", bool(got["score"].strip()), True)

    print("\nand what it heard reaches the record")
    before = int((got["before"] or {}).get("sent") or 0)
    after = int((got["after"] or {}).get("sent") or 0)
    check("the character has more sends against it than before", after > before, True)
    check("  and they are counted as copied", int((got["after"] or {}).get("copied") or 0) > 0, True)
    check("  the page said what the pass came to",
          "One at a time" in got["said"] and "%" in got["said"], True)
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
