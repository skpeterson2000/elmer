"""What this station's own receiver is hearing, from WSJT-X or JTDX.

WSJT-X sends every decode out over UDP to whatever is listening - the same
messages GridTracker and JTAlert read. A decode that carries a grid square
(a CQ, or the first call of a contact) says who was heard, from where, on
which band, and how strong. Put on the reach map, that is the forecast and
the evidence on one page: what the model said would arrive, and what the
antenna in the yard actually heard.

Nothing leaves the unit. This only listens - by default on 127.0.0.1, so a
WSJT-X on the same machine reaches it and nothing on the network does. A
WSJT-X on another computer needs the listener opened to the network, and
two programs cannot share one ordinary UDP port; WSJT-X's own answer is a
multicast group, which ELMER can join alongside GridTracker and the rest.

The protocol is WSJT-X's NetworkMessage.hpp: a Qt QDataStream, big-endian,
every message opening with the magic 0xadbccbda, a schema number, a type
and the sending program's id. Status (1) carries the dial frequency, so the
band; Decode (2) the message text and SNR; WSPRDecode (10) a grid outright.
Nothing here trusts a packet: every field is bounds-checked, and a bad one
is dropped and counted, never allowed to stop the listener.
"""
import ipaddress
import json
import logging
import re
import socket
import struct
import threading
import time
from datetime import datetime, timezone

from . import bandplan, geocode, paths

log = logging.getLogger("elmer")

MAGIC = 0xADBCCBDA
STATUS, DECODE, CLEAR, CLOSE, WSPR = 1, 2, 3, 6, 10
CONFIG = paths.STATE / "wsjtx.json"
DEFAULTS = {"enabled": True, "host": "127.0.0.1", "port": 2237, "multicast": ""}
HEARD_MINUTES = 30            # how long a station heard stays on the map
MAX_HEARD = 2000              # more than any band holds in half an hour
MAX_PACKET = 8192             # WSJT-X's messages are a few hundred bytes
RETRY_SECONDS = 60            # a port that is busy is tried again this often

GRID = re.compile(r"^[A-R]{2}[0-9]{2}$")
CALL = re.compile(r"^(?=.*[0-9])(?=.*[A-Z])[A-Z0-9/]{3,12}$")
NOT_GRIDS = {"RR73"}          # a valid-looking square that is a sign-off


class Malformed(ValueError):
    """A packet that does not read as WSJT-X's protocol."""


class _Reader:
    """QDataStream, as much of it as WSJT-X uses."""

    def __init__(self, data):
        self.data, self.at = data, 0

    def _take(self, n):
        if self.at + n > len(self.data):
            raise Malformed("ran out at byte %d" % self.at)
        piece = self.data[self.at:self.at + n]
        self.at += n
        return piece

    def u8(self):
        return self._take(1)[0]

    def boolean(self):
        return self.u8() != 0

    def u32(self):
        return struct.unpack(">I", self._take(4))[0]

    def i32(self):
        return struct.unpack(">i", self._take(4))[0]

    def u64(self):
        return struct.unpack(">Q", self._take(8))[0]

    def f64(self):
        return struct.unpack(">d", self._take(8))[0]

    def utf8(self):
        n = self.u32()
        if n == 0xFFFFFFFF:
            return ""
        if n > MAX_PACKET:
            raise Malformed("a string %d bytes long" % n)
        return self._take(n).decode("utf-8", "replace")


def parse(data):
    """One datagram -> a dict with its type and the fields ELMER uses, or
    None for a message type it does not read. Raises Malformed."""
    if len(data) > MAX_PACKET:
        raise Malformed("a %d byte packet" % len(data))
    r = _Reader(data)
    if r.u32() != MAGIC:
        raise Malformed("not WSJT-X's magic number")
    r.u32()                                       # schema; every one ELMER reads lays these out alike
    kind = r.u32()
    source = r.utf8()
    if kind == STATUS:
        dial = r.u64()
        mode = r.utf8()
        out = {"type": STATUS, "id": source, "dial_hz": dial, "mode": mode}
        try:                                       # the rest is newer, and optional here
            r.utf8(), r.utf8(), r.utf8()           # DX call, report, Tx mode
            r.boolean(), r.boolean(), r.boolean()  # Tx enabled, transmitting, decoding
            r.u32(), r.u32()                       # Rx DF, Tx DF
            out["de_call"], out["de_grid"] = r.utf8(), r.utf8()
        except Malformed:
            pass                                   # an older WSJT-X: the band is what matters
        return out
    if kind == DECODE:
        new = r.boolean()
        r.u32()                                    # QTime: ms since midnight
        snr = r.i32()
        r.f64()                                    # delta time
        df = r.u32()
        mode = r.utf8()
        message = r.utf8()
        r.boolean()                                # low confidence
        off_air = r.boolean()
        return {"type": DECODE, "id": source, "new": new, "snr": snr, "df": df, "mode": mode,
                "message": message, "off_air": off_air}
    if kind == WSPR:
        new = r.boolean()
        r.u32()
        snr = r.i32()
        r.f64()
        freq = r.u64()
        r.i32()                                    # drift
        call = r.utf8()
        grid = r.utf8()
        r.i32()                                    # power
        off_air = r.boolean()
        return {"type": WSPR, "id": source, "new": new, "snr": snr, "hz": freq, "call": call,
                "grid": grid, "off_air": off_air}
    if kind in (CLEAR, CLOSE):
        return {"type": kind, "id": source}
    return None


