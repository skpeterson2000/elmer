#!/usr/bin/env python3
"""The bench's terminator calculator, in the browser, against bench.py.

    python3 tests/test_bench_js.py

The page works the resistor bank out in static/bench.js so it answers as
the numbers are typed; bench.termination_bank is the same arithmetic in
Python, and test_bench.py holds that one to the right answers. This holds
the two to each other: the same cases, the same banks, on the Tools page as
served. Needs chromium, as the other page tests do.
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
from elmer import bench as B  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# (label, target, watts, share, duty, margin, each, values) - values None is
# E24, "E12" the short series, or a list of what is to hand.
CASES = [
    ("600 ohms, 100 W, 2 W parts", 600, 100, 0.5, 1, 1.5, 2, None),
    ("the handbook's six 106 ohm resistors", 600, 100, 0.5, 1, 1, 100, [106]),
    ("1500 W in 5 W parts", 600, 1500, 0.5, 1, 1.5, 5, None),
    ("800 ohms, SSB, half-watt parts from E12", 800, 50, 0.5, 0.3, 2, 0.5, "E12"),
    ("a drawer of three values", 450, 10, 0.5, 0.5, 1.5, 1, [220, 470, 1000]),
]


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

        def values_js(v):
            return "seriesValues('E12')" if v == "E12" else json.dumps(v)
        calls = ",".join("terminationBank(%s,%s,%s,%s,%s,%s,%s)" % (t, w, s, d, m, e, values_js(v))
                         for _, t, w, s, d, m, e, v in CASES)
        js = ("JSON.stringify({banks: [%s].map(p => p && p.banks.map(b => [b.series, b.parallel, b.value, "
              "+b.total.toFixed(2)])), shown: document.getElementById('bt-out').innerHTML})" % calls)
        got = json.loads(_browser.evaluate("http://127.0.0.1:%d/tools" % port, js, settle=2.0))
    finally:
        server.terminate()

    print("\n-- the page and bench.py find the same banks --")
    for case, js_banks in zip(CASES, got["banks"]):
        label, t, w, s, d, m, e, v = case
        values = B.series_values("E12") if v == "E12" else v
        py = B.termination_bank(t, w, s, d, m, e, values)
        want = [[b["series"], b["parallel"], b["value"], round(b["total"], 2)] for b in py["banks"]]
        check(label, js_banks, want)

    print("\n-- and the card shows them as the page opens --")
    check("the default bank is on the page", "40 × 1.5 kΩ" in got["shown"], True)
    check("  with the heat it was sized for", "<b>50.0 W</b>" in got["shown"], True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
