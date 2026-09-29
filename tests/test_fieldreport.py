#!/usr/bin/env python3
"""Mail home: the outgoing-mail settings, the problem report's send, and the
weekly field report that is off until switched on.

    python3 tests/test_fieldreport.py

Nothing here talks to a mail server. What is pinned is the shape of what
would be sent, that it is redacted, that it is written to the unit before it
goes, that the switch is off by default, and that a unit with no mail
settings says so rather than pretending.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import bugreport, db, fieldreport as F, mail  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"   (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    print("-- the address --")
    check("reports go to the project's reports mailbox", mail.CONTACT, "elmeramateurradio@gmail.com")
    check("  and the problem report page shows the same one", bugreport.CONTACT, mail.CONTACT)

    print("\n-- the subject --")
    # Tagged on the way out, whatever a caller wrote, so one filter at the
    # far end catches every message a unit sends.
    check("a subject is tagged", mail.subject_line("field report - build abc"),
          "[ELMER] field report - build abc")
    check("  once", mail.subject_line("[ELMER] test"), "[ELMER] test")
    check("  and an empty one is the tag alone", mail.subject_line(""), "[ELMER]")

    print("\n-- one way home: the drop --")
    # The operator's own mail server was a second door, with a panel that
    # asked for a host, a login and an app password beside the report. It
    # is gone: a unit keeps no mail password, and nothing can send but the drop.
    check("the mail module sends nothing and keeps no settings",
          [hasattr(mail, n) for n in ("send", "save", "settings", "configured", "SETTINGS")],
          [False, False, False, False, False])
    from elmer import home, diagnostics as D
    import os as _os
    was = _os.environ.get("ELMER_DROP_URL")
    _os.environ["ELMER_DROP_URL"] = "http://127.0.0.1:9/exec"
    try:
        check("with the drop set, it is the way home, named by callsign",
              (home.way() or {}).get("via"), "drop")
        check("  and the Send button says who it reaches", (home.way() or {}).get("to"), mail.CONTACT_NAME)
    finally:
        if was is None:
            _os.environ.pop("ELMER_DROP_URL", None)
        else:
            _os.environ["ELMER_DROP_URL"] = was
    check("without it there is no way, and the report is written for sending by hand", home.way(), None)
    # A unit that used the old door still has its settings, password and all.
    mail.OLD_SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    mail.OLD_SETTINGS.write_text('{"host": "smtp.example.net", "password": "hunter2"}')
    try:
        rows = []
        D._collected = rows
        D.check_mail()
        D._collected = None
        old = [r for r in rows if r["label"] == "old mail settings"]
        check("a leftover data/mail.json is named by the doctor, as a password nothing uses",
              (len(old), old[0]["state"] if old else None, "password" in (old[0]["detail"] if old else "")),
              (1, "warn", True))
    finally:
        D._collected = None
        mail.OLD_SETTINGS.unlink()

    print("\n-- a private file is its owner's alone --")
    # paths.keep_private guards the roster's signing key; checked here since
    # the mail settings it was first written for.
    import subprocess as _sp
    from elmer import paths as _paths
    scratch = _paths.STATE / "private-test.txt"
    scratch.parent.mkdir(parents=True, exist_ok=True)
    scratch.write_text("secret")
    if _os.name != "nt":
        _paths.keep_private(scratch)
        check("  the file is the operator's alone", oct(scratch.stat().st_mode & 0o777), "0o600")
    else:
        # Windows has no mode bits, so the question is asked the way Windows
        # answers it: who is on the file's permission list. A file every user
        # on the machine can read is handed to keep_private, and comes back
        # the owner's alone.
        _sp.run(["icacls", str(scratch), "/grant", "*S-1-5-32-545:R"], capture_output=True, text=True)
        before = "BUILTIN\\Users" in _sp.run(["icacls", str(scratch)], capture_output=True, text=True).stdout
        made = _paths.keep_private(scratch)
        after = _sp.run(["icacls", str(scratch)], capture_output=True, text=True).stdout
        check("  a file every user could read is made the owner's alone",
              (before, made, "BUILTIN\\Users" in after, _os.environ.get("USERNAME", "?") in after), (True, True, False, True))
    scratch.unlink()

    print("\n-- the field report --")
    check("off until switched on", F.settings()["opt_in"], False)
    check("  and not due while off", F.due(), False)
    check("the switch's text names what it sends and where",
          all(w in F.WHAT_IT_SENDS for w in ("forecast", "errors", "callsign", mail.CONTACT_NAME, "off until")), True)
    conn = db.connect()
    text = F.build(conn)
    check("it names the build and the machine", ("build" in text and "machine" in text), True)
    check("  carries the forecast scorecard heading", "forecast against the sondes" in text, True)
    check("  and what the unit has learned", "what this unit has learned" in text, True)
    check("  and the week in counts", "the week, in counts" in text, True)
    check("  and the log's complaints, counted", "errors " in text and "warnings " in text, True)
    check("  and no callsign", "KC9SP" in text.replace(mail.CONTACT, ""), False)
    path, written = F.write(conn)
    check("it is written to the unit first", (path.exists(), bool(written)), (True, True))
    check("  and the latest one can be read back", F.latest()["path"], str(path))
    F.set_opt_in(True)
    check("switched on, it is due at once", F.due(), True)
    result = F.send_now(conn, reason="test")
    check("with no door open it is written and not sent",
          (result["sent"], Path(result["path"]).exists(), "no way home" in result["detail"]),
          (False, True, True))
    check("  the failure is remembered for the page", F.settings()["last_result"]["sent"], False)
    check("  and it stays due, so the clock tries again", F.due(), True)
    F.set_opt_in(False)
    check("switched off again", F.due(), False)
    for _ in range(F.KEEP + 3):
        F.write(conn)
        time.sleep(0.01)
    check("old reports are pruned", len(list(F.REPORTS.glob("field-report-*.txt"))) <= F.KEEP, True)

    # The field report is the one that actually gets sent. A kiosk that came
    # up in a window instead of filling the screen was reported from a machine
    # whose report said nothing about the screen or the browser, because these
    # facts had been put in the problem report and not in this one.
    check("the screen and the browser travel with it",
          "the screen, and the browser" in text, True)
    for want in ("platform", "session type", "DISPLAY", "screen", "chosen"):
        check(f"  it carries {want}", want in text, True)
    check("  and the whole launch command", "--kiosk" in text, True)
    conn.close()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
