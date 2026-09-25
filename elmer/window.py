"""A window of ELMER's own, on Windows - and the server stops when it closes.

The kiosk on a Pi owns its browser: it starts it, and when the process ends
the server ends. --open on Windows used to hand the URL to whatever browser
is the default and get nothing back - a tab in somebody's existing Edge,
with no way to know when it closed - so the server ran on in a console
nobody was looking at.

Edge is on every Windows machine and Chrome on most, and both can open a
URL as an *app window*: no tabs, no address bar, the page and its title,
which is what a program's window looks like. Given a profile folder of its
own, that window is a process of its own - without one, a new window joins
the Edge already running and the launch returns at once, which is the tab
problem again. So: its own profile under ELMER's data, its own process,
and a thread that waits on it. When the window closes, the server stops
the way the Exit button stops it.

What this cannot do is warn at the moment of closing: by then the window
is gone. The warning is the page's, ahead of time - see owner.js - which
knows it is this window, asks how many people are on the unit, and says so
while they are. Where neither browser is found, the URL goes to the
default browser as a tab and the console says the window will not stop
the server; that is the truth of it, and better than pretending.
"""
import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from urllib.parse import quote

from . import paths

log = logging.getLogger("elmer")

# Where each family keeps itself on a Windows machine, in the order to try:
# Edge is on every machine, so it is the one that is always there.
CANDIDATES = [
    (r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe", "Edge"),
    (r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe", "Edge"),
    (r"%ProgramFiles%\Google\Chrome\Application\chrome.exe", "Chrome"),
    (r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe", "Chrome"),
    (r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe", "Chrome"),
]
PROFILE = paths.STATE / "window-profile"
OWNER_FLAG = "elmer_window=1"

# The same page the kiosk opens on, and for the same reason. On Windows the
# window used to be held back until the server answered - up to a minute of
# nothing at all on the screen, and then a window - because a browser pointed
# at a port that is not listening yet shows its own error page. The splash is
# the other answer to that: it is a file on disk, so it is on screen at once,
# and it watches the port itself and goes to the program when it answers. The
# Pi has opened this way for a long while; the window on Windows should not
# have been the one place that still stared at nothing.
SPLASH = Path(__file__).resolve().parent / "static" / "splash.html"

# How the window opens: the unit's setting, kept with the others under the
# key below. ELMER opens full screen, and that is the default, because that
# is what a program does - it opens at the size it is meant to be read at,
# and it does not need to be told twice. The default used to be "as-left",
# which handed the question to the browser's memory of its own bounds; that
# is a browser's habit showing through something that is not supposed to
# look like a browser, and on a profile whose browser had been killed rather
# than closed it meant opening small, every single time. "as-left" and a
# fixed WIDTHxHEIGHT are still here for somebody who wants them.
START_SETTING = "window_start"
START_DEFAULT = "maximized"
STARTS = ("as-left", "maximized")


def start_choice(value):
    """A setting as typed, made valid: one of STARTS or WIDTHxHEIGHT."""
    text = str(value or "").strip().lower().replace(" ", "")
    if text in STARTS:
        return text
    w, sep, h = text.partition("x")
    if sep and w.isdigit() and h.isdigit() and 400 <= int(w) <= 8000 and 300 <= int(h) <= 8000:
        return f"{int(w)}x{int(h)}"
    return START_DEFAULT


def remembered_placement():
    """The bounds the browser saved for ELMER's window, or None.

    They live under browser.app_window_placement, which is not a placement
    but a shelf of them, one per app the profile has opened - ELMER's is
    the only one here. The key beside it, browser.window_placement, belongs
    to an ordinary window with tabs and has nothing to say about this one;
    reading that one by mistake is what hid this bug.
    """
    try:
        prefs = json.loads((PROFILE / "Default" / "Preferences").read_text(encoding="utf-8"))
        shelf = prefs.get("browser", {}).get("app_window_placement") or {}
        for placement in shelf.values():
            if isinstance(placement, dict) and "right" in placement:
                return placement
    except (OSError, ValueError, AttributeError) as exc:
        log.debug("window: no saved placement to read: %s", exc)
    return None


def remembered_bounds():
    """Whether the profile has a window placement saved - a second launch."""
    return remembered_placement() is not None


def left_maximized():
    """Whether the window was maximized the last time it was closed."""
    placement = remembered_placement()
    return bool(placement and placement.get("maximized"))


def find_browser():
    """The first browser that can open an app window, as (path, name)."""
    if os.name != "nt":
        return None, None
    for raw, name in CANDIDATES:
        path = Path(os.path.expandvars(raw))
        if path.is_file():
            return str(path), name
    return None, None


def marked(url):
    """ELMER's URL with the mark that says this is ELMER's own window.

    The page reads it and grows an Exit button - see owner.js - so it has to
    survive anything the window is opened through, the splash included.
    """
    return f"{url}{'&' if '?' in url else '?'}{OWNER_FLAG}"


def opening_page(url, port=None):
    """What the window opens on: the splash where there is one, else ELMER.

    The splash carries the real destination in `to` rather than rebuilding
    it, so the mark above goes through unharmed.
    """
    page = marked(url)
    if port and SPLASH.is_file():
        return f"{SPLASH.as_uri()}?port={int(port)}&to={quote(page, safe='')}"
    return page


def command(browser, url, start=START_DEFAULT, remembered=None, maximized=None, port=None):
    """The browser as an app window on ELMER, in a profile of ELMER's own.

    The profile remembers the zoom set with Ctrl and the wheel, and its own
    idea of the window's last bounds. What ELMER says about size follows
    `start` (see START_SETTING): full screen, which is the default and is
    said plainly every launch; a fixed size by choice; or, for "as-left",
    nothing at all - except where the profile says the window was left
    maximized, which is worth repeating out loud, because a browser does
    not reliably restore that for itself.
    """
    PROFILE.mkdir(parents=True, exist_ok=True)
    cmd = [browser, f"--app={opening_page(url, port)}",
           f"--user-data-dir={PROFILE}",
           "--no-first-run", "--no-default-browser-check",
           "--disable-features=Translate"]
    start = start_choice(start)
    if start == "maximized":
        cmd.append("--start-maximized")
    elif start == "as-left":
        # The only answer that asks the profile anything, so it is the only
        # one that goes and reads it.
        remembered = remembered_bounds() if remembered is None else remembered
        maximized = left_maximized() if maximized is None else maximized
        if not remembered or maximized:
            cmd.append("--start-maximized")
    else:
        cmd.append("--window-size=" + start.replace("x", ","))
    return cmd


def launch(url, start=START_DEFAULT, port=None):
    """Open the window. Returns (process, browser name) or (None, None).

    Given `port`, the window opens now, on the splash, and finds the server
    for itself; without it the caller is expected to have waited already.
    """
    browser, name = find_browser()
    if not browser:
        return None, None
    try:
        process = subprocess.Popen(command(browser, url, start, port=port),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        log.warning("window: could not start %s: %s", name, exc)
        return None, None
    log.info("window: %s opened on %s (pid %s)", name, url, process.pid)
    return process, name


def watch(process, quitting, port):
    """Stop the server when the window goes away - unless the server is
    already on its way out, which is what `quitting` says."""
    from . import host

    def wait():
        try:
            process.wait()
        except OSError:
            return
        if quitting.is_set():
            return
        log.info("window: closed - stopping the server")
        print("\n  The ELMER window was closed - stopping.\n", flush=True)
        host.stop_main_thread(port)

    thread = threading.Thread(target=wait, name="window-watch", daemon=True)
    thread.start()
    return thread


def ask_to_close(process):
    """Ask the window to close the way its X does. True if it was asked.

    Popen.terminate() on Windows is TerminateProcess: the browser stops
    mid-breath, and everything it had not yet written to its profile - the
    size the window was at, the zoom, the note that it exited cleanly - is
    lost. Every shutdown through the Exit button did that, and measuring it
    was plain: end the window with terminate() and a window maximized three
    seconds earlier is remembered as small; ask it to close and the size is
    kept. taskkill without /F posts the close message instead, which is a
    person clicking the X. Without /T, too: /T waits on a tree of renderer
    processes that have already gone, and takes fifteen seconds to decide
    they are not coming back.
    """
    if os.name != "nt":
        return False
    try:
        asked = subprocess.run(["taskkill", "/PID", str(process.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10, check=False)
        # It refuses for anything with no window to close - a console
        # program, say - and then there is nothing to wait for.
        return asked.returncode == 0
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("window: could not ask the window to close: %s", exc)
        return False


def close(process):
    """Close the window, for a shutdown that started elsewhere - the Exit
    button, an update - so it does not stand empty over a stopped server."""
    if process is None or process.poll() is not None:
        return
    if ask_to_close(process):
        try:
            process.wait(timeout=8)
            return
        except subprocess.TimeoutExpired:
            log.warning("window: did not close when asked - ending it (pid %s)", process.pid)
        except OSError:
            return
    try:
        process.terminate()
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass
