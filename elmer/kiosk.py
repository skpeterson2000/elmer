"""Kiosk mode - a full-screen browser on the machine running the server.

ELMER on a Pi with a monitor is an appliance, so --kiosk
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
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from . import paths

log = logging.getLogger("elmer")

PROFILE_DIR = paths.STATE / "kiosk-profile"

# Shown before there is a server to show it, and only on a machine that has
# missed a healthy start - see :func:`launch_when_ready`.
SPLASH = Path(__file__).resolve().parent / "static" / "splash.html"

# How long every machine spends on the splash, whatever it is actually doing
# behind it - the fast one waits this out and the slow one is covered by it, so
# the two open the same way.  The splash enforces it; this is here because the
# number belongs beside the thing it describes.
#
# Set to about the median start counted on the Pis rather than to the slowest
# of them: at the median half the fleet never waits on this at all and the
# other half is covered, where a hold set to the worst board would make every
# machine sit through the worst board's day.
HOLD_SECONDS = 4.0

# A cold card can take a long time over the first page and the splash is on
# screen the whole while, so this is patience rather than a deadline: it is
# only reached when something is wrong, and then the log says so.
WARM_TIMEOUT = 90.0

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

# ----------------------------------------------------------- the last launch
# What the most recent --kiosk launch came to, kept where the problem report,
# the doctor and the dashboard can all read it. A unit nobody can paste a log
# from still has to be able to say why its screen is not full.
LAST = paths.STATE / "kiosk-last.json"
BROWSER_LOG = paths.STATE / "kiosk-browser.log"   # the browser's own stderr, this launch
EARLY_S = 15.0          # a browser gone within this of starting failed to start
WINDOW_WAIT_S = 10.0    # after that, how long to look for its window
STDERR_TAIL = 12

NOT_FOUND = "browser not found"
NO_SCREEN = "no screen"
EXITED = "started and exited"
NOT_FULL = "running but not full screen"
FULL = "running full screen"
UNCHECKABLE = "not checkable"
FAILED = (NOT_FOUND, NO_SCREEN, EXITED, NOT_FULL)

_which = shutil.which           # the tests stand these two in
_follower = {"thread": None}


def _run_tool(args):
    """What a small X tool printed, or None if it could not say."""
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        log.debug("kiosk: %s could not run: %s", args[0], exc)
        return None
    return out.stdout if out.returncode == 0 else None


def packaging(path):
    """'snap', 'flatpak' or None: how the browser at `path` is confined.

    Both keep the browser in a box of its own, and a box is the first thing
    to suspect when a launch fails: a snap has a /tmp of its own and cannot
    open a hidden folder in home, so a profile or a page handed to it from
    either is a file it cannot see."""
    if not path:
        return None
    for where in {str(path), os.path.realpath(path)}:
        if "/snap/" in where or "snapd" in where:
            return "snap"
        if "flatpak" in where:
            return "flatpak"
    return None


def _session_kind():
    session = (os.environ.get("XDG_SESSION_TYPE") or "").lower()
    if session == "wayland" or (os.environ.get("WAYLAND_DISPLAY") and session != "x11"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return None


def fullscreen(pid, family):
    """Whether the browser's window is full screen, as (True, False or None,
    why). None is "cannot tell here", said rather than guessed: Wayland does
    not let one program read another's window, and on X it takes xprop or
    wmctrl to ask."""
    kind = _session_kind()
    if kind == "wayland":
        return None, "a Wayland session does not let another program read a window's state"
    if kind != "x11":
        return None, "no X display to ask"
    xprop, wmctrl = _which("xprop"), _which("wmctrl")
    if not (xprop or wmctrl):
        return None, "neither xprop nor wmctrl is installed to ask X"
    wanted = ("chrom",) if family == "chromium" else ("firefox", "navigator")
    windows = []                                   # (id, pid, class)
    if wmctrl:
        for line in (_run_tool([wmctrl, "-lpx"]) or "").splitlines():
            bits = line.split(None, 4)
            if len(bits) >= 4:
                windows.append((bits[0], bits[2], bits[3].lower()))
    else:
        listed = _run_tool([xprop, "-root", "_NET_CLIENT_LIST"]) or ""
        for wid in re.findall(r"0x[0-9a-fA-F]+", listed.split("#", 1)[-1]):
            props = _run_tool([xprop, "-id", wid, "_NET_WM_PID", "WM_CLASS"]) or ""
            owner = re.search(r"_NET_WM_PID\(CARDINAL\) = (\d+)", props)
            klass = re.search(r"WM_CLASS\(STRING\) = (.*)", props)
            windows.append((wid, owner.group(1) if owner else "",
                            (klass.group(1) if klass else "").lower()))
    # By the process first; a browser that hands its window to a child of
    # its own is found by its class instead.
    ours = ([w for w in windows if w[1] == str(pid)]
            or [w for w in windows if any(k in w[2] for k in wanted)])
    if not ours:
        return None, f"no window of the browser's among the {len(windows)} on the screen"
    wid = ours[0][0]
    if xprop:
        state = _run_tool([xprop, "-id", wid, "_NET_WM_STATE"])
        if state is None:
            return None, f"xprop could not read window {wid}"
        shown = state.split("=", 1)[-1].strip() if "=" in state else "no state set"
        return "_NET_WM_STATE_FULLSCREEN" in state, f"window {wid}: {shown}"
    # wmctrl alone cannot print a state; the window's size against the
    # desktop's says the same thing.
    size = next((line.split() for line in (_run_tool([wmctrl, "-lG"]) or "").splitlines()
                 if line.split()[:1] == [wid]), None)
    desk = next((line for line in (_run_tool([wmctrl, "-d"]) or "").splitlines()
                 if " * " in line), "")
    screen = re.search(r"DG: (\d+)x(\d+)", desk)
    if not (size and len(size) >= 6 and screen):
        return None, "wmctrl could not give the window's size"
    w, h, sw, sh = int(size[4]), int(size[5]), int(screen.group(1)), int(screen.group(2))
    return w >= sw and h >= sh, f"window {wid} is {w}x{h} on a {sw}x{sh} desktop"


def _record(verdict, lines, **more):
    """The launch's outcome, to the log and to LAST."""
    data = {"at": time.time(), "verdict": verdict, "lines": list(lines), **more}
    try:
        LAST.parent.mkdir(parents=True, exist_ok=True)
        LAST.write_text(json.dumps(data, indent=1), encoding="utf-8")
    except OSError as exc:
        log.warning("kiosk: could not keep the launch's outcome at %s: %s", LAST, exc)
    if verdict in FAILED:
        log.warning("kiosk: verdict: %s", verdict)
    else:
        log.info("kiosk: verdict: %s", verdict)
    return data


