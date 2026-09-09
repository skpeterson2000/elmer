#!/usr/bin/env python3
"""The handful of things that differ by machine, checked on either machine.

    python3 tests/test_host.py

This file is meant to pass on a Pi and on Windows, which is the whole point of
the module it checks: if the two platforms disagree about what a serial port
is called, or about how the program is stopped, that disagreement should be
written down in one place and tested rather than discovered by somebody whose
install will not start.

Most of it is forced both ways deliberately - the Windows rules are exercised
on Linux and the other way round - because a rule that is only ever run on the
machine it was written for is not a rule, it is a habit.

The exception is stopping. Forcing the POSIX path while actually on Windows
would call os.kill, which on Windows does not raise anything: it terminates
the process. So that one is asked only where it can be answered, and the
Windows mechanism - which is portable - is proved on whatever this is.
"""
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import host  # noqa: E402

FAILS = []
REALLY_WINDOWS = host.WINDOWS


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def as_windows(windows):
    """Answer as the other machine for a moment."""
    host.WINDOWS = windows


def main():
    try:
        return run()
    finally:
        host.WINDOWS = REALLY_WINDOWS


def run():
    print("\n-- what counts as a serial port, on each machine --")
    as_windows(False)
    check("posix takes a device path", host.is_serial_device("/dev/ttyACM0"),
          True)
    check("  and refuses a COM name", host.is_serial_device("COM3"), False)
    as_windows(True)
    check("windows takes COM3", host.is_serial_device("COM3"), True)
    check("  and COM10, which needs the prefix",
          host.is_serial_device(r"\\.\COM10"), True)
    check("  and is not case-fussy", host.is_serial_device("com7"), True)
    check("  and refuses a device path",
          host.is_serial_device("/dev/ttyACM0"), False)

    print("\n-- and what is refused everywhere, since this opens what it is "
          "given --")
    for junk in ("", None, "COM", "COMx", "../../etc/passwd", "/dev",
                 "COM3; shutdown"):
        as_windows(True)
        windows = host.is_serial_device(junk)
        as_windows(False)
        check(f"{junk!r}", [windows, host.is_serial_device(junk)],
              [False, False])

    print("\n-- a USB id settles it; a name only settles it on POSIX --")
    as_windows(False)
    check("a port with a USB id", host.usb_serial("/dev/ttyS0", 0x0483), True)
    check("ttyACM with no id is still USB",
          host.usb_serial("/dev/ttyACM0", None), True)
    check("  but the Pi's own UART is not, and may have a GPS on it",
          host.usb_serial("/dev/ttyS0", None), False)
    as_windows(True)
    check("windows: a COM port with a USB id", host.usb_serial("COM3", 0x0483),
          True)
    check("  and one without is a built-in port, left alone",
          host.usb_serial("COM1", None), False)

    print("\n-- and only POSIX has a directory to fall back on --")
    as_windows(True)
    check("windows has no fallback list", host.serial_fallback(), [])
    as_windows(False)
    check("posix returns a list", isinstance(host.serial_fallback(), list),
          True)

    print("\n-- the kiosk is a Linux appliance and says so --")
    host.WINDOWS = REALLY_WINDOWS
    check("kiosk only where /proc and X are", host.can_kiosk(), host.LINUX)
    check("this machine names itself", bool(host.name()), True)

    print("\n-- stopping: the Windows mechanism, proved here --")
    # The main thread parks in accept(), exactly as the serving loop parks in
    # its own. Nothing wakes it but the knock, so a test that gets past accept
    # has proved the knock; the interrupt that follows is the thing itself.
    as_windows(True)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(4.0)
    port = listener.getsockname()[1]
    interrupted, timed_out = False, False
    threading.Timer(0.15, lambda: host.stop_main_thread(port)).start()
    try:
        conn, _ = listener.accept()
        conn.close()
        for _ in range(400):
            time.sleep(0.01)
    except KeyboardInterrupt:
        interrupted = True
    except socket.timeout:
        timed_out = True
    finally:
        listener.close()
    check("the knock reached a blocked accept()", timed_out, False)
    check("and the main thread was interrupted", interrupted, True)

    host.WINDOWS = REALLY_WINDOWS
    if REALLY_WINDOWS:
        print("\n-- the POSIX mechanism is not asked for here --")
        check("skipped on Windows, where os.kill does not raise", True, True)
    else:
        print("\n-- and the POSIX one, which is what the Pi still uses --")
        raised = False
        try:
            host.stop_main_thread()
            for _ in range(200):
                time.sleep(0.01)
        except KeyboardInterrupt:
            raised = True
        check("SIGINT to itself raises in the main thread", raised, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
