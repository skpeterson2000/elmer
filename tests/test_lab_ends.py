#!/usr/bin/env python3
"""Where a wire's ends are tied off is the operator's to say.

    python3 tests/test_lab_ends.py

The Lab marked the high point - an apex, a support, a mast top - and took
the ends from an angle: a V's droop, a sloper's slope, and for the
terminated wires the handbook's 6 ft posts, always. Somebody going out with
a wire knows the fence post and the tree, not the angle. What is held here:

  - a box for the ends, shown for the antennas whose ends hang somewhere,
    and one value with the angle slider, either way round: typed ends set
    the droop or the slope, a moved slider sets the ends;
  - typed ends hold: raise the apex and the droop follows, as it does with
    the rope already tied to the fence;
  - a terminated wire's ends replace the 6 ft posts in its table, its
    drawing, its pattern, the reach map and the fit - blank is the posts;
  - a sloping dipole's effective height is its middle, where its current
    is, and not a quarter of the way down.
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
from elmer import antenna_advice as A, patterns as P  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def the_backend():
    print("\n-- a terminated wire's ends, carried to the pattern and the fit --")
    posts = P.laid("tefv", 250.0, 18.0, 1.843)
    fence = P.laid("tefv", 250.0, 18.0, 1.843, end_ft=12.0)
    check("the handbook's 6 ft posts unless said otherwise", (posts.end_ft, fence.end_ft), (6.0, 12.0))
    check("the pattern is worked out from the ends given",
          P._travelling_setup(posts)[0] != P._travelling_setup(fence)[0], True)
    check("  and a pattern for one end height is never handed out for another",
          P._travelling_table(posts, 18.0 / (983.571 / 1.843)) is not P._travelling_table(fence, 18.0 / (983.571 / 1.843)),
          True)
    run =A.footprint_ft("tefv", 1.843, height_ft=18, length_ft=250, end_ft=12)
    check("ends at 12 ft from an 18 ft mast: legs rise 6 ft, and cover 2 x sqrt(125^2 - 6^2)",
          run, round(2 * math.sqrt(125 ** 2 - 6 ** 2)))
    check("  and blank ends are the posts, as before",
          A.footprint_ft("tefv", 1.843, height_ft=18, length_ft=250), 249)
    from elmer.app import app
    c = app.test_client()
    a = c.get("/api/pattern?type=tefv&mhz=1.843&height=18&length=250").get_json()
    b = c.get("/api/pattern?type=tefv&mhz=1.843&height=18&length=250&ends=15").get_json()
    check("the pattern route takes the ends", (a.get("main_lobe_deg") is not None,
                                               a.get("azimuth_lobe") != b.get("azimuth_lobe")
                                               or a.get("main_lobe_deg") != b.get("main_lobe_deg")), (True, True))


DRIVE = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof antennaFields === 'function' && document.getElementById('an-ends'), 12000);
  const tab = [...document.querySelectorAll('button, a')].find(b => b.textContent.trim() === 'Antennas');
  if (tab) tab.click();
  const set = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('input')); };
  const val = id => document.getElementById(id).value;
  const shown = cls => { const el = document.querySelector(cls); return !!el && el.style.display !== 'none'; };
  const out = {};
  set('an-type', 'invertedv'); await nap(500);
  set('an-f', '7.15'); set('an-h', '35'); await nap(300);
  out.vShown = shown('.an-when-ends'); out.vLabel = document.getElementById('an-ends-label').textContent;
  set('an-ends', '20'); await nap(300);
  out.vDroop = val('an-angle'); out.vMirror = val('an-angle-2');
  set('an-h', '40'); await nap(300);
  out.vDroopAfterRaise = val('an-angle'); out.vEndsHeld = val('an-ends');
  set('an-angle', '20'); await nap(300);
  out.vEndsFromSlider = val('an-ends');
  set('an-type', 'dipole'); await nap(500);
  set('an-f', '7.15'); set('an-h', '40'); await nap(300);
  out.dLabel = document.getElementById('an-ends-label').textContent;
  out.dFlatEnds = val('an-ends');
  set('an-ends', '10'); await nap(300);
  out.dSlope = val('an-angle');
  set('an-type', 'quarter'); await nap(400);
  out.vertShown = shown('.an-when-ends');
  set('an-type', 'tefv'); await nap(500);
  set('an-f', '1.843'); set('an-h', '18'); set('an-len', '250'); await nap(300);
  out.twBlank = val('an-ends');
  set('an-ends', '12'); await nap(700);
  const rows = [...document.querySelectorAll('#an-out tr')].map(r => r.innerText.replace(/\\s+/g, ' '));
  out.twRows = rows.filter(r => /tied off|Ground covered/.test(r));
  const wire = document.querySelector('#an-svg polyline');
  if (wire) {
    const pts = wire.getAttribute('points').trim().split(/\\s+/).map(p => p.split(',').map(Number));
    out.twLegSlope = (pts[0][1] - pts[1][1]) / (pts[1][0] - pts[0][0]);
  }
  let kept = null;
  try { kept = JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k => k.endsWith('lab.antenna.wire')) || '') || 'null'); } catch (e) {}
  out.kept = kept;
  resolve(JSON.stringify(out));
})
"""


def the_lab():
    print("\n-- the Lab --")
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
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab#ant", DRIVE, width=1300, height=1400,
                                           settle=1.0, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    leg = 468 / 7.15 / 2
    check("a V asks where its ends are tied off", (got.get("vShown"), got.get("vLabel")), (True, "Ends tied off at (ft)"))
    check("  ends at 20 ft from a 35 ft apex set the droop, on both sliders",
          (got.get("vDroop"), got.get("vMirror")), (str(round(math.degrees(math.asin(15 / leg)))),) * 2)
    check("  raising the apex to 40 keeps the ends and steepens the droop",
          (got.get("vEndsHeld"), got.get("vDroopAfterRaise")), ("20", str(round(math.degrees(math.asin(20 / leg))))))
    check("  and moving the slider sets the ends instead",
          got.get("vEndsFromSlider"), str(round((40 - leg * math.sin(math.radians(20))) * 10) / 10))
    check("a sloping dipole asks for its low end, which is its height while flat",
          (got.get("dLabel"), got.get("dFlatEnds")), ("Low end tied off at (ft)", "40"))
    check("  and a low end at 10 ft from a 40 ft support is its slope",
          got.get("dSlope"), str(round(math.degrees(math.asin(30 / (2 * leg))))))
    check("a vertical has no ends to tie off", got.get("vertShown"), False)
    check("a terminated wire's box starts blank, the handbook's posts", got.get("twBlank"), "")
    rows = got.get("twRows") or []
    check("  ends at 12 ft go in its table, and the ground it covers follows",
          (any("Ends tied off at 12" in r for r in rows), any("249.71" in r or "249.7" in r for r in rows)), (True, True))
    check("  the drawing puts them there, to scale: 6 ft of rise over 124.9 ft",
          abs((got.get("twLegSlope") or 0) - 6 / math.sqrt(125 ** 2 - 36)) < 0.01, True)
    check("  and the reach map is handed them", (got.get("kept") or {}).get("ends_ft"), 12)


def the_sloping_dipole():
    print("\n-- a sloping dipole radiates from its middle --")
    js = (ROOT / "elmer" / "static" / "lab.js").read_text(encoding="utf-8")
    check("its effective height is its middle, slopeDrop below the support",
          "heightFt - (type === 'dipole' ? slopeDrop : slopeDrop / 2)" in js, True)


if __name__ == "__main__":
    the_backend()
    the_lab()
    the_sloping_dipole()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
