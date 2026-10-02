"""Talking to a NanoVNA over USB, and being honest when there is not one.

The instrument presents a USB CDC serial port and a line-oriented shell. You
send a command and a newline, it answers, and it ends every answer with its
prompt - "ch> ". That is the whole protocol. It is unusually pleasant for a
piece of test gear and it means this module needs no vendor library, only
pyserial and some patience with timeouts.

    ch> info                    what it is and what firmware
    ch> scan 14000000 14350000 101 0b110
                                sweep, and give me frequency + S11 back
    ch> data 0                  the last S11 sweep, real and imaginary
    ch> frequencies             the frequencies those points were taken at

The reflection coefficient comes back as two floats per line, already
normalised to 50 ohms and already corrected by whatever calibration is loaded
in the instrument - which is the part that matters and the part that goes
wrong. A NanoVNA with no calibration, or one calibrated at the wrong end of
the coax, returns numbers with exactly the same confident air as a good one.
Nothing in the wire protocol can tell those apart, so this module does not
pretend to: it reports what the instrument says and the Lab explains what a
bad calibration looks like on screen.

Written against the documented protocol but never yet run against a device on
this machine - there was none attached. Every failure path returns a reason
rather than raising into a page.
"""
import logging
import math
import time

from . import host

log = logging.getLogger("elmer")

PROMPT = b"ch> "
BAUD = 115200                      # ignored by CDC, but pyserial wants one
READ_TIMEOUT = 2.0
SWEEP_TIMEOUT = 30.0

# What a NanoVNA looks like on the bus. The H and H4 are STM32 virtual COM
# ports; the -F family uses a CH340. Neither VID/PID is unique to a VNA, so a
# match is a candidate and `identify` is what settles it.
KNOWN = [
    (0x0483, 0x5740, "NanoVNA-H / H4 (STM32 VCP)"),
    (0x16c0, 0x0483, "NanoVNA (v2 bootloader VCP)"),
    (0x1a86, 0x7523, "CH340 - could be a NanoVNA-F"),
]


def _serial():
    try:
        import serial                                     # noqa: F401
        from serial.tools import list_ports
        return serial, list_ports
    except ImportError:
        return None, None


def candidates():
    """Every port that could plausibly be an instrument, best guess first."""
    serial, list_ports = _serial()
    if serial is None:
        return [], "pyserial is not installed on this machine"
    found = []
    for port in list_ports.comports():
        vid, pid = port.vid, port.pid
        # USB only, and let the identify step settle the rest. What counts as
        # a USB port is the machine's business rather than this module's -
        # /dev/ttyACM0 on the Pi, COM3 on Windows - so host answers it.
        if not host.usb_serial(port.device, vid):
            continue
        why = next((name for v, p, name in KNOWN if v == vid and p == pid), None)
        found.append({
            "device": port.device,
            "description": port.description or "",
            "vid": vid, "pid": pid,
            "looks_right": bool(why),
            "why": why or "not a known VNA id - worth a try if nothing else is",
        })
    found.sort(key=lambda p: not p["looks_right"])
    if not found:
        for path in host.serial_fallback():
            found.append({"device": path, "description": "", "vid": None,
                          "pid": None, "looks_right": False,
                          "why": "a serial port, with nothing saying what it is"})
    return found, None if found else "no USB serial ports at all - is it plugged in and switched on?"


def _drain(ser):
    ser.reset_input_buffer()
    ser.write(b"\r")
    ser.read_until(PROMPT)


def _ask(ser, command, timeout=READ_TIMEOUT):
    """Send one command, return its output with the echo and prompt stripped."""
    ser.timeout = timeout
    ser.reset_input_buffer()
    ser.write(command.encode("ascii") + b"\r")
    raw = ser.read_until(PROMPT)
    text = raw.decode("utf-8", "replace")
    if text.startswith(command):
        text = text[len(command):]
    return text.replace("ch> ", "").strip("\r\n \t")


def identify(device, timeout=READ_TIMEOUT):
    """Open a port and ask what it is. Returns (info, error)."""
    serial, _ = _serial()
    if serial is None:
        return None, "pyserial is not installed on this machine"
    v2 = _v2_identify(serial, device)
    if v2 is not None:
        return v2, None
    try:
        with serial.Serial(device, BAUD, timeout=timeout) as ser:
            time.sleep(0.2)                     # the CDC port needs a moment
            _drain(ser)
            info = _ask(ser, "info")
            version = _ask(ser, "version")
            if not info and not version:
                return None, ("%s answered nothing. It is a serial port but it "
                              "does not look like a NanoVNA." % device)
            return {"device": device, "info": info, "version": version}, None
    except Exception as exc:                    # port busy, gone, no permission
        return None, "could not talk to %s (%s)" % (device, exc)


def _floats(text):
    rows = []
    for line in text.splitlines():
        parts = line.split()
        try:
            rows.append([float(p) for p in parts])
        except ValueError:
            continue
    return rows


