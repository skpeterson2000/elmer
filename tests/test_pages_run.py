#!/usr/bin/env python3
"""Every page's script actually runs, in a real browser.

    python3 tests/test_pages_run.py

Twice in one day a page's inline script died at parse time and the page ran
with no script at all: once from a stray "});" left by an edit, once from a
`let seats` declared beside an existing `function seats`. The first was
caught by a bracket-balance check; the second is not a bracket problem, and
nothing short of a JavaScript engine can say whether a script runs. So this
loads each page in the Chromium the kiosk already runs, on a throwaway ELMER
on a throwaway state directory, and asks it whether a function the script
defines exists. If the script died, it does not.

This test requires Chromium and fails - not skips - without it. A test that
skips when its tool is missing is a test that never runs on the machine
where it matters.
"""
import subprocess
import sys
import tempfile
import time
import os
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

# A throwaway server, on the isolated state directory _isolate already set.
PORT = 5097
server = subprocess.Popen(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r)\n"
     "from elmer.app import app\n"
     "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
     % (str(ROOT), PORT)],
    env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    else:
        raise SystemExit("the throwaway server never answered")

    # Each page, and a name its inline script defines. A dead script defines
    # nothing, so `typeof` says "undefined".
    PAGES = [
        ("/party", "tick"),
        ("/net", "tick"),
        ("/net/board", "tick"),
        ("/j/1", "tick"),
        ("/lab", "calcAnt"),
        ("/bandplan", "bpRender"),
        ("/", "api"),
    ]
    print("\nevery page's script runs")
    for path, name in PAGES:
        got = _browser.evaluate(f"http://127.0.0.1:{PORT}{path}", f"typeof {name}",
                                settle=1.5, port=9341)
        check(f"{path} defines {name}()", got, "function")
finally:
    server.terminate()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
