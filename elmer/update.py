"""Keeping an installation current with the repository it came from.

An ELMER install is a git checkout, so an update is a fast-forward and nothing
more.  That is the whole design: no downloader, no unpacking, no separate
version feed to keep honest.  The checkout already knows where it came from and
git already knows how to tell whether it has fallen behind.

**ELMER never updates itself.**  It looks, it says what it found, and it waits
to be told.  Nobody sitting down to study should find the program changed under
them because a background thread decided it was time, and an update that
arrives unasked on a machine in a shack is a fault report from somewhere far
away rather than something anyone chose.  Applying one is always a press of a
button or a command typed on purpose.

Three rules hold for the applying, whenever it is asked for:

* **Fast-forward only.**  A merge is never attempted and a rebase never
  considered.  If history has diverged, ELMER says so and stops.
* **No update over local edits.**  Changes to tracked files are somebody's
  work in progress; an update that discards them is a bug, not a feature.  On
  the machine ELMER is actually written on, this is what keeps the updater
  quiet.  Untracked files are left out of that judgement on purpose: they are
  nobody's business but their owner's, and git will refuse on its own if an
  incoming commit would land on one.
* **Never prompt.**  The check runs on a background thread where a credential
  prompt would hang forever, so git is run with prompting disabled and ssh in
  batch mode.  A repository that cannot be read anonymously simply reports
  that it could not be reached.

Public repositories are readable over HTTPS with no credentials at all, so when
`origin` is an SSH URL - the way the machine that pushes is set up - the check
falls back to the HTTPS form of the same repository.  A Pi that only ever
consumes updates needs no key, no token and no account.

A schema change still needs a migration written for it - see
:func:`elmer.db.migrate` - but since an update only ever lands when somebody
asks for it, a missing one is a bad afternoon rather than six Pis at once.
"""
import fcntl
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "update.json"

# ELMER looks once at startup and then about once a day, which is as often as
# a study appliance has any reason to care.  The cached answer is what the
# dashboard reads, so opening it never waits on the network.
CHECK_EVERY = 24 * 3600
FIRST_CHECK_DELAY = 8           # let the server finish starting first

# What an install does about updates.  There is no "apply it for me": looking
# is the only thing ELMER does on its own.
POLICIES = ("notify", "off")
DEFAULT_POLICY = "notify"

TIMEOUT = 30

# git@host:owner/repo.git and ssh://git@host/owner/repo.git alike.
_SSH_URL = re.compile(r"^(?:ssh://)?git@([^:/]+)[:/](.+?)(?:\.git)?/?$")


