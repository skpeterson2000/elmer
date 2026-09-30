#!/usr/bin/env python3
"""A wire has to fit where somebody lives, and the Lab's drawings have to
be readable.

    python3 tests/test_lab_fit.py

From a screenshot: 250 ft of terminated wire on 160 m, from an 18 ft mast,
on "A small lot or a short garden" - and not a word about the lot. The sites
held a height and never a length. With it, three things on the same screen:
the compass said "at 74 degrees, where it works" over "reach about 679 mi",
which read as the steep ray reaching that far; the degree sign after the
heading box sat on a line of its own; "12:1, fed here" had the wire drawn
through it, and a town's name sat on the compass's E. What is held here:

  - each wire antenna's footprint - a dipole's 468/f, an inverted-V's 445/f of legs at
    their droop, a terminated wire's legs down from its mast to the end
    posts - against the site's usual straight run, and what to do when it
    does not fit: for this one, the longest terminated wire the lot takes;
  - verticals, beams and whips are not held to a length, nor is the tower
    site, which is "and room for it";
  - the Lab says it does not fit, and what instead;
  - the compass says where the lobe lands before how far the lower rays go;
  - the degree sign keeps to its box, the feed's label clears the wire, and
    no town's name sits on a compass letter.
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
from elmer import antenna_advice as A  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def the_arithmetic():
    print("\n-- what a wire asks of the ground --")
    f = A.fit("tefv", 1.843, "small", height_ft=18, length_ft=250)
    check("the screenshot's vee: two 125 ft legs from 18 ft to 6 ft posts cover 249 ft, the lot about 70",
          (f["need_ft"], f["room_ft"], f["fits"]), (249, 70, False))
    check("  and the longest terminated wire the lot takes from that mast is said",
          any("about 74 ft" in w and "an 18 ft mast" in w for w in f["instead"]), True)
    check("  as 0.14 of a wavelength on 160 m - the resistor's antenna - and a wavelength on about 13 MHz",
          any("0.14 of a wavelength" in w and "heats the resistor" in w and "about 13 MHz" in w
              for w in f["instead"]), True)
    long_enough = A.fit("tefv", 14.2, "small", height_ft=30, length_ft=250)
    check("on 20 m the longest that fits is still over a wavelength, and said as working",
          any("wavelengths here" in w and "still works" in w for w in long_enough["instead"]), True)
    check("  and on 160 m, a vertical", any("vertical" in w for w in f["instead"]), True)
    check("a taller mast shortens the run for the same wire",
          A.footprint_ft("tefv", 1.843, 60, 250) < A.footprint_ft("tefv", 1.843, 18, 250), True)
    check("a 160 m dipole is 468/f and does not fit either, and is told to bend or load",
          (A.fit("dipole", 1.843, "small")["need_ft"], A.fit("dipole", 1.843, "small")["fits"],
           any(w.startswith("Bend it") for w in A.fit("dipole", 1.843, "small")["instead"])), (254, False, True))
    check("a 20 m dipole fits a small lot", A.fit("dipole", 14.2, "small")["fits"], True)
    check("an inverted-V's legs are laid out at their droop: 80 m at 35 degrees",
          A.footprint_ft("invertedv", 3.8, droop_deg=35), round(445 / 3.8 * 0.8192))
    check("verticals, beams and whips are not held to a length",
          [A.fit(k, 1.843, "small") for k in ("quarter", "yagi", "whip")], [None, None, None])
    check("  nor is the tower site, which has room", A.fit("dipole", 1.843, "tower"), None)


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
  await until(() => typeof antennaFields === 'function' && document.getElementById('an-advise'), 12000);
  const tab = [...document.querySelectorAll('button, a')].find(b => b.textContent.trim() === 'Antennas');
  if (tab) tab.click();
  const set = (id, v, ev) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event(ev || 'input')); };
  // The type first and a pause, as test_lab_evaluate does: choosing it sets
  // the rest of the form for that antenna.
  set('an-type', 'tefv');
  await nap(600);
  set('an-f', '1.843'); set('an-site', 'small', 'change');
  set('an-h', '18'); set('an-len', '250'); set('an-head', '116');
  const useSel = document.getElementById('an-use'); if (useSel) useSel.value = 'digital';
  await nap(400);
  document.getElementById('an-advise').click();
  const advice = () => (document.getElementById('an-advice') || {}).innerText || '';
  await until(() => advice().includes('It does not fit'), 10000);
  const plan = () => document.querySelector('#an-pattern svg[data-plan]');
  await until(() => plan() && plan().dataset.type === 'tefv', 10000);
  await nap(800);
  const out = {advice: advice()};
  // The degree sign on the heading box's line.
  // Both boxes: the one in the list and the one beside the figure, which is
  // the one the screenshot showed.
  out.degreeOnItsLine = ['an-head', 'an-head-2'].map(id => {
    const head = document.getElementById(id), wrap = head.parentElement;
    return wrap.tagName === 'SPAN' && wrap.getBoundingClientRect().height < head.getBoundingClientRect().height * 1.5;
  });
  // The feed's label clear of the wire: under the ground line, where the resistor's is.
  const side = document.getElementById('an-svg');
  const feed = [...side.querySelectorAll('text')].find(t => t.textContent.includes('fed here'));
  const wire = side.querySelector('polyline');
  if (feed && wire) {
    const pts = wire.getAttribute('points').trim().split(/\\s+/).map(p => p.split(',').map(Number));
    out.feedBelowWire = feed.getBBox().y > Math.max(...pts.map(p => p[1]));
    // To scale: a leg's rise over its run, as drawn - 12 ft over 124.5.
    out.legSlope = (pts[0][1] - pts[1][1]) / (pts[1][0] - pts[0][0]);
  }
  out.caption = [...side.querySelectorAll('text')].map(t => t.textContent).find(t => t.includes('fires this way')) || '';
  // No town's name on a compass letter.
  const svg = plan();
  const letters = [...svg.querySelectorAll('text')].filter(t => /^[NESW]$/.test(t.textContent.trim())).map(t => t.getBBox());
  const names = [...svg.querySelectorAll('text[data-place]')].map(t => ({name: t.textContent, box: t.getBBox()}));
  const hit = (a, b) => a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
  out.placesNamed = names.length;
  out.onALetter = names.filter(n => letters.some(l => hit(n.box, l))).map(n => n.name);
  out.reachLine = [...svg.querySelectorAll('text')].map(t => t.textContent).find(t => /lands about|reach about/.test(t)) || '';
  resolve(JSON.stringify(out));
})
"""