def last():
    """The last launch's outcome, or None if this unit has not had one."""
    try:
        return json.loads(LAST.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        log.warning("kiosk: could not read %s: %s", LAST, exc)
        return None


def failed():
    """The last launch's outcome if it failed, else None - what the
    dashboard's one line is about."""
    got = last()
    return got if got and got.get("verdict") in FAILED else None


def verdict_line():
    got = last()
    if not got:
        return "verdict       no --kiosk launch recorded on this unit"
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(got.get("at") or 0))
    return f"verdict       {got.get('verdict')} (last --kiosk launch, {when})"


def last_lines():
    """The last launch as flat lines: its verdict, what the browser said if
    it died, the full-screen reading, and the facts as they were then."""
    got = last()
    out = [verdict_line()]
    if not got:
        return out
    if got.get("exit_code") is not None:
        out.append(f"exit code     {got['exit_code']}")
    for line in got.get("stderr") or []:
        out.append(f"browser said  {line}")
    if got.get("fullscreen"):
        out.append(f"full screen   {got['fullscreen']}")
    out.extend(f"at launch     {line}" for line in got.get("lines") or [])
    return out


def _tail(path, n=STDERR_TAIL):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [line for line in text.splitlines() if line.strip()][-n:]


def _follow(process, family, lines):
    """Watch the first seconds of a launch and write down what it came to.

    A browser gone within EARLY_S never started: its exit code and the last
    of what it said go to the log. One still running is asked, where that
    can be asked, whether its window went full screen."""
    try:
        try:
            code = process.wait(timeout=EARLY_S)
        except subprocess.TimeoutExpired:
            code = None
        if code is not None:
            tail = _tail(BROWSER_LOG)
            log.warning("kiosk: the browser exited with code %s within %.0f s of starting",
                        code, EARLY_S)
            for line in tail:
                log.warning("kiosk: browser said: %s", line)
            _record(EXITED, lines, exit_code=code, stderr=tail)
            return
        deadline = time.monotonic() + WINDOW_WAIT_S
        while True:
            full, why = fullscreen(process.pid, family)
            if full is not None or not why.startswith("no window") or time.monotonic() >= deadline:
                break
            time.sleep(1.0)
        if full is None:
            log.info("kiosk: whether it is full screen cannot be checked here: %s", why)
            _record(UNCHECKABLE, lines, fullscreen=why)
        elif full:
            _record(FULL, lines, fullscreen=why)
        else:
            log.warning("kiosk: the browser is running but not full screen: %s", why)
            _record(NOT_FULL, lines, fullscreen=why)
    except Exception:                    # a watcher, not the launch: it must not take anything down
        log.exception("kiosk: following the launch failed")


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
    if os.name == "nt":
        return True            # a Windows desktop always has one
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def session_facts():
    """Everything about this machine's screen and browsers, for a report.

    A kiosk that comes up in a window instead of filling the screen leaves
    almost nothing behind to look at: the launch logged a name and a pid, and
    the command itself only at debug, which on an appliance nobody has turned
    on. So this gathers the facts that decide it - which session type is
    running, which browsers are actually on the box, whether the one chosen is
    a snap (a confined browser cannot always read a profile directory handed
    to it), and what each one calls itself - and it is put in the log at every
    launch and in the bug report, so a machine on the other end of the country
    can say what happened without anybody guessing.
    """
    facts = {
        "platform": sys.platform,
        "display": os.environ.get("DISPLAY") or "",
        "wayland_display": os.environ.get("WAYLAND_DISPLAY") or "",
        "session_type": os.environ.get("XDG_SESSION_TYPE") or "",
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP") or "",
        "have_display": have_display(),
        "found": [],
        "chosen": None,
        "family": None,
        "snap": None,
        "packaging": None,
        "version": None,
        "profile_dir": str(PROFILE_DIR),
    }
    if os.name != "nt":
        for name, family in BROWSERS:
            where = shutil.which(name)
            if where:
                facts["found"].append({"name": name, "family": family, "path": where,
                                       "snap": packaging(where) == "snap",
                                       "packaging": packaging(where)})
    path, family = find_browser()
    facts["chosen"], facts["family"] = path, family
    if path:
        facts["packaging"] = packaging(path)
        facts["snap"] = facts["packaging"] == "snap"
        # What it calls itself. Asked only where asking is harmless: Edge and
        # Chrome on Windows do not take --version and answer it by opening a
        # browser window instead, which is a diagnostic with a side effect and
        # no place in a report. On Linux, where this matters, both families
        # print a version and exit.
        if os.name != "nt":
            # A snap wrapper can take a moment, so a short leash, and a failure
            # to answer is recorded as a fact rather than raised as a fault.
            try:
                out = subprocess.run([path, "--version"], capture_output=True, text=True,
                                     timeout=10, check=False)
                facts["version"] = (out.stdout or out.stderr or "").strip()[:120]
            except (OSError, subprocess.SubprocessError) as exc:
                facts["version"] = f"could not be asked: {exc}"
        profile = PROFILE_DIR / (family or "unknown")
        facts["profile_writable"] = os.access(PROFILE_DIR.parent, os.W_OK)
        facts["command"] = " ".join(_command(path, family, "<url>", profile))
    return facts


