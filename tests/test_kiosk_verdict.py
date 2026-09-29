#!/usr/bin/env python3
"""A kiosk that did not come up says why, in the log, the report and the doctor.

    python3 tests/test_kiosk_verdict.py

A unit nobody can paste a log from still has to explain a screen that did
not fill. What is held here, each with a stand-in browser and a stand-in
screen:

  - every launch ends in one of six verdicts, written down where the report,
    the doctor and the dashboard read it: browser not found, no screen,
    started and exited, running but not full screen, running full screen,
    not checkable;
  - a browser gone within the first seconds has its exit code and the last
    of what it said on stderr in the log - it used to go nowhere;
  - full screen is read from X with xprop, or with wmctrl alone, and on
    Wayland, or with neither tool, it is said to be uncheckable rather than
    guessed;
  - a snap or a flatpak browser is named as one;
  - a browser that never came up does not take the server down with it;
  - the problem report and the doctor carry a Kiosk section with the
    verdict first, redacted like the rest; the dashboard is told of a failed
    launch, on the local screen only, and offers "Report this".
"""
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
ROOT = Path(__file__).resolve().parents[1]
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


class Said(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


SCREEN_VARS = ("DISPLAY", "WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP")


def screen(**env):
    """This process's screen, as the kiosk will see it."""
    for name in SCREEN_VARS:
        os.environ.pop(name, None)
    os.environ.update(env)


def main():
    from elmer import kiosk as K
    said = Said()
    logging.getLogger("elmer").addHandler(said)
    logging.getLogger("elmer").setLevel(logging.INFO)
    saved_env = {name: os.environ.get(name) for name in SCREEN_VARS}
    real = {name: getattr(K, name) for name in
            ("find_browser", "_command", "_which", "_run_tool", "_processes",
             "EARLY_S", "WINDOW_WAIT_S", "SAMPLE_S", "FORCE_SETTLE_S")}
    K.EARLY_S, K.WINDOW_WAIT_S, K.SAMPLE_S, K.FORCE_SETTLE_S = 2.0, 0.0, 0.3, 0.0
    python = sys.executable
    running = []

    def browser(code):
        """A stand-in browser: this Python, running `code`."""
        K.find_browser = lambda: (python, "chromium")
        K._command = lambda path, family, url, profile: [python, "-c", code]

    def launch():
        process = K.launch("http://127.0.0.1:5000/")
        if process is not None:
            running.append(process)
        thread = K._follower["thread"]
        if thread is not None:
            thread.join(15)
        K._follower["thread"] = None
        return process, K.last()

    def x11(tools, answers):
        """An X screen with these tools on it, answering these questions."""
        screen(DISPLAY=":0", XDG_SESSION_TYPE="x11")
        K._which = lambda name: name if name in tools else None

        def run(args):
            for key, answer in answers.items():
                if key in " ".join(args):
                    return answer(args) if callable(answer) else answer
            return None
        K._run_tool = run

    stay = "import time; time.sleep(30)"
    try:
        print("\n-- the browser, named for what it is --")
        check("a snap is a snap", K.packaging("/snap/bin/chromium"), "snap")
        check("a flatpak is a flatpak",
              K.packaging("/var/lib/flatpak/exports/bin/org.chromium.Chromium"), "flatpak")
        check("an ordinary one is neither", K.packaging(python), None)

        print("\n-- no screen, no browser --")
        screen()
        browser(stay)
        # Windows always has a desktop, so the question is asked of the
        # screen directly there; on Linux the empty environment answers it.
        real_display = K.have_display
        if os.name == "nt":
            K.have_display = lambda: False
        try:
            _, got = launch()
        finally:
            K.have_display = real_display
        check("no DISPLAY and no WAYLAND_DISPLAY: no screen", got["verdict"], K.NO_SCREEN)
        screen(DISPLAY=":0", XDG_SESSION_TYPE="x11")
        K.find_browser = lambda: (None, None)
        _, got = launch()
        check("nothing to run: browser not found", got["verdict"], K.NOT_FOUND)
        check("  and the facts went with it",
              any(line.startswith("session type  x11") for line in got["lines"]), True)

        print("\n-- a browser that dies at the start says why --")
        said.lines.clear()
        browser("import sys; sys.stderr.write('Failed to create profile directory /home/kc9sp/x\\n'); sys.exit(3)")
        _, got = launch()
        check("started and exited", got["verdict"], K.EXITED)
        check("  with its exit code", got["exit_code"], 3)
        check("  and the last of what it said",
              any("Failed to create profile directory" in line for line in got["stderr"]), True)
        check("  both in the log, under kiosk:",
              (any("exited with code 3" in line for line in said.lines),
               any(line.startswith("kiosk: browser said: Failed to create") for line in said.lines)),
              (True, True))

        print("\n-- a browser that stays up: is it full screen? --")
        browser(stay)
        screen(WAYLAND_DISPLAY="wayland-0", XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="GNOME")
        _, got = launch()
        check("on Wayland it cannot be checked, and says so",
              (got["verdict"], "Wayland" in got["fullscreen"]), (K.UNCHECKABLE, True))
        check("  and the session is in the facts",
              any("WAYLAND_DISPLAY wayland-0" in line for line in got["lines"]), True)

        x11(tools=(), answers={})
        _, got = launch()
        check("on X with neither tool, not checkable either",
              (got["verdict"], "neither xprop nor wmctrl" in got["fullscreen"]), (K.UNCHECKABLE, True))

        def props(args):
            pid = running[-1].pid if running else 0
            return f'_NET_WM_PID(CARDINAL) = {pid}\nWM_CLASS(STRING) = "chromium", "Chromium"\n'
        listing = {"-root _NET_CLIENT_LIST": "_NET_CLIENT_LIST(WINDOW): window id # 0x1a00003\n",
                   "_NET_WM_PID WM_CLASS": props}
        x11(tools=("xprop",), answers={**listing,
            "_NET_WM_STATE": "_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN, _NET_WM_STATE_FOCUSED\n"})
        _, got = launch()
        check("xprop: a window marked full screen is running full screen", got["verdict"], K.FULL)
        x11(tools=("xprop",), answers={**listing,
            "_NET_WM_STATE": "_NET_WM_STATE(ATOM) = _NET_WM_STATE_MAXIMIZED_VERT, _NET_WM_STATE_MAXIMIZED_HORZ\n"})
        _, got = launch()
        check("xprop: a maximized window is running but not full screen", got["verdict"], K.NOT_FULL)
        check("  and says what state it is in", "MAXIMIZED_VERT" in got["fullscreen"], True)

        def listed(args):
            pid = running[-1].pid if running else 0
            return f"0x03a00003  0 {pid}   chromium.Chromium  unit ELMER\n"
        desk = "0  * DG: 1920x1080  VP: 0,0  WA: 0,27 1920x1053  Desktop\n"
        x11(tools=("wmctrl",), answers={"-lpx": listed, "-d": desk,
                                        "-lG": "0x03a00003  0 0    27   1280 800  unit ELMER\n"})
        _, got = launch()
        check("wmctrl alone: a window smaller than the desktop is not full screen",
              (got["verdict"], got["fullscreen"]),
              (K.NOT_FULL, "window 0x03a00003 is 1280x800 on a 1920x1080 desktop"))
        x11(tools=("wmctrl",), answers={"-lpx": listed, "-d": desk,
                                        "-lG": "0x03a00003  0 0    0    1920 1080 unit ELMER\n"})
        _, got = launch()
        check("  and one the size of the desktop is", got["verdict"], K.FULL)

        print("\n-- the evidence: whose window was read, and what else was there --")
        # The unit that sent "running but not full screen" read a window it
        # had found by class alone, on a desktop that may have held somebody's
        # own browser as well. Which window was read, and why, goes with the
        # verdict now, with everything else on the screen beside it.
        procs = {1: (0, "systemd", "/sbin/init"),
                 900: (1, "gnome-shell", "/usr/bin/gnome-shell"),
                 4000: (1, "chrome", "/usr/lib/chromium/chrome --user-data-dir=/home/op/.config"),
                 4400: (1, "gedit", "/usr/bin/gedit /home/op/notes.txt")}

        def with_kiosk(child_owns_window):
            """The launched pid, a child of it, and the processes above."""
            pid = running[-1].pid if running else 0
            out = dict(procs)
            out[pid] = (1, "chromium.launch", "/snap/bin/chromium --kiosk file:///x")
            out[pid + 1] = (pid, "chrome", "/snap/chromium/current/chrome --kiosk file:///x")
            return out, (pid + 1 if child_owns_window else pid)

        def desktop(kiosk_state, own=True, kiosk_listed=True, wm_full=True):
            """Three windows: the kiosk's (owned by a child of the launched
            pid), the operator's own Chromium, and an editor."""
            def listed(args):
                table, owner = with_kiosk(True)
                rows = []
                if kiosk_listed:
                    rows.append(f"0x05000004  0 {owner if own else 4000}   chromium.Chromium  ELMER")
                rows += ["0x03a00003  0 4000   chromium.Chromium  mail - Chromium",
                         "0x04400001  0 4400   gedit.Gedit  notes.txt"]
                return "\n".join(rows) + "\n"

            def state(args):
                wid = args[args.index("-id") + 1]
                return {"0x05000004": f"_NET_WM_STATE(ATOM) = {kiosk_state}\n",
                        "0x03a00003": "_NET_WM_STATE(ATOM) = _NET_WM_STATE_MAXIMIZED_VERT, _NET_WM_STATE_MAXIMIZED_HORZ\n",
                        }.get(wid, "_NET_WM_STATE(ATOM) = \n")

            def name(args):
                wid = args[args.index("-id") + 1] if "-id" in args else ""
                return {"0x1c00001": '_NET_WM_NAME(UTF8_STRING) = "GNOME Shell"\n',
                        "0x05000004": '_NET_WM_NAME(UTF8_STRING) = "ELMER"\n',
                        "0x03a00003": '_NET_WM_NAME(UTF8_STRING) = "mail - Chromium"\n',
                        "0x04400001": '_NET_WM_NAME(UTF8_STRING) = "notes.txt - secret plans"\n',
                        }.get(wid)
            x11(tools=("xprop", "wmctrl"), answers={
                "-lpx": listed,
                # The same windows, for a box with xprop and no wmctrl.
                "-root _NET_CLIENT_LIST": lambda args: "_NET_CLIENT_LIST(WINDOW): window id # " + ", ".join(
                    row.split()[0] for row in listed(args).splitlines()) + "\n",
                "_NET_WM_PID WM_CLASS": lambda args: next(
                    (f'_NET_WM_PID(CARDINAL) = {row.split()[2]}\nWM_CLASS(STRING) = "{row.split()[3]}"\n'
                     for row in listed(args).splitlines() if row.split()[0] == args[args.index("-id") + 1]), ""),
                "-lG": "0x05000004  0 0 0 1920 1080 x ELMER\n0x03a00003  0 80 60 1200 900 x mail\n",
                "_NET_SUPPORTING_WM_CHECK": "_NET_SUPPORTING_WM_CHECK(WINDOW): window id # 0x1c00001\n",
                "_NET_SUPPORTED": ("_NET_SUPPORTED(ATOM) = _NET_WM_STATE, "
                                   + ("_NET_WM_STATE_FULLSCREEN" if wm_full else "_NET_WM_STATE_HIDDEN") + "\n"),
                "_NET_DESKTOP_GEOMETRY": "_NET_DESKTOP_GEOMETRY(CARDINAL) = 1920, 1080\n",
                "_NET_WORKAREA": "_NET_WORKAREA(CARDINAL) = 0, 32, 1920, 1048\n",
                "_NET_WM_STATE": state,
                "_NET_WM_NAME": name,
            })
            K._processes = lambda: with_kiosk(True)[0]

        browser(stay)
        desktop("_NET_WM_STATE_FULLSCREEN, _NET_WM_STATE_FOCUSED")
        _, got = launch()
        ev = "\n".join(got.get("evidence") or [])
        check("the window a child of the launched browser owns is the kiosk's",
              (got["verdict"], "0x05000004" in got["fullscreen"]), (K.FULL, True))
        check("  read by its owner, not its class", "owned by the kiosk's process" in ev, True)
        check("  the operator's own browser beside it is named as another browser",
              "0x03a00003 another browser" in ev, True)
        check("  the kiosk's own title is written down", 'title "ELMER"' in ev, True)
        check("  but no other window's - not the operator's browsing, not another program's",
              ("mail - Chromium" in ev, "gedit" in ev, "secret plans" in ev), (False, True, False))
        check("  the window manager, and whether it can do full screen at all",
              '"GNOME Shell"; full screen supported: yes' in ev, True)
        check("  the screen and its work area", ("1920, 1080" in ev, "0, 32, 1920, 1048" in ev), (True, True))
        check("  each window's size and state",
              "1200x900 at 80,60" in ev and "MAXIMIZED_HORZ" in ev, True)
        check("  the browser's processes, under the pid launched",
              ("processes     2 under the launched pid" in ev, "--kiosk file:///x" in ev), (True, True))
        check("  and the desktop that is running", "desktop runs  gnome-shell" in ev, True)
        check("  and the window's state second by second from the launch",
              "timeline" in ev and "  at " in ev, True)

        desktop("_NET_WM_STATE_FOCUSED", kiosk_listed=False)
        _, got = launch()
        check("only somebody else's browser on the screen: read, and said to be found by class",
              (got["verdict"], "(found by class only)" in got["fullscreen"]), (K.NOT_FULL, True))
        check("  the evidence says none was the kiosk's",
              "none of the 2 windows is owned by the kiosk's process" in "\n".join(got["evidence"]), True)

        def two_browsers(args):
            return ("0x05000004  0 4000   chromium.Chromium  ELMER\n"
                    "0x03a00003  0 4000   chromium.Chromium  mail - Chromium\n")
        desktop("_NET_WM_STATE_FOCUSED", own=False)
        K._run_tool = (lambda run: lambda args: two_browsers(args) if "-lpx" in args else run(args))(K._run_tool)
        _, got = launch()
        check("two browser windows and neither the kiosk's: not guessed at",
              (got["verdict"], "cannot be told" in got["fullscreen"]), (K.UNCHECKABLE, True))

        desktop("_NET_WM_STATE_FOCUSED", wm_full=False)
        _, got = launch()
        check("a window manager that cannot do full screen says so",
              "full screen supported: NO" in "\n".join(got["evidence"]), True)

        # A window that goes full screen and is taken out of it again.
        calls = {"n": 0}
        desktop("x")
        inner = K._run_tool

        def flips(args):
            if "_NET_WM_STATE" in args and "0x05000004" in args:
                calls["n"] += 1
                return ("_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN\n" if calls["n"] <= 2
                        else "_NET_WM_STATE(ATOM) = _NET_WM_STATE_MAXIMIZED_VERT\n")
            return inner(args)
        K._run_tool = flips
        _, got = launch()
        lines = [ln for ln in got["evidence"] if ln.startswith("  at ")]
        check("full screen, then taken out of it: the timeline shows both",
              (any("FULLSCREEN" in ln for ln in lines), any("MAXIMIZED_VERT" in ln for ln in lines)),
              (True, True))
        check("  and the verdict is the state at the end", got["verdict"], K.NOT_FULL)

        print("\n-- full screen asked for twice, and set from outside when it is not --")
        install = (ROOT / "install.sh").read_text(encoding="utf-8")
        check("install.sh installs wmctrl as needed, not optional - an optional one never reaches a unit that has the rest",
              ('check_bin wmctrl wmctrl' in install, 'check_optional wmctrl' in install), (True, False))
        check("Chromium is launched with --start-fullscreen beside --kiosk",
              "--start-fullscreen" in real["_command"]("/snap/bin/chromium", "chromium", "u", "/p"), True)

        def forcing(tools, takes):
            """The desktop above, with these tools, where the kiosk window goes
            full screen once `takes` has asked for it (or never, for None)."""
            desktop("_NET_WM_STATE_FOCUSED")
            base = K._run_tool
            asked = []
            K._which = lambda name: name if name in ("xprop",) + tools else None

            def run(args):
                if args[0] in ("wmctrl", "xdotool") and ("add,fullscreen" in args or "FULLSCREEN" in args):
                    asked.append((args[0], args[-1] if args[0] == "xdotool" else args[3]))
                    return ""
                if "_NET_WM_STATE" in args and "0x05000004" in args and takes and any(a[0] == takes for a in asked):
                    return "_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN\n"
                return base(args)
            K._run_tool = run
            return asked

        asked = forcing(("wmctrl",), "wmctrl")
        _, got = launch()
        check("flags not enough, wmctrl present: it is asked, on the kiosk's window",
              asked[:1], [("wmctrl", "0x05000004")])
        check("  and the launch ends full screen, saying wmctrl did it",
              (got["verdict"], "wmctrl did" in got.get("set_by", "")), (K.FULL, True))
        check("  said in the verdict line itself", "wmctrl did" in K.verdict_line(), True)

        asked = forcing(("xdotool",), "xdotool")
        _, got = launch()
        check("only xdotool present: xdotool is asked", [a[0] for a in asked], ["xdotool"])
        check("  and said to have done it", (got["verdict"], "xdotool did" in got["set_by"]), (K.FULL, True))

        asked = forcing(("wmctrl", "xdotool"), None)
        _, got = launch()
        check("neither takes: both are tried", [a[0] for a in asked], ["wmctrl", "xdotool"])
        check("  and the verdict says none made it full screen",
              (got["verdict"], "none made it full screen" in K.verdict_line()), (K.NOT_FULL, True))

        # No tool at all, and X itself asked - the Ubuntu GNOME field report:
        # snap Chromium left merely focused, neither wmctrl nor xdotool.
        real_x = K._x_fullscreen
        try:
            K._x_fullscreen = lambda wid: None
            asked = forcing((), None)
            _, got = launch()
            check("no tool and no libX11: the verdict says that",
                  ("no wmctrl or xdotool" in got["set_by"], "libX11" in got["set_by"]), (True, True))

            sent = []
            asked = forcing((), None)
            inner = K._run_tool

            def after_x(args):
                if "_NET_WM_STATE" in args and "0x05000004" in args and sent:
                    return "_NET_WM_STATE(ATOM) = _NET_WM_STATE_FULLSCREEN" + chr(10)
                return inner(args)
            K._run_tool = after_x
            K._x_fullscreen = lambda wid: sent.append(wid) or True
            _, got = launch()
            check("no tool, but X asked directly on the kiosk's window: it goes full screen",
                  (sent[:1], got["verdict"], "X directly (libX11) did" in got.get("set_by", "")),
                  (["0x05000004"], K.FULL, True))

            sent.clear()
            K._run_tool = inner
            K._x_fullscreen = lambda wid: sent.append(wid) or True
            asked = forcing(("wmctrl",), None)
            _, got = launch()
            check("  and it is the last resort: wmctrl first, then X, and both said when neither takes",
                  ([a[0] for a in asked], sent[:1], "wmctrl: not full screen" in got["set_by"],
                   "X directly (libX11): not full screen" in got["set_by"]),
                  (["wmctrl"], ["0x05000004"], True, True))
        finally:
            K._x_fullscreen = real_x
        check("on this machine the real X request stands aside without a display",
              K._x_fullscreen("0x1") if (os.name == "nt" or not os.environ.get("DISPLAY")) else None, None)

        desktop("_NET_WM_STATE_FOCUSED", kiosk_listed=False)
        base = K._run_tool
        asked = []
        K._run_tool = lambda args: (asked.append(args) or "") if "add,fullscreen" in args else base(args)
        _, got = launch()
        check("a window found by class only is never set from outside - it may be the operator's",
              (asked, "found by class only" in got["set_by"]), ([], True))

        print("\n-- a hand-off to another process holding our profile is seen --")
        desktop("_NET_WM_STATE_FULLSCREEN", own=False)
        profile_dir = str(K.PROFILE_DIR / "chromium")
        handed = dict(procs)
        handed[4000] = (1, "chrome", f"/snap/chromium/current/chrome --user-data-dir={profile_dir} --kiosk")
        K._processes = lambda: ({**handed, running[-1].pid: (1, "chromium.launch", "/snap/bin/chromium")}
                                if running else handed)
        _, got = launch()
        ev = "\n".join(got["evidence"])
        check("a window whose owner holds our --user-data-dir is the kiosk's",
              ("owned by the kiosk's process" in ev, got["verdict"]), (True, K.FULL))
        check("  and the profile's holder outside the launched pid is named",
              "outside the launched pid: 4000" in ev, True)
        handed.pop(4000)
        _, got = launch()
        check("no process holding our profile: said plainly",
              "NO running process has our --user-data-dir" in "\n".join(got["evidence"]), True)

        print("\n-- the window read, named by its own properties --")
        desktop("_NET_WM_STATE_FULLSCREEN")
        base = K._run_tool
        K._run_tool = lambda args: ('WM_CLASS(STRING) = "chromium", "Chromium"\n'
                                    '_NET_WM_PID(CARDINAL) = 4242\n'
                                    '_NET_WM_NAME(UTF8_STRING) = "ELMER"\n'
                                    if "WM_CLASS" in args and "_NET_WM_NAME" in args else base(args))
        _, got = launch()
        check("its WM_CLASS, _NET_WM_PID and title are written down",
              any(ln.startswith("inspected     0x05000004") and '"chromium", "Chromium"' in ln
                  and "_NET_WM_PID 4242" in ln and 'title "ELMER"' in ln for ln in got["evidence"]), True)
        K._processes = lambda: with_kiosk(True)[0]

        print("\n-- the evidence reaches the report and the field report --")
        from elmer import bugreport, fieldreport
        section = "\n".join(K.last_lines())
        check("the Kiosk section carries the timeline", "timeline" in section, True)
        report = fieldreport.build()
        check("  and so does the weekly field report, which is the one that is sent",
              ("timeline" in report, "window read" in report), (True, True))
        check("a browser's version is not taken for a coordinate",
              bugreport.redact("Chromium 153.0.7433.47 snap"), "Chromium 153.0.7433.47 snap")
        check("  while a coordinate still is",
              bugreport.redact("at 46.5983,-94.3154."), "at [coord],[coord].")
        # Leave the last launch a good one, which is what follows expects.
        desktop("_NET_WM_STATE_FULLSCREEN")
        launch()
        K._processes = real["_processes"]

        print("\n-- what is failed and what is not --")
        check("running full screen is not a failure", K.failed(), None)
        x11(tools=(), answers={})
        launch()
        check("  nor is not being able to tell", K.failed(), None)
        browser("import sys; sys.stderr.write('cannot open /home/kc9sp/.config/elmer\\n'); sys.exit(1)")
        launch()
        check("  but a browser that exited is", (K.failed() or {}).get("verdict"), K.EXITED)

        print("\n-- a browser that never came up does not stop the server --")
        import threading
        killed = []
        real_kill = K.os.kill
        K.os.kill = lambda pid, sig: killed.append(sig)

        class Gone:
            def __init__(self, age):
                self.kiosk_started = time.monotonic() - age

            def wait(self, timeout=None):
                return 1
        try:
            K.watch(Gone(age=1.0), threading.Event()).join(5)
            check("gone within the first seconds: the server keeps running", killed, [])
            K.watch(Gone(age=K.EARLY_S + 60), threading.Event()).join(5)
            check("closed after it was up: the server stops, as it always has", len(killed), 1)
        finally:
            K.os.kill = real_kill

        print("\n-- the report and the doctor carry it, verdict first --")
        from elmer import bugreport, db, diagnostics, host
        conn = db.connect()
        db.set_callsign(conn, "KC9SP")
        text, redacted = bugreport.build(conn, kind="comment", said="testing")
        conn.close()
        section = text[text.index("\nKiosk\n"):] if "\nKiosk\n" in text else ""
        check("the report has a Kiosk section", bool(section), True)
        check("  its first line is the verdict",
              section.splitlines()[3].startswith("verdict       started and exited") if section else None, True)
        check("  with what the browser said",
              "browser said  cannot open /home/" in section, True)
        # The home folder here is named for the callsign, so the callsign's
        # own rule gets to it first: /home/[call]. Either way nothing of it
        # is left.
        check("  redacted like the rest of the report",
              (redacted, "kc9sp" in section.lower(), "cannot open /home/[" in section), (True, False, True))

        real_can = host.can_kiosk
        host.can_kiosk = lambda: True
        diagnostics._collected = []
        try:
            browser(stay)
            screen(DISPLAY=":0", XDG_SESSION_TYPE="x11")
            diagnostics.check_kiosk()
            found = {row["label"]: row for row in diagnostics._collected}
        finally:
            diagnostics._collected = None
            host.can_kiosk = real_can
        last_row = found.get("kiosk last launch", {})
        check("the doctor gives the last launch a line of its own",
              (last_row.get("state"), (last_row.get("detail") or "").startswith("started and exited")),
              ("warn", True))
        doctor_src = (ROOT / "elmer" / "diagnostics.py").read_text(encoding="utf-8")
        check("  and prints the Kiosk section in full on --doctor",
              'print("\\n  Kiosk\\n")' in doctor_src and "_kiosk.last_lines()" in doctor_src, True)

        print("\n-- the dashboard says so, on the local screen, with Report this --")
        from elmer.app import app
        c = app.test_client()
        here = c.get("/api/update", environ_base=LOCAL).get_json()
        away = c.get("/api/update", environ_base={"REMOTE_ADDR": "192.168.1.40"}).get_json()
        check("the local screen is told the last launch failed, and how",
              (here.get("kiosk_failed") or {}).get("verdict"), K.EXITED)
        check("  another device is not", away.get("kiosk_failed"), None)
        page = (ROOT / "elmer" / "static" / "update.js").read_text(encoding="utf-8")
        check("  the line offers Report this, which opens the problem report with the verdict in it",
              ("data-report-kiosk" in page, ">Report this</button>" in page,
               "The kiosk did not come up full screen: " in page), (True, True, True))
    finally:
        for process in running:
            try:
                process.kill()
                process.wait(5)
            except Exception:                 # already gone: nothing to stop
                pass
        for name, value in real.items():
            setattr(K, name, value)
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