def sender_and_grid(message):
    """Who sent a decoded message, and from which grid square, when the
    message says - "CQ K1ABC FN42", "CQ POTA K1ABC FN42", "W1AW K1ABC FN42".
    (None, None) for the rest: reports, RR73, 73, free text."""
    words = (message or "").upper().split()
    if len(words) < 2 or not GRID.match(words[-1]) or words[-1] in NOT_GRIDS:
        return None, None
    at = -3 if len(words) >= 3 and words[-2] == "R" else -2
    if len(words) < -at:
        return None, None
    call = words[at].strip("<>")
    if call in ("CQ", "QRZ", "DE") or not CALL.match(call):
        return None, None
    return call, words[-1]


class Heard:
    """The stations decoded lately, one entry per callsign and band, and
    what WSJT-X last said about itself."""

    def __init__(self):
        self.lock = threading.Lock()
        self.stations = {}
        self.dial = {}                             # per WSJT-X instance: dial Hz, mode
        self.station = {}

    def take(self, msg, now=None):
        now = now or time.time()
        kind = msg["type"]
        if kind == STATUS:
            with self.lock:
                self.dial[msg["id"]] = {"hz": msg["dial_hz"], "mode": msg["mode"]}
                if msg.get("de_call"):
                    self.station = {"call": msg["de_call"], "grid": msg.get("de_grid") or ""}
            return None
        if kind == CLOSE:
            with self.lock:
                self.dial.pop(msg["id"], None)
            return None
        if kind not in (DECODE, WSPR) or msg.get("off_air"):
            return None                            # a file replayed is not the air now
        if kind == WSPR:
            call, grid, hz, mode = msg["call"].strip("<>").upper(), msg["grid"].upper()[:4], msg["hz"], "WSPR"
            if not CALL.match(call) or not GRID.match(grid):
                return None
        else:
            call, grid = sender_and_grid(msg["message"])
            if not call:
                return None
            with self.lock:
                dial = self.dial.get(msg["id"])
            hz = dial["hz"] + msg["df"] if dial else None
            mode = msg["mode"] if msg["mode"] not in ("~", "+", "$", "#", "@", "&", ":", "`") else \
                (dial or {}).get("mode", "")
        where = geocode.from_grid(grid)
        if not where:
            return None
        mhz = hz / 1e6 if hz else None
        band = bandplan.band_at(mhz) if mhz else None
        entry = {"call": call, "grid": grid, "lat": where[0], "lon": where[1], "snr": msg["snr"],
                 "mhz": round(mhz, 4) if mhz else None, "band": band["name"] if band else None,
                 "mode": mode, "at": now}
        with self.lock:
            self.stations[(call, entry["band"])] = entry
            if len(self.stations) > MAX_HEARD:
                for key, _ in sorted(self.stations.items(), key=lambda kv: kv[1]["at"])[:len(self.stations) - MAX_HEARD]:
                    del self.stations[key]
        return entry

    def recent(self, minutes=HEARD_MINUTES, now=None):
        cutoff = (now or time.time()) - minutes * 60
        with self.lock:
            for key in [k for k, v in self.stations.items() if v["at"] < cutoff]:
                del self.stations[key]
            return sorted(self.stations.values(), key=lambda v: -v["at"])


def load_config():
    """The listener's settings, with the defaults for anything missing."""
    try:
        saved = json.loads(CONFIG.read_text(encoding="utf-8"))
    except FileNotFoundError:
        saved = {}
    except (OSError, ValueError) as exc:
        log.warning("WSJT-X listener settings at %s could not be read, using the defaults: %s", CONFIG, exc)
        saved = {}
    return {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}