def report_lines():
    """The same facts as flat lines, for the bug report and the doctor."""
    facts = session_facts()
    lines = [
        f"platform      {facts['platform']}",
        f"session type  {facts['session_type'] or '(not set)'}"
        f"   desktop {facts['desktop'] or '(not set)'}",
        f"DISPLAY       {facts['display'] or '(not set)'}"
        f"   WAYLAND_DISPLAY {facts['wayland_display'] or '(not set)'}",
        f"screen        {'yes' if facts['have_display'] else 'NO - kiosk stays headless'}",
    ]
    if facts["found"]:
        for got in facts["found"]:
            lines.append(f"found         {got['name']} ({got['family']})"
                         f"{' [' + got['packaging'] + ']' if got.get('packaging') else ''} at {got['path']}")
    elif os.name != "nt":
        lines.append("found         no chromium or firefox on PATH")
    lines.append(f"chosen        {facts['chosen'] or '(none)'}"
                 f"  family {facts['family'] or '-'}"
                 f"{' [' + facts['packaging'] + ' - confinement can block a profile or a page path]' if facts.get('packaging') else ''}")
    if facts.get("version"):
        lines.append(f"version       {facts['version']}")
    lines.append(f"profile dir   {facts['profile_dir']}"
                 f"{'' if facts.get('profile_writable', True) else '  NOT WRITABLE'}")
    if facts.get("command"):
        lines.append(f"command       {facts['command']}")
    return lines


