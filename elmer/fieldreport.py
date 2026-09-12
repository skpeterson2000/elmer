"""The field report: a card home, once a week, if the operator says so.

KC9SP asked for two things of the fleet's forecast: that a unit teach itself
the correction its own sky needs, and that it report the correction back -
"that will show us what to look for". This is the report. It carries what a
maintainer needs to see the forecast's skill in the field and nothing that
names a station:

* which build, on what machine, up how long;
* the forecast against the sondes over the week - error by lead and by
  sky, with persistence beside it as the yardstick it has to beat;
* the correction the unit has learned, by sky, and whether it is applying
  it; which months its calibration covers;
* how many hall rounds and study answers the week had, as counts;
* the errors and warnings, counted, and the last few of them in full -
  redacted the same way a problem report is (callsign, grid, coordinates,
  network addresses, home directories out).

It is **off** until the operator turns it on, the switch says exactly what
the report contains, every report is written to the state directory before
it is sent so it can be read, and the last one written is a click away. It
goes through the operator's own outgoing-mail settings (mail.py) to the
project's address, and nowhere else.
"""
import json
import logging
import platform
import threading
import time
from datetime import datetime, timezone

from . import bugreport, forecastlog, mail
from .paths import STATE

log = logging.getLogger("elmer")

SETTINGS = STATE / "fieldreport.json"
REPORTS = STATE / "reports"
EVERY_DAYS = 7
CHECK_EVERY = 3600                  # how often the clock is looked at
FIRST_CHECK_DELAY = 300             # let the unit finish starting first
KEEP = 12                           # reports kept on the unit
LEAD_PICKS = (1, 6, 12, 24)
STARTED = time.time()

WHAT_IT_SENDS = (
    "Once a week ELMER sends the project a field report: which build and "
    "machine, how the forecast did against the sondes this week (error by "
    "lead and by sky, with persistence as the yardstick), the correction "
    "this unit has learned and whether it is applying it, how many hall "
    "rounds and study answers there were - as counts - and the errors and "
    "warnings, counted, with the last few in full. Your callsign, grid "
    "square, coordinates, network addresses and home directory are taken "
    "out before it is written. Every report is saved here first so you can "
    "read it, and it goes to " + mail.CONTACT + " through the outgoing-mail "
    "settings on this unit. It is off until you turn it on."
)


def settings():
    try:
        data = json.loads(SETTINGS.read_text())
    except (OSError, ValueError):
        data = {}
    return {"opt_in": bool(data.get("opt_in")),
            "last_sent": data.get("last_sent"),
            "last_result": data.get("last_result"),
            "every_days": int(data.get("every_days") or EVERY_DAYS)}


def _save(data):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(data, indent=1))


def set_opt_in(wanted):
    data = settings()
    data["opt_in"] = bool(wanted)
    _save(data)
    log.info("field report: %s", "on - once a week" if data["opt_in"] else "off")
    return data


def due(now=None):
    s = settings()
    if not s["opt_in"]:
        return False
    now = time.time() if now is None else now
    last = s.get("last_sent") or 0
    return now - last >= s["every_days"] * 86400


# ------------------------------------------------------------------ build

def _fmt(summary):
    if not summary or not summary.get("n"):
        return "no readings"
    return f"n {summary['n']:4d}  bias {summary['bias']:+5.2f}  mae {summary['mae']:4.2f} MHz"


