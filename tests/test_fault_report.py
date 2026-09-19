#!/usr/bin/env python3
"""A fault is named as a fault, and the report carries what it was.

    python3 tests/test_fault_report.py

Reported from a screenshot and then a field report, sent to check that the
reporting was catching things. It caught the headline and not the fault,
and the page had blamed the wrong thing. Three faults, one incident:

  - the fault itself: /progress/<pool> hands its template a `standing`,
    the study rank, and the block every page gets - which routes splat in
    with ** - gained a `standing` of its own, the licence's. Two values for
    one keyword, and the progress page died. The licence's is
    `licence_standing` now;

  - the error page saw that a template had changed on disk and blamed it,
    telling the person to restart for a TypeError raised in app.py that a
    restart could not touch. Changed files are a likely cause only when
    the traceback ran through them, and the page says which it is;

  - the field report listed the UNHANDLED line and left the traceback in
    the log, where the reader of the report cannot see it. It carries the
    traceback now, and the scrubber that turned [user] into [user]] on its
    second pass leaves a scrubbed name alone.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import app as appmod, db, bugreport, fieldreport, logs
    app = appmod.app
    # The report reads the log file, which the launcher opens and a test
    # does not; open it the same way, under the isolated state.
    logs.setup("INFO", to_file=True)

    # A route that raises a plain TypeError in Python, nowhere near a
    # template. Registered before the first request, which is the only
    # time Flask allows it.
    @app.route("/__test_fault")
    def _fault():
        raise TypeError("a fault, for the test")

    conn = db.connect()
    db.set_callsign(conn, "KC9SP")
    settings = db.get_profile(conn)["settings"]
    settings["license"] = {"callsign": "KC9SP", "found": True, "license_class": "Extra",
                           "expires": "04/26/2032"}
    db.save_settings(conn, settings)
    client = app.test_client()
    client.set_cookie("elmer_user", str(conn.user_id))

    print("\n-- the progress page opens with a licence on the account --")
    r = client.get("/progress/tech2026", environ_base=LOCAL)
    check("/progress/tech2026 is 200, not a collision on 'standing'", r.status_code, 200)
    home = client.get("/", environ_base=LOCAL).get_data(as_text=True)
    check("  and the dashboard still says the licence's standing", "expires" in home and "KC9SP" in home, True)
    block = appmod.profile_block(conn)
    check("  the licence's standing has a name of its own in the block",
          ("licence_standing" in block, "standing" in block), (True, False))

    print("\n-- a fault is named as a fault, and a changed file is blamed only when it is involved --")
    # With nothing changed on disk since start.
    logs.changed_since_start = lambda: ""
    r = client.get("/__test_fault", environ_base=LOCAL)
    page = r.get_data(as_text=True)
    check("a 500, with the reference", (r.status_code, bool(re.search(r"e-[0-9a-f]{4}", page))), (500, True))
    check("  named as a fault, by kind", "This is a fault" in page and "TypeError" in page, True)
    # With a template changed on disk, but the fault raised in Python.
    logs.changed_since_start = lambda: "templates/bandplan.html"
    page = client.get("/__test_fault", environ_base=LOCAL).get_data(as_text=True)
    check("a changed template that the fault did not run through is not blamed",
          ("This is a fault" in page, "not the files" in page, "will not clear it" in page), (True, True, True))
    check("  though the restart is still suggested, so files and program agree", "restart" in page, True)
    body = client.get("/api/__nope_test", environ_base=LOCAL)
    check("  (an unknown API path is a plain 404, not a fault)", body.status_code, 404)

    print("\n-- the field report carries the traceback, not only the headline --")
    text = fieldreport.build(conn)
    text = text if isinstance(text, str) else text.get("text", "")
    check("the report names the fault", "UNHANDLED TypeError on GET /__test_fault" in text, True)
    check("  and carries its traceback", "the faults above, with their tracebacks" in text, True)
    check("  down to the line that says what went wrong", "TypeError: a fault, for the test" in text, True)

    print("\n-- the scrubber leaves a scrubbed name alone --")
    once = bugreport.RE_HOME.sub(lambda m: m.group(1) + "[user]", r"C:\Users\somebody\elmer\x.py")
    twice = bugreport.RE_HOME.sub(lambda m: m.group(1) + "[user]", once)
    check("a home path is scrubbed", once, r"C:\Users\[user]\elmer\x.py")
    check("  and scrubbing it again changes nothing", twice, once)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