def find_browser():
    """The first usable browser as (executable path, family), or (None, None)."""
    if os.name == "nt":
        # The browser ELMER's own window runs in (elmer/window.py): Edge or
        # Chrome by their installed paths, neither of which is on PATH.
        from . import window
        path, _name = window.find_browser()
        return (path, "chromium") if path else (None, None)
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
            # A browser keeps audio silent until somebody has clicked the
            # page, which is the right default for the web and the wrong one
            # for an appliance: the opening announcement is the unit saying
            # it is awake, and a unit that will only say so after it is
            # touched has not told anybody anything. Nothing here plays
            # audio the operator did not ask for - the announcement has its
            # own switch in the Station panel, and everything else is a
            # button being pressed.
            "--autoplay-policy=no-user-gesture-required",
        ]
    return [path, "--kiosk", "--new-instance", "--profile", str(profile), url]


def _window_command(path, family, url, profile):
    """A window beside ELMER's for the FCC or eCFR, with a close button; the
    entire point of it is that they can get out of it again and find ELMER
    still sitting there underneath.

    On the kiosk, a normal browser window - toolbar, back button - because
    the kiosk itself is the whole screen and this is the one window that
    is allowed not to be.  On Windows, where ELMER is an app window of its
    own, a popout in the same style: title bar, back arrow, close button,
    no tabs and no address bar - the outside site in a window of ELMER's,
    not a browser that appears from nowhere.
    """
    if family == "chromium" and os.name == "nt":
        return [
            path, f"--app={url}",
            f"--user-data-dir={profile}",
            "--no-first-run", "--no-default-browser-check",
            "--disable-session-crashed-bubble", "--noerrdialogs",
            "--disable-features=Translate",
            "--window-size=1100,820",
        ]
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
        # Its own process group (Linux; a no-op on Windows), so closing it
        # later cannot deliver a signal back to the server that started it.
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
    """Shut any external windows opened from the /away page - the ones still
    open; one the person closed themselves is gone already."""
    for process in _windows:
        close(process)
    _windows.clear()


def open_windows():
    """How many windows opened from /away are still up - for the tests and
    the log, not for anything a page shows."""
    _windows[:] = [p for p in _windows if p.poll() is None]
    return len(_windows)


def _allow_sound(profile):
    """Let the appliance make a sound before anybody has touched it.

    Firefox blocks audio until a page has been clicked, the same as
    Chromium, and says so with a preference rather than a flag. Written
    into the kiosk's own profile, which is ELMER's and nobody else's, so
    this cannot change how the operator's own browser behaves.
    """
    try:
        (profile / "user.js").write_text(
            'user_pref("media.autoplay.default", 0);\n'
            'user_pref("media.autoplay.blocking_policy", 0);\n', encoding="utf-8")
    except OSError as exc:                       # a read-only profile; not fatal
        log.debug("kiosk: could not write autoplay preferences (%s)", exc)


