"""Run the forecast blind over a month that has already happened, and grade it.

The live ledger grades the model one hour at a time and takes a fortnight
to say anything. But the past is on record: the ionosonde network keeps
every reading, GFZ keeps every Kp, SWPC keeps the flux. Hand the model, hour
by hour, only what it would have known at that hour - the day's flux, the
current Kp, the sonde readings then on the wire - and let it draw the next
24 hours; then score what it said against what the sondes went on to read.
A month of forecasting takes a few minutes on the Pi, and the result is the
same ledger the live unit keeps, so the same skill and adjustment code reads
it. ELMER is kept blind: nothing from after the hour reaches the hour.

What comes out is a measured statement about the model - bias by sky and by
lead, before and after a change - which is how a change to propagation.py
gets judged from now on: not "it looks plausible", but "August's MAE went
from 1.9 to 1.4 MHz". A month in a few minutes is worth more than a year of
impressions, and it never once puts a wrong curve in front of an operator.

Sources, each carrying its own terms:
  * GIRO / DIDBase (Lowell), FastChar "GetBest": foF2, hmF2, MUF(3000) and
    M(3000)F2 per station, every 15 minutes. CC-BY-NC-SA 4.0; each
    station's data provider is to be acknowledged, and is, in the output.
  * GFZ Potsdam: the planetary Kp index, three-hourly. CC BY 4.0.
  * NOAA SWPC: the observed 10.7 cm flux, daily (the last ~40 days).
"""
import json
import socket
import ssl
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from . import forecastlog, paths, propagation, ionosonde

log = logging.getLogger("elmer")

CACHE = paths.STATE / "hindcast"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool; hindcast)"
GIRO = ("https://lgdc.uml.edu/fastchar/getbest?ursiCode={code}"
        "&charName=foF2,hmF2,MUF(D),M(D)&DMUF=3000&fromDate={a}&toDate={b}")
GFZ_KP = "https://kp.gfz.de/app/json/?start={a}&end={b}&index=Kp"
# The whole geomagnetic and solar record in one text file: eight Kp a day,
# Ap, the sunspot number and the observed and adjusted 10.7 cm flux, every
# day since 1932, kept current to yesterday. One download answers a year.
GFZ_ARCHIVE = "https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt"
SWPC_F107 = "https://services.swpc.noaa.gov/json/f107_cm_flux.json"
# Penticton's own daily table, back to 2004 - the same observed flux GFZ
# carries, from the observatory that measures it. The second source for a
# year of flux when GFZ does not answer.
CANADA_F107 = "https://www.spaceweather.gc.ca/solar_flux_data/daily_flux_values/fluxtable.txt"
ARCHIVE_MAX_AGE_H = 24
# A request is tried this many times before it is given up on, with a pause
# that doubles between tries; a 429 waits what the server asks, within reason.
TRIES = 3
FIRST_PAUSE_S = 3.0
MAX_PAUSE_S = 60.0
# GIRO rate-limits, and seven stations asked in one breath is what trips it.
BETWEEN_STATIONS_S = 1.5
# How far the flux and Kp may be carried to an hour that has none of its
# own: a day or three of missing archive is bridged, a missing year is not.
FLUX_REACH_DAYS = 3
KP_REACH_DAYS = 1
# Less of the span covered than this and the run does not start - it would
# be forecasting a year on one number, which is what happened once.
FLUX_COVERAGE_MIN = 0.9

# The North American Digisondes that report to GIRO, as the live feed names
# them. Several are dark for months at a time; the fetch says which answered.
STATIONS = {
    "AL945": ("Alpena, MI, USA", 45.07, -83.56),
    "IF843": ("Idaho Natl Lab, ID, USA", 43.81, -112.68),
    "EG931": ("Eglin AFB, FL, USA", 30.50, -86.50),
    "MHJ45": ("Millstone Hill, MA, USA", 42.60, -71.50),
    "BC840": ("Boulder, CO, USA", 40.00, -105.30),
    "AU930": ("Austin, TX, USA", 30.40, -97.70),
    "WP937": ("Wallops Is, VA, USA", 37.90, -75.50),
}
DEFAULT_STATIONS = ("AL945", "IF843", "EG931", "MHJ45", "BC840", "AU930", "WP937")

