"""The bridge from a table to net control.

`party` knows how to run eight people racing a question. `netcontrol` knows how
to run a hall full of tables. Until this, nothing joined them: a table had no
way to report for duty, and net control was an interface nobody called.

This is the client half, and it runs on the cohort unit. One thread, one poll a
second, three jobs:

* say the table is here, and how many are sitting at it;
* notice when net control has put a new question up, and start it locally so
  the eight players in front of this Pi are racing it on their own screens;
* hand in the results when the round closes.

The players never speak to net control and net control never speaks to a
player. That is the whole reason a hundred tables fit on one master: it holds
one conversation per table rather than one per person, and the timing that
decides the race stays on the phone that painted the question.

A table that loses the network keeps working. The round in front of it finishes
on its own clock, the report is held and sent when the master comes back, and
net control meanwhile counts the table as quiet and carries on without it. A
hall does not stop because one Pi in the corner lost its wifi.
"""
import hashlib
import secrets
import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from . import party

log = logging.getLogger("elmer")

POLL_SECONDS = 1.0
# Between rounds - an intermission, the deck, waiting to begin - nothing on
# this table is timing anything, so the check-in eases to this. Net control
# counts a table quiet only after 25 s, and the run-up before a question is
# long enough that a table polling this slowly still catches it and speeds up
# before the round opens - so the room sees no difference and the wifi carries
# a third of the check-ins. The busy second is spent where it earns its keep:
# a round in progress.
WAITING_SECONDS = 3.0
TIMEOUT = 4.0
BACKOFF_MAX = 15.0

_bridge = None
_lock = threading.Lock()


def default_unit_name():
    """What to call this machine on a big board: its hostname, plainly."""
    try:
        return socket.gethostname().split(".")[0][:40] or "table"
    except OSError:
        return "table"


def machine_mark():
    """Four characters that are this machine and not the one beside it.

    Two Raspberry Pis out of the box are both called `raspberrypi`, and a name
    is not an identity: as ids they collide, and everything that tells units
    apart stops working at once. Discovery decides that a unit hearing its own
    id is hearing its own broadcast, so two identically named units are
    invisible to each other; net control keys tables by id, so the second table
    to check in replaces the first and a hall silently loses half its players.

    /etc/machine-id is the right thing to hash: unique per installation, stable
    across reboots and readable without privileges. Where it is missing, the
    MAC address behind uuid.getnode() is the fallback, and a random mark is the
    last resort - unstable across restarts, but unique, which is the property
    that actually matters here.
    """
    seed = ""
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            seed = Path(path).read_text().strip()
            if seed:
                break
        except OSError:
            continue
    if not seed:
        try:
            seed = f"{uuid.getnode():x}"
        except Exception:                              # pragma: no cover
            seed = uuid.uuid4().hex
    return hashlib.sha1(seed.encode()).hexdigest()[:4]


def default_unit_id():
    """A stable id for this unit, unique on the network it is on.

    The hostname leads, because an operator reading a log wants to recognise
    it; the mark decides ties. See :func:`machine_mark` for why a bare hostname
    is not enough.
    """
    return f"{default_unit_name()}-{machine_mark()}"[:40]


