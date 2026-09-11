#!/usr/bin/env python3
"""The way on to the big board from net control, and the way back off it.

    python3 tests/test_bigboard.py

One Pi runs the hall. It does not have to be a table as well - there are
usually other Pis in the room that are easier to sit down at - so its own
monitor is free to show the room, and the person running the net wants to put
the board on it without fetching a second machine.

The board used to open in a window of its own. On a kiosk that is a trap: the
browser is full screen with no tabs, no address bar and no back button, and a
window opened from a link cannot reliably close itself again. So net control
walks its own screen on to the board, and Escape walks it back - to the tables
list, the code people join by, and the controls, all still running.

What is checked here is that the link stays a link in this window, that every
place Escape can send somebody is a page this program actually serves, and
that the screen it returns to is the one you can run a net from. The order
Escape backs out in - one tournament, then the wall of them, then off - is a
thing only a browser can answer, and it was asked of one: a headless Chromium
driving the real page reported ESC_WENT_TO_THE_WALL=true while still on
/net/board, then AFTER_ESC=/net from the top.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer.app import app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


class Links(HTMLParser):
    """Every anchor on a page, with its attributes - so a target= can be seen."""

    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.found.append(dict(attrs))


app.config["TESTING"] = True
client = app.test_client()

print("\nnet control puts the board on its own screen")
page = client.get("/net")
check("net control answers", page.status_code, 200)

links = Links()
links.feed(page.get_data(as_text=True))
board = [a for a in links.found if (a.get("href") or "").startswith("/net/board")]
check("there is a way on to the board", len(board), 1)
# The whole point: not target=_blank. A kiosk has nowhere to put a new window
# and no way back out of one.
check("  and it opens in this window", board[0].get("target"), None)
check("  and says how to come back",
      "escape" in (board[0].get("title") or "").lower(), True)

print("\nthe board answers on both its names, with no net running")
for path in ("/net/board", "/board"):
    check(f"{path}", client.get(path).status_code, 200)

print("\nevery place Escape can send somebody is a page this program serves")
board_html = (Path(__file__).resolve().parents[1]
              / "elmer" / "templates" / "net_board.html").read_text(encoding="utf-8")
# Whatever the board navigates to, rather than whatever it mentions: a path in
# prose is not a promise, location.href is.
goes_to = sorted(set(re.findall(r"location\.href\s*=\s*'([^']+)'", board_html)
                     + re.findall(r"BACK\s*=\s*'([^']+)'", board_html)))
check("it navigates somewhere", bool(goes_to), True)
served = {str(r.rule) for r in app.url_map.iter_rules()}
for path in goes_to:
    check(f"  {path} is served", path in served, True)

print("\nand what it comes back to is a screen you can run a net from")
back = client.get("/net").get_data(as_text=True)
check("the code people join by", "Scan to play" in back, True)
check("the tables checked in", 'id="units"' in back, True)
check("the practice tables", 'id="addsim"' in back, True)
check("the way to end it", 'id="endnet"' in back, True)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