def measure(device, start_mhz, stop_mhz, points=101, timeout=SWEEP_TIMEOUT):
    """One S11 sweep, as SWR and return loss per point. Returns (sweep, error).

    The instrument is asked to scan and to hand back the frequencies with the
    data, rather than trusting that its idea of the span matches ours. When it
    will not do that - older firmware - the frequencies are asked for
    separately and, failing even that, computed from the span we requested.
    """
    # What was asked for is checked before what is installed. A sweep that
    # runs backwards is wrong whether or not pyserial is on this machine, and
    # answering a typo with "install pyserial" sends somebody to fix the wrong
    # thing - it also made this depend on which machine the tests ran on,
    # since a build with no serial library never reached the check at all.
    points = max(11, min(401, int(points)))
    start = int(round(float(start_mhz) * 1e6))
    stop = int(round(float(stop_mhz) * 1e6))
    if stop <= start:
        return None, "the stop frequency has to be above the start"
    serial, _ = _serial()
    if serial is None:
        return None, "pyserial is not installed on this machine"
    calibration = None
    v2 = _v2_sweep(serial, device, start, stop, points)
    if v2 is not None and v2[0] is None:
        return None, v2[1]
    if v2 is not None:
        pts, calibration = v2[0]
    try:
        if v2 is not None:
            raise _V2Done()
        with serial.Serial(device, BAUD, timeout=READ_TIMEOUT) as ser:
            time.sleep(0.2)
            _drain(ser)
            # mask 0b110: give me the frequency and S11, not S21 - there is
            # nothing on port 2 when you are looking at an antenna.
            body = _ask(ser, "scan %d %d %d 0b110" % (start, stop, points),
                        timeout=timeout)
            rows = _floats(body)
            if rows and len(rows[0]) >= 3:
                pts = [(r[0] / 1e6, r[1], r[2]) for r in rows]
            else:
                s11 = _floats(_ask(ser, "data 0", timeout=timeout))
                freqs = [r[0] for r in _floats(_ask(ser, "frequencies",
                                                    timeout=timeout))]
                if not s11:
                    return None, ("the instrument returned no sweep data - if "
                                  "it is mid-sweep or in a menu, let it finish "
                                  "and try again")
                if len(freqs) != len(s11):
                    freqs = [start + (stop - start) * n / (len(s11) - 1)
                             for n in range(len(s11))]
                pts = [(f / 1e6, r[0], r[1]) for f, r in zip(freqs, s11)]
    except _V2Done:
        pass
    except Exception as exc:
        return None, "could not sweep on %s (%s)" % (device, exc)

    out = []
    for mhz, re_, im in pts:
        mag = math.hypot(re_, im)
        # SWR is not defined when the magnitude reaches one: the formula
        # divides by (1 - |G|), and at or past unity more has come back than
        # went out, which no passive antenna does. Raw uncorrected data sits
        # there all the time - it is the ordinary look of an instrument with
        # no calibration loaded - so it is reported as null rather than as a
        # number, and counted, because a trace with nothing to draw needs to
        # say why instead of coming out blank.
        swr = None if mag >= 0.999999 else (1 + mag) / (1 - mag)
        out.append({
            "mhz": round(mhz, 5),
            "gx": round(re_, 5), "gy": round(im, 5),
            "gmag": round(mag, 5),
            "swr": None if swr is None else round(min(swr, 20.0), 3),
            "rl_db": round(-20 * math.log10(mag), 2) if mag > 1e-9 else 60.0,
            # Z from the reflection coefficient, which is the number an SWR
            # meter can never give and the reason to own one of these.
            "r": None, "x": None,
        })
    for row in out:
        g = complex(row["gx"], row["gy"])
        if abs(1 - g) > 1e-9:
            z = 50.0 * (1 + g) / (1 - g)
            row["r"], row["x"] = round(z.real, 2), round(z.imag, 2)
    unity = sum(1 for row in out if row["swr"] is None)
    return {"device": device, "points": len(out),
            "low_mhz": out[0]["mhz"] if out else None,
            "high_mhz": out[-1]["mhz"] if out else None,
            # How many points came back at or past total reflection. Zero is
            # an ordinary antenna; all of them is an instrument that has not
            # been calibrated, or one measuring an open port.
            "over_unity": unity,
            # For a V2, whose calibration is ELMER's: whether one was applied,
            # over what span and from when - or why not. None for an
            # instrument that calibrates itself.
            "calibration": calibration,
            "rows": out}, None


