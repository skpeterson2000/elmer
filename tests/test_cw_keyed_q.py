#!/usr/bin/env python3
"""The CW page answers Q-codes keyed by the operator.

    python3 tests/test_cw_keyed_q.py

Every button on the CW page has always keyed its Q-code at the learner;
now the learner can key it back. QRV on the space bar starts what the
pane's QRV button starts, QRT stops, and so on. What is held here, with
real key events on the space bar at a learner's speed:

  - QRV keyed on Copy practice starts a send, and QRT keyed stops it;
  - a code with no button on the pane is answered with the codes that work;
  - on Your sending, what is keyed is practice, and presses nothing;
  - while a drill is waiting for a character as its answer, it stands aside;
  - a burst is decoded on its own timing - a slow, uneven fist and a fast
    one both read right.
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


JS = r"""
(async () => {
  const nap = ms => new Promise(r => setTimeout(r, ms));
  const MORSE = {Q: '--.-', R: '.-.', V: '...-', T: '-', S: '...', L: '.-..', M: '--', '?': '..--..'};
  const press = (type) => document.dispatchEvent(new KeyboardEvent(type, {code: 'Space', key: ' ', bubbles: true}));
  // A learner's fist at about 12 wpm: a 100 ms dit, a little uneven.
  const key = async (word, dit = 100) => {
    let n = 0;
    for (const ch of word) {
      for (const el of MORSE[ch]) {
        const wob = 1 + ((n++ % 3) - 1) * 0.12;
        press('keydown'); await nap((el === '-' ? dit * 3 : dit) * wob); press('keyup'); await nap(dit * wob);
      }
      await nap(dit * 2.4);
    }
    await nap(1900);                               // quiet: the burst is over
  };
  const mode = m => document.querySelector('#cw-modes [data-mode="' + m + '"]').click();
  const heard = () => document.getElementById('cw-qhear-card').textContent.replace(/\s+/g, ' ').trim();
  const out = {};
  setKeyerMode('straight', false);

  mode('copy'); await nap(300);
  const status = () => document.getElementById('cw-copy-status').textContent;
  await key('QRV');
  out.qrv = {status: status(), sending: sending, card: heard()};
  await key('QRT');
  await nap(300);
  out.qrt = {sending: sending, stopShown: !document.getElementById('cw-stop').hidden, card: heard()};

  mode('today'); await nap(300);
  await key('QSL');
  out.nothere = heard();

  mode('key'); await nap(300);
  const before = sending;
  await key('QRV', 1200 / settings.wpm);           // this pane grades against the speed slider
  out.practice = {decoded: keyDecoder.text.replace(/\s+/g, ''), pressed: sending !== before};

  mode('copy'); await nap(300);
  flashKey = () => {};                              // a drill waiting for its answer
  out.drill = qhearHere();
  flashKey = null;
  out.free = qhearHere();

  // The paddles reach it through the keyer: a dah on the dah key lands in the listener.
  setKeyerMode('A', false);
  qhear.events = [];
  const pad = type => document.dispatchEvent(new KeyboardEvent(type, {code: settings.keyDah, bubbles: true}));
  pad('keydown'); await nap(250); pad('keyup'); await nap(400);
  out.paddle = {routed: keyer.decoder === qhearRecorder, marks: qhear.events.filter(e => e[0] === 'm').length};
  clearTimeout(qhear.timer); qhear.events = [];
  setKeyerMode('straight', false);

  // The decoder alone: a slow uneven fist, and a fast one.
  const burst = (word, dit, wobble) => {
    const ev = []; let n = 0;
    for (const ch of word) {
      const code = MORSE[ch];
      [...code].forEach((el, i) => {
        const w = 1 + ((n++ % 3) - 1) * wobble;
        ev.push(['m', (el === '-' ? 3 : 1) * dit * w]);
        if (i < code.length - 1) ev.push(['s', dit * w]);
      });
      ev.push(['s', dit * 3.2]);
    }
    return qhearDecode(ev.slice(0, -1), 60).text;
  };
  out.slow = burst('QRV', 160, 0.2);
  out.fast = burst('QSM?', 40, 0.05);
  return JSON.stringify(out);
})()
"""


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
        got = json.loads(_browser.evaluate("http://127.0.0.1:%d/cw" % port, JS, settle=2.0))
    finally:
        server.terminate()

    print("\n-- keyed on Copy practice --")
    started = "start now" in got["qrv"]["status"] or "sending" in got["qrv"]["status"]
    check("QRV starts the send, without keying QRV back", (got["qrv"]["sending"], started), (True, True))
    check("  and says what it heard and what it pressed", got["qrv"]["card"].startswith("QRV ready, go ahead"), True)
    check("QRT stops it", (got["qrt"]["sending"], got["qrt"]["stopShown"]), (False, False))
    check("  and says so", got["qrt"]["card"].startswith("QRT stop sending"), True)

    print("\n-- a code with no button here --")
    check("is answered with the ones that work", ("no button for that here" in got["nothere"], "QRV" in got["nothere"]),
          (True, True))

    print("\n-- on Your sending it is practice --")
    check("decoded as practice, pressing nothing", (got["practice"]["decoded"], got["practice"]["pressed"]),
          ("QRV", False))

    print("\n-- it stands aside for a drill's answer --")
    check("not while a drill waits for a character", got["drill"], False)
    check("  and back once it has it", got["free"], True)

    print("\n-- the paddles too --")
    check("a paddle key on Copy practice keys into the listener",
          (got["paddle"]["routed"], got["paddle"]["marks"] >= 1), (True, True))

    print("\n-- a fist on its own timing --")
    check("a slow, uneven fist reads right", got["slow"], "QRV")
    check("a fast one too", got["fast"], "QSM?")

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
