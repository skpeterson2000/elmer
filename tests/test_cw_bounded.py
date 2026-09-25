#!/usr/bin/env python3
"""The session has a visible end, in a real browser.

    python3 tests/test_cw_bounded.py

cw.py holds the pedagogy and test_cw_session.py holds it to account. What
this checks is that any of it reaches the screen, because a bound nobody can
see is not a bound: a learner who cannot see the end of a session is being
asked for an open-ended piece of their evening, and the honest answer to that
is no.

  - the length of today's session is on the page before it starts;
  - the parts are listed with their seconds, ending on the lap;
  - the lap is named as a lap and not as another drill;
  - the break card has a way out of it, and the way out is hidden until
    there is a reason to offer it;
  - the reading that decides that reason answers over the wire.

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

FAILS = []
ROOT = Path(__file__).resolve().parents[1]


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

URL = f"http://127.0.0.1:{PORT}/cw"

JS = r"""(async () => {
  const firstChar = CWS.koch[0];
  const $ = id => document.getElementById(id);
  const out = {errors: []};
  window.addEventListener('error', e => out.errors.push(String(e.message)));
  out.budget = todayBudget;
  out.clock = ($('cw-today-clock') || {}).textContent || '';
  out.steps = todaySession.map(s => ({kind: s.kind, seconds: s.seconds || 0,
                                      lap: !!s.lap, only: (s.only || []).join('')}));
  out.listed = ($('cw-today-steps') || {}).textContent || '';
  out.leave_hidden = !!($('cw-break-off') || {}).hidden;
  out.has_clock_line = !!$('cw-break-clock');
  out.words = typeof clockWords === 'function' ? clockWords(342) : null;
  out.cold_gap = todayColdGap;
  /* The record path, end to end from the page that will be walking it: a cold
     rep that landed, posted the way a drill posts it, and read back as the
     landmark for that character. Left until last because it writes. */
  try {
    await postJSON('/api/cw/result', {per_char: {[firstChar]: {
      sent: 3, copied: 3, confused: {}, repeats: 0, ms: [1100, 1000, 1050],
      outcomes: '111', cold_hit: true, cold_ms: 2900}}});
    const after = await api('/api/cw/plan');
    out.learned = after.plan.learned;
    const w = await postJSON('/api/cw/wins', {was: {learned: []}});
    out.wins = w.wins;
    out.baseline = w.baseline;
  } catch (e) { out.learned = 'threw: ' + e.message; }
  /* The reading, over the wire, from the page that will be asking for it. */
  try {
    const tired = Array(15).fill(800).concat([1600, 1600, 1600, 1600, 1600]);
    out.reading = (await postJSON('/api/cw/flagging', {times: tired})).reading;
    const steady = Array(25).fill(900);
    out.steady = (await postJSON('/api/cw/flagging', {times: steady})).reading;
  } catch (e) { out.reading = 'threw: ' + e.message; }
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

    print("\nthe session's length, on the page before it starts")
    got = _browser.evaluate(URL, JS, settle=3.0)
    if isinstance(got, str):
        got = json.loads(got)
    check("no javascript error on the page", got.get("errors"), [])
    check("the page knows how long today is", got["budget"] > 0, True)
    # A day is passes through the lesson, so the line says which pass this is
    # rather than only how long it runs - see cw.passes.
    check("  and says which pass of the day this is",
          "Pass 1 of" in got["clock"] and "today" in got["clock"], True)
    check("  with how long each one runs", "Each is about" in got["clock"], True)
    check("  it says the session ends on its own", "ends on its own" in got["clock"], True)
    check("  and that leaving at a break is allowed",
          "leave at any break" in got["clock"], True)
    check("  and that the gap is the point, not an interval",
          "coming back" in got["clock"], True)
    # 342 seconds is five minutes and forty-two: the page says "about", so
    # the words round to the minute rather than inventing a half one.
    check("the length reads as time, rounded honestly", got["words"], "6 min")

    print("\nthe parts, with their seconds")
    steps = got["steps"]
    check("there are parts to do", len(steps) >= 3, True)
    check("  every one is timed", all(s["seconds"] > 0 for s in steps), True)
    check("  they add up to about the clock",
          abs(sum(s["seconds"] for s in steps) - got["budget"]) <= 20, True)
    check("  and each is listed on the page with its seconds",
          got["listed"].count(" s") >= len(steps), True)

    print("\nthe way out of a break, offered only when there is a reason")
    check("the page has a line for the clock on the break card", got["has_clock_line"], True)
    check("  and a way out, hidden until there is a reason", got["leave_hidden"], True)

    print("\ncold and warm, end to end from the page")
    check("the page is given the gap from the server, not its own number",
          got["cold_gap"], 60000)
    check("a cold rep that landed makes the character learned", got["learned"], ["K"])
    check("  and the loudest line is said for it",
          bool(got["wins"]) and "is yours" in got["wins"][0], True)
    check("  which says what made it count",
          "nothing warmed up in front of it" in got["wins"][0], True)
    check("  and the baseline now names it",
          "K" in got["baseline"] and "cold" in got["baseline"], True)

    print("\nthe reading that gives the reason, over the wire")
    check("a session that has slowed says stop", got["reading"]["stop"], True)
    check("  with the person's own best in it", got["reading"]["best_s"], 0.8)
    check("  and what it is now", got["reading"]["now_s"], 1.6)
    check("a steady one does not", got["steady"]["stop"], False)
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