# --------------------------------------------------------------------------
# changing something on the instrument
# --------------------------------------------------------------------------
# Reading an instrument and driving one are different acts. A sweep asks a
# question and nothing is worse afterwards for having asked it. These change
# what the instrument is, and two of them destroy work: `cal reset` throws
# away the calibration that is loaded, and `save` overwrites a stored one.
# Neither can be undone except by doing the calibration again, standard by
# standard, which is ninety seconds somebody may not have where they are
# standing. So those two are marked, and the caller has to say it meant it.
#
# The shell on the other end will execute any string it is handed. This table
# is the whole of what ELMER will hand it: an action name from the page maps
# to a command built here, and nothing types through from a browser to a
# device that runs what it is given.
#
# These are the NanoVNA-H and H4 shell commands. The -F family runs different
# firmware behind a CH340 and may not answer them at all - which is not a
# thing to guess about on somebody's behalf, so a command that is not
# understood comes back as whatever the instrument said and is shown, rather
# than being reported as done.
CAL_STANDARDS = ["open", "short", "load", "isoln", "thru"]

# Slots differ by model - five on an H, seven on an H4 - so this is the widest
# range any of them has and the instrument is left to refuse the rest. Being
# wrong in that direction costs an error message; being wrong the other way
# would hide a slot somebody paid for.
MAX_SLOT = 6


def _slot(value):
    number = int(value)
    if not 0 <= number <= MAX_SLOT:
        raise ValueError("calibration slots are 0 to %d" % MAX_SLOT)
    return number


def _sweep_command(value):
    value = value or {}
    start = int(round(float(value.get("start_mhz")) * 1e6))
    stop = int(round(float(value.get("stop_mhz")) * 1e6))
    points = max(11, min(401, int(value.get("points") or 101)))
    if stop <= start:
        raise ValueError("the stop frequency has to be above the start")
    return "sweep %d %d %d" % (start, stop, points)


CONTROLS = {
    "sweep": {
        "build": _sweep_command,
        "does": "set the span the instrument itself is sweeping",
        "wants": "a start and stop in MHz",
    },
    "pause": {
        "build": lambda _: "pause",
        "does": "stop sweeping, so the trace on the screen holds still",
    },
    "resume": {
        "build": lambda _: "resume",
        "does": "start sweeping again",
    },
    "cal-step": {
        "build": lambda v: "cal %s" % _standard(v),
        "does": "measure one calibration standard",
        "wants": "which standard is on the port",
        "slow": True,
    },
    "cal-done": {
        "build": lambda _: "cal done",
        "does": "finish the calibration and apply it",
        "slow": True,
    },
    "cal-on": {
        "build": lambda _: "cal on",
        "does": "apply the calibration that is loaded",
    },
    "cal-off": {
        "build": lambda _: "cal off",
        "does": "show the raw measurement, with no correction applied",
    },
    "cal-reset": {
        "build": lambda _: "cal reset",
        "does": "throw away the calibration that is loaded",
        "destroys": "the calibration in the instrument's working memory. "
                    "Anything saved to a slot is still there; this is the one "
                    "being used now, and it comes back only by measuring the "
                    "standards again.",
        "slow": True,
    },
    "save": {
        "build": lambda v: "save %d" % _slot(v),
        "does": "store the current calibration in a slot",
        "wants": "which slot",
        "destroys": "whatever was in that slot. Slots are not a history - "
                    "there is one calibration per slot and the old one is "
                    "gone.",
    },
    "recall": {
        "build": lambda v: "recall %d" % _slot(v),
        "does": "load a stored calibration and its span",
        "wants": "which slot",
        "slow": True,
    },
}


def _standard(value):
    name = str(value or "").strip().lower()
    if name not in CAL_STANDARDS:
        raise ValueError("a calibration standard is one of: %s"
                         % ", ".join(CAL_STANDARDS))
    return name


def offered():
    """What the page may ask for, and what each one costs."""
    return [{"action": name, "does": spec["does"],
             "wants": spec.get("wants"), "destroys": spec.get("destroys"),
             "standards": CAL_STANDARDS if name == "cal-step" else None,
             "slots": MAX_SLOT if name in ("save", "recall") else None}
            for name, spec in CONTROLS.items()]


def control(device, action, value=None, confirmed=False):
    """Change one thing on the instrument, and report what it said back.

    Returns (result, error). The result carries the exact command sent and the
    instrument's own words, because most of these answer with nothing at all
    when they work - and "it said nothing" is a truthful thing to show an
    operator standing next to a screen that will show them the rest.
    """
    spec = CONTROLS.get(action)
    if spec is None:
        return None, "%s is not something ELMER asks a VNA to do" % action
    if spec.get("destroys") and not confirmed:
        return None, "that one destroys %s" % spec["destroys"]
    try:
        command = spec["build"](value)
    except (TypeError, ValueError) as exc:
        return None, str(exc) or "that is not a usable setting"

    serial, _ = _serial()
    if serial is None:
        return None, "pyserial is not installed on this machine"
    ser, is_v2 = None, False
    try:
        ser = _v2_open(serial, device, timeout=SWEEP_TIMEOUT if spec.get("slow") else READ_TIMEOUT)
        is_v2 = _is_v2(ser)
        if is_v2:
            said, error = _v2_control(ser, action, value)
            if error:
                return None, error
            return {"device": device, "action": action, "sent": "V2 " + action, "said": said,
                    "span": _v2_span(ser), "calibration": calibration_status()}, None
    except Exception as exc:
        return None, "could not talk to %s (%s)" % (device, exc)
    finally:
        if ser is not None and ser.is_open:
            if is_v2:
                _v2_release(ser)
            ser.close()
    try:
        with serial.Serial(device, BAUD, timeout=READ_TIMEOUT) as ser:
            time.sleep(0.2)
            _drain(ser)
            said = _ask(ser, command,
                        timeout=SWEEP_TIMEOUT if spec.get("slow")
                        else READ_TIMEOUT)
            # What the instrument is on now, asked rather than assumed. A
            # command that was refused, or that this firmware has never heard
            # of, leaves the span exactly where it was - and that shows here
            # rather than in a surprise three steps later.
            span = _span(ser)
    except Exception as exc:
        return None, "could not talk to %s (%s)" % (device, exc)
    return {"device": device, "action": action, "sent": command,
            "said": said, "span": span}, None


