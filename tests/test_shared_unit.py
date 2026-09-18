#!/usr/bin/env python3
"""A shared unit: the questions come in the right order, and a secret stays one.

    python3 tests/test_shared_unit.py

The first account on a unit is open, which is right for one person alone.
The danger is the second person: an open account can be switched into by
anyone and given a password by anyone, and whoever does that first owns
it. So the unit is asked whether it is shared the first time a second
account is about to be made, and on a shared unit the person at the
controls is asked to lock their own account before the second one exists
- at the one moment they are certainly the one at the controls. A token
saved on a shared unit needs a password on the account, and once saved it
never comes back over the wire. Runs against a throwaway database.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, diagnostics  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


TOKEN = "rbuapp_abcdefghijklmnop0123"


def main():
    from elmer.app import app
    c = app.test_client()

    print("\n-- one person, nothing asked --")
    d = c.get("/api/users").get_json()
    check("a fresh unit has not been asked whether it is shared", d["shared"], None)
    check("  and its one account is open", d["locked"], False)

    print("\n-- the second account: the unit is asked first --")
    r = c.post("/api/users/add", json={"name": "Bob"})
    check("adding a second account asks whether the unit is shared", (r.status_code, r.get_json().get("ask")), (409, "shared"))
    check("  and nobody was added", len(c.get("/api/users").get_json()["users"]), 1)
    r = c.post("/api/users/add", json={"name": "Bob", "shared": True})
    check("shared: the person at the controls is asked to lock their account first",
          (r.status_code, r.get_json().get("ask")), (409, "password"))
    check("  the answer about the unit was kept", c.get("/api/users").get_json()["shared"], True)
    check("  and still nobody was added", len(c.get("/api/users").get_json()["users"]), 1)

    print("\n-- the first account locks itself, and then Bob may come --")
    r = c.post("/api/users/password", json={"password": "alice-has-one"})
    check("the first account takes a password", (r.status_code, r.get_json()["locked"]), (200, True))
    r = c.post("/api/users/add", json={"name": "Bob"})
    check("now Bob is added without a question", r.status_code, 200)
    d = c.get("/api/users").get_json()
    check("  the controls pass to Bob, who is open", (d["display_name"], d["locked"]), ("Bob", False))

    print("\n-- a secret on a shared unit --")
    r = c.post("/api/settings", json={"repeaterbook_token": TOKEN})
    check("an open account on a shared unit may not keep a token", r.status_code, 403)
    c.post("/api/users/password", json={"password": "bob"})
    r = c.post("/api/settings", json={"repeaterbook_token": TOKEN})
    check("a locked one may", (r.status_code, r.get_json()["ok"]), (200, True))
    settings = r.get_json()["settings"]
    check("  the answer says one is saved and does not carry it",
          (settings.get("has_repeaterbook_token"), "repeaterbook_token" in settings), (True, False))
    page = c.get("/").get_data(as_text=True)
    check("  and the page never carries it either", TOKEN in page, False)
    cold = db.get_profile(db.connect(user_id=2))["settings"]
    raw = db.connect().execute("SELECT settings FROM profile WHERE id = 2").fetchone()["settings"]
    check("  while the database has it - sealed under Bob's password, named and not readable cold",
          ("repeaterbook_token" in (cold.get("sealed_fields") or []), TOKEN in raw), (True, False))
    r = c.post("/api/settings", json={"repeaterbook_token": ""})
    check("  an empty save forgets it", r.get_json()["settings"]["has_repeaterbook_token"], False)

    print("\n-- leaving an account open is an answer, given once --")
    r = c.post("/api/users/add", json={"name": "Carol"})
    check("Bob, locked, adds Carol with no question", r.status_code, 200)
    r = c.post("/api/users/add", json={"name": "Dave"})
    check("Carol, open, is asked to lock first", (r.status_code, r.get_json().get("ask")), (409, "password"))
    r = c.post("/api/users/add", json={"name": "Dave", "leave_open": True})
    check("  she may leave hers open", r.status_code, 200)
    # back to Carol: her answer was kept, so she is not asked again
    carol = next(u["id"] for u in c.get("/api/users").get_json()["users"] if u["name"] == "Carol")
    c.post("/api/users/switch", json={"id": carol, "password": ""})
    r = c.post("/api/users/add", json={"name": "Erin"})
    check("  and is not asked again", r.status_code, 200)

    print("\n-- the self-check names the open accounts --")
    diagnostics._collected = []
    diagnostics.check_accounts()
    line = diagnostics._collected[-1]
    diagnostics._collected = None
    check("a warning, saying how many are open", (line["state"].strip(), "no password" in line["detail"]), ("warn", True))
    check("  with the count", "3 of 5" in line["detail"], True)

    print("\n-- a unit marked one person's asks nothing --")
    conn = db.connect()
    db.set_shared(conn, False)
    r = c.post("/api/users/add", json={"name": "Frank"})
    check("adding on a one-person unit is not questioned", r.status_code, 200)
    diagnostics._collected = []
    diagnostics.check_accounts()
    check("  and the self-check is content", diagnostics._collected[-1]["state"].strip(), "ok")
    diagnostics._collected = None

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
