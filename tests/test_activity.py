#!/usr/bin/env python3
"""A Pi has one job: background work waits while the unit is in use.

    python3 tests/test_activity.py

While a game, a net, a mock exam or a study session is running, the work
nobody at the unit asked for - the spot feed, the FCC's files and their
index, the update check, the weekly report, the GPS watch, reading the
Library's books - waits, and runs when the unit is idle. What is held here:

  - the unit knows when it is busy, and with what, from the state that is
    already there: a game or people at the table, a net, an unfinished mock
    exam started lately, an answer in the last few minutes - and not from an
    exam abandoned hours ago or an answer from before lunch;
  - waiting says so once in the log and once when it goes ahead, and a loop
    told to stop while it waits stops;
  - the FCC download, asked for mid-game, starts when the game is over;
  - the Library reads stale books on its own only when the unit is idle,
    and the button always reads them;
  - the discovery hello no longer asks git who it is every few seconds.
"""
import logging
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
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


def main():
    from elmer import activity, db, netcontrol, party

    print("\n-- the unit knows when it is busy, and with what --")
    check("a fresh unit is idle", activity.busy(fresh=True), None)
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    check("somebody sitting at the table", activity.busy(fresh=True), "people at the table")
    party.close_room()
    check("  and idle again when the table closes", activity.busy(fresh=True), None)

    real_net = netcontrol.net
    netcontrol.net = lambda: object()
    try:
        check("hosting a net", activity.busy(fresh=True), "a net")
    finally:
        netcontrol.net = real_net

    conn = db.connect()
    now = db.utcnow()
    conn.execute("INSERT INTO exam (user_id, pool_id, started, total) VALUES (1, 'tech', ?, 35)",
                 ((now - timedelta(hours=3)).isoformat(),))
    conn.commit()
    check("an exam abandoned three hours ago is not somebody sitting one", activity.busy(conn), None)
    conn.execute("INSERT INTO exam (user_id, pool_id, started, total) VALUES (1, 'tech', ?, 35)",
                 ((now - timedelta(minutes=10)).isoformat(),))
    conn.commit()
    check("a mock exam started ten minutes ago and not finished", activity.busy(conn), "a mock exam")
    conn.execute("UPDATE exam SET finished = ?", (now.isoformat(),))
    conn.commit()

    answer = ("INSERT INTO answer_log (user_id, ts, day, pool_id, question_id, section, correct, mode) "
              "VALUES (1, ?, ?, 'tech', 'T1A01', 'T1A', 1, 'study')")
    conn.execute(answer, ((now - timedelta(minutes=10)).isoformat(), now.date().isoformat()))
    conn.commit()
    check("an answer ten minutes ago is not somebody studying now", activity.busy(conn), None)
    conn.execute(answer, ((now - timedelta(minutes=1)).isoformat(), now.date().isoformat()))
    conn.commit()
    check("an answer a minute ago is", activity.busy(conn), "a study session")
    conn.execute("DELETE FROM answer_log")
    conn.commit()
    conn.close()

    print("\n-- waiting says so, once each way, and can be stopped --")
    said = Said()
    logging.getLogger("elmer").addHandler(said)
    logging.getLogger("elmer").setLevel(logging.INFO)
    real_busy = activity.busy
    answers = iter(["a game at the table", "a game at the table", None])
    activity.busy = lambda *a, **k: next(answers, None)
    try:
        went = activity.wait_until_idle("spot sampling", poll=0.01)
    finally:
        activity.busy = real_busy
    waits = [line for line in said.lines if "spot sampling waits" in line]
    ahead = [line for line in said.lines if "spot sampling goes ahead" in line]
    check("it waited, and went ahead when the unit was idle", went, True)
    check("  saying once that it waits, and for what", (len(waits), "a game at the table" in (waits or [""])[0]), (1, True))
    check("  and once that it goes ahead", len(ahead), 1)
    stop = threading.Event()
    stop.set()
    activity.busy = lambda *a, **k: "a net"
    try:
        check("a loop told to stop while it waits stops", activity.wait_until_idle("x", stop=stop, poll=0.01), False)
    finally:
        activity.busy = real_busy

    print("\n-- the FCC download, asked for mid-game, starts after it --")
    from elmer import uls
    order = []
    real_wait, real_fetch = activity.wait_until_idle, uls.fetch
    activity.wait_until_idle = lambda what, *a, **k: order.append(("wait", what)) or True
    uls.fetch = lambda service: order.append(("fetch", service)) or (True, "stub")
    import os
    was_env = os.environ.get("ELMER_ULS")
    os.environ["ELMER_ULS"] = ""                  # the unit keeping itself current, not a press
    try:
        uls.ensure("amateur")
        for _ in range(100):
            if len(order) >= 2:
                break
            time.sleep(0.05)
    finally:
        activity.wait_until_idle, uls.fetch = real_wait, real_fetch
        if was_env is None:
            os.environ.pop("ELMER_ULS", None)
        else:
            os.environ["ELMER_ULS"] = was_env
    check("it waits for the unit before it fetches", [o[0] for o in order], ["wait", "fetch"])
    order.clear()
    activity.wait_until_idle = lambda what, *a, **k: order.append(("wait", what)) or True
    uls.fetch = lambda service: order.append(("fetch", service)) or (True, "stub")
    try:
        for _ in range(100):                       # the last one's thread has to finish first
            if not uls.fetching("amateur"):
                break
            time.sleep(0.05)
        uls.ensure("amateur", force=True)
        for _ in range(100):
            if order:
                break
            time.sleep(0.05)
    finally:
        activity.wait_until_idle, uls.fetch = real_wait, real_fetch
    check("  a press is somebody asking: it fetches at once", [o[0] for o in order], ["fetch"])

    print("\n-- the Library reads on its own only when the unit is idle --")
    from elmer.app import app
    c = app.test_client()
    activity.busy = lambda *a, **k: "a game at the table"
    try:
        auto = c.post("/api/library/index", json={"auto": True}, environ_base=LOCAL).get_json()
        asked = c.post("/api/library/index", json={}, environ_base=LOCAL).get_json()
    finally:
        activity.busy = real_busy
    check("reading stale books as the page opens waits for a game", auto.get("deferred"), "a game at the table")
    check("  the button is somebody asking, and reads them anyway", ("report" in asked, "deferred" in asked), (True, False))

    print("\n-- the discovery hello does not ask git who it is every few seconds --")
    from elmer import app as appmod, update
    asked_git = []
    real_state = update.state
    update.state = lambda: asked_git.append(1) or {"head": "abc1234"}
    appmod._version_cache["at"] = 0.0
    try:
        heads = [appmod._version_now() for _ in range(5)]
    finally:
        update.state = real_state
    check("five hellos, one question to git", (len(asked_git), heads[-1]), (1, "abc1234"))


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
