#!/usr/bin/env python3
"""One antenna, whichever page it was chosen on.

    python3 tests/test_station_antenna.py

The Lab, the Band Plan's reach map and the analyzer on Tools each had an
antenna picker with a memory of its own: an inverted V chosen on the Band
Plan was a dipole in the Lab. They now share one record (elmer.js,
stationAntenna). What is held here, in one browser, with the Lab and Tools
opened inside the Band Plan so all three are one browser's pages:

  - chosen on the Band Plan - kind, height, which way it is laid, ground -
    the Lab opens on it, as a choice it evaluates, and the analyzer opens on
    its kind;
  - and so it does by the Band Plan's own "Set up an antenna for this"
    button, which carried the segment's activity (phone, cw) as the kind -
    and the Lab, taking that for an antenna, suggested one over the choice;
  - changed in the Lab, the Band Plan open beside it follows at once;
  - the Band Plan offers every antenna the Lab does;
  - a coax cable picked on the analyzer is not taken for the antenna;
  - a new kind does not inherit the old one's details.
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


SNAP = {"sfi": 120.0, "k_index": 2.0, "hmf2": 300.0, "muf": 20.0, "fof2": 6.0, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}
SERVE = """import sys
sys.path.insert(0, %r)
from elmer import app as appmod, places, propagation
propagation.snapshot = lambda *a, **k: dict(%r)
places.refresh_in_background = lambda *a, **k: None
appmod._prefetch_regional = lambda place: None
appmod.app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)
"""

DRIVE = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  const out = {};
  await until(() => typeof bpReachSeed === 'function' && typeof stationAntenna === 'function', 10000);
  localStorage.clear();
  bpReachSeed();
  const sel = document.getElementById('bp-reach-ant');
  out.offered = [...sel.options].map(o => o.value).filter(v => v !== 'none');
  const put = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change')); };
  put('bp-reach-ant', 'invertedv'); put('bp-reach-h', '40'); put('bp-reach-hd', '120'); put('bp-reach-gnd', 'poor');
  out.record = stationAntenna();
  // The Lab, opened in this same browser.
  const frame = (src) => new Promise(res => {
    const f = document.createElement('iframe');
    f.style.width = '1200px'; f.style.height = '900px';
    f.onload = () => res(f);
    f.src = src; document.body.appendChild(f);
  });
  const lab = await frame('/lab#ant');
  const L = lab.contentWindow, LD = lab.contentDocument;
  await until(() => typeof L.antennaFields === 'function' && LD.getElementById('an-type').value, 10000);
  await nap(800);
  out.lab = {type: LD.getElementById('an-type').value, h: LD.getElementById('an-h').value,
             head: LD.getElementById('an-head').value, byHand: L.eval('anTypeByHand')};
  // By the button on a picked segment, which used to send kind=phone.
  remember('lab.antenna.site', 'small');
  const viaLink = await frame('/lab?f=1.900&kind=phone&class=General#ant');
  const VL = viaLink.contentWindow, VD = viaLink.contentDocument;
  await until(() => typeof VL.antennaFields === 'function' && VD.getElementById('an-type').value, 10000);
  await nap(1500);
  out.viaLink = {type: VD.getElementById('an-type').value, h: VD.getElementById('an-h').value,
                 byHand: VL.eval('anTypeByHand'), f: VD.getElementById('an-f').value,
                 advice: (VD.getElementById('an-advice').innerText || ''),
                 legs: [...VD.querySelectorAll('#an-out table.data tr')].map(r => r.innerText).join(' | ')};
  viaLink.remove();
  // Changed in the Lab: the Band Plan beside it follows.
  const setL = (id, v) => { const el = LD.getElementById(id); el.value = v; el.dispatchEvent(new L.Event('input')); };
  setL('an-type', 'yagi'); await nap(300); setL('an-h', '55'); await nap(600);
  out.afterLab = {bandplan: sel.value, h: document.getElementById('bp-reach-h').value, record: stationAntenna()};
  // The analyzer on Tools opens on it too.
  const tools = await frame('/tools');
  await until(() => tools.contentDocument.getElementById('vn-kind'), 10000);
  await nap(600);
  const vk = tools.contentDocument.getElementById('vn-kind');
  out.analyzer = vk.value;
  // A cable on the analyzer is not the station's antenna.
  vk.value = 'rg58'; vk.dispatchEvent(new tools.contentWindow.Event('change'));
  await nap(300);
  out.afterCable = stationAntenna().kind;
  // A terminated vee chosen here, with its length and ends - which decide
  // its takeoff angle more than its height does - reaches the Lab whole.
  const twBox = () => { const b = document.getElementById('bp-reach-tw'); return !!b && !b.hidden; };
  out.twHiddenForYagi = !twBox();
  put('bp-reach-ant', 'tefv');
  out.twShownForVee = twBox();
  put('bp-reach-len', '150'); put('bp-reach-ends', '10');
  out.veeRecord = stationAntenna();
  out.veeDrawn = bpReachAntenna();
  const lab2 = await frame('/lab#ant');
  const L2 = lab2.contentWindow, LD2 = lab2.contentDocument;
  await until(() => typeof L2.antennaFields === 'function' && LD2.getElementById('an-type').value === 'tefv', 10000);
  await nap(800);
  out.lab2 = {type: LD2.getElementById('an-type').value, len: LD2.getElementById('an-len').value,
              h: LD2.getElementById('an-h').value, bpH: document.getElementById('bp-reach-h').value,
              ends: LD2.getElementById('an-ends').value};
  put('bp-reach-ant', 'dipole');
  out.afterDipole = {shown: twBox(), len: document.getElementById('bp-reach-len').value};
  resolve(JSON.stringify(out));
})
"""


