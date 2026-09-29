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


def the_thin_ones():
    print("\n-- the thin ones: 40 AWG magnet wire and zip cord --")
    import math
    from elmer import antenna_advice as A
    check("40 AWG is 0.0799 mm, zip cord 18 and 22 AWG by their conductors",
          (C.INDEX["magnet40"]["od_mm"], C.INDEX["zip18"]["od_mm"], C.INDEX["zip22"]["od_mm"]), (0.0799, 1.02, 0.644))
    check("zip cord says the split-it dipole, and that its jacket lengthens it",
          ("half left joined is the feed line" in C.INDEX["zip18"]["note"], "resonates below" in C.INDEX["zip18"]["caution"]),
          (True, True))
    # No wire's RF loss can be under its own DC resistance. The old ring,
    # pi d delta, put 40 AWG there; the ring now has the skin's thickness.
    half = A.wavelength_ft(7.15) * 0.3048 * 0.5
    under = []
    for c in C.CONDUCTORS:
        d = c["od_mm"] / 1000.0
        dc = A.COPPER_RHO / c["sigma"] / (math.pi * d * d / 4.0) * half / 2.0
        if A.conductor_loss_ohms(7.15, c["od_mm"], c["sigma"], half) < dc - 1e-9:
            under.append(c["key"])
    check("no conductor's loss is below its DC resistance", under, [])
    check("  #14 as it was, to within two percent - the fix is for thin wire",
          round(A.conductor_loss_ohms(7.15, 1.63, 1.0, half), 2) in (1.43, 1.44, 1.45, 1.46), True)
    m = C.INDEX["magnet40"]
    hot = A.power_notes("dipole", 7.15, 100, m["od_mm"], m["sigma"], material="copper")
    qrp = A.power_notes("dipole", 7.15, 5, m["od_mm"], m["sigma"], material="copper")
    check("40 AWG at 100 W: a third of it heats the wire, and the fusing current is said",
          (30 < hot["wire_heat_w"] < 40, any("melts at about" in i for i in hot["items"])), (True, True))
    check("  at 5 W, no word of melting", any("melts" in i for i in qrp["items"]), False)
    m26 = C.INDEX["magnet26"]
    mid = A.power_notes("dipole", 7.15, 100, m26["od_mm"], m26["sigma"], material="copper")
    check("26 AWG is 0.405 mm, under a tenth of 100 W lost, and no word of melting",
          (m26["od_mm"], mid["wire_heat_w"] < 10, any("melts" in i for i in mid["items"])), (0.405, True, False))
    check("  and says the spool's current rating is for a coil, not a wire in the open",
          ("wound tight in a coil" in m26["caution"], "not the limit here" in m26["caution"]), (True, True))
    w14 = A.power_notes("dipole", 7.15, 1500, 1.63, 1.0, material="copper")
    check("#14 at the legal limit is nowhere near melting", any("melts" in i for i in w14["items"]), False)


def the_sources():
    print("\n-- what the Library's books say, cited --")
    import re
    import subprocess as sp
    got = {k: [s["where"] for s in C.sources(k)] for k in ("wire14", "alufence", "alucraft", "zip18", "magnet40")}
    check("the wires cite the ATP's para. H-50", all("para. H-50" in got[k] for k in ("wire14", "alufence", "zip18", "magnet40")), True)
    check("aluminium cites the handbook's conductivity table and its fatigue and contact cautions",
          [w for w in got["alufence"] if w != "para. H-50"], ["Table 46-2, p. 46-6", "p. 27-3", "p. 27-3"])
    check("the aluminium figure in the note is the table's: 3.54 over 5.80",
          round(3.54 / 5.80, 2), C.INDEX["alufence"]["sigma"])
    check("every source has a title, a place and its words",
          all(s.get("title") and s.get("where") and s.get("says") for s in C.SOURCES.values()), True)
    # The ATP ships with ELMER, so its words are checked against the book itself.
    atp = Path(__file__).resolve().parents[1] / "data" / "shelf" / "ATP-6-02.53-2025.pdf"
    from elmer import library
    text = sp.run([library.tool("pdftotext") or "pdftotext", "-enc", "UTF-8", str(atp), "-"],
                  capture_output=True).stdout.decode("utf-8", "ignore")
    flat = re.sub(r"\s+", " ", text)
    check("the ATP is quoted word for word", C.SOURCES["wire"]["says"] in flat, True)
    check("  on the page cited", C.SOURCES["wire"]["says"][:40] in re.sub(r"\s+", " ", text.split("\f")[C.SOURCES["wire"]["page"] - 1]), True)


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
        env=dict(os.environ, ELMER_SHELF=str(ROOT / "data" / "shelf")), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
          const craft = document.getElementById('an-out').innerText;
          sel.value = 'alufence'; sel.dispatchEvent(new Event('input')); sel.dispatchEvent(new Event('change'));
          await new Promise(res => setTimeout(res, 600)); calcAnt(); await new Promise(res => setTimeout(res, 600));
          const links = [...document.querySelectorAll('#an-out a')].map(a => a.getAttribute('href')).filter(h => h.indexOf('/library/read/') === 0);
          r(JSON.stringify({offered: [...sel.options].map(o => o.value), out: craft, fence: document.getElementById('an-out').innerText, links: links}));
        })"""
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab#ant", js, settle=0.5,
                                           cookies={"elmer_user": "1"}) or "{}")
        offered, out = got.get("offered") or [], got.get("out") or ""
        check("the dipole offers all three", all(k in offered for k in ("magnet15", "alufence", "alucraft")), True)
        check("craft wire chosen: its note, its caution, and how to work it",
              ("aluminium whatever color" in out, "Watch out:" in out, "Working it:" in out), (True, True, True))
        fence = got.get("fence") or ""
        check("fence wire: the Library's word, the ATP quoted and the handbook's table",
              ("From the Library:" in fence, "best kinds of wire for antennas are copper and aluminum" in fence, "Table 46-2" in fence),
              (True, True, True))
        check("  and the ATP, which ships with ELMER, opens at its page",
              any(h.startswith("/library/read/ATP-6-02.53-2025.pdf?page=134") for h in got.get("links") or []), True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    the_table()
    the_thin_ones()
    the_sources()
    the_lab()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
