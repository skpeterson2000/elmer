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
SAMPLE_S = 1.0          # how often the window's state is read until EARLY_S
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


# ------------------------------------------------- what the screen really holds
# A verdict alone did not find the fault. "Running but not full screen" came
# back from a unit with the window that was read, and nothing to say whether
# it was the kiosk's own window or some other browser's on the same desktop,
# whether the window manager can make a window full screen at all, or
# whether the window went full screen and was then taken out of it. Nobody
# can be asked for those at the other end of the country, so the unit writes
# them down itself, at every launch: the evidence below travels with the
# verdict into the log, the problem report and the field report.

# Compositors and window managers, by the process name they run under - the
# one fact about the desktop that Wayland will still tell another program.
DESKTOPS = ("gnome-shell", "mutter", "kwin_x11", "kwin_wayland", "xfwm4", "marco",
            "muffin", "openbox", "labwc", "wayfire", "sway", "Hyprland", "weston",
            "mutter-x11-fram", "cinnamon", "budgie-wm", "i3", "awesome", "fluxbox",
            "xfce4-session", "lxsession", "matchbox-window")
TREE_MOST = 12          # processes of the browser's written down
WINDOWS_MOST = 16       # windows on the screen written down


def _processes():
    """Every process as {pid: (ppid, name, command line)}, from /proc; {}
    where there is no /proc to read."""
    out = {}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return out
    for entry in entries:
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", "rb") as fh:
                stat = fh.read().decode(errors="replace")
            with open(f"/proc/{entry}/cmdline", "rb") as fh:
                cmd = fh.read().replace(b"\0", b" ").decode(errors="replace").strip()
        except OSError:              # gone between the listing and the read
            continue
        # The name is in parentheses and may hold spaces; the parent is the
        # second field after the closing one.
        name = stat[stat.find("(") + 1:stat.rfind(")")]
        fields = stat[stat.rfind(")") + 1:].split()
        try:
            out[int(entry)] = (int(fields[1]), name, cmd)
        except (IndexError, ValueError):
            continue
    return out


def _tree(pid, procs=None):
    """The launched process and every process under it, as {pid: (name, cmd)}.

    A snap or a wrapper script can hand the browser's window to a process of
    its own, and the window is only the kiosk's if its owner is in here."""
    procs = _processes() if procs is None else procs
    tree, todo = {}, [int(pid)]
    while todo:
        p = todo.pop()
        if p in tree or p not in procs:
            continue
        tree[p] = procs[p][1:]
        todo.extend(c for c, row in procs.items() if row[0] == p)
    return tree


def _desktop_running(procs=None):
    procs = _processes() if procs is None else procs
    names = {row[1] for row in procs.values()}
    return [d for d in DESKTOPS if d in names]


def _screen_windows(xprop, wmctrl):
    """Every managed window as (id, owner pid, class)."""
    windows = []
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
    return windows


def _state(xprop, wid):
    """A window's _NET_WM_STATE as a short string, or None if unreadable."""
    state = _run_tool([xprop, "-id", wid, "_NET_WM_STATE"]) if xprop else None
    if state is None:
        return None
    return state.split("=", 1)[-1].strip() if "=" in state else "no state set"