def check_config(host, port, multicast):
    """Settings worth binding, or the reason they are not."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return "the address to listen on has to be an IP address - 127.0.0.1 for this machine, 0.0.0.0 for any"
    try:
        port = int(port)
    except (TypeError, ValueError):
        return "the port has to be a number"
    if not 1024 <= port <= 65535:
        return "the port has to be between 1024 and 65535 - WSJT-X's own is 2237"
    if multicast:
        try:
            if not ipaddress.ip_address(multicast).is_multicast:
                return "%s is not a multicast address - WSJT-X's are in 224.0.0.0 to 239.255.255.255" % multicast
        except ValueError:
            return "the multicast group has to be an IP address, like 224.0.0.73"
    return None


class Listener:
    """The UDP listener: one thread, alive for as long as the server is,
    standing aside when it cannot bind and trying again."""

    def __init__(self, heard=None):
        self.heard = heard or Heard()
        self.config = load_config()
        self.state = {"listening": False, "error": None, "last_packet": None, "packets": 0, "dropped": 0}
        self._stop = threading.Event()
        self._restart = threading.Event()
        self._thread = None

    def where(self):
        c = self.config
        return "%s:%s" % (c["multicast"] or c["host"], c["port"])

    def start(self):
        if self._thread and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(target=self._run, name="wsjtx-listen", daemon=True)
        self._thread.start()
        return self._thread

    def stop(self):
        self._stop.set()
        self._restart.set()

    def configure(self, enabled, host, port, multicast):
        why = check_config(host, port, multicast)
        if why:
            return why
        self.config = {"enabled": bool(enabled), "host": host, "port": int(port), "multicast": multicast or ""}
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(self.config), encoding="utf-8")
        except OSError as exc:
            log.warning("WSJT-X listener settings could not be kept at %s: %s", CONFIG, exc)
        self._restart.set()
        return None

    def _bind(self):
        c = self.config
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        if c["multicast"]:
            # Sharing the port is right only for a multicast group, where every
            # member gets every packet. On an ordinary port, Windows would let
            # ELMER bind beside GridTracker and then hand each packet to one of
            # them at random - so there it is left off, and a taken port is
            # refused, which is the honest answer.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass                           # not every kernel allows it; SO_REUSEADDR still shares the group
            # A multicast listener binds the port on every interface, then joins
            # the group: bound to one address, Linux does not hand it the group's packets.
            sock.bind(("", c["port"]))
            group = socket.inet_aton(c["multicast"]) + socket.inet_aton("0.0.0.0")
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, group)
        else:
            sock.bind((c["host"], c["port"]))
        sock.settimeout(1.0)
        return sock

    def _run(self):
        warned = None
        while not self._stop.is_set():
            self._restart.clear()
            if not self.config["enabled"]:
                self.state.update(listening=False, error=None)
                self._restart.wait()
                continue
            sock = None
            try:
                sock = self._bind()
            except OSError as exc:
                why = ("port %s is already taken - another program (GridTracker, JTAlert, a second ELMER) "
                       "is listening there. Have WSJT-X send to a multicast group and set ELMER to join it, "
                       "or give ELMER a port of its own" % self.config["port"]
                       if getattr(exc, "errno", None) in (48, 98, 10048) else str(exc))
                self.state.update(listening=False, error=why)
                if warned != why:                  # once per failure, not once a minute
                    log.warning("WSJT-X listener could not open %s: %s", self.where(), exc)
                    warned = why
                self._restart.wait(RETRY_SECONDS)
                continue
            warned = None
            self.state.update(listening=True, error=None)
            log.info("WSJT-X listener on %s", self.where())
            bad_logged = False
            try:
                while not self._stop.is_set() and not self._restart.is_set():
                    try:
                        data, _ = sock.recvfrom(MAX_PACKET + 1)
                    except socket.timeout:
                        continue
                    self.state["packets"] += 1
                    self.state["last_packet"] = time.time()
                    try:
                        msg = parse(data)
                        if msg:
                            self.heard.take(msg)
                    except Malformed as exc:
                        self.state["dropped"] += 1
                        if not bad_logged:
                            log.warning("WSJT-X listener dropped a packet that is not WSJT-X's protocol (%s); "
                                        "further ones are counted, not logged", exc)
                            bad_logged = True
                    except Exception:      # noqa: BLE001 - one bad packet must not end the listener
                        self.state["dropped"] += 1
                        if not bad_logged:
                            log.exception("WSJT-X listener could not use a packet; further ones are counted")
                            bad_logged = True
            except OSError as exc:
                log.warning("WSJT-X listener on %s stopped: %s - opening it again", self.where(), exc)
                self.state.update(listening=False, error=str(exc))
                self._restart.wait(5)
            finally:
                sock.close()
        self.state["listening"] = False

    def snapshot(self):
        """For the page: whether it is listening and where, what WSJT-X
        last said about itself, and the stations heard lately."""
        last = self.state["last_packet"]
        with self.heard.lock:
            dials = list(self.heard.dial.values())
            station = dict(self.heard.station)
        return {"enabled": self.config["enabled"], "listening": self.state["listening"], "where": self.where(),
                "config": dict(self.config), "error": self.state["error"],
                "last_packet": datetime.fromtimestamp(last, timezone.utc).isoformat(timespec="seconds") if last else None,
                "quiet_s": round(time.time() - last) if last else None,
                "dropped": self.state["dropped"], "station": station,
                "dial": [{"mhz": round(d["hz"] / 1e6, 4), "mode": d["mode"]} for d in dials],
                "minutes": HEARD_MINUTES, "spots": self.heard.recent()}


_listener = None


def listener():
    """The one listener this server runs; created on first use, started by
    the server, never by an import."""
    global _listener
    if _listener is None:
        _listener = Listener()
    return _listener
