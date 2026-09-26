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
account, or read the operator's license class and failed the day it changed.
Patching each one is how the fifth happens. So the operator's state has one
root, and the tests move it: ELMER_STATE names a directory, set before any
part of the program is imported, and everything that writes goes there while
everything that ships is still found where it ships. In use, unset, both are
`data/`, and nothing changes.
"""
import logging
import os
import subprocess
from pathlib import Path

log = logging.getLogger("elmer")

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


def keep_private(path):
    """Make a file its owner's alone - for the few that hold a secret: the
    outgoing-mail password, the supporter roster's signing key.

    On Linux and the Pi that is mode 600. Windows has no mode bits - a chmod
    there sets or clears read-only and nothing else, so for years the
    password file was 600 in intent and whatever it inherited in fact: private
    under a user's own folder, readable by every account on the machine
    anywhere else. So on Windows the inherited permissions are removed and
    the owner and SYSTEM (which backups and the virus scanner run as) are the
    only ones granted - the rule OpenSSH holds a private key to there.

    Returns True when done. A failure is logged and returned, never raised:
    the file is still written, and the operator is told it is not private."""
    path = Path(path)
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
            return True
        except OSError as exc:
            log.warning("could not make %s private: %s", path, exc)
            return False
    user = os.environ.get("USERNAME") or ""
    domain = os.environ.get("USERDOMAIN") or ""
    if not user:
        log.warning("could not make %s private: no USERNAME to grant it to", path)
        return False
    who = f"{domain}\\{user}" if domain else user
    # Two steps: /reset clears anything granted on the file itself - a
    # removed inheritance keeps those - and then the inherited entries go
    # and the owner and SYSTEM are all that is left.
    for step in (["/reset"], ["/inheritance:r", "/grant:r", f"{who}:F", "*S-1-5-18:F"]):
        try:
            done = subprocess.run(["icacls", str(path)] + step, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("could not make %s private: %s", path, exc)
            return False
        if done.returncode != 0:
            log.warning("could not make %s private: icacls said %s", path, (done.stderr or done.stdout).strip()[:200])
            return False
    return True
