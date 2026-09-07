"""Where the station actually is, when something is willing to say.

A Pi in a Jeep is not at the QTH somebody typed in last winter, and every
answer ELMER gives about reach, bearings and exposure is an answer about a
place. So when a GPS is reachable, the fix wins; when it is not, the QTH that
was typed in wins, because that is what makes the program work in a field with
no network - which was the point of typing it in.

gpsd is read directly over its own protocol rather than through any of the
other station software, because gpsd already listens and needs nothing built.
`ELMER_GPSD`, or the `gpsd` unit setting, points this at another machine: a
second Pi in the same vehicle reads the one with the antenna on it.

Nothing here blocks for long or raises. A GPS that is missing, silent, or has
no fix yet is an ordinary Tuesday, and the honest answer to "where am I" is
then the one the operator gave.
"""
import json
import os
import socket
import time

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2947
# Long enough for a receiver that reports every few seconds to get a word in.
# ?POLL usually answers instantly, so this is the safety net rather than the
# normal path - and a unit with no GPS at all still fails in well under it,
# because nothing is listening and the connection is refused outright.
TIMEOUT = 5.0             # seconds to wait for a fix before giving up
FRESH_FOR = 30.0          # how long a fix is reused before asking again
STALE_AFTER = 300.0       # a fix older than this is history, not position

_last = {"at": 0.0, "fix": None}


def target(conn=None):
    """Which gpsd to ask: the unit setting, the environment, or this machine."""
    where = None
    if conn is not None:
        try:
            from . import db
            where = db.unit_get(conn, "gpsd")
        except Exception:
            where = None
    where = where or os.environ.get("ELMER_GPSD") or DEFAULT_HOST
    host, _, port = str(where).partition(":")
    try:
        port = int(port) if port else DEFAULT_PORT
    except ValueError:
        port = DEFAULT_PORT
    return host.strip() or DEFAULT_HOST, port


def usable(tpv, host="", port=0):
    """One gpsd TPV report as a fix, or None if it is not one.

    mode 2 is a 2D fix - position without altitude, which is every answer
    ELMER needs. mode 1 is "no fix yet" and is not a position at all, whatever
    else the report carries.
    """
    if not isinstance(tpv, dict) or tpv.get("class") not in (None, "TPV"):
        return None
    if tpv.get("mode", 0) < 2 or tpv.get("lat") is None:
        return None
    try:
        return {"lat": float(tpv["lat"]), "lon": float(tpv["lon"]),
                "alt_m": tpv.get("alt"), "mode": tpv.get("mode"),
                "time": tpv.get("time"), "read_at": time.time(),
                "from": f"{host}:{port}"}
    except (TypeError, ValueError):
        return None


def read_fix(host=None, port=None, timeout=TIMEOUT):
    """One position from gpsd, or None. Never raises, never waits long.

    Asks two ways at once, because watching alone was not enough. ?WATCH only
    delivers a report when the receiver next sends one, so the wait is however
    long that device's cycle happens to be - and a receiver reporting every few
    seconds put a perfectly good fix on the far side of the timeout. A station
    was reported as unable to find itself while the other program on the same
    Pi was showing a 3D fix on twelve satellites, which is exactly that.

    ?POLL asks gpsd for what it already knows instead, and answers immediately
    from its cache. Both are sent; whichever arrives first is the answer.
    """
    host = host or DEFAULT_HOST
    port = port or DEFAULT_PORT
    deadline = time.monotonic() + timeout
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return None
    try:
        sock.sendall(b'?WATCH={"enable":true,"json":true};\n?POLL;\n')
        buffer = b""
        while time.monotonic() < deadline:
            sock.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                chunk = sock.recv(8192)
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                kind = message.get("class")
                if kind == "TPV":
                    found = usable(message, host, port)
                    if found:
                        return found
                elif kind == "POLL":
                    # The cached answer: a list of reports, newest first.
                    for tpv in message.get("tpv") or []:
                        found = usable(tpv, host, port)
                        if found:
                            return found
    except OSError:
        return None
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return None


def fix(conn=None, max_age=FRESH_FOR):
    """The current position, cached briefly so a page load is not a GPS read.

    Thirty seconds is half a mile at highway speed, which is nothing to an
    antenna pattern and everything to a page that would otherwise open a
    socket for each of six panels.
    """
    now = time.time()
    if now - _last["at"] < max_age:
        # Reuse the last answer, including "there is nothing there". A gpsd
        # that is switched off must cost one timeout every half minute, not
        # one per panel on every page.
        return _last["fix"]
    host, port = target(conn)
    found = read_fix(host, port)
    if not found:
        # No receiver, or none with a lock. A phone streaming NMEA at this unit
        # is the fallback, and for a station with no antenna on a lead it is
        # the only source there is - which is the case it exists for. A real
        # receiver still wins when there is one, so this is only consulted
        # after gpsd has been asked and had nothing to say.
        from . import phonegps
        found = phonegps.current()
    if not found:
        # Last, what TowerWitch last knew. It is not a live fix and is not
        # presented as one - the age it was written travels with it - but on a
        # unit where TowerWitch has been running and ELMER has just started, it
        # is the difference between knowing roughly where the station is and
        # knowing nothing at all.
        from . import repeaters
        borrowed = repeaters.last_position()
        if borrowed:
            found = {"lat": borrowed["lat"], "lon": borrowed["lon"],
                     "alt_m": None, "mode": 2,
                     "read_at": time.time() - (borrowed["age_s"] or 0.0),
                     "source": "towerwitch", "town": borrowed.get("town"),
                     "from": "TowerWitch's last known position"}
    _last["at"] = now
    if found:
        _last["fix"] = found
        return found
    # A fix that has gone quiet is still where you are for a few minutes - a
    # tunnel is not a teleport. Past that, stop claiming to know.
    if _last["fix"] and now - _last["fix"]["read_at"] < STALE_AFTER:
        return _last["fix"]
    _last["fix"] = None
    return None


def place(conn=None):
    """The fix as a location, shaped the way a saved QTH is shaped."""
    found = fix(conn)
    if not found:
        return None
    from .geocode import to_grid
    grid = to_grid(found["lat"], found["lon"])
    # A position borrowed from TowerWitch keeps the town it knew, because
    # "Pequot Lakes" is a more honest label than a grid square implying a fix.
    short = found.get("town") or grid
    return {"lat": found["lat"], "lon": found["lon"], "grid": grid,
            "name": short, "short": short, "kind": "gps",
            "alt_m": found.get("alt_m"), "mode": found.get("mode"),
            # Say which it came from. A fix off somebody's handset and a fix
            # off a receiver on the roof are both positions, but an operator
            # deciding whether to trust a bearing deserves to know which.
            "source": found.get("source", "gps"), "from": found.get("from"),
            "age_s": round(max(0.0, time.time() - found["read_at"]), 1)}


def enabled(conn=None):
    """Whether to look at all. Off is a choice somebody may have made."""
    if conn is None:
        return True
    try:
        from . import db
        return db.unit_get(conn, "gps", "auto") != "off"
    except Exception:
        return True
