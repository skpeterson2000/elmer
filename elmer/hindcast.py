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
import logging
import re
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
SWPC_F107 = "https://services.swpc.noaa.gov/json/f107_cm_flux.json"

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

def _get(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


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


def fetch(start, end, codes=DEFAULT_STATIONS, force=False):
    """Everything a blind run needs for [start, end], cached under data/.

    Returns {"stations": {code: rows}, "kp": [[iso, kp]...], "f107": [[iso, flux]...],
    "answered": [codes], "silent": [codes]}. The window is widened a day each
    side so the first hours have a reading behind them and the last have
    readings ahead to be scored against.
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
           "fetched": datetime.now(timezone.utc).isoformat()}
    for code in codes:
        if code not in STATIONS:
            continue
        try:
            rows = parse_giro(_get(GIRO.format(code=code, a=a, b=b)))
        except Exception as exc:
            log.warning("hindcast: %s did not answer: %s", code, exc)
            rows = []
        if rows:
            out["stations"][code] = rows
            out["answered"].append(code)
        else:
            out["silent"].append(code)
    try:
        kp = json.loads(_get(GFZ_KP.format(
            a=urllib.parse.quote((start - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")),
            b=urllib.parse.quote((end + timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")))))
        out["kp"] = [[t, v] for t, v in zip(kp.get("datetime", []), kp.get("Kp", [])) if v is not None]
    except Exception as exc:
        log.warning("hindcast: GFZ Kp did not answer: %s", exc)
    try:
        flux = json.loads(_get(SWPC_F107))
        out["f107"] = sorted([[r["time_tag"], float(r["flux"])] for r in flux
                              if r.get("flux") is not None])
    except Exception as exc:
        log.warning("hindcast: SWPC flux did not answer: %s", exc)
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


def sondes_at(data, when):
    """The station rows the live feed would have shown at `when` - each
    station's latest reading at or before the hour, within MAX_AGE_HOURS,
    at or above the confidence the live feed accepts."""
    out = []
    for code, rows in data["stations"].items():
        name, lat, lon = STATIONS[code]
        best = None
        for r in rows:
            t = _t(r["time"])
            if t > when:
                break
            # The latest reading the live feed would have kept: one the
            # autoscaler graded below MIN_CONFIDENCE is dropped there, so the
            # previous good one is what would still have been showing.
            if r.get("cs") is not None and 0 <= r["cs"] < ionosonde.MIN_CONFIDENCE:
                continue
            best = (t, r)
        if not best:
            continue
        t, r = best
        age = (when - t).total_seconds() / 3600.0
        if age > ionosonde.MAX_AGE_HOURS:
            continue
        out.append({"name": name, "lat": lat, "lon": lon, "fof2": r["fof2"], "hmf2": r["hmf2"],
                    "mufd": r.get("mufd"), "m3000": r.get("md"), "confidence": r.get("cs"),
                    "age_minutes": round(age * 60), "time": t.isoformat(), "code": code})
    return out


def sfi_at(data, when):
    """The most recent flux at or before the hour; the nearest if none before."""
    rows = data.get("f107") or []
    before = [r for r in rows if _t(r[0]) <= when]
    if before:
        return before[-1][1]
    return rows[0][1] if rows else None


def kp_at(data, when):
    rows = data.get("kp") or []
    before = [r for r in rows if _t(r[0]) <= when]
    return before[-1][1] if before else (rows[0][1] if rows else 2.0)


def run(start, end, lat, lon, data, bands=(7.0, 14.0), step_hours=1,
        ledger=None, build="hindcast", learn=False, progress=None):
    """Forecast every hour from start to end, blind, into a ledger.

    `learn` lets the run apply the adjustment it has learned so far, as the
    live unit does; off, it measures the bare model. Returns the skill and
    the adjustment read back from the ledger, plus what was and was not
    available to it.
    """
    ledger_dir = ledger or (CACHE / f"ledger-{start:%Y%m%d}-{end:%Y%m%d}-{build}")
    saved = forecastlog.LEDGER
    forecastlog.LEDGER = ledger_dir
    try:
        for p in ledger_dir.glob("*.json"):
            p.unlink()
        when = start.replace(minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        hours, with_reading = 0, 0
        while when <= end:
            sfi = sfi_at(data, when)
            if sfi is None:
                break
            k = kp_at(data, when)
            sondes = sondes_at(data, when)
            cal = propagation.calibration(sfi, lat, lon, when=when, sondes=sondes)
            elevation = propagation.solar_elevation(lat, lon, when)
            muf, fof2 = propagation.levels(sfi, elevation, lat, cal and cal["m3000"],
                                           cal["factor"] if cal else 1.0,
                                           drive=propagation.f2_drive(lat, lon, when))
            source = cal["source"] if cal else "modelled"
            if source == "measured":
                with_reading += 1
                forecastlog.measured({"muf_source": "measured", "muf": round(muf, 1),
                                      "fof2": round(fof2, 2),
                                      "hmf2": cal.get("measured_hmf2"),
                                      "hmf2_measured": bool(cal.get("measured_hmf2")),
                                      "regime": propagation.sun_regime(elevation, lat, when),
                                      "calibration": cal}, now=when)
            bias = forecastlog.applied_bias(forecastlog.adjustment(now=when)) if learn else None
            out = []
            for mhz in bands:
                rows = propagation.outlook(mhz, lat, lon, sfi, k, start=when,
                                           anchor=cal["factor"] if cal else None,
                                           m3000=cal["m3000"] if cal else None,
                                           anchor_sun=cal.get("sun_deg") if cal else None,
                                           hmf2=(cal or {}).get("measured_hmf2") or propagation.HMF2_DEFAULT,
                                           bias=bias)
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
    finally:
        forecastlog.LEDGER = saved
    return {"start": start.isoformat(), "end": end.isoformat(), "hours": hours,
            "hours_with_reading": with_reading, "ledger": str(ledger_dir),
            "stations": list(data["stations"]), "silent": data.get("silent", []),
            "skill": skill, "adjustment": adjust, "build": build,
            "acknowledgement": ACKNOWLEDGEMENT.format(codes=", ".join(data["stations"]) or "no station")}


def report(result):
    """The run as text: what was said against what was measured."""
    lines = [f"  {result['hours']} hours forecast, {result['hours_with_reading']} with a sonde "
             f"in reach ({', '.join(result['stations']) or 'none'}"
             + (f"; silent: {', '.join(result['silent'])}" if result.get("silent") else "") + ")",
             f"  build {result['build']}", ""]
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
    lines.append("")
    lines.append("  what the unit would have learned to add, by sky (leads 6-24 h):")
    for k, v in result["adjustment"].items():
        lines.append(f"    {k:8s} {v['measured_bias']:+5.2f} MHz over {v['n']} measured hours"
                     + ("  -> applied" if v["applied"] else
                        ("  -> past the cap, not applied" if v["capped"] else
                         "  -> too few hours yet")))
    lines.append("")
    lines.append("  " + result["acknowledgement"])
    return "\n".join(lines)