def main():
    print("\n-- the record --")
    js = (ROOT / "elmer" / "static" / "elmer.js").read_text(encoding="utf-8")
    check("one record, in elmer.js, which every page loads", "function setStationAntenna" in js, True)
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    server = subprocess.Popen([sys.executable, "-c", SERVE % (str(ROOT), SNAP, port)], env=dict(os.environ),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", DRIVE, width=1400, height=1000,
                                           settle=1.0, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    from elmer import patterns
    print("\n-- chosen on the Band Plan --")
    check("the Band Plan offers every antenna the Lab does", sorted(got.get("offered") or []),
          sorted(patterns.ANTENNA_Q))
    rec = got.get("record") or {}
    check("its choice is the station's antenna: kind, height, laid, ground",
          (rec.get("kind"), rec.get("height_ft"), rec.get("heading_deg"), rec.get("ground")),
          ("invertedv", 40, 120, "poor"))
    lab = got.get("lab") or {}
    check("the Lab opens on it, height and heading and all",
          (lab.get("type"), lab.get("h"), lab.get("head")), ("invertedv", "40", "120"))
    check("  as a choice, which it evaluates rather than suggests over", lab.get("byHand"), True)
    via = got.get("viaLink") or {}
    check("by the band's own button too, with an old link's kind=phone ignored",
          (via.get("type"), via.get("h"), via.get("byHand")), ("invertedv", "40", True))
    check("  at the band's frequency - 160 m, not the Lab's default 14.200",
          via.get("f"), "1.900")
    import re
    overall = re.search(r"Overall length\s+([\d.]+) ft", via.get("legs") or "")
    # 445/f on 1.9 MHz is 234 ft, less a little for the conductor on screen;
    # on the Lab's default 14.2 it would be 31.
    check("  so the table is a 160 m V's, not a 20 m one's",
          bool(overall) and 225 < float(overall.group(1)) < 240, True)
    check("  on a small lot with a 40 ft support, the 40 ft is what counts, not the usual 22",
          ("what fits here is 22" in (via.get("advice") or ""), "Use 22 ft" in (via.get("advice") or "")),
          (False, False))
    check("  and a wire longer than the lot comes with the ways to get it up",
          "Making it fit" in (via.get("advice") or ""), True)
    bp = (ROOT / "elmer" / "static" / "bandplan.js").read_text(encoding="utf-8")
    check("  and the button no longer sends the segment's activity as a kind",
          "'&kind=' + encodeURIComponent(a.kind)" in bp, False)
    print("\n-- changed in the Lab --")
    after = got.get("afterLab") or {}
    check("the Band Plan open beside it follows", (after.get("bandplan"), after.get("h")), ("yagi", "55"))
    arec = after.get("record") or {}
    check("  and a new kind does not keep the old one's ground", (arec.get("kind"), arec.get("ground")), ("yagi", None))
    print("\n-- the analyzer --")
    check("opens on the station's antenna", got.get("analyzer"), "yagi")
    check("  and a cable picked there is not taken for the antenna", got.get("afterCable"), "yagi")
    print("\n-- a terminated wire's length and ends, chosen on the Band Plan --")
    check("the length and ends boxes are shown for a terminated wire only",
          (got.get("twHiddenForYagi"), got.get("twShownForVee")), (True, True))
    vee = got.get("veeRecord") or {}
    check("150 ft with ends at 10 ft is the station's antenna",
          (vee.get("kind"), vee.get("length_ft"), vee.get("ends_ft")), ("tefv", 150, 10))
    drawn = got.get("veeDrawn") or {}
    check("  the map is drawn from them", (drawn.get("length"), drawn.get("ends")), ("150", "10"))
    check("  and the Lab opens on the same wire",
          tuple((got.get("lab2") or {}).get(k) for k in ("type", "len", "ends")), ("tefv", "150", "10"))
    l2 = got.get("lab2") or {}
    check("  at the Band Plan's height, not the handbook mast the vee's fields start at",
          l2.get("h"), l2.get("bpH"))
    check("a new antenna hides the boxes and does not keep the wire's length",
          ((got.get("afterDipole") or {}).get("shown"), (got.get("afterDipole") or {}).get("len")), (False, ""))


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
