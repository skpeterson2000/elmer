#!/usr/bin/env python3
"""The reach map has a great-circle view, centered on the station.

    python3 tests/test_reach_globe.py

On the flat map a throw that runs off the top carries on over the pole and
comes down half a world to the side - correct, and it looks like a smear
along the edge unconnected to the lobe it came from. The great-circle view
is azimuthal equidistant about the QTH: a straight line from the middle is a
real heading, the distance from the middle is the real distance, and the
rim is the far side of the world, so there is no edge to leave by. What is
held here:

  - the flat map is still what opens, and the view is a choice that is kept;
  - in the great-circle view the station is the middle of the picture, and
    past the rim is empty - there is nothing further away than the far side;
  - it zooms about the middle and cannot be dragged off it;
  - the note under the map says when places were reached the long way round.
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


SNAP = {"sfi": 150.0, "k_index": 1.0, "hmf2": 300.0, "muf": 28.0, "fof2": 8.0, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}
SERVE = (
    "import sys; sys.path.insert(0, %r)\n"
    "from elmer import app as appmod, places, propagation\n"
    "propagation.snapshot = lambda *a, **k: dict(%r)\n"
    "places.refresh_in_background = lambda *a, **k: None\n"
    "appmod._prefetch_regional = lambda place: None\n"
    "appmod.app.run(host='127.0.0.1', port=%%d, threaded=True, use_reloader=False)" % (str(ROOT), SNAP))

DRIVE = """
new Promise(async resolve => { try {
  const nap = ms => new Promise(x => setTimeout(x, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof bpReachDraw === 'function' && document.getElementById('bp-reach-proj'), 12000);
  const out = {};
  const proj = document.getElementById('bp-reach-proj');
  out.opens = proj.value;
  await until(() => bpReachFor && bpReachFor.qth, 15000);
  // Which places the long way wins is the model's business, held in
  // test_long_path.py against a pinned clock. Here the page is asked only to
  // say so: the real answer, with three of its places marked the long way.
  const realFetch = window.fetch;
  window.fetch = async (u, o) => {
    const r = await realFetch(u, o);
    if (!String(u).includes('/api/bandplan/reach')) return r;
    const j = await r.json();
    j.long_cells = 3;
    return new Response(JSON.stringify(j), {status: r.status, headers: {'Content-Type': 'application/json'}});
  };
  const b20 = await until(() => document.querySelector('button[data-band="20 m"]'), 10000);
  if (b20) b20.click();
  await until(() => bpReachFor && bpReachFor.mhz === 14 && bpReachFor.long_cells === 3, 15000);
  await nap(300);
  out.longCells = bpReachFor.long_cells;
  out.note = (document.getElementById('bp-reach-note') || {}).textContent || '';
  window.fetch = realFetch;
  proj.value = 'globe'; proj.dispatchEvent(new Event('change'));
  await nap(400);
  const canvas = document.getElementById('bp-reach-map');
  const g = canvas.getContext('2d');
  const at = (x, y) => [...g.getImageData(Math.round(x), Math.round(y), 1, 1).data].slice(0, 3);
  const cx = canvas.width / 2, cy = canvas.height / 2;
  const here = at(cx, cy);
  out.middleIsHere = here[0] > 180 && here[1] > 70 && here[1] < 190 && here[2] < 120;   // the attention orange
  out.corner = at(2, 2);
  out.kept = recall('bandplan.proj', 'flat');
  const lon = bpView.lon, lat = bpView.lat;
  bpZoomAt(2, canvas.getBoundingClientRect().left + 10, canvas.getBoundingClientRect().top + 10);
  await nap(400);
  out.zoom = bpView.zoom;
  out.stillHere = bpView.lon === lon && bpView.lat === lat;
  const hereZoomed = at(cx, cy);
  out.middleStillHere = hereZoomed[0] > 180 && hereZoomed[2] < 120;
  resolve(JSON.stringify(out));
} catch (e) { resolve(JSON.stringify({error: String(e)})); } })
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
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/settings", method="POST",
                                     data=json.dumps({"location": {"lat": 46.60, "lon": -94.31,
                                                                   "short": "Pequot Lakes", "grid": "EN36"}}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", DRIVE, width=1400, height=1200,
                                           settle=1.0, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    if got.get("error"):
        print("  page:", got["error"])

    print("\n-- the flat map opens, and the view is a choice that is kept --")
    check("it opens on the flat map", got.get("opens"), "flat")
    check("the great circle, once chosen, is kept", got.get("kept"), "globe")

    print("\n-- the great circle is centered on the station, and ends at the far side --")
    check("the station is the middle of the picture", got.get("middleIsHere"), True)
    check("past the rim there is nothing: the far side of the world is as far as it goes",
          got.get("corner"), [13, 17, 23])

    print("\n-- it zooms about the middle --")
    check("zooming in zooms", got.get("zoom"), 2)
    check("  about the station, wherever the pointer was", (got.get("stillHere"), got.get("middleStillHere")), (True, True))

    print("\n-- and the note says when the long way round was the better path --")
    check("an answer with places reached the long way", got.get("longCells"), 3)
    check("  is said under the map, with how many", "3 places on this map are reached better the long way round" in (got.get("note") or ""), True)


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
