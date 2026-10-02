#!/usr/bin/env python3
"""The NanoVNA V2 (S-A-A-2): its binary protocol, and ELMER's calibration of it.

    python3 tests/test_nanovna_v2.py

A V2 has no shell; it reads and writes registers over a binary protocol, and
what it sends is raw - its on-screen calibration is not applied to USB data.
So ELMER calibrates it: an open, a short and a load measured at the jumper,
the error terms worked out at every point, kept on the unit, applied to every
sweep over that span.

No instrument is needed: a simulated V2 here speaks the protocol and measures
whatever is "on the port" through a bridge with known, imperfect error terms -
which is what makes the calibration testable, because the right answer is
known. What is held here:

  - a V2 is found by its USB id and identified by its own answer;
  - an uncalibrated sweep comes back, and says it is uncalibrated;
  - OPEN, SHORT, LOAD and DONE make a calibration, kept on the unit, and a
    sweep of a known load then reads that load, not the bridge's raw guess;
  - three readings of the same thing are refused, and so is a load that is
    not one; a sweep past the calibrated span says how much of it is raw;
  - every operation hands the V2 its own screen back when it is done, and
    nothing of the kind is sent to an instrument with a shell;
  - an instrument with a shell is still driven as before.
"""
import cmath
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import nanovna as N  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# The simulated bridge: what it reads for a true reflection G at frequency f.
E00 = lambda f: 0.08 + 0.03j * f / 14e6           # noqa: E731  directivity, drifting with frequency
E11 = lambda f: 0.12 - 0.04j                       # noqa: E731  source match
TRACK = lambda f: 0.21 * cmath.exp(-1j * f / 20e6)  # noqa: E731  tracking, turning with frequency


class Bench:
    """What is on the end of the jumper: a reflection coefficient, or a
    function of frequency giving one."""
    def __init__(self):
        self.load = 0.0

    def gamma(self, f):
        return self.load(f) if callable(self.load) else self.load


class FakeV2:
    """Enough of a V2 to be driven: registers, the FIFO, INDICATE."""
    def __init__(self, bench):
        self.bench, self.regs, self.out, self.is_open = bench, {0xF0: 2, 0xF1: 1, 0xF2: 3, 0xF3: 1, 0xF4: 2}, b"", True
        self.next_index = 0
        self.usb_mode = False                             # any write takes the screen; 0x26 = 2 gives it back

    def _u(self, addr, n):
        return int.from_bytes(bytes(self.regs.get(addr + k, 0) for k in range(n)), "little")

    def _put(self, addr, value, n):
        for k, b in enumerate(int(value).to_bytes(n, "little")):
            self.regs[addr + k] = b

    def write(self, data):
        i = 0
        while i < len(data):
            op = data[i]
            if op == 0x00:
                i += 1
            elif op == 0x0D:
                self.out += b"2"
                i += 1
            elif op in (0x10, 0x11, 0x12):
                n = {0x10: 1, 0x11: 2, 0x12: 4}[op]
                self.out += self._u(data[i + 1], n).to_bytes(n, "little")
                i += 2
            elif op in (0x20, 0x21, 0x22, 0x23):
                n = {0x20: 1, 0x21: 2, 0x22: 4, 0x23: 8}[op]
                addr = data[i + 1]
                value = int.from_bytes(data[i + 2:i + 2 + n], "little")
                self.usb_mode = not (addr == 0x26 and value == 2)
                if addr == 0x30:
                    self.next_index = 0                   # writing the FIFO clears it
                else:
                    self._put(addr, value, n)
                i += 2 + n
            elif op == 0x18:
                n = data[i + 2]
                start, step, pts = self._u(0x00, 8), self._u(0x10, 8), self._u(0x20, 2)
                for _ in range(n):
                    idx = self.next_index % pts
                    self.next_index += 1
                    f = start + step * idx
                    g = self.bench.gamma(f)
                    m = E00(f) + TRACK(f) * g / (1 - E11(f) * g)
                    fwd = complex(1_000_000, 0)
                    rev = m * fwd
                    vals = [fwd.real, fwd.imag, rev.real, rev.imag, 0, 0]
                    rec = b"".join(int(round(v)).to_bytes(4, "little", signed=True) for v in vals)
                    self.out += rec + idx.to_bytes(2, "little") + b"\0" * 6
                i += 3
            else:
                i += 1
        return len(data)

    def read(self, n):
        got, self.out = self.out[:n], self.out[n:]
        return got

    def flush(self):
        pass

    def reset_input_buffer(self):
        self.out = b""

    def close(self):
        self.is_open = False