class Bridge:
    """One table's conversation with net control."""

    net_mode = "tournament"
    hall_shootout = None
    hall_show = None                 # the host's hand on this table's screens
    showing = ""                     # what the table screen last said it shows
    # Whether somebody at this table has pressed "check in as ready". The
    # link itself is made without anybody's hand - a table hears a net and
    # joins it, or rejoins after the 04:00 restart - so the link says the
    # machine is up and this says the people are. Not remembered across a
    # restart: it is a person's word about tonight, and a table that came
    # back from a reboot has a person to press it again.
    ready = False

    def __init__(self, url, unit_id=None, name=None, token=None):
        self.url = url.rstrip("/")
        self.unit_id = (unit_id or default_unit_id())[:40]
        # The id is for machines to tell apart; the name is for people to read
        # off a board, so it falls back to the hostname without the mark.
        self.name = (name or default_unit_name())[:60]
        self.stop = threading.Event()
        self.thread = None
        self.state = "starting"
        self.last_error = None
        self.seen_round = 0          # net round this table has already started
        self.reported_round = 0      # net round this table has handed in
        self.pending = None          # a report waiting for the network
        self.last_contact = 0.0
        # Which net this is, learned at check-in. A network can hold several -
        # Technician here, General in the next room - and a table that can only
        # say it is reporting to an address cannot tell anybody which
        # tournament it is actually in.
        self.net_name = ""
        self.net_difficulty = ""
        # Whether anything on this table is timing right now - a round open
        # here, a round up at the master, or the run-up before one. The poll
        # runs fast while this holds and eases off between rounds.
        self._active = True
        # The round trip to net control, measured on this unit's own clock:
        # the time from sending a check-in to getting the reply, which is the
        # wifi between this Pi and the master and nothing else. Kept as a
        # small window so a single hiccup does not read as a bad link. Kept
        # apart by room, because a slow poll in the waiting room is nothing
        # and a slow one mid-round is somebody's lost seconds.
        self.rtt_ms = None
        self.rtt_room = ""
        self._rtt = __import__("collections").deque(maxlen=20)
        # This unit's own load, sampled now and then and sent up so the host
        # sees a table that is choking rather than only a table that is slow -
        # the two look the same from the far end and are fixed differently.
        # Sampled every few seconds, not every poll, because the SoC's
        # throttle word costs a subprocess and the answer does not move fast.
        self._host = {}
        self._host_at = 0.0
        # A token for this running unit, made fresh each start and sent with
        # every check-in. Net control tells units apart by it, so a fleet
        # imaged from one SD card - every Pi sharing a hostname and a
        # machine-id, and therefore a unit id - still shows as many tables
        # rather than collapsing into one. See netcontrol.Net._slot_for.
        self.instance = secrets.token_hex(4)
        # And which net it is, apart from what it is called. The name is a
        # label the net can change under us - it follows the material, the
        # host can type over it - so it is shown and never keyed on. The
        # token is the identity: a different one at the same address is a
        # new net, and this table's count of the rounds it has seen belongs
        # to the old one; the same one at a different address is the net we
        # were in, come back after a reboot on a new lease, and worth
        # following there.
        self.net_token = (token or "")[:24]
        # How to find the net again by its token when the address stops
        # answering - the app supplies it from discovery; the bridge itself
        # knows nothing about the roster.
        self.locate = locator

    # ------------------------------------------------------------- transport

    def _call(self, path, body):
        request = urllib.request.Request(
            self.url + path,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "User-Agent": "ELMER/1.0 (cohort unit)"})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read())

    # ------------------------------------------------------------------ work

    def _checkin(self, room):
        # People, not seats: the count is what net control starts the hall
        # on - see hall.py - and it used to include the practice players, so
        # a table with nobody at it and four machines could open the room.
        players = room.people_here() if room else 0
        # The names at this table - display names only, the same ones a
        # board shows - so the host can say something to one seat before it
        # has answered anything.
        names = ([p.name for p in room.players.values() if not p.bot][:16]
                 if room else [])
        # The room this measurement belongs to: a round open on this table
        # is "game", anything else "waiting". The last RTT is sent up so the
        # host sees this table's link; this call is itself the measurement.
        room = "game" if (room_open := (self.showing == "question")) else "waiting"
        started = time.monotonic()
        reply = self._call("/api/net/checkin",
                           {"unit": self.unit_id, "name": self.name,
                            "players": players, "showing": self.showing,
                            "names": names, "ready": self.ready,
                            "instance": self.instance,
                            "rtt": self.rtt_ms, "room": self.rtt_room,
                            "host": self._host_load()})
        rtt = (time.monotonic() - started) * 1000.0
        self._rtt.append(rtt)
        self.rtt_ms = round(rtt, 1)
        self.rtt_room = room
        if not reply.get("checked_in", True):
            # The net is full. Say so plainly and keep trying: a table that
            # arrives late should join when somebody else's table packs up.
            self.state = "refused"
            self.last_error = reply.get("reason")
            return None
        self.state = "joined"
        self.last_error = None
        self.last_contact = time.time()
        which = reply.get("net") or {}
        token = str(which.get("token") or "")[:24]
        if token and self.net_token and token != self.net_token:
            # Not the net this table was in: the host closed it and opened
            # another, or a different unit has the address now. The rounds
            # this table has seen were the old net's; counted against the
            # new one they would keep it from ever starting round one.
            log.info("cohort: the net at %s is a new one - this table starts "
                     "afresh in it", self.url)
            self.seen_round = 0
            self.reported_round = 0
            self.pending = None
        if token and token != self.net_token:
            self.net_token = token
            self._remember_self()
        if which.get("name"):
            self.net_name = str(which["name"])[:60]
            self.net_difficulty = str(which.get("difficulty") or "")[:20]
        self.net_mode = str(which.get("mode") or "tournament")
        # The hall's shootout, as it concerns this table. Kept so the table
        # screen can show the subjects when the pick is this table's.
        self.hall_shootout = reply.get("shootout")
        # And the show: announcements addressed to this table and its seats,
        # the card between rounds, the mode. Refreshed every poll, so a
        # cleared announcement clears here within the second.
        self.hall_show = reply.get("show")
        return reply.get("round")

    def _host_load(self):
        """A small snapshot of this unit's load, refreshed every few seconds."""
        now = time.monotonic()
        if now - self._host_at < 5.0:
            return self._host
        self._host_at = now
        try:
            from . import diagnostics
            h = diagnostics.host_load()
            self._host = {"per_core": h.get("per_core"),
                          "mem_used_pct": h.get("mem_used_pct"),
                          "temp_c": h.get("temp_c"),
                          "hot": diagnostics.load_is_hot(h),
                          "undervolt": bool(h.get("undervolt_now")
                                            or h.get("undervolt_ever"))}
        except Exception:                 # a snapshot is never worth a poll
            self._host = {}
        return self._host

    def pick(self, section):
        """Relay this table's choice of subject to the hall."""
        reply = self._call("/api/net/pick", {"unit": self.unit_id,
                                             "section": section})
        if reply.get("ok"):
            self.hall_shootout = reply.get("shootout") or self.hall_shootout
        return reply

    def _start_local(self, room, rnd):
        """Put net control's question on this table's screens."""
        room.start_round(
            rnd.get("pool", ""), rnd.get("question_id", ""),
            rnd.get("answer_index"),
            seconds=max(5.0, float(rnd.get("seconds") or 45.0)
                        - float(rnd.get("elapsed") or 0.0)),
            payload=rnd.get("question") or {},
            tag=rnd.get("number"))
        self.seen_round = rnd.get("number") or 0
        log.info("cohort: net round %s started locally", self.seen_round)

    def _report(self, room, tag):
        """Hand in this table's results once the local round has closed.

        The tag is read before the round is closed, because closing clears it
        off the room and a report filed against the wrong round is refused.
        """
        summary = room.close_round()
        if summary is None:
            return
        self.pending = {
            "unit": self.unit_id, "round": tag, "instance": self.instance,
            # Which of these were practice players travels with them. A hall
            # board that lists a machine among the fastest without saying so
            # is the one thing the practice players were built not to do.
            "players": [{"name": a["name"], "correct": a["correct"],
                         "ms": a["ms"], "bot": a.get("bot"),
                         # For the certificate only. The hall never puts it
                         # on a board; it is carried so the host can print it.
                         "cert_name": room.cert_name_of(a.get("player_id")),
                         # The class they said they hold, if they did - for
                         # the hall's log, which keeps no names at all.
                         "license": room.license_of(a.get("player_id"))}
                        for a in summary["answers"]],
        }

    def _flush(self):
        if not self.pending:
            return
        reply = self._call("/api/net/report", self.pending)
        if reply.get("accepted"):
            self.reported_round = self.pending["round"]
            log.info("cohort: reported %d answers for net round %s",
                     reply.get("counted", 0), self.reported_round)
            self.pending = None
        elif "already reported" in str(reply.get("reason", "")):
            self.pending = None      # net control already has it
        elif "not the one in progress" in str(reply.get("reason", "")):
            # The hall closed this round without us - the host called an
            # intermission, or the grace ran out. Nothing to hand in any
            # more; the table's own players were scored locally regardless.
            log.info("cohort: net round %s closed before this table reported",
                     self.pending["round"])
            self.pending = None

    def _tick(self):
        room = party.room(create=True, cohorts=1)
        rnd = self._checkin(room)
        self._flush()

        local = room.round
        # Fast while anything is timing: a live round at the master, one open
        # on this table, or the run-up on its way; quiet otherwise.
        lead = (self.hall_show or {}).get("lead_in")
        self._active = bool(rnd) or bool(local and not local.closed) or bool(lead)
        if rnd and (rnd.get("number") or 0) > self.seen_round:
            self._start_local(room, rnd)
            return
        # The local round is over when everybody has answered or time is up;
        # close it and queue the report. It is also over when the hall has
        # moved on without it - the host called an intermission and net
        # control scored the round early - because a table still showing a
        # question the hall has closed is a table the host's press did not
        # reach.
        if local and not local.closed and local.tag:
            hall_moved_on = rnd is None or (rnd.get("number") or 0) != local.tag
            if room.everyone_answered() or local.expired() or hall_moved_on:
                if hall_moved_on:
                    log.info("cohort: the hall closed round %s - closing it here",
                             local.tag)
                self._report(room, local.tag)
                self._flush()

    def _follow(self):
        """The net is not answering here; ask whether it is heard elsewhere.

        A host that rebooted overnight can come back on a different address,
        and a table that only remembered where the net *was* would sit
        offline beside a hall that is running. The token says it is the same
        net; the roster says where.
        """
        if not self.net_token or self.locate is None:
            return False
        try:
            found = self.locate(self.net_token)
        except Exception:                             # pragma: no cover
            return False
        url = str((found or {}).get("url") or "").rstrip("/")
        if not url or url == self.url:
            return False
        log.info("cohort: %s has moved from %s to %s - following it",
                 self.net_name or "the net", self.url, url)
        self.url = url
        self._remember_self()
        return True

    def _remember_self(self):
        """Keep the wiring from the bridge's own thread, which has no request."""
        try:
            from . import db
            connection = db.connect()
            try:
                remember(connection, self)
                connection.commit()
            finally:
                connection.close()
        except Exception:                             # pragma: no cover
            log.debug("cohort: could not save the net's address")

    def run(self):
        wait = POLL_SECONDS
        while not self.stop.is_set():
            try:
                self._tick()
                wait = POLL_SECONDS if self._active else WAITING_SECONDS
            except (urllib.error.URLError, OSError, ValueError) as exc:
                # Net control is off, busy, or unreachable. Not an error worth
                # stopping for - back off and keep the table running - and
                # worth asking whether the net is heard somewhere else now.
                self.state = "offline"
                self.last_error = f"{type(exc).__name__}: {exc}"
                wait = POLL_SECONDS if self._follow() else min(BACKOFF_MAX, wait * 1.8)
            except Exception as exc:                      # pragma: no cover
                self.state = "faulted"
                self.last_error = repr(exc)
                log.exception("cohort bridge: %s", exc)
                wait = BACKOFF_MAX
            self.stop.wait(wait)
        self.state = "stopped"

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="cohort-bridge")
        self.thread.start()
        return self

    def as_dict(self):
        return {"url": self.url, "unit": self.unit_id, "name": self.name,
                "net_name": self.net_name, "net_token": self.net_token,
                "difficulty": self.net_difficulty,
                "state": self.state, "error": self.last_error,
                "net_round": self.seen_round,
                "reported": self.reported_round,
                "waiting_to_report": bool(self.pending),
                "mode": self.net_mode,
                "ready": self.ready,
                "rtt_ms": self.rtt_ms,
                "rtt_p95": (round(sorted(self._rtt)[min(len(self._rtt) - 1,
                            int(len(self._rtt) * 0.95))], 1)
                            if len(self._rtt) >= 4 else None),
                "shootout": self.hall_shootout,
                "show": self.hall_show,
                "quiet_for": (round(time.time() - self.last_contact, 1)
                              if self.last_contact else None)}


