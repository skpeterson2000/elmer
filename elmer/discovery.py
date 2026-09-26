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

The roster is deliberately not the interface. A hall with nine units in it
would give the operator nine names, nine addresses and nine versions to read,
and none of that answers the only question in front of them, which is what
this unit should do about the others: run on its own, run a net, or take a
table under somebody else's net. So the roster stays here for the code to work
from, and what goes to the screen is a summary - how many, is anyone playing,
and which nets there are to report to.

The nets are named, because a network is expected to hold more than one of
them: Technician in this corner, General in that one, Extra in the next room.
A unit choosing between them is choosing on the material, so that is what a
net announces about itself, and a unit that is only a table passes on the
address of the net it reports to - which is how a late arrival finds a master
it cannot hear directly. Each net also carries a token, which is what it *is*
as against what it is called: names change under the tables in them, and
addresses change across a reboot, and the token is how a table tells a
renamed net from a new one and finds the one it was in at wherever it is now.

What is announced is what a neighbour needs to be useful - who this is, where
to reach it, whether it has a position, whether a game is on, and whether it is
running or reporting to a net. Not the operator's name, not their progress, not
their callsign. It goes to the local broadcast address and nowhere else, and
position sharing can be switched off without switching off discovery.
"""
import concurrent.futures
import ipaddress
import json
import logging
import socket
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlsplit

log = logging.getLogger("elmer")

# Adjacent to TowerWitch's 12345, so a network that lets one through tends to
# let the other, and the pair are easy to remember together.
DEFAULT_PORT = 12346
ANNOUNCE_EVERY = 8.0
# Three missed announcements and a unit has gone: shut down, moved, or off the
# air. Long enough that a busy Pi missing one does not vanish from the list.
GONE_AFTER = 30.0
MAGIC = "elmer-unit"
LIMITED = "255.255.255.255"
# How long a list of where to announce is trusted before the interfaces are
# asked again. They change when a cable goes in or the wifi comes back, which
# is minutes apart at the least; asking every announcement would be a
# subprocess every eight seconds for nothing.
TARGETS_FOR = 60.0


def interfaces_from(ip_output):
    """Every IPv4 interface that is up, from `ip -4 -br addr`, loopback left out."""
    out = []
    for row in str(ip_output or "").splitlines():
        parts = row.split()
        if len(parts) < 3 or parts[1] != "UP":
            continue
        for cidr in parts[2:]:
            try:
                iface = ipaddress.IPv4Interface(cidr)
            except ValueError:
                continue
            if not iface.ip.is_loopback:
                out.append(iface)
    return out


def _ip_addr():
    try:
        return subprocess.run(["ip", "-4", "-br", "addr"], capture_output=True,
                              text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def targets_from(ip_output):
    """The subnet broadcast of every interface that is up, from `ip -4 -br addr`.

    The limited broadcast, 255.255.255.255, leaves by one interface only -
    whichever holds the default route this minute. A Pi with Ethernet and
    wifi both up, or a tether beside the wifi, announces itself down the
    wrong one and is never heard, while it hears everybody: found on the
    bench, where one unit's counter climbed by one every eight seconds and
    the unit beside it received nothing in forty. The directed broadcast of
    each interface goes to that interface's own segment regardless of where
    the default route points, so every segment this unit is on hears it.
    """
    out = []
    for iface in interfaces_from(ip_output):
        if iface.network.prefixlen >= 31:
            continue
        addr = str(iface.network.broadcast_address)
        if addr not in out:
            out.append(addr)
    out.append(LIMITED)
    return out


def broadcast_targets():
    """Where an announcement goes on this machine, the limited broadcast last.

    Without `ip` - Windows, a stripped container - the limited broadcast is
    the whole list, which is what every unit did before.
    """
    return targets_from(_ip_addr())


# ------------------------------------------------------------------ the sweep
# Hearing is passive and can fail quietly - an access point that will not
# carry broadcast, a unit announcing down its other interface - and a person
# who missed the one moment the offer was on the screen has, in kiosk mode,
# no terminal to go looking from. So there is a button that looks: every
# address on this unit's own subnets is asked, on ELMER's port, whether an
# ELMER is there and what it is doing. One port, one small request per
# answering host, a few seconds in all, and only when somebody presses.

SWEEP_PORT = 5000
SWEEP_CONNECT = 0.35          # seconds to wait on one address
SWEEP_WORKERS = 64
SWEEP_LARGEST = 24            # a /16 is 65,000 addresses; the /24 around us will do
SWEEP_KEEP = 90.0             # how long what a sweep found stays in the roster

_found = {}                   # url -> (net record, when found)
_found_lock = threading.Lock()


def hosts_to_sweep(interfaces, largest=SWEEP_LARGEST):
    """The addresses worth asking: each up interface's subnet, no bigger than
    a /24 around the unit's own address, the unit's own addresses left out."""
    mine = {iface.ip for iface in interfaces}
    seen, out = set(), []
    for iface in interfaces:
        net = iface.network
        if net.prefixlen < largest:
            net = ipaddress.IPv4Network(f"{iface.ip}/{largest}", strict=False)
        for host in net.hosts():
            addr = str(host)
            if host in mine or addr in seen:
                continue
            seen.add(addr)
            out.append(addr)
    return out


def _net_record(url, me):
    """What a unit's /api/peers `me` says about the net it is in, as a roster
    entry - the same shape nets() builds from an announcement."""
    if me.get("hosting"):
        return {"url": url, "name": str(me.get("name") or "a net")[:60],
                "token": str(me.get("token") or "")[:24],
                "difficulty": str(me.get("difficulty") or "")[:20],
                "units": int(me.get("units") or 0),
                "round": int(me.get("round") or 0),
                "mode": str(me.get("mode") or "")[:16]}
    if me.get("table_of"):
        # A table points at its host; the host is asked directly below.
        return {"url": str(me["table_of"])[:120],
                "name": str(me.get("table_in") or "a net")[:60],
                "token": str(me.get("table_token") or "")[:24],
                "difficulty": "", "units": 0, "round": 0, "mode": "",
                "via": url}
    return None


def _ask(url, path="/api/peers", timeout=3.0):
    request = urllib.request.Request(url.rstrip("/") + path,
                                     headers={"User-Agent": "ELMER/1.0 (sweep)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _open(addr, port, timeout):
    try:
        with socket.create_connection((addr, port), timeout=timeout):
            return True
    except OSError:
        return False


def sweep(port=SWEEP_PORT, extra_urls=(), interfaces=None):
    """Look for nets on this unit's own subnets, and at the addresses given.

    Returns {"nets": [...], "asked": n, "answered": n, "seconds": s}. Every
    net found is remembered for SWEEP_KEEP seconds so that the roster, the
    offer on the table screen and auto-join all see it as if it had been
    heard - which is the point: the person pressed the button because the
    hearing did not happen.
    """
    started = time.monotonic()
    interfaces = interfaces_from(_ip_addr()) if interfaces is None else interfaces
    mine = {str(i.ip) for i in interfaces}
    hosts = hosts_to_sweep(interfaces)
    with concurrent.futures.ThreadPoolExecutor(SWEEP_WORKERS) as pool:
        open_hosts = [h for h, ok in zip(hosts, pool.map(
            lambda a: _open(a, port, SWEEP_CONNECT), hosts)) if ok]
    urls = [f"http://{h}:{port}" for h in open_hosts]
    for url in extra_urls:
        url = str(url or "").rstrip("/")
        if url and url not in urls and urlsplit(url).hostname not in mine:
            urls.append(url)
    found, answered = {}, 0
    with concurrent.futures.ThreadPoolExecutor(min(SWEEP_WORKERS, max(1, len(urls)))) as pool:
        def look(url):
            try:
                return url, _ask(url)
            except Exception:
                return url, None
        for url, reply in pool.map(look, urls):
            if not isinstance(reply, dict):
                continue
            answered += 1
            record = _net_record(url, reply.get("me") or {})
            if record and record["url"] not in found:
                found[record["url"]] = record
    # A host known only through one of its tables is asked itself, so the
    # entry carries the net's name, token and size rather than a table's
    # second-hand word - and drops out if the table's host is gone.
    for url, record in list(found.items()):
        if "via" not in record:
            continue
        try:
            board = _ask(url, "/api/net/board", timeout=3.0)
        except Exception:
            found.pop(url, None)
            continue
        found[url] = {"url": url, "name": str(board.get("name") or record["name"])[:60],
                      "token": str(board.get("token") or record["token"])[:24],
                      "difficulty": str(board.get("difficulty") or "")[:20],
                      "units": int(board.get("units_present") or 0),
                      "round": int((board.get("round") or {}).get("number") or 0),
                      "mode": str((board.get("show") or {}).get("mode") or "")[:16]}
    now = time.time()
    with _found_lock:
        for url, record in found.items():
            _found[url] = (record, now)
    nets = sorted(found.values(), key=lambda n: (-n["units"], n["name"]))
    log.info("sweep: %d addresses asked, %d ELMERs answered, %d net(s) found in %.1fs",
             len(hosts), answered, len(nets), time.monotonic() - started)
    return {"nets": nets, "asked": len(hosts), "answered": answered,
            "seconds": round(time.monotonic() - started, 1)}


def found_nets(now=None):
    """What the last sweep found and is still fresh, fullest first."""
    now = time.time() if now is None else now
    with _found_lock:
        stale = [u for u, (_, at) in _found.items() if now - at > SWEEP_KEEP]
        for u in stale:
            _found.pop(u, None)
        rows = [dict(r) for r, _ in _found.values()]
    return sorted(rows, key=lambda n: (-n["units"], n["name"]))


def merge_nets(heard, found):
    """Heard first, then what a sweep found that was not heard - by token
    where there is one, by address where there is not."""
    out = list(heard)
    have_tokens = {n.get("token") for n in out if n.get("token")}
    have_urls = {n["url"].rstrip("/") for n in out}
    for net in found:
        if (net.get("token") and net["token"] in have_tokens) or net["url"].rstrip("/") in have_urls:
            continue
        out.append(net)
    return sorted(out, key=lambda n: (-n.get("units", 0), n["name"]))


def _payload(unit, name, url, version, fix, party, share_position=True,
             net=None):
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
    # Which of the three parts this unit is already playing: running the net
    # for the hall, reporting to somebody else's, or neither. A neighbour that
    # is about to be offered a role needs to know which roles are left.
    out["net"] = net or {}
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
            "party": got.get("party") or {},
            "net": got.get("net") if isinstance(got.get("net"), dict) else {}}
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
        self._targets = []
        self._targets_at = 0.0

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
            # Outside the lock. describe() is the application's callback and
            # it reaches back in here: it reports this unit's position, and a
            # unit with no receiver of its own borrows one from the roster -
            # current(), which takes this same lock. Called from inside the
            # lock that is a self-deadlock, and a plain Lock cannot survive it.
            # The listener stops, the announcer piles up behind it, and every
            # page load blocks for ever. It only bit when the fix cache was
            # cold and another ELMER was broadcasting, so it showed up as an
            # occasional hang on startup rather than as anything reproducible.
            mine = self.describe() if self.describe else {}
            with self.lock:
                if peer["unit"] == (mine.get("unit") or ""):
                    continue              # this unit hearing its own broadcast
                first = peer["unit"] not in self.peers
                self.peers[peer["unit"]] = peer
                self.heard += 1
            if first:
                log.info("another ELMER on the network: %s at %s",
                         peer["name"], peer["address"])

    # ----------------------------------------------------------- announcing

    def targets(self, now=None):
        now = time.monotonic() if now is None else now
        if not self._targets or now - self._targets_at > TARGETS_FOR:
            self._targets = broadcast_targets()
            self._targets_at = now
        return list(self._targets)

    def _announce_once(self):
        if not self.describe:
            return
        mine = self.describe()
        net = mine.get("net") or {}
        data = _payload(mine.get("unit", ""), mine.get("name", ""),
                        mine.get("url", ""), mine.get("version", ""),
                        mine.get("fix"), mine.get("party"),
                        mine.get("share_position", True), net)
        where = self.targets()
        # A table already knows one address for certain: the net it reports
        # to. A copy goes there by name as well, so a network that will not
        # carry broadcast between its clients - some access points are set
        # up that way - still lets a table and its host find each other.
        host = urlsplit(str(net.get("table_of") or "")).hostname
        if host and host not in where and not host.startswith("127."):
            where.append(host)
        failed = None
        for target in where:
            try:
                self.sock.sendto(data, (target, self.port))
            except OSError as exc:
                failed = exc                     # one bad target is not all of them
        if failed is not None and len(where) == 1:
            raise failed
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

    def nets(self):
        """The tournaments running out there, told apart by their material.

        One network is expected to hold several: Technician in one corner,
        General in another, Extra in the next room. So this is a list, keyed
        by the address of the unit running each one, and what is shown of a
        net is what it is studying - which is what somebody choosing between
        them is actually choosing on.
        """
        live = self.current()
        found = {}
        for peer in live:
            net = peer.get("net") or {}
            if net.get("hosting") and peer.get("url"):
                found[peer["url"]] = {
                    "url": peer["url"],
                    "name": str(net.get("name") or "a net")[:60],
                    # The net's identity, apart from its name: the name is
                    # what it is called tonight and can change under a table
                    # that is in it; the token cannot.
                    "token": str(net.get("token") or "")[:24],
                    "difficulty": str(net.get("difficulty") or "")[:20],
                    "units": int(net.get("units") or 0),
                    # Waiting, in a round, or in intermission - so a person
                    # choosing can tell a game to join from one to watch.
                    "round": int(net.get("round") or 0),
                    "mode": str(net.get("mode") or "")[:16]}
        hosted = {n["token"] for n in found.values() if n["token"]}
        for peer in live:
            net = peer.get("net") or {}
            url = net.get("table_of")
            token = str(net.get("table_token") or "")[:24]
            # A table may report to a net this unit cannot hear itself - a
            # master on another subnet, or one wired in. It is still joinable,
            # and the table knows what it is called. A table still pointing
            # at the old address of a net heard directly on a new one is not
            # a second net, and is left out.
            if url and url not in found and token not in hosted:
                found[url] = {"url": str(url)[:120],
                              "name": str(net.get("table_in") or "a net")[:60],
                              "token": token, "difficulty": "", "units": 0,
                              "round": 0, "mode": ""}
        heard = sorted(found.values(), key=lambda n: (-n["units"], n["name"]))
        # And what the last sweep found: a net that could not be heard is
        # still a net, and the button was pressed because it could not be.
        return merge_nets(heard, found_nets())

    def net_by_token(self, token):
        """Where the net with this token is now, or None if it is not heard."""
        if not token:
            return None
        for net in self.nets():
            if net.get("token") == token:
                return net
        return None

    def games(self):
        """Every tournament out there worth putting on a board.

        A net is one game however many tables are in it, so a unit that is
        somebody's table is not listed again on its own account - its players
        are already in the hall's standings. A unit playing by itself is a
        game, and belongs on the board as much as a hall does: "a game on
        another Pi" is exactly what the screen at the front of the room was
        missing.
        """
        out = [dict(net, kind="hall", path="/api/net/board")
               for net in self.nets()]
        seen = {net["url"] for net in out}
        for peer in self.current():
            net = peer.get("net") or {}
            if net.get("hosting") or net.get("table_of"):
                continue
            if (peer.get("party") or {}).get("running") and peer.get("url"):
                if peer["url"] in seen:
                    continue
                out.append({"url": peer["url"], "name": peer["name"],
                            "difficulty": "", "units": 0,
                            "kind": "table", "path": "/api/board"})
                seen.add(peer["url"])
        return out

    def golf_rounds(self):
        """Every round of golf on another unit here that a person could join,
        for this unit's table screen to offer.

        A golfer at one unit and a golfer at another are in the same round by
        the second unit's screen becoming a screen onto the first's table -
        one round, played on one unit, so there is only ever one account of
        where a ball is. What is offered is what somebody deciding needs: the
        unit, the course, where the group is, and whether there is room. A
        unit that is a table in somebody's net is playing the net's game, not
        its own, and is not offered."""
        out = []
        for peer in self.current():
            golf = (peer.get("party") or {}).get("golf")
            net = peer.get("net") or {}
            if not isinstance(golf, dict) or not peer.get("url") or net.get("table_of"):
                continue
            out.append({"unit": peer["unit"], "name": peer["name"], "url": peer["url"],
                        "course": str(golf.get("course") or "")[:60],
                        "clubhouse": bool(golf.get("clubhouse")), "tee_in": golf.get("tee_in"),
                        "hole": golf.get("hole"), "holes": golf.get("holes"),
                        "people": int(golf.get("people") or 0), "full": bool(golf.get("full")),
                        "version": peer.get("version") or ""})
        out.sort(key=lambda g: (g["full"], g["name"]))
        return out

    def summary(self):
        """What the screen needs: how many, and what can be joined.

        Names and addresses of units stay out of it on purpose. The panel this
        feeds asks the operator to pick a part for this unit, and a list of
        which Pis are switched on does not help them pick it. The tournaments
        are named, because choosing between them is the one choice here that
        needs a name attached.
        """
        live = self.current()
        return {"count": len(live),
                "with_fix": any(p.get("gps") for p in live),
                "playing": any((p.get("party") or {}).get("running")
                               for p in live),
                "nets": self.nets()}

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
                "peers": peers, "count": len(peers), "error": self.error,
                "summary": self.summary()}


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


def games():
    """Every tournament this unit can hear, for the big board."""
    live = neighbourhood()
    return live.games() if live else []


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
