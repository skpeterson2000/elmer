"""Whether the unit is busy with the person or the table in front of it.

A Pi has one job. While a game, a net, a mock exam or a study session is
running, the work nobody at the unit asked for - the spot feed, the FCC's
license files and their index, the update check, the weekly report, the
GPS watch, re-reading the Library's books - waits, and runs when the unit is
idle. It never runs mid-question.

`busy()` says what the unit is doing, in words, or None when it is idle.
`wait_until_idle()` is what a background loop calls before its work: it
returns at once on an idle unit and otherwise waits, saying once in the log
what is waiting and for what, and once when it goes ahead.

Every signal is read defensively. A check that cannot answer - a database
that is locked, a module not yet loaded - counts as not busy for that one
signal, and is logged at debug: a unit that cannot tell must still get its
files eventually, and a signal that fails is not a reason to hold everything.
"""

import logging
import sqlite3
import threading
import time
from datetime import timedelta

log = logging.getLogger("elmer")

# How recent counts as "now". An answer in the last five minutes is somebody
# studying; an unfinished mock exam started in the last two hours is somebody
# sitting one - an abandoned exam stays unfinished for ever, so an old one is
# not a reason to wait.
STUDY_RECENT_S = 300
EXAM_RECENT_S = 7200
POLL_S = 30.0               # how often a waiting loop looks again
CACHE_S = 5.0               # one answer serves every loop that asks within this

_cache = {"at": 0.0, "value": None}
_cache_lock = threading.Lock()


def _table():
    """A game, or a table with people at it, on this unit."""
    from . import party
    room = party.room()
    if room is None:
        return None
    if room.round or room.golf or room.shootout or room.cutthroat or room.baseball or room.clubhouse:
        return "a game at the table"
    if any(not p.bot for p in room.players.values()):
        return "people at the table"
    return None


def _net():
    """Hosting a net, or a table in somebody's net with a round on."""
    from . import cohort, netcontrol
    if netcontrol.net() is not None:
        return "a net"
    bridge = cohort.bridge()
    if bridge is not None and getattr(bridge, "_active", False):
        return "a round in a net"
    return None


def _desk(conn=None):
    """A mock exam under way, or somebody answering questions."""
    from . import db
    own = conn is None
    conn = conn or db.connect()
    try:
        now = db.utcnow()
        exam = conn.execute("SELECT 1 FROM exam WHERE finished IS NULL AND started >= ? LIMIT 1",
                            ((now - timedelta(seconds=EXAM_RECENT_S)).isoformat(),)).fetchone()
        if exam:
            return "a mock exam"
        study = conn.execute("SELECT 1 FROM answer_log WHERE ts >= ? LIMIT 1",
                             ((now - timedelta(seconds=STUDY_RECENT_S)).isoformat(),)).fetchone()
        if study:
            return "a study session"
        return None
    finally:
        if own:
            conn.close()


def busy(conn=None, fresh=False):
    """What the unit is busy with, in words, or None when it is idle."""
    now = time.monotonic()
    with _cache_lock:
        if not fresh and conn is None and now - _cache["at"] < CACHE_S:
            return _cache["value"]
    found = None
    for name, check in (("table", _table), ("net", _net), ("desk", lambda: _desk(conn))):
        try:
            found = check()
        except (sqlite3.Error, AttributeError, ImportError, RuntimeError) as exc:
            log.debug("activity: the %s check could not answer: %s", name, exc)
            found = None
        if found:
            break
    if conn is None:
        with _cache_lock:
            _cache["at"], _cache["value"] = now, found
    return found


def wait_until_idle(what, stop=None, poll=POLL_S):
    """Hold `what` until the unit is idle. Returns False if `stop` was set
    while waiting, True otherwise - so a loop can end cleanly."""
    reason = busy()
    if not reason:
        return True
    log.info("%s waits: the unit is busy with %s", what, reason)
    started = time.monotonic()
    while reason:
        if stop is not None:
            if stop.wait(poll):
                return False
        else:
            time.sleep(poll)
        reason = busy()
    log.info("%s goes ahead: the unit is idle (waited %d s)", what, time.monotonic() - started)
    return True