def bridge():
    with _lock:
        return _bridge


# callable(token) -> {"url": ...} or None: where a net with this token is
# heard now. Set by the app from discovery; a bridge made before it is set,
# or in a test, simply has nowhere to ask.
locator = None


# Where a table remembers its net control, so a hall does not have to be
# re-wired by hand every morning - these Pis reboot at 04:00 for updates, and
# an operator should not arrive to find every table orphaned.
URL_SETTING = "net_url"
UNIT_SETTING = "net_unit"
NAME_SETTING = "net_name"
TOKEN_SETTING = "net_token"

# Whether this table will attach itself to a net it hears.  On, because the
# alternative is what every fresh Pi did until now: sit by itself running its
# own questions in a room where a hall was already going, because nobody had
# typed an address into it.
#
# It goes off when somebody cuts the table loose by hand, and only then.  An
# operator who has just taken a table out of a net and watches it walk
# straight back in has not been given a choice, they have been overruled.
AUTO_SETTING = "net_auto"


def auto_join_wanted(conn):
    try:
        from . import db
        return db.unit_get(conn, AUTO_SETTING, "on") != "off"
    except Exception:                     # pragma: no cover
        return True


def set_auto_join(conn, wanted):
    try:
        from . import db
        db.unit_set(conn, AUTO_SETTING, "on" if wanted else "off")
    except Exception:                     # pragma: no cover
        pass


