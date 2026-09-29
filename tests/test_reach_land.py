#!/usr/bin/env python3
"""The reach map fills land and water, and the band's color stays the thing
that means something.

    python3 tests/test_reach_land.py

The map drew only coastlines over land and sea of the same near-black, so
the band's glow read as sitting on the lines rather than on an ocean or a
continent. Held here:

  - the shapes ship with the program (tools/land.py): closed rings of land,
    and lakes, coarse and fine, no ring crossing the date line;
  - the fill covers land and not sea, lakes come out as water, and a ring
    off the view is not drawn (drawing all of them made a zoomed drag ten
    times slower);
  - where the reach is nothing, land and water are different colors; where
    it is strong, the pixel is the band's color alone, land or sea;
  - on the real page, mid-Pacific is drawn as water and the middle of a
    continent as land, and the Great Lakes as water.
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
MAPS = ROOT / "elmer" / "static" / "maps"


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


SNAP = {"sfi": 150.0, "k_index": 2.0, "hmf2": 300.0, "muf": 18.3, "fof2": 5.1, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}


def the_files():
    print("\n-- the shapes ship with the program --")
    for name, most_kb in (("land.json", 150), ("land-50m.json", 1500)):
        data = json.loads((MAPS / name).read_text(encoding="utf-8"))
        rings = data.get("land") or []
        check(f"{name}: land and lakes", (len(rings) > 100, len(data.get("lakes") or []) > 10), (True, True))
        check(f"  every ring closed", all(r[0] == r[-1] for r in rings + data["lakes"]), True)
        # Antarctica closes along the pole itself, from 180 to -180 at -90: a
        # jump that runs along a pole is the shape's own edge, not a crossing.
        check(f"  none crosses the date line",
              [i for i, r in enumerate(rings)
               if any(abs(a[0] - b[0]) > 180 and not (abs(a[1]) == 90 and abs(b[1]) == 90) for a, b in zip(r, r[1:]))],
              [])
        check(f"  small enough to ship ({most_kb} KB at most)", (MAPS / name).stat().st_size < most_kb * 1024, True)


def the_page():
    print("\n-- the page fills them, and the band's color wins --")
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
        js = """new Promise(async r => {
          const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
          await until(() => typeof bpFillMask === 'function' && bpLand, 10000);
          const out = {};
          // A square island with a square lake in it, on a 100 x 100 world of degrees.
          const sq = (a, b) => [[a, a], [b, a], [b, b], [a, b], [a, a]];
          const toy = {land: [sq(20, 80)], lakes: [sq(40, 60)]};
          const m = bpFillMask(100, 100, toy, x => x, y => y, 1000, [0, 0, 100, 100]);
          out.sea = m[10 * 100 + 10]; out.land = m[30 * 100 + 30]; out.lake = m[50 * 100 + 50];
          const off = bpFillMask(100, 100, {land: [sq(20, 80)], lakes: []}, x => x, y => y, 1000, [200, 0, 300, 100]);
          out.culled = off[50 * 100 + 50];
          // The pixel's color: nothing at sea and on land differ; a strong reach is the band's alone.
          const px = new Uint8ClampedArray(8);
          reachPixel(px, 0, 0, 0, 1); reachPixel(px, 4, 0, 255, 1);
          out.weak = [Array.from(px.slice(0, 3)), Array.from(px.slice(4, 7))];
          reachPixel(px, 0, 80, 0, 1); reachPixel(px, 4, 80, 255, 1);
          out.strong = [Array.from(px.slice(0, 3)), Array.from(px.slice(4, 7))];
          out.lut80 = Array.from(REACH_LUT.slice(240, 243));
          reachPixel(px, 0, 0, null, 1);
          out.none = Array.from(px.slice(0, 3)); out.lut0 = Array.from(REACH_LUT.slice(0, 3));
          // The whole world's mask, looked up by place.
          const gm = bpGlobeLand(bpLand);
          const at = (lat, lon) => gm.mask[Math.floor((90 - lat) * gm.H / 180) * gm.W + Math.floor((lon + 180) * gm.W / 360)];
          out.pacific = at(0, -150); out.brazil = at(-10, -55); out.sahara = at(23, 10); out.superior = at(47.7, -87.5);
          r(JSON.stringify(out));
        })"""
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", js, settle=0.5,
                                           cookies={"elmer_user": "1"}) or "{}")
        check("the fill covers land and not sea", (got.get("sea"), got.get("land")), (0, 255))
        check("  and a lake comes out as water", got.get("lake"), 0)
        check("  a ring off the view is not drawn", got.get("culled"), 0)
        weak, strong = got.get("weak") or [[], []], got.get("strong") or [[], []]
        check("where the reach is nothing, sea and land are different colors", weak[0] != weak[1], True)
        check("  the sea the bluer", weak[0][2] - weak[0][0] > weak[1][2] - weak[1][0], True)
        check("where it is strong, the band's color alone, land or sea",
              (strong[0] == got.get("lut80"), strong[1] == got.get("lut80")), (True, True))
        check("with no shapes, the map is drawn as it always was", got.get("none"), got.get("lut0"))
        check("the world's mask: mid-Pacific water, Brazil and the Sahara land",
              (got.get("pacific"), got.get("brazil") > 200, got.get("sahara") > 200), (0, True, True))
        check("  and Lake Superior water", got.get("superior"), 0)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    the_files()
    the_page()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
