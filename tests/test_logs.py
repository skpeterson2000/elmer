"""The log stays readable on a hall night, and a fault can be found by name.

    python3 tests/test_logs.py

The old log held about forty minutes of a hall before the polls rotated the
evening away, and a table pointed at a net that was not running wrote a
WARNING every fifteen seconds all night. These pin the three fixes: polls
are counted and summarised, repeats collapse to one line a minute, and an
unhandled exception carries a reference that the page, the JSON and the
log line all share - and that the log route can find.
"""
import logging
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401
from flask import Flask, jsonify  # noqa: E402
from elmer import logs  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


class Catch(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append((record.levelname, record.getMessage()))


app = Flask("t")
app.config["TESTING"] = False        # so the error handler, not the test client, sees the exception
logs.install_request_logging(app)


@app.route("/api/party/state")
def state():
    return jsonify({"ok": True})


@app.route("/api/thing")
def thing():
    return jsonify({"ok": True})


@app.route("/api/boom")
def boom():
    raise RuntimeError("deliberate")


@app.route("/page/boom")
def page_boom():
    raise RuntimeError("deliberate")


catch = Catch()
http = logging.getLogger("http")
http.addHandler(catch)
http.setLevel(logging.DEBUG)
http.propagate = False
client = app.test_client()

print("\npolls are counted, not written")
# A long window while the fifty go through - a loaded Pi can take longer
# than a fraction of a second over them - then a window of nothing at all.
logs.SUMMARY_EVERY = 60
logs.quiet = logs._Quiet()
for _ in range(50):
    client.get("/api/party/state", headers={"User-Agent": "ELMER/1.0 (big board)"})
check("fifty heartbeats wrote nothing", catch.lines, [])
logs.SUMMARY_EVERY = 0
client.get("/api/party/state")
check("  then one summary line", len(catch.lines), 1)
check("  saying how many, from whom, and the slowest",
      ("51 polls" in catch.lines[0][1], "client" in catch.lines[0][1], "slowest" in catch.lines[0][1]),
      (True, True, True))
catch.lines.clear()
client.get("/api/thing")
check("an ordinary request is written as itself", len(catch.lines) == 1 and "/api/thing -> 200" in catch.lines[0][1], True)
check("  at INFO", catch.lines[0][0], "INFO")

print("\nrepeats collapse")
catch.lines.clear()
logs.REPEAT_WINDOW = 0.3
logs.quiet = logs._Quiet()
for _ in range(6):
    client.post("/api/no-net/checkin", headers={"User-Agent": "ELMER/1.0 (cohort unit)"})
check("six identical refusals wrote one line", len(catch.lines), 1)
check("  at INFO, because ELMER's own component asked and handles it", catch.lines[0][0], "INFO")
time.sleep(0.35)
client.post("/api/no-net/checkin", headers={"User-Agent": "ELMER/1.0 (cohort unit)"})
check("  the next minute says how many were swallowed",
      any("5 more like it" in m for _, m in catch.lines), True)
catch.lines.clear()
client.get("/api/nowhere", headers={"User-Agent": "Mozilla/5.0"})
check("a browser being told 404 is still a WARNING", catch.lines[0][0], "WARNING")

print("\na fault carries a reference")
catch.lines.clear()
r = client.get("/api/boom")
body = r.get_json()
check("the API answers JSON with a reference", (r.status_code, body["error"], body["ref"][:2]),
      (500, "ELMER hit an error", "e-"))
check("  and the log line has the same reference and the traceback",
      any(body["ref"] in m and "deliberate" in m and "UNHANDLED" in m for lvl, m in catch.lines if lvl == "ERROR"), True)
r = client.get("/page/boom")
check("a page says it in a sentence, with the reference",
      (r.status_code, b"Reference <code>e-" in r.data), (500, True))
check("  polls and faults do not share a key", logs.is_poll("/api/boom"), False)
check("  the poll test knows the polling endpoints",
      [logs.is_poll(p) for p in ("/api/party/state?player=3", "/api/net/board", "/api/peers",
                                 "/api/net/checkin", "/api/difficulty")],
      [True, True, True, True, False])

print("\na thread that dies is logged, not lost")
got = []


class Grab(logging.Handler):
    def emit(self, record):
        got.append(record.getMessage())


elog = logging.getLogger("elmer")
grab = Grab()
elog.addHandler(grab)
logs.install_thread_hook()


def die():
    raise ValueError("thread fault")


t = threading.Thread(target=die, name="test-thread")
t.start()
t.join()
check("the thread's death is an ERROR naming it",
      any("THREAD test-thread died" in m and "thread fault" in m for m in got), True)
elog.removeHandler(grab)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
