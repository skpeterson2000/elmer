#!/usr/bin/env python3
"""Evaluate this setup judges the height on screen; it does not replace it.

    python3 tests/test_lab_evaluate.py

"Evaluate this setup" set the Lab to ELMER's recommendation - the height,
the NVIS switch, the use - so somebody who had typed the 30 ft their tree
allows and asked what ELMER thought found 69 ft in the box instead, and
every figure on the page answering about an antenna they cannot build. A
suggestion with its reason is what was asked for. What is held here:

  - the operator's height is said plainly beside ELMER's, with what each
    does: the angle a horizontal wire fires at and what that favors, a wire
    too near the ground to be efficient, a vertical whose angle height does
    not set, a terminated wire whose lobe its length sets;
  - the advice answers with it only when a height is sent;
  - on the page, Evaluate leaves the height, the antenna and the NVIS switch
    as they were, and ELMER's height goes in only when "Use it" is pressed.
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


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


SNAP = {"sfi": 120.0, "k_index": 2.0, "hmf2": 300.0, "muf": 20.0, "fof2": 6.0, "muf_source": "test",
        "calibration": {"factor": 1.0, "m3000": 3.1}, "fetched": 1, "ok": True}
SERVE = (
    "import sys; sys.path.insert(0, %r)\n"
    "from elmer import app as appmod, places, propagation\n"
    "propagation.snapshot = lambda *a, **k: dict(%r)\n"
    "places.refresh_in_background = lambda *a, **k: None\n"
    "appmod._prefetch_regional = lambda place: None\n"
    "appmod.app.run(host='127.0.0.1', port=%%d, threaded=True, use_reloader=False)" % (str(ROOT), SNAP))

DRIVE = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms || 150));
  const until = async (f, ms) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await nap(); return f(); };
  await until(() => typeof antennaAdvice === 'function', 12000);
  const tab = [...document.querySelectorAll('button, a')].find(b => b.textContent.trim() === 'Antennas');
  if (tab) tab.click();
  const sel = document.getElementById('an-type'), h = document.getElementById('an-h');
  const nvis = document.getElementById('an-nvis');
  sel.value = 'dipole'; sel.dispatchEvent(new Event('input'));
  await nap(600);
  const fBox = document.getElementById('an-f'); fBox.value = '7.15'; fBox.dispatchEvent(new Event('input'));
  h.value = '30'; h.dispatchEvent(new Event('input'));
  // DX, where ELMER wants 69 ft on 40 m: a real disagreement to be offered, not imposed
  const useSel = document.getElementById('an-use'); if (useSel) useSel.value = 'dx';
  const nvisWas = nvis ? nvis.checked : null;
  await nap(400);
  document.getElementById('an-advise').click();
  await until(() => document.getElementById('an-yours'), 10000);
  await nap(400);
  const out = {height: h.value, type: sel.value, nvisKept: nvis ? nvis.checked === nvisWas : true,
               yours: (document.getElementById('an-yours') || {}).textContent || ''};
  const use = document.querySelector('[data-use-height]');
  out.offered = use ? use.dataset.useHeight : null;
  if (use) { use.click(); await nap(300); }
  out.after = h.value;
  resolve(JSON.stringify(out));
})
"""


def main():
    from elmer import antenna_advice as A
    from elmer.app import app

    print("\n-- the operator's height, said beside ELMER's --")
    low = A.judge_height("dipole", 7.15, "dx", 30, 69)
    check("a dipole at 30 ft on 40 m is judged, not replaced", (low["height_ft"], low["close"]), (30.0, False))
    check("  its angle is said, and ELMER's, and what the lower one favors",
          ("degrees up" in low["words"], "ELMER would aim for 69 ft" in low["words"],
           "fires higher" in low["words"], "nearer contacts" in low["words"]), (True, True, True, True))
    check("  and the page is said to be worked out for theirs",
          "worked out for your height" in low["words"], True)
    at = A.judge_height("dipole", 7.15, "dx", 67, 69)
    check("a few feet off ELMER's is about where ELMER would put it",
          (at["close"], "about where ELMER would put it" in at["words"]), (True, True))
    high = A.judge_height("dipole", 7.15, "regional", 90, 40)
    check("higher than ELMER's for regional work says the near stations get quieter",
          ("fires lower" in high["words"], "get quieter" in high["words"]), (True, True))
    ground = A.judge_height("dipole", 3.8, "regional", 10, 40)
    check("a wire a few feet up on 80 m is told it warms the ground", "warms the earth" in ground["words"], True)
    vert = A.judge_height("quarter", 14.2, "dx", 20, 0)
    check("a vertical is told height does not set its angle", "stays low whatever its height" in vert["words"], True)
    tefv = A.judge_height("tefv", 7.15, "dx", 30, 50)
    check("a terminated wire is told its length sets the lobe, and the handbook's mast",
          ("wavelengths of wire" in tefv["words"], "handbook's mast is 50 ft" in tefv["words"]), (True, True))
    check("no height, no judgment", A.judge_height("dipole", 7.15, "dx", None, 69), None)

    print("\n-- the advice answers with it only when a height is sent --")
    c = app.test_client()
    with_h = c.get("/api/antenna-advice?mhz=7.15&kind=dipole&use=dx&height=30", environ_base=LOCAL).get_json()
    without = c.get("/api/antenna-advice?mhz=7.15&kind=dipole&use=dx", environ_base=LOCAL).get_json()
    check("sent a height, it judges it", (with_h.get("yours") or {}).get("height_ft"), 30.0)
    check("  and still says its own", with_h.get("height_ft") == without.get("height_ft"), True)
    check("not sent one, it says nothing about it", "yours" in without, False)

    print("\n-- on the page, Evaluate leaves the setup as it is --")
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    server = subprocess.Popen([sys.executable, "-c", SERVE % port], env=dict(os.environ),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab#ant", DRIVE, width=1300, height=1100,
                                           settle=1.0, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    check("the height typed is still the height", got.get("height"), "30")
    check("  the antenna is still the antenna", got.get("type"), "dipole")
    check("  the NVIS switch is as it was", got.get("nvisKept"), True)
    check("  and the setup is judged, in words", "At 30 ft" in (got.get("yours") or ""), True)
    offered = got.get("offered")
    check("ELMER's height is offered, not imposed", bool(offered) and offered != "30", True)
    check("  and goes in only when it is asked for", got.get("after"), offered)


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
