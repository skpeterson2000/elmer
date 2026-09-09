"""What this machine is, and the few things that differ because of it.

ELMER is a Python program and almost none of it cares what it is running on.
A handful of things do, and they are the reason a program ends up half-ported:
a `sys.platform` test dropped into whichever file needed it, then another one
somewhere else, until nobody can say what the Windows path actually does. So
they live here instead, named, with the reason attached.

Nothing here pretends a Windows laptop is a Pi. The kiosk is a touchscreen
bolted to a radio bench and does not exist off Linux. A serial port is
/dev/ttyACM0 on the Pi and COM3 on Windows. And stopping the program - which
is also how it restarts onto new code - is the one that actually bites.

**Stopping.** On POSIX, ELMER sends itself SIGINT: the signal interrupts
whatever the serving loop is parked in and Python raises KeyboardInterrupt in
the main thread, where ./elmer.py catches it and decides whether it is exiting
or coming back on the new code. Windows has no such delivery. `os.kill` there
does not raise anything - it terminates the process outright, which would take
the restart decision with it and leave an update half-applied. What Windows
has is `_thread.interrupt_main`, which makes the same exception pending; it
lands between bytecodes, so a main thread sitting in the accept loop will not
notice until the next request arrives. One throwaway connection to our own
port is what wakes it.
"""
import logging
import os
import re
import socket
import sys
import threading

log = logging.getLogger("elmer")

WINDOWS = os.name == "nt"
LINUX = sys.platform.startswith("linux")
MACOS = sys.platform == "darwin"

# COM1 through COM9 are nameable as they stand; from COM10 up Windows needs
# the device-namespace prefix, and software that forgets is the classic reason
# a tenth USB adapter "does not work".
_COM = re.compile(r"^(?:\\\\\.\\)?COM\d+$", re.IGNORECASE)


def name():
    """One line for a log, a report or a self-check."""
    return f"{sys.platform} ({'Windows' if WINDOWS else os.name})"


def stop_main_thread(port=None):
    """Make the main thread raise KeyboardInterrupt, wherever it is waiting.

    This is how both the Exit button and an applied update hand control back
    to ./elmer.py, which is the only place that decides between stopping and
    restarting. See this module's own notes for why the two platforms cannot
    share one mechanism.
    """
    if not WINDOWS:
        import signal
        os.kill(os.getpid(), signal.SIGINT)
        return

    import _thread
    _thread.interrupt_main()
    if not port:
        return
    # Nothing is sent and nothing is read: the connection exists only so the
    # accept loop returns to Python, where the pending interrupt is seen.
    def knock():
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=2):
                pass
        except OSError:
            pass                      # already gone, which is the outcome
    threading.Thread(target=knock, name="wake-main", daemon=True).start()


def is_serial_device(text):
    """Whether a string names a serial port on this machine.

    This guards an endpoint that opens whatever it is handed and writes to it,
    so it is a gate rather than a hint: anything not shaped like a port on
    *this* platform is refused before a file is touched.
    """
    text = str(text or "")
    if WINDOWS:
        return bool(_COM.match(text))
    return text.startswith("/dev/")


def usb_serial(device, vid):
    """Whether a port is worth offering as a possible instrument.

    A NanoVNA is a USB device. The machine's own built-in ports come back in
    the same list - and on the Pi one of them may have a GPS on it, where
    opening the port and sending "info" at it is nobody's idea of a good time.
    Windows has the same hazard under different names, so the rule is the
    same: a USB id, or a name that says USB.
    """
    if vid is not None:
        return True
    if WINDOWS:
        return False        # a COM port with no USB id is a built-in one
    return str(device or "").startswith(("/dev/ttyACM", "/dev/ttyUSB"))


def serial_fallback():
    """Ports to offer when the port list came back empty but devices exist.

    Only POSIX has a filesystem to look in. On Windows the enumeration is the
    whole story, and an empty list there means an empty list.
    """
    if WINDOWS:
        return []
    import glob
    return sorted(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*"))


def can_kiosk():
    """Whether the full-screen kiosk exists on this machine.

    It reads /proc to find a browser it already started, signals it by pid,
    and expects an X or Wayland session. That is a Linux appliance, not a
    portability gap to be papered over - on anything else ELMER is a program
    you open a browser at.
    """
    return LINUX
