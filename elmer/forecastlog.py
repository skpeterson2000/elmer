"""The forecast's own record: what it said, what the sky then did, and
whether its shape moved without the sky moving.

Every outlook ELMER draws is thrown away the moment the page is closed.
That left nobody to notice two things this week: that the model's shape
had changed under the operator (the code moved, the ionosphere did not),
and that the model's night-time level runs under what the sondes measure
at the same hour. An operator noticed both; the program could not have.

So the unit keeps a ledger. Each hour's outlook is written down with the
inputs it was drawn from and the build that drew it; each measured MUF is
written down as it arrives. From those two the unit can answer, on its own
and with numbers rather than impressions:

**Skill.** Yesterday at this hour the forecast said 12.4 MHz; the sondes
read 14.2. Kept by lead time and by sky - lit, grey, dark - so "the model
runs 1.8 MHz low at night" is a measured sentence with an n behind it.

**Adjustment.** Where the record shows a steady bias by sky, the unit
corrects its own model by that amount - only where no fresh reading holds
(the anchor already handles the hours near a reading), only once enough
readings agree, never by more than a cap, and always saying so on the
page and in the ledger. The Pi teaches itself the level; the shape stays
the model's. A correction learned from measurement is the kind of number
this program is allowed to use; the size of it, unit by unit, is exactly
what a field report should carry home.

**Drift.** When a new outlook differs from the last one by more than the
inputs moved, the model changed and the sky did not. With a new build that
is explained and logged as such; without one it is a WARNING, because the
only remaining explanation is that something is wrong.

Nothing here leaves the unit. It is a JSON file a day under data/forecasts,
pruned after KEEP_DAYS, and it carries no person - a location rounded to
a tenth of a degree, for the sun's sake, and numbers.
"""
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import paths

log = logging.getLogger("elmer")

LEDGER = paths.STATE / "forecasts"
KEEP_DAYS = 60

# Leads at which the anchor has let go and the model is speaking alone -
# the hours whose error says something about the model rather than about
# how well the nearest sonde described this sky.
MODEL_LEADS = range(6, 25)
# How many measured hours of one sky before a bias is believed enough to
# apply - a couple of nights, not a couple of readings.
ADJUST_MIN_N = 12
# The most the unit will correct its own MUF by, in MHz. A bias bigger than
# this is a broken station or a different sky, not a model to be nudged.
ADJUST_CAP_MHZ = 3.0
# Over how many days of record the bias is fitted.
ADJUST_DAYS = 14

# Drift: between two outlooks, at hours both forecast beyond the anchor's
# reach, the MUF moving by DRIFT_MHZ or the score moving by DRIFT_POINTS at
# an unchanged MUF, at DRIFT_HOURS or more of those hours, while the inputs
# sit inside the tolerances below - that is the model moving, not the sky.
# The score near the MUF is steep by design, so a score that moved because
# the MUF moved is not drift; a score that moved with the MUF still is.
DRIFT_MHZ = 1.0
DRIFT_POINTS = 15
DRIFT_SAME_MUF = 0.3
DRIFT_HOURS = 4
DRIFT_SKIP_FIRST = 6          # the anchor's own hours, where change is by design
# The anchor is an input too: the sondes' factor on the model carries into
# the first hours of every outlook, so two outlooks an hour apart legitimately
# differ where the factor did. Ten percent of it is a new reading, not drift.
INPUT_TOLERANCE = {"sfi": 8.0, "k_index": 1.5, "muf_now": 1.0, "anchor": 0.10}


def _day(when):
    return when.strftime("%Y-%m-%d")


def _path(day):
    return LEDGER / f"{day}.json"


def _load(day):
    try:
        with open(_path(day), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"day": day, "forecasts": [], "measured": {}}


def _save(day, data):
    LEDGER.mkdir(parents=True, exist_ok=True)
    tmp = _path(day).with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    tmp.replace(_path(day))


def _hour(iso):
    """An ISO time truncated to its UTC hour, as the ledger keys it."""
    t = datetime.fromisoformat(iso)
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0).isoformat()


def _days_back(n, until=None):
    until = until or datetime.now(timezone.utc)
    return [_day(until - timedelta(days=i)) for i in range(n)]


# ------------------------------------------------------------------ writing

def record(bands, inputs, build, now=None):
    """Write this hour's outlook down. Returns the drift verdict against
    the previous one, or None when there was nothing to compare.

    `bands` is the outlook's own list - name, hours with at/score/muf/regime.
    One entry per UTC hour: a page reloaded three times in an hour
    replaces rather than repeats.
    """
    now = now or datetime.now(timezone.utc)
    if not bands or not bands[0].get("hours"):
        return None
    hours = [_hour(h["at"]) for h in bands[0]["hours"]]
    entry = {
        "at": now.isoformat(),
        "hour": _hour(now.isoformat()),
        "build": build or "unknown",
        "inputs": {k: inputs.get(k) for k in ("sfi", "k_index", "muf_now", "muf_source",
                                              "fof2", "hmf2", "hmf2_measured", "m3000",
                                              "anchor", "lat", "lon", "adjustment")},
        "hours": hours,
        "mufs": [h.get("muf") for h in bands[0]["hours"]],
        "regimes": [h.get("regime") for h in bands[0]["hours"]],
        "bands": {b["band"]: [h["score"] for h in b["hours"]] for b in bands if b.get("hours")},
    }
    for key in ("lat", "lon"):
        if entry["inputs"].get(key) is not None:
            entry["inputs"][key] = round(float(entry["inputs"][key]), 1)
    previous = latest(before=entry["hour"], now=now)
    day = _day(now)
    data = _load(day)
    data["forecasts"] = [e for e in data["forecasts"] if e["hour"] != entry["hour"]]
    data["forecasts"].append(entry)
    _save(day, data)
    _prune(now)
    verdict = drift(previous, entry) if previous else None
    if verdict and verdict["moved"]:
        # INFO, all three. The hindcast showed the model itself is not still
        # from one issue hour to the next - the anchor's reach moves with the
        # sondes' sun - so a WARNING every hour would be noise, and noise is
        # how a real one gets missed. The verdict is on the record and on the
        # page; the hindcast is where "did the code move" is actually asked.
        why = ("with the sky" if verdict["inputs_moved"]
               else "with the build" if verdict["build_changed"]
               else "with neither the sky nor the build")
        log.info("forecast: the outlook moved %s - %s", why, verdict["note"])
    return verdict


def measured(snap, now=None):
    """Write a measured MUF down for this hour, if the snapshot has one.

    Only a reading - a modelled MUF written here would be the model
    grading its own homework.
    """
    if not snap or snap.get("muf_source") != "measured" or not snap.get("muf"):
        return False
    now = now or datetime.now(timezone.utc)
    day = _day(now)
    data = _load(day)
    cal = snap.get("calibration") or {}
    data["measured"][_hour(now.isoformat())] = {
        "muf": snap["muf"], "fof2": snap.get("fof2"),
        "hmf2": snap.get("hmf2") if snap.get("hmf2_measured") else None,
        "stations": cal.get("stations"), "nearest_km": cal.get("nearest_km"),
        "regime": snap.get("regime"),
    }
    _save(day, data)
    return True


def _prune(now):
    """Drop days older than the keep window. Only older: a day the clock
    has not reached is never anybody's to delete, whatever `now` says."""
    if not LEDGER.is_dir():
        return
    oldest = _day(now - timedelta(days=KEEP_DAYS - 1))
    for p in LEDGER.glob("????-??-??.json"):
        if p.stem < oldest:
            try:
                p.unlink()
            except OSError:
                pass


# ------------------------------------------------------------------ reading

def latest(before=None, days=3, now=None):
    """The most recent forecast entry, optionally strictly before an hour."""
    best = None
    for day in _days_back(days, now):
        for e in _load(day)["forecasts"]:
            if before and e["hour"] >= before:
                continue
            if best is None or e["hour"] > best["hour"]:
                best = e
    return best


def _measured_index(days, now=None):
    out = {}
    for day in _days_back(days + 1, now):
        out.update(_load(day)["measured"])
    return out


