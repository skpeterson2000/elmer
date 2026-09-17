"""Self-checks for `./elmer.py --doctor`.

Written for the case where the app "won't open": it reports every address the
server can actually be reached on, proves the pools and database are usable,
and says plainly which part is at fault.
"""
import json
import os
import socket
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OK, WARN, BAD = "  ok  ", " warn ", " FAIL "

# A round trip longer than this is fine in a waiting room and dear in a game:
# at a 30-second round it is a fiftieth of the clock, gone before the question
# is read. The wifi, not the master, is what spends it.
RTT_SLOW_MS = 600.0
# Load per core above this and the machine is doing more than it has hands
# for: work queues, and everything it serves waits behind the queue. That is
# latency too, but hidden inside the process rather than out on the wire, so
# it wears the same face and is fixed a different way.
LOAD_HOT = 1.5


def host_load():
    """What this machine is carrying: cores, load, memory, heat, throttling.

    All from the kernel and the SoC, no dependency added. A Pi fed more than
    it can chew serves everything slowly, which reads as latency and is not
    the network; only this tells the two apart. Each signal is taken on its
    own, because a machine that cannot report its temperature can still
    report its load.
    """
    out = {}
    try:
        out["cores"] = os.cpu_count() or 1
        out["load1"], out["load5"], out["load15"] = os.getloadavg()
        out["per_core"] = round(out["load1"] / out["cores"], 2)
    except (OSError, AttributeError):
        pass
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            info[k] = int(v.strip().split()[0])   # kB
        total, avail = info.get("MemTotal"), info.get("MemAvailable")
        if total:
            out["mem_total_mb"] = round(total / 1024)
            out["mem_avail_mb"] = round((avail or 0) / 1024)
            out["mem_used_pct"] = round(100 * (1 - (avail or 0) / total))
    except (OSError, ValueError, KeyError):
        pass
    try:
        milli = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip())
        out["temp_c"] = round(milli / 1000.0, 1)
    except (OSError, ValueError):
        pass
    # The SoC's own word on whether it is throttling, and whether it has since
    # boot. Under-voltage is the classic Raspberry Pi mystery-slowness - a
    # thin power supply - and nothing else in the program would ever catch it.
    try:
        raw = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                             text=True, timeout=4).stdout.strip()
        val = int(raw.split("=", 1)[1], 16) if "=" in raw else 0
        out["throttled_now"] = bool(val & 0xF)
        out["undervolt_now"] = bool(val & 0x1)
        out["throttled_ever"] = bool(val & 0xF0000)
        out["undervolt_ever"] = bool(val & 0x10000)
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    return out


def load_words(h):
    """One line describing a host_load() dict, or '' if it is empty."""
    if not h:
        return ""
    bits = []
    if "per_core" in h:
        bits.append(f"load {h['load1']:.1f} on {h['cores']} cores "
                    f"({h['per_core']:.1f}/core)")
    if "mem_used_pct" in h:
        bits.append(f"memory {h['mem_used_pct']}% of {h['mem_total_mb']} MB")
    if "temp_c" in h:
        bits.append(f"{h['temp_c']:.0f}°C")
    if h.get("undervolt_now"):
        bits.append("UNDER-VOLTAGE now (check the power supply)")
    elif h.get("throttled_now"):
        bits.append("throttling now")
    elif h.get("undervolt_ever"):
        bits.append("under-voltage since boot")
    return "; ".join(bits)


def load_is_hot(h):
    """Whether a host_load() dict is a machine in trouble."""
    return bool(h and (h.get("per_core", 0) > LOAD_HOT
                       or h.get("mem_used_pct", 0) >= 92
                       or h.get("temp_c", 0) >= 80
                       or h.get("throttled_now") or h.get("undervolt_now")))


def check_load():
    """This machine's own load - the latency that hides inside the process."""
    h = host_load()
    words = load_words(h)
    if not words:
        return True                       # not a machine that can say
    _line(WARN if load_is_hot(h) else OK, "machine load", words
          + (" - it is fed more than it can serve; everything it does waits "
             "behind the queue" if load_is_hot(h) else ""))
    return True


# When a caller wants the results rather than the printout - the dashboard
# asking the same questions the terminal does - checks are collected here as
# they run. One set of checks, two ways of reading them: a self-check that only
# worked from a terminal was a self-check most operators never ran.
_collected = None


def _line(state, label, detail="", fix=None):
    """One finding. `fix` names a remedy in app.py's REMEDIES - the one thing
    a press on the local screen can do about this line - or is None: the
    doctor looks and changes nothing, and a fix is a separate press, so the
    person stays in charge and nothing here needs a terminal."""
    if _collected is not None:
        _collected.append({"state": state.strip(), "label": label,
                           "detail": detail, "fix": fix})
        return
    print(f"  [{state}] {label}" + (f"  -  {detail}" if detail else ""))


def collect(port=5000):
    """Run every check and return what they found, instead of printing it."""
    global _collected
    _collected = []
    try:
        for check in (check_pools, check_figures, check_explanations,
                      check_database, check_templates, check_tools, check_manual,
                      check_kiosk, check_launcher, check_updates,
                      check_location, check_gps, check_repeaters,
                      check_towerwitch_service, check_towerwitch_beside,
                      check_neighbours_known,
                      check_net_role, check_hall, check_node, check_mail,
                      check_load, check_op25, check_internet, check_start):
            try:
                check()
            except Exception as exc:
                _collected.append({"state": BAD.strip(), "label": check.__name__,
                                   "detail": f"{type(exc).__name__}: {exc}"})
        try:
            check_server(port)
        except Exception:
            pass
        return list(_collected)
    finally:
        _collected = None


def local_addresses():
    """Every IPv4 address this machine answers on, best guess first."""
    found = []
    try:
        out = subprocess.run(["ip", "-4", "-br", "addr"], capture_output=True,
                             text=True, timeout=5).stdout
        for row in out.splitlines():
            parts = row.split()
            if len(parts) >= 3 and parts[1] == "UP":
                for cidr in parts[2:]:
                    ip = cidr.split("/")[0]
                    if not ip.startswith("127."):
                        found.append((parts[0], ip))
    except (OSError, subprocess.SubprocessError):
        pass
    if not found:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                found.append(("default", s.getsockname()[0]))
        except OSError:
            pass
    return found


def port_in_use(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


# Places a program can sit and still run, right up until the day it cannot.
# None of these is blocked by the operating system - a script runs perfectly
# well from the wastebasket on Raspberry Pi OS, which is the problem: nothing
# stops you, and then one day the folder is emptied and the study data goes
# with it.
LOCATION_TRAPS = [
    ("trash", ("/.trash", "/.local/share/trash", "/recycle.bin", "/$recycle.bin"),
     "the wastebasket - emptying it deletes ELMER and every answer you have "
     "logged"),
    ("downloads", ("/downloads", "/download"),
     "the downloads folder - it gets tidied, and re-downloading the zip "
     "overwrites what is here"),
    ("temporary", ("/tmp/", "/var/tmp/", "/private/var/folders"),
     "temporary storage - the system clears this, often at reboot"),
    ("removable", ("/media/", "/mnt/", "/run/media", "/volumes/"),
     "removable storage - it works until the stick is pulled or fails to "
     "mount"),
]


def install_location(root=None):
    """What kind of place this copy is installed in, and whether that is wise.

    Deliberately reports the kind and not the path: which folder somebody
    keeps their radio software in is nobody's business, but whether that
    folder survives a reboot is everybody's.
    """
    root = Path(root or ROOT).resolve()
    lowered = str(root).lower().replace("\\", "/") + "/"
    concerns = []
    kind = "ordinary"
    for name, needles, why in LOCATION_TRAPS:
        if any(n in lowered for n in needles):
            kind = name
            concerns.append(why)
            break
    if kind == "ordinary" and str(root).startswith(str(Path.home())):
        kind = "home"

    # Test the nearest thing that actually exists: asking whether a directory
    # nobody has created yet is writable always answers no, which would report
    # a fault against every location that has not been installed to.
    probe = root / "data"
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    writable = os.access(probe, os.W_OK)
    if not writable:
        concerns.append("ELMER cannot write to its own data folder, so nothing "
                        "you do will be saved")
    return {"kind": kind, "writable": writable, "concerns": concerns,
            "ok": not concerns}


def check_location():
    """Where this copy lives, and whether that place will still exist later."""
    where = install_location()
    if where["ok"]:
        _line(OK, "install location", f"{where['kind']}, writable")
        return True
    _line(WARN, "install location", f"{where['kind']} storage")
    for concern in where["concerns"]:
        _line(WARN, "", concern)
    _line(WARN, "", "move the whole folder somewhere permanent - data/ comes "
                    "with it")
    return True


def check_pools():
    directory = ROOT / "data" / "pools"
    files = sorted(directory.glob("*.json"))
    if not files:
        _line(BAD, "question pools", "none built - run ./elmer.py --build")
        return False
    total, bad = 0, []
    for path in files:
        try:
            pool = json.loads(path.read_text())
            total += len(pool["questions"])
            missing = [q["figure"] for q in pool["questions"]
                       if q.get("figure") and q["figure"] not in pool.get("figures", {})]
            if missing:
                bad.append(f"{path.stem} missing figures {sorted(set(missing))}")
        except (ValueError, KeyError) as exc:
            bad.append(f"{path.name}: {exc}")
    if bad:
        _line(BAD, "question pools", "; ".join(bad))
        return False
    _line(OK, "question pools", f"{len(files)} pools, {total} questions")
    return True


def check_figures():
    directory = ROOT / "data" / "figures"
    files = [p for p in directory.rglob("*") if p.is_file()] if directory.is_dir() else []
    if not files:
        _line(WARN, "diagrams", "none extracted - figure questions will show no image")
        return True
    _line(OK, "diagrams", f"{len(files)} files")
    return True


def check_explanations():
    from .content import load_pools
    from .explain import coverage, part97
    total = explained = 0
    thin = []
    for pool in load_pools().values():
        c = coverage(pool)
        total += c["questions"]
        explained += c["explained"]
        if c["sections_with_notes"] < c["sections"]:
            thin.append(f"{c['pool_id']} {c['sections_with_notes']}/{c['sections']} sections")
    rules = len(part97())
    if not total:
        _line(WARN, "explanations", "no pools loaded")
        return True
    state = OK if explained == total else WARN
    detail = f"{explained}/{total} questions, {rules} CFR sections cached"
    if thin:
        detail += "; incomplete: " + ", ".join(thin)
    if not rules:
        detail += "; run --build-rules for FCC rule text"
    _line(state, "explanations", detail)
    return True


def check_database():
    from . import db
    try:
        conn = db.connect()
        conn.execute("SELECT COUNT(*) FROM answer_log").fetchone()
        answers = conn.execute("SELECT COUNT(*) c FROM answer_log").fetchone()["c"]
        conn.close()
        _line(OK, "progress database", f"{db.DB_PATH} ({answers} answers logged)")
        return True
    except Exception as exc:
        _line(BAD, "progress database", f"{db.DB_PATH}: {exc}")
        return False


def check_templates():
    from .app import app
    missing = []
    for name in ("base.html", "home.html", "study.html", "exam.html",
                 "progress.html", "browse.html", "propagation.html", "lab.html"):
        try:
            app.jinja_env.get_template(name)
        except Exception as exc:
            missing.append(f"{name} ({type(exc).__name__})")
    for asset in ("elmer.css", "elmer.js", "study.js", "exam.js",
                  "propagation.js", "lab.js"):
        if not (ROOT / "elmer" / "static" / asset).is_file():
            missing.append(f"static/{asset}")
    if missing:
        _line(BAD, "templates and assets", ", ".join(missing))
        return False
    _line(OK, "templates and assets", "all present")
    return True


def check_tools():
    from . import library
    want = ("pdftotext", "pdftoppm", "pdfimages", "pdftohtml", "pdfinfo")
    found = {t: library.tool(t) for t in want}
    if all(found.values()):
        where = {os.path.dirname(p) for p in found.values()}
        _line(OK, "poppler tools", f"present in {', '.join(sorted(where))} "
              "(for --build and the library)")
    else:
        from . import host
        _line(WARN, "poppler tools", "missing " +
              ", ".join(t for t in want if not found[t]) +
              (" - it reads the NIFOG channel PDF and the manuals on the shelf"
               if host.WINDOWS else
               f" - looked on PATH ({os.environ.get('PATH') or 'empty'}) and in "
               f"{', '.join(library.FALLBACK_DIRS)}. sudo apt install poppler-utils; "
               "if it is installed, ELMER was started with a different PATH from "
               "your terminal's"),
              fix="poppler" if host.WINDOWS else None)
    return True


def check_library():
    """The operator's manuals, and whether ELMER has read them."""
    from . import library
    books = library.shelf()
    if not books:
        _line(OK, "library", f"nothing on the shelf at {library.SHELF} - copy "
              "your manuals in and ELMER will index them")
        return True
    rows = library.catalogue()
    stale = [r["name"] for r in rows if r["stale"]]
    pages = sum(r["pages"] or 0 for r in rows if r["indexed"])
    if stale:
        _line(WARN, "library", f"{len(rows)} on the shelf, {len(stale)} to "
              f"(re)index - open the Library page or run --index-library")
    else:
        _line(OK, "library", f"{len(rows)} book{'s' if len(rows) != 1 else ''}, "
              f"{pages} pages indexed")
    return True


def check_manual():
    """ELMER's own guide, on the shelf with the operator's manuals."""
    from . import db, manual
    try:
        st = manual.status(db.connect())
    except Exception as exc:
        _line(WARN, "user's guide", f"could not look: {type(exc).__name__}: {exc}")
        return True
    if st["declined"]:
        _line(OK, "user's guide", "declined on the Library page - not on the shelf, and not put back")
    elif not st["source"]:
        _line(WARN, "user's guide", "docs/USER-GUIDE.md is not in this checkout, so there is nothing to build it from")
    elif not st["present"]:
        _line(WARN, "user's guide", f"not on the shelf - it comes back when ELMER next starts, or now", fix="manual")
    elif st["stale"]:
        _line(WARN, "user's guide", "on the shelf, but the text has changed since it was built - rebuilt when ELMER next starts, or now", fix="manual")
    else:
        _line(OK, "user's guide", f"{manual.NAME} on the shelf")
    return True


def check_internet():
    try:
        request = urllib.request.Request(
            "https://www.hamqsl.com/solarxml.php",
            headers={"User-Agent": "ELMER/1.0"})
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read(200)
        _line(OK, "space weather feed", "hamqsl.com reachable")
    except Exception as exc:
        _line(WARN, "space weather feed", f"unreachable ({exc}) - "
              "everything except the propagation page still works")
    return True


def check_gps():
    """Whether the GPS is answering, and which one is being asked.

    Every answer ELMER gives about reach and bearings is an answer about a
    place, so "where does this think it is" belongs in the self-check. A GPS
    that is off or silent is not a fault - the typed QTH is what makes the
    program work in a field - but finding that out should take one command
    rather than an afternoon.
    """
    from . import db, gps
    try:
        conn = db.connect()
    except Exception:
        conn = None
    host, port = gps.target(conn)
    where = f"{host}:{port}"
    if conn is not None and not gps.enabled(conn):
        _line(WARN, "GPS", f"switched off for this unit - the typed QTH is "
                           f"used (./elmer.py --gpsd {host} turns it back on)")
        return True
    found = gps.read_fix(host, port)
    if not found:
        # TowerWitch broadcasts the station's position over the network, so
        # one receiver serves every device. If that is arriving, this unit has
        # a fix and the missing receiver is not a fault.
        from . import towerwitch as twnet
        shared = twnet.current()
        if shared:
            from .geocode import to_grid
            _line(OK, "GPS", f"3D fix from {shared['from']} - "
                             f"{to_grid(shared['lat'], shared['lon'])} "
                             f"({shared['lat']:.4f}, {shared['lon']:.4f})")
            return True
        # A phone streaming NMEA is the fallback, and on a station with no
        # receiver on a lead it is the whole answer - so say so before
        # reporting the receiver as a problem.
        from . import phonegps
        phone = phonegps.current()
        if phone:
            from .geocode import to_grid
            verdict = gps.sleuth(phone)
            quality = f", {verdict['quality']}" if verdict.get("quality") else ""
            if verdict.get("advice"):
                _line(WARN, "GPS", f"{phone.get('mode', 2)}D fix from a phone at {phone.get('from')}{quality} "
                                   f"- {to_grid(phone['lat'], phone['lon'])}; {verdict['advice']}")
            else:
                _line(OK, "GPS", f"{phone.get('mode', 2)}D fix from a phone at "
                                 f"{phone.get('from')}{quality} - "
                                 f"{to_grid(phone['lat'], phone['lon'])} "
                                 f"({phone['lat']:.4f}, {phone['lon']:.4f})")
            return True
        # And what TowerWitch last knew, which on a unit where it holds the
        # GPS is the only position there is - reported with its age, so a
        # stale one is visibly stale rather than quietly wrong.
        from . import repeaters
        borrowed = repeaters.last_position()
        if borrowed:
            age = borrowed.get("age_s")
            when = (f"{age / 3600:.1f} hours ago" if age and age > 3600
                    else f"{age:.0f} seconds ago" if age is not None
                    else "at an unknown time")
            _line(WARN, "GPS", f"no fix of its own, but TowerWitch last knew "
                               f"itself at {borrowed.get('town') or 'a position'} "
                               f"({borrowed['lat']:.4f}, {borrowed['lon']:.4f}). "
                               f"TowerWitch wrote that {when} - still right if "
                               f"the station has not moved since")
            return True
        # Distinguish "nothing is listening" from "listening, but no lock":
        # one is a wiring or address problem, the other is the sky.
        listener = phonegps.listener()
        heard = twnet.listener()
        also = (f"; a phone may stream NMEA to udp/{listener.port}"
                if listener else "")
        if heard:
            also += (f"; listening for a TowerWitch broadcast on "
                     f"udp/{heard.port} but none has arrived")
        if port_in_use(port, host):
            _line(WARN, "GPS", f"gpsd at {where} answered but has no fix yet - "
                               f"the typed QTH is used until it locks{also}")
        else:
            _line(WARN, "GPS", f"nothing listening at {where} - the typed QTH "
                               f"is used (./elmer.py --gpsd HOST points "
                               f"elsewhere){also}")
        return True
    from .geocode import to_grid
    verdict = gps.sleuth(found)
    quality = f", {verdict['quality']}" if verdict.get("quality") else ""
    if verdict.get("advice"):
        _line(WARN, "GPS", f"{found['mode']}D fix from {where}{quality} - "
                           f"{to_grid(found['lat'], found['lon'])}; {verdict['advice']}")
    else:
        _line(OK, "GPS", f"{found['mode']}D fix from {where}{quality} - "
                         f"{to_grid(found['lat'], found['lon'])} "
                         f"({found['lat']:.4f}, {found['lon']:.4f})")
    return True


def check_repeaters():
    """Where the repeater list comes from, and whether it covers here.

    A list of 258 machines is worthless if they are all four hundred miles
    behind you, and that is exactly the failure that looks like success on a
    dashboard. So report the source, and say whether it knows about *here*.
    """
    from . import repeaters
    try:
        rows, source = repeaters.load()
    except Exception as exc:
        _line(BAD, "repeaters", f"could not load ({type(exc).__name__}: {exc})")
        return False

    tw = repeaters.find_towerwitch()
    if not rows:
        _line(WARN, "repeaters", "none known - "
                                 + ("./elmer.py --import-repeaters will copy "
                                    f"the list from {tw}" if tw else
                                    "no TowerWitch found and nothing imported; "
                                    "VHF and UHF will not name machines"))
        return True

    detail = f"{len(rows)} known, from {source}"
    # Coverage is only answerable if we know where we are. Prefer the live
    # fix, because that is the position the operator is actually standing at.
    spot = None
    try:
        from . import db, gps
        conn = db.connect()
        spot = gps.place(conn) if gps.enabled(conn) else None
        if not spot:
            spot = db.get_profile(conn)["settings"].get("location") or None
    except Exception:
        spot = None
    if spot and spot.get("lat") is not None:
        here = repeaters.coverage(spot["lat"], spot["lon"])
        if here["known"]:
            _line(OK, "repeaters", f"{detail}; nearest {here['nearest_km']} km")
        else:
            _line(WARN, "repeaters", f"{detail}, but the nearest is "
                                     f"{here['nearest_km']} km away - this "
                                     f"list is about somewhere else")
        return True
    _line(OK, "repeaters", detail)
    return True


def check_towerwitch_service():
    """The TowerWitch on the network, if this unit has been pointed at one.

    Silent when none is configured: a single-Pi station is the normal case and
    should not be told about a thing it does not use.
    """
    from . import db, repeaters
    try:
        conn = db.connect()
    except Exception:
        conn = None
    url = repeaters.service_url(conn)
    if not url:
        return True
    rows = repeaters.from_service(url, 46.0, -94.0, 100)
    if rows:
        _line(OK, "TowerWitch service", f"{url} answered ({len(rows)} "
                                        f"repeaters for a test position)")
    else:
        _line(WARN, "TowerWitch service", f"{url} did not answer - ELMER uses "
                                          f"what is on disk until it does")
    return True


def check_towerwitch_beside():
    """TowerWitch installed beside ELMER, and whether the dashboard's button
    to it could start it: the Qt build on Windows wants PyQt5 in ELMER's
    own Python, the Tk build on a Pi wants tkinter. Silent when there is no
    TowerWitch: a unit without one is the normal case."""
    from . import towerwitch
    path = towerwitch.find()
    if path is None:
        return True
    import importlib.util
    if os.name == "nt":
        # What the Qt build imports; its requirements.txt is what the Fix
        # installs, and these are the import names those packages go by.
        wanted = {"PyQt5": "PyQt5", "requests": "requests", "utm": "utm",
                  "maidenhead": "maidenhead", "mgrs": "mgrs", "packaging": "packaging"}
        missing = [pkg for pkg, mod in wanted.items() if importlib.util.find_spec(mod) is None]
        if missing:
            _line(WARN, "TowerWitch", f"at {path}, but {', '.join(missing)} "
                                      f"{'is' if len(missing) == 1 else 'are'} not in ELMER's Python - "
                                      f"the dashboard's button cannot start it", fix="pyqt5")
        else:
            _line(OK, "TowerWitch", f"at {path}; its Qt build's packages are here, so the "
                                    f"dashboard's button can start it")
    else:
        if importlib.util.find_spec("tkinter") is None:
            _line(WARN, "TowerWitch", f"at {path}, but tkinter is missing - "
                                      f"sudo apt install python3-tk, then the button can start it")
        else:
            _line(OK, "TowerWitch", f"at {path}; the dashboard's button can start it")
    return True


def _neighbour_words(peers):
    """One clause per unit heard: who, where, and what it says it is doing."""
    parts = []
    for peer in peers:
        net = peer.get("net") or {}
        # A table that names its net has heard back from it; one that only
        # has an address is pointed at a net that has not answered it yet.
        role = ("running " + (net.get("name") or "a net") if net.get("hosting")
                else ("a table in " + net.get("table_in")) if net.get("table_in")
                else ("reporting to " + str(net.get("table_of")) + ", which has not "
                      "answered it") if net.get("table_of")
                else "on its own")
        parts.append(f"{peer['name']} at {peer['address']} ({role})")
    return "; ".join(parts)


def check_neighbours(listen=True, seconds=None):
    """Whether other ELMERs can be heard on this network, and what they are doing.

    The one thing most likely to go wrong on an evening with two Pis is that
    they cannot hear each other - a router that drops broadcast, a guest
    network that isolates clients, a firewall on the port - and nothing on
    either screen says so; each just plays alone.

    Inside a running ELMER the answer is the program's own roster, which is
    what it acts on and costs nothing to read. From the terminal, with no
    server running, the doctor listens on the discovery port itself, for a
    whole announce interval and a margin - or a live neighbour is missed half
    the time and the line says "none" when the answer is "one". Bound with
    SO_REUSEADDR so it can share the port with an ELMER already running here.
    """
    from . import cohort, discovery
    live = discovery.neighbourhood()
    if live is not None:
        peers = live.current()
        if peers:
            _line(OK, "other ELMERs", f"{len(peers)} heard in the last "
                  f"{discovery.GONE_AFTER:.0f} s - " + _neighbour_words(peers))
        else:
            _line(OK, "other ELMERs", f"none heard in the last {discovery.GONE_AFTER:.0f} s "
                  "- alone, or the only one switched on; a second unit on this "
                  f"network announces itself every {discovery.ANNOUNCE_EVERY:.0f} s")
        return True
    if not listen:
        _line(OK, "other ELMERs", "discovery is not running in this process - "
              "./elmer.py --doctor listens for itself")
        return True
    seconds = discovery.ANNOUNCE_EVERY + 2.0 if seconds is None else seconds
    me = cohort.default_unit_id()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        sock.settimeout(0.5)
        try:
            sock.bind(("", discovery.DEFAULT_PORT))
        except OSError as exc:
            _line(WARN, "other ELMERs", f"could not listen on udp/{discovery.DEFAULT_PORT} "
                  f"({exc}) - units here will not find each other until that port is free")
            return True
        heard = {}
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                data, sender = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            peer = discovery.parse(data, sender[0])
            if peer and peer["unit"] != me:      # not this unit's own voice
                heard[peer["unit"]] = peer
    finally:
        sock.close()
    if not heard:
        _line(OK, "other ELMERs", f"none heard in {seconds:.0f} s on udp/{discovery.DEFAULT_PORT} "
              "- alone, or the only one switched on; a second unit on this network "
              f"announces itself every {discovery.ANNOUNCE_EVERY:.0f} s")
        return True
    _line(OK, "other ELMERs", f"{len(heard)} heard - " + _neighbour_words(heard.values()))
    return True


def check_neighbours_known():
    """The roster as this process knows it, never a listen: for collect()."""
    return check_neighbours(listen=False)


def check_net_role():
    """Which hall this unit remembers, and whether it is still there.

    A table keeps the address and token of the net it was last in so that it
    rejoins after the overnight restart. When that net is gone - the host
    Pi is off, or opened a new net - the table sits reporting to nobody, and
    the reason is on this line rather than in a log.
    """
    from . import cohort, db
    try:
        conn = db.connect()
        url = (db.unit_get(conn, cohort.URL_SETTING) or "").strip()
        token = db.unit_get(conn, cohort.TOKEN_SETTING) or ""
        auto = cohort.auto_join_wanted(conn)
    except Exception as exc:
        _line(WARN, "hall", f"could not read the unit settings ({exc})")
        return True
    if not url or cohort.is_own_address(url):
        _line(OK, "hall", "not in a net" + (
              "; will join one it hears" if auto else
              "; auto-join is off - it will not join one it hears until told to")
              + (" (the address remembered was this unit's own, from hosting - "
                 "forgotten at the next start)" if url else ""))
        return True
    try:
        request = urllib.request.Request(url.rstrip("/") + "/api/net/board",
                                         headers={"User-Agent": "ELMER/1.0 (doctor)"})
        with urllib.request.urlopen(request, timeout=4) as response:
            board = json.loads(response.read())
        same = (not token) or board.get("token") == token
        _line(OK if same else WARN, "hall",
              f"remembers {url}, which is running {board.get('name') or 'a net'} "
              f"({board.get('units_present', 0)} tables present)"
              + ("" if same else " - a different net from the one this table was "
                 "in; the table starts afresh in it when it rejoins"))
    except Exception as exc:
        _line(WARN, "hall", f"remembers {url} but it is not answering ({type(exc).__name__}) "
              "- the table rejoins when it comes back, or follows the same net "
              "to a new address if it hears it there", fix="forget-net")
    return True


def check_mail():
    """Whether reports can leave this unit, and by which door.

    Never sends. It says what is set and, for the providers that refuse an
    account's own password, what they will want - the same words the refusal
    would use, said before the first refusal instead of after it.
    """
    from . import drop, mail
    s = mail.settings()
    if not mail.configured(s):
        if drop.configured():
            _line(OK, "mail home", f"reports go to {mail.CONTACT} by the drop - "
                  "nothing of the operator's on them; set an outgoing mail "
                  "server on the dashboard to send through your own account instead")
        else:
            _line(OK, "mail home", "no drop and no outgoing mail server set - reports "
                  f"are written to data/ and the page says where to send them ({mail.CONTACT})")
        _last_send(mail)
        return True
    known = mail.provider(s.get("host"))
    detail = (f"{s.get('sender')} via {s.get('host')}:{s.get('port') or '?'} "
              f"({s.get('security') or 'starttls'})"
              + (", login set" if s.get("user") else ", no login"))
    if known and not s.get("password"):
        _line(WARN, "mail home", detail + f" - {known.split(' (')[0]} will want an app "
              "password, and none is set")
    elif known and "yahoo" in (s.get("host") or "").lower() and (s.get("security") or "") != "ssl":
        _line(WARN, "mail home", detail + " - Yahoo wants port 465 and ssl")
    else:
        _line(OK, "mail home", detail + f" - reports go to {mail.CONTACT} with [ELMER] "
              "in the subject; Send a test on the dashboard proves the path")
    _last_send(mail)
    return True


def _last_send(mail):
    # What actually happened last time is worth more than what is configured.
    # A unit whose settings look right but whose last send was refused is the
    # exact case a report is written to catch, so it is said here in words.
    last = mail.last_result()
    if last:
        when = time.strftime("%d %b %H:%M", time.localtime(last.get("at", 0)))
        door = " by the drop" if last.get("via") == "drop" else ""
        if last.get("ok"):
            _line(OK, "last send", f"sent{door} {when} - {last.get('detail', '')}")
        else:
            _line(WARN, "last send", f"FAILED{door} {when} - {last.get('detail', '')}")


def check_hall():
    """When this unit runs a net, what the hall actually looks like.

    A net that has collapsed - three units checked in but one table on the
    board because a fleet shares an identity - is invisible on a dashboard
    that only shows the score. Said here so a report carries it.
    """
    from . import netcontrol, hall
    net = netcontrol.net()
    if net is None:
        return True
    board = net.board()
    units = board.get("units") or []
    real = [u for u in units if not u.get("simulated")]
    cloned = [u for u in real if u.get("cloned")]
    present = board.get("units_present", 0)
    detail = (f"{board.get('name')} - {len(real)} unit(s) checked in, "
              f"{present} present, {board.get('players', 0)} players")
    if cloned:
        _line(WARN, "net control", detail + f"; {len(cloned)} share an identity "
              "with another (a cloned SD card) - give the units their own hostnames")
    else:
        _line(OK, "net control", detail)
    # The wire to each table, which the master's own p95 never sees. A hall
    # can look healthy here and still feel slow at one table in the corner
    # whose link is bad; this is the line that finds it.
    linked = [u for u in real if u.get("rtt_ms") is not None]
    if linked:
        worst = max(linked, key=lambda u: u["rtt_ms"])
        summary = ", ".join(f"{u['name']} {u['rtt_ms']:.0f}ms"
                            + ("*" if u.get("rtt_room") == "game" else "")
                            for u in sorted(linked, key=lambda u: -u["rtt_ms"])[:6])
        if worst["rtt_ms"] > RTT_SLOW_MS:
            _line(WARN, "table links", f"slowest {worst['name']} at "
                  f"{worst['rtt_ms']:.0f}ms to master - that table's wifi is "
                  f"the delay, not this machine. {summary} (* = measured in a round)")
        else:
            _line(OK, "table links", f"{summary} to master"
                  + ("  (* = in a round)" if any(u.get("rtt_room") == "game" for u in linked) else ""))
    choking = [u for u in real if (u.get("host") or {}).get("hot")]
    if choking:
        names = ", ".join(f"{u['name']} ({(u['host'].get('per_core') or 0):.1f}/core"
                          + (", under-voltage" if u["host"].get("undervolt") else "")
                          + ")" for u in choking)
        _line(WARN, "table load", f"{len(choking)} table(s) overfed - {names}. "
              "That is not the wire; those Pis are doing more than they can serve")
    live = hall.conductor()
    if live is not None:
        d = live.as_dict()
        if d.get("state") == "faulted":
            _line(BAD, "conductor", f"faulted - {d.get('error')}")
        else:
            _line(OK, "conductor", f"{d.get('state')}"
                  + (f", {d['played']} rounds" if d.get("played") else "")
                  + (f" ({d['waiting_for']})" if d.get("waiting_for") else ""))
    tk = hall.timekeeper()
    if tk is not None and getattr(tk, "error", None):
        _line(BAD, "programme clock", tk.error)
    return True


def check_node():
    """When this unit is a table in somebody else's net, whether it is getting
    through - a bridge stuck offline or a report that cannot be handed in is a
    table playing to nobody, and nothing on its own screen says so plainly."""
    from . import cohort, netcontrol
    if netcontrol.net() is not None:
        return True                       # hosting, not a node
    link = cohort.bridge()
    if link is None:
        return True                       # on its own; check_net_role said so
    d = link.as_dict()
    if cohort.is_own_address(d.get("url")):
        _line(WARN, "this table", "reporting to this unit's own address, with no net "
              "running here - a leftover of hosting", fix="leave-net")
        return True
    state = d.get("state")
    detail = (f"reporting to {d.get('net_name') or d.get('url')} as "
              f"{d.get('name')}, round {d.get('net_round', 0)}")
    if state == "offline":
        _line(WARN, "this table", f"net control is not answering - {detail} "
              f"({d.get('error') or 'offline'}); the table keeps playing and "
              "reports when it is back")
    elif state in ("refused", "faulted"):
        _line(WARN, "this table", f"{state}: {d.get('error')} - {detail}")
    elif d.get("waiting_to_report"):
        _line(WARN, "this table", f"a report is waiting to go - {detail}")
    else:
        _line(OK, "this table", detail)
    rtt = d.get("rtt_ms")
    p95 = d.get("rtt_p95")
    if rtt is not None:
        line = f"{rtt:.0f}ms to net control" + (f", p95 {p95:.0f}ms" if p95 else "")
        if (p95 or rtt) > RTT_SLOW_MS:
            _line(WARN, "link to master", line + " - this unit's wifi is adding "
                  "the delay; move it closer to the access point or wire it")
        else:
            _line(OK, "link to master", line)
    return True


def check_op25():
    """Whether OP25 is on this machine eating it, and what ELMER will do.

    OP25 takes most of a Pi when it runs; a game on the same machine then
    serves everything from behind it. ELMER can stop it when a game starts -
    this says whether it is running, and whether that is armed - so the
    choke is named before the evening rather than guessed at during it.
    """
    from . import op25, db
    try:
        conn = db.connect()
    except Exception:
        conn = None
    procs = op25.running(conn)
    armed = op25.wanted(conn)
    if not procs:
        if armed:
            _line(OK, "OP25", "not running; it would be stopped when a game starts")
        else:
            _line(OK, "OP25", "not running (and stopping it is switched off)")
        return True
    pids = ", ".join(f"pid {p}" for p, _ in procs)
    if armed:
        _line(WARN, "OP25", f"running ({pids}) - it takes most of a Pi; ELMER "
              "will stop it when a net opens or a tournament starts", fix="stop-op25")
    else:
        _line(WARN, "OP25", f"running ({pids}) and stopping it is switched off "
              "- on a Pi 3 it will make a game feel slow; set stop_op25 on, or "
              "stop it by hand before playing")
    return True


def check_kiosk():
    """What ./elmer.py --kiosk would do if it were run right now - or, on
    Windows, what the window of ELMER's own will be.

    The kiosk is the Pi's full-screen Chromium and does not run on Windows;
    the browsers it looks for are on the PATH on a Pi and never on Windows,
    where Firefox lives in Program Files and being the default browser
    changes nothing. So on Windows the line is about the window instead:
    Edge or Chrome as an app window, closed to stop ELMER. Firefox cannot
    be that window - it has no app-window mode - and Edge is on every
    Windows machine, so the window is never missing for long.
    """
    from . import host, kiosk
    if not host.can_kiosk():
        from . import window
        path, name = window.find_browser()
        if path:
            _line(OK, "window", f"{name} ({Path(path).name}) - ELMER opens in a window of "
                                "its own; closing it stops ELMER")
        else:
            _line(WARN, "window", "no Edge or Chrome for a window of ELMER's own - it "
                                  "opens as a tab in the default browser, which will "
                                  "not stop it when closed")
        return True
    path, family = kiosk.find_browser()
    if not path:
        _line(WARN, "kiosk mode", "no chromium or firefox - --kiosk will serve "
                                  "normally instead")
        return True
    name = Path(path).name
    if not kiosk.have_display():
        _line(WARN, "kiosk mode", f"{name} found, but this session has no "
                                  "screen - --kiosk will serve normally instead")
        return True
    _line(OK, "kiosk mode", f"{name} ({family}) ready")
    return True


def check_updates():
    """Whether this install can keep itself current, and whether it is.

    Reads the last background check rather than making one: --doctor should
    answer straight away and work with the network unplugged.
    """
    from . import update
    st = update.state()
    if not st["checkout"]:
        _line(WARN, "updates", "this copy is not connected to the repository, so "
                               "it cannot update itself", fix="connect")
        return True
    was = update.cached()
    where = f"{st['head']} on {st['branch']}" if st["branch"] else st["head"]
    if st["dirty"]:
        _line(WARN, "updates", f"{where}, with local changes - held back "
                               "until they are committed or put aside")
        return True
    if not was or not was.get("checked_at"):
        _line(OK, "updates", f"{where} - not checked yet")
    elif was.get("error"):
        _line(WARN, "updates", f"{where} - last check: {was['error']}")
    elif was.get("behind"):
        _line(WARN, "updates", f"{where} - {was['behind']} waiting, "
                               "apply with ./elmer.py --update")
    else:
        _line(OK, "updates", f"{where} - up to date")
    return True


def check_launcher():
    """Whether ELMER is in the applications menu, and whether it points here.

    A .desktop entry holds an absolute Exec path, so moving the install folder
    leaves the icon pointing at somewhere that no longer exists - and the
    advice to move a copy out of the downloads folder is advice that causes
    exactly that. Saying "installed" for a dead icon would be the wrong kind
    of true.
    """
    from . import host, launcher
    if host.WINDOWS:
        # The Pi's .desktop entry has no meaning here; the Start Menu
        # shortcut install.ps1 writes is the menu entry on Windows, and it
        # carries the folder it points at the same way.
        import os
        lnk = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "ELMER.lnk"
        if not lnk.is_file():
            _line(WARN, "Start Menu", "ELMER is not on the Start Menu",
                  fix="start-menu")
            return True
        try:
            import subprocess
            target = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}').TargetPath"],
                capture_output=True, text=True, timeout=15).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            target = ""
        here = Path(__file__).resolve().parents[1]
        if target and Path(target).resolve().parent == here:
            _line(OK, "Start Menu", "ELMER is on the Start Menu, and points at this copy")
        elif target and Path(target).exists():
            _line(WARN, "Start Menu", f"the entry points at another copy: {Path(target).parent}")
        elif target:
            _line(BAD, "Start Menu", "the entry points at a folder that is no longer there",
                  fix="start-menu")
        else:
            _line(OK, "Start Menu", "ELMER is on the Start Menu")
        return True
    if not launcher.installed():
        _line(WARN, "menu entry", "not installed - add it with "
                                  "./elmer.py --install-launcher")
        return True
    if launcher.installed_here():
        _line(OK, "menu entry", "installed, and points at this copy")
        return True
    target = launcher.owner()
    if target and target.exists():
        _line(OK, "menu entry", "installed, but it points at another copy of "
                                "ELMER on this machine")
        _line(WARN, "", "./elmer.py --install-launcher would point it here "
                        "instead")
    else:
        _line(BAD, "menu entry", "points at a folder that is no longer there - "
                                 "the icon will do nothing")
        _line(WARN, "", "./elmer.py --install-launcher repoints it at this copy")
    return True


def check_start():
    """What this unit last took to serve its first page.

    Reported rather than judged, mostly: a board that takes eight seconds off
    a tired card is not broken, it is slow, and the operator can see that for
    themselves.  What is worth saying is when it has grown past the splash's
    hold, because past that the covering stops working and somebody is left
    watching a wait.

    It answers over HTTP with the rest of the doctor, which is the point of
    keeping it - one unit can read what every unit on the network took, and a
    median can be taken from a chair instead of on foot.
    """
    from . import db, startup
    try:
        record = startup.last(db.connect())
    except Exception as exc:
        _line(WARN, "start", f"could not be read ({exc})")
        return True
    if not record:
        _line(OK, "start", "not timed yet - this unit has not served a page "
                           "since the timing was added")
        return True
    took = record["build"]
    when = ""
    if record.get("at"):
        try:
            when = time.strftime(" on %d %b at %H:%M",
                                 time.localtime(float(record["at"])))
        except (TypeError, ValueError):
            when = ""
    from . import kiosk
    if took > kiosk.HOLD_SECONDS:
        _line(WARN, "start",
              f"first page took {took:.1f}s to build{when} - longer than the "
              f"{kiosk.HOLD_SECONDS:.0f}s the splash holds for, so the wait "
              f"shows")
    else:
        _line(OK, "start", f"first page built in {took:.1f}s{when}")
    return True


