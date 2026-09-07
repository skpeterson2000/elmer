#!/usr/bin/env python3
"""Checks for reading a position out of gpsd.

    python3 tests/test_gps.py

Runs against a stub gpsd on a loopback port, so it needs no receiver and says
the same thing on a machine that has never had one.

The case that prompted these: a station could not find itself while the other
program on the same Pi was showing a 3D fix on twelve satellites. Watching
alone only delivers a report when the receiver next sends one, so a receiver
reporting every few seconds put a good fix on the far side of the timeout.
Asking gpsd what it already knows answers immediately. Both are tested here,
including a gpsd that only answers one way.
"""
import json
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import gps  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


class StubGpsd(threading.Thread):
    """A gpsd that behaves however a test needs it to."""

    def __init__(self, mode="both", tpv_delay=0.0):
        super().__init__(daemon=True)
        self.mode = mode            # both | poll_only | watch_only | nothing
        self.tpv_delay = tpv_delay
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.stop = threading.Event()

    TPV = {"class": "TPV", "device": "/dev/ttyACM0", "mode": 3,
           "lat": 46.5983371, "lon": -94.3154177, "alt": 386.2,
           "time": "2026-09-07T12:00:00.000Z"}

    def run(self):
        while not self.stop.is_set():
            try:
                self.sock.settimeout(0.5)
                client, _ = self.sock.accept()
            except OSError:
                continue
            threading.Thread(target=self._serve, args=(client,),
                             daemon=True).start()

    def _serve(self, client):
        try:
            client.sendall(json.dumps(
                {"class": "VERSION", "release": "3.22"}).encode() + b"\n")
            client.settimeout(2.0)
            try:
                client.recv(4096)          # the ?WATCH / ?POLL the client sent
            except OSError:
                pass
            if self.mode in ("both", "poll_only"):
                client.sendall(json.dumps(
                    {"class": "POLL", "time": "2026-09-07T12:00:00.000Z",
                     "active": 1, "tpv": [self.TPV], "sky": []}).encode() + b"\n")
            if self.mode in ("both", "watch_only"):
                time.sleep(self.tpv_delay)
                client.sendall(json.dumps(self.TPV).encode() + b"\n")
            if self.mode == "nothing":
                # A receiver that is connected but has not locked: gpsd
                # answers, and says mode 1, which is not a position.
                client.sendall(json.dumps(
                    {"class": "TPV", "mode": 1}).encode() + b"\n")
            time.sleep(1.5)
        finally:
            try:
                client.close()
            except OSError:
                pass

    def close(self):
        self.stop.set()
        try:
            self.sock.close()
        except OSError:
            pass


def main():
    print("\n-- one report at a time, judged on its own --")
    check("a 3D fix is usable",
          bool(gps.usable({"class": "TPV", "mode": 3, "lat": 1.0, "lon": 2.0})), True)
    check("a 2D fix is usable too - altitude is not needed for a bearing",
          bool(gps.usable({"class": "TPV", "mode": 2, "lat": 1.0, "lon": 2.0})), True)
    check("mode 1 is 'no fix yet', not a position",
          gps.usable({"class": "TPV", "mode": 1, "lat": 1.0, "lon": 2.0}), None)
    check("no latitude, no fix",
          gps.usable({"class": "TPV", "mode": 3, "lon": 2.0}), None)
    check("a SKY report is not a position",
          gps.usable({"class": "SKY", "mode": 3, "lat": 1.0, "lon": 2.0}), None)
    check("rubbish is not a position", gps.usable("hello"), None)
    check("nothing is not a position", gps.usable(None), None)

    print("\n-- against a gpsd that answers both ways --")
    stub = StubGpsd("both")
    stub.start()
    try:
        got = gps.read_fix("127.0.0.1", stub.port, timeout=3)
        check("a fix comes back", bool(got), True)
        check("  at the right place", round(got["lat"], 4), 46.5983)
        check("  with the mode", got["mode"], 3)
        check("  labelled with where it came from",
              got["from"], f"127.0.0.1:{stub.port}")
    finally:
        stub.close()

    print("\n-- a gpsd whose device is slow: watching alone would time out --")
    # The reported case. The stream is four seconds away; the poll is not.
    stub = StubGpsd("both", tpv_delay=4.0)
    stub.start()
    try:
        started = time.monotonic()
        got = gps.read_fix("127.0.0.1", stub.port, timeout=3)
        took = time.monotonic() - started
        check("a fix still comes back inside the timeout", bool(got), True)
        check("  and quickly, because the poll answered", took < 1.5, True)
    finally:
        stub.close()

    print("\n-- and one that only streams, with no poll support --")
    stub = StubGpsd("watch_only")
    stub.start()
    try:
        check("watching still works on its own",
              bool(gps.read_fix("127.0.0.1", stub.port, timeout=3)), True)
    finally:
        stub.close()

    print("\n-- a receiver that is connected but has not locked --")
    stub = StubGpsd("nothing")
    stub.start()
    try:
        check("reports no fix rather than inventing one",
              gps.read_fix("127.0.0.1", stub.port, timeout=2), None)
    finally:
        stub.close()

    print("\n-- and nothing listening at all --")
    spare = socket.socket()
    spare.bind(("127.0.0.1", 0))
    dead = spare.getsockname()[1]
    spare.close()
    started = time.monotonic()
    check("refused outright, not waited on",
          gps.read_fix("127.0.0.1", dead, timeout=3), None)
    check("  and it did not spend the timeout doing it",
          time.monotonic() - started < 1.0, True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
