"""Whether the unit is busy with the person or the table in front of it.

A Pi has one job. While a game, a net, a mock exam or a study session is
running, the work nobody at the unit asked for - the spot feed, the FCC's
license files and their index, the update check, the weekly report, the
GPS watch, re-reading the Library's books - waits, and runs when the unit is
idle. It never runs mid-question.

Busy means somebody is doing something, not that something is open. A table
left seated, or a net left hosted, overnight is not a game: a table or a net
counts only if there has been play, an answer, a join or a press in the last
ten minutes, and a mock exam only while its answers are arriving. `touch()`
is how those are heard - the routes a person presses call it, and so does
net control when a new table checks in or a table reports real answers. It
is kept in memory, not in the database: a press is not worth a write to the
SD card, and after a restart the next press says it again.

`busy()` says what the unit is doing, in words, or None when it is idle.
`wait_until_idle()` is what a background loop calls before its work: it
returns at once on an idle unit and otherwise waits, saying once in the log
what is waiting and for what, and once when it goes ahead. A job that has
waited a whole day - a hall running round the clock, a table that is never
quiet for ten minutes - stops waiting for ten quiet minutes and takes the
first five, and the log says it ran on the backstop.

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
# studying. A table, a net or a mock exam with play, an answer, a join or a
# press in the last ten minutes is somebody using it. An unfinished mock exam
# is only ever considered in the two hours after it started - an abandoned
# exam stays unfinished for ever, so an old one is not a reason to wait even
# if a stale page is still pinging it.
STUDY_RECENT_S = 300
ACTIVE_S = 600
EXAM_RECENT_S = 7200
# The backstop. A job deferred this long goes ahead after this much quiet,
# rather than the ten minutes above: a unit that is never quiet for ten
# minutes must still get its files, its update check and its report.
BACKSTOP_S = 24 * 3600
BACKSTOP_QUIET_S = 300
POLL_S = 30.0               # how often a waiting loop looks again
CACHE_S = 5.0               # one answer serves every loop that asks within this

KINDS = ("table", "net", "exam")

_clock = time.monotonic     # one clock for presses and waits; the tests move it
_last = {}                  # kind -> _clock() at the last press, answer or join
_last_lock = threading.Lock()
_cache = {"at": 0.0, "value": None}
_cache_lock = threading.Lock()


def touch(kind):
    """Somebody did something at the table, in the net or on the exam."""
    if kind not in KINDS:
        raise ValueError(f"no such activity: {kind!r}")
    with _last_lock:
        _last[kind] = _clock()


def quiet_for(kind):
    """Seconds since the last `touch(kind)`, or None if there has been none."""
    with _last_lock:
        at = _last.get(kind)
    return None if at is None else _clock() - at


def _recent(kind, within):
    quiet = quiet_for(kind)
    return quiet is not None and quiet < within


def _table(within=ACTIVE_S):
    """A game, or a table with people at it, that somebody is playing."""
    from . import party
    room = party.room()
    if room is None or not _recent("table", within):
        return None
    if room.round or room.golf or room.shootout or room.cutthroat or room.baseball or room.clubhouse:
        return "a game at the table"
    if any(not p.bot for p in room.players.values()):
        return "people at the table"
    return None


def _net(within=ACTIVE_S):
    """Hosting a net, or a table in somebody's net with a round on, with
    somebody in it doing something."""
    from . import cohort, netcontrol
    if netcontrol.net() is not None and _recent("net", within):
        return "a net"
    # This unit's table in another unit's net: its people press here, at
    # the table, and the net that asks them is somewhere else.
    bridge = cohort.bridge()
    if bridge is not None and getattr(bridge, "_active", False) and _recent("table", within):
        return "a round in a net"
    return None


def _desk(conn=None, within=ACTIVE_S):
    """A mock exam whose answers are arriving, or somebody answering questions."""
    from . import db
    own = conn is None
    conn = conn or db.connect()
    try:
        now = db.utcnow()
        if _recent("exam", within):
            exam = conn.execute("SELECT 1 FROM exam WHERE finished IS NULL AND started >= ? LIMIT 1",
                                ((now - timedelta(seconds=EXAM_RECENT_S)).isoformat(),)).fetchone()
            if exam:
                return "a mock exam"
        study = conn.execute("SELECT 1 FROM answer_log WHERE ts >= ? LIMIT 1",
                             ((now - timedelta(seconds=min(STUDY_RECENT_S, within))).isoformat(),)).fetchone()
        if study:
            return "a study session"
        return None
    finally:
        if own:
            conn.close()


def busy(conn=None, fresh=False, within=ACTIVE_S):
    """What the unit is busy with, in words, or None when it is idle.

    `within` is how recent a press has to be to count; the backstop asks
    with a shorter one.
    """
    now = time.monotonic()
    cacheable = conn is None and within == ACTIVE_S
    with _cache_lock:
        if not fresh and cacheable and now - _cache["at"] < CACHE_S:
            return _cache["value"]
    found = None
    for name, check in (("table", lambda: _table(within)), ("net", lambda: _net(within)),
                        ("desk", lambda: _desk(conn, within))):
        try:
            found = check()
        except (sqlite3.Error, AttributeError, ImportError, RuntimeError) as exc:
            log.debug("activity: the %s check could not answer: %s", name, exc)
            found = None
        if found:
            break
    if cacheable:
        with _cache_lock:
            _cache["at"], _cache["value"] = now, found
    return found


def wait_until_idle(what, stop=None, poll=POLL_S):
    """Hold `what` until the unit is idle. Returns False if `stop` was set
    while waiting, True otherwise - so a loop can end cleanly.

    After BACKSTOP_S of waiting, five quiet minutes are enough: the job
    runs on the backstop, and the log says so.
    """
    reason = busy()
    if not reason:
        return True
    log.info("%s waits: the unit is busy with %s", what, reason)
    started = _clock()
    backstop = False
    while reason:
        if stop is not None:
            if stop.wait(poll):
                return False
        else:
            time.sleep(poll)
        waited = _clock() - started
        if waited >= BACKSTOP_S:
            if not backstop:
                backstop = True
                log.warning("%s has waited %.1f h for the unit to be quiet for %d minutes; "
                            "five quiet minutes will do now", what, waited / 3600, ACTIVE_S // 60)
            reason = busy(fresh=True, within=BACKSTOP_QUIET_S)
        else:
            reason = busy()
    waited = _clock() - started
    if backstop:
        log.warning("%s goes ahead on the backstop: it waited %.1f h, and the unit has been "
                    "quiet for %d minutes", what, waited / 3600, BACKSTOP_QUIET_S // 60)
    else:
        log.info("%s goes ahead: the unit is idle (waited %d s)", what, waited)
    return True