def skill(days=7, now=None):
    """How the forecast has done against the sondes: by lead and by sky.

    Errors are forecast minus measured, in MHz, so a negative bias means
    the model ran under the sky. `latest` is the one-line version: what was
    said for this hour a day ago against what the sondes read.
    """
    now = now or datetime.now(timezone.utc)
    seen = _measured_index(days, now)
    by_lead, by_regime, by_month = {}, {}, {}
    for day in _days_back(days, now):
        for e in _load(day)["forecasts"]:
            for lead in range(1, len(e["hours"])):
                target = e["hours"][lead]
                got = seen.get(target)
                if not got or e["mufs"][lead] is None:
                    continue
                err = float(e["mufs"][lead]) - float(got["muf"])
                by_lead.setdefault(lead, []).append(err)
                regime = (e["regimes"][lead] if lead < len(e["regimes"]) else None) or "unknown"
                by_regime.setdefault(regime, []).append(err)
                # By the month of the hour forecast, model leads only: a
                # season shows as a season, and the anchor's hours would
                # otherwise flatter every month alike.
                if lead in MODEL_LEADS:
                    by_month.setdefault(target[:7], {}).setdefault(regime, []).append(err)

    def summary(errs):
        n = len(errs)
        if not n:
            return {"n": 0, "bias": None, "mae": None}
        return {"n": n, "bias": round(sum(errs) / n, 2),
                "mae": round(sum(abs(x) for x in errs) / n, 2)}

    # Persistence - "the same as this hour yesterday" - is the yardstick any
    # forecast has to beat at 24 hours. A model that does not beat it is
    # adding shape and no skill, and the honest thing would be to hand the
    # operator yesterday's measured curve instead.
    persist, persist_month = [], {}
    for target, got in seen.items():
        earlier = seen.get(_hour((datetime.fromisoformat(target) - timedelta(hours=24)).isoformat()))
        if earlier and got.get("muf") and earlier.get("muf"):
            err = float(earlier["muf"]) - float(got["muf"])
            persist.append(err)
            persist_month.setdefault(target[:7], []).append(err)

    this_hour = _hour(now.isoformat())
    yesterday = None
    for day in _days_back(2, now):
        for e in _load(day)["forecasts"]:
            if this_hour in e["hours"]:
                lead = e["hours"].index(this_hour)
                if 20 <= lead <= 24 and (yesterday is None or lead > yesterday["lead"]):
                    yesterday = {"lead": lead, "said": e["mufs"][lead], "at": e["at"]}
    got = seen.get(this_hour)
    latest_line = None
    if yesterday and got:
        latest_line = {"lead_h": yesterday["lead"], "forecast": yesterday["said"],
                       "measured": got["muf"], "at": this_hour}
    return {"days": days,
            "n": sum(len(v) for v in by_lead.values()),
            "by_lead": {str(k): summary(v) for k, v in sorted(by_lead.items())},
            "by_regime": {k: summary(v) for k, v in sorted(by_regime.items())},
            "persistence_24h": summary(persist),
            "by_month": {m: {**{r: summary(v) for r, v in sorted(regs.items())},
                             "all": summary([x for v in regs.values() for x in v]),
                             "persistence": summary(persist_month.get(m, []))}
                         for m, regs in sorted(by_month.items())},
            "latest": latest_line}


def adjustment(days=ADJUST_DAYS, now=None):
    """What this unit's record says to add to the model's MUF, by sky.

    Fitted from the model's own hours - leads where the anchor has let go -
    so it measures the model, not the sonde. Applied only where there are
    ADJUST_MIN_N readings for that sky, and never beyond ADJUST_CAP_MHZ. A
    bias past the cap is reported and not applied: that is a broken station
    or a different sky, not a model to be nudged.
    """
    now = now or datetime.now(timezone.utc)
    seen = _measured_index(days, now)
    # Keyed by the measured hour, because that is the independent thing:
    # twenty forecasts made through a day all land on the same twenty-four
    # readings, and counting each landing as evidence would let one night
    # look like a fortnight. One mean per measured hour, then across hours.
    by_regime = {}
    for day in _days_back(days, now):
        for e in _load(day)["forecasts"]:
            for lead in MODEL_LEADS:
                if lead >= len(e["hours"]):
                    break
                target = e["hours"][lead]
                got = seen.get(target)
                if not got or e["mufs"][lead] is None:
                    continue
                regime = (e["regimes"][lead] if lead < len(e["regimes"]) else None) or "unknown"
                # What the model said before any earlier adjustment of its
                # own, so the correction does not compound on itself.
                said = float(e["mufs"][lead])
                prior = (e["inputs"].get("adjustment") or {}).get(regime) or 0.0
                by_regime.setdefault(regime, {}).setdefault(target, []).append(
                    float(got["muf"]) - (said - prior))
    out = {}
    for regime, per_hour in by_regime.items():
        diffs = [sum(v) / len(v) for v in per_hour.values()]
        n = len(diffs)
        raw = sum(diffs) / n
        applied = (max(-ADJUST_CAP_MHZ, min(ADJUST_CAP_MHZ, raw))
                   if n >= ADJUST_MIN_N and abs(raw) <= ADJUST_CAP_MHZ else 0.0)
        out[regime] = {"n": n, "measured_bias": round(raw, 2), "applied": round(applied, 2),
                       "capped": abs(raw) > ADJUST_CAP_MHZ, "enough": n >= ADJUST_MIN_N}
    return out


