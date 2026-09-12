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
    check("reports go to the arrl.net forwarder", mail.CONTACT, "KC9SP@ARRL.NET")
    check("  and the problem report page shows the same one", bugreport.CONTACT, mail.CONTACT)

    print("\n-- outgoing mail on this unit --")
    check("nothing is set to begin with", mail.configured(), False)
    ok, why = mail.send("test", "body")
    check("  so nothing is sent, and it says why", (ok, "no outgoing mail server" in why), (False, True))
    pub = mail.save(host="smtp.example.net", port="", security="starttls",
                    user="kc9sp", password="hunter2", sender="unit@example.net")
    check("saved settings are configured", pub["configured"], True)
    check("  the port defaults for the security", mail.settings()["port"], 587)
    check("  the password never comes back to the page",
          ("password" in pub, pub["has_password"]), (False, True))
    mail.save(password="")
    check("  a blank password on save keeps the old one", mail.settings()["password"], "hunter2")
    check("  the file is the operator's alone", oct(mail.SETTINGS.stat().st_mode & 0o777), "0o600")
    ok, why = mail.send("test", "body")
    check("a server that is not there is a plain failure, not an exception", ok, False)
    check("  with the reason in words", bool(why), True)
    mail.forget()
    check("forgotten is unconfigured again", mail.configured(), False)

    print("\n-- the field report --")
    check("off until switched on", F.settings()["opt_in"], False)
    check("  and not due while off", F.due(), False)
    check("the switch's text names what it sends and where",
          all(w in F.WHAT_IT_SENDS for w in ("forecast", "errors", "callsign", mail.CONTACT, "off until")), True)
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
    check("with no mail settings it is written and not sent",
          (result["sent"], Path(result["path"]).exists(), "no outgoing mail server" in result["detail"]),
          (False, True, True))
    check("  the failure is remembered for the page", F.settings()["last_result"]["sent"], False)
    check("  and it stays due, so the clock tries again", F.due(), True)
    F.set_opt_in(False)
    check("switched off again", F.due(), False)
    for _ in range(F.KEEP + 3):
        F.write(conn)
        time.sleep(0.01)
    check("old reports are pruned", len(list(F.REPORTS.glob("field-report-*.txt"))) <= F.KEEP, True)
    conn.close()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
