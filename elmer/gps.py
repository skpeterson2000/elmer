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
                # Every fix says where it came from. Callers were left to
                # assume it when the field was absent, and an assumption about
                # the provenance of a position is the wrong thing to leave to
                # a caller - one of them decides whether to pass it on.
                "source": "gps", "from": f"{host}:{port}"}
    except (TypeError, ValueError):
        return None


def sky_summary(sky):
    """A gpsd SKY report as the three numbers that say how good the fix is:
    satellites used, satellites seen, and HDOP - the geometry."""
    if not isinstance(sky, dict):
        return None
    sats = sky.get("satellites") or []
    out = {"sats": sum(1 for x in sats if x.get("used")), "seen": len(sats)}
    if sky.get("hdop") is not None:
        out["hdop"] = sky.get("hdop")
    return out


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
    sky = None                    # the last SKY seen: satellites and geometry

    def with_sky(found):
        if found and sky:
            found.update(sky)
        return found

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
                if kind == "SKY":
                    sky = sky_summary(message)
                elif kind == "TPV":
                    found = usable(message, host, port)
                    if found:
                        return with_sky(found)
                elif kind == "POLL":
                    # The cached answer: a list of reports, newest first.
                    for one in message.get("sky") or []:
                        sky = sky_summary(one) or sky
                        break
                    for tpv in message.get("tpv") or []:
                        found = usable(tpv, host, port)
                        if found:
                            return with_sky(found)
    except OSError:
        return None
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return None


def probe(host=None, port=None, seconds=4.0):
    """Everything gpsd says, verbatim, for somebody working out why.

    Two programs on one Pi reading one gpsd and disagreeing about whether there
    is a fix is not a thing to reason about from a distance. This reports the
    conversation itself - which devices gpsd has, what it answers a poll with,
    and what it streams - so the question becomes what gpsd said rather than
    what anybody believes it said.
    """
    host = host or DEFAULT_HOST
    port = port or DEFAULT_PORT
    out = {"host": f"{host}:{port}", "connected": False, "messages": [],
           "devices": [], "poll": None, "tpv": [], "sky": [],
           "usable_fix": None, "error": None}
    deadline = time.monotonic() + seconds
    try:
        sock = socket.create_connection((host, port), timeout=min(3.0, seconds))
    except OSError as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    out["connected"] = True
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
                out["messages"].append(kind)
                if kind == "DEVICES":
                    out["devices"] = [
                        {"path": d.get("path"), "driver": d.get("driver"),
                         "activated": d.get("activated"), "bps": d.get("bps")}
                        for d in message.get("devices") or []]
                elif kind == "POLL":
                    out["poll"] = {"active": message.get("active"),
                                   "tpv": message.get("tpv") or []}
                elif kind == "TPV":
                    out["tpv"].append({k: message.get(k) for k in
                                       ("mode", "lat", "lon", "alt", "time",
                                        "status", "device")})
                elif kind == "SKY":
                    sats = message.get("satellites") or []
                    out["sky"].append({
                        "seen": len(sats),
                        "used": sum(1 for s in sats if s.get("used")),
                        "hdop": message.get("hdop")})
                if out["usable_fix"] is None:
                    found = usable(message, host, port)
                    if found is None and kind == "POLL":
                        for one in message.get("tpv") or []:
                            found = usable(one, host, port)
                            if found:
                                break
                    if found:
                        out["usable_fix"] = found
    except OSError as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return out


_refresh = {"thread": None}