def check_pace():
    """Whether anything on this unit has crept, from the ledger."""
    try:
        from . import pace
        bad = pace.creepers()
    except Exception as exc:
        _line(WARN, "pace", f"the ledger could not be read ({exc})")
        return True
    if not pace.rows():
        _line(OK, "pace", "no requests timed yet - the ledger fills as pages are served")
    elif bad:
        worst = bad[0]
        _line(WARN, "pace", f"{len(bad)} endpoint(s) over budget or crept - worst {worst['key']} "
                            f"p95 {worst['p95']} ms" + (f", crept from {worst['base']} ms" if worst["crept"] else "")
                            + "; the weekly field report carries the table",
              fix="find what that endpoint does per call that it did not - the log around it, then the code")
    else:
        top = pace.rows()[0]
        _line(OK, "pace", f"nothing over budget, nothing crept - slowest {top['key']} p95 {top['p95']} ms")
    return True


def check_server(port):
    if port_in_use(port):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
                body = r.read(400).decode("utf-8", "replace")
            if "ELMER" in body:
                _line(OK, f"server on port {port}", "already running and answering")
            else:
                _line(WARN, f"port {port}", "in use by something that is not ELMER")
        except Exception as exc:
            _line(WARN, f"port {port}", f"in use but not answering HTTP ({exc})")
        return True
    _line(OK, f"port {port}", "free - ready to start")
    return True


