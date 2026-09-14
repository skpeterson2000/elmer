#!/usr/bin/env python3
"""The drop, and which door a report leaves by.

    python3 tests/test_drop.py

A stand-in for the Apps Script listens on a local port and behaves the way
the real one does: a POST is answered with a redirect to the page holding the
reply, and the reply is JSON saying what was done with the report. What was
posted is kept, so the payload can be checked for the tag the script looks
for and the subject tag one filter at the far end catches.

The door is checked on its own. With nothing set there is no door; with a
drop and no mail settings the drop; with mail settings the mail - because
filling them in is the choice - and forgetting them goes back to the drop.
Nothing here opens a real socket to anywhere but this machine.
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import drop, home, mail  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


# ------------------------------------------------- a script that is not one
POSTED = []
REPLY = {"ok": True, "mailed": "owner@example.com"}
STATUS = 302


class Script(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        POSTED.append(json.loads(self.rfile.read(n) or b"{}"))
        if STATUS != 302:
            self.send_response(STATUS)
            self.end_headers()
            return
        # Apps Script answers a POST with a redirect to the reply
        self.send_response(302)
        self.send_header("Location", f"http://127.0.0.1:{PORT}/reply")
        self.end_headers()

    def do_GET(self):
        body = json.dumps(REPLY).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


server = HTTPServer(("127.0.0.1", 0), Script)
PORT = server.server_address[1]
threading.Thread(target=server.serve_forever, daemon=True).start()


def run():
    # The program carries the project's drop; this test is about the
    # mechanism, so it starts from no address at all and puts it back.
    baked = drop.URL
    drop.URL = ""
    try:
        return _run()
    finally:
        drop.URL = baked


def _run():
    global STATUS, REPLY
    print("\n-- with nothing set, there is no door --")
    check("no drop", drop.configured(), False)
    check("no mail", mail.configured(), False)
    check("no way home", home.way(), None)
    sent, detail = home.deliver("problem report", "the body")
    check("  and delivering says so", sent, False)
    check("  naming the address to mail by hand", mail.CONTACT in detail, True)
    sent, detail = drop.send("problem report", "the body")
    check("  the drop alone says it is not set", sent, False)

    print("\n-- the unit's own drop, set without editing the program --")
    drop.SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    drop.SETTINGS.write_text(json.dumps({"url": f"http://127.0.0.1:{PORT}/exec"}))
    check("configured", drop.configured(), True)
    way = home.way()
    check("the door is the drop", way and way["via"], "drop")
    check("  to the project's address", way and way["to"], mail.CONTACT)

    print("\n-- a report goes by it --")
    POSTED.clear()
    sent, detail = home.deliver("problem report - build abc123", "line one\nline two\n",
                                kind="problem")
    check("sent", sent, True)
    check("  and the reply says what was done with it", "owner@example.com" in detail, True)
    check("  one post", len(POSTED), 1)
    p = POSTED[0]
    check("  carrying the tag the script looks for", p.get("tag"), "ELMER")
    check("  the subject tagged for the far end's filter",
          p.get("subject"), "[ELMER] problem report - build abc123")
    check("  the body as written", p.get("body"), "line one\nline two\n")
    check("  the kind", p.get("kind"), "problem")
    check("  a unit mark, four characters, not a name",
          isinstance(p.get("unit"), str) and len(p["unit"]) == 4, True)
    check("  and a build", bool(p.get("build")), True)
    last = mail.last_result()
    check("  remembered as the last send", last and last["ok"], True)
    check("    by the drop", last and last.get("via"), "drop")

    print("\n-- the test line --")
    POSTED.clear()
    sent, detail = home.test()
    check("sent", sent, True)
    check("  as a test", POSTED and POSTED[0].get("kind"), "test")
    check("  with the tag in the subject",
          POSTED and POSTED[0]["subject"].startswith("[ELMER] test message"), True)

    print("\n-- when the script refuses --")
    REPLY = {"ok": False, "detail": "not an ELMER report"}
    sent, detail = drop.send("x", "y")
    check("not sent", sent, False)
    check("  in the script's words", "not an ELMER report" in detail, True)
    check("  remembered as failed", mail.last_result()["ok"], False)
    REPLY = {"ok": True, "github": "reports/2026-09-13/181500-a1b2-problem.txt"}
    sent, detail = drop.send("x", "y")
    check("filed on GitHub is a success too", sent, True)
    check("  saying where", "reports/2026-09-13" in detail, True)

    print("\n-- when the drop is down --")
    STATUS = 500
    sent, detail = drop.send("x", "y")
    check("not sent", sent, False)
    check("  with the status", "500" in detail, True)
    STATUS = 302
    drop.SETTINGS.write_text(json.dumps({"url": "http://127.0.0.1:9/exec"}))
    sent, detail = drop.send("x", "y")
    check("nothing listening is said plainly", sent, False)
    check("  as unreachable", "could not reach the drop" in detail, True)
    drop.SETTINGS.write_text(json.dumps({"url": f"http://127.0.0.1:{PORT}/exec"}))

    print("\n-- a long report is cut to what the script takes --")
    POSTED.clear()
    drop.send("x", "y" * (drop.MOST + 10))
    check("cut", len(POSTED[0]["body"]), drop.MOST)

    print("\n-- mail settings are the choice of the other door --")
    mail.save(host="smtp.example.com", sender="me@example.com", security="none")
    way = home.way()
    check("the door is now mail", way and way["via"], "mail")
    check("  naming the server", "smtp.example.com" in way["detail"], True)
    check("  the drop is still there underneath", drop.configured(), True)
    mail.forget()
    check("forgetting goes back to the drop", home.way()["via"], "drop")

    print("\n-- the project's own drop, baked into the program --")
    drop.SETTINGS.unlink()
    check("with nothing on the unit and nothing baked in: no door", home.way(), None)
    drop.URL = f"http://127.0.0.1:{PORT}/exec"
    check("baked in, but the tests' veto stands: still no door", home.way(), None)
    veto = os.environ.pop("ELMER_DROP_URL")
    check("veto lifted: the drop", home.way()["via"], "drop")
    drop.SETTINGS.write_text(json.dumps({"url": "http://127.0.0.1:9/other"}))
    check("  and the unit's own wins over it", drop.url(), "http://127.0.0.1:9/other")
    drop.SETTINGS.unlink()
    os.environ["ELMER_DROP_URL"] = "http://127.0.0.1:9/env"
    check("  the environment's over the built-in", drop.url(), "http://127.0.0.1:9/env")
    os.environ["ELMER_DROP_URL"] = veto
    drop.URL = ""

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    finally:
        server.shutdown()