def launch(url):
    """Start a full-screen browser on `url`.  Returns the process, or None.

    Never raises: kiosk mode failing to start is a reason to fall back to the
    plain server with a printed URL, not to take the server down with it.
    """
    if not have_display():
        log.warning("kiosk: no DISPLAY or WAYLAND_DISPLAY - staying headless")
        lines = report_lines()
        for line in lines:
            log.warning("kiosk: %s", line)
        _record(NO_SCREEN, lines)
        return None
    path, family = find_browser()
    if not path:
        log.warning("kiosk: no chromium or firefox found - staying headless")
        lines = report_lines()
        for line in lines:
            log.warning("kiosk: %s", line)
        _record(NOT_FOUND, lines)
        return None

    profile = PROFILE_DIR / family
    profile.mkdir(parents=True, exist_ok=True)
    if family == "firefox":
        _allow_sound(profile)
    command = _command(path, family, url, profile)
    # At info, and the whole of it. A kiosk that comes up in a window rather
    # than filling the screen used to leave nothing in the log to look at,
    # because the one line that would have said why was at debug and nobody
    # runs an appliance at debug.
    lines = report_lines()
    for line in lines:
        log.info("kiosk: %s", line)
    log.info("kiosk: launching %s", " ".join(command))
    # What the browser says goes to a file of this launch's own rather than
    # nowhere: a browser that refuses its profile says why on stderr, and
    # that is the one line that explains a kiosk that never came up.
    try:
        BROWSER_LOG.parent.mkdir(parents=True, exist_ok=True)
        said = open(BROWSER_LOG, "wb")
    except OSError as exc:
        log.warning("kiosk: no file for the browser's own messages (%s): %s", BROWSER_LOG, exc)
        said = subprocess.DEVNULL
    try:
        # Its own process group, so closing the browser later cannot deliver a
        # signal back to the server that started it.
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=said,
            start_new_session=True)
    except OSError as exc:
        log.warning("kiosk: could not start %s (%s)", path, exc)
        _record(EXITED, lines, exit_code=None, stderr=[f"could not be started: {exc}"])
        return None
    finally:
        if said is not subprocess.DEVNULL:
            said.close()                 # the browser has its own copy of the handle
    log.info("kiosk: %s (pid %d) on %s", Path(path).name, process.pid, url)
    process.kiosk_started = time.monotonic()
    thread = threading.Thread(target=_follow, args=(process, family, lines),
                              name="kiosk-follow", daemon=True)
    _follower["thread"] = thread
    thread.start()
    return process


class Adopted:
    """A kiosk browser inherited from the process ELMER restarted out of.

    os.execv replaces the program but not the process: the pid stays, and so
    do its children.  The browser started before an update is therefore still
    ours to wait on and to close - only the Popen object went with the old
    image.  This puts back just enough of one for :func:`close` and
    :func:`watch` to carry on without knowing the difference.
    """

    def __init__(self, pid):
        self.pid = pid
        self._status = None

    def poll(self):
        if self._status is not None:
            return self._status
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:      # reaped elsewhere, or never ours
            self._status = -1
            return self._status
        except OSError:
            return None
        if pid == 0:
            return None
        self._status = status
        return status

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            status = self.poll()
            if status is not None:
                return status
            if deadline is not None and time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(f"pid {self.pid}", timeout)
            time.sleep(0.1)

    def _signal(self, sig):
        try:
            os.kill(self.pid, sig)
        except (OSError, ProcessLookupError):
            self._status = -1

    def terminate(self):
        self._signal(signal.SIGTERM)

    def kill(self):
        self._signal(signal.SIGKILL)


