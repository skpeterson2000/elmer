"""The GPS already in the operator's pocket.

Every additional thing a station needs is a thing that can be left on the
bench. A receiver on a USB lead is one more item on a list nobody reads before
they leave, and the day it is forgotten is exactly the day the position
mattered - whereas the phone is already in the vehicle, already has a fix, and
was never going to be left behind.

So ELMER listens for one. A phone running any of the ordinary NMEA-forwarding
apps points a stream at this Pi and the position arrives, no receiver, no
antenna, no pairing.

**Not Bluetooth Low Energy**, which is the obvious guess and the one route that
does not work. The Bluetooth SIG defines a Location and Navigation Service, but
phones implement it as a client - to read a bike computer - and neither Android
nor iOS will serve its own fix over GATT. Getting at it that way means writing
and installing a phone application, which is precisely the "one more thing to
remember" this exists to avoid. Plain UDP over the wifi the phone is already on
needs nothing but an app the operator already has, or can install once.

The stream is NMEA 0183, the same sentences a receiver on a serial line emits,
so anything that speaks GPS speaks this. Only RMC and GGA are read: between
them they carry position, fix quality, altitude and whether the fix is valid at
all, and the rest of the sentence zoo says nothing ELMER asks about.

A hardware receiver still wins where there is one. This fills in when there is
not, which is the case it was built for.
"""
import logging
import socket
import threading
import time

log = logging.getLogger("elmer")

DEFAULT_PORT = 29998
STALE_AFTER = 30.0        # a phone that has stopped sending is not a position
BIND = "0.0.0.0"

_listener = None
_lock = threading.Lock()


def _checksum_ok(sentence):
    """NMEA carries an XOR checksum after a '*'. Honour it.

    A truncated datagram is not rare on a phone that has just changed cell, and
    half a sentence parses into a plausible-looking wrong position far more
    readily than it fails outright.
    """
    if "*" not in sentence:
        return False
    body, _, given = sentence.partition("*")
    body = body.lstrip("$")
    try:
        want = int(given[:2], 16)
    except ValueError:
        return False
    got = 0
    for ch in body:
        got ^= ord(ch)
    return got == want


def _degrees(value, hemisphere):
    """NMEA writes ddmm.mmmm, which is neither degrees nor minutes."""
    if not value or not hemisphere:
        return None
    try:
        raw = float(value)
    except ValueError:
        return None
    degrees = int(raw / 100)
    minutes = raw - degrees * 100
    out = degrees + minutes / 60.0
    if hemisphere.upper() in ("S", "W"):
        out = -out
    return out


def parse(sentence):
    """One NMEA sentence to a partial fix, or None.

    Returns only what the sentence actually carries, so a caller can merge GGA's
    altitude onto RMC's position rather than choosing between them.
    """
    sentence = sentence.strip()
    if not sentence.startswith("$") or not _checksum_ok(sentence):
        return None
    parts = sentence.split("*")[0].split(",")
    kind = parts[0][3:]          # GP, GN, GL... then RMC/GGA

    if kind == "RMC" and len(parts) >= 7:
        # Field 2 is A for a valid fix and V for a warning - V means the
        # receiver is reporting where it last thought it was, which is not the
        # same as knowing.
        if parts[2] != "A":
            return None
        lat = _degrees(parts[3], parts[4])
        lon = _degrees(parts[5], parts[6])
        if lat is None or lon is None:
            return None
        out = {"lat": lat, "lon": lon, "mode": 2}
        try:
            if parts[7]:
                out["speed_mps"] = float(parts[7]) * 0.514444   # knots
        except (IndexError, ValueError):
            pass
        return out

    if kind == "GGA" and len(parts) >= 10:
        try:
            quality = int(parts[6] or 0)
        except ValueError:
            quality = 0
        if quality == 0:
            return None          # no fix
        lat = _degrees(parts[2], parts[3])
        lon = _degrees(parts[4], parts[5])
        if lat is None or lon is None:
            return None
        out = {"lat": lat, "lon": lon, "mode": 3}
        try:
            out["alt_m"] = float(parts[9]) if parts[9] else None
        except ValueError:
            out["alt_m"] = None
        try:
            out["sats"] = int(parts[7]) if parts[7] else None
        except ValueError:
            pass
        return out

    return None


class Listener:
    """A UDP socket that turns a phone's NMEA into a position."""

    def __init__(self, port=DEFAULT_PORT, bind=BIND):
        self.port = int(port)
        self.bind = bind
        self.sock = None
        self.thread = None
        self.stop = threading.Event()
        self.fix = None
        self.sentences = 0
        self.rejected = 0
        self.last_from = None
        self.error = None

    def _absorb(self, data, sender):
        # A datagram may hold several sentences; a phone that batches them is
        # being kind to the radio, not misbehaving.
        for line in data.decode("ascii", "ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            got = parse(line)
            if got is None:
                self.rejected += 1
                continue
            self.sentences += 1
            merged = dict(self.fix or {})
            merged.update(got)
            # GGA carries altitude and satellite count, RMC carries speed;
            # keep whichever arrived most recently for each and stamp the lot.
            merged["read_at"] = time.time()
            merged["from"] = f"{sender[0]} (phone)"
            merged["source"] = "phone"
            self.fix = merged
            self.last_from = sender[0]

    def run(self):
        while not self.stop.is_set():
            try:
                data, sender = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                self._absorb(data, sender)
            except Exception as exc:              # pragma: no cover
                self.error = repr(exc)
                log.debug("phone gps: %s", exc)

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(1.0)
        self.sock.bind((self.bind, self.port))
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="phone-gps")
        self.thread.start()
        log.info("phone GPS: listening for NMEA on udp/%d", self.port)
        return self

    def close(self):
        self.stop.set()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    def current(self):
        """The last fix, if it is recent enough to still mean anything."""
        got = self.fix
        if not got:
            return None
        if time.time() - got["read_at"] > STALE_AFTER:
            return None
        return got

    def as_dict(self):
        got = self.current()
        return {"listening": bool(self.thread and self.thread.is_alive()),
                "port": self.port, "sentences": self.sentences,
                "rejected": self.rejected, "from": self.last_from,
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
    """The phone's fix, if one is arriving."""
    live = listener()
    return live.current() if live else None
