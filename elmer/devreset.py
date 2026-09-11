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
"""
import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


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
    """Take them. Returns what went."""
    if not available():
        return {"ok": False, "error": "not a git checkout"}
    before = would_remove()
    done = _clean(dry_run=False)
    if done.returncode != 0:
        return {"ok": False, "error": (done.stderr or "git clean failed")[:200]}
    gone = [line.replace("Removing ", "").strip()
            for line in done.stdout.splitlines() if line.strip()]
    log.warning("dev reset: removed %d item(s) from data/ - %s",
                len(gone), ", ".join(gone[:8]))
    return {"ok": True, "removed": gone, "count": len(gone),
            "expected": before.get("count")}
