"""Kiosk mode - a full-screen browser on the machine running the server.

ELMER on a Pi with a monitor is an appliance rather than a website, so --kiosk
brings up a full-screen browser pointed at the local server and puts an Exit
button in the top bar.  The whole thing can then be started and stopped without
touching a terminal.

Chromium is preferred over Firefox: its kiosk mode is the better behaved of the
two under Wayland, which is what Raspberry Pi OS runs now.  Either browser gets
a throwaway profile of its own, because launched against the normal profile a
browser that is already open would just add a tab to the existing window and
never go full screen at all.
"""
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

log = logging.getLogger("elmer")

PROFILE_DIR = Path(__file__).resolve().parents[1] / "data" / "kiosk-profile"

# Chromium first - see the module docstring.  Each entry is the executable name
# and the flags that put it full screen on a throwaway profile.
BROWSERS = (
    ("chromium", "chromium"),
    ("chromium-browser", "chromium"),
    ("google-chrome", "chromium"),
    ("firefox", "firefox"),
    ("firefox-esr", "firefox"),
)


def have_display():
    """True if there is a screen to put a window on."""
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def find_browser():
    """The first usable browser as (executable path, family), or (None, None)."""
    for name, family in BROWSERS:
        path = shutil.which(name)
        if path:
            return path, family
    return None, None


def _command(path, family, url, profile):
    if family == "chromium":
        return [
            path, "--kiosk", url,
            # Its own profile, so an already-open Chromium does not swallow
            # this launch and turn it into a tab in the existing window.
            f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check",
            # An appliance has nobody to dismiss a restore-session bubble or an
            # infobar, and either one would sit on top of the page forever.
            "--disable-session-crashed-bubble", "--disable-infobars",
            "--noerrdialogs", "--disable-translate",
            # Otherwise Chromium asks the GNOME login keyring to unlock, which
            # on a fresh profile means a password prompt sitting on top of the
            # kiosk with no way past it.  ELMER never asks the browser to save
            # a password, so its own basic store has nothing to protect.
            "--password-store=basic",
        ]
    return [path, "--kiosk", "--new-instance", "--profile", str(profile), url]


def launch(url):
    """Start a full-screen browser on `url`.  Returns the process, or None.

    Never raises: kiosk mode failing to start is a reason to fall back to the
    plain server with a printed URL, not to take the server down with it.
    """
    if not have_display():
        log.warning("kiosk: no DISPLAY or WAYLAND_DISPLAY - staying headless")
        return None
    path, family = find_browser()
    if not path:
        log.warning("kiosk: no chromium or firefox found - staying headless")
        return None

    profile = PROFILE_DIR / family
    profile.mkdir(parents=True, exist_ok=True)
    command = _command(path, family, url, profile)
    log.debug("kiosk: %s", " ".join(command))
    try:
        # Its own process group, so closing the browser later cannot deliver a
        # signal back to the server that started it.
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
    except OSError as exc:
        log.warning("kiosk: could not start %s (%s)", path, exc)
        return None
    log.info("kiosk: %s (pid %d) on %s", Path(path).name, process.pid, url)
    return process


def close(process):
    """Shut the kiosk browser down, firmly if it will not go politely."""
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    except OSError:
        pass


def watch(process, quitting):
    """Stop the server when the kiosk browser goes away.

    Without this, closing the window would leave the server running with no way
    left to reach it on a machine that has no terminal open.  `quitting` is set
    by our own shutdown path, so the Exit button does not trip this as well.
    """
    def wait():
        try:
            process.wait()
        except OSError:
            return
        if quitting.is_set():
            return
        log.info("kiosk: browser closed - stopping the server")
        os.kill(os.getpid(), signal.SIGINT)

    thread = threading.Thread(target=wait, name="kiosk-watch", daemon=True)
    thread.start()
    return thread


def launch_when_ready(url, port, quitting, timeout=20.0):
    """Wait for the server to answer, then bring the browser up on it.

    Chromium shows its own error page if it arrives before the socket is
    listening, and on an appliance nobody is there to press reload.
    """
    from .diagnostics import port_in_use

    def run():
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if port_in_use(port):
                break
            time.sleep(0.1)
        else:
            log.warning("kiosk: server did not come up within %.0fs", timeout)
            return
        process = launch(url)
        if process is not None:
            holder.append(process)
            watch(process, quitting)

    holder = []
    thread = threading.Thread(target=run, name="kiosk-launch", daemon=True)
    thread.start()
    return holder