def fix(conn=None, max_age=FRESH_FOR):
    """The current position, as last found - never a live read on the
    caller's time.

    Thirty seconds is half a mile at highway speed, which is nothing to an
    antenna pattern and everything to a page that would otherwise open a
    socket for each of six panels. And a page that asks after the answer
    has gone stale gets the last one at once while a thread goes looking:
    the probe for a receiver - gpsd, TowerWitch, a phone, another ELMER -
    took two seconds to come back empty on a laptop with none, and it was
    landing on whichever page asked first, every half minute; the home
    page, mostly, and the launcher waiting on it.
    """
    now = time.time()
    if now - _last["at"] >= max_age:
        t = _refresh["thread"]
        if t is None or not t.is_alive():
            import threading
            host, port = target(conn)
            t = threading.Thread(target=_look, args=(host, port), name="gps-fix", daemon=True)
            _refresh["thread"] = t
            t.start()
    # The last answer, including "there is nothing there" - and a fix that
    # has gone quiet is still where you are for a few minutes; a tunnel is
    # not a teleport. Past that, stop claiming to know.
    if _last["fix"] and now - _last["fix"]["read_at"] >= STALE_AFTER:
        _last["fix"] = None
    # With no answer in hand, the sources that cost nothing to ask are asked
    # now: TowerWitch's broadcast and a phone's stream are already in memory,
    # read by their own threads. Without this the first "locate me" after a
    # start lost: the probe ran a second in, before TowerWitch's first packet,
    # and every ask for the next half minute repeated its empty answer while
    # the position sat in the listener. gpsd still outranks them - the probe
    # replaces this with the receiver's own fix as soon as it has one.
    if not _last["fix"]:
        from . import towerwitch, phonegps
        cheap = towerwitch.current() or phonegps.current()
        if cheap:
            _last["fix"] = cheap
    return _last["fix"]


def _look(host, port):
    """One probe for a fix, off the request path: what fix() used to do
    on the caller's time. The sources in the order they are trusted."""
    now = time.time()
    found = read_fix(host, port)
    if not found:
        # The station's own GPS, taken off the network where TowerWitch puts
        # it. One receiver in the vehicle, every device knowing where it is -
        # which is the arrangement, and it wants no configuring at either end.
        from . import towerwitch
        found = towerwitch.current()
    if not found:
        # No receiver, or none with a lock. A phone streaming NMEA at this unit
        # is the fallback, and for a station with no antenna on a lead it is
        # the only source there is - which is the case it exists for. A real
        # receiver still wins when there is one, so this is only consulted
        # after gpsd has been asked and had nothing to say.
        from . import phonegps
        found = phonegps.current()
    if not found:
        # Another ELMER on the same network that has a receiver. It announces
        # its fix; this one takes it. Same idea as TowerWitch's broadcast and
        # deliberately separate: that is the arrangement when TowerWitch is
        # running, this one holds when it is not.
        from . import discovery
        found = discovery.borrowed_fix()
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
                     # Said out loud, because the paragraph above claims this
                     # is not presented as a live fix and it was: it came back
                     # from place() like any other and outranked the QTH the
                     # operator had typed. A position read out of another
                     # program's state file is the answer when there is no
                     # other; it is not news from a receiver. See qth_for().
                     "last_known": True,
                     "from": "TowerWitch's last known position"}
    _last["at"] = now
    if found:
        _last["fix"] = found
    elif _last["fix"] and now - _last["fix"]["read_at"] >= STALE_AFTER:
        _last["fix"] = None
    return _last["fix"]


# ------------------------------------------------------------- the sleuth
# Where the position comes from, and what to do when it goes. A phone in a
# pocket loses the sky; a puck under the dash sees half of it; a receiver
# that is fine on the bench is not fine behind a windscreen with a heated
# element in it. The fix says where it came from; this watches how it has
# been going and says which antenna to move, or when a phone is not going
# to be enough and a receiver on a lead is the move.

WATCH_EVERY = 20.0          # seconds between samples
HISTORY_S = 900.0           # how much of the recent past the verdict reads
_history = []               # samples, oldest first: {t, located, source, mode, sats, hdop}
_watch = {"thread": None, "stop": None}


def _sample(conn=None):
    found = fix(conn, max_age=0.0)
    now = time.time()
    _history.append({"t": now, "located": bool(found),
                     "source": (found or {}).get("source"), "mode": (found or {}).get("mode"),
                     "sats": (found or {}).get("sats"), "hdop": (found or {}).get("hdop"),
                     "stale": bool(found and now - found["read_at"] > FRESH_FOR * 2)})
    while _history and now - _history[0]["t"] > HISTORY_S:
        _history.pop(0)


