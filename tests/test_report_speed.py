#!/usr/bin/env python3
"""The problem report and the doctor say where their time goes, and do not
spend it twice.

    python3 tests/test_report_speed.py

On a fast laptop POST /api/report took six to nine seconds and /api/doctor
five and a half. The time was the self-check, and a report that was
written and then sent ran it twice. What is held here:

  - each check's time is on its own lines, and the report says what the
    self-check took and which checks were slowest;
  - sending the report just written sends that file, not a new build -
    unless the words or the callsign box changed since, when it is written
    again from them;
  - the doctor takes the GPS from the server's own watch when that has
    looked recently, rather than waiting up to five seconds on gpsd; with
    no recent look it asks the receiver as before;
  - the space weather feed is asked once, kept, and asked again in the
    background when the answer is old - the doctor never waits on it twice.

Nothing here reaches the network: the feed, the receiver and the send are
stand-ins.
"""
import sys
import threading
import time
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


def main():
    from elmer import bugreport, db, diagnostics as D, gps, home as wayhome
    asked = {"n": 0, "fail": None}

    def fake_ask():
        asked["n"] += 1
        with D._internet_lock:
            D._internet["at"], D._internet["error"] = time.time(), asked["fail"]
    real_ask, D._ask_internet = D._ask_internet, fake_ask
    real_read = gps.read_fix
    reads = {"n": 0}

    def fake_read(host=None, port=None, timeout=None):
        reads["n"] += 1
        return None
    gps.read_fix = fake_read
    try:
        print("\n-- each check's time, and where the self-check's went --")
        rows = D.collect()
        check("every line carries its check's time", all("ms" in r for r in rows), True)
        conn = db.connect()
        text, _ = bugreport.build(conn, lines=10)
        check("the report says what the self-check took",
              "  -> the self-check took " in text and "; slowest " in text, True)
        line = next((ln for ln in text.splitlines() if ln.startswith("  [") and " ms)" in ln), "")
        check("  and each line its own time", bool(line), True)

        print("\n-- the feed is asked once and kept --")
        D._internet.update(at=0.0, error=None)
        asked["n"] = 0
        D._collected = []
        D.check_internet()
        check("the first look in a server asks, there being nothing kept", asked["n"], 1)
        D.check_internet()
        check("  a fresh answer is used as it stands", asked["n"], 1)
        D._internet["at"] = time.time() - D.INTERNET_FRESH_S - 60
        D._collected = []
        D.check_internet()
        said = D._collected[-1]
        D._collected = None
        t = D._internet["thread"]
        if t is not None:
            t.join(5)
        check("  an old one is used at once, and asked again behind it",
              (said["state"], "as of 11 min ago" in said["detail"], asked["n"]), ("ok", True, 2))
        D._internet["at"] = 0.0
        asked["fail"] = OSError("no route")
        D.check_internet()          # --doctor at a terminal: asked, and said
        check("  --doctor at a terminal asks for itself", asked["n"], 3)
        asked["fail"] = None

        print("\n-- the GPS from the server's own watch --")
        stop = threading.Event()
        watch = threading.Thread(target=stop.wait, daemon=True)
        watch.start()
        saved = (dict(gps._watch), list(gps._history), dict(gps._last))
        try:
            gps._watch["thread"] = watch
            gps._history[:] = [{"t": time.time(), "located": True}]
            gps._last.update(at=time.time(), fix={
                "lat": 46.6, "lon": -94.3, "mode": 3, "read_at": time.time(),
                "source": "gps", "from": "127.0.0.1:2947"})
            reads["n"] = 0
            D._collected = []
            D.check_gps()
            got = [r for r in D._collected if r["label"] == "GPS"]
            D._collected = None
            check("a recent look from the watch is the answer, gpsd not asked again",
                  (reads["n"], bool(got) and "3D fix" in got[0]["detail"]), (0, True))
            gps._history[:] = []
            D._collected = []
            D.check_gps()
            D._collected = None
            check("  with no recent look, the receiver is asked as before", reads["n"], 1)
        finally:
            stop.set()
            gps._watch.clear(); gps._watch.update(saved[0])
            gps._history[:] = saved[1]
            gps._last.clear(); gps._last.update(saved[2])

        print("\n-- sending the report just written sends that file --")
        from elmer.app import app
        c = app.test_client()
        sent, builds = [], {"n": 0}
        real_deliver, real_build = wayhome.deliver, bugreport.build

        def counting_build(*a, **k):
            builds["n"] += 1
            return real_build(*a, **k)
        wayhome.deliver = lambda subject, text, kind="report": (sent.append(text) or True, "stand-in")
        bugreport.build = counting_build
        try:
            body = {"said": "the band plan went blank", "kind": "problem", "station": False}
            wrote = c.post("/api/report", json=body, environ_base=LOCAL).get_json()
            name = Path(wrote["path"]).name
            check("writing builds it once", builds["n"], 1)
            got = c.post("/api/report", json={**body, "send": True, "report": name},
                         environ_base=LOCAL).get_json()
            check("  sending it names the file and builds nothing",
                  (builds["n"], got.get("sent"), Path(got["path"]).name), (1, True, name))
            check("  and what went is what was written, word for word",
                  sent[-1] == Path(wrote["path"]).read_text(encoding="utf-8"), True)
            c.post("/api/report", json={**body, "said": "changed my mind", "send": True},
                   environ_base=LOCAL)
            check("words changed since: written again from them", builds["n"], 2)
            c.post("/api/report", json={**body, "send": True, "report": "../elmer.log"},
                   environ_base=LOCAL)
            check("  a name that is not one of ours is not read - it is written afresh",
                  (builds["n"], "elmer.log" in sent[-1][:200]), (3, False))
        finally:
            wayhome.deliver, bugreport.build = real_deliver, real_build
        conn.close()
    finally:
        D._ask_internet, gps.read_fix = real_ask, real_read
        D._collected = None

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
