#!/usr/bin/env python3
"""FM on the reach map: in bounds where the rules put it, and rated for the fades.

    python3 tests/test_reach_fm.py

The map offered FM on every HF band and rated it like a steady signal: 100 W
of FM on 20 m lit 5,000 km. Then, for a while, it offered FM only where the
band plan has FM activity - which is convention, not law, and wrong both
ways: narrow FM is legal on 20 m for a General, and a Technician may not
transmit FM on 10 m at all. Held here:

  - whether a class may transmit FM on a band is 47 CFR's answer, quoted
    word for word from ELMER's copy: phone within the class's privileges,
    narrow below 29.0 MHz (97.307(f)(1)); never on 30 m (97.305(c)), never
    on 60 m (97.303(h)(3)), never by a Novice or Technician (97.307(f)(10));
    CB under Part 95;
  - on a sky path FM needs the Rayleigh fade allowance on top of its own
    threshold - 9.8 dB for 90 percent of the time, from the formula - and
    the other modes do not;
  - asked for FM out of bounds, the map is not drawn: the answer is the
    rule, for the page's owl; in bounds, it is drawn as FM;
  - the page marks FM out of bounds on the panel, shows the owl with the
    rule quoted in place of the map without asking for one, and where FM
    is legal but nobody operates it, says both.
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
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
SECTION = "§ "


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


SNAP = {"sfi": 180.0, "k_index": 2.0, "hmf2": 300.0, "muf": 30.0, "fof2": 9.5, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}
QTH = {"lat": 46.60, "lon": -94.31, "short": "Pequot Lakes", "grid": "EN36"}


def the_model():
    print("\n-- where the rules put FM --")
    from elmer import bandplan as B, explain
    from elmer import propagation as P
    table = {}
    for band in ("160 m", "80 m", "60 m", "40 m", "30 m", "20 m", "17 m", "15 m", "12 m", "10 m", "11 m"):
        table[band] = {c: B.fm_permission(band, c)["permitted"] for c in ("Technician", "General", "Extra")}
    check("a Technician: CB only", [b for b, r in table.items() if r["Technician"]], ["11 m"])
    check("a General: every HF phone band but 60 m and 30 m",
          [b for b, r in table.items() if not r["General"]], ["60 m", "30 m"])
    tech10 = B.fm_permission("10 m", "Technician")
    check("  a Technician on 10 m is out, under 97.307(f)(10)",
          [r["citation"] for r in tech10["rules"]], [SECTION + "97.307(f)(10)"])
    check("  30 m and 60 m out, each under its own rule",
          ([r["citation"] for r in B.fm_permission("30 m", "Extra")["rules"]],
           [r["citation"] for r in B.fm_permission("60 m", "Extra")["rules"]]),
          ([SECTION + "97.305(c)(3)(viii)"], [SECTION + "97.303(h)(3)"]))
    g20 = B.fm_permission("20 m", "General")
    check("a General on 20 m: in bounds, narrow, under 97.307(f)(1)",
          (g20["permitted"], g20["narrow"], [r["citation"] for r in g20["rules"]], g20["segments"]),
          (True, True, [SECTION + "97.307(f)(1)"], [[14.225, 14.35]]))
    every = [r for band in table for c in ("Technician", "General", "Extra") for r in B.fm_permission(band, c)["rules"]]
    parts = explain.part97()
    astray = [r["citation"] for r in every
              if not r["quote"] or r["quote"] not in ((parts.get(r["url"].rsplit("-", 1)[1]) or {}).get("paragraphs") or [])]
    check("every rule is quoted word for word from ELMER's Part 97", astray, [])
    check("FM is operated, by the band plan, on 10 m and CB only - a different question",
          sorted(n for n, f, _ in P.BANDS if f <= 30 and P.fm_used(n)), ["10m", "11m"])

    print("\n-- FM over the sky, through its fades --")
    check("the allowance is the Rayleigh formula's for 90 percent",
          P.FM_SKY_FADE_DB, round(-10 * math.log10(-math.log(0.9)), 1))
    check("  which is 9.8 dB", P.FM_SKY_FADE_DB, 9.8)
    # Against the mode's own need at the far end, worked out apart from the
    # sky path: the same site and sun sky_budget asks the link budget for.
    from elmer import linkbudget
    fm = P.sky_budget(29.6, 2000, 1, 100, "fm")
    own = linkbudget.needed_dbm(29.6, "fm", "residential", sun_deg=0.0)
    check("FM's need on a sky path is its own threshold plus the allowance",
          (fm["fade_db"], round(fm["needed_dbm"] - own, 1)), (9.8, 9.8))
    for mode in ("ssb", "cw", "ft8", "am"):
        b = P.sky_budget(29.6, 2000, 1, 100, mode)
        check(f"  {mode.upper()} gets none, and needs only its own",
              (b["fade_db"], round(b["needed_dbm"] - linkbudget.needed_dbm(29.6, mode, "residential", sun_deg=0.0), 1)),
              (0.0, 0.0))


def the_route():
    print("\n-- the map asked for FM --")
    from elmer import app as appmod, propagation
    from elmer.app import app
    propagation.snapshot = lambda *a, **k: dict(SNAP)
    appmod._prefetch_regional = lambda place: None
    c = app.test_client()
    c.set_cookie("elmer_user", "1")
    c.post("/api/settings", json={"location": QTH}, environ_base=LOCAL)

    def reach(band, emission, cls):
        q = {"band": band, "emission": emission, "class": cls, "antenna": "dipole", "height": "50",
             "watts": "100", "heading": "90"}
        return c.get("/api/bandplan/reach?" + "&".join(f"{k}={v}" for k, v in q.items()), environ_base=LOCAL).get_json()
    tech = reach("10m", "fm", "Technician")
    check("FM on 10 m for a Technician: no map, the rule instead",
          (tech["ok"], "cells" in tech, [r["citation"] for r in tech["out_of_bounds"]["rules"]]),
          (False, False, [SECTION + "97.307(f)(10)"]))
    check("FM on 30 m for an Extra: out", reach("30m", "fm", "Extra").get("out_of_bounds", {}).get("permitted"), False)
    g20 = reach("20m", "fm", "General")
    check("FM on 20 m for a General: drawn as FM, with its fade allowance",
          (g20["ok"], g20["emission_depth"]["mode"], g20["emission_depth"]["sky_fade_db"]), (True, "fm", 9.8))
    check("FM on CB for anybody", reach("11m", "fm", "Technician")["ok"], True)
    check("SSB on 10 m for a Technician is not the question", reach("10m", "ssb", "Technician")["ok"], True)

    def bands(cls):
        return {b["name"]: b for b in c.get(f"/api/bandplan?class={cls}", environ_base=LOCAL).get_json()["bands"]}
    t, g = bands("Technician"), bands("General")
    check("the band list carries the rule for the class read",
          (t["10 m"]["fm"]["permitted"], g["10 m"]["fm"]["permitted"], g["20 m"]["fm"]["permitted"]), (False, True, True))
    check("  and whether FM is operated there", (g["20 m"]["fm_used"], g["10 m"]["fm_used"]), (False, True))


def the_page():
    print("\n-- the page --")
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
          await until(() => typeof bpReach === 'function' && bpData, 10000);
          const fm = document.querySelector('input[name="bp-reach-em"][value="fm"]');
          const bandsFor = async cls => (await (await fetch('/api/bandplan?class=' + cls)).json()).bands;
          const out = {};
          // Read as a Technician: 10 m FM is out of bounds.
          document.getElementById('bp-class').value = 'Technician';
          const t10 = (await bandsFor('Technician')).find(b => b.name === '10 m');
          let asked = 0;
          const real = window.fetch;
          window.fetch = (url, o) => { if (String(url).indexOf('/api/bandplan/reach') === 0) asked++; return real(url, o); };
          bpSetEmission('fm'); bpBand = t10.name; bpReachCache = {};
          await bpReach(t10);
          const box = document.getElementById('bp-reach-oob');
          out.tech = {marked: fm.closest('label').classList.contains('oob'), owl: !box.hidden,
                      text: box.innerText, asked: asked, drawn: bpReachFor !== null};
          window.fetch = real;
          // Read as a General on 20 m: drawn, legal and not used.
          document.getElementById('bp-class').value = 'General';
          const g20 = (await bandsFor('General')).find(b => b.name === '20 m');
          bpBand = g20.name; bpReachCache = {};
          await bpReach(g20);
          await until(() => bpReachFor, 20000);
          out.general = {marked: fm.closest('label').classList.contains('oob'), owl: !box.hidden,
                         mode: document.getElementById('bp-reach-mode').innerText};
          r(JSON.stringify(out));
        })"""
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", js, settle=0.5,
                                           cookies={"elmer_user": "1"}) or "{}")
        tech, gen = got.get("tech") or {}, got.get("general") or {}
        check("a Technician on 10 m: FM marked out of bounds on the panel", tech.get("marked"), True)
        check("  the owl in place of the map, the rule quoted and cited",
              (tech.get("owl"), "J3E and R3E" in (tech.get("text") or ""), "97.307(f)(10)" in (tech.get("text") or "")),
              (True, True, True))
        check("  and no map asked for, and none drawn", (tech.get("asked"), tech.get("drawn")), (0, False))
        check("a General on 20 m: FM in bounds, no owl", (gen.get("marked"), gen.get("owl")), (False, False))
        check("  narrow, with the rule quoted, and said to be legal and not used",
              ("modulation index greater than 1" in (gen.get("mode") or ""), "Legal here, and not used" in (gen.get("mode") or "")),
              (True, True))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    the_model()
    the_route()
    the_page()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
