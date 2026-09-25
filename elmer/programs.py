"""What has worked for other people at a park or a summit.

Somebody planning a Saturday at a park wants three things a rule book does
not carry: whether people actually make their ten there, what they make it
on, and when. Both programs publish that - POTA keeps every activation
with its CW, data and phone counts, and SOTA keeps every activation with
its QSO count - keyed by the reference, with no login. So this fetches a
place's record, reads a story out of it, and keeps it on disk so that the
story is still there at the park, where the signal is not.

What the story is not: a prediction. It is what the last few hundred people
did, which is the best guide there is to what the next one will do, and the
words say so.
"""
import json
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone

from . import activations, paths

CACHE = paths.STATE / "programs"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"
TIMEOUT = 20
MAX_AGE_SECONDS = 24 * 3600
# Enough activations to make a story from, and a bounded request at a park
# that has had thousands. The total still comes from the stats endpoint.
SAMPLE = 400

POTA_PARK = "https://api.pota.app/park/{ref}"
POTA_STATS = "https://api.pota.app/park/stats/{ref}"
POTA_ACTIVATIONS = "https://api.pota.app/park/activations/{ref}?count={count}"
SOTA_SUMMIT = "https://api2.sota.org.uk/api/summits/{ref}"
SOTA_ACTIVATIONS = "https://api2.sota.org.uk/api/activations/{ref}"

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def kind_of(ref):
    """'park' for a POTA reference, 'summit' for a SOTA one, else None."""
    ref = (ref or "").strip().upper()
    if "/" in ref and "-" in ref:
        return "summit"
    if "-" in ref and ref.split("-")[-1].isdigit():
        return "park"
    return None


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def _story(rows, qualifies):
    """The record read out: how many made it, on what, when, and lately.
    `rows` are (date, qsos, cw, data, phone) with the mode counts None where
    the program does not keep them."""
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: r[0], reverse=True)
    qsos = [r[1] for r in rows if r[1] is not None]
    months = Counter(r[0].month for r in rows)
    busiest = [MONTHS[m - 1] for m, _ in months.most_common(3)]
    out = {
        "sample": len(rows),
        "typical_qsos": round(statistics.median(qsos)) if qsos else None,
        "made_it": round(100 * sum(1 for q in qsos if q >= qualifies) / len(qsos)) if qsos else None,
        "busiest": busiest,
        "by_month": [months.get(m, 0) for m in range(1, 13)],
        "last": rows[0][0].date().isoformat(),
        "recent": [{"date": r[0].date().isoformat(), "qsos": r[1], "call": r[5]} for r in rows[:5]],
    }
    cw, data, phone = (sum(r[n] or 0 for r in rows) for n in (2, 3, 4))
    total = cw + data + phone
    if total:
        out["modes"] = {"cw": round(100 * cw / total), "data": round(100 * data / total),
                        "phone": round(100 * phone / total)}
    return out


def _pota(ref):
    park = _get(POTA_PARK.format(ref=ref)) or {}
    if not park.get("reference"):
        return {"ok": False, "found": False, "error": f"POTA has no park {ref}"}
    stats = _get(POTA_STATS.format(ref=ref)) or {}
    rows = []
    for a in _get(POTA_ACTIVATIONS.format(ref=ref, count=SAMPLE)) or []:
        try:
            when = datetime.strptime(str(a.get("qso_date")), "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        rows.append((when, a.get("totalQSOs"), a.get("qsosCW"), a.get("qsosDATA"),
                     a.get("qsosPHONE"), a.get("activeCallsign") or ""))
    return {
        "ok": True, "found": True, "kind": "park", "ref": park["reference"],
        "name": park.get("name") or ref, "lat": park.get("latitude"), "lon": park.get("longitude"),
        "grid": park.get("grid6") or park.get("grid4") or "", "where": park.get("locationDesc") or "",
        "type": park.get("parktypeDesc") or "", "agency": park.get("agencies") or "",
        "website": park.get("website") or "",
        "access": park.get("accessMethods") or "", "methods": park.get("activationMethods") or "",
        "totals": {"attempts": stats.get("attempts"), "activations": stats.get("activations"),
                   "qsos": stats.get("contacts")},
        "qualifies": activations.POTA["qualifies"],
        "story": _story(rows, activations.POTA["qualifies"]),
    }


