"""The FCC's own licence records, read from the files the FCC publishes.

The Commission's lookup API is gone, but the Universal Licensing System still
puts the whole database on a public shelf every Sunday, one zip per radio
service, for anyone who will go and get it: `l_amat.zip` for the amateur
service, `l_gmrs.zip` for GMRS, `l_frc.zip` for the commercial operator
licences - the GROL, the MROP, the GMDSS tickets, the Ship Radar endorsement.
That is the source. A site that answers a callsign is reading these files;
ELMER reads them too, and then answers callsigns with no network at all.

Each zip holds pipe-delimited tables from the ULS public-access schema. Only
three are read, and only a few fields of each: HD (the licence header - the
callsign, its status, the grant and expiry dates), AM or FA (the operator
class), and EN (the licensee, from which the FRN is kept and the name and
address are not - same rule as the amateur lookup has always had). The rows
go into a SQLite table on the unit; a lookup is one indexed read.

A file is fetched when a licence of its service is first asked about, and
again only when the FCC has posted a newer one - checked by asking for the
file's date, not by downloading it. The amateur file is two hundred
megabytes, so a unit that only ever meets amateur calls fetches only that,
and a unit that never meets a GMRS call never fetches the GMRS file.
"""
import logging
import os
import re
import sqlite3
import threading
import time
import urllib.request
import zipfile
from datetime import datetime
from email.utils import parsedate_to_datetime

from . import paths

log = logging.getLogger("elmer")

BASE = "https://data.fcc.gov/download/pub/uls/complete/"
DIR = paths.STATE / "uls"
DB = DIR / "uls.sqlite"
USER_AGENT = "ELMER/1.0 (+https://github.com/skpeterson2000/elmer; KC9SP@arrl.net)"
TIMEOUT = 60                           # per read, not for the whole file
CHECK_EVERY = 6 * 3600                 # how often the FCC is asked whether a file is newer

SERVICES = {
    "amateur":    {"file": "l_amat.zip", "class_table": "AM", "label": "amateur",
                   "grace_days": 730},          # 47 CFR 97.21(b): two years to renew without a retest
    "gmrs":       {"file": "l_gmrs.zip", "class_table": None, "label": "GMRS",
                   "grace_days": 0},            # Part 95: none
    "commercial": {"file": "l_frc.zip", "class_table": "FA", "label": "commercial operator",
                   "grace_days": 0},
}

# The shape of a call says its service, with no lookup at all.
RE_AMATEUR = re.compile(r"^[AKNW][A-Z]?\d[A-Z]{1,3}$")
RE_GMRS = re.compile(r"^(W[QR][A-Z]{2}\d{3}|K[A-Z]{2}\d{4})$")
RE_COMMERCIAL = re.compile(r"^(PG|MP|DO|DB|DM|RR|RL|T[12]?)[A-Z]{0,2}\d{5,10}$")

# AM.dat operator class letters; FA.dat operator class codes.
AMATEUR_CLASS = {"N": "Novice", "T": "Technician", "P": "Technician", "G": "General",
                 "A": "Advanced", "E": "Extra"}
COMMERCIAL_CLASS = {"PG": "General Radiotelephone Operator License",
                    "MP": "Marine Radio Operator Permit",
                    "RR": "Restricted Radiotelephone Operator Permit",
                    "RL": "Restricted Radiotelephone Operator Permit - Limited Use",
                    "DO": "GMDSS Radio Operator's License",
                    "DB": "GMDSS Radio Operator/Maintainer License",
                    "DM": "GMDSS Radio Maintainer's License",
                    "T1": "First Class Radiotelegraph Operator's Certificate",
                    "T2": "Second Class Radiotelegraph Operator's Certificate",
                    "T": "Third Class Radiotelegraph Operator's Certificate"}
STATUS = {"A": "active", "E": "expired", "C": "cancelled", "T": "terminated", "L": "pending"}

_fetching = {}                         # service -> thread, while a fetch runs
_checked = {}                          # service -> when the FCC was last asked for the date
_lock = threading.Lock()


