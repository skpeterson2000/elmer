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
import glob
import logging
import math
import time

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
        # A NanoVNA is a USB device. The Pi's own on-board UARTs turn up in
        # this list too, and on this rig one of them may have a GPS on it -
        # opening that and sending "info" at it is nobody's idea of a good
        # time. USB only, and let the identify step settle the rest.
        if vid is None and not (port.device.startswith("/dev/ttyACM")
                                or port.device.startswith("/dev/ttyUSB")):
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
        for path in sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")):
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
    serial, _ = _serial()
    if serial is None:
        return None, "pyserial is not installed on this machine"
    points = max(11, min(401, int(points)))
    start = int(round(float(start_mhz) * 1e6))
    stop = int(round(float(stop_mhz) * 1e6))
    if stop <= start:
        return None, "the stop frequency has to be above the start"
    try:
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
    except Exception as exc:
        return None, "could not sweep on %s (%s)" % (device, exc)

    out = []
    for mhz, re_, im in pts:
        mag = math.hypot(re_, im)
        swr = None if mag >= 0.999999 else (1 + mag) / (1 - mag)
        out.append({
            "mhz": round(mhz, 5),
            "gx": round(re_, 5), "gy": round(im, 5),
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
    return {"device": device, "points": len(out),
            "low_mhz": out[0]["mhz"] if out else None,
            "high_mhz": out[-1]["mhz"] if out else None,
            "rows": out}, None
