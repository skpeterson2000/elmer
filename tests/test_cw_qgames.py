#!/usr/bin/env python3
"""The Q-code games on the CW page: Hear it, key it, and the matching cards.

    python3 tests/test_cw_qgames.py

The record: a missed code is drawn more and soon, a code answered right
several times running steps back, and the answers count. The routes: a
round of codes with four meanings each, and an answer counted. Then the
page: a whole round of Hear it, key it played in chromium - the hear-it
prompts answered by pressing a meaning, the key-it prompts keyed on the
space bar with real key events - and a deal of the matching cards played
to the end.
"""
import json
import os
import random
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
from elmer import cw  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def record_checks():
    print("-- the record --")
    now = 1_000_000.0
    record = {}
    for _ in range(4):
        cw.qgame_take(record, "QRS", True, now)
    cw.qgame_take(record, "QTH", False, now)
    check("answers are counted", (record["QRS"]["seen"], record["QRS"]["right"], record["QRS"]["run"]), (4, 4, 4))
    check("  a miss resets the run and is remembered", (record["QTH"]["run"], record["QTH"]["missed_at"]), (0, now))
    check("a code ELMER does not know is not counted", "QXX" in cw.qgame_take(record, "QXX", True, now), False)
    w = {c: cw.qgame_weight(record.get(c), now + 60) for c in ("QRS", "QTH", "QRZ")}
    check("just missed outweighs never met, which outweighs solid", w["QTH"] > w["QRZ"] > w["QRS"], True)
    check("  and the miss fades after ten minutes", cw.qgame_weight(record["QTH"], now + 3600) < w["QTH"], True)
    rng = random.Random(7)
    draws = [cw.qgame_draw(record, rng, 1, now + 60)[0] for _ in range(2000)]
    check("drawn over and over, the missed code comes up far more than the solid one",
          draws.count("QTH") > 5 * draws.count("QRS"), True)
    rnd = cw.qgame_draw(record, random.Random(1), 10, now)
    check("a round has no code twice", len(set(rnd)), 10)
    ch = cw.qgame_choices("QRS", random.Random(3))
    check("four meanings, the right one among them, none twice",
          (len(ch), "QRS" in [c["code"] for c in ch], len({c["code"] for c in ch})), (4, True, 4))
    for heard, want in (("QRS", True), ("QRS?", True), ("Q R S", True), ("·QRS", True), ("QRQ", False), ("QR", False)):
        check(f"  keyed {heard!r} for QRS", cw.qgame_keyed_matches("QRS", heard), want)


def route_checks():
    print("\n-- the routes --")
    from elmer.app import app
    client = app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    d = client.get("/api/cw/qgame?count=10", environ_base=local).get_json()
    check("a round of ten, each with four meanings",
          (len(d["round"]), all(len(r["choices"]) == 4 for r in d["round"])), (10, True))
    r = client.post("/api/cw/qgame", json={"code": "QSY", "right": False}, environ_base=local).get_json()
    check("an answer is counted on the record", (r["ok"], r["stat"]["seen"], r["stat"]["run"]), (True, 1, 0))
    check("  and an unknown code refused",
          client.post("/api/cw/qgame", json={"code": "ZZZ", "right": True}, environ_base=local).status_code, 400)


