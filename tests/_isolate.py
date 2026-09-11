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

# The guard. Not a fingerprint of data/ - a live ELMER on the same machine
# writes its log and its database every second, and a fingerprint blames
# whoever wrote last. Python's audit hook sees what *this process* does: every
# file it opens for writing, every database it connects to, every remove,
# rename or mkdir - and nothing any other process does. That is exactly the
# question: did the test touch the operator's files.
#
# Reading is allowed, because the pools and the figures live under data/ and
# reading them is the point. Connecting to a database under data/ is not
# allowed even to read - that is how a test came to depend on the operator's
# licence class - and neither is any kind of write.
_touched = []


def _under_real(path):
    try:
        p = Path(os.fsdecode(path))
        if not p.is_absolute():
            p = Path.cwd() / p
        return REAL.resolve() in p.resolve().parents or p.resolve() == REAL.resolve()
    except Exception:
        return False


_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


def _hook(event, args):
    try:
        if event == "open":
            path, mode, flags = args
            writing = (mode and any(c in mode for c in "wax+")) or (flags and flags & _WRITE_FLAGS)
            if writing and _under_real(path):
                _touched.append(f"{event} {os.fsdecode(path)} ({mode or flags})")
        elif event in ("sqlite3.connect",):
            if args and _under_real(args[0]):
                _touched.append(f"{event} {args[0]}")
        elif event in ("os.remove", "os.unlink", "os.rmdir", "os.mkdir", "os.rename",
                       "shutil.rmtree", "shutil.move", "os.truncate"):
            for a in args[:2]:
                if isinstance(a, (str, bytes, os.PathLike)) and _under_real(a):
                    _touched.append(f"{event} {os.fsdecode(a)}")
                    break
    except Exception:
        pass                              # the hook must never take the test down


sys.addaudithook(_hook)


@atexit.register
def _guard():
    if _touched:
        sys.stderr.write("\nISOLATION BREACH: this test touched the operator's data/:\n")
        for line in _touched[:12]:
            sys.stderr.write(f"    {line}\n")
        sys.stderr.write("A test must run against ELMER_STATE, never against data/.\n")
        sys.stderr.flush()
        os._exit(3)
