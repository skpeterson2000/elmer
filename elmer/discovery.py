"""One ELMER noticing another on the same network.

Two Pis in a vehicle, or four on a club table, and neither knowing the other is
there. That is a waste twice over: one of them may have a GPS antenna and a
lock while the other has been guessing for ten minutes, and either could have
been running a tournament against the other all evening.

So each unit says hello on the network every few seconds, and listens for the
others. Nothing is configured at either end - a station is heard or it is not,
and one that goes quiet drops off the list by itself.

Two things come of it.

**Position.** A unit with a receiver announces its fix, and a unit without one
takes it. That is the same idea as TowerWitch's broadcast and deliberately
separate from it: TowerWitch's is the arrangement when TowerWitch is running,
and this one holds when it is not, or when the machine with the antenna is
simply another ELMER. A station that has a lock should not have to be asked.

**Company.** Knowing another ELMER is there is what makes it possible to
suggest a tournament, which is the point of having built one. The suggestion is
made and nothing more: a unit never starts a round on another unit's say-so.

What is announced is what a neighbour needs to be useful - who this is, where
to reach it, whether it has a position, and whether a game is on. Not the
operator's name, not their progress, not their callsign. It goes to the local
broadcast address and nowhere else, and position sharing can be switched off
without switching off discovery.
"""
import json
import logging
import socket
import threading
import time

log = logging.getLogger("elmer")

# Adjacent to TowerWitch's 12345, so a network that lets one through tends to
# let the other, and the pair are easy to remember together.
DEFAULT_PORT = 12346
ANNOUNCE_EVERY = 8.0
# Three missed announcements and a unit has gone: shut down, moved, or off the
# air. Long enough that a busy Pi missing one does not vanish from the list.
GONE_AFTER = 30.0
MAGIC = "elmer-unit"


def _payload(unit, name, url, version, fix, party, share_position=True):
    """What this unit tells the network about itself."""
    out = {"elmer": MAGIC, "unit": unit, "name": name, "url": url,
           "version": version, "sent": time.time()}
    # Never pass on a position borrowed from another unit. Two units without
    # receivers would echo one between themselves for ever: neither could age
    # it out, because each would keep hearing it refreshed by the other, and
    # no one looking at either screen could tell it came from no antenna at
    # all. The caller checks this too; it is guarded here as well because this
    # is the function that actually puts bytes on the wire, and a loop like
    # that is silent while it happens.
    if fix and fix.get("source") == "elmer-peer":
        fix = None
    if fix and share_position:
        # The fix travels with the announcement, so a unit without a receiver
        # needs no second request to be useful - it simply knows.
        out["gps"] = {"lat": fix["lat"], "lon": fix["lon"],
                      "mode": fix.get("mode"), "source": fix.get("source", "gps"),
                      "age_s": round(max(0.0, time.time() - fix["read_at"]), 1)}
    out["party"] = party or {}
    return json.dumps(out).encode()


def parse(data, sender_ip):
    """One announcement, or None if it is not one of ours."""
    try:
        got = json.loads(data.decode("utf-8", "ignore"))
    except (ValueError, AttributeError):
        return None
    if not isinstance(got, dict) or got.get("elmer") != MAGIC:
        return None
    unit = str(got.get("unit") or "")[:40]
    if not unit:
        return None
    peer = {"unit": unit, "name": str(got.get("name") or unit)[:60],
            "url": str(got.get("url") or "")[:120],
            "version": str(got.get("version") or "")[:40],
            "address": sender_ip, "heard_at": time.time(),
            "party": got.get("party") or {}}
    gps = got.get("gps")
    if isinstance(gps, dict):
        try:
            lat, lon = float(gps["lat"]), float(gps["lon"])
        except (KeyError, TypeError, ValueError):
            lat = lon = None
        if lat is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
            peer["gps"] = {"lat": lat, "lon": lon,
                           "mode": gps.get("mode") or 2,
                           "source": gps.get("source"),
                           "age_s": gps.get("age_s")}
    return peer


