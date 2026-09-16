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

# How the window opens: the unit's setting, kept with the others under the
# key below. "as-left" is the default - the profile restores the bounds the
# person left the window at, and ELMER says nothing about size - with one
# exception: a machine with no bounds saved yet gets it maximised, which is
# the offer a first launch makes. "maximized" and "WIDTHxHEIGHT" are the
# person's own choice and are applied every launch, saved bounds or not.
START_SETTING = "window_start"
# Full screen by default: the whole display and nothing of the browser's
# on it - no title bar, no menu button, nothing that says what is drawing
# the screen. Windows has no kiosk mode and does not need one for this;
# full screen is what an application takes. The other choices are there
# for somebody who wants a window among windows.
START_DEFAULT = "fullscreen"
STARTS = ("fullscreen", "as-left", "maximized")


def start_choice(value):
    """A setting as typed, made valid: one of STARTS or WIDTHxHEIGHT."""
    text = str(value or "").strip().lower().replace(" ", "")
    if text in STARTS:
        return text
    w, sep, h = text.partition("x")
    if sep and w.isdigit() and h.isdigit() and 400 <= int(w) <= 8000 and 300 <= int(h) <= 8000:
        return f"{int(w)}x{int(h)}"
    return START_DEFAULT


def remembered_bounds():
    """Whether the profile has a window placement saved - a second launch."""
    try:
        prefs = json.loads((PROFILE / "Default" / "Preferences").read_text(encoding="utf-8"))
        return bool(prefs.get("browser", {}).get("app_window_placement"))
    except (OSError, ValueError, AttributeError):
        return False


def find_browser():
    """The first browser that can open an app window, as (path, name)."""
    if os.name != "nt":
        return None, None
    for raw, name in CANDIDATES:
        path = Path(os.path.expandvars(raw))
        if path.is_file():
            return str(path), name
    return None, None


def command(browser, url, start=START_DEFAULT, remembered=None):
    """The browser as an app window on ELMER, in a profile of ELMER's own.

    The profile remembers the window's last bounds - which screen, how big
    - and the zoom set with Ctrl and the wheel, and restores both. What
    ELMER adds about size follows `start` (see START_SETTING): nothing, for
    "as-left" with bounds saved; maximised for a first launch or by choice;
    a fixed size by choice. A size given every launch regardless was what
    made the window come back where ELMER put it, not where it was left.
    """
    PROFILE.mkdir(parents=True, exist_ok=True)
    joiner = "&" if "?" in url else "?"
    cmd = [browser, f"--app={url}{joiner}{OWNER_FLAG}",
           f"--user-data-dir={PROFILE}",
           "--no-first-run", "--no-default-browser-check",
           "--disable-features=Translate"]
    start = start_choice(start)
    remembered = remembered_bounds() if remembered is None else remembered
    if start == "fullscreen":
        cmd.append("--start-fullscreen")
    elif start == "maximized" or (start == "as-left" and not remembered):
        cmd.append("--start-maximized")
    elif start != "as-left":
        cmd.append("--window-size=" + start.replace("x", ","))
    return cmd


def launch(url, start=START_DEFAULT):
    """Open the window. Returns (process, browser name) or (None, None)."""
    browser, name = find_browser()
    if not browser:
        return None, None
    try:
        process = subprocess.Popen(command(browser, url, start),
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
    button, an update - so it does not stand empty over a stopped server.

    Two ways, because Edge on Windows does not promise that the process
    launched is the process holding the window: the browser re-launches
    itself and the first pid can be gone while the window stands. So the
    launched process is ended with its whole tree, and then every browser
    process running on ELMER's own profile directory - which nothing but
    this window ever uses - is ended by name. An application closes when it
    is told to close; it does not leave a page up saying so."""
    if process is not None and process.poll() is None:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            else:
                process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass
    close_by_profile()


def close_by_profile():
    """End any browser process on ELMER's window profile, whatever its pid.
    Windows only; elsewhere the launched process is the window."""
    if os.name != "nt":
        return
    marker = str(PROFILE).replace("'", "''")
    script = ("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*--user-data-dir=" + marker +
              "*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        log.debug("window: could not close by profile: %s", exc)