def _x_evidence(xprop, wmctrl, windows, owners, wanted, chosen, how):
    """The X screen as lines: the window manager, the screen, and each window."""
    lines = []
    wm = "unknown"
    if xprop:
        check = _run_tool([xprop, "-root", "_NET_SUPPORTING_WM_CHECK"]) or ""
        found = re.search(r"0x[0-9a-fA-F]+", check)
        if found:
            named = _run_tool([xprop, "-id", found.group(0), "_NET_WM_NAME"]) or ""
            wm = named.split("=", 1)[-1].strip() if "=" in named else "unnamed"
        supported = _run_tool([xprop, "-root", "_NET_SUPPORTED"])
        can = ("unknown" if supported is None else
               "yes" if "_NET_WM_STATE_FULLSCREEN" in supported else
               "NO - this window manager cannot make a window full screen")
        lines.append(f"window mgr    {wm}; full screen supported: {can}")
        size = _run_tool([xprop, "-root", "_NET_DESKTOP_GEOMETRY"]) or ""
        work = _run_tool([xprop, "-root", "_NET_WORKAREA"]) or ""
        lines.append(f"screen        {size.split('=', 1)[-1].strip() or 'unknown'}"
                     f"   work area {work.split('=', 1)[-1].strip()[:40] or 'unknown'}")
    geometry = {}
    if wmctrl:
        for line in (_run_tool([wmctrl, "-lG"]) or "").splitlines():
            bits = line.split()
            if len(bits) >= 6:
                geometry[bits[0]] = f"{bits[4]}x{bits[5]} at {bits[2]},{bits[3]}"
    lines.append(f"window read   {chosen or 'none'} - {how}")
    lines.append(f"windows       {len(windows)} on the screen")
    for wid, owner, klass in windows[:WINDOWS_MOST]:
        browser = any(k in klass for k in wanted)
        mark = ("KIOSK" if wid == chosen else
                "kiosk's process" if owner in owners else
                "another browser" if browser else "other")
        # A title can say what somebody is reading - an inbox, an address -
        # so only the kiosk's own is written down, which is ELMER's page.
        # Whose a window is, its owner and its class already say.
        title = ""
        if mark in ("KIOSK", "kiosk's process") and xprop:
            named = _run_tool([xprop, "-id", wid, "_NET_WM_NAME"]) or ""
            title = named.split("=", 1)[-1].strip()[:60] if "=" in named else ""
        lines.append(f"  {wid} {mark:16} pid {owner or '?':>7} {klass[:30]}"
                     f"{'  ' + geometry[wid] if wid in geometry else ''}"
                     f"  state {_state(xprop, wid) or '?'}"
                     f"{'  title ' + title if title else ''}")
    return lines


def _profile_holders(profile, procs):
    """The pids whose command line carries our --user-data-dir.

    A snap, or a Chromium already running on the same profile, can hand the
    launch to another process and let the one ELMER started exit or idle:
    the window is then owned by a process that is not under the launched
    pid, but it still has our profile on its command line."""
    if not profile:
        return set()
    flag = f"--user-data-dir={profile}"
    return {p for p, row in procs.items() if flag in row[2]}


def _inspected(xprop, wid):
    """The read window's WM_CLASS, _NET_WM_PID and title, as one line."""
    got = (_run_tool([xprop, "-id", wid, "WM_CLASS", "_NET_WM_PID", "_NET_WM_NAME"]) or "") if xprop else ""

    def value(name):
        found = re.search(rf"^{name}\([A-Z0-9_]+\) = (.*)$", got, re.MULTILINE)
        return found.group(1).strip()[:60] if found else "?"
    return (f"inspected     {wid}  WM_CLASS {value('WM_CLASS')}  _NET_WM_PID {value('_NET_WM_PID')}"
            f"  title {value('_NET_WM_NAME')}")


