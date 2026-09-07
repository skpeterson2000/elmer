#!/usr/bin/env python3
"""Put this station's GPS on the network, in TowerWitch's own packet.

    python3 tools/gps_broadcast.py

One receiver in the vehicle, every device knowing where it is. TowerWitch-P
already does this; the trouble is that it is the only thing that does, so a
station running a different build of TowerWitch - or none - broadcasts nothing,
and every unit without its own receiver has to be solved from scratch again.

This reads the local gpsd and sends the same packet TowerWitch-P sends, to the
same port, in the same shape. Anything already listening for TowerWitch hears
it without being told, including ELMER.

Run it on whichever machine has the receiver:

    python3 tools/gps_broadcast.py                 # every 5 seconds, forever
    python3 tools/gps_broadcast.py --once          # send one and stop
    python3 tools/gps_broadcast.py --port 12345 --interval 10

It sends only a position, and only when gpsd actually has one - a station that
does not know where it is should say nothing rather than broadcast its last
guess to every device in the vehicle.
"""
import argparse
import json
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import gps                                   # noqa: E402
from elmer.towerwitch import DEFAULT_PORT               # noqa: E402


def packet(fix):
    """TowerWitch's broadcast, exactly as TowerWitch-P.py builds it."""
    return {
        "timestamp": datetime.now().isoformat(),
        "source": "TowerWitch",
        "gps_lat": fix["lat"],
        "gps_lon": fix["lon"],
        "speed_mps": fix.get("speed_mps"),
        "is_vehicle_speed": bool((fix.get("speed_mps") or 0) > 1.0),
        "closest_armer_towers": [],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--interval", type=float, default=5.0,
                    help="seconds between sends (default 5)")
    ap.add_argument("--to", default="255.255.255.255",
                    help="where to send (default the broadcast address)")
    ap.add_argument("--gpsd", default="127.0.0.1",
                    help="which gpsd to read (default this machine)")
    ap.add_argument("--once", action="store_true", help="send one and stop")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    host, _, port = args.gpsd.partition(":")

    print(f"reading gpsd at {host}:{port or 2947}, broadcasting to "
          f"{args.to}:{args.port} every {args.interval:g}s")
    sent = quiet = 0
    try:
        while True:
            fix = gps.read_fix(host, int(port or 2947))
            if fix:
                sock.sendto(json.dumps(packet(fix)).encode(),
                            (args.to, args.port))
                sent += 1
                if sent == 1 or sent % 12 == 0:
                    print(f"  sent {sent}: {fix['lat']:.5f}, {fix['lon']:.5f} "
                          f"({fix['mode']}D)")
                quiet = 0
            else:
                quiet += 1
                if quiet in (1, 12):
                    print("  gpsd has no fix - sending nothing")
            if args.once:
                return 0 if fix else 1
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nstopped after {sent} broadcast(s)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
