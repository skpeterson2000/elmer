#!/usr/bin/env python3
"""A Pi has one job: background work waits while the unit is in use.

    python3 tests/test_activity.py

While a game, a net, a mock exam or a study session is running, the work
nobody at the unit asked for - the spot feed, the FCC's files and their
index, the update check, the weekly report, the GPS watch, reading the
Library's books - waits, and runs when the unit is idle. What is held here:

  - the unit knows when it is busy, and with what: a game or people at the
    table, a net, a mock exam, each only while somebody is doing something
    at it - play, an answer, a join or a press in the last ten minutes -
    and an answer in the last few minutes; not a table left seated with
    nobody pressing anything for eleven minutes, not an exam whose answers
    stopped, not an exam abandoned hours ago, not an answer from before lunch;
  - a press is heard where people press: the table's and the net's routes,
    a table joining the net, a table reporting people's answers (not a
    timer's), and the exam page saying an answer was given;
  - waiting says so once in the log and once when it goes ahead, and a loop
    told to stop while it waits stops;
  - a job that has waited more than a day runs at the first five quiet
    minutes rather than waiting for ten, and the log says it ran on the
    backstop;
  - when a job began waiting survives a restart: it is written to the
    operator's state once as the wait begins and once as the job runs, never
    per check, and a job that began waiting 25 hours ago, before a restart,
    runs at the first five quiet minutes after it;
  - the FCC download, asked for mid-game, starts when the game is over;
  - the Library reads stale books on its own only when the unit is idle,
    and the button always reads them;
  - the discovery hello no longer asks git who it is every few seconds.
"""
import importlib
import json
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
    from elmer.app import app
    c = app.test_client()

    # The clock the presses are stamped with, moved by hand.
    clock = [1000.0]
    real_clock = activity._clock
    activity._clock = lambda: clock[0]

    def later(seconds):
        clock[0] += seconds

    print("\n-- the unit knows when it is busy, and with what --")
    check("a fresh unit is idle", activity.busy(fresh=True), None)
    c.post("/api/party/open", json={"cohorts": 1}, environ_base=LOCAL)
    c.post("/api/party/join", json={"name": "KC9SP", "device": "phone"}, environ_base=LOCAL)
    check("somebody who has just sat down at the table", activity.busy(fresh=True), "people at the table")
    later(9 * 60)
    check("  nine minutes later, still", activity.busy(fresh=True), "people at the table")
    later(2 * 60)
    check("a table seated with no activity for 11 minutes is idle", activity.busy(fresh=True), None)
    c.post("/api/party/next", json={}, environ_base=LOCAL)
    check("  and busy again the moment somebody presses something there",
          activity.busy(fresh=True), "people at the table")
    c.get("/api/party/state", environ_base=LOCAL)
    later(11 * 60)
    c.get("/api/party/state", environ_base=LOCAL)
    check("  a page polling the table is not somebody playing at it", activity.busy(fresh=True), None)
    party.close_room()
    activity.touch("table")
    check("  and a closed table is idle, pressed or not", activity.busy(fresh=True), None)

    netcontrol.net(create=True, name="Test Net")
    try:
        later(11 * 60)
        check("a net hosted with nobody doing anything in it for 11 minutes is idle",
              activity.busy(fresh=True), None)
        r = c.post("/api/net/mode", json={"mode": "tournament"}, environ_base=LOCAL)
        check("hosting a net, and pressing something in it",
              (r.status_code, activity.busy(fresh=True)), (200, "a net"))
        later(11 * 60)
        c.post("/api/net/checkin", json={}, environ_base=LOCAL)
        check("  a table's check-in every second is not somebody in the net",
              activity.busy(fresh=True), None)
    finally:
        netcontrol.close_net()

    hall = netcontrol.Net(name="Test Net")
    later(11 * 60)
    hall.check_in("pi-kitchen", name="Kitchen", players=2)
    check("a table joining the net is the net in use", activity.quiet_for("net"), 0.0)
    later(11 * 60)
    hall.check_in("pi-kitchen", name="Kitchen", players=2)
    check("  the same table checking in again is not", activity.quiet_for("net"), 11 * 60.0)
    hall.round, hall.round_number = {"question_id": "T1A01"}, 1
    hall.report("pi-kitchen", 1, [{"name": "BOT-1", "correct": True, "ms": 900, "bot": "easy"}])
    check("  a table of practice bots reporting is not people answering",
          activity.quiet_for("net"), 11 * 60.0)
    hall.results.clear()
    hall.report("pi-kitchen", 1, [{"name": "KC9SP", "correct": True, "ms": 4200}])
    check("  a table reporting its people's answers is", activity.quiet_for("net"), 0.0)

    conn = db.connect()
    now = db.utcnow()
    conn.execute("INSERT INTO exam (user_id, pool_id, started, total) VALUES (1, 'tech', ?, 35)",
                 ((now - timedelta(hours=3)).isoformat(),))
    conn.commit()
    check("an exam abandoned three hours ago is not somebody sitting one", activity.busy(conn), None)
    conn.execute("INSERT INTO exam (user_id, pool_id, started, total) VALUES (1, 'tech', ?, 35)",
                 ((now - timedelta(minutes=10)).isoformat(),))
    conn.commit()
    later(11 * 60)
    check("a mock exam started ten minutes ago whose answers are not arriving",
          activity.busy(conn), None)
    exam_id = conn.execute("SELECT MAX(id) FROM exam").fetchone()[0]
    r = c.post(f"/api/exam/{exam_id}/answering", environ_base=LOCAL)
    check("  the exam page saying an answer was given", (r.status_code, r.get_data()), (204, b""))
    check("  and now it is somebody sitting one", activity.busy(conn), "a mock exam")
    later(11 * 60)
    check("  and eleven minutes after the last answer, it is not", activity.busy(conn), None)
    activity.touch("exam")
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
    exam_js = (Path(__file__).resolve().parents[1] / "elmer" / "static" / "exam.js").read_text(encoding="utf-8")
    ping = exam_js[exam_js.index("function answering()"):]
    ping = ping[:ping.index("}\n") + 1]
    check("the exam page pings on every answer, and sends nothing in it",
          ("answers[pos] = +b.dataset.n; answering();" in exam_js,
           "/answering'" in ping, "body" in ping), (True, True, False))

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

    print("\n-- a job deferred for a day runs at the first five quiet minutes --")
    # A table somebody pressed at seven minutes ago: busy by the ten-minute
    # rule, quiet by the backstop's five. Both clocks move an hour a poll.
    wall = [1_790_000_000.0]
    real_wall = activity._wall
    activity._wall = lambda: wall[0]
    room = party.room(create=True, cohorts=1)
    room.join("KC9SP")
    said.lines.clear()

    def stamp_seven_minutes_ago():
        activity._last["table"] = clock[0] - 7 * 60

    stamp_seven_minutes_ago()
    check("a table somebody pressed at seven minutes ago is busy", activity.busy(fresh=True), "people at the table")

    class Polls:
        """Each poll is an hour, and somebody pressed seven minutes before it."""
        def __init__(self, limit):
            self.n, self.limit = 0, limit

        def wait(self, _):
            self.n += 1
            clock[0] += 3600
            wall[0] += 3600
            stamp_seven_minutes_ago()
            return self.n >= self.limit

    under = Polls(limit=23)
    check("  a job that has waited under a day keeps waiting",
          activity.wait_until_idle("the weekly field report", stop=under), False)
    check("  and it did not run on the backstop", [line for line in said.lines if "backstop" in line], [])
    said.lines.clear()
    stamp_seven_minutes_ago()
    over = Polls(limit=48)
    went = activity.wait_until_idle("the update check", stop=over)
    check("a job deferred for over 24 hours runs at the first idle window", (went, over.n), (True, 24))
    check("  the log says it ran on the backstop",
          len([line for line in said.lines if "the update check goes ahead on the backstop" in line]), 1)
    said.lines.clear()

    print("\n-- when a job began waiting survives a restart --")
    writes = []

    def counting(module):
        real_write = module._write_deferred

        def write():
            writes.append(dict(module._deferred_mem))
            real_write()
        module._write_deferred = write

    def on_disk():
        try:
            return json.loads(activity.DEFERRED.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    check("a job that ran is off the record", "the update check" in on_disk(), False)
    counting(activity)
    began = wall[0]
    stamp_seven_minutes_ago()
    five = Polls(limit=5)
    check("the FCC file waits for the table, and the unit is stopped five hours in",
          (activity.wait_until_idle("the FCC amateur file", stop=five), five.n), (False, 5))
    check("  when it began waiting is in the operator's state",
          on_disk().get("the FCC amateur file"), began)
    check("  written once as the wait began, not once a check", len(writes), 1)

    # The restart: the module comes back from nothing, with nothing in memory.
    activity = importlib.reload(activity)
    activity._clock = lambda: clock[0]
    activity._wall = lambda: wall[0]
    counting(activity)
    writes.clear()
    wall[0] = began + 25 * 3600
    clock[0] += 20 * 3600
    stamp_seven_minutes_ago()
    check("after the restart the table is still busy by the ten-minute rule",
          activity.busy(fresh=True), "people at the table")
    fresh_job = Polls(limit=1)
    check("  a job that has only just begun waiting waits",
          activity.wait_until_idle("spot sampling", stop=fresh_job), False)
    writes.clear()
    said.lines.clear()
    after = Polls(limit=5)
    went = activity.wait_until_idle("the FCC amateur file", stop=after)
    check("a job that began waiting 25 hours ago, across a restart, runs at the first 5 idle minutes",
          (went, after.n), (True, 0))
    check("  the log says it ran on the backstop",
          len([line for line in said.lines if "the FCC amateur file goes ahead on the backstop" in line]), 1)
    check("  and it is off the record, in one write",
          ("the FCC amateur file" in on_disk(), len(writes)), (False, 1))
    activity._end("spot sampling")
    activity._end("the weekly field report")
    activity._end("x")
    said.lines.clear()
    party.close_room()
    activity._clock = real_clock
    activity._wall = real_wall

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