def _span(ser):
    """The first and last frequency the instrument is actually sweeping."""
    try:
        rows = _floats(_ask(ser, "frequencies"))
    except Exception:
        return None
    if not rows:
        return None
    return {"low_mhz": round(rows[0][0] / 1e6, 5),
            "high_mhz": round(rows[-1][0] / 1e6, 5), "points": len(rows)}


# --------------------------------------------------------------------------
# the NanoVNA V2 (S-A-A-2): a binary register protocol, and raw data
# --------------------------------------------------------------------------
# The V2 has no shell. Its USB port speaks a small binary protocol of
# register reads and writes (NanoRFE's "NanoVNA V2 USB protocol"):
#
#   0x00            NOP - eight of them put the parser in a known state
#   0x0d            INDICATE - the device answers one byte, "2"
#   0x10 a          READ one byte at register a      (0x11 READ2, 0x12 READ4)
#   0x18 a n        READFIFO: n records from FIFO register a
#   0x20 a v        WRITE one byte                   (0x21 WRITE2, 0x22 WRITE4,
#                                                     0x23 WRITE8, little-endian)
#
#   0x00  sweep start, Hz (u64)        0x10  sweep step, Hz (u64)
#   0x20  sweep points (u16)           0x22  values per frequency (u16)
#   0x26  USB data mode: writing 2 leaves it, and the V2's own screen and
#         sweep come back (main2.cpp, cmdRegisterWrite, since 2020-05-01)
#   0x30  the measurement FIFO - written to clear it, read in 32-byte records:
#         fwd0 re/im, rev0 re/im, rev1 re/im (six int32), the point's index
#         (u16), six bytes reserved
#   0xf0  device variant (2)           0xf1  protocol version (1)
#   0xf2  hardware revision            0xf3/0xf4  firmware major/minor
#
# Checked against an S-A-A-2 on this bench: variant 2, protocol 1, hardware
# revision 3, firmware 1.2.
#
# What comes back is raw. S11 is rev0/fwd0 straight off the bridge, with no
# correction: the calibration done on the V2's own screen is applied to its
# own display and not to what it sends over USB. So the host calibrates, and
# here the host is ELMER - an open, a short and a load measured at the end of
# the jumper that goes on the antenna, the three error terms worked out at
# every point, kept on the unit, and applied to every sweep over that span.
# Until that is done, every number the V2 gives is said to be uncalibrated.
#
# Any register write puts the V2 in "USB MODE": its screen stops plotting and
# says so, and its own menus wait. Nothing over USB draws on that screen or
# sets what it shows - there are no registers for traces, markers or format -
# but the V2 can be handed back, and ELMER does that at the end of every
# operation, so the instrument is only ever ELMER's while ELMER is measuring.
V2_IDS = [(0x04b4, 0x0008)]
KNOWN.append((0x04b4, 0x0008, "NanoVNA V2 / S-A-A-2"))
V2_RECORD = 32
V2_MAX_READ = 255
V2_MAX_POINTS = 1024


def _v2_open(serial, device, timeout=READ_TIMEOUT):
    ser = serial.Serial(device, BAUD, timeout=timeout)
    ser.write(b"\x00" * 8)
    time.sleep(0.05)
    ser.reset_input_buffer()
    return ser


def _is_v2(ser):
    """Whether what is on the port answers INDICATE as a V2 does."""
    ser.reset_input_buffer()
    ser.write(b"\x0d")
    return ser.read(1) == b"2"


def _v2_read1(ser, addr):
    ser.write(bytes([0x10, addr]))
    b = ser.read(1)
    return b[0] if b else None


def _v2_read4(ser, addr):
    ser.write(bytes([0x12, addr]))
    b = ser.read(4)
    return int.from_bytes(b, "little") if len(b) == 4 else None


def _v2_write2(ser, addr, value):
    ser.write(bytes([0x21, addr]) + int(value).to_bytes(2, "little"))


def _v2_write8(ser, addr, value):
    ser.write(bytes([0x23, addr]) + int(value).to_bytes(8, "little"))


