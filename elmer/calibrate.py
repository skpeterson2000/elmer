"""Calibrate my forecast: the hindcast run for this unit, on this unit, with
the operator watching.

One job at a time, in a thread, for about five minutes: fetch a year of the
record for the nearest sondes, run the model blind over it, fit the month by
sky table, run the year again with the table applied to show what it bought,
save the table, and hand the live forecast the result. The page polls
`status()` and shows a card between the numbers; every month that completes
is a finding worth a sentence, and those are what the operator reads while
they wait - not a spinner, and not silence.

Nothing leaves the unit. The record fetched is GIRO's and GFZ's, under their
terms; the table is this unit's, about this sky.
"""
import logging
import secrets
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

from . import forecastlog, hindcast

log = logging.getLogger("elmer")

_lock = threading.Lock()
_job = None


class Job:
    def __init__(self, lat, lon, days, build, place):
        self.lat, self.lon, self.days = lat, lon, int(days)
        self.build, self.place = build, place
        self.state = "queued"           # queued, fetching, running, checking, done, failed, stopped
        self.error = None
        self.started = time.time()
        self.finished = None
        self.hours_total = self.days * 24
        self.hours_done = 0
        self.pass_no = 0                # 1 = bare, 2 = calibrated
        self.findings = []              # sentences, oldest first
        self.stations = []
        self.silent = []
        self.result = None              # {"before": ..., "after": ..., "table": ...}
        self.stop = threading.Event()
        self._last_month = None
        self._end = None

    # ------------------------------------------------------------ the run
    def run(self):
        try:
            self.state = "fetching"
            end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=3)
            start = end - timedelta(days=self.days)
            self._end = end
            data = hindcast.fetch(start, end, notice=self.say)
            if not data["stations"] and not self.stop.is_set():
                # GIRO refusing every station in one breath is GIRO being
                # busy, not GIRO being down: one more go after a rest, said
                # once, and the wait is the page's to show.
                self.say("No sonde answered - GIRO is busy. Trying once more in 45 s.")
                if self.stop.wait(45):
                    self.state = "stopped"
                    return
                data = hindcast.fetch(start, end, force=True, notice=self.say)
            self.stations, self.silent = data.get("answered", []), data.get("silent", [])
            if not data["stations"]:
                raise hindcast.Unavailable("No ionosonde answered for the span, so there is nothing to "
                                           "calibrate against. GIRO was busy or unreachable; try again later.")
            self.say(f"{len(self.stations)} sonde{'s' if len(self.stations) != 1 else ''} answered for the span: "
                     f"{', '.join(self.stations)}"
                     + (f"; {', '.join(self.silent)} silent" if self.silent else "") + ".")
            for line in data.get("trouble") or []:
                self.say(line)
            # Enough of a record to run on? A year forecast on one flux
            # number is worse than no run, and that is what a missing
            # archive used to produce. The covered tail is run instead,
            # when there is one worth running.
            start, self.days = self._enough(data, start, end)
            self.hours_total = self.days * 24
            if self.stop.is_set():
                self.state = "stopped"
                return
            self.state = "running"
            self.pass_no = 1
            bare = hindcast.run(start, end, self.lat, self.lon, data, build=self.build,
                                progress=self._progress, stop=self.stop)
            if self.stop.is_set():
                self.state = "stopped"
                return
            table = bare["table"]
            applied = sum(1 for m in table["months"].values() for c in forecastlog.month_cells(m).values() if c["applied"])
            small = sum(1 for m in table["months"].values() for c in forecastlog.month_cells(m).values() if c.get("small"))
            if applied:
                self.say(f"Fitted: {applied} month-and-sky corrections worth applying, "
                         f"{small} within ten percent of the model and left alone, from "
                         f"{bare['hours_with_reading']} hours with a sonde in reach.")
            else:
                self.say(f"The model already fits this sky: every month-and-sky cell came within "
                         f"ten percent of the sondes over {bare['hours_with_reading']} hours, so there "
                         f"is nothing to correct here - which is worth knowing, and now measured.")
            self.state = "checking"
            self.pass_no = 2
            self.hours_done = 0
            self._last_month = None
            after = hindcast.run(start, end, self.lat, self.lon, data, build=self.build + "+cal",
                                 calibration=table, progress=self._progress, stop=self.stop)
            if self.stop.is_set():
                self.state = "stopped"
                return
            b24 = bare["skill"]["by_lead"].get("24", {}).get("mae")
            a24 = after["skill"]["by_lead"].get("24", {}).get("mae")
            p24 = bare["skill"].get("persistence_24h", {}).get("mae")
            if b24 and a24:
                self.say(f"Over the span, the 24-hour forecast's error went from {b24:.1f} to {a24:.1f} MHz"
                         + (f"; 'same as yesterday' manages {p24:.1f}." if p24 else "."))
            forecastlog.save_calibration(table)
            forecastlog._cal_cache.clear()
            self.result = {"before": _slim(bare), "after": _slim(after), "table": table}
            self.state = "done"
            log.info("calibration: done for %s - %d cells applied, 24h MAE %.2f -> %.2f",
                     self.place, applied, b24 or 0, a24 or 0)
        except hindcast.Unavailable as exc:
            # The record could not be had. Said in words, logged as a
            # warning, and not a bug: the network was the matter.
            self.state = "failed"
            self.error = str(exc)[:300]
            log.warning("calibration: could not run - %s", exc)
        except Exception as exc:                        # noqa: BLE001 - a bug, with a reference
            ref = "e-" + secrets.token_hex(2)
            self.state = "failed"
            self.error = (f"Something went wrong that ELMER did not expect (reference {ref}). "
                          "The Software panel's recent log has the details, and Send feedback "
                          "carries them.")
            log.error("calibration UNHANDLED %s  ref %s\n%s", type(exc).__name__, ref, traceback.format_exc())
        finally:
            self.finished = time.time()

    def _enough(self, data, start, end):
        """The span the record can honestly cover: (start, days).

        Raises Unavailable when it cannot cover enough of anything; shortens
        the span to the covered tail when that is a fortnight or more, and
        says so, so the person knows what they got and why.
        """
        cov = hindcast.coverage(data, start, end)
        if cov["f107"] >= hindcast.FLUX_COVERAGE_MIN:
            if cov["kp"] < 0.5:
                self.say("Kp was missing for most of the span; quiet geomagnetic conditions were "
                         "assumed for those hours, which only touches the storm days.")
            return start, self.days
        if cov["f107_from"]:
            first = datetime.strptime(cov["f107_from"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            tail_days = int((end - first).total_seconds() // 86400)
            if tail_days >= 14:
                src = (data.get("sources") or {}).get("f107") or "what answered"
                self.say(f"The flux record reaches back only to {first:%d %B %Y} ({src}), so the "
                         f"{tail_days} days it covers are calibrated and the rest left for another day.")
                return end - timedelta(days=tail_days), tail_days
        raise hindcast.Unavailable(
            "The year's solar flux record could not be fetched, so there is nothing to run the "
            "model against"
            + (f" ({(data.get('sources') or {}).get('f107') or 'no source'} covered "
               f"{round(100 * cov['f107'])}% of the span)" if cov["f107"] else "")
            + ". Nothing is wrong with the model; try again when GFZ or Penticton answers.")

    def _progress(self, when, hours):
        self.hours_done = hours
        if self.stop.is_set():
            return
        month = when.strftime("%Y-%m")
        if self._last_month and month != self._last_month and self.pass_no == 1:
            self._finding_for(self._last_month, when)
        self._last_month = month

    def _finding_for(self, month, now):
        """One sentence about the month just finished, from the ledger so far."""
        try:
            sk = forecastlog.skill(days=45, now=now)
            row = (sk.get("by_month") or {}).get(month)
            if not row:
                return
            parts = []
            for regime, word in (("lit", "by day"), ("dark", "at night"), ("grey", "at the grey line")):
                v = row.get(regime) or {}
                if v.get("n"):
                    b = v["bias"]
                    parts.append(f"{abs(b):.1f} MHz {'under' if b < 0 else 'over'} {word}")
            if parts:
                name = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
                note = ""
                lit = (row.get("lit") or {}).get("bias")
                # The size is measured; the cause is not, so it is not named.
                # This used to blame the winter anomaly in any month, and
                # once did so in September on a run fed the wrong flux.
                if lit is not None and lit < -4:
                    note = (" The daytime F layer over you ran denser than the model's season "
                            "allows for this month.")
                elif lit is not None and lit > 4:
                    note = (" The daytime F layer over you ran thinner than the model's season "
                            "allows for this month.")
                elif abs((row.get("dark") or {}).get("bias", 0)) > 3:
                    note = " The nights here differ from the stations the season was fitted from."
                self.say(f"{name}: the model ran " + ", ".join(parts) + "." + note)
        except Exception:                                 # a finding is a courtesy
            log.exception("calibration finding")

    def say(self, text):
        self.findings.append({"at": time.time(), "text": text})

    def status(self):
        total = self.hours_total
        done = self.hours_done
        overall = (done / total) if total else 0.0
        if self.pass_no == 2:
            overall = 0.5 + 0.5 * overall
        elif self.pass_no == 1:
            overall = 0.5 * overall
        elapsed = (self.finished or time.time()) - self.started
        return {"state": self.state, "error": self.error, "place": self.place,
                "days": self.days, "pass": self.pass_no, "hours_done": done, "hours_total": total,
                "fraction": round(min(1.0, overall), 3), "elapsed_s": round(elapsed),
                "stations": self.stations, "silent": self.silent,
                "findings": self.findings[-30:], "result": self.result}


def _slim(res):
    sk = res["skill"]
    return {"by_regime": sk["by_regime"], "by_lead": {k: sk["by_lead"][k] for k in ("1", "6", "12", "24") if k in sk["by_lead"]},
            "persistence_24h": sk.get("persistence_24h"),
            "by_month": {m: {"mae": row["all"]["mae"], "persistence": (row.get("persistence") or {}).get("mae")}
                         for m, row in (sk.get("by_month") or {}).items()},
            "hours": res["hours"], "hours_with_reading": res["hours_with_reading"],
            "sondes_voting": res.get("sondes_voting")}


def start(lat, lon, days=365, build="", place=""):
    """Begin a calibration, unless one is running. Returns the status."""
    global _job
    with _lock:
        if _job and _job.state in ("queued", "fetching", "running", "checking"):
            return _job.status()
        _job = Job(lat, lon, days, build, place)
        threading.Thread(target=_job.run, name="calibrate", daemon=True).start()
        return _job.status()


def status():
    with _lock:
        if _job is None:
            table = forecastlog.calibration()
            return {"state": "idle", "table": table}
        out = _job.status()
        out["table"] = forecastlog.calibration()
        return out


def stop():
    with _lock:
        if _job and _job.state in ("queued", "fetching", "running", "checking"):
            _job.stop.set()
            return True
        return False
