#!/usr/bin/env python3
"""The inverted V in the Lab: one leg length, and a drawing to scale.

    python3 tests/test_lab_vee.py

Two faults, found by looking at the picture. The drawing hung every V from
the same point with a fixed drop, so a steeper droop drew shorter legs - the
same wire half as long at 60 degrees as at 10 - and the ends sat by the grass
whatever the apex was. And the leg itself was two lengths: the table cut a V
5% short of a flat dipole, 445/f, while the ends-and-droop geometry and the
server's heights and footprint worked from a flat dipole's 468/f. What is
held here, in a real browser:

  - the drawn leg is the table's leg at every droop, measured against the
    drawn apex height;
  - the drawn ends are the ends box's height;
  - drooped until the ends meet the ground, the rest of each leg lies on it
    and the drawing says so;
  - the ends box, the table and the server all use the same leg;
  - the derivation shows the 5% and lands on the table's figure.
"""
import json
import math
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
GROUND_Y = 210          # the drawing's ground line, lab.js drawAntenna


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


DRIVE = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof antennaFields === 'function' && typeof calcAnt === 'function', 10000);
  const set = (id, v, ev) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event(ev || 'input')); };
  set('an-type', 'invertedv', 'change'); await nap(400);
  const shot = async (mhz, apex, droop) => {
    set('an-f', mhz); set('an-h', apex); set('an-angle', droop); await nap(300);
    calcAnt(); await nap(300);
    const pl = document.querySelector('#an-svg polyline[data-vee]');
    const txt = [...document.querySelectorAll('#an-svg text')].map(t => t.textContent);
    return {points: pl ? pl.getAttribute('points') : '', leg: (window.LAB_ANTENNA || {}).legFt,
            ends: document.getElementById('an-ends').value, words: txt};
  };
  const out = {};
  out.a10 = await shot('7.200', '40', '10');
  out.a35 = await shot('7.200', '40', '35');
  out.a60 = await shot('7.200', '40', '60');
  out.low = await shot('7.200', '15', '60');
  const d = document.querySelector('#an-out details.derivation');
  out.derivation = d ? d.textContent : '';
  resolve(JSON.stringify(out));
})
"""


def pts(s):
    return [tuple(float(v) for v in p.split(",")) for p in s.split()]


def measure(shot, apex_ft):
    """The drawn right leg, in feet, and the drawn end height, from the apex's scale."""
    p = pts(shot["points"])
    apex = min(p, key=lambda q: q[1])
    right = [q for q in p if q[0] > apex[0]]
    sc = (GROUND_Y - apex[1]) / apex_ft
    length, prev = 0.0, apex
    for q in right:
        length += math.hypot(q[0] - prev[0], q[1] - prev[1])
        prev = q
    return length / sc, (GROUND_Y - right[0][1]) / sc, right


def main():
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
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab#ant", DRIVE, width=1300, height=1000,
                                           settle=1.5, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()

    print("\n-- one leg --")
    leg = (got.get("a35") or {}).get("leg") or 0
    check("the table's leg on 40 m is 445/f halved, for the conductor on screen",
          abs(leg - 445 / 7.2 / 2) < 1.5, True)
    from elmer import antenna_advice as aa
    check("  and the server's is the same cut", (aa.V_CUT, round(aa.V_LEG_WL * 983.571 / 7.2, 2)),
          (445.0, round(445 / 7.2 / 2, 2)))

    print("\n-- drawn to scale --")
    for key, droop in (("a10", 10), ("a35", 35), ("a60", 60)):
        shot = got.get(key) or {}
        if not shot.get("points"):
            check(f"a V is drawn at {droop} degrees", False, True)
            continue
        drawn_leg, drawn_end, _ = measure(shot, 40)
        check(f"at {droop} degrees the drawn leg is the table's", abs(drawn_leg - shot["leg"]) < 0.5, True)
        check(f"  and the drawn ends are the ends box's {shot['ends']} ft",
              abs(drawn_end - float(shot["ends"])) < 0.6, True)
        want = 40 - shot["leg"] * math.sin(math.radians(droop))
        check("  which is the apex less the leg's drop", abs(float(shot["ends"]) - want) < 0.15, True)

    print("\n-- drooped to the ground --")
    low = got.get("low") or {}
    if low.get("points"):
        drawn_leg, _, right = measure(low, 15)
        check("a 15 ft apex at 60 degrees: the leg reaches the ground and lies along it",
              (abs(right[-1][1] - GROUND_Y) < 0.01, len(right)), (True, 2))
        check("  the whole leg is still drawn", abs(drawn_leg - low["leg"]) < 0.5, True)
        check("  and the drawing says so", "ends on the ground" in (low.get("words") or []), True)

    print("\n-- the working --")
    der = got.get("derivation") or ""
    check("the derivation shows the V's 445 and why", ("445" in der, "5% shorter" in der), (True, True))
    check("  and no longer says the droop leaves the length alone", "not the length" in der, False)


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