def _v2_span(ser):
    """The sweep the V2 is set to, read back from its registers."""
    start = (_v2_read4(ser, 0x00) or 0) | ((_v2_read4(ser, 0x04) or 0) << 32)
    step = (_v2_read4(ser, 0x10) or 0) | ((_v2_read4(ser, 0x14) or 0) << 32)
    ser.write(bytes([0x11, 0x20]))
    b = ser.read(2)
    points = int.from_bytes(b, "little") if len(b) == 2 else 0
    if not points or not start:
        return None
    return {"start_hz": start, "step_hz": step, "points": points,
            "low_mhz": round(start / 1e6, 5),
            "high_mhz": round((start + step * (points - 1)) / 1e6, 5)}


def _v2_set_span(ser, start_hz, stop_hz, points):
    points = max(2, min(V2_MAX_POINTS, int(points)))
    step = (int(stop_hz) - int(start_hz)) // (points - 1)
    _v2_write8(ser, 0x00, int(start_hz))
    _v2_write8(ser, 0x10, step)
    _v2_write2(ser, 0x20, points)
    _v2_write2(ser, 0x22, 1)
    return _v2_span(ser)


def _v2_release(ser):
    """Give the V2 its screen back. A failure here costs only the screen -
    the measurement is already in hand - so it is logged, not raised."""
    try:
        ser.write(bytes([0x20, 0x26, 0x02]))
        ser.flush()
    except Exception as exc:   # noqa: BLE001 - on the way out; the port may already be gone
        log.warning("could not hand the V2 its screen back: %s", exc)


