"""What calibration has done, as numbers a chart can draw.

An operator asked whether calibration works as intended, and nothing on the
page could say: a run printed three numbers while it ran and kept only its
table. The record to answer from was there all along - every run leaves a
year of the model, hour by hour, against the sondes, once bare and once
with the table it fitted - and so was the live forecast's own log. This
reads them:

**Runs.** Each run summarised from its replay folders: the 24-hour
forecast's error and bias bare, with the table in force when it began, and
with the new one, month by month and by sky, and "same as yesterday" beside
them. A summary is a few kilobytes and is kept; the folders, eighteen
megabytes each, are not - once a run's summary is written, older runs'
folders are removed (`prune`), because a Pi's card filled with them.

**Live.** The last sixty days as the forecast was actually issued: for each
hour the sondes measured, what the forecast said for it a day or so before,
at the longest lead the log has between LEAD_MIN and LEAD_MAX hours - the
first hours are held to the reading by design and would flatter it - and,
where it was logged, what the model said before the unit's corrections.

The runs score the model alone, as calibration fits it; the live forecast
also blends in the last days' measurements. The two are labelled as what
they are and never compared as one.

Nothing here leaves the unit.
"""
import json
import logging
import re
import shutil
from datetime import datetime, timedelta, timezone

from . import forecastlog, hindcast

log = logging.getLogger("elmer")

SUMMARIES = hindcast.CACHE / "runs"
SUMMARY_VERSION = 1
LEAD_MIN, LEAD_MAX = 6, 24
LIVE_DAYS = 60
SKIES = ("dark", "gray", "lit")
_RUN = re.compile(r"^ledger-(\d{8})-(\d{8})-(.+?)(\+cal|\+held)?$")


def runs_on_disk():
    """The calibration runs whose replay folders are here, oldest first:
    {key, start, end, build, bare, cal, held (folders or None), made}."""
    found = {}
    if not hindcast.CACHE.is_dir():
        return []
    for d in hindcast.CACHE.iterdir():
        m = _RUN.match(d.name)
        if not m or not d.is_dir():
            continue
        start, end, build, tag = m.groups()
        key = f"{start}-{end}-{build}"
        run = found.setdefault(key, {"key": key, "start": start, "end": end, "build": build,
                                     "bare": None, "cal": None, "held": None, "made": 0.0})
        run[{None: "bare", "+cal": "cal", "+held": "held"}[tag]] = d
        try:
            run["made"] = max(run["made"], d.stat().st_mtime)
        except OSError as exc:
            log.debug("calcharts: could not read the time of %s: %s", d.name, exc)
    # A run is its bare folder and the table's; a bare folder alone is a run
    # that stopped, or a hindcast from the command line, and is not a run.
    return sorted((r for r in found.values() if r["bare"] and r["cal"]), key=lambda r: r["made"])


def _score(folder, start, end):
    """The skill of one replay folder over its span."""
    days = (end - start).days + 2
    forecastlog.use(folder, keep_days=100000)
    try:
        return forecastlog.skill(days=days, now=end + timedelta(hours=23))
    finally:
        forecastlog.use(None)


def _slim(sk):
    """What the charts need of a skill: the 24-hour lead, and month by month."""
    lead = sk["by_lead"].get(24) or sk["by_lead"].get("24") or {}
    months = {}
    for month, row in (sk.get("by_month") or {}).items():
        months[month] = {"all": row.get("all"), "persistence": row.get("persistence"),
                         **{s: row.get(s) for s in SKIES if row.get(s)}}
    return {"lead24": lead, "persistence_24h": sk.get("persistence_24h"), "by_month": months, "n": sk.get("n")}


