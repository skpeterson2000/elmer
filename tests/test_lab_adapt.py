#!/usr/bin/env python3
"""The antenna you have, on the band you want.

    python3 tests/test_lab_adapt.py

Somebody on the Band Plan picked a 160 m segment inside their privileges and
pressed "Set up an antenna for this". The Lab took the kind of antenna they
had and designed a new one for 160 m - 234 ft of V for a 70 ft lot - and
never asked how to get the antenna that is up onto the band. Hams answer
that every week: it may already work there; lengthen it electrically, a coil
in each leg or the whole thing fed as a Marconi T; ladder line and a tuner;
a link of added wire; or, for a band above, jumpers or traps. And a
compromise antenna costs decibels that CW and FT8 do not need, so the mode
matters, and so does the band. What is held here:

  - the station's antenna carries the band it is cut for, from the Band Plan
    and the Lab alike;
  - cut for another band, the Lab leads with that antenna on this one: each
    way to get it there, with its feet and microhenries and what it gives up;
  - the modes the license allows there, now and after dark, to where the
    operator is reaching;
  - the other bands where the antenna works as it is, open now;
  - a harmonic is "it already works here"; a band above is jumpers or traps;
  - cut for the band asked about, nothing changes.
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
DAY = {"fof2": 6.0, "hmf2": 300.0, "elevation": 35.0, "k_index": 2.0, "muf": 20.0}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


SNAP = {"sfi": 120.0, "k_index": 2.0, "hmf2": 300.0, "muf": 20.0, "fof2": 6.0, "elevation": 35.0,
        "muf_source": "test", "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True, "bands": []}
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
  await until(() => typeof bpReachSeed === 'function', 10000);
  localStorage.clear(); bpReachSeed();
  const put = (id, v) => { const el = document.getElementById(id); el.value = v; el.dispatchEvent(new Event('change')); };
  put('bp-reach-ant', 'invertedv'); put('bp-reach-h', '40'); put('bp-reach-cut', '7.150');
  remember('lab.antenna.site', 'small');
  const out = {record: stationAntenna()};
  document.body.innerHTML = '';
  const f = document.createElement('iframe'); f.id = 'fr';
  f.style.width = '1250px'; f.style.height = '1500px'; f.style.border = '0';
  await new Promise(res => { f.onload = res; f.src = '/lab?f=1.900&class=General#ant'; document.body.appendChild(f); });
  const D = f.contentDocument;
  await until(() => D.getElementById('an-adapt') && D.querySelector('#an-adapt table'), 15000);
  await nap(500);
  const box = D.getElementById('an-adapt');
  out.text = box ? box.innerText : '';
  out.cut = D.getElementById('an-cut').value;
  out.first = (() => { const a = D.getElementById('an-advice'); const kids = a ? [...a.querySelectorAll('.nvis')] : [];
                       return kids.length ? kids[0].id : ''; })();
  // A slider moved afterwards: still an evaluation of this antenna at its
  // own height, never the small lot's usual 22 ft.
  const ang = D.getElementById('an-angle'); ang.value = '20';
  ang.dispatchEvent(new f.contentWindow.Event('input'));
  await nap(1500);
  out.afterSlider = (D.getElementById('an-advice') || {}).innerText || '';
  if (box) { const top = box.getBoundingClientRect().top + f.contentWindow.scrollY;
             f.contentWindow.scrollTo(0, Math.max(0, top - 150)); await nap(300); }
  resolve(JSON.stringify(out));
})
"""


