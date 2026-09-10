#!/usr/bin/env python3
"""What the kiosk shows while the server is still coming up.

    python3 tests/test_kiosk_splash.py

The splash exists to fill the empty screen on a cold card, and the danger in
it is that it fills the screen on a warm one too: shown on every machine it
makes the struggling unit indistinguishable from the healthy one, and the
difference then lives only in a log nobody opens.  So the rule under test is
not "a splash appears" but "a splash appears late": under the grace period the
browser goes straight to the program and the splash is never seen at all.

Time is forced rather than waited on - the real grace is two and a half
seconds and no test should spend them.
"""
import logging
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import diagnostics, kiosk  # noqa: E402

# The last case deliberately lets the wait run out, which the module warns
# about.  That warning is the expected answer here, not news.
logging.getLogger("elmer").setLevel(logging.CRITICAL)

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run(comes_up_after, grace=0.3, timeout=2.0):
    """Start the launcher against a port that answers after so many seconds.

    Returns the URL the browser was opened on, or None if it was never opened.
    """
    began = time.monotonic()
    opened = []

    def port_in_use(_port):
        return time.monotonic() - began >= comes_up_after

    def launch(url):
        opened.append(url)
        return None                       # nothing to watch or shut down

    was_probe, was_launch, was_grace = (diagnostics.port_in_use,
                                        kiosk.launch, kiosk.GRACE_SECONDS)
    diagnostics.port_in_use = port_in_use
    kiosk.launch = launch
    kiosk.GRACE_SECONDS = grace
    try:
        kiosk.launch_when_ready("http://localhost:5000", 5000,
                                threading.Event(), timeout=timeout)
        deadline = time.monotonic() + timeout + 1.0
        while not opened and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        diagnostics.port_in_use = was_probe
        kiosk.launch = was_launch
        kiosk.GRACE_SECONDS = was_grace
    return opened[0] if opened else None


print("\nthe splash is on disk, because there is no server to serve it")
check("the file is there", kiosk.SPLASH.is_file(), True)
check("beside the icon it shows", (kiosk.SPLASH.parent / "icon.png").is_file(),
      True)
check("a healthy start is measured in seconds, not minutes",
      0 < kiosk.GRACE_SECONDS <= 5, True)

print("\na machine that starts normally never shows it")
quick = run(comes_up_after=0.05)
check("goes straight to the program", quick, "http://localhost:5000")

print("\na machine that is late shows it, and says how late")
slow = run(comes_up_after=5.0, grace=0.3)
check("the splash, not the program", (slow or "").startswith("file://"), True)
check("named the splash", "splash.html" in (slow or ""), True)
check("told which port to watch", "port=5000" in (slow or ""), True)
check("carrying the seconds already spent",
      float((slow or "").split("waited=")[-1]) >= 0.3, True)

print("\nwithout the splash file it waits, as it did before there was one")
was = kiosk.SPLASH
kiosk.SPLASH = Path(__file__).resolve().parent / "no-such-splash.html"
try:
    late = run(comes_up_after=0.6, grace=0.3)
    check("waited for the program rather than opening on nothing", late,
          "http://localhost:5000")
    check("and opens nothing at all if it never comes",
          run(comes_up_after=99, grace=0.3, timeout=0.5), None)
finally:
    kiosk.SPLASH = was

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
