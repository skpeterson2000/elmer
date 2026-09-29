#!/usr/bin/env python3
"""Local and Zulu, in the bar on every page.

    python3 tests/test_header_clock.py

Every QSO, net, contest and spot is in UTC, and working it out from local in
your head at the moment of a contact is how a log gets an hour wrong. So the
bar carries both. What is held here:

  - both clocks are in the bar, labelled Local (with its zone) and Zulu;
  - Zulu is the UTC time, 24-hour, with its Z;
  - they tick;
  - each says its date on hover - Zulu's is the one that turns over;
  - on a phone the bar keeps Zulu, the one a log needs; a tap shows local
    in its place, label and all, and it goes back to Zulu on its own - a
    glance, never a state it can be left in and logged from.
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


DRIVE = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms));
  const t = id => (document.querySelector(id + ' .clock-t') || {}).textContent || '';
  const shown = id => { const el = document.querySelector(id); return !!el && getComputedStyle(el).display !== 'none'; };
  await nap(300);
  const first = t('#clock-utc');
  const now = new Date(), two = n => String(n).padStart(2, '0');
  const want = two(now.getUTCHours()) + ':' + two(now.getUTCMinutes());
  await nap(1300);
  resolve(JSON.stringify({
    localLab: (document.querySelector('#clock-local .clock-lab') || {}).textContent || '',
    utcLab: (document.querySelector('#clock-utc .clock-lab') || {}).textContent || '',
    local: t('#clock-local'), utc: first, utcLater: t('#clock-utc'), wantHm: want,
    utcTitle: (document.getElementById('clock-utc') || {}).title || '',
    localShown: shown('#clock-local'), utcShown: shown('#clock-utc'),
  }));
})
"""


TAP = """
new Promise(async resolve => {
  const nap = ms => new Promise(r => setTimeout(r, ms));
  const shown = id => { const el = document.querySelector(id); return !!el && getComputedStyle(el).display !== 'none'; };
  const both = () => [shown('#clock-utc'), shown('#clock-local')];
  await nap(300);
  const out = {start: both()};
  document.getElementById('clocks').click(); await nap(100);
  out.tapped = both();
  out.tappedLabel = (document.querySelector('#clock-local .clock-lab') || {}).textContent || '';
  document.getElementById('clocks').click(); await nap(100);
  out.tappedAgain = both();
  document.getElementById('clocks').click(); await nap(10400);
  out.leftAlone = both();
  resolve(JSON.stringify(out));
})
"""


def main():
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
        wide = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab", DRIVE, width=1400, height=700,
                                            settle=1.0, cookies={"elmer_user": "1"}) or "{}")
        phone = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab", DRIVE, width=400, height=800,
                                             settle=1.0, cookies={"elmer_user": "1"}) or "{}")
        tap = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/lab", TAP, width=400, height=800,
                                           settle=1.0, cookies={"elmer_user": "1"}) or "{}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    import re
    print("\n-- in the bar --")
    check("both clocks, labelled", (wide.get("localLab", "").startswith("Local"), wide.get("utcLab")), (True, "Zulu"))
    check("  Local carries its zone", len(wide.get("localLab", "")) > len("Local"), True)
    utc = wide.get("utc", "")
    check("Zulu is 24-hour with its Z", bool(re.fullmatch(r"\d\d:\d\d:\d\dZ", utc)), True)
    check("  and is the UTC time", utc[:5], wide.get("wantHm"))
    check("the local clock shows a time", bool(re.search(r"\d\d:\d\d:\d\d", wide.get("local", ""))), True)
    check("they tick", utc != wide.get("utcLater"), True)
    check("Zulu says its date on hover",
          bool(re.search(r"\d{4}-\d\d-\d\d$", wide.get("utcTitle", ""))), True)
    print("\n-- on a phone --")
    check("the bar keeps Zulu, the one a log needs", (phone.get("utcShown"), phone.get("localShown")), (True, False))
    check("  it starts on Zulu", tap.get("start"), [True, False])
    check("  a tap shows local in its place, labelled as local",
          (tap.get("tapped"), tap.get("tappedLabel", "").startswith("Local")), ([False, True], True))
    check("  a second tap is Zulu again", tap.get("tappedAgain"), [True, False])
    check("  and left alone, local goes back to Zulu by itself", tap.get("leftAlone"), [True, False])


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
