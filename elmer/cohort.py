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
import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request

from . import party

log = logging.getLogger("elmer")

POLL_SECONDS = 1.0
TIMEOUT = 4.0
BACKOFF_MAX = 15.0

_bridge = None
_lock = threading.Lock()


def default_unit_id():
    """Something stable and human enough to read off a big board."""
    try:
        return socket.gethostname().split(".")[0][:40] or "table"
    except OSError:
        return "table"


class Bridge:
    """One table's conversation with net control."""

    def __init__(self, url, unit_id=None, name=None):
        self.url = url.rstrip("/")
        self.unit_id = (unit_id or default_unit_id())[:40]
        self.name = (name or self.unit_id)[:60]
        self.stop = threading.Event()
        self.thread = None
        self.state = "starting"
        self.last_error = None
        self.seen_round = 0          # net round this table has already started
        self.reported_round = 0      # net round this table has handed in
        self.pending = None          # a report waiting for the network
        self.last_contact = 0.0

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
        players = len(room.players) if room else 0
        reply = self._call("/api/net/checkin",
                           {"unit": self.unit_id, "name": self.name,
                            "players": players})
        if not reply.get("checked_in", True):
            # The net is full. Say so plainly and keep trying: a table that
            # arrives late should join when somebody else's table packs up.
            self.state = "refused"
            self.last_error = reply.get("reason")
            return None
        self.state = "joined"
        self.last_error = None
        self.last_contact = time.time()
        return reply.get("round")

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
            "unit": self.unit_id, "round": tag,
            "players": [{"name": a["name"], "correct": a["correct"],
                         "ms": a["ms"]}
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

    def _tick(self):
        room = party.room(create=True, cohorts=1)
        rnd = self._checkin(room)
        self._flush()

        local = room.round
        if rnd and (rnd.get("number") or 0) > self.seen_round:
            self._start_local(room, rnd)
            return
        # The local round is over when everybody has answered or time is up;
        # close it and queue the report.
        if local and not local.closed and local.tag:
            if room.everyone_answered() or local.expired():
                self._report(room, local.tag)
                self._flush()

    def run(self):
        wait = POLL_SECONDS
        while not self.stop.is_set():
            try:
                self._tick()
                wait = POLL_SECONDS
            except (urllib.error.URLError, OSError, ValueError) as exc:
                # Net control is off, busy, or unreachable. Not an error worth
                # stopping for - back off and keep the table running.
                self.state = "offline"
                self.last_error = f"{type(exc).__name__}: {exc}"
                wait = min(BACKOFF_MAX, wait * 1.8)
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
                "state": self.state, "error": self.last_error,
                "net_round": self.seen_round,
                "reported": self.reported_round,
                "waiting_to_report": bool(self.pending),
                "quiet_for": (round(time.time() - self.last_contact, 1)
                              if self.last_contact else None)}


def bridge():
    with _lock:
        return _bridge


# Where a table remembers its net control, so a hall does not have to be
# re-wired by hand every morning - these Pis reboot at 04:00 for updates, and
# an operator should not arrive to find every table orphaned.
URL_SETTING = "net_url"
UNIT_SETTING = "net_unit"
NAME_SETTING = "net_name"


def connect(url, unit_id=None, name=None, conn=None):
    """Point this table at a net control and start reporting to it."""
    global _bridge
    with _lock:
        if _bridge is not None:
            _bridge.stop.set()
        _bridge = Bridge(url, unit_id, name).start()
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
    log.info("cohort: rejoining the net at %s as %s", url, unit_id or "this table")
    return connect(url, unit_id, name)


def disconnect(conn=None):
    global _bridge
    with _lock:
        if _bridge is not None:
            _bridge.stop.set()
        _bridge = None
    if conn is not None:
        forget(conn)
