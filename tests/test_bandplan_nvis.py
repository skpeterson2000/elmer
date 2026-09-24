#!/usr/bin/env python3
"""The NVIS switch on the band plan gives the panel back when it is turned off.

    python3 tests/test_bandplan_nvis.py

The switch is a comparison: tick it and the panel is set to a wire a fifth of
a wave up, which is an NVIS antenna, and the reach map is redrawn for it.
Untick it and you are meant to get your own antenna back and see the two
pictures side by side, which is the whole reason the switch is there.

It did not give it back. The handler acted only on the way in, so unticking
left the inverted V on the panel and redrew exactly the same map - and the
map, reported as doing a poor job of showing what NVIS is, was being asked to
show the difference between an NVIS antenna and itself. On every band and in
any ionosphere, because it is not a propagation question at all.

Nothing short of a browser can check this: the whole of it is what a change
event does to two form controls.
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
    print("\nFAILED: this test needs chromium")
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
  const nap = () => new Promise(r => setTimeout(r, 200));
  const t0 = Date.now();
  while ((typeof bpReachSeed !== 'function' || typeof bpData === 'undefined'
          || !bpData || !bpData.bands) && Date.now() - t0 < 12000) await nap();
  if (typeof bpData === 'undefined' || !bpData || !bpData.bands) {
    resolve(JSON.stringify({error: 'no band plan'})); return;
  }
  /* an HF band, so the reach panel is in play at all */
  const hf = bpData.bands.find(b => b.high <= 30 && b.low >= 3);
  if (!hf) { resolve(JSON.stringify({error: 'no HF band'})); return; }
  bpBand = hf.name;
  bpReachSeed();
  const sel = document.getElementById('bp-reach-ant');
  const h = document.getElementById('bp-reach-h');
  const nv = document.getElementById('bp-reach-nvis');
  if (!sel || !h || !nv) { resolve(JSON.stringify({error: 'no panel'})); return; }
  /* a ground-mounted vertical: the antenna NVIS is worth comparing against */
  sel.value = 'quarter'; h.value = '8';
  const before = {ant: sel.value, h: h.value};
  nv.checked = true;  nv.dispatchEvent(new Event('change'));
  await nap();
  const on = {ant: sel.value, h: h.value};
  nv.checked = false; nv.dispatchEvent(new Event('change'));
  await nap();
  const off = {ant: sel.value, h: h.value};
  resolve(JSON.stringify({band: hf.name, before: before, on: on, off: off}));
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

    raw = _browser.evaluate(f"http://127.0.0.1:{PORT}/bandplan", DRIVE,
                            settle=1.5, port=9343, cookies={'elmer_user': '1'})
    got = json.loads(raw or "{}")
    print("\nthe switch is a comparison, so it has to be reversible")
    check("the panel answered", got.get("error"), None)
    if not got.get("error"):
        print(f"    (on {got['band']})")
        check("ticking it sets a low wire", got["on"]["ant"], "invertedv")
        check("  a fifth of a wave up, not the height that was there",
              got["on"]["h"] != got["before"]["h"], True)
        check("unticking gives the antenna back", got["off"]["ant"],
              got["before"]["ant"])
        check("  and the height with it", got["off"]["h"], got["before"]["h"])
        check("  so off is not still the NVIS wire",
              got["off"]["ant"] == "invertedv" and got["before"]["ant"] != "invertedv",
              False)
finally:
    server.terminate()
    try:
        server.wait(timeout=5)
    except Exception:
        server.kill()

print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
sys.exit(1 if FAILS else 0)
