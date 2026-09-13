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
import logging
import os
import subprocess
import threading
from pathlib import Path

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


def find_browser():
    """The first browser that can open an app window, as (path, name)."""
    if os.name != "nt":
        return None, None
    for raw, name in CANDIDATES:
        path = Path(os.path.expandvars(raw))
        if path.is_file():
            return str(path), name
    return None, None


def command(browser, url):
    """The browser as an app window on ELMER, in a profile of ELMER's own."""
    PROFILE.mkdir(parents=True, exist_ok=True)
    joiner = "&" if "?" in url else "?"
    return [browser, f"--app={url}{joiner}{OWNER_FLAG}",
            f"--user-data-dir={PROFILE}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-features=Translate", "--window-size=1280,860"]


def launch(url):
    """Open the window. Returns (process, browser name) or (None, None)."""
    browser, name = find_browser()
    if not browser:
        return None, None
    try:
        process = subprocess.Popen(command(browser, url),
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


def close(process):
    """Close the window, for a shutdown that started elsewhere - the Exit
    button, an update - so it does not stand empty over a stopped server."""
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass
