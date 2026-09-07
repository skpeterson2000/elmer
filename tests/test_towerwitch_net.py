#!/usr/bin/env python3
"""Checks for taking the station's position off the network.

    python3 tests/test_towerwitch_net.py

TowerWitch broadcasts where the station is over UDP, so one receiver serves
every device in the vehicle. This is ELMER's side of that: hear the broadcast,
take the position, and refuse everything that is not one.

The packet shape is TowerWitch's own and is not negotiable from this end, so
these tests use it verbatim - if TowerWitch changes it, these fail, which is
the point.
"""
import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import towerwitch  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def packet(**over):
    """A TowerWitch broadcast, exactly as TowerWitch-P.py builds one."""
    out = {"timestamp": "2026-09-07T18:40:00.000000", "source": "TowerWitch",
           "gps_lat": 46.5983371, "gps_lon": -94.3154177,
           "speed_mps": 0.053, "is_vehicle_speed": False,
           "closest_armer_towers": [{"site_name": "PEQUOT LAKES",
                                     "distance": "4.2 mi", "bearing": "185",
                                     "nac": "0x3A1", "control_channels": "..."}]}
    out.update(over)
    return json.dumps(out).encode()


def main():
    print("\n-- a real broadcast is read --")
    got = towerwitch.parse(packet())
    check("a position comes out", bool(got), True)
    check("  latitude", round(got["lat"], 5), 46.59834)
    check("  longitude", round(got["lon"], 5), -94.31542)
    check("  called a network fix, not a local one",
          got["source"], "towerwitch-net")
    check("  speed carried through", round(got["speed_mps"], 3), 0.053)
    check("  and whether the station is moving", got["moving"], False)
    check("moving is taken from TowerWitch, not guessed",
          towerwitch.parse(packet(is_vehicle_speed=True))["moving"], True)

    print("\n-- and everything that is not one is refused --")
    check("another program's broadcast on the same port",
          towerwitch.parse(packet(source="SomethingElse")), None)
    check("TowerWitch with no lock yet",
          towerwitch.parse(packet(gps_lat=None, gps_lon=None)), None)
    check("a half-filled packet",
          towerwitch.parse(packet(gps_lat=46.6, gps_lon=None)), None)
    check("a latitude off the planet",
          towerwitch.parse(packet(gps_lat=999.0)), None)
    check("a longitude off the planet",
          towerwitch.parse(packet(gps_lon=-500.0)), None)
    check("text where a number should be",
          towerwitch.parse(packet(gps_lat="north-ish")), None)
    check("not JSON at all", towerwitch.parse(b"hello"), None)
    check("an empty datagram", towerwitch.parse(b""), None)
    check("JSON that is not an object", towerwitch.parse(b"[1,2,3]"), None)

    print("\n-- over a real socket, as it actually arrives --")
    live = towerwitch.start(0)
    port = live.sock.getsockname()[1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        check("nothing heard yet", towerwitch.current(), None)
        sock.sendto(packet(), ("127.0.0.1", port))
        deadline = time.time() + 3
        while towerwitch.current() is None and time.time() < deadline:
            time.sleep(0.05)
        heard = towerwitch.current()
        check("the broadcast is heard", bool(heard), True)
        check("  and says who sent it",
              heard["from"].startswith("TowerWitch at"), True)
        check("  counted once", live.heard, 1)

        for junk in (b"hello", packet(source="Other"), packet(gps_lat=None)):
            sock.sendto(junk, ("127.0.0.1", port))
        time.sleep(0.4)
        check("junk is counted as ignored, not accepted", live.ignored, 3)
        check("  and did not disturb the good fix",
              round(towerwitch.current()["lat"], 5), 46.59834)

        # TowerWitch sends every 25 seconds; silence means it has stopped
        # talking, which is not the same as the station having stopped moving.
        live.fix["read_at"] = time.time() - towerwitch.STALE_AFTER - 1
        check("a broadcast that has stopped arriving goes stale",
              towerwitch.current(), None)
    finally:
        sock.close()
        towerwitch.stop_listening()
    check("stopping the listener closes it", towerwitch.listener(), None)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