def the_lab():
    print("\n-- the Lab --")
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
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", method="POST",
                                     data=json.dumps({"location": {"lat": 46.60, "lon": -94.31,
                                                                   "short": "Pequot Lakes", "grid": "EN36"}}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
        shot = os.environ.get("LAB_FIT_SHOT")
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab#ant", DRIVE, width=1300, height=1500,
                                           settle=1.0, cookies={"elmer_user": "1"}, out=shot,
                                           clip=os.environ.get("LAB_FIT_CLIP")) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    advice = got.get("advice") or ""
    check("the small lot is told the vee does not fit, and by how much",
          ("It does not fit" in advice, "249 ft" in advice, "70 ft" in advice), (True, True, True))
    check("  and what does: the longest wire the lot takes", "about 74 ft" in advice, True)
    check("the degree sign keeps to its box's line, in the list and beside the figure",
          got.get("degreeOnItsLine"), [True, True])
    check("the feed's label is below the wire, not on it", got.get("feedBelowWire"), True)
    # The vee was drawn with its height stretched six times and a caption
    # apologising for it; the picture is what a newcomer believes.
    check("the vee is drawn to scale: each leg rises 12 ft over its 124.5 ft of ground",
          abs((got.get("legSlope") or 0) - 12 / 124.5) < 0.01, True)
    check("  and says so, with the ground it covers, and no stretch",
          ("drawn to scale" in got.get("caption", ""), "249 ft of ground" in got.get("caption", ""),
           "true scale" in got.get("caption", "")), (True, True, False))
    check("the compass names places", (got.get("placesNamed") or 0) > 0, True)
    check("  and none of them sits on a compass letter", got.get("onALetter"), [])
    check("the compass says where the lobe lands before how far lower rays go",
          (got.get("reachLine") or "").startswith("lands about") and "lower rays reach" in got.get("reachLine", ""), True)


if __name__ == "__main__":
    the_arithmetic()
    the_lab()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