def build(conn=None, now=None):
    """The report as text. Redacted the way a problem report is."""
    now = now or datetime.now(timezone.utc)
    stamp = bugreport.build_stamp()
    out = []
    add = out.append
    add("ELMER field report")
    add("=" * 60)
    add(f"written    {now.strftime('%Y-%m-%d %H:%M UTC')}")
    add(f"build      {stamp['commit']} on {stamp['branch']}, dated {stamp['dated']}")
    if stamp["modified"]:
        add("           NOTE: tracked files differ from the repository")
    add(f"machine    {platform.system()} {platform.release()} {platform.machine()}, "
        f"python {platform.python_version()}")
    up = time.time() - STARTED
    add(f"up         {up / 3600:.1f} h this run")

    # -- the forecast against the sky
    add("")
    add("forecast against the sondes, last 7 days (forecast - measured)")
    add("-" * 60)
    try:
        skill = forecastlog.skill(7, now)
        if not skill["n"]:
            add("  no graded hours yet - the ledger is under a day old, or no sonde was in reach")
        else:
            for lead in LEAD_PICKS:
                s = skill["by_lead"].get(str(lead))
                if s:
                    add(f"  {lead:2d} h lead      {_fmt(s)}")
            for regime in ("lit", "grey", "twilight", "dark"):
                s = skill["by_regime"].get(regime)
                if s:
                    add(f"  {regime:14s} {_fmt(s)}")
            add(f"  persistence 24 h {_fmt(skill['persistence_24h'])}  (the yardstick)")
            latest = skill.get("latest")
            if latest:
                add(f"  latest: said {latest['forecast']} for {latest['at']} "
                    f"({latest['lead_h']} h out); the sondes read {latest['measured']}")
    except Exception as exc:                     # a report never fails on its own subject
        add(f"  could not be read ({type(exc).__name__}: {exc})")

    add("")
    add("what this unit has learned")
    add("-" * 60)
    try:
        adj = forecastlog.adjustment(now=now)
        if not adj:
            add("  no adjustment yet")
        for regime, row in sorted((adj or {}).items()):
            add(f"  {regime:10s} measured bias {row['measured_bias']:+5.2f} MHz over "
                f"{row['n']} h -> applying {row['applied']:+5.2f}"
                + ("  (capped)" if row.get("capped") else "")
                + ("" if row.get("enough") else "  (too few to apply)"))
        table = forecastlog.calibration()
        if table:
            months = sorted((table.get("months") or {}).keys())
            add(f"  calibration covers {len(months)} month(s): {', '.join(months)}; "
                f"made {table.get('made', '?')} over {table.get('days', '?')} days")
            month = now.strftime("%m")
            cells = forecastlog.month_cells((table.get("months") or {}).get(month) or {})
            for sky, cell in sorted(cells.items()):
                add(f"    this month, {sky:8s} factor {cell['factor']:.3f} over {cell['n']} h"
                    + ("" if cell.get("applied") else "  (not applied)"))
        else:
            add("  never calibrated")
    except Exception as exc:
        add(f"  could not be read ({type(exc).__name__}: {exc})")

    # -- the week's use, as counts
    add("")
    add("the week, in counts")
    add("-" * 60)
    if conn is not None:
        since = time.time() - 7 * 86400
        try:
            rounds = conn.execute(
                "SELECT COUNT(DISTINCT ts) c, COUNT(*) a, "
                "SUM(CASE WHEN correct THEN 1 ELSE 0 END) r "
                "FROM hall_log WHERE ts >= ?", (since,)).fetchone()
            add(f"  hall: {rounds['c'] or 0} round(s), {rounds['a'] or 0} answers, "
                f"{rounds['r'] or 0} correct")
        except Exception:
            add("  hall: no log")
        try:
            study = conn.execute(
                "SELECT COUNT(*) a, SUM(CASE WHEN correct THEN 1 ELSE 0 END) r "
                "FROM answer_log WHERE ts >= ?", (since,)).fetchone()
            add(f"  study: {study['a'] or 0} answers, {study['r'] or 0} correct")
        except Exception:
            add("  study: no log")
    else:
        add("  (no database open)")

    # -- the log's complaints
    add("")
    body = bugreport._tail(bugreport.LOG, 3000)
    errors = [ln for ln in body if " ERROR " in ln or "UNHANDLED" in ln]
    # A browser asking for a favicon the kiosk does not have is not a
    # warning anybody wants to read twelve of.
    warnings = [ln for ln in body if " WARNING " in ln and "favicon.ico" not in ln]
    drifts = [ln for ln in body if "forecast: the outlook moved" in ln]
    add(f"errors {len(errors)}, warnings {len(warnings)}, forecast drift notes "
        f"{len(drifts)} in the last {len(body)} log lines")
    add("-" * 60)
    out.extend(errors[-10:] or ["  (no errors)"])
    out.extend(warnings[-10:])
    out.extend(drifts[-3:])

    text = "\n".join(out) + "\n"
    callsign, places = None, []
    if conn is not None:
        try:
            from . import db
            profile = db.get_profile(conn)
            callsign = profile["callsign"]
            spot = profile["settings"].get("location") or {}
            places = [spot.get("short"), spot.get("name"), spot.get("grid")]
        except Exception:
            pass
    return bugreport.redact(text, callsign, places)


def write(conn=None, now=None):
    """Save the report on the unit first. Returns (path, text)."""
    text = build(conn, now)
    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / time.strftime("field-report-%Y%m%d-%H%M%S.txt")
    path.write_text(text)
    old = sorted(REPORTS.glob("field-report-*.txt"))
    for stale in old[:-KEEP]:
        try:
            stale.unlink()
        except OSError:
            pass
    return path, text


def latest():
    """The last report written here, for the page to show."""
    found = sorted(REPORTS.glob("field-report-*.txt"))
    if not found:
        return None
    path = found[-1]
    try:
        return {"path": str(path), "text": path.read_text(),
                "written": path.stat().st_mtime}
    except OSError:
        return None


def send_now(conn=None, reason="weekly"):
    """Write and send. Returns a dict the page can show; never raises."""
    path, text = write(conn)
    stamp = bugreport.build_stamp().get("commit") or "unknown"
    subject = f"ELMER field report - build {stamp} - {time.strftime('%Y-%m-%d')}"
    ok, detail = mail.send(subject, text)
    data = settings()
    data["last_result"] = {"at": time.time(), "sent": ok, "detail": detail,
                           "path": str(path), "reason": reason}
    if ok:
        data["last_sent"] = time.time()
    _save(data)
    log.info("field report %s: %s (%s)", "sent" if ok else "not sent", detail, path.name)
    return {"sent": ok, "detail": detail, "path": str(path), "text": text}


# ------------------------------------------------------------------ clock

def watch(open_conn, interval=CHECK_EVERY, delay=FIRST_CHECK_DELAY):
    """Look at the clock once an hour; send when a week is up and the switch
    is on. `open_conn` returns a fresh database connection - this runs in
    its own thread and must not borrow a request's."""
    def run():
        first = True
        while True:
            time.sleep(delay if first else interval)
            first = False
            try:
                if due():
                    conn = open_conn()
                    try:
                        send_now(conn)
                    finally:
                        conn.close()
            except Exception as exc:                  # never let the clock die
                log.warning("field report: %s: %s", type(exc).__name__, exc)
    thread = threading.Thread(target=run, name="field-report", daemon=True)
    thread.start()
    return thread