ACKNOWLEDGEMENT = ("Ionosonde data from the Global Ionospheric Radio Observatory "
                   "(GIRO / DIDBase, Lowell), CC-BY-NC-SA 4.0, with thanks to the "
                   "data providers of {codes}. Kp from GFZ Potsdam, CC BY 4.0. "
                   "10.7 cm flux from NOAA SWPC.")


# ---------------------------------------------------------------- fetching

class Unavailable(RuntimeError):
    """The record could not be had, said in words for the page. Not a bug:
    the network, a busy server, a certificate the machine cannot check."""


def _host(url):
    return urllib.parse.urlsplit(url).hostname or url


def _plain(exc):
    """A network failure in a sentence a person can act on."""
    if isinstance(exc, urllib.error.HTTPError):
        return {429: "it is busy and asked us to wait", 403: "it refused the request",
                404: "it has nothing at that address"}.get(exc.code, f"it answered HTTP {exc.code}")
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc):
        return "this machine could not check its certificate"
    if isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(reason, (socket.timeout, TimeoutError)):
        return "it did not answer in time"
    if isinstance(reason, socket.gaierror) or "getaddrinfo" in str(exc):
        return "there is no route to it - is the network up?"
    return str(reason)[:80] or exc.__class__.__name__


def _ssl_context():
    """A context that can check certificates when the machine's own store
    cannot - certifi, if it is installed, carries the roots and
    intermediates a bare Windows Python sometimes lacks."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:                # noqa: BLE001 - no certifi, no help
        return None


def _get(url, timeout=60, tries=TRIES, notice=None, what=None):
    """The body at a URL, tried a few times before it is given up on.

    A busy server (429) is waited for as long as it asks, within reason; a
    timeout, a dropped connection or a certificate this machine cannot
    check gets a pause and another go, the last with certifi's roots if
    they are here. `notice` is told, in words, when there is a wait worth
    knowing about, so the page can say "GFZ is busy, trying again in 20 s"
    rather than nothing. The last failure is raised with a plain reason.
    """
    what = what or _host(url)
    pause, context, last = FIRST_PAUSE_S, None, None
    for attempt in range(1, tries + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 504):
                break                                   # not going to change by asking again
            if exc.code == 429:
                try:
                    pause = min(MAX_PAUSE_S, max(pause, float(exc.headers.get("Retry-After") or 0)))
                except (TypeError, ValueError):
                    pass
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ssl.SSLError) as exc:
            last = exc
            if "CERTIFICATE_VERIFY_FAILED" in str(exc) and context is None:
                context = _ssl_context()                # the next try checks with certifi's roots
        if attempt == tries:
            break
        reason = _plain(last)
        log.info("hindcast: %s - %s; trying again in %.0f s (%d of %d)", what, reason, pause, attempt, tries)
        if notice and (last is not None and getattr(last, "code", None) == 429 or pause >= 10):
            notice(f"{what[:1].upper() + what[1:]} {reason}; trying again in {pause:.0f} s.")
        time.sleep(pause)
        pause = min(MAX_PAUSE_S, pause * 2)
    raise Unavailable(f"{what}: {_plain(last)}") from last


def parse_giro(text):
    """GIRO's tabulated text into rows: time, cs, fof2, hmf2, mufd, md.

    A value the autoscaler could not produce is printed as ---; a row with
    no foF2 is no reading. The confidence score comes along so the same
    refusal the live feed applies (MIN_CONFIDENCE) applies here.
    """
    rows = []
    header = None
    for line in text.splitlines():
        if line.startswith("# Time"):
            header = re.sub(r"\s+QD", "", line[1:]).split()
            continue
        if not line or line.startswith("#") or header is None:
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        # Columns: Time CS <value QD>* - every value is followed by a QD flag.
        values = parts[2::2]
        names = header[2:]
        row = {"time": parts[0], "cs": _num(parts[1])}
        for name, value in zip(names, values):
            key = {"foF2": "fof2", "hmF2": "hmf2", "MUF(D)": "mufd", "M(D)": "md"}.get(name, name)
            row[key] = _num(value)
        if row.get("fof2") is None or row.get("hmf2") is None:
            continue
        rows.append(row)
    return rows


def _num(text):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def parse_canada_flux(text):
    """Penticton's daily table into flux rows, one a day at the 20:00 UT
    reading - the noon value, which is the day's official figure and the
    one GFZ carries. Columns: fluxdate fluxtime julian carrington obs adj ursi."""
    by_day = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 7 or not parts[0].isdigit() or len(parts[0]) != 8:
            continue
        try:
            obs = float(parts[4])
        except ValueError:
            continue
        if obs <= 0:
            continue
        day, hhmm = parts[0], parts[1][:4]
        # The 20:00 reading wins; failing that the first seen stands.
        if hhmm == "2000" or day not in by_day:
            by_day[day] = obs
    return [[f"{d[:4]}-{d[4:6]}-{d[6:]}T20:00:00", v] for d, v in sorted(by_day.items())]


def coverage(data, start, end, now=None):
    """How much of [start, end] the record actually covers: the share of
    days with a flux reading and with any Kp, and the flux's first day.
    Today is not counted against it - the day's flux is read at noon in
    Penticton and published after, so a span that ends now ends yesterday
    as far as the record can be expected to go."""
    now = now or datetime.now(timezone.utc)
    end = min(end, now - timedelta(days=1))
    days = max(1, int((end - start).total_seconds() // 86400) + 1)
    lo, hi = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
    flux_days = sorted({r[0][:10] for r in data.get("f107") or [] if lo <= r[0][:10] <= hi})
    kp_days = {r[0][:10] for r in data.get("kp") or [] if lo <= r[0][:10] <= hi}
    return {"days": days, "f107": round(len(flux_days) / days, 3), "kp": round(len(kp_days) / days, 3),
            "f107_from": flux_days[0] if flux_days else None, "f107_to": flux_days[-1] if flux_days else None}


def parse_gfz_archive(text):
    """GFZ's daily lines into (kp rows, flux rows).

    Each line: year month day ... Kp1..Kp8 ap1..ap8 Ap SN F10.7obs F10.7adj D.
    Kp is three-hourly from 00Z; the flux is the day's observed Penticton
    value (adjusted to 1 AU is the other column, and is not what the live
    feed shows). -1 marks a value not yet available.
    """
    kp, flux = [], []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 28:
            continue
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            day = datetime(y, m, d, tzinfo=timezone.utc)
            for i in range(8):
                v = float(parts[7 + i])
                if v >= 0:
                    kp.append([(day + timedelta(hours=3 * i)).isoformat().replace("+00:00", "Z"), v])
            f = float(parts[25])
            if f > 0:
                flux.append([day.strftime("%Y-%m-%dT20:00:00"), f])
        except (ValueError, IndexError):
            continue
    return kp, flux


def _archive(notice=None):
    """The GFZ archive, fetched at most once a day."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "gfz-archive.txt"
    try:
        age_h = (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 3600.0
        if age_h < ARCHIVE_MAX_AGE_H:
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    text = _get(GFZ_ARCHIVE, timeout=180, notice=notice, what="GFZ")
    if "\n19" not in text[:100000] and "\n20" not in text[:100000]:
        raise Unavailable("GFZ: what came back was not the archive")
    path.write_text(text, encoding="utf-8")
    return text


def fetch(start, end, codes=DEFAULT_STATIONS, force=False, notice=None):
    """Everything a blind run needs for [start, end], cached under data/.

    Returns {"stations": {code: rows}, "kp": [[iso, kp]...], "f107": [[iso, flux]...],
    "answered": [codes], "silent": [codes], "sources": {...}, "trouble": [...]}.
    The window is widened a day each side so the first hours have a reading
    behind them and the last have readings ahead to be scored against.

    Nothing here raises for a source that does not answer: each is tried,
    the next source is tried behind it, and what came of it is said in
    `sources` and, where a person should know, in `trouble` - plain
    sentences for the page. Whether what came back is enough to run on is
    `coverage`'s question, and the caller's.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    key = f"{start:%Y%m%d}-{end:%Y%m%d}-{'-'.join(sorted(codes))}"
    path = CACHE / f"{key}.json"
    if path.exists() and not force:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    a = (start - timedelta(days=1)).strftime("%Y/%m/%d+00:00:00")
    b = (end + timedelta(days=2)).strftime("%Y/%m/%d+00:00:00")
    out = {"stations": {}, "kp": [], "f107": [], "answered": [], "silent": [],
           "sources": {"kp": None, "f107": None}, "trouble": [],
           "fetched": datetime.now(timezone.utc).isoformat()}
    first = True
    for code in codes:
        if code not in STATIONS:
            continue
        if not first:
            time.sleep(BETWEEN_STATIONS_S)          # GIRO's limit is per breath
        first = False
        try:
            rows = parse_giro(_get(GIRO.format(code=code, a=a, b=b), notice=notice, what=f"GIRO ({code})"))
        except Exception as exc:                    # noqa: BLE001 - said, and the next station asked
            log.warning("hindcast: %s did not answer: %s", code, exc)
            rows = []
        if rows:
            out["stations"][code] = rows
            out["answered"].append(code)
        else:
            out["silent"].append(code)
    # Kp and flux from the GFZ archive - a year is the same download as a
    # week - trimmed to the window; the SWPC feed fills the last day or two
    # the archive has not reached.
    lo = (start - timedelta(days=2)).isoformat()
    hi = (end + timedelta(days=2)).isoformat()
    try:
        kp, flux = parse_gfz_archive(_archive(notice=notice))
        out["kp"] = [r for r in kp if lo <= r[0].replace("Z", "+00:00") <= hi]
        out["f107"] = [r for r in flux if lo[:10] <= r[0][:10] <= hi[:10]]
        out["sources"] = {"kp": "GFZ archive", "f107": "GFZ archive"}
    except Exception as exc:                        # noqa: BLE001 - the next sources are tried
        log.warning("hindcast: GFZ archive did not answer: %s", exc)
        out["trouble"].append(f"GFZ's archive of Kp and flux did not answer ({_plain(exc)}).")
        try:
            kp = json.loads(_get(GFZ_KP.format(
                a=urllib.parse.quote((start - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")),
                b=urllib.parse.quote((end + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z"))),
                notice=notice, what="GFZ"))
            out["kp"] = [[t, v] for t, v in zip(kp.get("datetime", []), kp.get("Kp", [])) if v is not None]
            out["sources"]["kp"] = "GFZ Kp service"
        except Exception as exc2:                   # noqa: BLE001
            log.warning("hindcast: GFZ Kp did not answer either: %s", exc2)
            out["trouble"].append("Kp could not be had at all; quiet geomagnetic conditions are assumed, "
                                  "which only touches the storm days.")
        try:
            flux = parse_canada_flux(_get(CANADA_F107, notice=notice, what="Penticton"))
            out["f107"] = [r for r in flux if lo[:10] <= r[0][:10] <= hi[:10]]
            out["sources"]["f107"] = "Penticton (spaceweather.gc.ca)"
            out["trouble"].append("The 10.7 cm flux came from the Penticton observatory's own table instead.")
        except Exception as exc3:                   # noqa: BLE001
            log.warning("hindcast: Penticton flux did not answer either: %s", exc3)
    try:
        recent = json.loads(_get(SWPC_F107, notice=notice, what="SWPC"))
        have = {r[0][:10] for r in out["f107"]}
        out["f107"] += sorted([[r["time_tag"], float(r["flux"])] for r in recent
                               if r.get("flux") is not None and r["time_tag"][:10] not in have
                               and lo[:10] <= r["time_tag"][:10] <= hi[:10]])
        out["f107"].sort()
        if out["sources"]["f107"] is None and out["f107"]:
            out["sources"]["f107"] = "SWPC (recent days only)"
    except Exception as exc:                        # noqa: BLE001
        log.warning("hindcast: SWPC flux did not answer: %s", exc)
    cov = coverage(out, start, end)
    log.info("hindcast: fetched %d-%d: %d stations, flux %d%% of the span from %s, Kp %d%% from %s",
             int(start.strftime("%Y%m%d")), int(end.strftime("%Y%m%d")), len(out["stations"]),
             round(100 * cov["f107"]), out["sources"]["f107"], round(100 * cov["kp"]), out["sources"]["kp"])
    # Kept only when it is worth keeping: a fetch that came back with no
    # flux to speak of would otherwise be served from the cache for a day.
    if cov["f107"] >= FLUX_COVERAGE_MIN and out["stations"]:
        path.write_text(json.dumps(out), encoding="utf-8")
    return out


# ---------------------------------------------------------- the blind hour

def _band_name(mhz):
    for name, f, _ in propagation.BANDS:
        if abs(f - mhz) < 0.6:
            return name
    return f"{mhz:g} MHz"


def _t(iso):
    t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _indexed(data):
    """Each station's acceptable rows with their times parsed once, sorted -
    a year of 15-minute readings is 35,000 rows a station, and walking them
    from the top for every hour of the year was most of the running time."""
    if "_index" in data:
        return data["_index"]
    index = {}
    for code, rows in data["stations"].items():
        keep = []
        for r in rows:
            # The latest reading the live feed would have kept: one the
            # autoscaler graded below MIN_CONFIDENCE is dropped there, so the
            # previous good one is what would still have been showing.
            if r.get("cs") is not None and 0 <= r["cs"] < ionosonde.MIN_CONFIDENCE:
                continue
            keep.append((_t(r["time"]), r))
        keep.sort(key=lambda tr: tr[0])
        index[code] = ([t for t, _ in keep], [r for _, r in keep])
    data["_index"] = index
    return index


def sondes_at(data, when):
    """The station rows the live feed would have shown at `when` - each
    station's latest reading at or before the hour, within MAX_AGE_HOURS,
    at or above the confidence the live feed accepts."""
    import bisect
    out = []
    for code, (times, rows) in _indexed(data).items():
        name, lat, lon = STATIONS[code]
        i = bisect.bisect_right(times, when) - 1
        if i < 0:
            continue
        t, r = times[i], rows[i]
        age = (when - t).total_seconds() / 3600.0
        if age > ionosonde.MAX_AGE_HOURS:
            continue
        out.append({"name": name, "lat": lat, "lon": lon, "fof2": r["fof2"], "hmf2": r["hmf2"],
                    "mufd": r.get("mufd"), "m3000": r.get("md"), "confidence": r.get("cs"),
                    "age_minutes": round(age * 60), "time": t.isoformat(), "code": code})
    return out


def _nearest(rows, when, reach_days):
    """The most recent value at or before the hour, else the first after -
    either within reach, or None. A reading from the far side of a gap of
    months is no reading: a year was once run on a flux from eleven months
    away because the fallback was "the nearest there is"."""
    reach = timedelta(days=reach_days)
    before = [r for r in rows if when - reach <= _t(r[0]) <= when]
    if before:
        return before[-1][1]
    after = [r for r in rows if when < _t(r[0]) <= when + reach]
    return after[0][1] if after else None


def sfi_at(data, when):
    """The most recent flux at or before the hour, within reach; None if
    the record does not cover the hour."""
    return _nearest(data.get("f107") or [], when, FLUX_REACH_DAYS)


def kp_at(data, when):
    """The Kp block containing the hour, within reach; quiet (2.0) if the
    record does not cover it - the run counts those hours and says so."""
    v = _nearest(data.get("kp") or [], when, KP_REACH_DAYS)
    return 2.0 if v is None else v


def run(start, end, lat, lon, data, bands=(7.0, 14.0), step_hours=1,
        ledger=None, build="hindcast", learn=False, progress=None,
        calibration=None, stop=None, persist=False):
    """Forecast every hour from start to end, blind, into a ledger.

    `learn` lets the run apply the adjustment it has learned so far, as the
    live unit does; off, it measures the bare model. `calibration` is a
    month-by-sky factor table to apply as the live unit would - the second
    pass, after the first has fitted it. `stop` is an Event that ends the
    run early. Returns the skill and the adjustment read back from the
    ledger, plus what was and was not available to it.
    """
    ledger_dir = ledger or (CACHE / f"ledger-{start:%Y%m%d}-{end:%Y%m%d}-{build}")
    # This thread's ledger, and this thread's alone - the live unit's
    # logger keeps writing its own. A hindcast ledger is never pruned: the
    # live unit keeps sixty days, and a year run under that rule quietly
    # graded only its last two months - the same numbers as the quarter,
    # which is how it was noticed.
    forecastlog.use(ledger_dir, keep_days=100000)
    try:
        for p in ledger_dir.glob("*.json"):
            p.unlink()
        when = start.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        hours, with_reading, votes, without_kp, stopped = 0, 0, [], 0, None
        while when <= end and not (stop and stop.is_set()):
            sfi = sfi_at(data, when)
            if sfi is None:
                stopped = f"no flux reading within {FLUX_REACH_DAYS} days of {when:%Y-%m-%d %H:%M} UTC"
                log.warning("hindcast: stopped - %s", stopped)
                break
            k = kp_at(data, when)
            if _nearest(data.get("kp") or [], when, KP_REACH_DAYS) is None:
                without_kp += 1
            sondes = sondes_at(data, when)
            cal = propagation.calibration(sfi, lat, lon, when=when, sondes=sondes)
            elevation = propagation.solar_elevation(lat, lon, when)
            muf, fof2 = propagation.levels(sfi, elevation, lat, cal and cal["m3000"],
                                           cal["factor"] if cal else 1.0,
                                           drive=propagation.f2_drive(lat, lon, when), when=when)
            source = cal["source"] if cal else "modelled"
            if source == "measured":
                with_reading += 1
                votes.append(cal["stations"])
                forecastlog.measured({"muf_source": "measured", "muf": round(muf, 1),
                                      "fof2": round(fof2, 2),
                                      "hmf2": cal.get("measured_hmf2"),
                                      "hmf2_measured": bool(cal.get("measured_hmf2")),
                                      "regime": propagation.sun_regime(elevation, lat, when),
                                      "calibration": cal}, now=when)
            bias = forecastlog.applied_bias(forecastlog.adjustment(now=when)) if learn else None
            record = None
            if persist:
                ahead = [(when + timedelta(hours=i)).isoformat() for i in range(25)]
                record = forecastlog.persistence(ahead, now=when)
            out = []
            for mhz in bands:
                rows = propagation.outlook(mhz, lat, lon, sfi, k, start=when,
                                           anchor=cal["factor"] if cal else None,
                                           m3000=cal["m3000"] if cal else None,
                                           anchor_sun=cal.get("sun_deg") if cal else None,
                                           hmf2=(cal or {}).get("measured_hmf2") or propagation.HMF2_DEFAULT,
                                           bias=bias, calibration=calibration,
                                           persist=record)
                out.append({"band": _band_name(mhz), "hours": [
                    {"at": r["at"], "score": r["score"], "muf": r["muf"],
                     "regime": r["regime"], "day": r["day"]} for r in rows]})
            forecastlog.record(out, {"sfi": sfi, "k_index": k, "muf_now": round(muf, 1),
                                     "muf_source": source, "fof2": round(fof2, 2),
                                     "hmf2": (cal or {}).get("measured_hmf2"),
                                     "hmf2_measured": bool((cal or {}).get("measured_hmf2")),
                                     "m3000": cal["m3000"] if cal else None,
                                     "anchor": cal["factor"] if cal else 1.0,
                                     "lat": lat, "lon": lon, "adjustment": bias or {}},
                               build, now=when)
            hours += 1
            if progress and hours % 24 == 0:
                progress(when, hours)
            when += timedelta(hours=step_hours)
        days = max(1, int((end - start).total_seconds() // 86400) + 2)
        skill = forecastlog.skill(days=days, now=end)
        adjust = forecastlog.adjustment(days=days, now=end)
        # The table this run would teach - meaningful from a bare pass, and
        # reported from a calibrated one as what is left to learn.
        table = forecastlog.fit_calibration(
            days, end, build=build, stations=list(data["stations"]),
            acknowledgement=ACKNOWLEDGEMENT.format(codes=", ".join(data["stations"]) or "no station"))
    finally:
        forecastlog.use(None)
    return {"start": start.isoformat(), "end": end.isoformat(), "hours": hours,
            "hours_with_reading": with_reading, "hours_without_kp": without_kp,
            "stopped": stopped,
            "sondes_voting": round(sum(votes) / len(votes), 1) if votes else 0,
            "ledger": str(ledger_dir),
            "stations": list(data["stations"]), "silent": data.get("silent", []),
            "skill": skill, "adjustment": adjust, "table": table, "build": build,
            "calibrated": calibration is not None, "persisted": bool(persist),
            "acknowledgement": ACKNOWLEDGEMENT.format(codes=", ".join(data["stations"]) or "no station")}


def report(result):
    """The run as text: what was said against what was measured."""
    lines = [f"  {result['hours']} hours forecast, {result['hours_with_reading']} with a sonde "
             f"in reach, {result.get('sondes_voting', 0)} voting on average "
             f"({', '.join(result['stations']) or 'none'}"
             + (f"; silent: {', '.join(result['silent'])}" if result.get("silent") else "") + ")",
             f"  build {result['build']}"
             + (" - as the live forecast runs, the record blended in past the reading" if result.get("persisted")
                else " - the model alone, the record kept out"), ""]
    sk = result["skill"]
    lines.append(f"  skill against the sondes, {sk['n']} forecast-hours scored (MHz, forecast minus measured)")
    lines.append("    by sky:   " + "   ".join(
        f"{k:8s} bias {v['bias']:+5.2f} mae {v['mae']:4.2f} n {v['n']:5d}"
        for k, v in sk["by_regime"].items() if v["n"]))
    leads = sk["by_lead"]
    picks = [l for l in ("1", "3", "6", "12", "18", "24") if l in leads]
    lines.append("    by lead:  " + "   ".join(
        f"{l:>2}h bias {leads[l]['bias']:+5.2f} mae {leads[l]['mae']:4.2f}" for l in picks))
    p = sk.get("persistence_24h") or {}
    if p.get("n"):
        lines.append(f"    persistence (same hour yesterday) at 24h: mae {p['mae']:4.2f} over {p['n']} hours"
                     f"  - the yardstick the 24h column has to beat")
    months = sk.get("by_month") or {}
    if len(months) > 1:
        lines.append("")
        lines.append("  month by month (model leads 6-24 h; persistence at 24 h):")
        lines.append("    month    dark bias/mae     grey bias/mae     lit bias/mae      all mae   persist mae")
        for m, row in months.items():
            def cell(r):
                v = row.get(r) or {}
                return f"{v['bias']:+5.2f}/{v['mae']:4.2f}" if v.get("n") else "     -     "
            lines.append(f"    {m}  {cell('dark'):>15s}  {cell('grey'):>15s}  {cell('lit'):>15s}   "
                         f"{(row.get('all') or {}).get('mae', 0) or 0:5.2f}     "
                         f"{(row.get('persistence') or {}).get('mae', 0) or 0:5.2f}")
    lines.append("")
    lines.append("  what the unit would have learned to add, by sky (leads 6-24 h):")
    for k, v in result["adjustment"].items():
        lines.append(f"    {k:8s} {v['measured_bias']:+5.2f} MHz over {v['n']} measured hours"
                     + ("  -> applied" if v["applied"] else
                        ("  -> past the cap, not applied" if v["capped"] else
                         "  -> too few hours yet")))
    table = result.get("table") or {}
    if table.get("months"):
        lines.append("")
        lines.append("  the calibration this run teaches - the sondes' MUF over the model's, by month and sky:")
        lines.append("    month     dark          grey          lit")
        for m, regs in table["months"].items():
            regs = forecastlog.month_cells(regs)

            def cell(r):
                v = regs.get(r)
                if not v:
                    return "     -      "
                mark = "" if v["applied"] else ("=" if v.get("small") else "?")
                return f"x{v['measured']:.2f} n{v['n']:<4d}{mark}"
            lines.append(f"    {m}      {cell('dark'):13s} {cell('grey'):13s} {cell('lit'):13s}")
        lines.append("    (= : within 10% of the model, left alone; ? : too few hours; applied factors are bounded 0.5-2.0)")
    lines.append("")
    lines.append("  " + result["acknowledgement"])
    return "\n".join(lines)