class Neighbourhood:
    """Everyone else running ELMER here, and this unit saying it is here too."""

    def __init__(self, port=DEFAULT_PORT, describe=None):
        self.port = int(port)
        self.describe = describe          # callable() -> the payload arguments
        self.sock = None
        self.stop = threading.Event()
        self.listener = None
        self.announcer = None
        self.peers = {}
        self.lock = threading.Lock()
        self.sent = 0
        self.heard = 0
        self.error = None

    # ------------------------------------------------------------- listening

    def _listen(self):
        while not self.stop.is_set():
            try:
                data, sender = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            peer = parse(data, sender[0])
            if peer is None:
                continue
            with self.lock:
                mine = self.describe() if self.describe else {}
                if peer["unit"] == (mine.get("unit") or ""):
                    continue              # this unit hearing its own broadcast
                first = peer["unit"] not in self.peers
                self.peers[peer["unit"]] = peer
                self.heard += 1
            if first:
                log.info("another ELMER on the network: %s at %s",
                         peer["name"], peer["address"])

    # ----------------------------------------------------------- announcing

    def _announce_once(self):
        if not self.describe:
            return
        mine = self.describe()
        data = _payload(mine.get("unit", ""), mine.get("name", ""),
                        mine.get("url", ""), mine.get("version", ""),
                        mine.get("fix"), mine.get("party"),
                        mine.get("share_position", True))
        self.sock.sendto(data, ("255.255.255.255", self.port))
        self.sent += 1

    def _announce(self):
        while not self.stop.is_set():
            try:
                self._announce_once()
            except OSError as exc:
                self.error = f"{type(exc).__name__}: {exc}"
            except Exception as exc:                  # pragma: no cover
                self.error = repr(exc)
                log.debug("discovery announce: %s", exc)
            self.stop.wait(ANNOUNCE_EVERY)

    # ---------------------------------------------------------------- roster

    def current(self):
        """The units heard from recently, most recently first."""
        now = time.time()
        with self.lock:
            live = [dict(p, quiet_for=round(now - p["heard_at"], 1))
                    for p in self.peers.values()
                    if now - p["heard_at"] <= GONE_AFTER]
        return sorted(live, key=lambda p: p["quiet_for"])

    def with_fix(self):
        """A neighbour that knows where it is, if any does."""
        for peer in self.current():
            if peer.get("gps"):
                return peer
        return None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.settimeout(1.0)
        self.sock.bind(("", self.port))
        self.listener = threading.Thread(target=self._listen, daemon=True,
                                         name="elmer-discovery-listen")
        self.announcer = threading.Thread(target=self._announce, daemon=True,
                                          name="elmer-discovery-announce")
        self.listener.start()
        self.announcer.start()
        log.info("saying hello to other ELMERs on udp/%d", self.port)
        return self

    def close(self):
        self.stop.set()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    def as_dict(self):
        peers = self.current()
        return {"running": bool(self.listener and self.listener.is_alive()),
                "port": self.port, "sent": self.sent, "heard": self.heard,
                "peers": peers, "count": len(peers), "error": self.error}


_net = None
_lock = threading.Lock()


def neighbourhood():
    with _lock:
        return _net


def start(describe, port=DEFAULT_PORT):
    global _net
    with _lock:
        if _net is not None:
            _net.close()
        _net = Neighbourhood(port, describe).start()
        return _net


def stop_listening():
    global _net
    with _lock:
        if _net is not None:
            _net.close()
        _net = None


def peers():
    live = neighbourhood()
    return live.current() if live else []


def borrowed_fix():
    """A position announced by another ELMER, shaped like any other fix."""
    live = neighbourhood()
    peer = live.with_fix() if live else None
    if not peer:
        return None
    gps = peer["gps"]
    return {"lat": gps["lat"], "lon": gps["lon"], "alt_m": None,
            "mode": gps.get("mode") or 2, "source": "elmer-peer",
            "read_at": time.time() - float(gps.get("age_s") or 0.0),
            "from": f"ELMER on {peer['name']}"}
