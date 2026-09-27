#!/usr/bin/env python3
"""The Lab turns an antenna on its compass, all the way round.

    python3 tests/test_lab_turn.py

Which way an antenna is laid was two sliders, 0 to 179. The one beside the
figure stayed at 179 even for a Yagi or a terminated wire - antennas that
fire one way and need the whole compass - so half of it could not be reached
from where the pattern is drawn, and a slider has ends where a compass has
none. The compass is the control now. What is held here:

  - both boxes take a degree and agree with each other, past 179 too;
  - they wrap: 360 is 0, one below 0 is 359, and Shift and an arrow turn
    fifteen degrees at a time;
  - dragging round the compass turns the antenna exactly as far as the hand,
    and the pattern is drawn again when it is let go;
  - tapping a place on the rim aims a one-way antenna straight at it, and
    lays a plain wire across the line to it, so it fires broadside that way;
  - a plain wire keeps to half the circle - 30 and 210 are the same wire -
    and a Yagi gets all of it;
  - the bearing is kept with the antenna it belongs to, for the band plan's
    reach map to open on.

This needs a browser: the whole of it is what a pointer does to a drawing.
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


# The sky and the places around the station, canned: the page asks for a
# pattern as it loads, and a test asks nobody's server anything.
SNAP = {"sfi": 120.0, "k_index": 2.0, "hmf2": 300.0, "muf": 20.0, "fof2": 6.0, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}
SERVE = (
    "import sys; sys.path.insert(0, %r)\n"
    "from elmer import app as appmod, places, propagation\n"
    "propagation.snapshot = lambda *a, **k: dict(%r)\n"
    "places.refresh_in_background = lambda *a, **k: None\n"
    "appmod._prefetch_regional = lambda place: None\n"
    "appmod.app.run(host='127.0.0.1', port=%%d, threaded=True, use_reloader=False)" % (str(ROOT), SNAP))

DRIVE = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof antennaFields === 'function' && typeof wirePlanTurn === 'function', 12000);
  const tab = [...document.querySelectorAll('button, a')].find(b => b.textContent.trim() === 'Antennas');
  if (tab) tab.click();
  const sel = document.getElementById('an-type');
  const a = document.getElementById('an-head'), b = document.getElementById('an-head-2');
  const said = () => (document.getElementById('an-head-2-v') || {}).textContent || '';
  const plan = () => document.querySelector('#an-pattern svg[data-plan]');
  const out = {};
  const choose = async kind => {
    const old = plan();
    sel.value = kind; sel.dispatchEvent(new Event('input'));
    // the compass drawn for this antenna, not a late answer about the last one
    await until(() => plan() && plan() !== old && plan().dataset.type === kind, 10000);
  };
  const type = (el, v) => { el.value = v; el.dispatchEvent(new Event('input')); return a.value; };
  const redrawn = async old => { await until(() => plan() && plan() !== old, 10000); await nap(); };

  await choose('tefv');
  out.boxes = [a.type, b.type];
  out.past179 = [type(b, '350'), b.value];
  out.wrapUp = type(a, '360');
  out.wrapDown = type(a, '-1');
  type(a, '350');
  a.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowUp', shiftKey: true, bubbles: true}));
  out.shift = a.value;

  // a drag, from 45 degrees round to 100, at the compass's own scale
  let svg = plan();
  const cx = +svg.dataset.cx, cy = +svg.dataset.cy, R = +svg.dataset.r;
  const at = deg => {
    const pt = svg.createSVGPoint(), r = deg * Math.PI / 180;
    pt.x = cx + 0.6 * R * Math.sin(r); pt.y = cy - 0.6 * R * Math.cos(r);
    const s = pt.matrixTransform(svg.getScreenCTM());
    return {clientX: s.x, clientY: s.y, pointerId: 7, bubbles: true};
  };
  const hit = deg => { const p = at(deg); return document.elementFromPoint(p.clientX, p.clientY) || svg; };
  hit(45).dispatchEvent(new PointerEvent('pointerdown', at(45)));
  out.duringDrag = a.value;
  svg.dispatchEvent(new PointerEvent('pointermove', at(100)));
  out.movedTo = a.value;
  out.redrawnWhileDragging = plan() !== svg;
  svg.dispatchEvent(new PointerEvent('pointerup', at(100)));
  await redrawn(svg);
  out.letGo = a.value;
  out.words = said();
  let kept = recall('lab.antenna', {}) || {};
  out.kept = [kept.heading_deg, kept.heading_kind];

  // a place on the rim
  svg = plan();
  let place = svg.querySelector('[data-bearing]');
  out.hasPlaces = !!place;
  if (place) {
    const want = Math.round(parseFloat(place.dataset.bearing)) % 360;
    place.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, pointerId: 8}));
    await redrawn(svg);
    out.aimed = [+a.value, want];
  }

  // a plain wire keeps to half the circle, and is laid across the line to a place
  await choose('dipole');
  out.wireWrap = type(a, '210');
  svg = plan();
  place = svg.querySelector('[data-bearing]');
  if (place) {
    const want = (Math.round(parseFloat(place.dataset.bearing)) + 90) % 180;
    place.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, pointerId: 9}));
    await redrawn(svg);
    out.wireAimed = [+a.value, want];
  }

  // and a Yagi has the whole compass
  await choose('yagi');
  out.yagi = type(a, '270');
  out.yagiWords = said();
  resolve(JSON.stringify(out));
})
"""


def main():
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    server = subprocess.Popen([sys.executable, "-c", SERVE % port], env=dict(os.environ),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        # A place to be, so the compass has places on its rim.
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", method="POST",
                                     data=json.dumps({"location": {"lat": 46.60, "lon": -94.31,
                                                                   "short": "Pequot Lakes", "grid": "EN36"}}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab#ant", DRIVE, width=1300, height=1100,
                                           settle=1.0, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()

    print("\n-- the boxes take a degree, and go on round --")
    check("both are degree boxes, not sliders", got.get("boxes"), ["number", "number"])
    check("the one by the figure goes past 179 for a terminated wire, and the other follows",
          got.get("past179"), ["350", "350"])
    check("360 is 0", got.get("wrapUp"), "0")
    check("one below 0 is 359", got.get("wrapDown"), "359")
    check("Shift and an arrow turn fifteen degrees, round past north", got.get("shift"), "5")

    print("\n-- the compass turns it --")
    check("pressing on the compass points it where the pointer is", got.get("duringDrag"), "45")
    check("  and it follows the hand", got.get("movedTo"), "100")
    check("  the pattern is not worked out again at every step of the drag", got.get("redrawnWhileDragging"), False)
    check("  let go, and it stays where it was let go", got.get("letGo"), "100")
    check("  and says which way it fires", "fires 100" in (got.get("words") or ""), True)
    check("  kept with the antenna it belongs to", got.get("kept"), [100, "tefv"])
    check("the compass has places on its rim", got.get("hasPlaces"), True)
    aimed = got.get("aimed") or [None, None]
    check("tapping one aims the terminated wire straight at it", aimed[0], aimed[1])

    print("\n-- a wire has no front; a Yagi has --")
    check("a plain wire laid at 210 is the wire laid at 30", got.get("wireWrap"), "30")
    wire = got.get("wireAimed") or [None, None]
    check("  and aimed at a place it is laid across the line, to fire broadside that way", wire[0], wire[1])
    check("a Yagi keeps the whole compass", got.get("yagi"), "270")
    check("  and says where the boom points", "boom points 270" in (got.get("yagiWords") or ""), True)


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
