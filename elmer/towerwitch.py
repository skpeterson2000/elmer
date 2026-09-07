"""The station's GPS, taken off the network where TowerWitch puts it.

One receiver on one Pi, and every device in the vehicle knowing where it is.
That is the arrangement TowerWitch already provides: it broadcasts its position
over UDP, so anything on the network can have the same 3D fix without a second
antenna, a second receiver, or a fight over who owns the serial port.

ELMER listens for it. Nothing is asked of TowerWitch and nothing is configured
between them - a broadcast is heard or it is not.

This is deliberately a different thing from reading TowerWitch's state file,
which is its last known position and carries the age of a file write. This is
the live fix, arriving every few seconds with its own timestamp, and it is
treated as one.

The packet is TowerWitch's own, unchanged:

    {"timestamp": "...", "source": "TowerWitch",
     "gps_lat": 46.5983, "gps_lon": -94.3154,
     "speed_mps": 0.05, "is_vehicle_speed": false,
     "closest_armer_towers": [...]}

Only the position is taken. What else rides along is TowerWitch's business.

A word on trust, kept in the same terms as everything else here: anything on
the network can send a packet to this port, so this is a station on a network
the operator controls taking a position from another station on it. It is not
authenticated and does not pretend to be. A receiver wired to this machine
still wins wherever there is one.
"""
import json
import logging
import socket
import threading
import time

log = logging.getLogger("elmer")

DEFAULT_PORT = 12345      # TowerWitch's own default, in its UDP_CONFIG
BIND = ""                 # every interface, because a broadcast arrives on one
# TowerWitch sends every 25 seconds by default. Three missed sends and it has
# stopped talking, which is not the same as the station having stopped moving.
STALE_AFTER = 90.0

_listener = None
_lock = threading.Lock()


def parse(payload):
    """One TowerWitch broadcast as a fix, or None.

    Refuses anything that is not TowerWitch's, and anything carrying no
    position - it broadcasts tower data whether or not it has a lock, so a
    packet is not by itself evidence of one.
    """
    try:
        data = json.loads(payload.decode("utf-8", "ignore"))
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, dict) or data.get("source") != "TowerWitch":
        return None
    try:
        lat = data.get("gps_lat")
        lon = data.get("gps_lon")
        if lat is None or lon is None:
            return None
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    out = {"lat": lat, "lon": lon, "mode": 3, "alt_m": None,
           "source": "towerwitch-net", "read_at": time.time(),
           "sent": data.get("timestamp")}
    try:
        if data.get("speed_mps") is not None:
            out["speed_mps"] = float(data["speed_mps"])
    except (TypeError, ValueError):
        pass
    out["moving"] = bool(data.get("is_vehicle_speed"))
    return out


class Listener:
    """A UDP socket that hears TowerWitch announce where the station is."""

    def __init__(self, port=DEFAULT_PORT):
        self.port = int(port)
        self.sock = None
        self.thread = None
        self.stop = threading.Event()
        self.fix = None
        self.heard = 0
        self.ignored = 0
        self.last_from = None
        self.error = None

    def run(self):
        while not self.stop.is_set():
            try:
                data, sender = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            got = parse(data)
            if got is None:
                self.ignored += 1
                continue
            got["from"] = f"TowerWitch at {sender[0]}"
            self.fix = got
            self.heard += 1
            self.last_from = sender[0]
            if self.heard == 1:
                log.info("TowerWitch on the network: position from %s",
                         sender[0])

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError:
            pass
        self.sock.settimeout(1.0)
        self.sock.bind((BIND, self.port))
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="towerwitch-net")
        self.thread.start()
        log.info("listening for TowerWitch on udp/%d", self.port)
        return self

    def close(self):
        self.stop.set()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    def current(self):
        got = self.fix
        if not got or time.time() - got["read_at"] > STALE_AFTER:
            return None
        return got

    def as_dict(self):
        got = self.current()
        return {"listening": bool(self.thread and self.thread.is_alive()),
                "port": self.port, "heard": self.heard,
                "ignored": self.ignored, "from": self.last_from,
                "has_fix": bool(got), "error": self.error,
                "age_s": round(time.time() - got["read_at"], 1) if got else None}


def listener():
    with _lock:
        return _listener


def start(port=DEFAULT_PORT):
    global _listener
    with _lock:
        if _listener is not None:
            _listener.close()
        _listener = Listener(port).start()
        return _listener


def stop_listening():
    global _listener
    with _lock:
        if _listener is not None:
            _listener.close()
        _listener = None


def current():
    """The position TowerWitch last announced, if it is still current."""
    live = listener()
    return live.current() if live else None
