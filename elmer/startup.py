"""How long this unit takes to become usable, which is not when it starts.

The socket is bound in a tenth of a second.  The first page can take five
more, because a megabyte of pools comes off the card the first time somebody
asks for one rather than at import.  So a start timed by connecting to the
port reports a tenth of a second on the slowest board in the fleet - which is
worse than not timing it at all, since it is a number that looks like an
answer.

What is timed here is the building of the first page - the pools coming off
the card - and not the wall time until somebody happened to ask for one.  The
difference is the whole value of the number: a unit nobody visits for an hour
would otherwise record an hour and call it a slow start.  How long after
starting it was asked is kept beside it, because a page asked for promptly
carries the operator's whole wait in it and a page asked for later does not.

It is written down rather than only logged, because the question is asked
later and usually from somewhere else - the doctor carries it, the doctor
answers over HTTP, and one unit can then read what every other unit on the
network took to come up.  A median wants a fleet, and walking to each board
to read a log is how a median never gets taken.

Static files are not a page.  They come off the disk without touching a pool,
so timing one would measure the disk, not the program.
"""
import logging
import time

log = logging.getLogger("elmer")

# Import time rather than process start: what happens before this module is
# read is the interpreter coming up, which is not ELMER's to account for and
# not what changes between a fast card and a slow one.
BEGAN = time.monotonic()
BEGAN_AT = time.time()

KEY_BUILD = "first_page_build"      # what the page cost to make
KEY_AFTER = "first_page_after"      # how long after starting it was asked for
KEY_AT = "first_page_at"

_recorded = False


def note_first_page(connection, build_seconds):
    """Called when a page - not a static file - has been served.

    `build_seconds` is what that request took, which is the number worth
    keeping: it is the same measurement on a board somebody opened straight
    away and on one nobody touched until morning.

    Only the first page counts, and only once per run: the second comes off a
    warm program and says nothing about starting.
    """
    global _recorded
    if _recorded:
        return None
    _recorded = True
    after = time.monotonic() - BEGAN - build_seconds
    log.info("first page built in %.1fs, asked for %.1fs after starting",
             build_seconds, max(0.0, after))
    try:
        from . import db
        db.unit_set(connection, KEY_BUILD, round(build_seconds, 2))
        db.unit_set(connection, KEY_AFTER, round(max(0.0, after), 2))
        db.unit_set(connection, KEY_AT, time.time())
    except Exception as exc:                # a slow start is not worth a 500
        log.debug("could not record the start: %s", exc)
    return build_seconds


def last(connection):
    """What the last start took, or None if none has been recorded yet."""
    try:
        from . import db
        build = db.unit_get(connection, KEY_BUILD)
        if build is None:
            return None
        after = db.unit_get(connection, KEY_AFTER)
        return {"build": float(build),
                "after": float(after) if after is not None else None,
                "at": db.unit_get(connection, KEY_AT)}
    except Exception:
        return None


def waiting():
    """True while this run has not served its first page yet."""
    return not _recorded
