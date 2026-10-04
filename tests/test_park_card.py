#!/usr/bin/env python3
"""A tree on the reach map opens the park's card - the POTA page's own card.

    python3 tests/test_park_card.py

The Band Plan's reach map draws a tree at each park being activated, and
hovering one said who and on what. The park itself - how often it is
activated, on what, when, where people set up - was on the POTA / SOTA page,
one card away. Now pressing a tree opens that card under the map. It is the
same card, moved to parkcard.js and loaded by both pages, so the two cannot
describe a park two ways. What is held here, in a real browser:

  - the POTA page still draws its card, with the spots as buttons that set
    the sheet's "of" box;
  - on the Band Plan, a press on a tree opens the card for that park, with
    the spots named rather than offered as buttons there is no sheet for;
  - a press that is the end of a drag does not;
  - Close puts it away.

The park's record is stood in for inside the page: a test does not ask the
program for it over the network.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402

FAILS = []

RECORD = {"ok": True, "kind": "park", "ref": "US-0001", "name": "Test State Park",
          "type": "State Park", "agency": "DNR", "where": "Somewhere County", "grid": "EN26",
          "sentence": "Activated 40 times by 22 operators.",
          "story": {"modes": {"phone": 50, "cw": 30, "data": 20},
                    "by_month": [1, 0, 2, 3, 5, 8, 9, 7, 4, 2, 1, 0], "recent": []},
          "seen": None,
          "spots": {"about": "Spots ELMER holds.",
                    "spots": [{"short": "Boat launch", "kind": "parking", "grid": "EN26aa"}]}}

# The record, stood in for: every /api/reference the page asks for answers
# with RECORD, and the page counts the asking.
STUB = """
window.__asked = [];
const __api = api;
api = async (url, o) => { if (String(url).startsWith('/api/reference')) { window.__asked.push(url); return %s; } return __api(url, o); };
""" % json.dumps(RECORD)

POTA = STUB + r"""
(async () => {
  acCard(await api('/api/reference?ref=US-0001'));
  const box = document.getElementById('ac-pick-card');
  return JSON.stringify({name: (box.querySelector('b') || {}).textContent || '',
                         spotButtons: box.querySelectorAll('.ac-spot').length,
                         links: [...box.querySelectorAll('a.btn')].map(a => a.textContent)});
})()"""

BANDPLAN = STUB + r"""
(async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 40 && !bpData; i++) await wait(150);
  document.getElementById('bp-reach').hidden = false;
  bpReachBind();
  const canvas = document.getElementById('bp-reach-map');
  canvas.setPointerCapture = () => {};          // synthetic pointers are not capturable
  const r = canvas.getBoundingClientRect(), k = canvas.width / r.width;
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  bpSpotHits = [{x: (cx - r.left) * k, y: (cy - r.top) * k, kind: 'pota', age: 3,
                 s: {ref: 'US-0001', call: 'W0TST', name: 'Test State Park'}}];
  const press = (x0, y0, x1, y1) => {
    canvas.dispatchEvent(new PointerEvent('pointerdown', {clientX: x0, clientY: y0, pointerId: 7, bubbles: true}));
    canvas.dispatchEvent(new PointerEvent('pointerup', {clientX: x1, clientY: y1, pointerId: 7, bubbles: true}));
  };
  const box = document.getElementById('bp-park');
  press(cx - 60, cy, cx, cy);                    // a drag that ends on the tree
  const afterDrag = !box.hidden;
  await wait(400);                               // past the double-tap window
  press(cx, cy, cx, cy);                         // a press on it
  await wait(300);
  const card = document.getElementById('bp-park-card');
  const opened = {set: box.classList.contains('park-box') && box.classList.contains('arrive'), shown: !box.hidden, name: (card.querySelector('b') || {}).textContent || '',
                  spotButtons: card.querySelectorAll('.ac-spot').length,
                  spotsNamed: card.textContent.includes('Boat launch'), asked: window.__asked.slice(),
                  links: [...card.querySelectorAll('a.btn')].map(a => [a.textContent, a.href, a.target])};
  await wait(400);
  press(r.left + 20, r.top + 20, r.left + 20, r.top + 20);   // empty map
  const emptyAsked = window.__asked.length;
  document.getElementById('bp-park-shut').click();
  return JSON.stringify({afterDrag, opened, emptyAsked, closed: box.hidden});
})()"""


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        print("\nFAILED: this test needs chromium")
        return 1
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
         "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port, timeout=1).close()
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise SystemExit("the throwaway server never answered")
        pota = json.loads(_browser.evaluate("http://127.0.0.1:%d/activations" % port, POTA, settle=1.5))
        bp = json.loads(_browser.evaluate("http://127.0.0.1:%d/bandplan" % port, BANDPLAN, settle=2.0))
    finally:
        server.terminate()

    print("\n-- the POTA / SOTA page --")
    check("the card is drawn for the place picked", pota["name"], "Test State Park")
    check("  with the spots as buttons for the sheet", pota["spotButtons"], 1)
    check("  and the park on POTA, with no activator to name", pota["links"], ["US-0001 on POTA"])

    print("\n-- the Band Plan's reach map --")
    check("the end of a drag over a tree opens nothing", bp["afterDrag"], False)
    check("a press on a tree opens the park's card", (bp["opened"]["shown"], bp["opened"]["name"]),
          (True, "Test State Park"))
    check("  set apart in its own tinted box, washed as it arrives", bp["opened"]["set"], True)
    check("  asking for that park", bp["opened"]["asked"], ["/api/reference?ref=US-0001"])
    check("  the spots named, not offered as buttons with no sheet here",
          (bp["opened"]["spotsNamed"], bp["opened"]["spotButtons"]), (True, 0))
    check("  with the park and the activator on POTA, opening beside ELMER", bp["opened"]["links"],
          [["US-0001 on POTA", "https://pota.app/#/park/US-0001", "_blank"],
           ["W0TST on POTA", "https://pota.app/#/profile/W0TST", "_blank"]])
    check("a press on empty map asks for nothing", bp["emptyAsked"], 1)
    check("Close puts it away", bp["closed"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
