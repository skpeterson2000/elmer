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
import subprocess
import sys
import threading
import time
from pathlib import Path

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

    print("\n-- how it opens: the person's preference, and a first launch's offer --")
    size = lambda c: [a for a in c if a.startswith("--window-size") or a == "--start-maximized"]  # noqa: E731
    check("nothing saved yet: maximised, as the offer",
          size(window.command("b", "http://x/", "as-left", remembered=False)), ["--start-maximized"])
    check("bounds saved, left as they were: nothing said",
          size(window.command("b", "http://x/", "as-left", remembered=True)), [])
    check("maximised by choice: every launch, saved bounds or not",
          size(window.command("b", "http://x/", "maximized", remembered=True)), ["--start-maximized"])
    check("a size by choice: that size",
          size(window.command("b", "http://x/", "1280x860", remembered=True)), ["--window-size=1280,860"])
    check("a setting as typed is made valid", window.start_choice(" 1600 X 1000 "), "1600x1000")
    check("  and nonsense is the default", window.start_choice("huge"), "as-left")
    check("  as is a size no screen has", window.start_choice("10x10"), "as-left")

    print("\n-- the setting, kept with the unit's --")
    client0 = appmod.app.test_client()
    local0 = {"REMOTE_ADDR": "127.0.0.1"}
    check("the default", client0.get("/api/window", environ_base=local0).get_json()["start"], "as-left")
    r = client0.post("/api/window", json={"start": "maximized"}, environ_base=local0)
    check("set to maximised", r.get_json()["start"], "maximized")
    check("  and kept", client0.get("/api/window", environ_base=local0).get_json()["start"], "maximized")
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