def summarize(run):
    """A run's summary, worked out from its folders and kept. Read back when
    it is already kept and made by this version."""
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    path = SUMMARIES / f"{run['key']}.json"
    try:
        kept = json.loads(path.read_text(encoding="utf-8"))
        if kept.get("version") == SUMMARY_VERSION:
            return kept
    except (OSError, ValueError):
        pass                            # not kept yet, or unreadable: work it out
    start = datetime.strptime(run["start"], "%Y%m%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(run["end"], "%Y%m%d").replace(tzinfo=timezone.utc)
    out = {"version": SUMMARY_VERSION, "key": run["key"], "build": run["build"],
           "start": start.date().isoformat(), "end": end.date().isoformat(),
           "made": datetime.fromtimestamp(run["made"], timezone.utc).isoformat(timespec="minutes")}
    for tag in ("bare", "cal", "held"):
        out[tag] = _slim(_score(run[tag], start, end)) if run[tag] else None
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(out), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        log.warning("calcharts: the summary of run %s was not kept: %s", run["key"], exc)
    log.info("calcharts: run %s summarised - 24 h error bare %s, calibrated %s MHz", run["key"],
             (out["bare"]["lead24"] or {}).get("mae"), (out["cal"]["lead24"] or {}).get("mae"))
    return out


def summaries():
    """Every run kept, oldest first: the summaries written, and any run whose
    folders are here but not yet summarised, summarised now."""
    out = {}
    if SUMMARIES.is_dir():
        for p in SUMMARIES.glob("*.json"):
            try:
                s = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                log.warning("calcharts: summary %s unreadable, left out: %s", p.name, exc)
                continue
            if s.get("version") == SUMMARY_VERSION:
                out[s["key"]] = s
    for run in runs_on_disk():
        if run["key"] not in out:
            out[run["key"]] = summarize(run)
    return sorted(out.values(), key=lambda s: s.get("made") or "")


def prune(keep_key):
    """Remove every run's replay folders but `keep_key`'s, once each has a
    summary kept. Returns the folders removed. A folder whose summary could
    not be kept stays, and says so."""
    removed = []
    for run in runs_on_disk():
        if run["key"] == keep_key:
            continue
        if not (SUMMARIES / f"{run['key']}.json").is_file():
            summarize(run)
        if not (SUMMARIES / f"{run['key']}.json").is_file():
            log.warning("calcharts: run %s kept on disk - its summary could not be written", run["key"])
            continue
        for tag in ("bare", "cal", "held"):
            folder = run[tag]
            if folder is None:
                continue
            try:
                shutil.rmtree(folder)
                removed.append(folder.name)
            except OSError as exc:
                log.warning("calcharts: could not remove %s: %s", folder.name, exc)
    if removed:
        log.info("calcharts: removed %d replay folder(s) of older runs, their summaries kept: %s",
                 len(removed), ", ".join(removed))
    return removed


def live(days=LIVE_DAYS, now=None):
    """The last `days` days as the forecast was issued: for each measured hour,
    the forecast made for it at the longest lead from LEAD_MIN to LEAD_MAX
    hours, and the model's own figure where it was logged."""
    now = now or datetime.now(timezone.utc)
    measured = forecastlog._measured_index(days, now)
    issued = {}
    for day in forecastlog._days_back(days + 2, now):
        for e in forecastlog._load(day)["forecasts"]:
            issued[e["hour"]] = e
    points = []
    for target in sorted(measured):
        got = measured[target]
        if not got or got.get("muf") is None:
            continue
        t = datetime.fromisoformat(target)
        pick = None
        for lead in range(LEAD_MAX, LEAD_MIN - 1, -1):
            e = issued.get(forecastlog._hour((t - timedelta(hours=lead)).isoformat()))
            if not e or target not in e["hours"]:
                continue
            i = e["hours"].index(target)
            if e["mufs"][i] is None:
                continue
            model = (e.get("mufs_model") or [None] * len(e["hours"]))[i]
            pick = {"t": target, "measured": got["muf"], "forecast": e["mufs"][i], "lead": lead,
                    "model": model, "regime": got.get("regime")}
            break
        if pick:
            points.append(pick)
    return {"days": days, "points": points, "lead_min": LEAD_MIN, "lead_max": LEAD_MAX}


def charts():
    """Everything the page draws: the table in force, every run, the live
    forecast."""
    table = forecastlog.calibration() or {}
    runs = summaries()
    return {"table": {"made": table.get("made"), "months": {m: forecastlog.month_cells(e)
                                                            for m, e in (table.get("months") or {}).items()}},
            "runs": runs, "latest": runs[-1] if runs else None, "live": live()}
