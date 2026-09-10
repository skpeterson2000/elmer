"""Parks on the Air awards, which are public and belong to the operator.

People pay for a second way to show what they have earned. A good deal of it is
already published, free, keyed by callsign - and POTA's profile endpoint is the
part that needs no key, no subscription and no password. So ELMER can show an
operator their own awards beside their name, and can look up anybody else's,
which is the more interesting half: work a station, put their call in, and see
what they have been doing.

    Not every award is reachable, and the famous ones are the ones that are
    not. DXCC, WAS, VUCC and WAC live in Logbook of the World behind the
    operator's own login - asking for that password is a different and much
    larger commitment than a lookup, and this module does not make it. QRZ's
    logbook API wants a paid subscription key. So this is named for what it is
    rather than "Awards", because a panel titled Awards that cannot show
    somebody's DXCC is not modest, it is wrong.

What is kept is the awards and the counts. The endpoint also returns the
operator's name, their town and a gravatar hash; :mod:`elmer.callsign` already
set the precedent for that - the FCC record it reads carries a name and street
address, and it keeps neither, because there is no reason for this program to
hold them. The same reasoning applies here and the same choice is made.
"""
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "pota"
API = "https://api.pota.app/profile/{call}"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"

# Awards move slowly; the hunt counts move whenever somebody works a park. A
# day is short enough that a weekend's activity shows up and long enough that
# opening the dashboard twenty times costs one request.
MAX_AGE_SECONDS = 24 * 3600

# Every amateur callsign carries a digit and a letter, which is enough to
# turn away a typed sentence without a request going out over the network.
# Slashes are allowed because portable and reciprocal calls use them.
RE_CALL = re.compile(r"^(?=.*[0-9])(?=.*[A-Z])[A-Z0-9/]{3,16}$")


def normalise(call):
    return re.sub(r"\s+", "", (call or "")).upper()


def _keep(raw):
    """The awards and the counts, and deliberately nothing else.

    Sorted newest first, because the most recent one is the one somebody wants
    to see and the list is otherwise in whatever order it arrived.
    """
    stats = raw.get("stats") or {}
    awards = []
    for row in raw.get("awards") or []:
        name = (row.get("name") or "").strip()
        if not name:
            continue
        awards.append({
            "name": name,
            "granted": (row.get("granted") or "")[:10],       # the date, not the second
            "endorsements": [e for e in (row.get("endorsements") or []) if e],
        })
    awards.sort(key=lambda a: a["granted"], reverse=True)
    hunter = stats.get("hunter") or {}
    activator = stats.get("activator") or {}
    return {
        "awards": awards,
        "hunter": {"parks": hunter.get("parks") or 0,
                   "qsos": hunter.get("qsos") or 0},
        "activator": {"activations": activator.get("activations") or 0,
                      "parks": activator.get("parks") or 0,
                      "qsos": activator.get("qsos") or 0},
        "endorsements": stats.get("endorsements") or 0,
    }


def _fetch(call):
    request = urllib.request.Request(API.format(call=call),
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=12) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def lookup(call, refresh=False):
    """One operator's POTA record, from cache where it can be.

    Returns a dict with `ok`. A callsign with no POTA profile is `ok` False and
    `found` False, which is not an error - most licensees have never chased a
    park, and saying so plainly is better than an apology.

    With no network and something on disk, the cached copy is returned however
    old it is, marked `stale`. A unit in a field should still show what it knew
    last time rather than an empty panel.
    """
    call = normalise(call)
    if not RE_CALL.match(call):
        return {"ok": False, "found": False, "call": call,
                "error": "that is not a callsign"}
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{call.replace('/', '-')}.json"
    cached = None
    if path.exists():
        try:
            cached = json.loads(path.read_text())
        except (OSError, ValueError):
            cached = None
        if cached and not refresh:
            age = time.time() - cached.get("fetched_at", 0)
            if age < MAX_AGE_SECONDS:
                cached["cached"] = True
                return cached

    try:
        raw = _fetch(call)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            out = {"ok": False, "found": False, "call": call,
                   "error": "no POTA record for this callsign",
                   "fetched_at": time.time()}
            try:
                path.write_text(json.dumps(out))
            except OSError:
                pass
            return out
        return _fallback(cached, call, f"POTA returned {exc.code}")
    except Exception as exc:                       # network, timeout, garbage
        return _fallback(cached, call, f"could not reach POTA ({exc})")

    out = {"ok": True, "found": True, "call": call, "fetched_at": time.time()}
    out.update(_keep(raw))
    try:
        path.write_text(json.dumps(out))
    except OSError:
        pass
    return out


def _fallback(cached, call, error):
    """What is on disk beats nothing, and it says how old it is."""
    if cached:
        cached["cached"] = True
        cached["stale"] = True
        cached["error"] = error
        return cached
    return {"ok": False, "found": False, "call": call, "error": error}


def summary(record):
    """One line for a panel that has room for one line."""
    if not record or not record.get("found"):
        return ""
    awards = record.get("awards") or []
    hunter = record.get("hunter") or {}
    bits = []
    if awards:
        bits.append("%d award%s" % (len(awards), "" if len(awards) == 1 else "s"))
    if hunter.get("parks"):
        bits.append("%d parks hunted" % hunter["parks"])
    activator = record.get("activator") or {}
    if activator.get("activations"):
        bits.append("%d activations" % activator["activations"])
    return ", ".join(bits)
