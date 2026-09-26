#!/usr/bin/env python3
"""The golfer's swing, in a real browser: the phone's and the table screen's.

    python3 tests/test_golf_swing_page.py

The rules are test_golf_hand.py's. This is the hands: the order a person
meets them in - set up the shot, choose an answer, the meter starts, Hit
swings - and that what reaches the server is what the golfer did. The
network is stubbed inside the page, so each check reads exactly what the
page would have sent.

It also holds a fault found reading this code: the club buttons on the
phone's question share the look of the answers, and every button with that
look was wired as an answer - so a club tapped with the question open was a
wrong answer, and a foul ball nobody swung.
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
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# The shot as a phone or the table would read it off the state.
READING = {"need": 0.8, "sweet": 0.03, "spin_cap": 1.0, "reaches": True, "says": "", "club": "7-iron"}
GOLF = {"your_turn": True, "over": False, "hole": 1, "par": 4, "address_waits": True,
        "your_shape": {"shape": 0.5, "spin": 0.0}, "away_shape": {"shape": 0.5, "spin": 0.0},
        "club_names": {}, "club_labels": {}, "away": 7,
        "you": {"reading": READING, "clubs": ["driver", "7-iron"], "default_club": "7-iron",
                "lie": "fairway", "left": 160, "club_yards": {}},
        "balls": {"7": {"reading": READING, "clubs": ["driver", "7-iron"], "club": "7-iron",
                        "default_club": "7-iron", "lie": "fairway", "club_yards": {}}}}
ROUND = {"number": 3, "to": 7, "question": {"choices": ["a", "b", "c", "d"], "text": "q", "section": "T1A"}}

# A stub for the page's own api(): it records every call and accepts every
# answer. The state poll is refused, so the page's own tick stands still.
STUB = """
  window.__sent = [];
  api = async (path, body) => {
    if (path.startsWith('/api/party/state')) throw new Error('no polling in this test');
    __sent.push([path, body]);
    return {ok: true, status: 200, data: {accepted: true, ok: true}};
  };
