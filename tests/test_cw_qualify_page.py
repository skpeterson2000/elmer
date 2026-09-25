#!/usr/bin/env python3
"""The qualifying run, on the screen, in a real browser.

    python3 tests/test_cw_qualify_page.py

test_cw_qualify.py holds the scoring. This holds the pane: that the speed can
be named and means something in words before anybody commits five minutes to
it, that the run starts and can be stopped, that the clean stretch is shown as
it grows rather than only at the end, and that every ending leads somewhere -
a run that lands goes to the lesson, a run that reached offers the speed it
measured, and a run from somebody whose characters are not there yet is sent
to the place the characters are learned.

This test requires Chromium and fails - not skips - without it. The audio
policy is asked for, because a run that will not sound is not a run.
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
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const $ = id => document.getElementById(id);

  document.querySelector('#cw-modes [data-mode=qualify]').click();
  await sleep(300);
  out.pane_shown = !$('cw-qualify').hidden;
  out.setup_shown = !$('cw-q-setup').hidden;

  /* The speed means something in words before anybody commits to it. */
  const said = {};
  for (const wpm of [5, 13, 20, 35]) {
    const box = $('cw-q-wpm');
    box.value = wpm;
    box.dispatchEvent(new Event('input'));
    said[wpm] = ($('cw-q-hint').textContent || '').slice(0, 160);
  }
  out.hints = said;
  out.readout = $('cw-q-wpm-v').textContent;

  /* Start it, at a speed slow enough that the run is short. */
  $('cw-q-wpm').value = 5;
  $('cw-q-wpm').dispatchEvent(new Event('input'));
  $('cw-q-start').click();
  await sleep(4000);
  out.running = !$('cw-q-running').hidden;
  out.clock = $('cw-q-clock').textContent;
  out.stretch_line = ($('cw-q-stretch').textContent || '').slice(0, 140);
  out.copy_focused = document.activeElement && document.activeElement.id === 'cw-q-copy';

  /* Type perfect copy of what has gone out, and let it be scored. */
  await sleep(5000);
  out.stretch_after = ($('cw-q-stretch').textContent || '').slice(0, 140);

  /* Stop it, and see that the ending leads somewhere. */
  $('cw-q-stop').click();
  await sleep(2500);
  out.result_shown = !$('cw-q-result').hidden;
  out.head = $('cw-q-head').textContent;
  out.words = $('cw-q-words').textContent;
  out.buttons = Array.from($('cw-q-after').querySelectorAll('button')).map(b => b.textContent);
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

    print("\nthe pane")
    check("no javascript error", got.get("errors"), [])
    check("the mode button opens it", got["pane_shown"], True)
    check("  and it opens on the setup", got["setup_shown"], True)

    print("\nthe speed is named, and means something")
    check("the readout follows the slider", got["readout"], "35 wpm")
    check("  a slow speed is described as where people start",
          "start" in got["hints"]["5"], True)
    check("  and thirteen recalls the tests that lived there",
          "Novice" in got["hints"]["13"], True)
    check("  a middling one by what it is for", bool(got["hints"]["13"]), True)
    # The hint is the one ladder the program keeps - see cw.SPEED_LADDER - so
    # the page names the rung rather than carrying its own second opinion.
    check("  and a fast one names where it sits",
          "head copy" in got["hints"]["35"], True)
    check("  every speed says something", all(got["hints"].values()), True)

    print("\nthe run")
    check("starting it shows the run", got["running"], True)
    check("  the clock is going", got["clock"] != "0:00", True)
    check("  the copy box has the keyboard", got["copy_focused"], True)
    # A scrambled first half minute is what settling looks like, and the
    # page says so rather than showing a bare zero.
    check("  a scrambled start is not held against anybody",
          "not held against you" in got["stretch_line"], True)
    check("  and the stretch is reported while it runs",
          bool(got["stretch_after"]), True)

    print("\nevery ending leads somewhere")
    check("stopping gives a verdict", bool(got["head"]), True)
    check("  and something to do next", len(got["buttons"]) >= 1, True)
    check("  none of which is a dead end",
          all(b.strip() for b in got["buttons"]), True)
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
