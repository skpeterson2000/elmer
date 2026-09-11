"""Import this before anything from elmer, and the test cannot touch data/.

    import _isolate  # noqa: F401
    from elmer import ...

It does two things. It moves the operator's state - the database, the log,
the print shelf, every cache, the notes - to a fresh temporary directory by
setting ELMER_STATE before the program is imported, so a test that asks the
app a question is asking a blank unit rather than this one. And it takes a
fingerprint of the real data/ as the test starts and compares it as the test
ends, so a test that reaches the operator's files anyway - through a path
this helper does not know about, or a module that computed its own - fails
loudly instead of leaving a stranger's club name in somebody's settings.

The fingerprint is deliberately wide: every file under data/ that the program
writes, by size and modification time. What ships with the program is not
watched, because reading it is the point.
"""
import atexit
import os
import sys
import tempfile
from pathlib import Path

if "elmer" in sys.modules or any(m.startswith("elmer.") for m in sys.modules):
    raise RuntimeError("_isolate must be imported before anything from elmer")

ROOT = Path(__file__).resolve().parents[1]
# The directory guarded. Overridable so the guard can be proved against a
# stand-in without a test ever touching the real one to do it.
REAL = Path(os.environ.get("ELMER_ISOLATE_WATCH") or (ROOT / "data"))

STATE = Path(tempfile.mkdtemp(prefix="elmer-test-"))
os.environ["ELMER_STATE"] = str(STATE)

# The operator's files: what the program writes. Names, and whole directories.
WATCHED_FILES = ["elmer.db", "elmer.db-wal", "elmer.db-shm", "elmer.db-journal",
                 "elmer.log", "update.json", "server-console.log"]
WATCHED_DIRS = ["prints", "statutes", "nifog", "places", "pota", "callsign",
                "geocode", "ionosonde", "notes", "explanations", "kiosk-profile"]


def _fingerprint():
    seen = {}
    for name in WATCHED_FILES:
        p = REAL / name
        if p.exists():
            st = p.stat()
            seen[name] = (st.st_size, st.st_mtime_ns)
    for name in WATCHED_DIRS:
        d = REAL / name
        if d.is_dir():
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    st = p.stat()
                    seen[str(p.relative_to(REAL))] = (st.st_size, st.st_mtime_ns)
    return seen


_before = _fingerprint()


@atexit.register
def _guard():
    after = _fingerprint()
    changed = sorted(k for k in set(_before) | set(after) if _before.get(k) != after.get(k))
    if changed:
        sys.stderr.write("\nISOLATION BREACH: this test touched the operator's data/:\n")
        for k in changed[:12]:
            sys.stderr.write(f"    {k}\n")
        sys.stderr.write("A test must run against ELMER_STATE, never against data/.\n")
        sys.stderr.flush()
        os._exit(3)
