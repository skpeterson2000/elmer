#!/usr/bin/env python3
"""The splash hands over when ELMER is ready, not when it is listening.

    python3 tests/test_splash_ready.py

The splash probed a static file, which the server serves as soon as its
socket is bound - and then the dashboard was built and filled its panels in
front of the operator, so a cold start outlasted the splash meant to cover
it. What is held here:

  - /ready.png refuses until the first page and its panels have been built,
    starts that work on the first ask, and then serves the icon;
  - the splash stays up while that work is still going, past its 4 s hold,
    and goes once it is done;
  - a server that answers but never says ready is still gone to, after the
    backstop - a working program is not held behind a picture.
"""
import os
import subprocess
import sys
import time
import urllib.error
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


def the_route():
    print("\n-- /ready.png --")
    from elmer import app as appmod
    c = appmod.app.test_client()
    first = c.get("/ready.png")
    check("refused until the first page and its panels are built", first.status_code, 503)
    check("  and never kept by a cache", first.headers.get("Cache-Control"), "no-store")
    for _ in range(300):
        got = c.get("/ready.png")
        if got.status_code == 200:
            break
        time.sleep(0.1)
    check("the first ask started the work, and then it answers", got.status_code, 200)
    check("  with the icon, an image the splash can load", got.mimetype, "image/png")
    check("the work is the dashboard and the panels it fetches",
          appmod.READY_PATHS, ("/", "/api/propagation", "/api/update"))


# A server whose warm-up takes `delay` seconds, or never finishes (None),
# and which writes down when a browser first asks for the dashboard.
SERVE = """import sys, time
sys.path.insert(0, %r)
from flask import request
from elmer import app as appmod
delay, mark = %r, %r
real = appmod._warm_up
def slow():
    if delay is None:
        return
    time.sleep(delay)
    real()
appmod._warm_up = slow
@appmod.app.before_request
def _mark():
    if request.path == '/' and 'ELMER' not in request.headers.get('User-Agent', ''):
        open(mark, 'a').write(repr(time.time()) + chr(10))
appmod.app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)
"""


def splash_left_at(delay, extra="", settle=12.0):
    """Open the splash against a server with this warm-up, and return how
    long after the browser was started it asked for the dashboard, or None."""
    import tempfile
    port = _browser._free_port()
    mark = Path(tempfile.mkdtemp()) / "home.txt"
    server = subprocess.Popen([sys.executable, "-c", SERVE % (str(ROOT), delay, str(mark), port)],
                              env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        splash = (ROOT / "elmer" / "static" / "splash.html").as_uri() + f"?port={port}{extra}"
        began = time.time()
        _browser.evaluate(splash, "1", width=900, height=600, settle=settle)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    try:
        first = float(mark.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    return first - began


def the_splash():
    print("\n-- the splash waits for ready --")
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    # Timed from the browser's start, which includes Chromium coming up - a
    # second or so - so the bounds allow for it.
    slow = splash_left_at(8.0)
    check("a warm-up taking 8 s holds the splash past its 4 s hold, until it is done",
          slow is not None and slow >= 8.0, True)
    quick = splash_left_at(0.0)
    check("one done at once: the splash goes after its hold, not before",
          quick is not None and 4.0 <= quick <= 7.5, True)
    # A backstop past the hold, so leaving at the hold would be caught.
    never = splash_left_at(None, extra="&ready_ms=6000")
    check("a server that never says ready is gone to after the backstop, not at the hold",
          never is not None and 6.0 <= never <= 10.5, True)
    print(f"  (the browser asked for the dashboard at {slow and round(slow, 1)} s, "
          f"{quick and round(quick, 1)} s and {never and round(never, 1)} s)")


if __name__ == "__main__":
    the_route()
    the_splash()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