def connect(url, unit_id=None, name=None, conn=None, token=None):
    """Point this table at a net control and start reporting to it."""
    global _bridge
    with _lock:
        if _bridge is not None:
            _bridge.stop.set()
        _bridge = Bridge(url, unit_id, name, token).start()
    if conn is not None:
        remember(conn, _bridge)
    return _bridge


def remember(conn, link):
    """Keep the wiring, so the table finds its way back after a reboot."""
    try:
        from . import db
        db.unit_set(conn, URL_SETTING, link.url)
        db.unit_set(conn, UNIT_SETTING, link.unit_id)
        db.unit_set(conn, NAME_SETTING, link.name)
        db.unit_set(conn, TOKEN_SETTING, link.net_token or "")
    except Exception:                     # pragma: no cover
        log.debug("cohort: could not save the net control address")


def forget(conn):
    try:
        from . import db
        db.unit_set(conn, URL_SETTING, "")
    except Exception:                     # pragma: no cover
        pass


def resume(conn):
    """Reconnect to the net control this table was last pointed at.

    Called once at startup. A hall of tables that came back from an overnight
    reboot should rejoin the net on its own; nobody wants to walk twenty Pis
    through a form before the doors open.
    """
    try:
        from . import db
        url = (db.unit_get(conn, URL_SETTING) or "").strip()
    except Exception:                     # pragma: no cover
        return None
    if not url:
        return None
    unit_id = db.unit_get(conn, UNIT_SETTING) or None
    name = db.unit_get(conn, NAME_SETTING) or None
    token = db.unit_get(conn, TOKEN_SETTING) or None
    log.info("cohort: rejoining the net at %s as %s", url, unit_id or "this table")
    return connect(url, unit_id, name, token=token)


def disconnect(conn=None):
    global _bridge
    with _lock:
        if _bridge is not None:
            _bridge.stop.set()
        _bridge = None
    if conn is not None:
        forget(conn)
