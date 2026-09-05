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

A full-screen browser has no back button, no tabs and no address bar, so a link
to somewhere outside ELMER is a one-way trip: the operator lands on the FCC site
with no way back to the study session and no way to stop the program.  Off-site
links therefore go through ELMER's own /away page, and :func:`open_window` puts
the external site in an ordinary window - one with a close button - leaving the
kiosk window still on ELMER underneath.
"""
import logging
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

log = logging.getLogger("elmer")

PROFILE_DIR = Path(__file__).resolve().parents[1] / "data" / "kiosk-profile"

# Ordinary windows opened for an off-site link, kept so they can be shut when
# ELMER stops rather than left orphaned on the screen.
_windows = []

# Chromium first - see the module docstring.  Each entry is the executable name
# and the flags that put it full screen on a throwaway profile.
BROWSERS = (
    ("chromium", "chromium"),
    ("chromium-browser", "chromium"),
    ("google-chrome", "chromium"),
    ("firefox", "firefox"),
    ("firefox-esr", "firefox"),
)


def serving_elsewhere(port):
    """The PID of another ELMER already serving on this port, or None.

    Only our own processes count: the point is to offer to stand aside for
    something we started, not to interfere with whatever else may be listening.
    """
    import getpass
    try:
        out = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True,
                             timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    pids = set()
    for line in out.splitlines():
        if f":{port} " not in line:
            continue
        for match in re.findall(r"pid=(\d+)", line):
            pids.add(int(match))
    me = os.getpid()
    for pid in pids:
        if pid == me:
            continue
        try:
            cmdline = open(f"/proc/{pid}/cmdline", "rb").read().decode(
                "utf-8", "replace").replace("\0", " ")
            owner = os.stat(f"/proc/{pid}").st_uid
        except OSError:
            continue
        if owner == os.getuid() and "elmer.py" in cmdline:
            return pid
    return None


def stop_other(pid, port, timeout=10.0):
    """Ask another ELMER to stop, and wait for the port to come free.

    Used only when the operator has said to, and only for one of our own
    processes - :func:`serving_elsewhere` will not return anybody else's.
    """
    import socket
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.25)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                log.info("stopped the ELMER already on port %s (pid %s)", port, pid)
                return True
    try:                                       # it did not go quietly
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
    except (OSError, ProcessLookupError):
        pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def ask(question, options, timeout=60):
    """Put a question to a desktop user who has no terminal.

    Returns the chosen option, or None when there is no way to ask. A launcher
    entry runs with Terminal=false, so anything printed to stdout is printed
    into the void - which is how a deliberate fallback came to look like a bug.
    """
    zenity = shutil.which("zenity")
    if not zenity or not have_display():
        return None
    args = [zenity, "--question", "--title=ELMER", "--no-wrap",
            f"--text={question}",
            f"--ok-label={options[0]}", f"--cancel-label={options[1]}"]
    try:
        done = subprocess.run(args, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return options[0] if done.returncode == 0 else options[1]


def tell(message):
    """Say something to a desktop user with no terminal. Best effort."""
    zenity = shutil.which("zenity")
    if not zenity or not have_display():
        return False
    try:
        subprocess.Popen([zenity, "--info", "--title=ELMER", "--no-wrap",
                          f"--text={message}"])
        return True
    except (OSError, subprocess.SubprocessError):
        return False


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


def _window_command(path, family, url, profile):
    """A normal browser window: toolbar, back button, close button.

    Deliberately *not* kiosk mode.  This is the window that takes somebody to
    the FCC or eCFR, and the entire point of it is that they can get out of it
    again and find ELMER still sitting there underneath.
    """
    if family == "chromium":
        return [
            path, "--new-window", url,
            # A profile of its own again, and a different one from the kiosk
            # window's: sharing it would hand the URL to the running kiosk
            # instance, which would open it full screen with no way back.
            f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-session-crashed-bubble", "--noerrdialogs",
            "--disable-translate", "--password-store=basic",
            "--window-size=1200,860",
        ]
    return [path, "--new-instance", "--profile", str(profile), url]


def open_window(url):
    """Open `url` in an ordinary window beside the kiosk.  True if it started.

    Used by the /away page.  Never raises: an external link failing to open is
    a disappointment, not a reason to take the study session down.
    """
    if not have_display():
        return False
    path, family = find_browser()
    if not path:
        return False
    profile = PROFILE_DIR / f"{family}-web"
    profile.mkdir(parents=True, exist_ok=True)
    command = _window_command(path, family, url, profile)
    log.debug("kiosk: external window %s", " ".join(command))
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True)
    except OSError as exc:
        log.warning("kiosk: could not open a window on %s (%s)", url, exc)
        return False
    _windows[:] = [p for p in _windows if p.poll() is None]
    _windows.append(process)
    log.info("kiosk: opened %s in a separate window (pid %d)", url, process.pid)
    return True


def close_windows():
    """Shut any external windows opened from the /away page."""
    for process in _windows:
        close(process)
    _windows.clear()


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
