#!/usr/bin/env python3
"""One slider, three jobs, and the antenna type is the selector.

    python3 tests/test_angle_slider.py

A dipole and an end-fed slope; an inverted V droops its legs; a ground
plane droops its radials. All three are the same gesture - how far from
horizontal - and they were three sliders with three ids, three defaults
and three chances to forget one. That had already happened once: an-slope
was left out of the input list and the slider did nothing at all.

They are one control now, and the antenna type is the token that drives
it: the label, the range and the starting angle come from the token, and
so does the tail of the readout, so adding an antenna means adding an
entry rather than editing branches in four places.

The range and the start still change with the antenna, because they teach
something. A V at nought degrees is not a V, and forty-five is where a
ground plane's radials come out near fifty ohms.

This needs a browser: the whole of it is what a select does to a range.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


ROOT = Path(__file__).resolve().parents[1]
check("chromium is on this machine", bool(_browser.available()), True)
if not _browser.available():
    sys.exit(1)

PORT = _browser._free_port()
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\n"
     "from elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
     % (str(ROOT), PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

DRIVE = """
new Promise(async resolve => {
  const nap = () => new Promise(r => setTimeout(r, 150));
  const t0 = Date.now();
  while (typeof antennaFields !== 'function' && Date.now() - t0 < 12000) await nap();
  const sel = document.getElementById('an-type');
  const el = document.getElementById('an-angle');
  const lab = document.getElementById('an-angle-label');
  const out = document.getElementById('an-angle-v');
  if (!sel || !el || !lab) { resolve(JSON.stringify({error: 'no controls'})); return; }
  const look = async kind => {
    sel.value = kind;
    sel.dispatchEvent(new Event('input'));
    await nap();
    const box = el.closest('.field');
    return {label: lab.textContent, value: el.value, max: el.max,
            shown: !box || box.style.display !== 'none',
            said: (out || {}).textContent || ''};
  };
  const seen = {};
  for (const kind of ['dipole', 'invertedv', 'groundplane', 'efhw', 'yagi']) {
    seen[kind] = await look(kind);
  }
  /* Set the V to something of our own, wander off, come back. */
  await look('invertedv');
  el.value = '50'; el.dispatchEvent(new Event('input')); await nap();
  await look('dipole');
  const back = await look('invertedv');
  resolve(JSON.stringify({seen: seen, remembered: back.value}));
});
"""

try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        raise SystemExit("the throwaway server never answered")

    raw = _browser.evaluate(f"http://127.0.0.1:{PORT}/lab", DRIVE,
                            settle=1.5, port=9347, cookies={'elmer_user': '1'})
    got = json.loads(raw or "{}")
    print("\nthe type drives the slider")
    check("the controls are there", got.get("error"), None)
    if not got.get("error"):
        seen = got["seen"]
        check("a dipole slopes, from flat", 
              (seen["dipole"]["label"][:5], seen["dipole"]["value"]), ("Slope", "0"))
        check("  an end-fed the same", seen["efhw"]["label"][:5], "Slope")
        check("  a V droops its legs, and never from flat",
              (seen["invertedv"]["label"][:9], seen["invertedv"]["value"]),
              ("Leg droop", "35"))
        check("  a ground plane droops its radials, at the 50 ohm angle",
              (seen["groundplane"]["label"][:6], seen["groundplane"]["value"]),
              ("Radial", "45"))
        check("  and the ranges are the antenna's own",
              (seen["dipole"]["max"], seen["invertedv"]["max"]), ("70", "60"))

        print("\nit is hidden for an antenna with no angle")
        check("a Yagi has no angle to set", seen["yagi"]["shown"], False)
        check("  and a dipole does", seen["dipole"]["shown"], True)

        print("\none idiom, and the tail is the token's")
        check("the V says what the angle is",
              "legs down" in seen["invertedv"]["said"], True)
        check("  the ground plane says what it buys",
              "Ω" in seen["groundplane"]["said"], True)
        check("  and the dipole at nought says flat rather than nothing",
              "flat" in seen["dipole"]["said"], True)

        print("\nand it remembers what you set, per antenna")
        check("a V drooped to 50, left, and returned to", got["remembered"], "50")
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except Exception:
        server.kill()

print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
sys.exit(1 if FAILS else 0)
