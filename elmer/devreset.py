"""Put this unit back to how a fresh clone finds it. For the person building it.

    ---------------------------------------------------------------
    THIS IS A DEVELOPMENT TOOL. To take it out again, delete this
    file, the /api/dev/reset routes in app.py, and the Developer
    panel at the foot of tools.html. Nothing else refers to it.
    ---------------------------------------------------------------

Somebody writing this program resets it constantly - to see the first run
again, to photograph an empty dashboard, to check that a new install does what
it should. Doing that from a terminal means leaving the application, and the
whole point of the rest of ELMER is that leaving is the thing that costs.

What "fresh" means is not invented here. `.gitignore` is already a written
inventory of what belongs to the operator rather than to the program, so a
reset is exactly `git clean` of the ignored files under data/ - which leaves
the pools, figures and rules a clone ships with, and takes the database, the
logs, the caches and the fetched lists.

Two things it will not do. It will not answer a request from anywhere but this
machine, because a study session that anybody on the network can erase is not
a study session. And it will not act without being told twice: the first call
says what would go, and only a second one carrying that list actually goes.

And one thing it cannot do from inside a running ELMER: the deleting itself.
The server holds the database and the log open, and on Windows the ELMER
window holds its browser profile; git clean cannot remove an open file there
("failed to remove data/elmer.db: Invalid argument"), so a reset done in
place said it was resetting and took nothing. So the press only marks the
reset - a file in data/ - and restarts ELMER the way an update does; the new
process finds the mark before it opens anything and does the clean then, when
nothing is held. The mark is inside data/ and untracked, so the clean takes
it too, and a clean that failed is not tried for ever.
"""
import logging
import shutil
import subprocess
import time
from pathlib import Path

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PENDING = DATA / "reset-pending"       # the mark: reset on the next start


def available():
    """Whether a reset can be done here at all."""
    return bool(shutil.which("git")) and (ROOT / ".git").exists()


def _clean(dry_run):
    flags = "-xdn" if dry_run else "-xdf"
    return subprocess.run(["git", "clean", flags, "data/"], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=60)


def would_remove():
    """What a reset would take, without taking any of it."""
    if not available():
        return {"ok": False,
                "error": "this copy is not a git checkout, so ELMER cannot "
                         "work out what a fresh one would look like"}
    done = _clean(dry_run=True)
    if done.returncode != 0:
        return {"ok": False, "error": (done.stderr or "git clean failed")[:200]}
    items = [line.replace("Would remove ", "").strip()
             for line in done.stdout.splitlines() if line.strip()]
    return {"ok": True, "items": items, "count": len(items)}


def reset():
    """Take them, now. Only for a process that holds nothing in data/ - the
    startup path, before the log and the database are opened. Returns what
    went. Retries for a few seconds: the browser window closed on the way
    out can take a moment to let go of its profile."""
    if not available():
        return {"ok": False, "error": "not a git checkout"}
    before = would_remove()
    done = None
    for attempt in range(12):
        done = _clean(dry_run=False)
        if done.returncode == 0:
            break
        time.sleep(0.5)
    if done is None or done.returncode != 0:
        return {"ok": False, "error": (done.stderr if done else "git clean failed")[:200]}
    gone = [line.replace("Removing ", "").strip()
            for line in done.stdout.splitlines() if line.strip()]
    log.warning("dev reset: removed %d item(s) from data/ - %s",
                len(gone), ", ".join(gone[:8]))
    return {"ok": True, "removed": gone, "count": len(gone),
            "expected": before.get("count")}


def request():
    """Mark the reset for the next start. The restart is the caller's."""
    if not available():
        return {"ok": False, "error": "not a git checkout"}
    DATA.mkdir(parents=True, exist_ok=True)
    PENDING.write_text("reset asked for from the Developer panel\n", encoding="utf-8")
    return {"ok": True, "restarting": True}


def pending():
    return PENDING.exists()


def perform_if_pending():
    """At startup, before anything in data/ is opened: the reset that was
    asked for, if one was. Returns what went, or None when nothing was
    asked for. The mark goes first, so a clean that cannot finish is not
    tried at every start from then on."""
    if not pending():
        return None
    try:
        PENDING.unlink()
    except OSError:
        pass
    return reset()
