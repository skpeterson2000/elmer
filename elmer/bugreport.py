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

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "elmer.log"

# Where to send one. Left empty on purpose: an address baked into a public
# repository is an address that gets scraped, and it is not this file's place
# to decide whose inbox fills up. Set it, or leave it and ELMER simply says
# where the file is.
CONTACT = ""

RE_GRID = re.compile(r"\b([A-R]{2}[0-9]{2})[a-x]{2}\b")
RE_LATLON = re.compile(r"-?\b\d{1,3}\.\d{4,}\b")
RE_PRIVATE_IP = re.compile(
    r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b")
RE_CALL = re.compile(r"\b[AKNW][A-Z]?\d[A-Z]{1,3}\b")
# An account name is often somebody's actual name, and a log is full of paths.
# /home/jsmith/ELMER/data/elmer.log says more about a person than the grid
# square that was so carefully cut down two lines above it.
RE_HOME = re.compile(r"(/home/|/Users/|\\Users\\)[^/\\ \t\n\"',;:)\]]+")


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


def build(conn=None, lines=400, include_station=False):
    """The report, as text, ready to be read before it is sent."""
    stamp = build_stamp()
    out = []
    add = out.append

    add("ELMER problem report")
    add("=" * 60)
    add(f"written    {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    add(f"build      {stamp['commit']} on {stamp['branch']}, dated {stamp['dated']}")
    if stamp["subject"]:
        add(f"           \"{stamp['subject']}\"")
    if not stamp["checkout"]:
        add("           (a downloaded copy, so there is no commit to name)")
    if stamp["modified"]:
        add("           NOTE: tracked files differ from the repository")
    add(f"python     {platform.python_version()}")
    add(f"system     {platform.system()} {platform.release()} {platform.machine()}")
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
                       ("nifog", ROOT / "data" / "nifog")):
        add(f"{name:10s} {'present' if path.exists() else 'absent'}")

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


def write(conn=None, lines=400, include_station=False):
    """Save the report where somebody can find it. Returns (path, redacted)."""
    text, redacted = build(conn, lines, include_station)
    folder = ROOT / "data"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("elmer-report-%Y%m%d-%H%M%S.txt")
    path.write_text(text)
    return path, redacted, text