def applied_bias(adj):
    """The by-sky offsets to hand the model - only the ones being applied."""
    return {k: v["applied"] for k, v in (adj or {}).items() if v.get("applied")}


def drift(previous, entry):
    """Did the outlook move more than its inputs did, between two entries?"""
    if not previous or not entry:
        return None
    prev_idx = {h: i for i, h in enumerate(previous["hours"])}
    pairs = []                    # (i in entry, j in previous) beyond both anchors
    for i, hour in enumerate(entry["hours"]):
        j = prev_idx.get(hour)
        if i >= DRIFT_SKIP_FIRST and j is not None and j >= DRIFT_SKIP_FIRST:
            pairs.append((i, j))
    moved = {}
    # The level: the model's own MUF at the same hour, drawn an hour apart.
    muf_jumps = [abs(float(entry["mufs"][i]) - float(previous["mufs"][j])) for i, j in pairs
                 if entry["mufs"][i] is not None and j < len(previous["mufs"])
                 and previous["mufs"][j] is not None]
    big = [d for d in muf_jumps if d >= DRIFT_MHZ]
    if len(big) >= DRIFT_HOURS:
        moved["MUF"] = round(max(big), 1)
    # The shape: a score that moved while the MUF under it did not.
    for name, scores in entry["bands"].items():
        before = previous["bands"].get(name)
        if not before:
            continue
        diffs = []
        for i, j in pairs:
            if j >= len(before) or j >= len(previous["mufs"]) or entry["mufs"][i] is None \
                    or previous["mufs"][j] is None:
                continue
            if abs(float(entry["mufs"][i]) - float(previous["mufs"][j])) <= DRIFT_SAME_MUF:
                diffs.append(abs(scores[i] - before[j]))
        big = [d for d in diffs if d >= DRIFT_POINTS]
        if len(big) >= DRIFT_HOURS:
            moved[name] = max(big)
    a, b = previous["inputs"], entry["inputs"]

    def far(key):
        x, y = a.get(key), b.get(key)
        if x is None or y is None:
            return x != y
        return abs(float(x) - float(y)) > INPUT_TOLERANCE[key]

    inputs_moved = any(far(k) for k in INPUT_TOLERANCE) or a.get("muf_source") != b.get("muf_source")
    build_changed = (previous.get("build") or "") != (entry.get("build") or "")
    if moved:
        worst = max(moved, key=moved.get)
        unit = "MHz" if worst == "MUF" else "points"
        note = (f"{worst} moved up to {moved[worst]} {unit} at matching hours "
                f"since {previous['hour'][:16]}Z"
                + (f"; build {previous.get('build')} -> {entry.get('build')}" if build_changed else "")
                + ("; the inputs moved too" if inputs_moved
                   else "; the inputs did not move - the model did"))
    else:
        note = ""
    return {"moved": bool(moved), "bands": moved, "inputs_moved": inputs_moved,
            "build_changed": build_changed, "note": note,
            "since": previous["hour"]}


def latest_drift(days=2):
    """The most recent drift the ledger can show, for the page and the report."""
    entries = []
    for day in _days_back(days):
        entries.extend(_load(day)["forecasts"])
    entries.sort(key=lambda e: e["hour"])
    for prev, cur in zip(entries[-3:-1], entries[-2:]):
        v = drift(prev, cur)
        if v and v["moved"]:
            return v
    return None