class Port:
    def __init__(self, device, vid, pid):
        self.device, self.vid, self.pid, self.description = device, vid, pid, "USB Serial Device"


def install_fake(bench, vid=0x04B4, pid=0x0008):
    # One instrument, opened again and again: a V2 keeps its registers - its
    # span - between one opening of the port and the next.
    device = FakeV2(bench)

    class serial:  # noqa: N801 - stands in for the module
        @staticmethod
        def Serial(port, baud, timeout=None):  # noqa: N802
            device.out, device.is_open = b"", True
            return device

    class list_ports:  # noqa: N801
        @staticmethod
        def comports():
            return [Port("COM10", vid, pid)]
    N._serial = lambda: (serial, list_ports)
    N.host.usb_serial = lambda device, vid: True


def z_gamma(z):
    return (z - 50) / (z + 50)


def main():
    bench = Bench()
    install_fake(bench)

    print("-- found by its USB id, identified by its own answer --")
    ports, err = N.candidates()
    check("the S-A-A-2's id is known", (ports[0]["looks_right"], ports[0]["why"]), (True, "NanoVNA V2 / S-A-A-2"))
    info, err = N.identify("COM10")
    check("it identifies as a V2, from its registers",
          (info["family"], "variant 2, protocol 1, hardware revision 3" in info["info"], info["version"]),
          ("v2", True, "firmware 1.2"))
    check("  with no calibration yet", info["calibration"]["has"], False)

    print("\n-- uncalibrated, it says so --")
    bench.load = z_gamma(75)
    got, err = N.measure("COM10", 14.0, 14.35, 51)
    check("a sweep comes back, every point", (err, got["points"]), (None, 51))
    check("  and says it is raw", "uncalibrated" in got["calibration"]["note"], True)
    raw_r = got["rows"][25]["r"]
    check("  where the raw bridge reading is far from the 75 ohms on the port", abs(raw_r - 75) > 10, True)

    print("\n-- three readings of the same thing are refused --")
    N.control("COM10", "sweep", {"start_mhz": 14.0, "stop_mhz": 14.35, "points": 51})
    for std in ("open", "short", "load"):
        N.control("COM10", "cal-step", std)
    check("OPEN, SHORT and LOAD with nothing changed are not a calibration",
          "read nearly the same" in (N.control("COM10", "cal-done")[1] or ""), True)
    bench.load = 1.0
    N.control("COM10", "cal-step", "open")
    bench.load = -1.0
    N.control("COM10", "cal-step", "short")
    bench.load = 1.0
    N.control("COM10", "cal-step", "load")
    check("and an OPEN measured as the LOAD is caught", "LOAD reads like" in (N.control("COM10", "cal-done")[1] or ""),
          True)

    print("\n-- the real standards make a calibration --")
    for std, g in (("open", 1.0), ("short", -1.0), ("load", 0.0)):
        bench.load = g
        r, e = N.control("COM10", "cal-step", std)
        check(f"{std.upper()} is measured", e, None)
    r, e = N.control("COM10", "cal-done")
    check("DONE makes and keeps it", (e, r["calibration"]["has"], r["calibration"]["applied"]), (None, True, True))
    check("  on this unit, in the state folder", N._cal_path().exists(), True)

    print("\n-- and a sweep then reads what is really on the port --")
    for z in (75 + 0j, 25 - 30j, 50 + 50j):
        bench.load = z_gamma(z)
        got, err = N.measure("COM10", 14.0, 14.35, 51)
        row = got["rows"][25]
        check(f"  {z.real:g}{z.imag:+g}j ohms reads as itself",
              (abs(row["r"] - z.real) < 0.6, abs(row["x"] - z.imag) < 0.6), (True, True))
    check("  and says the calibration was applied, with no note", got["calibration"].get("note"), None)
    bench.load = z_gamma(50)
    check("a 50 ohm load reads SWR 1.0", N.measure("COM10", 14.0, 14.35, 51)[0]["rows"][10]["swr"] < 1.02, True)

    print("\n-- past the calibrated span, it says how much is raw --")
    got, err = N.measure("COM10", 14.0, 14.7, 51)
    check("the half beyond 14.35 MHz is counted and said", got["calibration"]["outside"] > 20
          and "outside the calibrated" in got["calibration"]["note"], True)

    print("\n-- the controls a V2 does not have are said, not faked --")
    check("no slots, no pause", [bool(N.control("COM10", a, 1)[1]) for a in ("save", "recall", "pause")],
          [True, True, True])
    check("throwing the calibration away still asks first",
          N.control("COM10", "cal-reset")[1].startswith("that one destroys"), True)
    r, e = N.control("COM10", "cal-reset", confirmed=True)
    check("  and confirmed, it is gone", (e, N.calibration_status()["has"]), (None, False))

    print("\n-- which V2, and its firmware, without writing anything --")
    info, _ = N.identify("COM10")
    check("hardware revision 3 is the V2 Plus, not the V2_2",
          (info["hardware_revision"], info["model"]), (3, "NanoVNA V2 Plus (V2.3)"))
    up = info["updates"]
    check("1.2 could be either official build, and it says the instrument cannot tell",
          (up["could_be"], "cannot say which" in up["words"]), (["20201013", "20210726"], True))
    check("  the stable one and the newest are named", (up["stable"], up["newest"]), ("20201013", "20210726"))
    check("  every known image carries its size and SHA-256",
          all(r["bytes"] > 100000 and len(r["sha256"]) == 64 for r in up["releases"]), True)
    page = ('<a href="downloads/20201013/nanovna-v2-20201013-v2plus.bin">x</a>'
            '<a href="downloads/20210726/nanovna-v2-20210726-v2plus.bin">y</a>'
            '<a href="downloads/20991231/nanovna-v2-20991231-v2plus.bin">z</a>'
            '<a href="downloads/20251215/nanorfe-20251215-v2plus45.bin">plus4</a>')
    got, err = N.firmware_page_check(3, fetch=lambda url: page)
    check("the vendor's page, read on a press, shows a release ELMER does not know",
          (err, got["new"]), (None, ["nanovna-v2-20991231-v2plus.bin"]))
    check("  and not another model's image as this one's", "nanorfe-20251215-v2plus45.bin" in got["listed"], False)

    def unreachable(url):
        raise OSError("no network")
    got, err = N.firmware_page_check(3, fetch=unreachable)
    check("a page that cannot be read is said, and the table still stands",
          (got, "could not be read" in err), (None, True))
    device = FakeV2(bench)
    device.regs[0xF3] = 0xFF

    class BootSerial:
        @staticmethod
        def Serial(port, baud, timeout=None):  # noqa: N802
            device.out = b""
            return device
    real = N._serial
    N._serial = lambda: (BootSerial, None)
    info, _ = N.identify("COM10")
    N._serial = real
    check("a V2 in its bootloader is recognised as one, and not offered a sweep",
          (info["bootloader"], "bootloader" in info["info"]), (True, True))

    print("\n-- its screen is its own again when ELMER is done --")
    bench.load = z_gamma(50)
    real_dev = FakeV2(bench)

    def reopen(device):
        def open_it(*a, **k):
            device.out, device.is_open = b"", True
            return device
        return lambda: (type("s", (), {"Serial": staticmethod(open_it)}), None)
    N._serial = reopen(real_dev)
    for what, run in (("a sweep", lambda: N.measure("COM10", 14.0, 14.35, 51)),
                      ("setting the span", lambda: N.control("COM10", "sweep",
                                                             {"start_mhz": 14.0, "stop_mhz": 14.35, "points": 51})),
                      ("a calibration step", lambda: N.control("COM10", "cal-step", "load")),
                      ("asking what it is", lambda: N.identify("COM10"))):
        real_dev.usb_mode = True
        run()
        check("after %s, the V2 is out of USB MODE" % what, real_dev.usb_mode, False)
    N.control("COM10", "cal-reset", confirmed=True)

    class ShellPort(FakeV2):
        def write(self, data):
            self.sent = getattr(self, "sent", b"") + data
            return len(data)
    shell_dev = ShellPort(bench)
    N._serial = reopen(shell_dev)
    N._v2_identify(N._serial()[0], "COM10")
    check("and a shell instrument is never sent the hand-back", b"\x20\x26\x02" in shell_dev.sent, False)
    N._serial = real

    print("\n-- an instrument with a shell is not taken for a V2 --")

    class Shell(FakeV2):
        def write(self, data):
            if b"\x0d" in data:
                self.out += b"\r\nch> "
            return len(data)
    shell_ser = Shell(bench)
    check("a ch> prompt is not the V2's '2'", N._is_v2(shell_ser), False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