def adopt(pid):
    """Take back the kiosk browser after a restart, or None if it is gone."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        log.info("kiosk: browser %s did not survive the restart", pid)
        return None
    log.info("kiosk: adopted the browser left running by the restart (pid %d)", pid)
    return Adopted(pid)


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
        began = getattr(process, "kiosk_started", None)
        if began is not None and time.monotonic() - began < EARLY_S:
            # Not somebody closing the kiosk - a browser that never came up.
            # Stopping would leave a dark unit nobody can reach to find out
            # why; serving on lets another device, or the dashboard once a
            # browser is opened by hand, say what happened.
            log.warning("kiosk: the browser did not stay up - the server keeps running "
                        "so the failure can be seen and reported")
            return
        log.info("kiosk: browser closed - stopping the server")
        os.kill(os.getpid(), signal.SIGINT)

    thread = threading.Thread(target=wait, name="kiosk-watch", daemon=True)
    thread.start()
    return thread




def launch_when_ready(url, port, quitting, timeout=20.0):
    """Open the browser now, on the splash, and let it find the server.

    Waiting for the socket and only then starting the browser is the safe
    order - chromium shows its own error page if it arrives first, and on an
    appliance nobody is there to press reload. The cost is an empty screen for
    as long as the first render takes, which on a cold card is several seconds
    while a megabyte of pools comes off it.

    So the browser opens immediately on a splash held on disk, and that page
    watches the port and goes to the program the moment it answers - never
    sooner than :data:`HOLD_SECONDS`, so a machine that was ready in a quarter
    of a second opens exactly the way a slow one does. Sameness across the
    fleet is the point: a start that looks identical every time is what a
    solid one looks like, and the working is not the operator's problem.

    It is still worth knowing which card is slow, so the fact is taken and put
    where it belongs - a line in the log, timed by the thread below, rather
    than a number on a screen somebody is trying to study in front of.

    Where the splash is missing this falls back to the old wait-then-open
    rather than guessing, since a browser opened on nothing is worse than a
    late one.
    """
    from .diagnostics import port_in_use

    def started(process):
        if process is not None:
            holder.append(process)
            watch(process, quitting)

    def fetch_home():
        """Ask for a real page, and wait for it the way the operator will.

        The socket is bound long before a page can be built - the pools come
        off the card on the first request, not at import - so connecting to
        the port measures nothing and reports a tenth of a second on the
        slowest board there is.  One honest request costs the same time
        somebody was going to spend anyway, and spends it before the browser
        arrives rather than after, so the page the splash hands over to is
        already built.
        """
        began = time.monotonic()
        deadline = began + timeout
        while time.monotonic() < deadline:
            if port_in_use(port):
                break
            time.sleep(0.1)
        else:
            log.warning("kiosk: server did not come up within %.0fs", timeout)
            return None
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{port}/",
                headers={"User-Agent": "ELMER/kiosk (warming the first page)"})
            with urllib.request.urlopen(request, timeout=WARM_TIMEOUT) as page:
                page.read(2048)
        except Exception as exc:
            log.warning("kiosk: the first page did not come: %s", exc)
            return None
        return time.monotonic() - began

    def time_the_start():
        """Below the waterline: how long this machine actually took.

        The number itself is written down by the server that served the page -
        see :mod:`elmer.startup` - so that the doctor can carry it to whoever
        asks.  This says it on the console too, where somebody watching a
        start is already looking.
        """
        took = fetch_home()
        if took is not None:
            log.info("kiosk: first page in %.1fs", took)

    def wait_then_launch():
        """With no splash to hold the screen, wait for a page and then open.

        The same honest wait as above: opening on a bound socket would put
        chromium in front of a page that is still being built, which is the
        empty screen this was all meant to stop.
        """
        took = fetch_home()
        if took is not None:
            log.info("kiosk: first page in %.1fs", took)
            started(launch(url))

    holder = []
    watcher = wait_then_launch
    if SPLASH.is_file():
        # From the disk rather than through the server - there is no server
        # yet, which is the whole point.
        started(launch(SPLASH.as_uri() + "?port=" + str(port)))
        watcher = time_the_start
    thread = threading.Thread(target=watcher, name="kiosk-launch", daemon=True)
    thread.start()
    return holder
