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
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OK, WARN, BAD = "  ok  ", " warn ", " FAIL "


def _line(state, label, detail=""):
    print(f"  [{state}] {label}" + (f"  -  {detail}" if detail else ""))


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
    count = sum(1 for _ in directory.rglob("*")) if directory.is_dir() else 0
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
    have = [t for t in ("pdftotext", "pdftoppm", "pdfimages") if shutil.which(t)]
    if len(have) == 3:
        _line(OK, "poppler tools", "present (needed only for --build)")
    else:
        _line(WARN, "poppler tools", "missing " +
              ", ".join(t for t in ("pdftotext", "pdftoppm", "pdfimages")
                        if t not in have) + " - rebuilding pools will fail")
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
        # Distinguish "nothing is listening" from "listening, but no lock":
        # one is a wiring or address problem, the other is the sky.
        if port_in_use(port, host):
            _line(WARN, "GPS", f"gpsd at {where} answered but has no fix yet - "
                               f"the typed QTH is used until it locks")
        else:
            _line(WARN, "GPS", f"nothing listening at {where} - the typed QTH "
                               f"is used (./elmer.py --gpsd HOST points "
                               f"elsewhere)")
        return True
    from .geocode import to_grid
    _line(OK, "GPS", f"{found['mode']}D fix from {where} - "
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


def check_kiosk():
    """What ./elmer.py --kiosk would do if it were run right now."""
    from . import kiosk
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
        _line(WARN, "updates", "not a git checkout - run ./elmer.py --adopt "
                               "to point this copy at the repository")
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
    from . import launcher
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
        check_templates(), check_tools(), check_kiosk(), check_launcher(),
        check_updates(), check_location(),
        check_gps(), check_repeaters(), check_towerwitch_service(),
        check_internet(), check_server(port),
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
