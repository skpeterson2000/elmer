#!/usr/bin/env python3
"""The Set QTH button, pressed in a real browser, on every page that has one.

    python3 tests/test_setqth.py

Reported as "only pretends to work", and it did, in four separate ways:

  - an empty box answered "Not found", which is not what happens when
    nothing was looked for;
  - six matches on screen answered "Not found" as well;
  - a typo changed one line of small grey text and nothing else, so the
    press looked as though it had landed;
  - and on the EME page the button had no click handler attached at all.
    initPlace was called and its return value dropped, so that button did
    nothing, quietly, on every press it ever got.

Two quieter ones went with them: a town name was saved twice - once by the
picker's onPick and once by the caller - and the box arrived holding a name
rather than a place, so the first press had to geocode the QTH it had just
been shown, which on a unit with no network is the one QTH that cannot be
set.

What is checked here is that every press now either saves exactly once or
says why not. This test requires Chromium and fails - not skips - without it.
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

# The geocoder this test used to reach is somebody else's server on the far
# side of the internet, with a rate limit on it. So the test passed on its own
# and failed inside a full run, which is the worst way for a test to behave -
# and what it was reporting was Nominatim's mood, not this program's behavior.
# The three answers the page has to tell apart are canned here instead: one
# place, several places, none. Everything from the box to the save is still
# the real path.
STUB = """
from elmer import geocode
def _search(query, limit=6):
    q = (query or "").strip().lower()
    if q.startswith("springfield"):
        return [{"name": "Springfield, Illinois", "lat": 39.8, "lon": -89.65,
                 "kind": "place"},
                {"name": "Springfield, Missouri", "lat": 37.2, "lon": -93.3,
                 "kind": "place"}]
    if q.startswith("pequot"):
        return [{"name": "Pequot Lakes, Minnesota", "lat": 46.6, "lon": -94.31,
                 "kind": "place"}]
    return []
geocode.search = _search
"""
PORT = _browser._free_port()
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n%s\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
     % (str(ROOT), STUB, PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Each press is watched through fetch, because "did it save" is a question
# about what went to the server and not about what the screen said.
JS = r"""(async () => {
  const out = {};
  const calls = [];
  const realFetch = window.fetch;
  window.fetch = (...a) => { calls.push(String(a[0]).replace(/^https?:\/\/[^/]+/, '')); return realFetch(...a); };
  const input = document.getElementById('q-place');
  const btn = document.getElementById('q-save');
  out.has_button = !!btn;
  out.has_box = !!input;
  if (!btn || !input) return out;
  const toasts = () => Array.from(document.querySelectorAll('#toaster .toast')).map(
    t => t.querySelector('b').textContent).join(' // ');
  const listShown = () => { const l = document.getElementById('q-place-results'); return !!(l && !l.hidden); };

  async function press(label, text) {
    calls.length = 0;
    document.querySelectorAll('#toaster .toast').forEach(t => t.remove());
    input.value = text;
    input._place = null;
    btn.click();
    await new Promise(r => setTimeout(r, 1200));
    const said = toasts();
    await new Promise(r => setTimeout(r, 2600));
    out[label] = {saves: calls.filter(u => u.indexOf('/api/settings') === 0).length,
                  said: said || toasts(), picklist: listShown()};
  }
  await press('empty', '');
  await press('ambiguous', 'Springfield');
  await press('nonsense', 'zzqqxx nowhere');
  await press('grid', 'EN34kp');
  await press('town', 'Pequot Lakes, MN');
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

    for page in ("propagation", "eme"):
        print(f"\n-- /{page} --")
        got = _browser.evaluate(f"http://127.0.0.1:{PORT}/{page}", JS, settle=4.0)
        if isinstance(got, str):
            got = json.loads(got)
        check("the page has a Set QTH button and a box", (got["has_button"], got["has_box"]), (True, True))

        # Nothing typed. Nothing was looked for, so "not found" is the wrong
        # answer - and the press must not be silent either.
        check("an empty box saves nothing", got["empty"]["saves"], 0)
        check("  and says what to type instead of 'not found'",
              got["empty"]["said"], "Nothing to set yet")

        # Several matches: the list is the answer, and the button says so.
        check("an ambiguous name saves nothing", got["ambiguous"]["saves"], 0)
        check("  and sends the person to the list", got["ambiguous"]["said"], "More than one place matches")
        check("  which is on screen", got["ambiguous"]["picklist"], True)

        # No match: said out loud, and last search's list taken down.
        check("a name that matches nothing saves nothing", got["nonsense"]["saves"], 0)
        check("  and says so where it will be seen", got["nonsense"]["said"], "No place found")
        check("  with no stale list left standing", got["nonsense"]["picklist"], False)

        # A grid square needs no network at all: placeLocal reads it.
        check("a grid square saves, once", got["grid"]["saves"], 1)
        check("  and says it is set", got["grid"]["said"], "QTH set")

        # A town name goes through the geocoder, and is saved once - not twice,
        # which is what onPick and the caller both saving came to.
        check("a town name saves, once and not twice", got["town"]["saves"], 1)
        check("  and says it is set", got["town"]["said"], "QTH set")
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