PAGE = r"""
(async () => {
  const nap = ms => new Promise(r => setTimeout(r, ms));
  const MORSE = CODE;
  const press = type => document.dispatchEvent(new KeyboardEvent(type, {code: 'Space', key: ' ', bubbles: true}));
  const key = async (word, dit = 90) => {
    for (const ch of word) {
      for (const el of MORSE[ch]) { press('keydown'); await nap(el === '-' ? dit * 3 : dit); press('keyup'); await nap(dit); }
      await nap(dit * 2.5);
    }
    await nap(1600);
  };
  setKeyerMode('straight', false);
  document.querySelector('#cw-modes [data-mode="qgames"]').click(); await nap(300);
  const out = {steps: [], keyedRight: 0, typed: null};
  document.getElementById('qg-start').click();
  for (let n = 0; n < 60 && !qg.round.length; n++) await nap(100);
  for (let i = 0; i < qg.round.length; i++) {
    await nap(300);
    const item = qg.round[i], hear = i % 2 === 0;
    out.steps.push(document.getElementById('qg-step').textContent);
    if (hear) {
      // One wrong on purpose, the rest right.
      const pickRight = i !== 2;
      const btns = [...document.querySelectorAll('#qg-choices [data-qg-code]')];
      const b = btns.find(x => (x.dataset.qgCode === item.code) === pickRight);
      b.click();
    } else if (i === 9) {
      const t = document.getElementById('qg-typed'); t.value = item.code.toLowerCase();
      document.getElementById('qg-typed-go').click();
      out.typed = qg.answered;
    } else {
      out.claimWaiting = !!qhearClaim;
      await key(item.code);
      if (document.getElementById('qg-feedback').textContent.startsWith('Right')) out.keyedRight++;
    }
    await nap(150);
    if (i === 2) out.wrongShown = document.querySelector('#qg-choices .wrong') !== null &&
                                  document.querySelector('#qg-choices .right') !== null;
    if (i < qg.round.length - 1) {
      // Next by keying QRV, once - the rest by pressing it.
      // (a click on Next keys QRV aloud first, as every Q button does, so wait for the prompt)
      if (i === 0) { await key('QRV'); out.nextByKey = qg.i === 1; } else document.getElementById('qg-next').click();
      for (let n = 0; n < 60 && qg.i !== i + 1; n++) await nap(100);
    } else {
      document.getElementById('qg-next').click();
      for (let n = 0; n < 60 && document.getElementById('qg-summary').hidden; n++) await nap(100);
    }
  }
  await nap(300);
  out.summary = document.getElementById('qg-summary').textContent;
  out.again = document.getElementById('qg-start').textContent;

  // The matching cards.
  document.getElementById('qg-pick-match').click();
  for (let n = 0; n < 40 && !qm.cards.length; n++) await nap(100);
  out.dealt = qm.cards.length;
  // A wrong pair first, then every pair.
  const iCode = qm.cards.findIndex(c => c.kind === 'code');
  const iOther = qm.cards.findIndex(c => c.kind === 'meaning' && c.code !== qm.cards[iCode].code);
  qmTurn(iCode); qmTurn(iOther); out.wrongBusy = qm.busy;
  await nap(1300);
  out.turnedBack = document.querySelectorAll('.qg-card.down').length;
  const codes = [...new Set(qm.cards.map(c => c.code))];
  for (const c of codes) {
    qmTurn(qm.cards.findIndex(x => x.code === c && x.kind === 'code'));
    qmTurn(qm.cards.findIndex(x => x.code === c && x.kind === 'meaning'));
    await nap(100);
  }
  out.matched = qm.matched; out.turns = qm.turns;
  out.matchStatus = document.getElementById('qg-match-status').textContent;
  return JSON.stringify(out);
})()
"""


def page_checks():
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
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
        raw = _browser.evaluate("http://127.0.0.1:%d/cw" % port, PAGE, settle=2.0)
        if not str(raw).startswith("{"):
            raise SystemExit("page: %s" % raw)
        got = json.loads(raw)
    finally:
        server.terminate()

    print("\n-- Hear it, key it, played through --")
    check("ten prompts, hear and key turn about",
          (len(got["steps"]), got["steps"][0].endswith("hear it"), got["steps"][1].endswith("key it")), (10, True, True))
    check("a key-it prompt waits for a keyed answer", got.get("claimWaiting"), True)
    check("the codes keyed on the space bar were taken as right", got["keyedRight"], 4)
    check("one typed in lower case was taken too", got["typed"], True)
    check("a wrong pick shows the right one beside it", got.get("wrongShown"), True)
    check("keying QRV after an answer goes to the next", got.get("nextByKey"), True)
    check("the round ends 9 of 10, the miss named to come round again",
          (got["summary"].startswith("9 of 10"), "come round again" in got["summary"]), (True, True))
    check("  and Play again is QRV", got["again"].startswith("Play again"), True)

    print("\n-- the matching cards --")
    check("six pairs dealt", got["dealt"], 12)
    check("a wrong pair turns back", (got["wrongBusy"], got["turnedBack"]), (True, 12))
    check("every pair matched, and the turns counted", (got["matched"], got["turns"]), (6, 7))
    check("  and it says so", got["matchStatus"].startswith("All six pairs in 7 turns"), True)


def main():
    record_checks()
    route_checks()
    page_checks()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