def service_of(call):
    call = (call or "").upper()
    if RE_GMRS.match(call):
        return "gmrs"
    if RE_AMATEUR.match(call):
        return "amateur"
    if RE_COMMERCIAL.match(call):
        return "commercial"
    return None


def _connect():
    DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB), timeout=30)
    conn.execute("""CREATE TABLE IF NOT EXISTS licence (
        service TEXT NOT NULL, call TEXT NOT NULL, status TEXT, code TEXT,
        granted TEXT, expires TEXT, cancelled TEXT, klass TEXT, radar TEXT, frn TEXT,
        city TEXT, state TEXT, zip TEXT,
        PRIMARY KEY (service, call))""")
    conn.execute("CREATE INDEX IF NOT EXISTS licence_frn ON licence (frn)")
    conn.execute("""CREATE TABLE IF NOT EXISTS files (
        service TEXT PRIMARY KEY, fetched REAL, dated TEXT, rows INTEGER)""")
    return conn


def have(service):
    """When this service's file was read, and how many rows - or None."""
    if not DB.is_file():
        return None
    with _connect() as conn:
        row = conn.execute("SELECT fetched, dated, rows FROM files WHERE service = ?", (service,)).fetchone()
    return {"fetched": row[0], "dated": row[1], "rows": row[2]} if row else None


def _fields(line):
    return line.decode("latin-1").rstrip("\r\n").split("|")


def build(service, zip_path):
    """Read the tables ELMER needs out of a ULS zip into the index. The old
    rows for the service go only once the new ones are all in."""
    spec = SERVICES[service]
    started = time.time()
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        with _connect() as conn:
            conn.execute("DROP TABLE IF EXISTS fresh")
            conn.execute("""CREATE TEMP TABLE fresh (
                call TEXT PRIMARY KEY, status TEXT, code TEXT, granted TEXT, expires TEXT,
                cancelled TEXT, klass TEXT, radar TEXT, frn TEXT, city TEXT, state TEXT, zip TEXT)""")
            batch = []
            for line in z.open("HD.dat"):
                f = _fields(line)
                if len(f) < 10 or not f[4]:
                    continue
                batch.append((f[4].upper(), f[5], f[6], f[7], f[8], f[9]))
                if len(batch) >= 5000:
                    conn.executemany("INSERT OR REPLACE INTO fresh (call, status, code, granted, expires, cancelled) VALUES (?,?,?,?,?,?)", batch)
                    batch = []
            if batch:
                conn.executemany("INSERT OR REPLACE INTO fresh (call, status, code, granted, expires, cancelled) VALUES (?,?,?,?,?,?)", batch)
            table = spec["class_table"]
            if table and f"{table}.dat" in names:
                batch = []
                for line in z.open(f"{table}.dat"):
                    f = _fields(line)
                    if len(f) < 7 or not f[4]:
                        continue
                    batch.append((f[5].strip(), (f[6].strip() if table == "FA" else ""), f[4].upper()))
                    if len(batch) >= 5000:
                        conn.executemany("UPDATE fresh SET klass = ?, radar = ? WHERE call = ?", batch)
                        batch = []
                if batch:
                    conn.executemany("UPDATE fresh SET klass = ?, radar = ? WHERE call = ?", batch)
            if "EN.dat" in names:
                batch = []
                for line in z.open("EN.dat"):
                    f = _fields(line)
                    if len(f) < 23 or not f[4]:
                        continue
                    # The FRN and the town: the name and the street are on
                    # this row too, and are left on it.
                    batch.append((f[22].strip(), f[16].strip().title(), f[17].strip().upper(), f[18].strip()[:5], f[4].upper()))
                    if len(batch) >= 5000:
                        conn.executemany("UPDATE fresh SET frn = ?, city = ?, state = ?, zip = ? WHERE call = ?", batch)
                        batch = []
                if batch:
                    conn.executemany("UPDATE fresh SET frn = ?, city = ?, state = ?, zip = ? WHERE call = ?", batch)
            conn.execute("DELETE FROM licence WHERE service = ?", (service,))
            conn.execute("""INSERT INTO licence (service, call, status, code, granted, expires, cancelled, klass, radar, frn, city, state, zip)
                            SELECT ?, call, status, code, granted, expires, cancelled, klass, radar, frn, city, state, zip FROM fresh""", (service,))
            rows = conn.execute("SELECT COUNT(*) FROM fresh").fetchone()[0]
            conn.execute("DROP TABLE fresh")
            dated = datetime.fromtimestamp(zip_path.stat().st_mtime).date().isoformat()
            conn.execute("INSERT OR REPLACE INTO files (service, fetched, dated, rows) VALUES (?,?,?,?)",
                         (service, time.time(), dated, rows))
    with _connect() as conn:
        conn.execute("VACUUM")             # the replaced rows' space, given back
    log.info("uls: %s file read - %d licences in %.0f s", spec["label"], rows, time.time() - started)
    return rows


