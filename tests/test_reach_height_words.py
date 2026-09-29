#!/usr/bin/env python3
"""What the reach map says about the antenna's height fits the antenna.

    python3 tests/test_reach_height_words.py

Under the reach map a line gives the antenna's gain at three angles, then
says what the height means. Those words were a horizontal wire's for every
antenna: a terminated end-fed vee 10 ft up on 40 m - a low-angle, vertically
polarized travelling-wave antenna, weak overhead by its own pattern - was
told it stood at "a DX height, with a dip over the county" and that for NVIS
it "would come down to about 28 ft", up from 10. Held here:

  - the map's answer says what shape of antenna it drew: horizontal,
    vertical, or travelling (a terminated wire);
  - a terminated wire and a vertical are told their weakness overhead is the
    antenna's own and that no height makes them NVIS antennas, with the
    horizontal wire's NVIS height offered as the thing to use instead - no
    "DX height", no "come down";
  - a horizontal wire keeps the reflection's words, and is told to come down
    or to go up to the NVIS height, whichever is true.
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


SNAP = {"sfi": 150.0, "k_index": 2.0, "hmf2": 300.0, "muf": 21.7, "fof2": 6.6, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}
QTH = {"lat": 46.60, "lon": -94.31, "short": "Pequot Lakes", "grid": "EN36"}


def antennas():
    """The map's own antenna blocks, as the server writes them."""
    print("\n-- the map says what shape of antenna it drew --")
    from elmer import app as appmod, propagation
    from elmer.app import app
    propagation.snapshot = lambda *a, **k: dict(SNAP)
    appmod._prefetch_regional = lambda place: None
    c = app.test_client()
    c.post("/api/settings", json={"location": QTH}, environ_base=LOCAL)

    def block(kind, height, band="40m", heading="179"):
        q = {"band": band, "antenna": kind, "height": height, "watts": "50", "heading": heading,
             "ground": "poor", "emission": "ft8"}
        return c.get("/api/bandplan/reach?" + "&".join(f"{k}={v}" for k, v in q.items()),
                     environ_base=LOCAL).get_json()["antenna"]
    out = {"vee": block("tefv", "10"), "vertical": block("quarter", "10", heading=""),
           "dipole_high": block("dipole", "60", heading="90")}
    check("a terminated vee is a travelling-wave antenna", out["vee"]["shape"], "travelling")
    check("a quarter-wave vertical is a vertical", out["vertical"]["shape"], "vertical")
    check("a dipole is horizontal", out["dipole_high"]["shape"], "horizontal")
    check("the vee is weak straight up by its own pattern, and not NVIS",
          (out["vee"]["gain"]["overhead_db"] < -4, out["vee"]["nvis"]), (True, False))
    return out


def words(blocks):
    print("\n-- and the page's words fit it --")
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
    # A horizontal wire below the NVIS height that the model does not call an
    # NVIS antenna is rare on real bands, so that case is given directly.
    cases = dict(blocks)
    cases["dipole_low"] = {"shape": "horizontal", "nvis": False, "nvis_ft": 28, "height_ft": 12,
                           "gain": {"overhead_db": 0.0, "low_db": -3.0}}
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        js = """new Promise(async r => {
          const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
          await until(() => typeof bpHeightWords === 'function', 8000);
          const sgn = x => (x >= 0 ? '+' : '-') + Math.abs(x).toFixed(1) + ' dB';
          const cases = %s;
          const out = {};
          for (const [k, a] of Object.entries(cases))
            out[k] = bpHeightWords(a, a.gain, '40 m', Math.round(a.height_ft || 0), sgn);
          r(JSON.stringify(out));
        })""" % json.dumps(cases)
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", js, settle=0.5,
                                           cookies={"elmer_user": "1"}) or "{}")
        vee = got.get("vee", "")
        check("the vee is told its weakness overhead is its own, low-angle at any height",
              ("fires low along its length" in vee, "that is the antenna, not the ground" in vee), (True, True))
        check("  that no height makes it an NVIS antenna, and what to use instead",
              ("No height makes it an NVIS antenna" in vee, f"a horizontal wire about {blocks['vee']['nvis_ft']} ft up" in vee),
              (True, True))
        check("  and not a DX height, nor to come down", ("DX height" in vee, "come down" in vee), (False, False))
        vert = got.get("vertical", "")
        check("a vertical is told the same, as a vertical",
              ("A vertical sends its power low" in vert, "No height makes it an NVIS antenna" in vert, "DX height" in vert),
              (True, True, False))
        high = got.get("dipole_high", "")
        # One of the three things a horizontal wire's reflection can be doing
        # straight up - at 60 ft on 40 m it is -3 dB there, the middle one.
        said = any(w in high for w in ("reflection is adding", "reflection is cancelling", "Neither adding nor cancelling"))
        check("a dipole 60 ft up keeps a horizontal wire's words, and comes down for NVIS",
              (said, "No height makes it" in high, f"come down to about {blocks['dipole_high']['nvis_ft']} ft" in high),
              (True, False, True))
        check("a horizontal wire below the NVIS height goes up to it, not down",
              ("go up to about 28 ft" in got.get("dipole_low", ""), "come down" in got.get("dipole_low", "")), (True, False))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    words(antennas())
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
