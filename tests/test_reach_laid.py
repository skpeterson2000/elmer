#!/usr/bin/env python3
"""The reach map draws a directional antenna's pattern even when the box for
which way it is laid is empty, and says the direction was assumed.

    python3 tests/test_reach_laid.py

A blank "laid" box used to mean "all round": the map dropped the antenna's
direction entirely, so a Yagi or a terminated end-fed vee - antennas that fire
one way - came out as a doughnut, the same as a vertical. An operator reading
that map was told a beam covers everywhere. What is held here:

  - a blank box on an antenna with a direction is drawn laid toward north,
    exactly the map a typed 0 draws, and the answer says it was assumed;
  - a typed 0 is not "assumed", and a vertical, which has no direction, is
    still drawn the same all round and assumes nothing;
  - the terminated wire's map really turns when it is laid another way;
  - the page says so beside the box: amber and "assumed" when it guessed,
    and for a terminated wire, which way it fires once it is set.
"""
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


# The sky, canned: the map is asked about geometry and the antenna, not about
# today's ionosphere, and a test asks nobody's server anything.
SNAP = {"sfi": 120.0, "k_index": 2.0, "hmf2": 300.0, "muf": 20.0, "fof2": 6.0, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}


def main():
    from elmer import app as appmod, propagation
    from elmer.app import app
    propagation.snapshot = lambda *a, **k: dict(SNAP)
    appmod._prefetch_regional = lambda place: None
    # One moment for every map, or two asked a second apart differ where the
    # terminator crosses a cell, and "the same map" would be the clock's call.
    from datetime import datetime, timezone
    noon = datetime(2026, 6, 21, 18, 0, tzinfo=timezone.utc)
    real_reach = propagation.reach_map
    propagation.reach_map = lambda *a, **k: real_reach(*a, **dict(k, when=noon))
    c = app.test_client()
    c.post("/api/settings", json={"location": {"lat": 46.60, "lon": -94.31, "short": "Pequot Lakes", "grid": "EN36"}},
           environ_base=LOCAL)

    def reach(**kw):
        q = {"band": "20m", "height": "50", "watts": "100", "ground": "average", **kw}
        r = c.get("/api/bandplan/reach?" + "&".join(f"{k}={v}" for k, v in q.items()), environ_base=LOCAL)
        return r.get_json()

    print("\n-- a blank box on an antenna with a direction is drawn laid toward north, and says so --")
    blank = reach(antenna="tefv", heading="")
    typed = reach(antenna="tefv", heading="0")
    check("a blank box draws the terminated vee laid toward north",
          (blank["antenna"]["heading"], blank["antenna"]["heading_assumed"]), (0.0, True))
    check("  the same map a typed 0 draws, cell for cell", blank["cells"] == typed["cells"], True)
    check("  and a typed 0 is the operator's, not assumed", typed["antenna"]["heading_assumed"], False)
    yagi = reach(antenna="yagi", heading="")
    check("a Yagi with a blank box is drawn pointing north, assumed",
          (yagi["antenna"]["heading"], yagi["antenna"]["heading_assumed"]), (0.0, True))
    vert = reach(antenna="quarter", heading="")
    check("a vertical has no direction: still all round, nothing assumed",
          (vert["antenna"]["heading"], vert["antenna"]["heading_assumed"]), (None, False))

    print("\n-- and the terminated wire's map turns with it --")
    south = reach(antenna="tefv", heading="180")
    check("laid south, the map is not the map laid north", south["cells"] != typed["cells"], True)

    print("\n-- the page says it beside the box --")
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer import app as appmod, propagation\n"
         # the page asks for the sky as it loads: the same canned one here
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
          await until(() => typeof bpReachLaid === 'function', 8000);
          const box = document.getElementById('bp-reach-laid'), hd = document.getElementById('bp-reach-hd');
          const out = {};
          bpReachLaid({antenna: {kind: 'tefv', heading: 0, heading_assumed: true}});
          out.assumed = box.hidden ? '' : box.textContent;
          out.placeholder = hd.placeholder;
          out.amber = hd.style.borderColor !== '';
          bpReachLaid({antenna: {kind: 'tefv', heading: 45, heading_assumed: false}});
          out.set = box.textContent;
          out.cleared = hd.style.borderColor === '' && hd.placeholder === 'laid';
          bpReachLaid({antenna: {kind: 'quarter', heading: null, heading_assumed: false}});
          out.vertical_hidden = box.hidden;
          r(JSON.stringify(out));
        })"""
        import json
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", js, settle=0.5,
                                           cookies={"elmer_user": "1"}) or "{}")
        check("an assumed direction is said, beside the box",
              ("assumed" in got.get("assumed", ""), "north" in got.get("assumed", "")), (True, True))
        check("  and a terminated wire is told which end is which",
              "from the feed end to the resistor" in got.get("assumed", ""), True)
        check("  the box itself shows it: amber, and a questioning placeholder",
              (got.get("amber"), got.get("placeholder")), (True, "0 ?"))
        check("set to 45, it says the wire fires northeast and that a wrong lobe means a wrong wire",
              ("fires northeast" in got.get("set", ""), "wire that needs turning" in got.get("set", "")), (True, True))
        check("  and the warning is gone once a direction is given", got.get("cleared"), True)
        check("a vertical gets no line about direction at all", got.get("vertical_hidden"), True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
