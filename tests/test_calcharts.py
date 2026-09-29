#!/usr/bin/env python3
"""What calibration has done, drawn from the record - and the record kept small.

    python3 tests/test_calcharts.py

An operator asked whether calibration works as intended, and nothing on the
page could say: a run printed three numbers while it ran and kept only its
table. Every run leaves a year of the model against the sondes, bare and with
its table, and the live forecast keeps its own log; this holds the charts
that read them (calcharts.py) to the record:

  - a run is found by its replay folders - bare and with the table - and a
    lone bare folder (a stopped run, a command-line hindcast) is not a run;
  - its summary scores each folder at the 24-hour lead and by month, with
    known errors coming back as themselves, and is kept and read back;
  - the older runs' folders are removed once their summaries are kept, and
    the latest run's are not;
  - the live chart takes, for each measured hour, the forecast made at the
    longest lead from 6 to 24 hours, and the model's own figure where the
    forecast logged it - which the forecast now does, before the unit's
    corrections;
  - the route answers with all of it, and the page draws four charts, each
    with its reading, and says the table's flags for what they are.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
import _browser  # noqa: E402
from elmer import calcharts, forecastlog, hindcast, propagation  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
END = datetime(2026, 9, 20, 0, 0, tzinfo=timezone.utc)
START = END - timedelta(days=10)


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def write_ledger(folder, error, days=10, end=END, model_offset=None):
    """A ledger of `days` days: the sondes read 10 MHz every hour, and every
    forecast is off by `error` MHz at every lead."""
    forecastlog.use(folder, keep_days=100000)
    try:
        t = end - timedelta(days=days)
        while t < end:
            hours = [(t + timedelta(hours=k)) for k in range(25)]
            bands = [{"band": "20m", "hours": [{"at": h.isoformat(), "muf": 10.0 + error, "regime": "lit", "score": 50,
                                                 "muf_model": (10.0 + error + model_offset) if model_offset is not None else None}
                                                for h in hours]}]
            forecastlog.record(bands, {"sfi": 100}, "test", now=t)
            forecastlog.measured({"muf": 10.0, "muf_source": "measured", "regime": "lit"}, now=t)
            t += timedelta(hours=1)
    finally:
        forecastlog.use(None)


def the_runs():
    print("\n-- runs, from their folders --")
    base = hindcast.CACHE
    old = f"{START:%Y%m%d}-{END:%Y%m%d}-aaa"
    new = f"{START:%Y%m%d}-{END:%Y%m%d}-bbb"
    write_ledger(base / f"ledger-{old}", 2.0)
    write_ledger(base / f"ledger-{old}+cal", 1.0)
    time.sleep(1.1)                      # the newer run is newer on the clock too
    write_ledger(base / f"ledger-{new}", -1.5)
    write_ledger(base / f"ledger-{new}+cal", 0.5)
    write_ledger(base / f"ledger-{new}+held", -0.5)
    write_ledger(base / f"ledger-{START:%Y%m%d}-{END:%Y%m%d}-lonely", 3.0)
    runs = calcharts.runs_on_disk()
    check("two runs, oldest first; a bare folder alone is not a run", [r["key"] for r in runs], [old, new])
    check("  the newer has the table that was in force", (runs[0]["held"] is None, runs[1]["held"] is not None), (True, True))
    s = calcharts.summarize(runs[1])
    check("its 24-hour error, bare, with the new table and with the old",
          (s["bare"]["lead24"]["mae"], s["cal"]["lead24"]["mae"], s["held"]["lead24"]["mae"]), (1.5, 0.5, 0.5))
    check("  and the bias, signed", (s["bare"]["lead24"]["bias"], s["cal"]["lead24"]["bias"]), (-1.5, 0.5))
    check("  month by month", sorted(s["bare"]["by_month"]), ["2026-09"])
    check("the summary is kept", (calcharts.SUMMARIES / f"{new}.json").is_file(), True)
    check("  and read back rather than worked out again", calcharts.summarize(runs[1])["made"], s["made"])

    print("\n-- the older runs' folders let go, their summaries kept --")
    removed = calcharts.prune(new)
    check("the older run's two folders removed", sorted(removed), sorted([f"ledger-{old}", f"ledger-{old}+cal"]))
    check("  the newer run's three kept", [r["key"] for r in calcharts.runs_on_disk()], [new])
    check("  and the lone bare folder, which is no run, left alone",
          (base / f"ledger-{START:%Y%m%d}-{END:%Y%m%d}-lonely").is_dir(), True)
    check("both runs are still in the summaries", [x["key"] for x in calcharts.summaries()], [old, new])


def the_live():
    print("\n-- the live forecast, a day ahead --")
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    target = now - timedelta(hours=2)
    for lead, said, model in ((30, 99.0, None), (24, 11.0, 12.0), (8, 10.5, None), (3, 10.0, None)):
        t = target - timedelta(hours=lead)
        hours = [(t + timedelta(hours=k)) for k in range(31)]
        bands = [{"band": "20m", "hours": [{"at": h.isoformat(), "muf": said if h == target else 9.0,
                                             "muf_model": model if h == target else None,
                                             "regime": "lit", "score": 50} for h in hours]}]
        forecastlog.record(bands, {"sfi": 100}, "test", now=t)
    forecastlog.measured({"muf": 10.2, "muf_source": "measured", "regime": "lit"}, now=target)
    # and the hour after, so the live chart has a line to draw
    forecastlog.measured({"muf": 9.4, "muf_source": "measured", "regime": "lit"}, now=target + timedelta(hours=1))
    pts = [p for p in calcharts.live(now=now)["points"] if p["t"] == forecastlog._hour(target.isoformat())]
    check("the forecast at the longest lead from 6 to 24 hours - not 30, not 3",
          [(p["lead"], p["forecast"], p["measured"]) for p in pts], [(24, 11.0, 10.2)])
    check("  with the model's own figure, where it was logged", [p["model"] for p in pts], [12.0])

    print("\n-- the forecast logs the model before the unit's corrections --")
    cell = {"factor": 1.5, "applied": True}
    table = {"months": {m: {"lit": cell, "gray": cell, "dark": cell}
                        for m in [f"{k:02d}" for k in range(1, 13)]}}
    hours = propagation.outlook(14.2, 46.6, -94.3, 120.0, hours=6, calibration=table)
    moved = [h for h in hours if h.get("muf_model") and h["muf"] != h["muf_model"]]
    check("each hour carries the model's figure, and calibration moves the issued one off it", bool(moved), True)
    e = forecastlog.latest(days=3) or {}
    check("the log keeps it beside what was issued", "mufs_model" in e, True)


def the_page():
    print("\n-- the route and the page --")
    from elmer import app as appmod
    from elmer.app import app
    appmod._prefetch_regional = lambda place: None
    c = app.test_client()
    c.set_cookie("elmer_user", "1")
    forecastlog.save_calibration({"made": END.isoformat(), "days": 365, "months": {
        "01": {"lit": {"factor": 1.12, "measured": 1.12, "n": 268, "applied": True, "small": False, "bounded": False},
               "gray": {"factor": 1.0, "measured": 1.08, "n": 56, "applied": False, "small": True, "bounded": False},
               "dark": {"factor": 1.0, "measured": 0.9, "n": 30, "applied": False, "small": False, "bounded": False}}}})
    d = c.get("/api/calibrate/charts", environ_base=LOCAL).get_json()
    check("the route answers with the table, the runs and the live forecast",
          (d["ok"], len(d["runs"]), bool(d["live"]["points"]), sorted(d["table"]["months"])), (True, 2, True, ["01"]))
    check("chromium is on this machine", bool(_browser.available()), True)
    if not _browser.available():
        return
    port = _browser._free_port()
    server = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\nfrom elmer import app as appmod\n"
         "appmod._prefetch_regional = lambda place: None\n"
         "appmod.app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)" % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        js = """new Promise(async r => {
          const until = (f, ms) => new Promise(res => { const t0 = Date.now(); const go = () => (f() || Date.now() - t0 > ms) ? res(f()) : setTimeout(go, 100); go(); });
          await until(() => document.querySelectorAll('#calc-body .calc-chart').length === 4, 20000);
          r(JSON.stringify({charts: [...document.querySelectorAll('#calc-body .calc-chart')].map(c => c.id),
                            svgs: document.querySelectorAll('#calc-body svg').length,
                            tables: document.querySelectorAll('#calc-body details table').length,
                            table: (document.querySelector('#calc-table .read') || {}).innerText || ''}));
        })"""
        got = json.loads(_browser.evaluate(f"http://127.0.0.1:{port}/propagation", js, settle=0.5,
                                           cookies={"elmer_user": "1"}) or "{}")
        check("four charts, each drawn and each with a table",
              (got.get("charts"), got.get("svgs"), got.get("tables")),
              (["calc-live", "calc-months", "calc-table", "calc-runs"], 4, 4))
        read = got.get("table") or ""
        check("the table's flags said for what they are: applied, within ten percent, too few hours",
              ("1 of 3 were applied" in read, "1 were within ten percent" in read, "1 had too few hours" in read), (True, True, True))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    the_runs()
    the_live()
    the_page()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
