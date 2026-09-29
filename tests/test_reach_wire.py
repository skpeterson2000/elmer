#!/usr/bin/env python3
"""The reach map draws the terminated wire the Lab has, and says which it drew.

    python3 tests/test_reach_wire.py

A terminated end-fed vee's pattern is its length's as much as its height's,
and the band plan has no box for the length: it takes the Lab's. But the
Lab kept its record only when advice was asked for, so a length typed there
never arrived. With 50 ft set in the Lab - a steep, nearly all-round antenna
on 40 m - the map drew the handbook's 500 ft: low, one way, and with a null
close in where a 300 km hop needs a steep angle. Held here:

  - the model itself: 500 ft of vee has that null and 50 ft has none, and
    50 ft is steep and nearly round - so the two pictures were two antennas;
  - the map's answer says which wire it drew, how long in wavelengths, and
    whether the length was given or the handbook's;
  - the Lab keeps the wire's kind and length whenever either changes, and
    the band plan asks for that length;
  - the page says which wire was drawn, and for a long one why a ring close
    in can be dark.
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
MHZ = 7.15


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


SNAP = {"sfi": 150.0, "k_index": 2.0, "hmf2": 300.0, "muf": 21.7, "fof2": 6.6, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}
QTH = {"lat": 46.60, "lon": -94.31, "short": "Pequot Lakes", "grid": "EN36"}


def the_model():
    print("\n-- 50 ft and 500 ft of the same wire are two antennas --")
    from elmer import patterns, propagation as P
    lam = 983.571 / MHZ
    h = 10.0 / lam

    def weights(length):
        w = P.takeoff_weights(patterns.laid("tefv", length, 10.0, MHZ), h, 300.0, mhz=MHZ, heading=179.0, ground="poor")
        return {b: [round(w(km, b), 2) for km in (300, 1000)] for b in (179, 0)}
    long_, short = weights(500), weights(50)
    check("500 ft: a null where a 300 km hop leaves, and the main lobe past it",
          (long_[179][0] < 0.05, long_[179][1] > 0.9), (True, True))
    check("  and nothing off its back", long_[0], [0.0, 0.0])
    check("50 ft: no null close in", short[179][0] > 0.4, True)
    check("  and nearly as much off its back as ahead",
          abs(short[0][0] - short[179][0]) < 0.15, True)
    best = patterns.height_gains(patterns.laid("tefv", 50, 10.0, MHZ), h, mhz=MHZ, ground="poor")["best_deg"]
    check("  its best angle steep, as the Lab draws it", best > 60, True)


def the_answer():
    print("\n-- the map says which wire it drew --")
    from elmer import app as appmod, propagation
    from elmer.app import app
    propagation.snapshot = lambda *a, **k: dict(SNAP)
    appmod._prefetch_regional = lambda place: None
    c = app.test_client()
    c.post("/api/settings", json={"location": QTH}, environ_base=LOCAL)

    def wire(**extra):
        q = {"band": "40m", "antenna": "tefv", "height": "10", "heading": "179", "ground": "poor", **extra}
        return c.get("/api/bandplan/reach?" + "&".join(f"{k}={v}" for k, v in q.items()),
                     environ_base=LOCAL).get_json()["antenna"]["wire"]
    handbook, given = wire(), wire(length="50")
    check("no length given: the handbook's 500 ft, said so", (handbook["length_ft"], handbook["from"]), (500, "handbook"))
    check("50 ft given: drawn as 50, said so", (given["length_ft"], given["from"]), (50, "given"))
    check("  and how long that is on this band", given["length_wl"], round(50 / (983.571 / MHZ), 2))
    q = {"band": "40m", "antenna": "dipole", "height": "30", "heading": "90"}
    d = c.get("/api/bandplan/reach?" + "&".join(f"{k}={v}" for k, v in q.items()), environ_base=LOCAL).get_json()
    check("a dipole has no wire length to say", d["antenna"]["wire"], None)
    return handbook, given


def the_pages(handbook, given):
    print("\n-- the Lab keeps it, and the band plan asks for it --")
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
        # The Lab: the vee chosen and 50 ft typed, with no advice asked for.
        lab_js = """new Promise(async r => {
          const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
          await until(() => document.getElementById('an-len') && typeof isTw === 'function', 8000);
          const type = document.getElementById('an-type'), len = document.getElementById('an-len');
          type.value = 'tefv'; type.dispatchEvent(new Event('input'));
          len.value = '50'; len.dispatchEvent(new Event('input'));
          r(localStorage.getItem('elmer.lab.antenna.wire') || 'null');
        })"""
        kept = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab", lab_js, settle=0.5,
                                            cookies={"elmer_user": "1"}) or "null")
        check("the Lab keeps the wire as it is typed, without advice asked",
              (kept or {}).get("kind"), "tefv")
        check("  with its length", (kept or {}).get("length_ft"), 50)

        # The band plan, with that record in the browser.
        bp_js = """new Promise(async r => {
          const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
          await until(() => typeof bpReachAntenna === 'function', 8000);
          const sel = document.getElementById('bp-reach-ant');
          localStorage.setItem('elmer.lab.antenna.wire', JSON.stringify({kind: 'tefv', length_ft: 50}));
          sel.value = 'tefv';
          const asked_vee = bpReachAntenna().length;
          sel.value = 'termsloper';
          const asked_sloper = bpReachAntenna().length;
          r(JSON.stringify({vee: asked_vee, sloper: asked_sloper,
                            given: bpWireWords(%s), handbook: bpWireWords(%s)}));
        })""" % (json.dumps(given), json.dumps(handbook))
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", bp_js, settle=0.5,
                                           cookies={"elmer_user": "1"}) or "{}")
        check("the band plan asks for the Lab's 50 ft vee", got.get("vee"), "50")
        check("  and not for a different kind of wire", got.get("sloper"), "")
        g, hb = got.get("given", ""), got.get("handbook", "")
        check("the page says the 50 ft wire was drawn, and that it is short and steep",
              ("Drawn as 50 ft of wire" in g, "as the Lab has it" in g, "most of it goes up, and round" in g),
              (True, True, True))
        check("the handbook's wire is said to be the handbook's, with where to set yours",
              ("the handbook’s size" in hb, "Set the length in the Lab" in hb), (True, True))
        check("  and why a ring close in can be dark under it",
              ("nulls between them" in hb, "fill them part way" in hb), (True, True))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    the_model()
    the_pages(*the_answer())
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
