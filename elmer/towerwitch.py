"""The station's GPS, taken off the network where TowerWitch puts it.

One receiver on one Pi, and every device in the vehicle knowing where it is.
That is the arrangement TowerWitch already provides: it broadcasts its position
over UDP, so anything on the network can have the same 3D fix without a second
antenna, a second receiver, or a fight over who owns the serial port.

ELMER listens for it. Nothing is asked of TowerWitch and nothing is configured
between them - a broadcast is heard or it is not.

This is deliberately a different thing from reading TowerWitch's state file,
which is its last known position and carries the age of a file write. This is
the live fix, arriving every few seconds with its own timestamp, and it is
treated as one.

The packet is TowerWitch's own, unchanged:

    {"timestamp": "...", "source": "TowerWitch",
     "gps_lat": 46.5983, "gps_lon": -94.3154,
     "speed_mps": 0.05, "is_vehicle_speed": false,
     "closest_armer_towers": [...]}

Only the position is taken. What else rides along is TowerWitch's business.

A word on trust, kept in the same terms as everything else here: anything on
the network can send a packet to this port, so this is a station on a network
the operator controls taking a position from another station on it. It is not
authenticated and does not pretend to be. A receiver wired to this machine
still wins wherever there is one.
"""
import json
import logging
import socket
from pathlib import Path
import threading
import time

log = logging.getLogger("elmer")

DEFAULT_PORT = 12345      # TowerWitch's own default, in its UDP_CONFIG
BIND = ""                 # every interface, because a broadcast arrives on one
# TowerWitch sends every 25 seconds by default. Three missed sends and it has
# stopped talking, which is not the same as the station having stopped moving.
STALE_AFTER = 90.0

_listener = None
_lock = threading.Lock()


def parse(payload):
    """One TowerWitch broadcast as a fix, or None.

    Refuses anything that is not TowerWitch's, and anything carrying no
    position - it broadcasts tower data whether or not it has a lock, so a
    packet is not by itself evidence of one.
    """
    try:
        data = json.loads(payload.decode("utf-8", "ignore"))
    except (ValueError, AttributeError):
        return None
    if not isinstance(data, dict) or data.get("source") != "TowerWitch":
        return None
    try:
        lat = data.get("gps_lat")
        lon = data.get("gps_lon")
        if lat is None or lon is None:
            return None
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    out = {"lat": lat, "lon": lon, "mode": 3, "alt_m": None,
           "source": "towerwitch-net", "read_at": time.time(),
           "sent": data.get("timestamp")}
    try:
        if data.get("speed_mps") is not None:
            out["speed_mps"] = float(data["speed_mps"])
    except (TypeError, ValueError):
        pass
    out["moving"] = bool(data.get("is_vehicle_speed"))
    return out


class Listener:
    """A UDP socket that hears TowerWitch announce where the station is."""

    def __init__(self, port=DEFAULT_PORT):
        self.port = int(port)
        self.sock = None
        self.thread = None
        self.stop = threading.Event()
        self.fix = None
        self.heard = 0
        self.ignored = 0
        self.last_from = None
        self.error = None

    def run(self):
        while not self.stop.is_set():
            try:
                data, sender = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            got = parse(data)
            if got is None:
                self.ignored += 1
                continue
            got["from"] = f"TowerWitch at {sender[0]}"
            self.fix = got
            self.heard += 1
            self.last_from = sender[0]
            if self.heard == 1:
                log.info("TowerWitch on the network: position from %s",
                         sender[0])

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError:
            pass
        self.sock.settimeout(1.0)
        self.sock.bind((BIND, self.port))
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="towerwitch-net")
        self.thread.start()
        log.info("listening for TowerWitch on udp/%d", self.port)
        return self

    def close(self):
        self.stop.set()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    def current(self):
        got = self.fix
        if not got or time.time() - got["read_at"] > STALE_AFTER:
            return None
        return got

    def as_dict(self):
        got = self.current()
        return {"listening": bool(self.thread and self.thread.is_alive()),
                "port": self.port, "heard": self.heard,
                "ignored": self.ignored, "from": self.last_from,
                "has_fix": bool(got), "error": self.error,
                "age_s": round(time.time() - got["read_at"], 1) if got else None}


def listener():
    with _lock:
        return _listener


def start(port=DEFAULT_PORT):
    global _listener
    with _lock:
        if _listener is not None:
            _listener.close()
        _listener = Listener(port).start()
        return _listener


def stop_listening():
    global _listener
    with _lock:
        if _listener is not None:
            _listener.close()
        _listener = None


def current():
    """The position TowerWitch last announced, if it is still current."""
    live = listener()
    return live.current() if live else None


# ------------------------------------------------------- the other dashboard
# ELMER and TowerWitch are two programs on one bench, and each has a button
# to the other - greyed when the other is not installed, the way TowerWitch
# greys its OP25 button. This side finds TowerWitch beside ELMER, says
# whether it is running (it announces itself on the network, and a
# broadcast from this machine is it), and starts it when pressed on the
# unit's own screen. Nothing over the network can start a desktop program.

def find():
    """Where TowerWitch is installed, or None: the same places the repeater
    reader looks, since it is the same program."""
    from .repeaters import find_towerwitch
    return find_towerwitch()


# The TowerWitch this ELMER started, if it did: the surest answer to
# "is it running" is the process itself.
_started = {"proc": None, "at": 0.0}


_processes = {"at": 0.0, "out": []}
PROCESSES_FOR = 20.0            # seconds a process listing is reused: a page is not a reason to list them again


