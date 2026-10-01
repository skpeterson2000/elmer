#!/usr/bin/env python3
"""Two operators on the unit's frequencies, each on their own device.

    python3 tests/test_cw_air.py

The simulator is a partner who is never nervous. A person is the next step:
a friend across the room, a student and an Elmer at the club. Each is signed
in as themselves on their own phone or computer; both tune to one of the
unit's frequencies; what either keys goes out word by word, as their own
fist. What is held here:

  - tuning, and who else is there;
  - a word keyed by one is heard by the other, text and fist both - the
    element timings as keyed, not a clean re-send;
  - nobody hears their own words back;
  - a typed word still goes out as code, timed at the speed given;
  - a frequency nobody is tuned to refuses words, and an unknown one is
    named as such;
  - working each other counts as the unit being in use;
  - in the browser: the page tunes, a word keyed there reaches the other
    operator with its fist, and the other's word comes back, is played and
    is logged.
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
from elmer import activity, db, sked  # noqa: E402
from elmer.app import app  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def second_user():
    conn = db.connect()
    row = conn.execute("SELECT id FROM profile WHERE callsign = 'W1AW'").fetchone()
    if row:
        return row["id"]
    first = conn.execute("SELECT id FROM profile ORDER BY id LIMIT 1").fetchone()["id"]
    conn.execute("UPDATE profile SET callsign = 'KC9SP', name = 'Scott' WHERE id = ?", (first,))
    conn.commit()
    return db.add_user(conn, "Hiram", "W1AW")["id"]


def unit(a_id, b_id):
    print("\n-- on the air, through the routes --")
    a, b = app.test_client(), app.test_client()
    a.set_cookie("elmer_user", str(a_id))
    b.set_cookie("elmer_user", str(b_id))
    check("an unknown frequency is named as such",
          a.post("/api/cw/sked/tune", json={"freq": "3.999"}, environ_base=LOCAL).status_code, 400)
    check("a word on a frequency nobody tuned to is refused",
          a.post("/api/cw/sked/send", json={"freq": "7.040", "text": "CQ"}, environ_base=LOCAL).status_code, 409)
    a.post("/api/cw/sked/tune", json={"freq": "7.030"}, environ_base=LOCAL)
    t = b.post("/api/cw/sked/tune", json={"freq": "7.030"}, environ_base=LOCAL).get_json()
    check("tuning shows who else is there", [x["call"] for x in t["tuned"]], ["KC9SP", "W1AW"])
    fist = [["s", 400], ["m", 64], ["s", 58], ["m", 210], ["s", 61], ["m", 70]]   # K, as a hand keys it
    a.post("/api/cw/sked/send", json={"freq": "7.030", "text": "K", "elements": fist, "wpm": 18},
           environ_base=LOCAL)
    got = b.get(f"/api/cw/sked/poll?freq=7.030&after={t['seq']}", environ_base=LOCAL).get_json()
    w = got["words"][0] if got["words"] else {}
    check("the other operator hears the word, from its sender",
          (w.get("text"), w.get("call")), ("K", "KC9SP"))
    check("  with the fist as keyed, not a clean re-send", w.get("elements"), [[k, float(v)] for k, v in fist])
    mine = a.get(f"/api/cw/sked/poll?freq=7.030&after={t['seq']}", environ_base=LOCAL).get_json()
    check("nobody hears their own words back", mine["words"], [])
    b.post("/api/cw/sked/send", json={"freq": "7.030", "text": "TU", "elements": [], "wpm": 20},
           environ_base=LOCAL)
    got = a.get(f"/api/cw/sked/poll?freq=7.030&after={got['seq']}", environ_base=LOCAL).get_json()
    els = got["words"][0]["elements"] if got["words"] else []
    marks = [ms for k, ms in els if k == "m"]
    check("a typed word still goes out as code: T is a dah, U two dits and a dah at 20 wpm",
          [round(m) for m in marks], [180, 60, 60, 180])
    check("working each other counts as the unit in use", activity.busy(fresh=True), "a CW contact on the air")
    a.post("/api/cw/sked/leave", environ_base=LOCAL)
    b.post("/api/cw/sked/leave", environ_base=LOCAL)


DRIVE = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof airTune === 'function', 10000);
  showMode('contact');
  document.querySelector('[data-work="air"]').click();
  document.getElementById('cw-air-freq').value = '14.050';
  await airTune();
  const out = {tuned: air.on, freq: air.freq};
  // Key "R" by hand, through the key's own decoder: dit dah dit.
  showMode('contact');
  const el = (ms, kind) => kind === 'm' ? keyDecoder.mark(ms) : keyDecoder.space(ms);
  el(700, 's'); el(60, 'm'); el(60, 's'); el(185, 'm'); el(65, 's'); el(62, 'm'); keyDecoder.flush();
  keyDecoder.text += ' ';
  await until(() => air.log.some(e => e.who === 'you'), 5000);
  out.sent = air.log.filter(e => e.who === 'you').map(e => e.text);
  // The other operator's word arrives, is played and is logged.
  window.__ready = true;
  await until(() => air.log.some(e => e.who === 'them'), 15000);
  out.heard = air.log.filter(e => e.who === 'them').map(e => [e.call, e.text]);
  out.played = player.playingUntil > 0;
  out.who = document.getElementById('cw-air-who').textContent;
  resolve(JSON.stringify(out));
})
"""


def browser(a_id, b_id):
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
         "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"

    def as_b(path, body=None):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Content-Type": "application/json", "Cookie": f"elmer_user={b_id}"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read() or b"{}")

    import threading
    result = {}

    def other_operator():
        # Wait for the page to tune, then tune too, hear its word, and answer.
        deadline = time.time() + 40
        seq = 0
        while time.time() < deadline:
            try:
                t = as_b("/api/cw/sked/tune", {"freq": "14.050"})
                seq = 0
                if any(x["call"] == "KC9SP" for x in t["tuned"]):
                    break
            except OSError:
                pass
            time.sleep(0.5)
        while time.time() < deadline:
            got = as_b(f"/api/cw/sked/poll?freq=14.050&after={seq}")
            if got["words"]:
                result["heard"] = got["words"][0]
                break
            time.sleep(0.3)
        as_b("/api/cw/sked/send", {"freq": "14.050", "text": "FB", "elements": [], "wpm": 20})

    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(base + "/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        th = threading.Thread(target=other_operator, daemon=True)
        th.start()
        got = json.loads(_browser.evaluate(base + "/cw", DRIVE, width=1300, height=1400, settle=1.5,
                                           cookies={"elmer_user": str(a_id)}) or "{}")
        th.join(timeout=5)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    print("\n-- in the browser --")
    check("the page tunes to the frequency", (got.get("tuned"), got.get("freq")), (True, "14.050"))
    check("a word keyed there is logged as sent", got.get("sent"), ["R"])
    heard = result.get("heard") or {}
    check("  and reaches the other operator, with its fist",
          (heard.get("text"), [k for k, _ in heard.get("elements") or []]), ("R", ["s", "m", "s", "m", "s", "m"]))
    check("the other's word comes back, is played and logged",
          (got.get("heard"), got.get("played")), ([["W1AW", "FB"]], True))
    check("  and the page says who is on the frequency", "W1AW" in (got.get("who") or ""), True)


def main():
    b_id = second_user()
    conn = db.connect()
    a_id = conn.execute("SELECT id FROM profile WHERE callsign = 'KC9SP'").fetchone()["id"]
    unit(a_id, b_id)
    browser(a_id, b_id)


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
