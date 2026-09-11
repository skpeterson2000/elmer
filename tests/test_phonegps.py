#!/usr/bin/env python3
"""Checks for the phone-as-GPS listener.

    python3 tests/test_phonegps.py

Plain standard library, no test runner to install, because a station Pi should
be able to check itself without first being given a development environment.

The parser is where the risk is. A position is not a value that announces when
it is wrong: a corrupted sentence produces a plausible number in the wrong
ocean rather than an error, and everything downstream - bearings, reach, RF
exposure - quietly answers about the wrong place. So most of this is about what
must be refused.
"""
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import phonegps  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def near(label, got, want, tol=1e-5):
    ok = got is not None and abs(got - want) < tol
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted about {want})"))
    if not ok:
        FAILS.append(label)


def nmea(body):
    """Build a sentence with a correct checksum.

    Written out rather than pasted from a capture so a test cannot pass by
    accident on data whose checksum was never right in the first place.
    """
    parity = 0
    for ch in body:
        parity ^= ord(ch)
    return f"${body}*{parity:02X}"


RMC = nmea("GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W")
GGA = nmea("GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,")


def main():
    print("\n-- a position is read out of the sentences that carry one --")
    rmc, gga = phonegps.parse(RMC), phonegps.parse(GGA)
    near("RMC latitude, ddmm.mmmm to degrees", rmc["lat"], 48 + 7.038 / 60)
    near("RMC longitude", rmc["lon"], 11 + 31.0 / 60)
    near("RMC speed, knots to m/s", rmc["speed_mps"], 22.4 * 0.514444, 1e-3)
    near("GGA altitude in metres", gga["alt_m"], 545.4, 1e-6)
    check("GGA satellite count", gga["sats"], 8)

    print("\n-- hemispheres, which are a sign and not a letter --")
    south = phonegps.parse(
        nmea("GPGGA,123519,3351.650,S,15112.700,E,1,08,0.9,10.0,M,,M,,"))
    near("  south of the equator is negative", south["lat"], -(33 + 51.650 / 60))
    near("  east of Greenwich is positive", south["lon"], 151 + 12.700 / 60)
    west = phonegps.parse(
        nmea("GPRMC,123519,A,4635.900,N,09418.925,W,0,0,230394,,"))
    near("  west of Greenwich is negative", west["lon"], -(94 + 18.925 / 60))

    print("\n-- and everything that must be refused --")
    check("a void RMC: the receiver is guessing, not knowing",
          phonegps.parse(
              nmea("GPRMC,123519,V,4807.038,N,01131.000,E,0,0,230394,,")), None)
    check("a GGA reporting fix quality 0",
          phonegps.parse(
              nmea("GPGGA,123519,4807.038,N,01131.000,E,0,00,,,M,,M,,")), None)
    check("a sentence whose checksum does not match",
          phonegps.parse(RMC[:-2] + "00"), None)
    check("a datagram truncated mid-sentence",
          phonegps.parse("$GPRMC,123519,A,4807.0"), None)
    check("a sentence with no checksum at all",
          phonegps.parse("$GPRMC,123519,A,4807.038,N,01131.000,E"), None)
    check("rubbish", phonegps.parse("hello"), None)
    check("nothing", phonegps.parse(""), None)
    check("a sentence type this does not read",
          phonegps.parse(nmea("GPGSV,3,1,11,03,03,111,00")), None)
    check("multi-constellation talker IDs are still read",
          phonegps.parse(
              nmea("GNRMC,123519,A,4807.038,N,01131.000,E,0,0,230394,,")) is not None,
          True)

    print("\n-- the listener, end to end over a real socket --")
    live = phonegps.start(0)          # port 0: let the OS pick a free one
    port = live.sock.getsockname()[1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        check("nothing has arrived yet", phonegps.current(), None)
        # A phone that batches several sentences into one datagram is being
        # kind to the radio, so that has to work too.
        sock.sendto((RMC + "\r\n" + GGA + "\r\n").encode(), ("127.0.0.1", port))
        deadline = time.time() + 3
        while phonegps.current() is None and time.time() < deadline:
            time.sleep(0.05)
        got = phonegps.current()
        check("a fix arrives", bool(got), True)
        near("  at the position sent", got["lat"], 48 + 7.038 / 60)
        check("  merged across both sentences: altitude from GGA",
              got.get("alt_m"), 545.4)
        check("  and speed from RMC", round(got.get("speed_mps", 0), 3),
              round(22.4 * 0.514444, 3))
        check("  labelled as a phone, not a receiver", got["source"], "phone")
        check("  two sentences counted", live.sentences, 2)

        sock.sendto(b"$GPRMC,nonsense\r\n", ("127.0.0.1", port))
        time.sleep(0.3)
        check("  a bad sentence is counted as rejected, not accepted",
              live.rejected >= 1, True)

        # A phone that has gone quiet is not a position any more.
        live.fix["read_at"] = time.time() - phonegps.STALE_AFTER - 1
        check("a fix that has gone stale stops being offered",
              phonegps.current(), None)
    finally:
        sock.close()
        phonegps.stop_listening()
    check("stopping the listener closes it", phonegps.listener(), None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
