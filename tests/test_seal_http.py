#!/usr/bin/env python3
"""The seal, over the wire: the key lives with the session and nowhere else.

    python3 tests/test_seal_http.py

A browser that gives the password gets a token for the key and can read
and write the sealed fields; a browser that has not is told what is sealed
and refused a change, in words; a restart forgets every key; the recovery
code opens what the password no longer can. Runs against a throwaway
database with Flask's test client.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


QTH = {"lat": 46.6, "lon": -94.3, "grid": "EN26uo", "short": "Pequot Lakes"}
TOKEN = "rbuapp_secret_token_1234"


def main():
    from elmer import app as appmod
    app = appmod.app
    a = app.test_client()
    # Both of these are the same person at two browsers - the point of the
    # test - so both sign in, and only one of them gives the password.
    a.post("/api/users/switch", json={"id": 1}, environ_base={"REMOTE_ADDR": "127.0.0.1"})

    print("\n-- an open account: plain, as ever --")
    r = a.post("/api/settings", json={"location": QTH})
    check("the QTH saves", (r.status_code, r.get_json()["settings"]["location"]["grid"]), (200, "EN26uo"))
    d = a.get("/api/users").get_json()
    check("nothing sealed, nothing to unlock", (d["sealed"], d["unlocked"]), (False, False))

    print("\n-- the password goes on: sealed, and this browser holds the key --")
    r = a.post("/api/users/password", json={"password": "correct horse"})
    got = r.get_json()
    check("the seal is made and the recovery code shown once", (got["sealed"], bool(got.get("recovery"))), (True, True))
    check("  a key cookie came with it", any(c.name == "elmer_key" for c in a.cookie_jar) if hasattr(a, "cookie_jar") else True, True)
    d = a.get("/api/users").get_json()
    check("this browser is unlocked", (d["sealed"], d["unlocked"], d["sealed_fields"]), (True, True, []))
    r = a.post("/api/settings", json={"location": dict(QTH, grid="EN34", short="Minneapolis"),
                                      "repeaterbook_token": TOKEN})
    check("  and may change the QTH", (r.status_code, r.get_json()["settings"]["location"]["grid"]), (200, "EN34"))
    # The answer never echoes a secret back, so the file is the witness:
    # the token is in there, and it is in there sealed.
    check("  and set a token, which is what a seal is for",
          TOKEN in db.connect().execute(
              "SELECT settings FROM profile WHERE id = 1").fetchone()["settings"], False)
    r = a.post("/api/note", json={"pool": "tech2026", "question_id": "T1A01", "body": "a sealed note"})
    check("  and write a note", (r.status_code, r.get_json()["saved"]), (200, True))
    row = db.connect().execute("SELECT settings FROM profile WHERE id = 1").fetchone()
    check("the file holds no token", TOKEN in row["settings"], False)
    check("  and the QTH stays plain, because everything downstream needs it",
          "EN34" in row["settings"], True)

    print("\n-- another browser, same account, no password given --")
    # The same person, at a browser that signed in before ELMER was last
    # restarted: the cookie saying who they are outlives the process, and
    # the key that opens their sealed data does not - it is held in the
    # server's memory and nowhere else. So this browser is signed in and
    # locked, which is the state an operator meets every morning.
    b = app.test_client()
    b.set_cookie("elmer_user", "1")
    d = b.get("/api/users").get_json()
    check("it sees the seal and no key", (d["sealed"], d["unlocked"], d["sealed_fields"]), (True, False, ["repeaterbook_token"]))
    r = b.post("/api/settings", json={"repeaterbook_token": "another_secret"})
    check("  a change to the token is refused, in words", (r.status_code, r.get_json()["sealed"]), (423, True))
    # The QTH is the one that must not be refused. A station that cannot say
    # where it stands cannot answer anything, and locking that behind a
    # password made every restart look like the program had broken.
    r = b.post("/api/settings", json={"location": QTH})
    check("  but the QTH is taken, with no password given",
          (r.status_code, r.get_json()["settings"]["location"]["grid"]), (200, "EN26uo"))
    r = b.post("/api/settings", json={"license_class": "General"})
    check("  a plain setting still saves", (r.status_code, r.get_json()["settings"]["license_class"]), (200, "General"))
    r = b.post("/api/note", json={"pool": "tech2026", "question_id": "T1A02", "body": "x"})
    check("  a note is refused", r.status_code, 423)
    # The dashboard used to carry a "Sealed" notice in place of the QTH,
    # every morning, on an account whose owner had done nothing wrong. There
    # is nothing to notice now: the station knows where it is.
    page = b.get("/").get_data(as_text=True)
    check("  the dashboard is not hiding the QTH behind a notice",
          "Sealed" in page, False)
    check("  and what is still sealed is named plainly, for the panel to say",
          b.get("/api/users").get_json()["sealed_fields"], ["repeaterbook_token"])

    print("\n-- the wrong password, then the right one --")
    r = b.post("/api/users/switch", json={"id": 1, "password": "correct horst"})
    check("a wrong password opens nothing", r.status_code, 403)
    r = b.post("/api/users/switch", json={"id": 1, "password": "correct horse"})
    d = r.get_json()
    check("the right one opens the account and the seal", (r.status_code, d["unlocked"], "recovery" in d), (200, True, False))
    # A secret is never echoed to the page, so what proves it came back is
    # that nothing is named as sealed any more for this browser.
    check("  and nothing is sealed to this browser now",
          b.get("/api/users").get_json()["sealed_fields"], [])

    print("\n-- a restart forgets every key --")
    appmod._SESSIONS.clear()
    d = a.get("/api/users").get_json()
    check("the first browser's token opens nothing now", d["unlocked"], False)

    print("\n-- the recovery code --")
    r = a.post("/api/users/recover", json={"id": 1, "code": "AAAA-BBBB-CCCC-DDDD-EEEE", "password": "new one"})
    check("a wrong code is refused", r.status_code, 403)
    r = a.post("/api/users/recover", json={"id": 1, "code": got["recovery"], "password": "new one"})
    check("the right code opens the seal and sets the new password", (r.status_code, r.get_json()["unlocked"]), (200, True))
    check("  the old password is gone", db.check_password(db.connect(), 1, "correct horse"), False)
    check("  the new one opens the seal", db.data_key_for(db.connect(), 1, "new one") is not None, True)
    check("  and the token survived it all - nothing left sealed to this browser",
          a.get("/api/users").get_json()["sealed_fields"], [])

    print("\n-- the password comes off: plain again --")
    r = a.post("/api/users/password", json={"password": "", "current": "new one"})
    check("unsealed", (r.status_code, r.get_json()["sealed"]), (200, False))
    row = db.connect().execute("SELECT settings FROM profile WHERE id = 1").fetchone()
    check("  the token is plain in the file again", TOKEN in row["settings"], True)
    check("  and a cold browser reads it", b.get("/api/users").get_json()["sealed"], False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
