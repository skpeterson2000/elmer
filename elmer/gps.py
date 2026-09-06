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
TIMEOUT = 2.5             # seconds to wait for a fix before giving up
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


def read_fix(host=None, port=None, timeout=TIMEOUT):
    """One position from gpsd, or None. Never raises, never waits long."""
    host = host or DEFAULT_HOST
    port = port or DEFAULT_PORT
    deadline = time.monotonic() + timeout
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
    except OSError:
        return None
    try:
        sock.sendall(b'?WATCH={"enable":true,"json":true};\n')
        buffer = b""
        while time.monotonic() < deadline:
            sock.settimeout(max(0.1, deadline - time.monotonic()))
            try:
                chunk = sock.recv(4096)
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
                if message.get("class") != "TPV":
                    continue
                # mode 2 is a 2D fix: position without altitude, which is
                # every answer ELMER needs. mode 1 is "no fix yet" and is not
                # a position at all, whatever else the sentence carries.
                if message.get("mode", 0) < 2 or message.get("lat") is None:
                    continue
                return {"lat": float(message["lat"]),
                        "lon": float(message["lon"]),
                        "alt_m": message.get("alt"),
                        "mode": message.get("mode"),
                        "time": message.get("time"),
                        "read_at": time.time(),
                        "from": f"{host}:{port}"}
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
    return {"lat": found["lat"], "lon": found["lon"], "grid": grid,
            "name": grid, "short": grid, "kind": "gps",
            "alt_m": found.get("alt_m"), "mode": found.get("mode"),
            "source": "gps", "from": found.get("from"),
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
