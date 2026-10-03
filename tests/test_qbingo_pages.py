#!/usr/bin/env python3
"""Q-code bingo on the table screen and a phone, against a running unit.

    python3 tests/test_qbingo_pages.py

A real table, two people seated, bingo started through the same route the
tile uses. The table: the tile is lit, the stage says to listen, and Key
the next code sends a code to the speaker without writing it. Ann's phone:
a card of sixteen meanings and no codes; the top row marked and Bingo
called before those codes are keyed is refused, with the reason; once they
are keyed it stands; the finished card shows its codes; and the table then
says who won.
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


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def post(base, path, body):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Cookie": "elmer_user=1"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"{}")


TABLE = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 80 && !(lastTableState && lastTableState.qbingo); i++) await sleep(150);
  qbAutoOn = false;                                       // the test presses; no calls of its own
  window.__sounds = [];
  ballPlayer = {send: (groups) => __sounds.push(groups.map(g => g.map(c => c.char).join('')).join(' '))};
  await sleep(300);
  const stage = () => document.getElementById('stage').textContent.replace(/\s+/g, ' ');
  const out = {chosen: !!document.querySelector('#qbingo.chosen'), before: stage(),
               tilesHidden: document.querySelector('.gc-tiles').hidden, stop: !document.getElementById('stopt').hidden};
  document.querySelector('[data-qb="call"]').click();
  for (let i = 0; i < 40 && !__sounds.length; i++) await sleep(150);
  await sleep(300);
  out.sounded = __sounds.slice();
  out.after = stage();
  out.chip = document.getElementById('round-chip').textContent;
  return JSON.stringify(out);
})()
"""

PHONE = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  me = {id: %(ann)d, name: 'Ann', cohort: 'A'};
  shownRound = null;
  await tick();
  for (let i = 0; i < 40 && !document.querySelector('.qb-card'); i++) { await sleep(150); await tick(); }
  const out = {};
  const squares = [...document.querySelectorAll('[data-qb-sq]')];
  out.squares = squares.length;
  out.showsCodes = document.querySelectorAll('.qb-sq b').length;
  for (const i of [0, 1, 2, 3]) document.querySelector('[data-qb-sq="' + i + '"]').click();
  await sleep(300);
  out.marked = document.querySelectorAll('.qb-sq.on').length;
  document.getElementById('qb-claim').click();
  await sleep(600);
  out.early = document.getElementById('qb-said').textContent;
  // Every code keyed, from the table.
  const call = () => fetch('/api/party/qbingo/call',
                           {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
  for (let n = 0; n < 23; n++) await call();
  shownRound = null; await tick(); await sleep(200);
  for (const i of [0, 1, 2, 3]) if (!document.querySelector('[data-qb-sq="' + i + '"]').classList.contains('on'))
    document.querySelector('[data-qb-sq="' + i + '"]').click();
  await sleep(300);
  const claim = document.getElementById('qb-claim');
  out.claimThere = !!claim;
  if (claim) { claim.click(); await sleep(800); }
  await tick(); await sleep(300);
  out.end = document.getElementById('view').textContent.replace(/\s+/g, ' ');
  out.codesShown = document.querySelectorAll('.qb-sq b').length;
  return JSON.stringify(out);
})()
"""

TABLE_AFTER = r"""
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 80 && !(lastTableState && lastTableState.qbingo); i++) await sleep(150);
  await sleep(400);
  return JSON.stringify({stage: document.getElementById('stage').textContent.replace(/\s+/g, ' ')});
})()
"""


def main():
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        print("\nFAILED: this test needs chromium")
        return 1
    port = _browser._free_port()
    base = "http://127.0.0.1:%d" % port
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
         "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                urllib.request.urlopen(base + "/api/ping", timeout=1).close()
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise SystemExit("the throwaway server never answered")
        urllib.request.urlopen(urllib.request.Request(base + "/party", headers={"Cookie": "elmer_user=1"}), timeout=15)
        post(base, "/api/party/bots", {"on": False})
        ann = post(base, "/api/party/join", {"name": "Ann"})
        post(base, "/api/party/join", {"name": "Bob"})
        ann_id = (ann.get("player") or ann).get("id")
        started = post(base, "/api/party/mode", {"mode": "qbingo"})
        check("the tile's route starts bingo", (started.get("qbingo") or {}).get("players"), 2)
        table = json.loads(_browser.evaluate(base + "/party", TABLE, width=1280, height=900, settle=1.5,
                                             cookies={"elmer_user": "1"}))
        phone = json.loads(_browser.evaluate(base + "/j/1", PHONE % {"ann": ann_id}, settle=1.0))
        after = json.loads(_browser.evaluate(base + "/party", TABLE_AFTER, width=1280, height=900, settle=1.5,
                                             cookies={"elmer_user": "1"}))
    finally:
        server.terminate()

    print("\n-- the table --")
    check("the tile is lit, the tiles stand down, Stop is offered",
          (table["chosen"], table["tilesHidden"], table["stop"]), (True, True, True))
    check("before the first call it says the cards are out", "Cards are on the phones" in table["before"], True)
    check("Key the next code sends one Q signal to the speaker", (len(table["sounded"]),
          table["sounded"][0][:1] if table["sounded"] else None), (1, "Q"))
    check("  and does not write it", table["sounded"][0] in table["after"] if table["sounded"] else True, False)
    check("  the chip counts it", table["chip"], "Q-code bingo · call 1 of 23")

    print("\n-- Ann's phone --")
    check("a card of sixteen meanings, no codes on it", (phone["squares"], phone["showsCodes"]), (16, 0))
    check("the top row marks", phone["marked"], 4)
    check("Bingo before those codes are keyed is refused, and says why",
          phone["early"].startswith("not yet"), True)
    check("once every code is out, the call stands", "you won" in phone["end"], True)
    check("  and the finished card shows its codes", phone["codesShown"], 16)

    print("\n-- the table after --")
    check("the table says who won, and the winning line",
          ("Bingo! Ann" in after["stage"], "Q" in after["stage"]), (True, True))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
