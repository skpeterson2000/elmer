#!/usr/bin/env python3
"""Checks for one board watching every tournament on the network.

    python3 tests/test_boards.py

A hall can hold several nets at once - Technician in one corner, General in
another, Extra in the next room - and the screen at the front of a room should
show the room, not whichever one happens to be running on the Pi the screen is
plugged into.

The parts worth testing are the ones that decide what a room full of people
sees. A net must be counted once however many tables are in it. A tournament
that goes off the air must not blank the board. And nothing here may block the
poll that asks for it, because a board that stutters is a board nobody trusts.
"""
import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elmer import discovery, netwatch  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def wait_for(test, seconds=3.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if test():
            return True
        time.sleep(0.05)
    return False


class OneBoard(BaseHTTPRequestHandler):
    """A stand-in for another Pi's net control."""

    payload = {"name": "Technician net", "units_present": 3, "players": 22}
    answering = True

    def do_GET(self):
        if not OneBoard.answering:
            self.send_error(503)
            return
        body = json.dumps(OneBoard.payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def peer(unit, name, url, **over):
    got = {"unit": unit, "name": name, "url": url, "version": "",
           "address": "10.0.0.1", "heard_at": time.time(), "party": {},
           "net": {}}
    got.update(over)
    return got


def main():
    print("\n-- what is worth putting on a board --")
    live = discovery.Neighbourhood(port=0, describe=lambda: {"unit": "me"})
    live.peers = {
        "a": peer("a", "Shack Pi", "http://10.0.0.1:5000",
                  net={"hosting": True, "name": "Technician net",
                       "difficulty": "technician", "units": 3}),
        "b": peer("b", "Table 2", "http://10.0.0.2:5000",
                  net={"table_of": "http://10.0.0.1:5000"},
                  party={"running": True, "players": 8}),
        "c": peer("c", "Bench Pi", "http://10.0.0.3:5000",
                  party={"running": True, "players": 4}),
        "d": peer("d", "Spare Pi", "http://10.0.0.4:5000"),
    }
    games = live.games()
    check("a net and a lone game, and nothing else", len(games), 2)
    check("  the net first", games[0]["name"], "Technician net")
    check("  asked for a hall's board", games[0]["path"], "/api/net/board")
    # A table's players are already counted in the hall's standings; showing
    # the table again would put the same people on the screen twice.
    check("  a table is not a second tournament",
          [g["url"] for g in games], ["http://10.0.0.1:5000",
                                      "http://10.0.0.3:5000"])
    check("  a unit playing by itself is one", games[1]["kind"], "table")
    check("  asked for its own board", games[1]["path"], "/api/board")

    print("\n-- fetching them never blocks the poll that asks --")
    server = HTTPServer(("127.0.0.1", 0), OneBoard)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    watch = [{"url": url, "name": "Technician net", "path": "/api/net/board"}]
    started = time.time()
    first = netwatch.look(watch)
    check("the first look answers at once", round(time.time() - started, 1) < 0.2, True)
    check("  with nothing yet", first[0]["board"], None)
    check("the board arrives",
          wait_for(lambda: netwatch.look(watch)[0]["board"] is not None), True)
    check("  and is the neighbour's",
          netwatch.look(watch)[0]["board"]["units_present"], 3)

    print("\n-- a tournament that goes off the air --")
    OneBoard.answering = False
    netwatch._cache[url]["tried"] = 0.0       # force the next look to refresh
    check("the error is noticed",
          wait_for(lambda: netwatch.look(watch)[0]["error"]), True)
    # The room keeps watching the last thing it saw rather than a blank screen.
    check("  and the last board is still there",
          netwatch.look(watch)[0]["board"]["units_present"], 3)
    OneBoard.answering = True

    print("\n-- and one nobody is watching any more --")
    netwatch.forget(keep=())
    check("is dropped", netwatch.look([])[0:1], [])
    check("  and its board with it", url in netwatch._cache, False)
    server.shutdown()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
