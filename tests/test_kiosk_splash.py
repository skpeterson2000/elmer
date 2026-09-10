#!/usr/bin/env python3
"""What the kiosk shows while the server is still coming up.

    python3 tests/test_kiosk_splash.py

Every machine opens the same way: the splash, a short hold, then the program.
The fast board waits out the hold it did not need and the slow board is
covered by it, and neither of them shows the operator the difference - a start
that looks identical every time is what a solid one looks like.

The difference is still worth having, so it is taken and written to the log
instead of the screen, and that is the half of this most easily lost: a later
change that quietly drops the timing line would leave nothing anywhere saying
which card is slow.  So it is checked here.
"""
import logging
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import diagnostics, kiosk  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


class Heard(logging.Handler):
    """Everything the module said, so the log line can be asked for."""

    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class Page:
    """A page, served the moment it is asked for."""

    def read(self, _n=None):
        return b"<html>ELMER</html>"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def run(comes_up_after, timeout=2.0, page_takes=0.0, page_fails=False):
    """Start the launcher against a port that answers after so many seconds.

    `page_takes` is the part the socket does not know about - the pools coming
    off the card on the first request - which is the whole reason the launcher
    asks for a page instead of connecting to a port.

    Returns the URL the browser was opened on - or None - and the log.
    """
    began = time.monotonic()
    opened = []

    def port_in_use(_port):
        return time.monotonic() - began >= comes_up_after

    def launch(url):
        opened.append(url)
        return None                       # nothing to watch or shut down

    def urlopen(_request, timeout=None):
        if page_fails:
            raise OSError("nothing there")
        time.sleep(page_takes)
        return Page()

    heard = Heard()
    log = logging.getLogger("elmer")
    was_probe, was_launch = diagnostics.port_in_use, kiosk.launch
    was_open = kiosk.urllib.request.urlopen
    diagnostics.port_in_use = port_in_use
    kiosk.launch = launch
    kiosk.urllib.request.urlopen = urlopen
    log.addHandler(heard)
    was_level = log.level
    log.setLevel(logging.INFO)
    try:
        kiosk.launch_when_ready("http://localhost:5000", 5000,
                                threading.Event(), timeout=timeout)
        # Long enough for the watching thread to finish whatever it will do -
        # including the page, which is the part that takes the time.
        deadline = (time.monotonic() + min(comes_up_after, timeout)
                    + page_takes + 1.0)
        while time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        diagnostics.port_in_use = was_probe
        kiosk.launch = was_launch
        kiosk.urllib.request.urlopen = was_open
        log.removeHandler(heard)
        log.setLevel(was_level)
    return (opened[0] if opened else None), heard.lines


def timed(lines):
    """The seconds out of the log line, or None if nobody wrote one."""
    for line in lines:
        found = re.search(r"first page in ([\d.]+)s", line)
        if found:
            return float(found.group(1))
    return None


print("\nthe splash is on disk, because there is no server to serve it")
check("the file is there", kiosk.SPLASH.is_file(), True)
# Named rather than assumed: the page paints from the disk, so whatever it
# asks for has to be sitting beside it or the first thing anybody sees on a
# cold start is a broken image.
shows = re.search(r"icon'\)\.src = '([^']+)'", kiosk.SPLASH.read_text())
check("it names a picture", bool(shows), True)
check("which is beside it",
      (kiosk.SPLASH.parent / shows.group(1)).is_file() if shows else None, True)

print("\nthe hold is the same number in both places it is written")
held = re.search(r"HOLD_MS = (\d+)", kiosk.SPLASH.read_text())
check("the page states one", bool(held), True)
check("and it matches kiosk.HOLD_SECONDS",
      int(held.group(1)) if held else None, int(kiosk.HOLD_SECONDS * 1000))
# Bounded at both ends, because both ends are mistakes: under a second the
# fast board flashes the splash and the slow one dwells on it, which is the
# seam this exists to hide, and past the slowest real start it is no longer
# covering a wait but adding one.
check("long enough to read as a start, short enough not to be a wait",
      1.0 <= kiosk.HOLD_SECONDS <= 8.0, True)

print("\nevery machine opens on it - the quick one included")
quick, said = run(comes_up_after=0.05)
check("the splash", "splash.html" in (quick or ""), True)
check("from the disk", (quick or "").startswith("file://"), True)
check("told which port to watch", "port=5000" in (quick or ""), True)
check("and the wait it did not need is in the log, not on the screen",
      timed(said) is not None and timed(said) < 1.0, True)

print("\nso does the slow one, and the log carries what the screen does not")
slow, said = run(comes_up_after=1.2)
check("the same splash", "splash.html" in (slow or ""), True)
check("the log knows this board was slower", (timed(said) or 0) >= 1.0, True)

print("\nthe number is the page, not the port - which is the whole of the fix")
# A board where the socket is instant and the first page is not: timing the
# port would call this a tenth of a second and be wrong by a factor of ten.
_, said = run(comes_up_after=0.05, page_takes=1.0, timeout=3.0)
check("timed what the operator waits for", (timed(said) or 0) >= 1.0, True)
check("not what the socket did", (timed(said) or 9) < 0.5, False)

print("\na port that is open with nothing behind it is not a start")
was = kiosk.SPLASH
kiosk.SPLASH = Path(__file__).resolve().parent / "no-such-splash.html"
try:
    stuck, said = run(comes_up_after=0.05, page_fails=True, timeout=2.0)
    check("opened nothing on a page that never came", stuck, None)
    check("and said why", any("first page did not come" in line
                              for line in said), True)
finally:
    kiosk.SPLASH = was

print("\na server that never comes up is said out loud")
never, said = run(comes_up_after=99, timeout=0.4)
check("still opened on the splash", "splash.html" in (never or ""), True)
check("and warned", any("did not come up" in line for line in said), True)

print("\nwithout the splash file it waits, as it did before there was one")
was = kiosk.SPLASH
kiosk.SPLASH = Path(__file__).resolve().parent / "no-such-splash.html"
try:
    late, said = run(comes_up_after=0.5)
    check("waited for the program rather than opening on nothing", late,
          "http://localhost:5000")
    check("and timed it just the same", (timed(said) or 0) >= 0.4, True)
    gone, _ = run(comes_up_after=99, timeout=0.4)
    check("opens nothing at all if it never comes", gone, None)
finally:
    kiosk.SPLASH = was

print()
if FAILS:
    print(f"{len(FAILS)} failed: " + ", ".join(FAILS))
    sys.exit(1)
print("all good")