def _remote_date(service):
    """When the FCC last posted this service's file - a HEAD, not a download."""
    request = urllib.request.Request(BASE + SERVICES[service]["file"], method="HEAD",
                                     headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        stamp = response.headers.get("Last-Modified")
        size = response.headers.get("Content-Length")
    when = parsedate_to_datetime(stamp) if stamp else None
    return when, int(size or 0)


def fetch(service):
    """Download this service's file and read it in. Returns (ok, message)."""
    spec = SERVICES[service]
    DIR.mkdir(parents=True, exist_ok=True)
    target = DIR / spec["file"]
    part = target.with_suffix(".part")
    request = urllib.request.Request(BASE + spec["file"], headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response, part.open("wb") as out:
            stamp = response.headers.get("Last-Modified")
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        part.replace(target)
        if stamp:
            when = parsedate_to_datetime(stamp).timestamp()
            os.utime(target, (when, when))
        rows = build(service, target)
    except Exception as exc:
        part.unlink(missing_ok=True)
        log.warning("uls: %s file could not be fetched or read: %s", spec["label"], exc)
        return False, f"the FCC's {spec['label']} file could not be fetched ({exc.__class__.__name__})"
    try:
        target.unlink()                # the index is what is kept; the zip is not
    except OSError:
        pass
    return True, f"{rows} {spec['label']} licences read from the FCC's file"


def fetching(service):
    t = _fetching.get(service)
    return bool(t and t.is_alive())


def ensure(service, force=False):
    """Have this service's file, fetching it in the background if it is
    missing or the FCC has posted a newer one. Returns what is happening."""
    if service not in SERVICES:
        return "unknown service"
    # ELMER_ULS=off: never fetch by itself - a metered connection, or a
    # bench. Lookups then answer from whatever files are already here.
    if os.environ.get("ELMER_ULS", "").lower() in ("off", "0", "no") and not force:
        return "off"
    with _lock:
        if fetching(service):
            return "fetching"
        here = have(service)
        want = force or here is None
        if not want and time.time() - _checked.get(service, 0) > CHECK_EVERY:
            _checked[service] = time.time()
            try:
                when, _ = _remote_date(service)
                want = bool(when) and when.date().isoformat() > (here["dated"] or "")
            except Exception as exc:
                log.debug("uls: could not ask the FCC for the %s file's date: %s", service, exc)
        if not want:
            return "current"

        def run():
            ok, message = fetch(service)
            (log.info if ok else log.warning)("uls: %s", message)
        t = threading.Thread(target=run, name=f"uls-{service}", daemon=True)
        _fetching[service] = t
        t.start()
        return "fetching"


def _date(text):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text or "", fmt).date()
        except ValueError:
            continue
    return None


def lookup(call):
    """The FCC's record for a callsign, from the index - or None when the
    service's file has not been read yet (in which case it is asked for)."""
    call = (call or "").upper().strip()
    service = service_of(call)
    if not service:
        return None
    state = ensure(service)
    here = have(service)
    if here is None:
        return {"callsign": call, "found": False, "service": service, "pending": state == "fetching",
                "reason": (f"the FCC's {SERVICES[service]['label']} file is being fetched - look again in a few minutes"
                           if state == "fetching" else f"the FCC's {SERVICES[service]['label']} file is not on this unit yet")}
    with _connect() as conn:
        row = conn.execute("SELECT status, code, granted, expires, cancelled, klass, radar, frn, city, state, zip FROM licence WHERE service = ? AND call = ?",
                           (service, call)).fetchone()
        others = []
        if row and row[7]:
            others = [{"callsign": r[0], "service": r[1], "status": STATUS.get(r[2], r[2]), "class": _class(r[1], r[3], r[4])}
                      for r in conn.execute("SELECT call, service, status, klass, radar FROM licence WHERE frn = ? AND NOT (service = ? AND call = ?)",
                                            (row[7], service, call))]
    source = f"FCC ULS, the {SERVICES[service]['label']} file of {here['dated']}"
    if row is None:
        return {"callsign": call, "found": False, "service": service, "source": source,
                "reason": f"no FCC {SERVICES[service]['label']} record for this callsign"}
    status, code, granted, expires, cancelled, klass, radar, frn, city, state, zip_code = row
    from .callsign import status_for
    record = {
        "callsign": call, "found": status in ("A", "E"), "service": service,
        "type": "GMRS" if service == "gmrs" else ("COMMERCIAL" if service == "commercial" else "PERSON"),
        "fcc_status": STATUS.get(status, status),
        "license_class": _class(service, klass, radar),
        "class_code": klass or None, "radar": radar == "Y",
        "granted": granted or None, "expires": expires or None, "cancelled": cancelled or None,
        "frn": frn or None, "others": others,
        # The town on the record, for placing a far station; never the street.
        "place": f"{city}, {state}" if city and state else None, "zip": zip_code or None,
        "uls_url": "https://wireless2.fcc.gov/UlsApp/UlsSearch/searchLicense.jsp",
        "checked": datetime.now().date().isoformat(), "cached": False, "source": source,
    }
    if status in ("C", "T"):
        record["reason"] = f"the FCC record is {STATUS[status]}" + (f" as of {cancelled}" if cancelled else "")
    record["status"] = status_for(_date(expires), SERVICES[service]["grace_days"])
    if service == "commercial" and not expires and status == "A":
        record["status"] = {"state": "current", "days": None, "lifetime": True}   # a GROL is for life
    return record


def _class(service, klass, radar):
    if service == "amateur":
        return AMATEUR_CLASS.get((klass or "").upper())
    if service == "commercial":
        name = COMMERCIAL_CLASS.get((klass or "").upper())
        if name and radar == "Y":
            name += " with Ship Radar endorsement"
        return name
    return None


def by_frn(frn):
    """Every licence in the index under one FRN - the door the old API
    shut: a person's amateur, GMRS and commercial tickets together."""
    if not frn or not DB.is_file():
        return []
    with _connect() as conn:
        return [{"callsign": r[0], "service": r[1], "status": STATUS.get(r[2], r[2]),
                 "class": _class(r[1], r[3], r[4]), "expires": r[5]}
                for r in conn.execute("SELECT call, service, status, klass, radar, expires FROM licence WHERE frn = ?", (str(frn),))]


def watch():
    """Keep the files this unit has read current: every few hours, each
    service with an index is asked about, and refreshed when the FCC has
    posted a newer file. Services never asked about are never fetched."""
    def run():
        time.sleep(300)                    # let the unit come up first
        while True:
            for service in SERVICES:
                try:
                    if have(service):
                        ensure(service)
                except Exception as exc:
                    log.debug("uls watch: %s", exc)
            time.sleep(CHECK_EVERY)
    threading.Thread(target=run, name="uls-watch", daemon=True).start()


def state():
    """What is on the unit, for the doctor and the Station panel."""
    return {s: {"have": have(s), "fetching": fetching(s), "file": v["file"]} for s, v in SERVICES.items()}