"""
WAIT = """
  const until = (f, ms) => new Promise(res => { const t0 = Date.now();
    const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
  const sleep = ms => new Promise(res => setTimeout(res, ms));
"""

PHONE = WAIT + """
new Promise(async r => {
  await until(() => typeof paintQuestion === 'function' && window.GolfSwing, 8000);
""" + STUB + """
  me = {id: 7, name: 'Ann'};
  const gf = %(golf)s, round = %(round)s;
  const out = {};
  try { paintQuestion(round, null, gf); } catch (e) { r(JSON.stringify({error: String(e) + " " + (e.stack || "").slice(0, 300)})); return; }
  out.meter_shown = !!document.getElementById('gs-meter');
  out.idle_before = document.getElementById('gs-meter').classList.contains('idle');
  out.hit_before = document.getElementById('gs-hit').disabled;
  document.querySelector('#clubs .club').click();
  await sleep(200);
  out.club_answers = __sent.filter(x => x[0] === '/api/party/answer').length;
  document.querySelector('#choices .choice[data-i="2"]').click();
  out.idle_after = document.getElementById('gs-meter').classList.contains('idle');
  out.hit_after = document.getElementById('gs-hit').disabled;
  out.pick_answers = __sent.filter(x => x[0] === '/api/party/answer').length;
  await sleep(500);
  document.getElementById('gs-hit').click();
  await sleep(200);
  const a = __sent.find(x => x[0] === '/api/party/answer');
  out.sent = a ? {chosen: a[1].chosen, player: a[1].player, meter_ok: a[1].meter > 0 && a[1].meter <= 1} : null;
  const box = document.createElement('div');
  box.innerHTML = GolfSwing.setupHTML({shape: 0, spin: 0}, %(reading)s);
  document.body.appendChild(box);
  GolfSwing.wireSetup(box, %(reading)s, postShape);
  const s = box.querySelector('#gs-shape');
  s.value = '-60'; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change'));
  await sleep(200);
  const sh = __sent.find(x => x[0] === '/api/party/shape');
  out.shape = sh ? sh[1] : null;
  out.said = box.querySelector('#gs-shape-said').textContent;
  r(JSON.stringify(out));
})
"""

PUTT = WAIT + """
new Promise(async r => {
  await until(() => typeof paintQuestion === 'function' && window.GolfSwing, 8000);
""" + STUB + """
  me = {id: 7, name: 'Ann'};
  const gf = %(golf)s, round = %(round)s;
  const out = {};
  try { paintQuestion(round, null, gf); } catch (e) { r(JSON.stringify({error: String(e)})); return; }
  out.meter_shown = !!document.getElementById('gs-meter');
  out.says_putt = (document.getElementById('swing') || {}).textContent.includes('Your putt');
  const notch = document.querySelector('#gs-meter .gs-notch');
  out.notch = notch ? notch.style.left : null;
  document.querySelector('#choices .choice[data-i="0"]').click();
  await sleep(300);
  document.getElementById('gs-hit').click();
  await sleep(200);
  const a = __sent.find(x => x[0] === '/api/party/answer');
  out.sent = a ? {chosen: a[1].chosen, player: a[1].player, meter_ok: a[1].meter > 0 && a[1].meter <= 1} : null;
  r(JSON.stringify(out));
})
"""

# The phone's sound. A phone plays nothing the page starts on its own, so
# every clip goes through one Web Audio engine that the first tap unlocks.
# Here the unlock is called directly - a test cannot make a real finger -
# and what is checked is what comes after: that the engine runs, and that a
# clip is fetched, decoded and played through it rather than as a fresh
# <audio> element a phone would refuse.
SOUND = WAIT + """
new Promise(async r => {
  await until(() => window.Voice && window.Sfx, 8000);
  const out = {before: Voice.unlocked};
  Voice.unlock();
  await until(() => Voice.unlocked, 3000);
  out.after = Voice.unlocked;
  let made = 0;
  const Real = window.Audio;
  window.Audio = function (...a) { made += 1; return new Real(...a); };
  Sfx.setHave(['whoosh']);
  Sfx.play('whoosh');
  await until(() => performance.getEntriesByType('resource').some(e => e.name.includes('/golf/sound/whoosh.mp3')), 3000);
  await sleep(300);
  out.fetched = performance.getEntriesByType('resource').some(e => e.name.includes('/golf/sound/whoosh.mp3'));
  out.elements = made;
  r(JSON.stringify(out));
})
"""

TABLE = WAIT + """
new Promise(async r => {
  await until(() => typeof seatColumnHTML === 'function' && window.GolfSwing, 8000);
""" + STUB + """
  const gf = %(golf)s, round = %(round)s;
  lastTableState = {round, golf: gf};
  const out = {};
  const box = document.createElement('div');
  box.innerHTML = seatColumnHTML({id: 7, name: 'Ann'}, round, null, gf);
  document.body.appendChild(box);
  out.swings = !!box.querySelector('[data-swings]');
  box.querySelector('[data-seat-answer="7"][data-choice="1"]').click();
  await sleep(100);
  out.pick_answers = __sent.filter(x => x[0] === '/api/party/answer').length;
  out.running = !document.getElementById('seat7-meter').classList.contains('idle');
  await sleep(400);
  box.querySelector('[data-seat-hit="7"]').click();
  await sleep(200);
  const a = __sent.find(x => x[0] === '/api/party/answer');
  out.sent = a ? {chosen: a[1].chosen, player: a[1].player, meter_ok: a[1].meter > 0 && a[1].meter <= 1} : null;
  r(JSON.stringify(out));
})
"""


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
try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        raise SystemExit("the throwaway server never answered")
    fill = {"golf": json.dumps(GOLF), "round": json.dumps(ROUND), "reading": json.dumps(READING)}

    # The phone's page is only served while a table is running, and the
    # table screen is what opens one - as on a real evening.
    urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/party",
                                                  headers={"Cookie": "elmer_user=1"}), timeout=10)

    print("\non the phone")
    got = json.loads(_browser.evaluate(f"http://127.0.0.1:{PORT}/j/1", PHONE % fill, settle=0.5,
                                       cookies={"elmer_user": "1"}) or "{}")
    if got.get("error"): print("  page error:", got["error"])
    check("the meter is on the question, waiting", (got.get("meter_shown"), got.get("idle_before"),
                                                     got.get("hit_before")), (True, True, True))
    check("a club tapped with the question open is not an answer", got.get("club_answers"), 0)
    check("choosing an answer starts the meter and sends nothing",
          (got.get("idle_after"), got.get("hit_after"), got.get("pick_answers")), (False, False, 0))
    check("Hit sends the answer chosen, with the swing", got.get("sent"),
          {"chosen": 2, "player": 7, "meter_ok": True})
    check("a shape set up is posted on release", got.get("shape"), {"player": 7, "shape": -0.6})
    check("  and said in words while it moves", got.get("said"), "draw")

    print("\non the phone, on the green")
    putt = {"need": 0.5, "sweet": 0.03, "range": 20, "feet": 10, "putt": True}
    green = json.loads(json.dumps(GOLF))
    green["you"].update({"reading": None, "putt": putt, "lie": "green", "clubs": ["putter"], "default_club": "putter"})
    got = json.loads(_browser.evaluate(f"http://127.0.0.1:{PORT}/j/1", PUTT % {**fill, "golf": json.dumps(green)},
                                       settle=0.5, cookies={"elmer_user": "1"}) or "{}")
    if got.get("error"): print("  page error:", got["error"])
    check("a putt has its own meter, and says it is a putt", (got.get("meter_shown"), got.get("says_putt")), (True, True))
    check("  the notch at the pace to the mark", got.get("notch"), "50%")
    check("  and the putt is struck with it", got.get("sent"), {"chosen": 0, "player": 7, "meter_ok": True})

    print("\nthe phone's sound")
    # A headless browser holds the same rule a phone does - no sound until a
    # real tap - and a script cannot make a real tap, so this one is started
    # with that rule off. What it proves is what happens after the unlock.
    got = json.loads(_browser.evaluate(f"http://127.0.0.1:{PORT}/j/1", SOUND % fill, settle=0.5,
                                       cookies={"elmer_user": "1"},
                                       flags=("--autoplay-policy=no-user-gesture-required",)) or "{}")
    check("the first tap unlocks the page's one audio engine", got.get("after"), True)
    check("  and a clip is fetched and played through it", got.get("fetched"), True)
    check("  not as a fresh audio element a phone would refuse", got.get("elements"), 0)

    print("\nat the table screen")
    got = json.loads(_browser.evaluate(f"http://127.0.0.1:{PORT}/party", TABLE % fill, settle=0.5,
                                       cookies={"elmer_user": "1"}) or "{}")
    check("the seated golfer's column swings", got.get("swings"), True)
    check("choosing starts the meter and sends nothing", (got.get("running"), got.get("pick_answers")), (True, 0))
    check("Hit sends the answer chosen, with the swing", got.get("sent"),
          {"chosen": 1, "player": 7, "meter_ok": True})
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server.kill()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
