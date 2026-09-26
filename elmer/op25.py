"""Quiet OP25 so a game has the Pi to itself.

OP25 decodes P25 with GNU Radio, and on a Raspberry Pi - a 3 especially - it
takes most of the machine when it runs. A tournament does not need much, but
what it needs it needs *on time*: a Pi already pinned by OP25 serves every
question and every answer from the back of a queue, which reads as latency
and is not the network (see diagnostics.host_load). So when this unit opens a
net or starts a tournament, it can stop OP25 first and hand the game a quiet
machine. The operator relaunches OP25 afterwards; nothing here starts it
again, because only the operator knows whether the scanner should come back.

Precise on purpose. The obvious `pkill -f op25` matches anything with that
path on its command line - a shell sitting in ~/op25, an editor, this very
program if it were run from there - so instead the canonical OP25 app name is
matched (`multi_rx.py`), the candidates are listed, this process and its
parent are never among those killed, and each is stopped by pid with a term
first and a kill only for what will not go. What was stopped is logged and
handed back, so the report and the self-check can say it happened.
"""
import logging
import os
import signal
import subprocess
import time

log = logging.getLogger("elmer")

# Whether to stop OP25 when a game starts, and what an OP25 process looks
# like. Both live in unit settings so an operator can widen the match to
# their own launch script, or turn the whole thing off, without a code change.
ENABLED_SETTING = "stop_op25"
MATCH_SETTING = "op25_match"
DEFAULT_MATCH = "multi_rx.py"


def _settings(conn):
    from . import db
    enabled = db.unit_get(conn, ENABLED_SETTING, "on") != "off" if conn else True
    match = (db.unit_get(conn, MATCH_SETTING, "") if conn else "") or DEFAULT_MATCH
    return enabled, match


def wanted(conn):
    try:
        return _settings(conn)[0]
    except Exception:                     # pragma: no cover
        return False


def match_pattern(conn):
    try:
        return _settings(conn)[1]
    except Exception:                     # pragma: no cover
        return DEFAULT_MATCH


_no_pgrep_said = [False]


def find(match=DEFAULT_MATCH):
    """Every OP25 process, as (pid, command line) - never this one or its parent."""
    mine = {os.getpid(), os.getppid()}
    out = []
    try:
        res = subprocess.run(["pgrep", "-af", match], capture_output=True,
                             text=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        # No pgrep: not Linux, and OP25 is a Linux program - there is nothing
        # here to stop. Said once, not at every game.
        if not _no_pgrep_said[0]:
            log.info("op25: not looked for on this machine (%s) - OP25 runs on Linux", exc)
            _no_pgrep_said[0] = True
        return out
    for line in res.stdout.splitlines():
        pid_s, _, cmd = line.partition(" ")
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        if pid in mine:
            continue                      # never the game, or the shell running it
        # pgrep -f matches the whole command line, so a shell wrapper or a
        # launch script that merely names the app slips in - and killing the
        # terminal or the service wrapper is not the point; the decoder is.
        # Keep only a process that *is* OP25: its own interpreter or script,
        # not a shell that spawned it and still shows it in its arguments.
        tokens = cmd.split()
        if not tokens:
            continue
        first = os.path.basename(tokens[0])
        is_shell = first in ("bash", "sh", "dash", "zsh", "ksh") or "-c" in tokens
        looks_like_op25 = first.startswith("python") or first.endswith(".py")
        if is_shell or not looks_like_op25 or "pgrep" in cmd:
            continue
        out.append((pid, cmd.strip()))
    return out


def running(conn=None, match=None):
    """The OP25 processes on this machine right now (for the self-check)."""
    return find(match or match_pattern(conn))


def stop(conn=None, match=None, reason="a game is starting"):
    """Stop OP25 to free the Pi. Returns the list of (pid, cmd) it stopped.

    Term first, and kill only what has not gone after a moment. Never raises:
    a game must start whether or not the scanner would lie down politely.
    """
    match = match or match_pattern(conn)
    found = find(match)
    if not found:
        return []
    for pid, cmd in found:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError) as exc:
            log.warning("op25: could not stop pid %d (%s): %s", pid,
                        cmd[:60], exc)
    # A GNU Radio flowgraph can take a breath to unwind; give it one, then
    # insist for anything still there.
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        if not find(match):
            break
        time.sleep(0.2)
    for pid, cmd in find(match):
        try:
            os.kill(pid, signal.SIGKILL)
            log.info("op25: pid %d would not stop on its own - killed it", pid)
        except (ProcessLookupError, PermissionError) as exc:
            log.warning("op25: could not kill pid %d: %s", pid, exc)
    log.info("op25: stopped %d process(es) because %s - %s", len(found), reason,
             ", ".join(f"pid {p}" for p, _ in found))
    return found


def stop_if_wanted(conn, reason="a game is starting"):
    """Stop OP25 when the operator has left the setting on. The one the app
    calls at net-open and tournament-start; silent and safe when off or
    when OP25 is not running."""
    try:
        if not wanted(conn):
            return []
        return stop(conn, reason=reason)
    except Exception as exc:              # pragma: no cover - never block a game
        log.warning("op25: could not check on it: %s", exc)
        return []
