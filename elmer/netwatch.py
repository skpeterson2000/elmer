"""Watching every tournament on the network at once.

A hamfest can hold several nets - Technician in one corner, General in another,
Extra in the next room - and the big board could only ever show the one running
on the Pi the screen happened to be plugged into. That is the wrong way round.
The screen at the front of a room should show the room, and the Pi driving it
is an implementation detail nobody in the room cares about.

So the board asks this unit for every game it can hear, and this unit goes and
fetches them. The fetching is here rather than in the browser for three
reasons. A board polls about once a second and there may be half a dozen
tournaments, which from a browser is half a dozen cross-origin requests a
second, and none of them would be permitted anyway. The answers are shared, so
two screens on one Pi cost the hall nothing extra. And a net that goes off the
air must not take the board down with it: a failed fetch leaves the last answer
in place, marked stale, and the board says which tournament has gone quiet
rather than going blank.

Nothing here blocks the request that asks for it. A poll returns what is
cached and sets the refresh going in the background; the next poll, a second
later, has the new answer. A board that waited for six Pis in series would
stutter every time one of them was slow, and the one thing a screen at the
front of a room must not do is stutter.
"""
import json
import logging
import threading
import time
import urllib.error
import urllib.request

log = logging.getLogger("elmer")

TIMEOUT = 1.5            # a single unit's board, over a hall's wireless
FRESH_FOR = 1.5          # a cached board older than this is worth refreshing
RETRY_AFTER = 4.0        # ... but one that just failed is left alone this long
STALE_AFTER = 10.0       # a board older than this is admitted to be stale
GONE_AFTER = 60.0        # ... and older than this stops being shown at all

# `at` is when a board was last got, and only ever moves on success: a net that
# has gone off the air keeps the last thing the room saw, and the age of it is
# what tells the room it has gone. `tried` moves on every attempt, so a unit
# that is not answering is not asked again on every poll.
_cache = {}              # url -> {"board", "at", "tried", "error"}
_lock = threading.Lock()
_busy = set()            # urls a refresh is already in flight for


def _fetch(url, path):
    request = urllib.request.Request(
        url.rstrip("/") + path,
        headers={"User-Agent": "ELMER/1.0 (big board)"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read())


def _refresh(url, path):
    """One tournament, fetched off the request thread."""
    try:
        board = _fetch(url, path)
        with _lock:
            _cache[url] = {"board": board, "at": time.time(),
                           "tried": time.time(), "error": None}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # Keep whatever was there. A net that misses one poll is not gone, and
        # a board that blanks every time a Pi hiccups is unwatchable.
        with _lock:
            was = _cache.get(url) or {}
            _cache[url] = {"board": was.get("board"), "at": was.get("at"),
                           "tried": time.time(),
                           "error": f"{type(exc).__name__}: {exc}"}
    finally:
        with _lock:
            _busy.discard(url)


def _start_refresh(url, path):
    with _lock:
        if url in _busy:
            return
        _busy.add(url)
    threading.Thread(target=_refresh, args=(url, path), daemon=True,
                     name="elmer-board-watch").start()


def look(games):
    """The latest board for each game, and a refresh set going for the stale.

    `games` is what discovery heard: dicts with a url, a name, and the path to
    ask for - a net's hall board, or a lone table's own. What comes back is one
    entry per game in the same order, whether or not it has ever answered.
    """
    now = time.time()
    out = []
    for game in games:
        url = game.get("url") or ""
        path = game.get("path") or "/api/net/board"
        with _lock:
            held = dict(_cache.get(url) or {})
        since_try = now - (held.get("tried") or 0.0)
        if since_try > (RETRY_AFTER if held.get("error") else FRESH_FOR):
            _start_refresh(url, path)
        age = (now - held["at"]) if held.get("at") else None
        board = held.get("board") if age is not None and age <= GONE_AFTER else None
        out.append(dict(game,
                        board=board,
                        age_s=round(age, 1) if age is not None else None,
                        stale=bool(board is not None and age > STALE_AFTER),
                        error=held.get("error")))
    return out


def forget(keep=()):
    """Drop boards for tournaments nobody is watching any more."""
    keep = set(keep)
    with _lock:
        for url in [u for u in _cache if u not in keep]:
            _cache.pop(url, None)