def _sota(ref):
    summit = _get(SOTA_SUMMIT.format(ref=ref)) or {}
    if not summit.get("summitCode"):
        return {"ok": False, "found": False, "error": f"SOTA has no summit {ref}"}
    rows = []
    for a in _get(SOTA_ACTIVATIONS.format(ref=ref)) or []:
        try:
            when = datetime.fromisoformat(str(a.get("activationDate")).replace("Z", "+00:00"))
        except ValueError:
            continue
        rows.append((when, a.get("qsos"), None, None, None, a.get("ownCallsign") or ""))
    return {
        "ok": True, "found": True, "kind": "summit", "ref": summit["summitCode"],
        "name": summit.get("name") or ref, "lat": summit.get("latitude"), "lon": summit.get("longitude"),
        "grid": summit.get("locator") or "", "where": summit.get("regionName") or "",
        "alt_m": summit.get("altM"), "alt_ft": summit.get("altFt"), "points": summit.get("points"),
        "association": summit.get("associationName") or "",
        "totals": {"activations": len(rows) or summit.get("activationCount")},
        "qualifies": activations.SOTA["qualifies"],
        "story": _story(rows, activations.SOTA["qualifies"]),
    }


def lookup(ref, refresh=False):
    """A park's or a summit's record, from disk where it is fresh enough,
    else from the program; what is on disk beats nothing when the network
    is gone, and says how old it is."""
    ref = (ref or "").strip().upper()
    kind = kind_of(ref)
    if not kind:
        return {"ok": False, "found": False, "ref": ref,
                "error": "that is not a POTA park (US-0690) or a SOTA summit (W0D/BB-001) reference"}
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{ref.replace('/', '_')}.json"
    cached = None
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
        if cached and not refresh and time.time() - cached.get("fetched_at", 0) < MAX_AGE_SECONDS:
            cached["cached"] = True
            return cached
    try:
        out = _pota(ref) if kind == "park" else _sota(ref)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"ok": False, "found": False, "ref": ref, "error": f"no {kind} {ref} in the program's list"}
        return _fallback(cached, ref, f"the program answered {exc.code}")
    except Exception as exc:                       # network, timeout, garbage
        return _fallback(cached, ref, f"could not reach the program ({exc})")
    out["ref"] = out.get("ref") or ref
    out["fetched_at"] = time.time()
    try:
        path.write_text(json.dumps(out), encoding="utf-8")
    except OSError:
        pass
    return out


def _fallback(cached, ref, error):
    if cached:
        cached["cached"] = True
        cached["stale"] = True
        cached["error"] = error
        return cached
    return {"ok": False, "found": False, "ref": ref, "error": error}


def sentence(record):
    """The story in one paragraph, for a card."""
    story = record.get("story")
    if not story:
        return "No activations on record yet - the first one writes the story."
    parts = []
    totals = record.get("totals") or {}
    n = totals.get("activations") or story["sample"]
    parts.append(f"{n} activation{'s' if n != 1 else ''} on record" +
                 (f", {totals['qsos']:,} contacts" if totals.get("qsos") else "") + ".")
    if story.get("modes"):
        m = story["modes"]
        parts.append(f"Of the last {story['sample']}, contacts were {m['phone']}% phone, "
                     f"{m['cw']}% CW and {m['data']}% data.")
    if story.get("typical_qsos") is not None:
        parts.append(f"The typical activation made {story['typical_qsos']} QSOs and "
                     f"{story['made_it']}% got their {record.get('qualifies')}.")
    if story.get("busiest"):
        months = story["busiest"]
        parts.append("Busiest in " + (months[0] if len(months) == 1
                                      else ", ".join(months[:-1]) + " and " + months[-1]) + ".")
    last = story["recent"][0] if story.get("recent") else None
    if last:
        parts.append(f"Last activated {last['date']}" +
                     (f" by {last['call']}" if last.get("call") else "") +
                     (f", {last['qsos']} QSOs" if last.get("qsos") is not None else "") + ".")
    return " ".join(parts)
