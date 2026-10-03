#!/usr/bin/env python3
"""The Band Plan's "Set up an antenna for this" takes its antenna to the Lab.

    python3 tests/test_bandplan_to_lab.py

The Lab read the shared station antenna, but the Band Plan wrote it only
when one of its own controls was changed - so an antenna it had seeded or
remembered never arrived, and one chosen since in the Lab was shown there
instead. What is held here:

  - on the Band Plan, with a different antenna already kept, pressing the
    button keeps the one on screen and puts its kind, height and power on
    the link;
  - with no antenna chosen there, the link is left alone and the Lab
    suggests one, as before;
  - the Lab, opened from such a link in a browser that kept nothing, sets
    up that antenna, at that height, at that power.
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


BANDPLAN = r"""
(async () => {
  for (let i = 0; i < 40 && !document.getElementById('bp-reach-ant'); i++) await new Promise(r => setTimeout(r, 250));
  setStationAntenna({kind: 'efhw', height_ft: 20}, 'lab');            // chosen earlier, somewhere else
  const sel = document.getElementById('bp-reach-ant');
  sel.value = 'tefv';
  document.getElementById('bp-reach-h').value = '50';
  const w = document.getElementById('bp-reach-w');
  delete w.dataset.cb; delete w.dataset.was;                          // an amateur band: the box is the power
  w.value = '400';
  const press = () => {
    const a = document.createElement('a');
    a.className = 'btn sm primary bp-to-lab';
    a.href = '/lab?f=14.175&class=Extra#ant';
    document.body.appendChild(a);
    let went = null;
    const stop = e => { e.preventDefault(); went = a.getAttribute('href'); };
    document.addEventListener('click', stop);
    a.click();
    document.removeEventListener('click', stop);
    a.remove();
    return went;
  };
  const out = {};
  out.href = press();
  out.kept = stationAntenna();
  // On 11 m the box holds the law's 4 W and keeps the operator's own aside;
  // the Lab is asked about the station, so it gets the operator's own.
  w.dataset.cb = '1'; w.dataset.was = '400'; w.value = '4';
  out.cb = press();
  delete w.dataset.cb; delete w.dataset.was;
  sel.value = 'none';
  out.none = press();
  return JSON.stringify(out);
})()
"""

LAB = r"""
(async () => {
  await new Promise(r => setTimeout(r, 1500));
  return JSON.stringify({kind: document.getElementById('an-type').value, h: document.getElementById('an-h').value,
                         pw: document.getElementById('an-pw').value, f: document.getElementById('an-f').value});
})()
"""


def main():
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        print("\nFAILED: this test needs chromium")
        return 1
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer.app import app\n"
         "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port, timeout=1).close()
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise SystemExit("the throwaway server never answered")
        bp = json.loads(_browser.evaluate("http://127.0.0.1:%d/bandplan" % port, BANDPLAN, settle=2.0))
        lab = json.loads(_browser.evaluate("http://127.0.0.1:%d/lab?f=14.175&class=Extra&kind=tefv&h=50&pw=400" % port,
                                           LAB, settle=2.0))
    finally:
        server.terminate()

    print("\n-- the Band Plan's press --")
    check("the antenna on screen is kept, over the one chosen earlier",
          ((bp["kept"] or {}).get("kind"), (bp["kept"] or {}).get("height_ft"), (bp["kept"] or {}).get("from")),
          ("tefv", 50, "bandplan"))
    check("  and the link carries it, its height and the power",
          all(p in (bp["href"] or "") for p in ("kind=tefv", "h=50", "pw=400", "f=14.175")), True)
    check("  on 11 m, the operator's own power, not the 4 W the law holds the box to",
          ("pw=400" in (bp["cb"] or ""), "pw=4&" in (bp["cb"] or "")), (True, False))
    check("  still landing on the Lab's antennas", (bp["href"] or "").endswith("#ant"), True)
    check("with no antenna chosen, the link is left as it was", bp["none"], "/lab?f=14.175&class=Extra#ant")

    print("\n-- the Lab, from the link, in a browser that kept nothing --")
    check("that antenna, at that height and power, on that frequency",
          (lab["kind"], lab["h"], lab["pw"], float(lab["f"] or 0)), ("tefv", "50", "400", 14.175))

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
