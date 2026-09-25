#!/usr/bin/env python3
"""The window of ELMER's own on Windows, and what closing it would end.

    python3 tests/test_window.py

The launch itself needs Edge or Chrome and a screen, so it is proved by
hand and by the console line it prints. What is checked here is the rest:
the command that makes it a window of its own, the watcher that stops the
server when it ends and stays quiet when the server is already going, and
the count of people the page's warning is built from - this table's, and
the other tables' of a net this unit runs, practice players left out.
"""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import app as appmod, host, party, window  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run():
    print("\n-- a window of its own --")
    cmd = window.command("browser.exe", "http://localhost:5000/")
    check("an app window, not a tab", cmd[1].startswith("--app="), True)
    check("  on ELMER, marked as the window", cmd[1], f"--app=http://localhost:5000/?{window.OWNER_FLAG}")
    check("  in a profile of ELMER's own", any(a.startswith("--user-data-dir=") for a in cmd), True)
    cmd = window.command("browser.exe", "http://localhost:5000/?x=1")
    check("  a query already there is joined, not doubled", cmd[1], "--app=http://localhost:5000/?x=1&elmer_window=1")

    print("\n-- opening on the splash, so the wait is watched rather than blank --")
    # The window used to be held back until the server answered: up to a
    # minute of nothing on the screen, and no way to tell a slow start from a
    # dead one. The kiosk has never done that - it opens on a page held on
    # disk and lets that page find the server - and this is the same page.
    cmd = window.command("b", "http://localhost:5000/", port=5000)
    opened = cmd[1][len("--app="):]
    check("the window opens on the splash, from disk", opened.startswith("file:"), True)
    check("  which is told where to find the server", "port=5000" in opened, True)
    check("  and where to hand over to, mark and all",
          "to=" + quote("http://localhost:5000/?" + window.OWNER_FLAG, safe="") in opened, True)
    check("without a port there is nothing to wait for: straight to ELMER",
          window.command("b", "http://localhost:5000/")[1],
          "--app=http://localhost:5000/?" + window.OWNER_FLAG)
    was_splash = window.SPLASH
    window.SPLASH = Path(str(was_splash) + ".not-here")
    try:
        check("no splash on this machine: straight to ELMER, as before",
              window.command("b", "http://localhost:5000/", port=5000)[1],
              "--app=http://localhost:5000/?" + window.OWNER_FLAG)
    finally:
        window.SPLASH = was_splash
    splash = was_splash.read_text(encoding="utf-8")
    check("the splash honors where it was told to go", "params.get('to')" in splash, True)
    check("  and goes there rather than to a rebuilt home page", "location.href = onward" in splash, True)

    print("\n-- how it opens: full screen, unless the person said otherwise --")
    size = lambda c: [a for a in c if a.startswith("--window-size") or a == "--start-maximized"]  # noqa: E731
    check("said nothing: full screen, which is what ELMER opens as",
          size(window.command("b", "http://x/")), ["--start-maximized"])
    check("nothing saved yet: full screen too, whatever was asked for",
          size(window.command("b", "http://x/", "as-left", remembered=False, maximized=False)), ["--start-maximized"])
    check("bounds saved, left at a size of its own: nothing said",
          size(window.command("b", "http://x/", "as-left", remembered=True, maximized=False)), [])
    check("left maximized: maximized again, said out loud",
          size(window.command("b", "http://x/", "as-left", remembered=True, maximized=True)), ["--start-maximized"])
    check("maximized by choice: every launch, saved bounds or not",
          size(window.command("b", "http://x/", "maximized", remembered=True, maximized=False)), ["--start-maximized"])
    check("a size by choice: that size",
          size(window.command("b", "http://x/", "1280x860", remembered=True, maximized=True)), ["--window-size=1280,860"])
    check("a setting as typed is made valid", window.start_choice(" 1600 X 1000 "), "1600x1000")
    check("  and nonsense is the default", window.start_choice("huge"), "maximized")
    check("  as is a size no screen has", window.start_choice("10x10"), "maximized")

    print("\n-- how it was left, read from the browser's own profile --")
    # Two keys sit side by side in Preferences and only one is this window's.
    # browser.window_placement is a tabbed window's; ELMER's is the entry in
    # browser.app_window_placement. Reading the wrong one said "bounds are
    # remembered" while never noticing they were remembered as maximized, so
    # the flag was never given and the window came up small launch after
    # launch. Here the two disagree on purpose.
    import json as _json
    was_profile = window.PROFILE
    sandbox = Path(os.environ["ELMER_STATE"]) / "window-test"
    (sandbox / "Default").mkdir(parents=True, exist_ok=True)
    window.PROFILE = sandbox
    prefs = sandbox / "Default" / "Preferences"
    tabbed = {"maximized": False, "left": 10, "top": 10, "right": 1060, "bottom": 1058}
    try:
        check("no profile yet: nothing remembered", window.remembered_bounds(), False)
        check("  and nothing to say about maximized", window.left_maximized(), False)
        prefs.write_text(_json.dumps({"browser": {
            "window_placement": tabbed,
            "app_window_placement": {"localhost_/": dict(tabbed, maximized=True)}}}), encoding="utf-8")
        check("the app window's own placement is the one read", window.remembered_bounds(), True)
        check("  left maximized, whatever the tabbed window did", window.left_maximized(), True)
        prefs.write_text(_json.dumps({"browser": {
            "window_placement": dict(tabbed, maximized=True),
            "app_window_placement": {"localhost_/": tabbed}}}), encoding="utf-8")
        check("  left at a size of its own, likewise", window.left_maximized(), False)
        check("  bounds are still remembered", window.remembered_bounds(), True)
        prefs.write_text("{ not json", encoding="utf-8")
        check("an unreadable profile is a first launch, not a crash", window.remembered_bounds(), False)
        prefs.write_text(_json.dumps({"browser": {"app_window_placement": {}}}), encoding="utf-8")
        check("  an empty shelf too", window.remembered_bounds(), False)
    finally:
        window.PROFILE = was_profile

    print("\n-- the setting, kept with the unit's --")
    client0 = appmod.app.test_client()
    local0 = {"REMOTE_ADDR": "127.0.0.1"}
    check("the default: full screen, the way a program opens",
          client0.get("/api/window", environ_base=local0).get_json()["start"], "maximized")
    r = client0.post("/api/window", json={"start": "as-left"}, environ_base=local0)
    check("set to the size it is left at", r.get_json()["start"], "as-left")
    check("  and kept", client0.get("/api/window", environ_base=local0).get_json()["start"], "as-left")
    check("  not from the LAN", client0.post("/api/window", json={"start": "as-left"},
                                             environ_base={"REMOTE_ADDR": "10.0.0.5"}).status_code, 403)

    print("\n-- the watcher --")
    stopped = []
    real = host.stop_main_thread
    host.stop_main_thread = lambda port=None: stopped.append(port)
    try:
        # A process that ends on its own stands in for the window closing.
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.3)"])
        quitting = threading.Event()
        t = window.watch(proc, quitting, 5000)
        t.join(5)
        check("the server is told to stop when the window ends", stopped, [5000])
        stopped.clear()
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.3)"])
        quitting = threading.Event()
        quitting.set()                       # the server is already going
        t = window.watch(proc, quitting, 5000)
        t.join(5)
        check("  but not when it is already stopping", stopped, [])
    finally:
        host.stop_main_thread = real

    print("\n-- closing it from our side --")
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    window.close(proc)
    check("the window is closed", proc.poll() is not None, True)
    window.close(proc)
    check("  and closing it again is nothing", proc.poll() is not None, True)

    print("\n-- an off-site link: a popout of ELMER's own, closed with it --")
    from elmer import kiosk
    cmd = kiosk._window_command(r"C:\\edge\\msedge.exe", "chromium", "https://www.fcc.gov/", Path("p"))
    if os.name == "nt":
        check("on Windows the outside site opens as a popout - app style, no tabs, no address bar",
              cmd[1], "--app=https://www.fcc.gov/")
    else:
        check("on the kiosk it is a normal window with a toolbar", cmd[1:3], ["--new-window", "https://www.fcc.gov/"])
    check("  in a profile of its own, not ELMER's window's", any(a.startswith("--user-data-dir=") for a in cmd), True)
    # The popout stood in for by a process that lasts: nothing opens on the screen.
    real_open = kiosk._window_command
    opened = []
    kiosk._window_command = lambda path, family, url, profile: (opened.append(url) or [sys.executable, "-c", "import time; time.sleep(30)"])
    real_find, real_display = kiosk.find_browser, kiosk.have_display
    kiosk.find_browser, kiosk.have_display = (lambda: (sys.executable, "chromium")), (lambda: True)
    was_window, was_token = appmod.app.config.get("WINDOW"), appmod.app.config["KIOSK_TOKEN"]
    appmod.app.config["WINDOW"], appmod.app.config["KIOSK_TOKEN"] = True, "tok"
    try:
        client1 = appmod.app.test_client()
        r = client1.post("/api/open-external", json={"token": "tok", "url": "https://www.fcc.gov/wireless"}, environ_base=local0)
        check("the ELMER window's page can ask for it", (r.status_code, r.get_json()["opened"]), (200, True))
        check("  and it opened what was asked", opened, ["https://www.fcc.gov/wireless"])
        check("  ELMER keeps hold of it", kiosk.open_windows(), 1)
        check("  not from the LAN", client1.post("/api/open-external", json={"token": "tok", "url": "https://www.fcc.gov/"},
                                                 environ_base={"REMOTE_ADDR": "10.0.0.5"}).status_code, 403)
        check("  not without the token", client1.post("/api/open-external", json={"token": "x", "url": "https://www.fcc.gov/"},
                                                      environ_base=local0).status_code, 403)
        page = client1.get("/away?url=https%3A%2F%2Fwww.fcc.gov%2F&from=/", environ_base=local0).get_data(as_text=True)
        check("  the page offers it beside ELMER", "Open it beside ELMER" in page, True)
        check("  and says Exit takes it too", "Exit closes it along with ELMER" in page, True)
        kiosk.close_windows()
        check("closing with ELMER closes it", kiosk.open_windows(), 0)
    finally:
        kiosk._window_command, kiosk.find_browser, kiosk.have_display = real_open, real_find, real_display
        appmod.app.config["WINDOW"], appmod.app.config["KIOSK_TOKEN"] = was_window, was_token
        kiosk.close_windows()

    print("\n-- who the warning counts --")
    client = appmod.app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    party.close_room()
    check("nobody, with nothing running", client.get("/api/people", environ_base=local).get_json()["total"], 0)
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    room.join("W9ABC")
    room.fill_bots()
    d = client.get("/api/people", environ_base=local).get_json()
    check("two people at this table, on phones", d["here"], 2)
    check("  and the practice players are not people", d["total"], 2)
    room.join("N0SEAT", device="screen")
    d = client.get("/api/people", environ_base=local).get_json()
    check("  somebody seated at the screen itself is not warned about", (room.people_here(), d["here"]), (3, 2))
    client.post("/api/net/open", json={"difficulty": "technician"}, environ_base=local)
    client.post("/api/net/checkin", json={"unit": "pi-9", "name": "Nine", "players": 3, "ready": True},
                environ_base=local)
    client.post("/api/net/checkin", json={"unit": "pi-7", "name": "Seven", "players": 0}, environ_base=local)
    d = client.get("/api/people", environ_base=local).get_json()
    check("a net with a table of three", (d["others"], d["tables"]), (3, 1))
    check("  counted with this table's own", d["total"], 5)
    client.post("/api/net/end", json={}, environ_base=local)
    party.close_room()
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP", device="screen")
    check("one person, at the screen, alone: nothing to warn", client.get("/api/people", environ_base=local).get_json()["total"], 0)
    room.join("W9ABC")                       # on a phone
    check("  a phone at the table is", client.get("/api/people", environ_base=local).get_json()["total"], 1)
    from elmer import golf
    room.book_clubhouse({"difficulty": "technician", "holes": [1, 2, 3], "course": "pebble-beach",
                         "course_name": "Pebble Beach Golf Links", "seconds": 30}, 300)
    check("  but not during golf: the party is on the scorecard", client.get("/api/people", environ_base=local).get_json()["total"], 0)
    room.leave_clubhouse()
    room.fill_bots()
    room.begin_golf(golf.course("pebble-beach"), [1, 2, 3], None, 30)
    check("  in the clubhouse or on the course", client.get("/api/people", environ_base=local).get_json()["total"], 0)
    room.end_golf()
    client.post("/api/net/end", json={}, environ_base=local)
    party.close_room()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    finally:
        from elmer import hall, netcontrol
        hall.halt()
        netcontrol.close_net()
        time.sleep(0.1)
