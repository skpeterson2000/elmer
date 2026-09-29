#!/usr/bin/env python3
"""Three wires a new operator is offered, and what they teach the hard way.

    python3 tests/test_conductors_hardway.py

Enameled magnet wire, aluminium electric-fence wire and colored aluminium
craft wire are all on the shelf where somebody starting out looks, and each
has a lesson in it that is usually learned by an antenna that will not
connect, will not stay tuned, or corrodes open. Electrically each is
practically #14; the lessons are mechanical and chemical, and the Lab now
says them. Held here:

  - each is in the Lab's list at the metal's real size - magnet wire and
    craft wire by AWG (15 AWG 1.450 mm, 16 AWG 1.291 mm), fence wire by the
    steel wire gauge it is sold by (14 gauge, 2.0 mm) - and the two
    aluminium ones at aluminium's conductivity;
  - each says its lesson: the enamel is an insulator over the whole surface,
    the copper-colored craft wire is aluminium under a nonconducting oxide,
    aluminium clamped to copper corrodes, soft wire stretches and detunes;
  - electrically they cut and cover a band like #14, which is itself worth
    knowing;
  - fence and magnet wire are offered for the terminated wires, which are
    what a quarter-mile spool is for;
  - the Lab shows how to work a conductor, not only its note and caution.
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
from elmer import conductors as C  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def the_table():
    print("\n-- in the list, at the metal's real size --")
    sizes = {k: (C.INDEX[k]["od_mm"], C.INDEX[k]["material"], C.INDEX[k]["sigma"])
             for k in ("magnet15", "alufence", "alucraft")}
    check("magnet wire: 15 AWG copper", sizes["magnet15"], (1.45, "copper", 1.00))
    check("fence wire: 14 gauge by the steel wire gauge, aluminium", sizes["alufence"], (2.0, "aluminium", 0.61))
    check("craft wire: 16 AWG, aluminium", sizes["alucraft"], (1.29, "aluminium", 0.61))

    print("\n-- each says its lesson --")
    m, f, a = C.INDEX["magnet15"], C.INDEX["alufence"], C.INDEX["alucraft"]
    check("the enamel is an insulator, and has to come off", ("insulator" in m["work"], "enamel" in m["work"]), (True, True))
    check("  and soft copper stretches, and snaps where it flexes",
          ("stretches" in m["caution"], "snaps where it flexes" in m["caution"]), (True, True))
    check("craft wire is aluminium whatever its color, under an oxide that does not conduct",
          ("aluminium whatever color" in a["note"], "does not conduct" in a["note"]), (True, True))
    check("  and dead soft: it stretches and parts on a long span",
          ("stretches" in a["caution"], "parts" in a["caution"]), (True, True))
    check("fence wire clamped to copper corrodes, and is sold by the steel gauge",
          ("corrode" in f["caution"], "steel wire gauge" in f["note"]), (True, True))

    print("\n-- electrically, practically #14 --")
    ref = C.describe("wire14", 7.15)
    for k in ("magnet15", "alufence", "alucraft"):
        d = C.describe(k, 7.15)
        check(f"{k}: the same cut and within a few percent of the band",
              (d["k"] == ref["k"], abs(d["band_scale"] - 1.0) <= 0.03), (True, True))
    check("the terminated wires offer fence and magnet wire",
          [k in [o["key"] for o in C.options(7.15, "tefv")] for k in ("alufence", "magnet15")], [True, True])
    check("and the Lab is handed how to work each", all(C.describe(k, 7.15)["work"] for k in ("magnet15", "alufence", "alucraft")), True)


def the_lab():
    print("\n-- the Lab says it --")
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
        js = """new Promise(async r => {
          const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
          await until(() => typeof loadConductors === 'function' && document.getElementById('an-cond'), 10000);
          const set = (id, v) => { const el = document.getElementById(id); el.value = v; };
          set('an-f', '7.15'); set('an-type', 'dipole'); set('an-h', '30');
          await loadConductors(7.15, 'dipole');
          const sel = document.getElementById('an-cond');
          sel.value = 'alucraft'; sel.dispatchEvent(new Event('input')); sel.dispatchEvent(new Event('change'));
          await new Promise(res => setTimeout(res, 600));
          calcAnt();
          await new Promise(res => setTimeout(res, 600));
          r(JSON.stringify({offered: [...sel.options].map(o => o.value), out: document.getElementById('an-out').innerText}));
        })"""
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab#ant", js, settle=0.5,
                                           cookies={"elmer_user": "1"}) or "{}")
        offered, out = got.get("offered") or [], got.get("out") or ""
        check("the dipole offers all three", all(k in offered for k in ("magnet15", "alufence", "alucraft")), True)
        check("craft wire chosen: its note, its caution, and how to work it",
              ("aluminium whatever color" in out, "Watch out:" in out, "Working it:" in out), (True, True, True))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    the_table()
    the_lab()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