def processes(max_age=PROCESSES_FOR):
    """Every TowerWitch process on this machine, as (pid, command line):
    a Python running one of its scripts - not a shell that names it, and
    never this program. Listed at most every PROCESSES_FOR seconds: on
    Windows the listing is a PowerShell that takes most of a second, and
    it was being run for every home page."""
    import os
    import subprocess
    import time
    if time.time() - _processes["at"] < max_age:
        return list(_processes["out"])
    mine = {os.getpid(), os.getppid()}
    out = []
    _processes["at"] = time.time()
    _processes["out"] = out
    try:
        if os.name == "nt":
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*TowerWitch*' } "
                 "| ForEach-Object { \"$($_.ProcessId) $($_.CommandLine)\" }"],
                capture_output=True, text=True, timeout=15)
        else:
            res = subprocess.run(["pgrep", "-af", "TowerWitch"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return out
    for line in res.stdout.splitlines():
        pid_s, _, cmd = line.strip().partition(" ")
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        if pid in mine:
            continue
        tokens = cmd.split()
        if not tokens:
            continue
        first = os.path.basename(tokens[0]).strip('"').lower()
        if first in ("bash", "sh", "dash", "zsh", "powershell", "powershell.exe", "pwsh", "pwsh.exe", "cmd.exe"):
            continue
        if "pgrep" in cmd or "Get-CimInstance" in cmd:
            continue
        if not (first.startswith("python") or first.endswith(".py")):
            continue
        if not any(t.lower().endswith(".py") and "towerwitch" in t.lower() for t in tokens):
            continue
        out.append((pid, cmd.strip()))
    return out


def running_here():
    """Whether TowerWitch is running on this machine.

    The process table is the answer; the broadcast is a second opinion.
    TowerWitch announces itself every few seconds while it runs, and the
    listener keeps the last announcement for ninety seconds - so for a
    minute and a half after somebody closes it the broadcast alone would
    still say "running", and the button would refuse to start it. So: the
    process ELMER started, if it is alive; else any TowerWitch process;
    and when the broadcast says otherwise, a line in the log says which
    was believed and why.
    """
    proc = _started["proc"]
    if proc is not None and proc.poll() is None:
        return True
    found = processes()
    live = listener()
    heard = bool(live and live.current()
                 and ((live.last_from or "") in ("127.0.0.1", "::1", "localhost") or _is_own(live.last_from)))
    if found:
        return True
    if heard:
        age = round(time.time() - live.current()["read_at"], 1)
        log.info("towerwitch: broadcast %.0fs old from this machine but no TowerWitch process - "
                 "closed since; the button will start it", age)
    return False


def _is_own(addr):
    try:
        own = {info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None)}
    except OSError:
        own = set()
    return addr in own


def status():
    """For the button: installed where, running or not."""
    path = find()
    return {"installed": path is not None, "path": str(path) if path else None,
            "running": running_here() if path else False}


# Which build to start on Windows, in order. The Tk one first: it is the
# build KC9SP actually runs, it is what the Pis run, and it is the one
# being worked on - a button that opened the other one showed a TowerWitch
# without the day's changes in it, which reads as the changes not having
# landed.
#
# It used to be the other way round, for a good reason that has since
# stopped being true: the Tk build imported fcntl at the top of the file,
# which is POSIX only, so on Windows it died before a window could appear.
# That import is guarded now and the single-instance lock is kept through
# msvcrt, so the Tk build starts here. It also asks less of the machine
# than the Qt one - stdlib and its own modules, where TowerWitch-P wants
# PyQt5, requests, utm, maidenhead and mgrs.
WINDOWS_BUILDS = ("TowerWitch_Tkinter.py", "TowerWitch-P.py")


def launch(path):
    """Start TowerWitch from its folder. Returns (ok, said). Its own
    launcher where it has one; on Windows the first of WINDOWS_BUILDS
    that is actually in the folder."""
    import os
    import subprocess
    import sys
    path = Path(path)
    if os.name == "nt":
        for name in WINDOWS_BUILDS:
            script = path / name
            if script.is_file():
                break
        else:
            return False, ("none of " + ", ".join(WINDOWS_BUILDS)
                           + " is in that folder")
        cmd = [sys.executable, str(script)]
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            proc = subprocess.Popen(cmd, cwd=str(path), creationflags=flags,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except OSError as exc:
            return False, f"could not start it: {exc}"
    else:
        for name in ("run_towerwitch.sh", "towerwitch.sh"):
            if (path / name).is_file():
                cmd = ["bash", str(path / name)]
                break
        else:
            script = path / "TowerWitch_Tkinter.py"
            if not script.is_file():
                return False, "no launcher and no TowerWitch_Tkinter.py in that folder"
            cmd = [sys.executable, str(script)]
        env = dict(os.environ)
        env.setdefault("DISPLAY", ":0")
        try:
            proc = subprocess.Popen(cmd, cwd=str(path), env=env, start_new_session=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except OSError as exc:
            return False, f"could not start it: {exc}"
    # A program that dies in its first seconds has something to say.
    try:
        proc.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        _started["proc"], _started["at"] = proc, time.time()
        return True, "TowerWitch is starting on this unit's screen"
    err = ""
    try:
        err = (proc.stderr.read() or b"").decode("utf-8", "replace").strip().splitlines()[-1:]
        err = err[0] if err else ""
    except Exception:
        pass
    return False, f"TowerWitch stopped as soon as it started (exit {proc.returncode})" + (f": {err}" if err else "")