def fullscreen(pid, family, evidence=None, found=None, profile=None):
    """Whether the browser's window is full screen, as (True, False or None,
    why). None is "cannot tell here", said rather than guessed: Wayland does
    not let one program read another's window, and on X it takes xprop or
    wmctrl to ask. Given a list as `evidence`, what the reading rested on is
    added to it - see the section above. Given a dict as `found`, the window
    read goes in it: its id, and whether it is the kiosk's by its owner
    ("owned") or was only taken by its class - only an owned window may be
    set full screen by another program. `profile` is the kiosk's
    --user-data-dir, whose holders count as the kiosk's process."""
    evidence = [] if evidence is None else evidence
    found = {} if found is None else found
    kind = _session_kind()
    if kind == "wayland":
        return None, "a Wayland session does not let another program read a window's state"
    if kind != "x11":
        return None, "no X display to ask"
    xprop, wmctrl = _which("xprop"), _which("wmctrl")
    if not (xprop or wmctrl):
        return None, "neither xprop nor wmctrl is installed to ask X"
    wanted = ("chrom",) if family == "chromium" else ("firefox", "navigator")
    windows = _screen_windows(xprop, wmctrl)
    procs = _processes()
    holders = _profile_holders(profile, procs)
    owners = {str(p) for p in _tree(pid, procs)} | {str(pid)} | {str(p) for p in holders}
    # The kiosk's window is one its own process, a process under it, or a
    # process holding its profile owns. Only when there is none is a window
    # taken by its class, and then the reading says so: that window may be
    # somebody's own browser.
    ours = [w for w in windows if w[1] in owners]
    how = "owned by the kiosk's process"
    if not ours:
        ours = [w for w in windows if any(k in w[2] for k in wanted)]
        how = (f"by class only - none of the {len(windows)} windows is owned by the kiosk's "
               f"process; {len(ours)} browser window(s) on the screen")
    chosen = ours[0][0] if ours else None
    found.update(wid=chosen, owned=how.startswith("owned"))
    evidence.extend(_x_evidence(xprop, wmctrl, windows, owners, wanted, chosen, how))
    if chosen:
        evidence.append(_inspected(xprop, chosen))
    if not ours:
        return None, f"no window of the browser's among the {len(windows)} on the screen"
    wid = chosen
    if len(ours) > 1 and how.startswith("by class"):
        # Several browser windows and none of them the kiosk's by process:
        # any one of them read would be a guess.
        states = "; ".join(f"{w[0]}: {_state(xprop, w[0]) or '?'}" for w in ours[:4])
        return None, f"{how} - which is the kiosk's cannot be told ({states})"
    if xprop:
        shown = _state(xprop, wid)
        if shown is None:
            return None, f"xprop could not read window {wid}"
        note = "" if how.startswith("owned") else " (found by class only)"
        return "_NET_WM_STATE_FULLSCREEN" in shown, f"window {wid}: {shown}{note}"
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


def _process_evidence(pid, procs=None, profile=None):
    """The browser's processes and the desktop's, as lines - and which
    running processes hold the kiosk's profile, so a hand-off to another
    process (a snap's, or a browser session already open) shows."""
    procs = _processes() if procs is None else procs
    if not procs:
        return ["processes     no /proc to read"]
    lines = [f"desktop runs  {', '.join(_desktop_running(procs)) or 'none of the known window managers'}"]
    tree = _tree(pid, procs)
    if profile:
        holders = sorted(_profile_holders(profile, procs))
        if not holders:
            lines.append("our profile   NO running process has our --user-data-dir on its "
                         "command line - the launch was handed to a browser that is not ours")
        else:
            outside = [p for p in holders if p not in tree]
            lines.append(f"our profile   {len(holders)} process(es) have our --user-data-dir"
                         f"{'' if not outside else ', ' + str(len(outside)) + ' of them outside the launched pid: ' + ', '.join(map(str, outside[:6]))}")
    if not tree:
        lines.append(f"processes     the launched pid {pid} is gone - the browser handed "
                     f"off to another process or exited")
        return lines
    lines.append(f"processes     {len(tree)} under the launched pid {pid}")
    for p, (name, cmd) in list(tree.items())[:TREE_MOST]:
        lines.append(f"  {p:>7} {name[:16]:16} {cmd[:160]}")
    return lines


# What sets a window full screen when the browser's own flags did not, in
# the order tried: each is a way of asking the window manager the same thing.
FORCERS = (
    ("wmctrl", lambda tool, wid: [tool, "-i", "-r", wid, "-b", "add,fullscreen"]),
    ("xdotool", lambda tool, wid: [tool, "windowstate", "--add", "FULLSCREEN", wid]),
)
FORCE_SETTLE_S = 1.5    # how long a window manager is given to act on it


X_DIRECT = "X directly (libX11)"