def _env():
    """An environment where git can only fail, never stop and ask.

    The check runs unattended on a background thread.  A credential prompt or
    an ssh host-key question there does not produce a dialogue anybody can
    answer - it produces a thread that never returns.
    """
    return {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "echo",
        "SSH_ASKPASS": "echo",
        "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o ConnectTimeout=10",
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def _git(*args, timeout=TIMEOUT):
    """Run git in the install directory.  Returns (ok, output)."""
    try:
        done = subprocess.run(("git",) + args, cwd=ROOT, env=_env(),
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"git {args[0]} timed out after {timeout}s"
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    out = (done.stdout or "") + (done.stderr or "")
    return done.returncode == 0, out.strip()


def https_url(url):
    """The anonymous HTTPS form of a remote URL, or None if there is not one."""
    match = _SSH_URL.match(url or "")
    if match:
        return f"https://{match.group(1)}/{match.group(2)}.git"
    if (url or "").startswith("https://"):
        return url
    return None


def is_checkout():
    """True if this install is a git working copy we can update."""
    return (ROOT / ".git").exists() and _git("rev-parse", "--git-dir")[0]


def state():
    """What this install is, right now, without touching the network."""
    if not is_checkout():
        return {"checkout": False, "branch": None, "head": None, "subject": None,
                "date": None, "dirty": False, "remote": None}
    _, branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    _, head = _git("rev-parse", "--short", "HEAD")
    _, subject = _git("log", "-1", "--format=%s")
    _, when = _git("log", "-1", "--format=%cs")
    # Tracked changes only.  A note somebody dropped in the directory, or a
    # PDF the station tools wrote there, is not a reason to stop updating for
    # ever - and if an incoming commit really would land on top of an untracked
    # file, git refuses that by itself and says which file.
    ok, porcelain = _git("status", "--porcelain", "--untracked-files=no")
    _, remote = _git("remote", "get-url", "origin")
    return {
        "checkout": True,
        "branch": None if branch == "HEAD" else branch,   # None means detached
        "head": head,
        "subject": subject,
        "date": when,
        "dirty": bool(ok and porcelain),
        "remote": remote or None,
    }


def _fetch(branch):
    """Fetch `branch` into FETCH_HEAD.  Returns (ok, error).

    Tried in the order that needs the least: the configured remote first, then
    the anonymous HTTPS form of it, which is what lets a Pi with no key stay
    current with a repository the developing machine pushes to over ssh.
    """
    _, origin = _git("remote", "get-url", "origin")
    attempts, seen = [], set()
    for candidate in ("origin" if origin else None, https_url(origin)):
        if candidate and candidate not in seen:
            seen.add(candidate)
            attempts.append(candidate)
    if not attempts:
        return False, "no origin remote is configured"

    last = "could not reach the repository"
    for where in attempts:
        ok, out = _git("fetch", "--quiet", where, branch)
        if ok:
            return True, None
        last = out or last
        log.debug("update: fetch from %s failed - %s", where, out)
    return False, last.splitlines()[-1] if last else "fetch failed"


def _commits(rev_range, limit=25):
    """The commits in a range, newest first, as {short, subject} pairs."""
    ok, out = _git("log", f"-{limit}", "--format=%h\x1f%s", rev_range)
    if not ok or not out:
        return []
    rows = []
    for line in out.splitlines():
        short, _, subject = line.partition("\x1f")
        rows.append({"short": short, "subject": subject})
    return rows


def cached():
    """The last check's answer, or None.  Never touches the network."""
    try:
        return json.loads(CACHE.read_text())
    except (OSError, ValueError):
        return None


def _cache(result):
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(result, indent=2))
    except OSError as exc:
        log.debug("update: could not write %s (%s)", CACHE, exc)
    return result


def check(max_age=0):
    """Ask the repository whether this install has fallen behind.

    `max_age` in seconds returns the cached answer if it is younger than that,
    so the dashboard can ask on every load without a fetch on every load.
    """
    if max_age:
        was = cached()
        if was and time.time() - was.get("checked_at", 0) < max_age:
            return was

    st = state()
    result = dict(st, checked_at=time.time(), behind=0, ahead=0,
                  commits=[], error=None)
    if not st["checkout"]:
        result["error"] = ("this install is not a git checkout, so there is "
                           "nothing to update from")
        return _cache(result)
    if not st["branch"]:
        result["error"] = ("this checkout is not on a branch, so ELMER will "
                           "not move it")
        return _cache(result)

    ok, error = _fetch(st["branch"])
    if not ok:
        result["error"] = error
        return _cache(result)

    _, behind = _git("rev-list", "--count", "HEAD..FETCH_HEAD")
    _, ahead = _git("rev-list", "--count", "FETCH_HEAD..HEAD")
    result["behind"] = int(behind) if behind.isdigit() else 0
    result["ahead"] = int(ahead) if ahead.isdigit() else 0
    result["commits"] = _commits("HEAD..FETCH_HEAD")
    log.info("update check: %s behind, %s ahead%s", result["behind"],
             result["ahead"], " (local changes)" if st["dirty"] else "")
    return _cache(result)


def blocked(status=None):
    """Why an update cannot be applied right now, or None if it can."""
    status = status or cached() or {}
    st = state()
    if not st["checkout"]:
        return "this install is not a git checkout"
    if not st["branch"]:
        return "this checkout is not on a branch"
    if st["dirty"]:
        return ("there are local changes here - commit or put them aside "
                "first, and ELMER will leave them alone until you do")
    if status.get("ahead"):
        return (f"this install is {status['ahead']} commit(s) ahead of the "
                "repository, so history has diverged")
    return None


def apply():
    """Fast-forward the install.  Returns (ok, message, detail dict)."""
    status = check()
    if status.get("error"):
        return False, status["error"], status
    why = blocked(status)
    if why:
        return False, why, status
    if not status["behind"]:
        return True, "already up to date", status

    before = status["head"]
    ok, out = _git("merge", "--ff-only", "FETCH_HEAD")
    if not ok:
        log.warning("update: fast-forward refused - %s", out)
        return False, out.splitlines()[-1] if out else "git refused to update", status

    after = state()
    _, changed = _git("diff", "--name-only", f"{before}..HEAD")
    files = changed.splitlines() if changed else []
    detail = {
        "from": before, "to": after["head"], "subject": after["subject"],
        "commits": status["commits"], "files": len(files),
        # A dependency or installer change is the one thing a restart alone
        # will not put right, so it is said out loud rather than discovered
        # as a traceback later.
        "rerun_install": any(f in ("requirements.txt", "install.sh") for f in files),
    }
    _cache(dict(after, checked_at=time.time(), behind=0, ahead=0,
                commits=[], error=None))
    log.info("updated %s -> %s (%d files)", before, after["head"], len(files))
    return True, f"updated to {after['head']}", detail


def adopt(remote=None, branch="main"):
    """Turn a plain copy of ELMER into a checkout of the repository.

    A directory that was copied rather than cloned has no way to update.  This
    gives it one without overwriting a single file: the history is fetched
    alongside, HEAD is pointed at it, and whatever differs locally is left in
    the working tree as ordinary uncommitted changes for somebody to look at.
    """
    if is_checkout():
        return False, "this install is already a git checkout"
    remote = remote or "https://github.com/skpeterson2000/elmer.git"
    for args in (("init", "--quiet"),
                 ("remote", "add", "origin", remote),
                 ("fetch", "--quiet", "origin", branch)):
        ok, out = _git(*args, timeout=180)
        if not ok:
            return False, out or f"git {args[0]} failed"
    ok, out = _git("checkout", "-B", branch, "--no-track", "FETCH_HEAD", "--")
    if not ok:                       # never with force: files here come first
        ok, out = _git("reset", "--mixed", "FETCH_HEAD")
        if not ok:
            return False, out or "could not point this copy at the repository"
    st = state()
    return True, (f"adopted at {st['head']}"
                  + (" - `git status` shows what differs locally"
                     if st["dirty"] else "")), st


# --------------------------------------------------------------------------
# policy, kept with the rest of the profile settings
# --------------------------------------------------------------------------

def policy(conn):
    """Whether this install looks for updates at all: notify or off.

    Kept against the unit rather than against a person: which software the
    machine in the shack runs is not something that should change because
    somebody else picked their own name in the top bar.

    An install set to the old "apply automatically" reads as "notify" from
    here on, because that setting no longer exists - looking is the only thing
    ELMER does on its own now.
    """
    from . import db
    value = db.unit_get(conn, "updates")
    if value is None:                  # from before ELMER could be shared
        value = db.get_profile(conn)["settings"].get("updates")
    return value if value in POLICIES else DEFAULT_POLICY


def set_policy(conn, value):
    from . import db
    if value not in POLICIES:
        raise ValueError(f"unknown update policy: {value}")
    db.unit_set(conn, "updates", value)
    log.info("update policy set to %s", value)
    return value


# --------------------------------------------------------------------------
# restarting onto the new code
# --------------------------------------------------------------------------

RESTART_ENV = "ELMER_KIOSK_PID"     # the browser the new process should adopt
RESTART_FLAG = "ELMER_RESTARTED"    # tells the new process why it is starting


def _seal_fds():
    """Stop this process's open files from following it into the next one.

    Werkzeug marks its listening socket inheritable so that a reloader child
    can take it over.  Left that way it survives an exec as well, and the new
    ELMER then waits for a port that it is itself holding open without knowing
    it - a restart that hangs and never serves again.  Everything above stdin,
    stdout and stderr is therefore marked close-on-exec first.
    """
    try:
        fds = [int(name) for name in os.listdir("/proc/self/fd")]
    except (OSError, ValueError):
        os.closerange(3, 4096)
        return
    for fd in fds:
        if fd < 3:                       # the console is meant to carry over
            continue
        try:
            flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
        except OSError:
            pass


def exec_restart(kiosk_pid=None):
    """Replace this process with a fresh one on the updated code.

    os.execv keeps the process id and its children, so a kiosk browser started
    before the update is still there afterwards and is handed over by pid
    rather than being closed and reopened.  The screen never goes blank; the
    page reconnects on its own once the server is listening again.
    """
    environment = dict(os.environ)
    # The port is still being let go as this process is replaced, so the new
    # one has to know it is a restart: it waits for its own socket instead of
    # deciding that another ELMER got there first and standing aside.
    environment[RESTART_FLAG] = "1"
    if kiosk_pid:
        environment[RESTART_ENV] = str(kiosk_pid)
    else:
        environment.pop(RESTART_ENV, None)
    script = str(ROOT / "elmer.py")
    log.info("restarting on the updated code")
    sys.stdout.flush()
    sys.stderr.flush()
    _seal_fds()
    os.execve(sys.executable, [sys.executable, script] + sys.argv[1:], environment)


# --------------------------------------------------------------------------
# the background check
# --------------------------------------------------------------------------

def announce(status):
    """One line about a waiting update, or None.  Never changes anything."""
    if not status or not status.get("behind"):
        return None
    n = status["behind"]
    newest = (status.get("commits") or [{}])[0].get("subject", "")
    line = (f"An ELMER update is waiting: {n} commit{'' if n == 1 else 's'}"
            + (f", latest \"{newest}\"" if newest else ""))
    why = blocked(status)
    return line + (f"\n  It cannot be applied as things stand: {why}" if why
                   else "\n  Apply it from the dashboard, or with "
                        "./elmer.py --update, whenever it suits you.")


def watch(get_policy, interval=CHECK_EVERY, delay=FIRST_CHECK_DELAY,
          on_found=None):
    """Look for updates in the background for as long as ELMER runs.

    Looking is all it does.  What turns up is written to the cache for the
    dashboard to show and handed to `on_found` to say out loud - applying it
    is somebody's decision, made later, in their own time.

    `get_policy` is called each time round, so turning the check off in the
    dashboard takes effect without a restart.
    """
    import threading

    def run():
        first = True
        while True:
            time.sleep(delay if first else interval)
            first = False
            try:
                if get_policy() == "off":
                    continue
            except Exception:                     # a closed database, say
                continue
            try:
                status = check()
            except Exception as exc:              # never take the server down
                log.debug("update check failed: %s", exc)
                continue
            said = announce(status)
            if said:
                log.info(said.replace("\n  ", " - "))
                if on_found:
                    on_found(said)

    thread = threading.Thread(target=run, name="update-watch", daemon=True)
    thread.start()
    return thread