def _v2_raw(ser, points, timeout=SWEEP_TIMEOUT):
    """One raw S11 sweep: the rev0/fwd0 ratio at each point, by its index."""
    # The V2 shares one FIFO between its own screen's sweep and USB. Handed
    # back after the last operation, it has been sweeping its own span; a
    # write to the points register switches the hardware to ELMER's span at
    # once, and the pause lets the sweep in flight land before the clear.
    _v2_write2(ser, 0x20, points)
    time.sleep(0.15)
    ser.write(bytes([0x20, 0x30, 0x00]))           # clear the FIFO: a fresh sweep
    got = {}
    deadline = time.monotonic() + timeout
    while len(got) < points and time.monotonic() < deadline:
        n = min(V2_MAX_READ, points - len(got))
        ser.write(bytes([0x18, 0x30, n]))
        data = ser.read(n * V2_RECORD)
        for k in range(len(data) // V2_RECORD):
            rec = data[k * V2_RECORD:(k + 1) * V2_RECORD]
            v = [int.from_bytes(rec[j:j + 4], "little", signed=True) for j in range(0, 24, 4)]
            index = int.from_bytes(rec[24:26], "little")
            fwd = complex(v[0], v[1])
            if index < points and abs(fwd) > 0:
                got[index] = complex(v[2], v[3]) / fwd
    if len(got) < points:
        return None
    return [got[i] for i in range(points)]


# --- ELMER's own calibration, for the V2 --------------------------------------

def _cal_path():
    from . import paths
    return paths.STATE / "vna_v2_cal.json"


def _cal_load():
    import json
    try:
        return json.loads(_cal_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        log.warning("the V2 calibration at %s could not be read: %s", _cal_path(), exc)
        return {}


def _cal_save(data):
    import json
    path = _cal_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(path)
        return True
    except OSError as exc:
        log.error("the V2 calibration could not be saved to %s: %s", path, exc)
        return False


def sol_terms(m_open, m_short, m_load):
    """The one-port error terms from an ideal open (+1), short (-1) and load
    (0): e00 the directivity, e11 the source match, and e10e01 the tracking.
    The measured reflection m and the real one G are related by
    m = e00 + e10e01 G / (1 - e11 G)."""
    e00 = m_load
    e11 = (m_open + m_short - 2 * m_load) / (m_open - m_short)
    track = (m_open - m_load) * (1 - e11)
    return e00, e11, track


# A real open and a real short sit at opposite ends of what the bridge can
# read, so their raw readings differ by about twice the tracking term at
# every point; a load sits between them. Two sweeps of the same thing differ
# only by noise. A calibration built from three readings of whatever happened
# to be on the port would correct every later sweep into nonsense, quietly -
# so the standards are checked before they are used, and refused with which
# one looks wrong.
STANDARD_APART = 0.5       # open and short must differ by at least half their mean size
LOAD_APART = 0.2           # the load must sit at least this far from each, in the same terms
STANDARD_SHARE = 0.8       # ...at this share of the points


def standards_look_wrong(opens, shorts, loads):
    """Why these three readings cannot be an open, a short and a load, or None."""
    n = len(opens)
    if not n or n != len(shorts) or n != len(loads):
        return "the three standards were not measured over the same points"
    apart = load_off = 0
    for o, s, ld in zip(opens, shorts, loads):
        mo, ms, ml = complex(*o), complex(*s), complex(*ld)
        scale = max(1e-9, (abs(mo) + abs(ms)) / 2)
        if abs(mo - ms) >= STANDARD_APART * scale:
            apart += 1
        if min(abs(ml - mo), abs(ml - ms)) >= LOAD_APART * scale:
            load_off += 1
    if apart < STANDARD_SHARE * n:
        return ("the OPEN and the SHORT read nearly the same - the same thing was on the port for both, "
                "or a standard was not connected. Measure them again.")
    if load_off < STANDARD_SHARE * n:
        return ("the LOAD reads like the OPEN or the SHORT - check that the 50 ohm load is the one "
                "on the port, and measure it again.")
    return None


def sol_correct(m, terms):
    """The real reflection from a measured one, through the error terms."""
    e00, e11, track = terms
    d = m - e00
    return d / (track + e11 * d)


def _cal_terms_at(cal, hz):
    """The error terms at a frequency, straight between the calibration's own
    points; None outside its span - a calibration is not stretched."""
    start, step, pts = cal["start_hz"], cal["step_hz"], cal["points"]
    if hz < start - 1 or hz > start + step * (pts - 1) + 1:
        return None
    x = (hz - start) / step if step else 0.0
    i = min(pts - 2, max(0, int(x)))
    t = x - i
    a, b = cal["terms"][i], cal["terms"][i + 1]
    return tuple(complex(a[2 * k], a[2 * k + 1]) * (1 - t) + complex(b[2 * k], b[2 * k + 1]) * t
                 for k in range(3))


def calibration_status():
    """What ELMER holds for the V2: whether there is a calibration, over what
    span, made when, whether it is applied, and which standards of one in
    progress have been measured."""
    data = _cal_load()
    cal = data.get("cal")
    pending = data.get("pending") or {}
    return {"has": bool(cal), "applied": bool(cal) and data.get("apply", True),
            "made": cal.get("made") if cal else None,
            "low_mhz": round(cal["start_hz"] / 1e6, 5) if cal else None,
            "high_mhz": round((cal["start_hz"] + cal["step_hz"] * (cal["points"] - 1)) / 1e6, 5) if cal else None,
            "points": cal["points"] if cal else None,
            "measured": [s for s in ("open", "short", "load") if s in pending]}


def _v2_control(ser, action, value):
    """The V2's answer to each of the page's controls. Returns (said, error)."""
    from datetime import datetime, timezone
    if action == "sweep":
        start = int(round(float(value.get("start_mhz")) * 1e6))
        stop = int(round(float(value.get("stop_mhz")) * 1e6))
        if stop <= start:
            return None, "the stop frequency has to be above the start"
        span = _v2_set_span(ser, start, stop, value.get("points") or 101)
        if not span:
            return "set, but the V2 did not read its span back", None
        return "set: %s to %s MHz, %d points" % (span["low_mhz"], span["high_mhz"], span["points"]), None
    if action in ("pause", "resume", "save", "recall"):
        return None, ("a V2 has no %s over USB - its calibration is ELMER's, kept on this unit, "
                      "and it sweeps when asked" % action)
    data = _cal_load()
    if action == "cal-step":
        standard = _standard(value)
        if standard not in ("open", "short", "load"):
            return None, "an antenna needs OPEN, SHORT and LOAD; %s is for two-port work" % standard.upper()
        span = _v2_span(ser)
        if not span:
            return None, "set the span first - the V2 is not sweeping anything ELMER can read"
        raw = _v2_raw(ser, span["points"])
        if raw is None:
            return None, "the V2 did not return a full sweep - try again"
        pending = data.get("pending") or {}
        if pending.get("span") != span:
            pending = {"span": span}                # a new span starts a new calibration
        pending[standard] = [[g.real, g.imag] for g in raw]
        data["pending"] = pending
        if not _cal_save(data):
            return None, "measured, but it could not be kept on this unit - see the log"
        done = [s for s in ("open", "short", "load") if s in pending]
        return "%s measured over %s-%s MHz; %d of open, short and load done" % (
            standard.upper(), span["low_mhz"], span["high_mhz"], len(done)), None
    if action == "cal-done":
        pending = data.get("pending") or {}
        missing = [s for s in ("open", "short", "load") if s not in pending]
        if missing:
            return None, "still to measure: %s" % ", ".join(s.upper() for s in missing)
        span = pending["span"]
        why = standards_look_wrong(pending["open"], pending["short"], pending["load"])
        if why:
            return None, why
        terms = []
        for o, s, ld in zip(pending["open"], pending["short"], pending["load"]):
            mo, ms, ml = complex(*o), complex(*s), complex(*ld)
            e = sol_terms(mo, ms, ml)
            terms.append([e[0].real, e[0].imag, e[1].real, e[1].imag, e[2].real, e[2].imag])
        data["cal"] = {"made": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                       "start_hz": span["start_hz"], "step_hz": span["step_hz"],
                       "points": span["points"], "terms": terms}
        data["apply"] = True
        data.pop("pending", None)
        if not _cal_save(data):
            return None, "worked out, but it could not be kept on this unit - see the log"
        log.info("V2 calibration made over %s-%s MHz, %d points",
                 span["low_mhz"], span["high_mhz"], span["points"])
        return "calibrated over %s-%s MHz, %d points, and applied to every sweep over that span" % (
            span["low_mhz"], span["high_mhz"], span["points"]), None
    if action in ("cal-on", "cal-off"):
        if not data.get("cal"):
            return None, "there is no calibration yet - measure OPEN, SHORT and LOAD, then DONE"
        data["apply"] = action == "cal-on"
        _cal_save(data)
        return ("applying ELMER's calibration" if data["apply"] else "showing the raw bridge readings"), None
    if action == "cal-reset":
        data.pop("cal", None)
        data.pop("pending", None)
        _cal_save(data)
        return "ELMER's calibration for the V2 is gone", None
    return None, "%s is not something ELMER asks a V2 to do" % action


class _V2Done(Exception):
    """The V2 has already swept; skip the shell's way of doing it."""


def _v2_identify(serial, device):
    """The V2's account of itself, or None when it is not a V2."""
    ser, is_v2 = None, False
    try:
        ser = _v2_open(serial, device)
        is_v2 = _is_v2(ser)
        if not is_v2:
            return None
        variant, proto, hw = _v2_read1(ser, 0xF0), _v2_read1(ser, 0xF1), _v2_read1(ser, 0xF2)
        major, minor = _v2_read1(ser, 0xF3), _v2_read1(ser, 0xF4)
        cal = calibration_status()
        if major == 0xFF:
            # The bootloader answers on the same id and reads 0xFF here; it
            # does not measure, and it is how firmware is written.
            return {"device": device, "family": "v2", "bootloader": True,
                    "info": "a NanoVNA V2 in its bootloader - it will not sweep until it is restarted",
                    "version": "bootloader", "calibration": cal}
        model = V2_MODELS.get(hw, "a NanoVNA V2 of hardware revision %s ELMER does not know" % hw)
        return {"device": device, "family": "v2", "hardware_revision": hw, "model": model,
                "firmware": [major, minor],
                "info": "%s - device variant %s, protocol %s, hardware revision %s" % (model, variant, proto, hw),
                "version": "firmware %s.%s" % (major, minor),
                "calibration": cal, "updates": firmware_status(hw, major, minor)}
    except Exception as exc:   # noqa: BLE001 - a port that is busy or gone is "not a V2 here"
        log.info("V2 probe on %s: %s", device, exc)
        return None
    finally:
        if ser is not None and ser.is_open:
            if is_v2:                  # never into a shell instrument
                _v2_release(ser)
            ser.close()


def _v2_sweep(serial, device, start, stop, points):
    """None when the device is not a V2; ((pts, calibration), None) when it
    swept; (None, why) when it is a V2 and the sweep failed."""
    ser, is_v2 = None, False
    try:
        ser = _v2_open(serial, device)
        is_v2 = _is_v2(ser)
        if not is_v2:
            return None
        span = _v2_set_span(ser, start, stop, points)
        if not span:
            return (None, "the V2 would not take the sweep it was asked for")
        raw = _v2_raw(ser, span["points"])
        if raw is None:
            return (None, "the V2 did not return a full sweep - is it mid-menu? try again")
    except Exception as exc:   # noqa: BLE001 - reported to the page as the reason
        return (None, "could not sweep on %s (%s)" % (device, exc))
    finally:
        if ser is not None and ser.is_open:
            if is_v2:                  # never into a shell instrument
                _v2_release(ser)
            ser.close()
    data = _cal_load()
    cal = data.get("cal") if data.get("apply", True) else None
    pts, outside = [], 0
    for n, g in enumerate(raw):
        hz = span["start_hz"] + span["step_hz"] * n
        terms = _cal_terms_at(cal, hz) if cal else None
        if terms is not None:
            g = sol_correct(g, terms)
        elif cal:
            outside += 1
        pts.append((hz / 1e6, g.real, g.imag))
    status = calibration_status()
    if not data.get("cal"):
        status["note"] = ("uncalibrated - these are the V2's raw bridge readings. Measure OPEN, SHORT "
                          "and LOAD below, then DONE, before believing any number here.")
    elif not data.get("apply", True):
        status["note"] = "uncalibrated by choice - showing the raw readings"
    elif outside:
        status["note"] = ("%d of %d points lie outside the calibrated %s-%s MHz and are raw"
                          % (outside, len(raw), status["low_mhz"], status["high_mhz"]))
    status["outside"] = outside
    return ((pts, status), None)


# --- which V2 it is, and its firmware ------------------------------------------
#
# The hardware revision register is set from each board's BOARD_REVISION in
# the vendor's firmware source (github.com/nanovna-v2/NanoVNA2-firmware,
# board_*/board.hpp; main2.cpp writes it to 0xF2). "S-A-A-2" is the family's
# name; the model is this.
V2_MODELS = {
    0: "NanoVNA V2_0",
    1: "NanoVNA V2_1",
    2: "NanoVNA V2_2 (S-A-A-2)",
    3: "NanoVNA V2 Plus (V2.3)",
    4: "NanoVNA V2 Plus4",
}

# The official images ELMER knows of, by hardware revision. There is no
# machine-readable index - the GitHub releases stop at 20201013 and carry no
# files - so this table is kept by hand from the vendor's firmware page
# (nanorfe.com/nanovna-firmware.html), each file fetched and its SHA-256
# taken here, since the vendor publishes none (2026-10-01). Releases are
# named by date; the major.minor the instrument reports is not a release
# name, and the 20210726 build is believed to report 1.2 as 20201013 does,
# so the instrument alone cannot say which of the two it has.
V2_FIRMWARE = {
    3: [
        {"release": "20201013", "status": "stable", "reports": "1.2",
         "url": "https://nanorfe.com/downloads/20201013/nanovna-v2-20201013-v2plus.bin",
         "bytes": 114616,
         "sha256": "b8e4a2825aadfb84a61e2ab8c6920f630f2b742cd3153254eca15a59303d244e",
         "notes": "the first release with Plus4 support; 7 calibration save slots, CALIBRATE > RESET ALL, "
                  "a PAUSE SWEEP fix and AGC fixes"},
        {"release": "20210726", "status": "experimental", "reports": "1.2 (believed; not confirmed)",
         "url": "https://nanorfe.com/downloads/20210726/nanovna-v2-20210726-v2plus.bin",
         "bytes": 111036,
         "sha256": "721e4d33719ff78698db515a2dbcd5fdc10cd93649c50ecb189b90830209f3b6",
         "notes": "no release notes published; the public commits before it change averaging, speed up the "
                  "V2 Plus's timings and fix a display flicker"},
    ],
}
V2_FIRMWARE_PAGE = "https://nanorfe.com/nanovna-firmware.html"


def firmware_status(hw, major, minor):
    """What ELMER can say about this V2's firmware without writing anything:
    the official releases it knows for this model, which of them the
    reported version could be, and what is newer. Offline - this is the
    table above, not a fetch."""
    known = V2_FIRMWARE.get(hw)
    reported = "%s.%s" % (major, minor)
    if not known:
        return {"known": False, "reported": reported, "page": V2_FIRMWARE_PAGE,
                "words": "ELMER does not keep a firmware list for this model; the vendor's page has it."}
    could_be = [r["release"] for r in known if r["reports"].startswith(reported)]
    stable = [r for r in known if r["status"] == "stable"][-1]
    newest = known[-1]
    if could_be:
        words = ("It reports %s, which the official %s build%s report%s - the instrument cannot say which. "
                 % (reported, " and ".join(could_be), "s" if len(could_be) > 1 else "", "" if len(could_be) > 1 else "s"))
    else:
        words = "It reports %s, which no official release ELMER knows of reports. " % reported
    words += ("The stable release for this model is %s; the newest is %s, which the vendor marks %s."
              % (stable["release"], newest["release"], newest["status"]))
    return {"known": True, "reported": reported, "could_be": could_be, "releases": known,
            "stable": stable["release"], "newest": newest["release"], "page": V2_FIRMWARE_PAGE,
            "words": words}


def firmware_page_check(hw, fetch=None):
    """Read the vendor's firmware page - on the operator's press, never on its
    own - and say whether it lists an image for this model that ELMER's table
    does not know, which is how a new release would first show. Returns
    (result, error); a page that cannot be read is said, not guessed past."""
    import re
    import urllib.request
    token = {3: "v2plus.bin", 2: "v2_2.bin", 4: "v2plus4"}.get(hw)
    if token is None:
        return None, "ELMER does not know which files on the vendor's page are this model's"
    try:
        if fetch is None:
            req = urllib.request.Request(V2_FIRMWARE_PAGE, headers={"User-Agent": "ELMER"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", "replace")
        else:
            html = fetch(V2_FIRMWARE_PAGE)
    except (OSError, ValueError) as exc:
        log.warning("could not read the NanoVNA firmware page %s: %s", V2_FIRMWARE_PAGE, exc)
        return None, "the vendor's firmware page could not be read (%s) - ELMER's own list still stands" % exc
    links = sorted(set(re.findall(r'href="([^"]*%s[^"]*)"' % re.escape(token), html)))
    known = {r["url"].rsplit("/", 1)[-1] for r in V2_FIRMWARE.get(hw, [])}
    names = [link.rsplit("/", 1)[-1] for link in links]
    new = [n for n in names if n not in known]
    return {"listed": names, "new": new,
            "words": ("The vendor's page lists %s for this model, which ELMER does not know yet - read its notes "
                      "there before anything else." % ", ".join(new)) if new else
                     ("The vendor's page lists nothing for this model that ELMER does not already know.")}, None
