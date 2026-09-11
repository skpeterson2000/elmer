"""Printouts: the PDFs this unit has made, kept where they were made.

A chart is built by pressing a button in ELMER and then, until now, dropped
into the browser's downloads folder - which on a Pi running full screen with no
tabs and no address bar means leaving the application, finding a file manager,
and coming back. The file was three feet away and out of reach.

So the unit keeps them. Every PDF it builds is written here, listed on a shelf
inside the application, opened in the page it was made from and printed from
there. Nothing has to be found, and nothing has to be left.

The shelf is not an archive. It holds the last few dozen things printed, oldest
dropped first, because the case it is for is "print that again" and "I meant
the other class" - not a filing cabinet. Everything on it can be rebuilt from
the button that made it, so losing the tail of it costs nobody anything.
"""
import json
import logging
import re
import time
import uuid
from pathlib import Path
from . import paths

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
SHELF = paths.STATE / "prints"
INDEX = SHELF / "index.json"

# Enough to cover an evening of "one more version of that", and small enough
# that a full shelf is a few megabytes on a card that has better uses.
KEEP = 30
KEEP_BYTES = 40 * 1024 * 1024

SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _load():
    try:
        got = json.loads(INDEX.read_text())
        return got if isinstance(got, list) else []
    except (OSError, ValueError):
        return []


def _save(rows):
    SHELF.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(rows, indent=1))


def _path(print_id):
    """The file for an id, or None if the id is not one of ours.

    Ids are generated here and are plain hex, so anything else is somebody
    trying their luck with a path - and this function is what stands between
    that and the filesystem.
    """
    if not re.fullmatch(r"[0-9a-f]{12,32}", str(print_id or "")):
        return None
    return SHELF / f"{print_id}.pdf"


def keep(pdf, name, kind, title, meta=None):
    """Put a freshly built PDF on the shelf and return its row."""
    SHELF.mkdir(parents=True, exist_ok=True)
    print_id = uuid.uuid4().hex[:16]
    path = SHELF / f"{print_id}.pdf"
    path.write_bytes(pdf)
    row = {"id": print_id, "name": SAFE.sub("-", name) or "printout.pdf",
           "kind": kind, "title": title, "bytes": len(pdf),
           "made_at": time.time(), "meta": meta or {}}
    rows = [row] + _load()
    _save(rows)
    prune()
    log.info("printout kept: %s (%s, %d bytes)", row["name"], kind, len(pdf))
    return row


def prune():
    """Drop the oldest until the shelf is a shelf again."""
    rows, total, kept = _load(), 0, []
    for row in rows:                       # newest first
        total += int(row.get("bytes") or 0)
        if len(kept) < KEEP and total <= KEEP_BYTES:
            kept.append(row)
            continue
        path = _path(row.get("id"))
        if path and path.exists():
            path.unlink()
    if len(kept) != len(rows):
        _save(kept)
    return len(rows) - len(kept)


def shelf():
    """What is on it, newest first, with anything whose file has gone left out."""
    rows, live = _load(), []
    for row in rows:
        path = _path(row.get("id"))
        if path and path.exists():
            live.append(row)
    if len(live) != len(rows):
        _save(live)
    return live


def one(print_id):
    for row in shelf():
        if row["id"] == print_id:
            return row
    return None


def read(print_id):
    """The bytes, or None. The id is checked before anything touches disk."""
    path = _path(print_id)
    if path is None or not path.exists():
        return None
    return path.read_bytes()


def forget(print_id):
    path = _path(print_id)
    if path is None:
        return False
    rows = [r for r in _load() if r.get("id") != print_id]
    gone = path.exists()
    if gone:
        path.unlink()
    _save(rows)
    return gone