def _x_fullscreen(wid):
    """Ask for full screen the way wmctrl does - an EWMH _NET_WM_STATE client
    message to the root window - through libX11 itself, which every X desktop
    has, so a unit without wmctrl or xdotool is not left in a window. A field
    report from Ubuntu GNOME had neither, and Chromium's own --kiosk
    --start-fullscreen left it merely focused. True if the request was sent,
    False if X refused it, None if there is no libX11 or display to ask."""
    if os.name == "nt" or not os.environ.get("DISPLAY"):
        return None
    import ctypes
    import ctypes.util
    name = ctypes.util.find_library("X11")
    if not name:
        return None
    try:
        x = ctypes.CDLL(name)
    except OSError as exc:
        log.warning("kiosk: libX11 would not load from %s: %s", name, exc)
        return None
    x.XOpenDisplay.restype = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XDefaultRootWindow.restype = ctypes.c_ulong
    x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    x.XInternAtom.restype = ctypes.c_ulong
    x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
    x.XFlush.argtypes = [ctypes.c_void_p]
    x.XCloseDisplay.argtypes = [ctypes.c_void_p]

    class ClientMessage(ctypes.Structure):
        _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                    ("display", ctypes.c_void_p), ("window", ctypes.c_ulong),
                    ("message_type", ctypes.c_ulong), ("format", ctypes.c_int),
                    ("data", ctypes.c_long * 5)]

    class Event(ctypes.Union):            # XEvent is padded to 24 longs
        _fields_ = [("xclient", ClientMessage), ("pad", ctypes.c_long * 24)]

    display = x.XOpenDisplay(None)
    if not display:
        log.warning("kiosk: libX11 could not open display %s", os.environ.get("DISPLAY"))
        return None
    try:
        event = Event()
        event.xclient.type = 33                   # ClientMessage
        event.xclient.send_event = 1
        event.xclient.display = display
        event.xclient.window = int(wid, 16)
        event.xclient.message_type = x.XInternAtom(display, b"_NET_WM_STATE", 0)
        event.xclient.format = 32
        event.xclient.data[0] = 1                 # _NET_WM_STATE_ADD
        event.xclient.data[1] = x.XInternAtom(display, b"_NET_WM_STATE_FULLSCREEN", 0)
        event.xclient.data[3] = 1                 # asked by a normal application
        redirect_and_notify = (1 << 20) | (1 << 19)
        sent = x.XSendEvent(display, x.XDefaultRootWindow(display), 0,
                            redirect_and_notify, ctypes.byref(event))
        x.XFlush(display)
        return bool(sent)
    finally:
        x.XCloseDisplay(display)


def _force(pid, family, wid, profile):
    """Ask the window manager to make window `wid` full screen, with each
    tool in FORCERS that is present, then X directly, until one does it.
    Returns (full, why, tried): tried names each and what came of it."""
    tried = []
    full, why = False, ""
    for name, command in FORCERS:
        tool = _which(name)
        if not tool:
            continue
        ran = _run_tool(command(tool, wid))
        time.sleep(FORCE_SETTLE_S)
        full, why = fullscreen(pid, family, profile=profile)
        tried.append(f"{name}: {'full screen' if full else 'not full screen'}"
                     f"{'' if ran is not None else ' (it reported a failure)'}")
        log.info("kiosk: set full screen with %s on %s - %s", name, wid, why)
        if full:
            return True, why, tried
    try:
        sent = _x_fullscreen(wid)
    except (OSError, ValueError, AttributeError) as exc:     # a libX11 without a symbol, a bad wid
        log.warning("kiosk: asking X directly for full screen failed on %s: %s", wid, exc)
        sent = False
    if sent is not None:
        time.sleep(FORCE_SETTLE_S)
        full, why = fullscreen(pid, family, profile=profile)
        tried.append(f"{X_DIRECT}: {'full screen' if full else 'not full screen'}"
                     f"{'' if sent else ' (X refused the request)'}")
        log.info("kiosk: set full screen with %s on %s - %s", X_DIRECT, wid, why)
    return full, why, tried


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
    how = f" - {got['set_by']}" if got.get("set_by") else ""
    return f"verdict       {got.get('verdict')} (last --kiosk launch, {when}){how}"


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
    out.extend(got.get("evidence") or [])
    out.extend(f"at launch     {line}" for line in got.get("lines") or [])
    return out


def _tail(path, n=STDERR_TAIL):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [line for line in text.splitlines() if line.strip()][-n:]


