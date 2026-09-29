#!/usr/bin/env python3
"""A zoomed reach map is the same map, closer: the same antenna, power and mode.

    python3 tests/test_reach_zoom.py

When the reach map is zoomed, the page asks the model for the window at a
finer step. That request used to carry the band, the mode and the window and
nothing else, so the server drew the sky alone - every direction alike, at
its default 100 W of SSB. A terminated end-fed vee laid south looked right
across the world and, zoomed in over North America, lit Hudson Bay as
brightly as Texas: a different antenna, or none. Held here:

  - the zoomed request carries the antenna, its height, the way it is laid,
    the ground, the power and the mode, exactly as the page's controls say;
  - an answer for settings changed while it was on its way is not drawn;
  - and the server, asked with them, draws the vee one way even in a window:
    south lit, north dark.
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
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# The sky, canned: this is about what is asked for, not today's ionosphere.
SNAP = {"sfi": 150.0, "k_index": 2.0, "hmf2": 300.0, "muf": 21.7, "fof2": 6.6, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}
QTH = {"lat": 46.60, "lon": -94.31, "short": "Pequot Lakes", "grid": "EN36"}


def the_server():
    print("\n-- the server, asked for a window with the antenna --")
    from elmer import app as appmod, propagation
    from elmer.app import app
    from datetime import datetime, timezone
    propagation.snapshot = lambda *a, **k: dict(SNAP)
    appmod._prefetch_regional = lambda place: None
    evening = datetime(2026, 9, 28, 23, 0, tzinfo=timezone.utc)
    real_reach = propagation.reach_map
    propagation.reach_map = lambda *a, **k: real_reach(*a, **dict(k, when=evening))
    c = app.test_client()
    c.post("/api/settings", json={"location": QTH}, environ_base=LOCAL)
    window = {"top": "71.6", "bottom": "21.6", "left": "-129.3", "span": "70", "step": "1"}
    q = {"band": "40m", "mode": "round", **window, "antenna": "tefv", "height": "10", "watts": "50",
         "heading": "179", "ground": "poor", "emission": "ft8"}
    d = c.get("/api/bandplan/reach?" + "&".join(f"{k}={v}" for k, v in q.items()), environ_base=LOCAL).get_json()
    check("the window is drawn for the vee", ((d.get("antenna") or {}).get("kind"), d.get("window")), ("tefv", True))

    def at(dlat):
        r = int(round((d["lat0"] - (QTH["lat"] + dlat)) / d["step"]))
        col = int(round(((QTH["lon"]) - d["lon0"]) % 360 / d["step"]))
        return d["cells"][r * d["cols"] + col]
    south, north = at(-10), at(10)
    check("  lit a thousand kilometers south, the way it fires", south > 30, True)
    check("  and dark as far north, off its back", north, 0)
    sky = c.get("/api/bandplan/reach?" + "&".join(f"{k}={v}" for k, v in {"band": "40m", "mode": "round", **window}.items()),
                environ_base=LOCAL).get_json()
    check("the window asked without them is the sky alone - what the zoom used to draw",
          (sky.get("antenna"), sky["cells"] != d["cells"]), (None, True))


def the_page():
    print("\n-- the page's zoomed request --")
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer import app as appmod, propagation\n"
         "propagation.snapshot = lambda *a, **k: dict(%r)\nappmod._prefetch_regional = lambda place: None\n"
         "appmod.app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), SNAP, port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        # The controls set as the operator had them; the request recorded
        # rather than sent, and answered as the server would.
        js = """new Promise(async r => {
          const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
          await until(() => typeof bpRefine === 'function', 8000);
          const set = (id, v) => { const el = document.getElementById(id); el.value = v; };
          set('bp-reach-ant', 'tefv'); set('bp-reach-h', '10'); set('bp-reach-w', '50');
          set('bp-reach-hd', '179'); set('bp-reach-gnd', 'poor');
          document.querySelector('input[name="bp-reach-em"][value="ft8"]').checked = true;
          const asked = [];
          const real = window.fetch;
          let answer = {ok: true, cells: [], rows: 0, cols: 0, step: 1, lat0: 0, lon0: 0};
          window.fetch = async (url, opts) => {
            if (String(url).indexOf('/api/bandplan/reach?') === 0 && String(url).indexOf('top=') > 0) {
              asked.push(String(url));
              return {json: async () => answer};
            }
            return real(url, opts);
          };
          bpReachFor = bpReachFor || {band: '40m'};
          bpView.band = '40m|round'; bpView.zoom = 3.1; bpView.proj = 'flat';
          bpView.lat = 46.6; bpView.lon = -94.3; bpView.refined = null;
          await bpRefine();
          const drawn = bpView.refined !== null;
          // settings changed while the answer is on its way: not drawn
          bpView.refined = null;
          window.fetch = async (url, opts) => {
            if (String(url).indexOf('top=') > 0) {
              asked.push(String(url));
              set('bp-reach-h', '40');            // the operator moved the height meanwhile
              return {json: async () => answer};
            }
            return real(url, opts);
          };
          await bpRefine();
          window.fetch = real;
          r(JSON.stringify({asked: asked, drawn: drawn, stale_drawn: bpView.refined !== null}));
        })"""
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", js, settle=0.5,
                                           cookies={"elmer_user": "1"}) or "{}")
        asked = got.get("asked") or []
        check("the zoom asked for its window", len(asked) >= 1, True)
        params = dict(p.split("=", 1) for p in (asked[0].split("?", 1)[1].split("&") if asked else []))
        check("  carrying the antenna, height, laid, ground, power and mode",
              tuple(params.get(k) for k in ("antenna", "height", "heading", "ground", "watts", "emission")),
              ("tefv", "10", "179", "poor", "50", "ft8"))
        check("  and the window itself", all(k in params for k in ("top", "bottom", "left", "span", "step")), True)
        check("its answer is drawn", got.get("drawn"), True)
        check("an answer for settings changed on the way is not", got.get("stale_drawn"), False)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    the_server()
    the_page()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
