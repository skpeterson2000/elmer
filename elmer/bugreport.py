"""One file somebody can send when ELMER misbehaves, with nothing in it they
did not agree to send.

A log is only useful to whoever reads it if it says which build it came from,
what the machine is, and what happened just before the trouble. It is only
*sendable* if the person sending it can see what is in it first. Those two
pull in opposite directions, so this does both jobs deliberately: it gathers
the diagnosis, and it takes out the things that identify a station unless the
operator says otherwise.

What comes out by default: the callsign, the last two characters of the grid
square, any coordinates, and the addresses of machines on the home network.
What stays: versions, timings, error text, tracebacks, and the sequence of
requests - which is the part that actually finds a fault.

The station is told exactly what was removed. Nobody should have to take a
program's word for what it is about to send on their behalf.
"""
import platform
import re
import time
from pathlib import Path
from . import paths

ROOT = Path(__file__).resolve().parents[1]
LOG = paths.STATE / "elmer.log"

# Where to send one: KC9SP's arrl.net forwarder, chosen by him for exactly
# this - it forwards to his inbox and is filtered on the way. The address
# and the sending path live in mail.py; this is the name the report page
# shows beside the file it wrote.
from .mail import CONTACT  # noqa: E402

RE_GRID = re.compile(r"\b([A-R]{2}[0-9]{2})[a-x]{2}\b")
RE_LATLON = re.compile(r"-?\b\d{1,3}\.\d{4,}\b")
RE_PRIVATE_IP = re.compile(
    r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b")
RE_CALL = re.compile(r"\b[AKNW][A-Z]?\d[A-Z]{1,3}\b")
# An account name is often somebody's actual name, and a log is full of paths.
# /home/jsmith/ELMER/data/elmer.log says more about a person than the grid
# square that was so carefully cut down two lines above it.
RE_HOME = re.compile(r"(/home/|/Users/|\\Users\\)[^/\\ \t\n\"',;:)\]]+")
# A service token - RepeaterBook's begin rbuapp_ - is a password by another
# name. Nothing here logs one, and this makes sure of it anyway.
RE_TOKEN = re.compile(r"\b(?:rbuapp|app)_[A-Za-z0-9._-]{6,}")


def redact(text, callsign=None, places=()):
    """Take the station out of the log, leaving the fault in it."""
    if callsign:
        text = re.sub(re.escape(str(callsign)), "[callsign]", text,
                      flags=re.IGNORECASE)
    # The town ELMER named the QTH as is every bit as identifying as the grid
    # square it came from, and no pattern finds it - it is an ordinary string.
    # So the names this install actually holds are removed by name.
    for name in sorted({str(p) for p in places if p and len(str(p)) > 3},
                       key=len, reverse=True):
        text = re.sub(re.escape(name), "[place]", text, flags=re.IGNORECASE)
    text = RE_CALL.sub("[callsign]", text)
    # A four-character grid is a hundred kilometres across, which is enough to
    # say "this happens in the upper midwest" and not enough to say whose
    # driveway it is.
    text = RE_GRID.sub(r"\1xx", text)
    text = RE_LATLON.sub("[coord]", text)
    text = RE_PRIVATE_IP.sub("[lan-ip]", text)
    text = RE_HOME.sub(lambda m: m.group(1) + "[user]", text)
    text = RE_TOKEN.sub("[token]", text)
    return text


def build_stamp():
    """Which build this is - the first question anybody reading a log asks."""
    try:
        from . import update
        state = update.state()
    except Exception:
        state = {}
    return {
        "commit": state.get("head") or "unknown",
        "branch": state.get("branch") or "-",
        "dated": state.get("date") or "-",
        "subject": state.get("subject") or "",
        "modified": bool(state.get("dirty")),
        "checkout": bool(state.get("checkout")),
        # A portable build names the commit it was made from and when.
        "built": state.get("built") or "",
    }


def log_stamp(log):
    """Put the build in the log itself, so any log answers the question."""
    stamp = build_stamp()
    log.info("ELMER %s on %s (%s), python %s, %s %s",
             stamp["commit"], stamp["branch"], stamp["dated"],
             platform.python_version(), platform.system(), platform.machine())
    if stamp["modified"]:
        log.info("this install has local changes to tracked files")


def _tail(path, lines):
    try:
        text = path.read_text(errors="replace").splitlines()
    except OSError:
        return []
    return text[-lines:]


# What the operator typed is the one thing the log cannot say. It is kept
# to a few paragraphs and put first, because whoever reads the report wants
# "the band plan tab went blank when I pressed print" before the load average.
SAID_MOST = 2000


def headline(said):
    """The first line of what was said, short enough for a subject."""
    for line in str(said or "").splitlines():
        line = " ".join(line.split())
        if line:
            return line if len(line) <= 60 else line[:57].rstrip() + "..."
    return ""


def build(conn=None, lines=400, include_station=False, said=""):
    """The report, as text, ready to be read before it is sent.

    `said` is the operator's own account of what happened, if they gave
    one. `include_station` puts the callsign on the report and leaves the
    text unredacted - their choice, made so a reply can reach them; without
    it nothing on the report says whose it is, the operator's words
    included, since a callsign typed into them is still a callsign.
    """
    stamp = build_stamp()
    out = []
    add = out.append

    add("ELMER problem report")
    add("=" * 60)
    add(f"written    {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    if include_station and conn is not None:
        try:
            from . import db
            call = (db.get_profile(conn).get("callsign") or "").strip().upper()
        except Exception:
            call = ""
        add(f"from       {call or '(no callsign on this unit)'} - included so a reply can reach them")
    add(f"build      {stamp['commit']} on {stamp['branch']}, dated {stamp['dated']}")
    if stamp["subject"]:
        add(f"           \"{stamp['subject']}\"")
    if not stamp["checkout"] and stamp["built"]:
        add(f"           (a portable build, made {stamp['built']})")
    elif not stamp["checkout"]:
        add("           (a downloaded copy, so there is no commit to name)")
    if stamp["modified"]:
        add("           NOTE: tracked files differ from the repository")
    add(f"python     {platform.python_version()}")
    add(f"system     {platform.system()} {platform.release()} {platform.machine()}")
    try:
        from .diagnostics import host_load, load_words
        words = load_words(host_load())
        if words:
            add(f"load       {words}")
    except Exception:
        pass
    try:
        from . import op25
        procs = op25.running()
        if procs:
            add(f"op25       running ({len(procs)} process) - a heavy neighbour "
                "on this Pi")
    except Exception:
        pass
    try:
        import flask
        add(f"flask      {flask.__version__}")
    except Exception:
        add("flask      not importable")

    # What this install has, without naming anybody.
    if conn is not None:
        try:
            from . import db
            add(f"schema     {conn.execute('PRAGMA user_version').fetchone()[0]}")
            people = conn.execute("SELECT COUNT(*) c FROM profile").fetchone()["c"]
            answers = conn.execute("SELECT COUNT(*) c FROM answer_log").fetchone()["c"]
            add(f"install    {people} profile(s), {answers} answers logged")
        except Exception as exc:
            add(f"install    could not be read ({type(exc).__name__})")

    try:
        from .diagnostics import install_location
        where = install_location()
        add(f"location   {where['kind']}, "
            + ("writable" if where["writable"] else "NOT WRITABLE"))
        for concern in where["concerns"]:
            add(f"           WARNING: {concern}")
    except Exception:
        add("location   could not be determined")

    for name, path in (("repeaters", ROOT / "data" / "repeaters.json"),
                       ("places", ROOT / "data" / "places.json"),
                       ("nifog", paths.STATE / "nifog")):
        add(f"{name:10s} {'present' if path.exists() else 'absent'}")

    said = str(said or "").strip()[:SAID_MOST]
    if said:
        add("")
        add("what happened, in the operator's words")
        add("-" * 60)
        out.extend(said.splitlines())

    callsign, places = None, []
    if conn is not None and not include_station:
        try:
            from . import db
            profile = db.get_profile(conn)
            callsign = profile["callsign"]
            spot = profile["settings"].get("location") or {}
            places = [spot.get("short"), spot.get("name"), spot.get("grid")]
        except Exception:
            callsign, places = None, []

    # The self-check, embedded. A report that made somebody read four hundred
    # log lines to find what one line of the doctor already knew was a report
    # that buried its own answer. The doctor speaks in plain sentences and
    # knows the things the log does not say out loud - a hall collapsed to one
    # table, a mail send refused, a bridge offline - so it goes at the top.
    add("")
    add("self-check")
    add("-" * 60)
    try:
        from . import diagnostics
        results = diagnostics.collect()
        worst = {"FAIL": 0, "warn": 0, "ok": 0}
        for c in results:
            worst[c["state"]] = worst.get(c["state"], 0) + 1
            mark = {"FAIL": "FAIL", "warn": "warn", "ok": " ok "}.get(c["state"], c["state"])
            add(f"  [{mark}] {c['label']}: {c['detail']}")
        add(f"  -> {worst.get('FAIL', 0)} failing, {worst.get('warn', 0)} warnings, "
            f"{worst.get('ok', 0)} ok")
    except Exception as exc:
        add(f"  (self-check could not run: {type(exc).__name__}: {exc})")

    # The last time this unit tried to mail anything, and how it went - the
    # one fact a report about mail failing most needs, and the one that used
    # to scroll out of the log tail before anyone read it.
    try:
        from . import mail
        last = mail.last_result()
        if last:
            import datetime
            when = datetime.datetime.fromtimestamp(last.get("at", 0)).strftime("%Y-%m-%d %H:%M")
            add("")
            add(f"last send{' (by the drop)' if last.get('via') == 'drop' else ''}: "
                f"{'sent' if last.get('ok') else 'FAILED'} at {when} - "
                f"{last.get('detail', '')}")
    except Exception:
        pass

    body = _tail(LOG, lines)
    errors = [ln for ln in body if " ERROR " in ln or "UNHANDLED" in ln
              or " WARNING " in ln]

    add("")
    add(f"errors and warnings in the last {len(body)} log lines: {len(errors)}")
    add("-" * 60)
    out.extend(errors[-40:] or ["  (none)"])
    add("")
    add(f"last {len(body)} log lines")
    add("-" * 60)
    out.extend(body)

    text = "\n".join(out) + "\n"
    if include_station:
        return text, False
    return redact(text, callsign, places), True


# The name a report file has, and the only names the page may ask for by
# name: what this module writes and what fieldreport.py writes, nothing else
# - the route that serves one is the line between a browser and the disk.
RE_NAME = re.compile(r"(elmer|field)-report-\d{8}-\d{6}\.txt")


def locate(name):
    """The file for a report name, or None if it is not one of ours."""
    if not RE_NAME.fullmatch(str(name or "")):
        return None
    folder = paths.STATE / "reports" if name.startswith("field") else paths.STATE
    path = folder / name
    return path if path.is_file() else None


def write(conn=None, lines=400, include_station=False, said=""):
    """Save the report where somebody can find it. Returns (path, redacted)."""
    text, redacted = build(conn, lines, include_station, said)
    # Beside the log it was cut from: the state directory, which is data/
    # on a unit and somewhere else only when a test moved it.
    folder = paths.STATE
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("elmer-report-%Y%m%d-%H%M%S.txt")
    path.write_text(text)
    return path, redacted, text
