"""Where things live: what ships with the program, and what belongs to whoever
runs it.

Two kinds of thing were in `data/`, and for a long time they were told apart
only by .gitignore. The question pools, the figures, the bundled places and
the rule text ship with the program and are read. The database, the log, the
print shelf, the caches of things fetched from the network, and the notes
somebody typed belong to the operator and are written.

The distinction matters most to the tests. A test that imports the app and
asks it a question used to do so against the operator's own database, shelf
and log - and four of them, in one day, wrote a stranger's club name into a
unit setting, left a certificate on the real shelf, set a password on a real
account, or read the operator's licence class and failed the day it changed.
Patching each one is how the fifth happens. So the operator's state has one
root, and the tests move it: ELMER_STATE names a directory, set before any
part of the program is imported, and everything that writes goes there while
everything that ships is still found where it ships. In use, unset, both are
`data/`, and nothing changes.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# What ships with the program. Never moved: a test needs the pools.
CONTENT = ROOT / "data"

# What belongs to the operator. Moved by ELMER_STATE, read once at import so
# that a program is one place for its whole life - a state directory that
# changed under a running server would be a worse bug than any it prevents.
STATE = Path(os.environ.get("ELMER_STATE") or (ROOT / "data")).resolve()


def isolated():
    """True when the operator's state has been moved away from data/."""
    return STATE != CONTENT.resolve()