def unit():
    from elmer import adapt
    print("\n-- the ways, worked out --")
    p = adapt.plan(1.9, "invertedv", 7.15, height_ft=40, site="small", license_class="General",
                   km=800, snap=DAY, use="regional")
    leads = [w["lead"] for w in p["ways"]]
    check("a 40 m V on 160 m: add wire, a Marconi T, coils, a tuner",
          sorted(leads), sorted(["Add wire.", "Feed it as a Marconi T.", "Load it.",
                                 "Feed it with ladder line and a tuner."]))
    t = next(w for w in p["ways"] if w["lead"] == "Feed it as a Marconi T.")
    check("  the Marconi T names its down-lead, its top hat and its coil",
          ("40 ft down-lead" in t["text"], "62 ft of wire at the top" in t["text"], "µH" in t["text"]),
          (True, True, True))
    loaded = next(w for w in p["ways"] if w["lead"] == "Load it.")
    check("  the T gives up less than coils in the legs of so short a wire",
          t["loss_db"] > loaded["loss_db"], True)
    check("  and they come best first", [w["loss_db"] for w in p["ways"]] ==
          sorted((w["loss_db"] for w in p["ways"]), reverse=True), True)
    print("\n-- the modes and the other bands --")
    modes = {m["label"]: m for m in p["modes"]}
    check("a General's modes on 160 m", sorted(modes), ["CW", "FT8", "SSB"])
    check("  by day 160 m is the D layer's; after dark FT8 and CW are solid",
          (modes["SSB"]["now"], modes["FT8"]["night"], modes["CW"]["night"]), ("short", "solid", "solid"))
    forty = next((b for b in p["bands"] if b["band"] == "40m"), None)
    check("  and 40 m, where the antenna works as it is, is open now in SSB",
          bool(forty and forty["as_is"] and any(m["mode"] == "SSB" for m in forty["modes"])), True)
    check("  a Technician on 40 m has CW only", adapt._allowed_modes("40m", "Technician"), [("cw", "CW")])
    print("\n-- the other cases --")
    h = adapt.plan(21.2, "dipole", 7.05, height_ft=40, license_class="General", km=3000, snap=DAY)
    check("a 40 m dipole on 15 m already works - its third harmonic",
          (h["ways"][0]["lead"], "3rd harmonic" in h["ways"][0]["text"]), ("It already works here.", True))
    up = adapt.plan(14.2, "dipole", 7.15, height_ft=40, license_class="General", km=3000, snap=DAY)
    check("a 40 m dipole on 20 m: jumpers or traps, and the tuner",
          [w["lead"] for w in up["ways"]], ["Shorten it with jumpers or traps.", "Feed it with ladder line and a tuner."])
    v = adapt.plan(3.75, "quarter", 7.15, license_class="General", km=500, snap=DAY)
    check("a 40 m quarter-wave vertical on 80 m: a base coil", v["ways"][0]["lead"], "Load it at the base.")
    check("cut for the band asked about, nothing changes", adapt.plan(7.2, "dipole", 7.15), None)
    check("a Yagi is not adapted here", adapt.plan(1.9, "yagi", 14.2), None)
    check("the Lab and the Band Plan offer the same bands to cut for",
          all(f'value="{m:.3f}"' in (ROOT / "elmer/templates" / page).read_text(encoding="utf-8")
              for m in adapt.CUT_FOR.values() for page in ("lab.html", "bandplan.html")), True)


def main():
    unit()
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    from elmer import db
    conn = db.connect()
    settings = db.get_profile(conn)["settings"]
    settings["location"] = {"lat": 46.603, "lon": -94.3094, "kind": "town", "grid": "EN26uo",
                            "short": "Pequot Lakes", "name": "Pequot Lakes"}
    settings["license_class"] = "General"
    db.save_settings(conn, settings)
    conn.commit()
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
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/bandplan", DRIVE, width=1250, height=1500,
                                           settle=1.0, cookies={"elmer_user": "1"},
                                           out=os.environ.get("LAB_ADAPT_SHOT"), clip="#fr") or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    print("\n-- from the Band Plan, in the Lab --")
    rec = got.get("record") or {}
    check("the Band Plan's antenna carries the band it is cut for", (rec.get("kind"), rec.get("cut_mhz")),
          ("invertedv", 7.15))
    check("  and the Lab opens on it", got.get("cut"), "7.150")
    text = got.get("text") or ""
    check("the Lab leads with that antenna on this band",
          ("Your 40 m antenna on 160 m" in text.replace("YOUR 40 M ANTENNA ON 160 M", "Your 40 m antenna on 160 m"),
           got.get("first")), (True, "an-adapt"))
    after = got.get("afterSlider") or ""
    check("a slider moved keeps the operator's 40 ft, not the lot's usual 22",
          ("what fits here is 22" in after, "Your setup" in after, "Your 40 m antenna on 160 m" in after
           or "YOUR 40 M ANTENNA ON 160 M" in after), (False, True, True))
    check("  the ways, the modes now and after dark, and where it works now",
          ("Marconi T" in text, "after dark" in text, "as it is" in text), (True, True, True))


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
