"""The last sweep the instrument gave us, kept where more than one page can see it.

A measurement used to live in the page that took it. That was fine while the
VNA and the Smith chart were two tabs of the same document - the trace was a
variable and the chart read it - and it stops being fine the moment they are
two pages, because a variable does not cross a page load.

So it is kept here instead, and the arrangement is better than the one it
replaces rather than a workaround for it. A sweep now survives a reload, which
it never did; it can be looked at from the phone in your pocket while the
instrument is on the bench in front of the Pi; and it is still there tomorrow
when somebody wants to know what the antenna measured before they cut it.

One sweep, not a history. There is one instrument on the bench and one antenna
on the end of it, and a page asking "what did it measure" means the last thing
it measured. Keeping every sweep would be a different feature with a different
question behind it - what changed - and it should be built as one if it is
wanted, rather than arrived at by never deleting anything.
"""
import json
import logging
import time
from pathlib import Path

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "sweep.json"

# A sweep is at most 401 points of six small numbers. This is a sanity bound
# rather than a limit anybody will meet: something an order of magnitude
# larger than the instrument can produce is not a sweep, it is a mistake or a
# browser being creative, and it does not get written to the card.
MAX_POINTS = 1000


def keep(sweep):
    """Hold one measurement. Returns what was kept, or None if it was not."""
    rows = (sweep or {}).get("rows")
    if not rows or not isinstance(rows, list) or len(rows) > MAX_POINTS:
        return None
    record = {
        "device": str(sweep.get("device") or "")[:120],
        "points": len(rows),
        "low_mhz": sweep.get("low_mhz"),
        "high_mhz": sweep.get("high_mhz"),
        "over_unity": sweep.get("over_unity") or 0,
        "taken": time.time(),
        "rows": rows,
    }
    try:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        STORE.write_text(json.dumps(record))
    except OSError as exc:
        log.warning("sweep not kept: %s", exc)
        return None
    return record


def last():
    """The measurement on hand, or None. Never raises: a page asking what the
    instrument said is not a page that should break because a file did."""
    try:
        return json.loads(STORE.read_text())
    except (OSError, ValueError):
        return None


def forget():
    """Throw the held sweep away."""
    try:
        STORE.unlink()
        return True
    except OSError:
        return False
