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
            ("find_browser", "_command", "_which", "_run_tool", "EARLY_S", "WINDOW_WAIT_S")}
    K.EARLY_S, K.WINDOW_WAIT_S = 2.0, 0.0
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
