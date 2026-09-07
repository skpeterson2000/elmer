#!/usr/bin/env python3
"""Checks for one ELMER noticing another on the same network.

    python3 tests/test_discovery.py

Two Pis in a vehicle, neither knowing the other is there: one may have a GPS
antenna and a lock while the other has been guessing for ten minutes, and
either could have been running a tournament against the other all evening.

The part worth testing hardest is the one that is invisible when it goes wrong:
a unit must never pass on a position it borrowed from a neighbour. Two units
without receivers would otherwise echo one between themselves indefinitely,
and it would never age out or be traceable to a real antenna.
"""
import json
import socket
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import discovery  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def hello(**over):
    out = {"elmer": discovery.MAGIC, "unit": "shack-pi", "name": "Shack Pi",
           "url": "http://192.168.1.31:5000", "version": "abc1234",
           "sent": time.time(),
           "gps": {"lat": 44.9778, "lon": -93.2650, "mode": 3,
                   "source": "gps", "age_s": 2.0},
           "party": {"running": False, "players": 0, "seats": 24},
           "net": {}}
    out.update(over)
    return json.dumps(out).encode()


def free_port():
    probe = socket.socket()
    probe.bind(("", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def main():
    print("\n-- an announcement is read --")
    peer = discovery.parse(hello(), "192.168.1.31")
    check("a neighbour comes out", bool(peer), True)
    check("  named", peer["name"], "Shack Pi")
    check("  reachable", peer["url"], "http://192.168.1.31:5000")
    check("  the address is the sender's, not what it claimed",
          peer["address"], "192.168.1.31")
    check("  with its position", round(peer["gps"]["lat"], 4), 44.9778)
    check("  and what it is up to", peer["party"]["running"], False)

    print("\n-- and anything else on the port is ignored --")
    check("another program's broadcast",
          discovery.parse(json.dumps({"hello": "there"}).encode(), "10.0.0.1"),
          None)
    check("a TowerWitch packet, which shares the neighbourhood",
          discovery.parse(json.dumps({"source": "TowerWitch",
                                      "gps_lat": 1, "gps_lon": 2}).encode(),
                          "10.0.0.1"), None)
    check("not JSON", discovery.parse(b"hello", "10.0.0.1"), None)
    check("no unit id", discovery.parse(hello(unit=""), "10.0.0.1"), None)
    check("a position off the planet is dropped, the peer is kept",
          "gps" in discovery.parse(
              hello(gps={"lat": 999, "lon": 0}), "10.0.0.1"), False)

    print("\n-- over a real socket --")
    port = free_port()
    me = {"unit": "bench-pi", "name": "Bench", "url": "http://127.0.0.1:5000",
          "version": "def5678", "party": {}}
    live = discovery.start(lambda: dict(me), port=port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        check("nobody there yet", discovery.peers(), [])
        sock.sendto(hello(), ("127.0.0.1", port))
        deadline = time.time() + 3
        while not discovery.peers() and time.time() < deadline:
            time.sleep(0.05)
        found = discovery.peers()
        check("the neighbour is heard", len(found), 1)
        check("  and can be borrowed from",
              round(discovery.borrowed_fix()["lat"], 4), 44.9778)
        check("  labelled as a neighbour's, not our own",
              discovery.borrowed_fix()["source"], "elmer-peer")
        check("  and says whose", discovery.borrowed_fix()["from"],
              "ELMER on Shack Pi")

        # A unit hearing itself would otherwise appear as its own neighbour.
        sock.sendto(hello(unit="bench-pi", name="Bench"), ("127.0.0.1", port))
        time.sleep(0.4)
        check("a unit does not befriend itself", len(discovery.peers()), 1)

        # Repeated announcements are the same neighbour, not many.
        for _ in range(3):
            sock.sendto(hello(), ("127.0.0.1", port))
        time.sleep(0.4)
        check("repeat announcements are one neighbour",
              len(discovery.peers()), 1)

        # Three missed announcements and it has gone.
        with live.lock:
            live.peers["shack-pi"]["heard_at"] = time.time() - discovery.GONE_AFTER - 1
        check("a unit that goes quiet drops off", discovery.peers(), [])
        check("  and cannot be borrowed from", discovery.borrowed_fix(), None)

        # A neighbour with no fix is still a neighbour worth knowing about.
        sock.sendto(hello(gps=None), ("127.0.0.1", port))
        time.sleep(0.4)
        check("a neighbour without a position still appears",
              len(discovery.peers()), 1)
        check("  but offers no fix", discovery.borrowed_fix(), None)
    finally:
        sock.close()
        discovery.stop_listening()

    print("\n-- a borrowed position is never passed on --")
    # The important one. gps.fix() consults discovery, and discovery announces
    # what gps.fix() returned; without this guard two receiverless units would
    # echo a position between themselves for ever.
    from elmer import app as elmer_app
    described = elmer_app._describe_this_unit()
    check("describing this unit does not raise", isinstance(described, dict), True)
    borrowed = {"lat": 1.0, "lon": 2.0, "mode": 3, "read_at": time.time(),
                "source": "elmer-peer"}
    payload = json.loads(discovery._payload(
        "u", "n", "http://x", "v", borrowed, {}, True))
    check("an echoed fix is not announced", "gps" in payload, False)
    own = dict(borrowed, source="gps")
    payload = json.loads(discovery._payload(
        "u", "n", "http://x", "v", own, {}, True))
    check("a real one is", "gps" in payload, True)
    payload = json.loads(discovery._payload(
        "u", "n", "http://x", "v", own, {}, False))
    check("and not when position sharing is off", "gps" in payload, False)

    print("\n-- several nets on one network --")
    # Technician in this corner, General in that one, Extra in the next room.
    # A unit deciding where to report picks on the material, so that is what
    # the summary carries - and never the names of the Pis running them.
    port = free_port()
    live = discovery.start(lambda: {"unit": "bench-pi", "name": "Bench",
                                    "url": "http://127.0.0.1:5000"}, port=port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(hello(unit="a", name="A", url="http://10.0.0.1:5000",
                          net={"hosting": True, "name": "Technician net",
                               "difficulty": "technician", "units": 3}),
                    ("127.0.0.1", port))
        sock.sendto(hello(unit="b", name="B", url="http://10.0.0.2:5000",
                          gps=None,
                          net={"hosting": True, "name": "General net",
                               "difficulty": "general", "units": 1}),
                    ("127.0.0.1", port))
        deadline = time.time() + 3
        while len(discovery.peers()) < 2 and time.time() < deadline:
            time.sleep(0.05)
        nets = live.nets()
        check("both nets are found", len(nets), 2)
        check("  the busiest first", nets[0]["name"], "Technician net")
        check("  and each is joinable", nets[0]["url"], "http://10.0.0.1:5000")
        summary = live.summary()
        check("the summary counts the units", summary["count"], 2)
        check("  notices a fix among them", summary["with_fix"], True)
        check("  and names no unit at all",
              [k for k in summary if k in ("peers", "name", "address")], [])

        # A table can reach a master this unit cannot hear itself.
        sock.sendto(hello(unit="c", name="C", url="http://10.0.0.3:5000",
                          net={"table_of": "http://10.9.9.9:5000",
                               "table_in": "Extra net"}),
                    ("127.0.0.1", port))
        deadline = time.time() + 3
        while len(live.nets()) < 3 and time.time() < deadline:
            time.sleep(0.05)
        far = [n for n in live.nets() if n["url"] == "http://10.9.9.9:5000"]
        check("a net heard of second-hand is still joinable", len(far), 1)
        check("  and knows what it is called", far[0]["name"], "Extra net")

        # The unit hosting a net is heard directly as well as through its
        # tables; that is one net, not two.
        sock.sendto(hello(unit="d", name="D", url="http://10.0.0.4:5000",
                          net={"table_of": "http://10.0.0.1:5000"}),
                    ("127.0.0.1", port))
        time.sleep(0.4)
        check("a net reported twice is counted once",
              len([n for n in live.nets() if n["url"] == "http://10.0.0.1:5000"]), 1)
    finally:
        sock.close()
        discovery.stop_listening()

    print("\n-- what this unit says it is doing --")
    payload = json.loads(discovery._payload(
        "u", "n", "http://x", "v", None, {}, True,
        {"hosting": True, "name": "General net", "difficulty": "general"}))
    check("the part it is playing goes out with it",
          payload["net"]["name"], "General net")
    payload = json.loads(discovery._payload("u", "n", "http://x", "v", None, {}))
    check("and is empty when it is playing none", payload["net"], {})

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