def start_watch(every=WATCH_EVERY):
    """Sample the position steadily in the background, so the verdict is
    read from how the fix has actually been going and not from one look."""
    import threading
    if _watch["thread"] and _watch["thread"].is_alive():
        return _watch["thread"]
    stop = threading.Event()

    def run():
        while not stop.is_set():
            try:
                _sample()
            except Exception:                    # pragma: no cover
                pass
            stop.wait(every)
    t = threading.Thread(target=run, daemon=True, name="gps-watch")
    t.start()
    _watch["thread"], _watch["stop"] = t, stop
    return t


def stop_watch():
    if _watch["stop"]:
        _watch["stop"].set()


SOURCE_WORDS = {
    "gps": "a receiver on this unit (gpsd)",
    "towerwitch": "TowerWitch's receiver, over the network",
    "phone": "a phone streaming to this unit",
    "elmer": "another ELMER's receiver, over the network",
}


def sleuth(found, history=None):
    """The source in words, how it has been going, and what to do about it.

    Returns {"source", "words", "quality", "drops", "advice"}; `advice` is
    None when there is nothing to say - a receiver with a good fix that has
    held is a receiver to leave alone.
    """
    hist = _history if history is None else history
    now = time.time()
    recent = [h for h in hist if now - h["t"] <= HISTORY_S]
    drops = sum(1 for a, b in zip(recent, recent[1:]) if a["located"] and not b["located"])
    weak = sum(1 for h in recent if h["located"] and (
        (h.get("sats") is not None and h["sats"] < 5) or (h.get("hdop") is not None and h["hdop"] > 5)))
    out = {"source": None, "words": "no position from anywhere", "quality": None,
           "drops": drops, "samples": len(recent), "advice": None}
    if not found:
        from . import phonegps
        phone = phonegps.listener()
        if recent and any(h["located"] for h in recent):
            last = next(h for h in reversed(recent) if h["located"])
            out["words"] = f"the fix from {SOURCE_WORDS.get(last['source'], last['source'] or 'somewhere')} has gone"
            if last["source"] == "phone":
                out["advice"] = ("the phone has lost the sky - a pocket, a footwell or a metal roof will do it. "
                                 "Put it on the dash or by a window; if it keeps going, a phone is not going to "
                                 "be enough here and a USB receiver on the dash (a u-blox puck, about $15) is the move")
            elif last["source"] in ("gps", "towerwitch"):
                out["advice"] = ("the receiver has lost its fix - move the puck: the dash, the roof, away from the "
                                 "metal and any heated glass; a magnet mount on the roof sees the whole sky")
        elif phone and phone.sentences == 0:
            out["advice"] = (f"a phone app is expected on udp/{phone.port} but nothing has arrived - check the app "
                             f"is sending to this unit's address, not the phone's own")
        return out
    src = found.get("source") or "gps"
    out["source"] = src
    out["words"] = SOURCE_WORDS.get(src, found.get("from") or src)
    bits = []
    if found.get("mode"):
        bits.append(f"{found['mode']}D")
    if found.get("sats") is not None:
        bits.append(f"{found['sats']} satellites" + (f" of {found['seen']} seen" if found.get("seen") else ""))
    if found.get("hdop") is not None:
        bits.append(f"HDOP {found['hdop']}")
    out["quality"] = ", ".join(bits) if bits else None
    if src == "phone":
        if drops >= 2 or weak >= 3:
            out["advice"] = (f"the phone's fix has dropped {drops} time{'s' if drops != 1 else ''} in the last "
                             f"{HISTORY_S / 60:.0f} minutes - it is not seeing enough sky where it sits. On the "
                             f"dash or by a window it may hold; if not, a phone is not going to be enough here and "
                             f"a USB receiver on the dash (a u-blox puck, about $15) is the move")
    elif src in ("gps", "towerwitch"):
        poor = (found.get("mode") == 2 or (found.get("sats") is not None and found["sats"] < 5)
                or (found.get("hdop") is not None and found["hdop"] > 5))
        if poor or drops >= 2:
            out["advice"] = ("the receiver is short of satellites" +
                             (f" - {found['sats']} in use" if found.get("sats") is not None else "") +
                             (f", dropped {drops} times lately" if drops else "") +
                             " - move the puck: the dash, the roof, away from the metal and any heated glass; "
                             "a magnet mount on the roof sees the whole sky")
    return out


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
            "sats": found.get("sats"), "seen": found.get("seen"), "hdop": found.get("hdop"),
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