def doctor(port=5000):
    print("\n  ELMER self-check\n")
    print(f"  python      {sys.version.split()[0]}")
    print(f"  project     {ROOT}")
    try:
        import flask
        print(f"  flask       {flask.__version__}")
    except Exception:
        print("  flask       NOT INSTALLED - pip3 install flask")
    print()

    results = [
        check_pools(), check_figures(), check_explanations(), check_database(),
        check_templates(), check_tools(), check_library(), check_manual(), check_kiosk(),
        check_launcher(),
        check_updates(), check_location(),
        check_gps(), check_repeaters(), check_towerwitch_service(), check_towerwitch_beside(),
        check_neighbours(), check_net_role(), check_hall(), check_node(),
        check_mail(), check_load(), check_op25(),
        check_internet(), check_start(), check_pace(), check_server(port),
    ]

    print("\n  Open ELMER at any of these:\n")
    print(f"      http://localhost:{port}          (on this Pi)")
    addresses = local_addresses()
    for interface, ip in addresses:
        print(f"      http://{ip}:{port}      (from another device, via {interface})")
    if not addresses:
        print("      no network interface is up - only localhost will work")

    print("\n  If a browser on another device cannot reach it, check that the")
    print("  device is on the same network as this Pi, then watch the log while")
    print("  you try:  tail -f data/elmer.log")
    print("  If nothing appears there, the request never arrived and the problem")
    print("  is the network, not ELMER.\n")
    return all(results)
