#!/usr/bin/env python3
"""The VNA's calibration buttons mark themselves as the drill goes.

    python3 tests/test_vna_calmarks.py

OPEN, SHORT and LOAD turn green with a check as each is measured, so the
operator can follow the calibration at a glance; with one made and none
under way, all three and DONE stand green; a fresh drill or a reset clears
them. The page is driven in chromium with the calibration states a V2
reports, and with the bare successes an instrument that calibrates on its
own screen gives.
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


JS = r"""
(() => {
  const marked = () => [...document.querySelectorAll('.btn.measured')]
    .map(b => b.getAttribute('data-value') || b.getAttribute('data-vna')).sort().join(' ');
  const out = {};
  vnCalMarks({has: false, measured: []});                  out.none = marked();
  vnCalMarks({has: false, measured: ['open']});            out.open = marked();
  vnCalMarks({has: false, measured: ['open', 'short']});   out.two = marked();
  vnCalMarks({has: true, measured: []});                   out.made = marked();
  vnCalMarks({has: true, measured: ['short']});            out.again = marked();
  vnCalMarkStep('cal-reset');                              out.reset = marked();
  vnCalMarkStep('cal-step', 'open');                       out.shell_open = marked();
  vnCalMarkStep('cal-step', 'load');                       out.shell_two = marked();
  vnCalMarkStep('cal-done');                               out.shell_done = marked();
  const b = document.querySelector('.btn.measured');
  out.check_mark = b ? getComputedStyle(b, '::before').content : '';
  return JSON.stringify(out);
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
        got = json.loads(_browser.evaluate("http://127.0.0.1:%d/tools" % port, JS, settle=2.0))
    finally:
        server.terminate()

    print("\n-- a V2, which says what it holds --")
    check("nothing measured, nothing marked", got["none"], "")
    check("OPEN measured, OPEN marked", got["open"], "open")
    check("OPEN and SHORT", got["two"], "open short")
    check("a calibration made: all three and DONE", got["made"], "cal-done load open short")
    check("a fresh drill marks only what it has measured", got["again"], "short")
    check("a reset clears them", got["reset"], "")
    print("\n-- an instrument that calibrates on its own screen, marked as each succeeds --")
    check("OPEN", got["shell_open"], "open")
    check("then LOAD", got["shell_two"], "load open")
    check("DONE marks it made, as a V2's is", got["shell_done"], "cal-done load open short")
    check("a marked button carries a check, not colour alone", "✓" in got["check_mark"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
