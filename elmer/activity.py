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
first five, and the log says it ran on the backstop. When each job began
waiting is kept in the operator's state (`deferred.json`), written once as
the wait begins and once as the job runs, so a restart does not start the
day again.

Every signal is read defensively. A check that cannot answer - a database
that is locked, a module not yet loaded - counts as not busy for that one
signal, and is logged at debug: a unit that cannot tell must still get its
files eventually, and a signal that fails is not a reason to hold everything.
"""

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta

from . import paths

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

# When each deferred job began waiting, by the wall clock, because it has to
# mean the same thing after a restart and the monotonic clock does not.
DEFERRED = paths.STATE / "deferred.json"
# A name nobody has waited under for this long is a job that no longer
# exists under that name; it is dropped at the next write.
FORGET_AFTER_S = 14 * 24 * 3600

_clock = time.monotonic     # the clock presses are stamped with; the tests move it
_wall = time.time           # the clock a wait is measured by; the tests move it too
_last = {}                  # kind -> _clock() at the last press, answer or join
_last_lock = threading.Lock()
_deferred_lock = threading.Lock()
_deferred_mem = {}          # what the file holds: job -> _wall() when it began waiting
_deferred_loaded = False
_deferred_said = set()      # the one warning about the file, said once
_backstopped = set()        # jobs already told the log they are on the backstop
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


def _say_once(key, message, *args):
    if key not in _deferred_said:
        _deferred_said.add(key)
        log.warning(message, *args)


def _record():
    """What is waiting and since when: read from the file the first time it is
    asked for, and kept here after that - this process is the only writer.
    Called inside _deferred_lock."""
    global _deferred_loaded
    if _deferred_loaded:
        return _deferred_mem
    _deferred_loaded = True
    try:
        data = json.loads(DEFERRED.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _deferred_mem
    except (OSError, ValueError) as exc:
        _say_once("read", "deferred jobs: cannot read %s, so a wait that began before a "
                  "restart starts again: %s", DEFERRED, exc)
        return _deferred_mem
    if not isinstance(data, dict):
        _say_once("shape", "deferred jobs: %s is not a record of waits; starting afresh", DEFERRED)
        return _deferred_mem
    _deferred_mem.update({str(k): float(v) for k, v in data.items()
                          if isinstance(v, (int, float))})
    return _deferred_mem


def _write_deferred():
    """The record to the file. Called inside _deferred_lock. A state directory
    that cannot be written leaves the record in memory: the backstop still
    works, only not across a restart."""
    now = _wall()
    for k in [k for k, v in _deferred_mem.items() if now - v >= FORGET_AFTER_S]:
        del _deferred_mem[k]
    tmp = DEFERRED.with_name(f"{DEFERRED.name}.{os.getpid()}.tmp")
    try:
        DEFERRED.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(_deferred_mem, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, DEFERRED)
    except OSError as exc:
        _say_once("write", "deferred jobs: cannot write %s, so how long a job has waited "
                  "will not survive a restart: %s", DEFERRED, exc)
        try:
            tmp.unlink()
        except OSError:
            pass                        # it was never made, or the directory is gone


def _waiting_since(what):
    """When `what` began waiting, if a wait of its was left unfinished."""
    with _deferred_lock:
        return _record().get(what)


def _begin(what, since):
    with _deferred_lock:
        _record()[what] = since
        _write_deferred()


def _end(what):
    with _deferred_lock:
        if _record().pop(what, None) is not None:
            _write_deferred()
    _backstopped.discard(what)


def _waited(since):
    # A Pi has no clock of its own and can boot an hour in the past before
    # the network sets it right; a wait that seems to have begun in the
    # future has waited no time at all.
    return max(0.0, _wall() - since)


def _busy_for(what, since):
    """busy(), or the backstop's shorter question once `what` has waited a day."""
    if since is None or _waited(since) < BACKSTOP_S:
        return busy()
    if what not in _backstopped:
        _backstopped.add(what)
        log.warning("%s has waited %.1f h for the unit to be quiet for %d minutes; "
                    "five quiet minutes will do now", what, _waited(since) / 3600, ACTIVE_S // 60)
    return busy(fresh=True, within=BACKSTOP_QUIET_S)


def wait_until_idle(what, stop=None, poll=POLL_S):
    """Hold `what` until the unit is idle. Returns False if `stop` was set
    while waiting, True otherwise - so a loop can end cleanly.

    After BACKSTOP_S of waiting, five quiet minutes are enough: the job
    runs on the backstop, and the log says so. The wait is counted from when
    it began, before a restart if there was one; a loop told to stop leaves
    its wait on record for the next start to pick up.
    """
    since = _waiting_since(what)
    reason = _busy_for(what, since)
    if reason:
        if since is None:
            since = _wall()
            _begin(what, since)
            log.info("%s waits: the unit is busy with %s", what, reason)
        else:
            log.info("%s waits: the unit is busy with %s (it has been waiting since %s)",
                     what, reason, datetime.fromtimestamp(since).strftime("%Y-%m-%d %H:%M"))
        while reason:
            if stop is not None:
                if stop.wait(poll):
                    return False
            else:
                time.sleep(poll)
            reason = _busy_for(what, since)
    if since is None:
        return True
    waited = _waited(since)
    _end(what)
    if waited >= BACKSTOP_S:
        log.warning("%s goes ahead on the backstop: it waited %.1f h, and the unit has been "
                    "quiet for %d minutes", what, waited / 3600, BACKSTOP_QUIET_S // 60)
    else:
        log.info("%s goes ahead: the unit is idle (waited %d s)", what, waited)
    return True