def _follow(process, family, lines, profile=None):
    """Watch the first seconds of a launch and write down what it came to.

    A browser gone within EARLY_S never started: its exit code and the last
    of what it said go to the log. One still running is asked, where that
    can be asked, whether its window went full screen - and if its own
    flags did not do it, the window manager is asked to (see _force), and
    which step did it, or that none did, goes with the verdict."""
    try:
        # Read once a second from the start, and each change written down:
        # a window that went full screen and was taken out of it again, or
        # one that never went, look the same at the end and not on the way.
        started = time.monotonic()
        timeline, seen, code = [], None, None
        while True:
            try:
                code = process.wait(timeout=SAMPLE_S)
                break
            except subprocess.TimeoutExpired:
                pass
            elapsed = time.monotonic() - started
            _full, why = fullscreen(process.pid, family, profile=profile)
            if why != seen:
                log.debug("kiosk: at %.1f s %s", elapsed, why)
                timeline.append(f"  at {elapsed:4.1f} s  {why}")
                seen = why
            if elapsed >= EARLY_S:
                break
        if code is not None:
            tail = _tail(BROWSER_LOG)
            log.warning("kiosk: the browser exited with code %s within %.0f s of starting",
                        code, EARLY_S)
            for line in tail:
                log.warning("kiosk: browser said: %s", line)
            _record(EXITED, lines, exit_code=code, stderr=tail,
                    evidence=["timeline" + ("" if timeline else "      (gone before a first reading)")]
                    + timeline)
            return
        deadline = time.monotonic() + WINDOW_WAIT_S
        while True:
            evidence, found = [], {}
            full, why = fullscreen(process.pid, family, evidence, found, profile)
            if full is not None or not why.startswith("no window") or time.monotonic() >= deadline:
                break
            time.sleep(1.0)
        # The browser's own flags first; then, on X, the window manager asked
        # directly - but only for a window shown to be the kiosk's by its
        # owner. One taken by its class alone may be the operator's own
        # browser, and making that full screen would be a fault of our own.
        steps = "--kiosk --start-fullscreen" if family == "chromium" else "--kiosk"
        if full:
            set_by = f"the browser's own flags ({steps}) did it"
        elif full is False and found.get("owned"):
            forced, forced_why, tried = _force(process.pid, family, found["wid"], profile)
            if not tried:
                set_by = (f"the browser's own flags ({steps}) did not, and there is no wmctrl "
                          f"or xdotool to set it, nor a libX11 and display to ask X directly - "
                          f"none of them made it full screen")
            elif forced:
                set_by = f"the browser's own flags ({steps}) did not; {tried[-1].split(':')[0]} did"
                full, why = True, forced_why
            else:
                set_by = (f"none made it full screen: the browser's own flags ({steps}), "
                          + ", ".join(tried))
                why = forced_why or why
            log.info("kiosk: full screen - %s", set_by)
        elif full is False:
            set_by = (f"the browser's own flags ({steps}) did not, and the window read was found "
                      f"by class only, so it was not set from outside - it may not be the kiosk's")
        else:
            set_by = ""
        evidence = (_process_evidence(process.pid, profile=profile) + evidence
                    + ([f"full screen   {set_by}"] if set_by else [])
                    + ["timeline      the window's state, from the launch:"] + timeline
                    + [f"browser said  {line}" for line in _tail(BROWSER_LOG)])
        # At info, every launch: the evidence is only worth anything if it is
        # there for the launch that went wrong, and nobody knows in advance
        # which one that will be.
        for line in evidence:
            log.info("kiosk: %s", line)
        if full is None:
            log.info("kiosk: whether it is full screen cannot be checked here: %s", why)
            _record(UNCHECKABLE, lines, fullscreen=why, evidence=evidence)
        elif full:
            _record(FULL, lines, fullscreen=why, evidence=evidence, set_by=set_by)
        else:
            log.warning("kiosk: the browser is running but not full screen: %s", why)
            _record(NOT_FULL, lines, fullscreen=why, evidence=evidence, set_by=set_by)
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
            # Asked for twice over: --kiosk alone has come up focused and
            # not full screen on GNOME under X, with a snap's Chromium.
            "--start-fullscreen",
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
    thread = threading.Thread(target=_follow, args=(process, family, lines, profile),
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
