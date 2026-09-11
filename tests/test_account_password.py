#!/usr/bin/env python3
"""Checks for offering a password when a unit stops being one person's.

    python3 tests/test_account_password.py

A password is optional and every account starts without one, which is right for
somebody studying alone. Nothing used to change when a second person appeared,
so the protection sat in a menu nobody opened until after they had been bitten.

The property tested hardest here is a privacy one. The offer must be computed
from the asked account alone - how many accounts share the unit, whether this
one has a password, whether it has been asked before - and never from anybody
else's state. The second person to arrive must see the same words whether the
first has a password or not, because telling them a clubmate is unprotected
would be its own small betrayal.

Runs against a temporary database and never touches a real one.
"""
import sys
import tempfile
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


def fresh():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = db.connect(tmp.name)
    return conn, tmp.name


def main():
    print("\n-- alone on your own Pi, nothing is asked --")
    conn, _ = fresh()
    alice = db.get_profile(conn)["id"]
    check("a single account is never offered a password",
          db.should_offer_password(conn, alice), False)
    check("  and it has none to begin with", db.has_password(conn, alice), False)

    print("\n-- a second person arrives, and both are asked --")
    bob = db.add_user(conn, "Bob", "")["id"]
    check("the newcomer is offered one", db.should_offer_password(conn, bob), True)
    check("and so is the person who was already here",
          db.should_offer_password(conn, alice), True)

    print("\n-- the offer knows nothing about anybody else --")
    # The load-bearing property. Bob's offer must not change when Alice's
    # protection does, or the dialogue becomes a report on his clubmate.
    before = db.should_offer_password(conn, bob)
    db.set_password(conn, alice, "alice-has-one")
    check("Alice setting a password does not change what Bob is offered",
          db.should_offer_password(conn, bob), before)
    db.set_password(conn, alice, "")
    check("  nor does her removing it again",
          db.should_offer_password(conn, bob), before)
    check("and Alice, now protected, is not asked again",
          (db.set_password(conn, alice, "x"),
           db.should_offer_password(conn, alice))[1], False)
    db.set_password(conn, alice, "")

    print("\n-- declining sticks --")
    db.mark_password_offered(conn, bob)
    check("somebody who said no is not asked again",
          db.should_offer_password(conn, bob), False)
    check("  even though he still has no password",
          db.has_password(conn, bob), False)
    check("and saying no for one account says nothing for another",
          db.should_offer_password(conn, alice), True)

    print("\n-- setting one stops the asking --")
    carol = db.add_user(conn, "Carol", "")["id"]
    check("Carol is asked", db.should_offer_password(conn, carol), True)
    db.set_password(conn, carol, "anything at all")
    check("  and not once she has one", db.should_offer_password(conn, carol), False)
    check("a password of any length is accepted, because this is a study Pi",
          db.check_password(conn, carol, "anything at all"), True)
    check("  and the wrong one is refused",
          db.check_password(conn, carol, "Anything at all"), False)

    print("\n-- what a password actually protects --")
    check("an account with one cannot be opened without it",
          db.may_alter(conn, carol, ""), False)
    check("  and can with it", db.may_alter(conn, carol, "anything at all"), True)
    check("an account without one is open, which is the default state",
          db.may_alter(conn, bob, ""), True)
    db.set_moderator(conn, "club-key")
    check("the moderator key opens any of them, for a forgotten password",
          db.may_alter(conn, carol, "club-key"), True)

    print("\n-- what the dialog promises is what the server does --")
    # The dialog says "any length, anything you like", and then says the
    # password crosses the network in clear - which is the honest threat
    # model: it is a name tag, not a vault. The endpoint used to refuse
    # anything under four characters anyway, so somebody who believed the
    # sentence in front of them got a bare 400 back. Asked of the route,
    # because the promise is the route's to keep.
    import elmer.db as dbmod
    spare = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    spare.close()
    dbmod.DB_PATH = spare.name
    from elmer.app import app
    app.config["TESTING"] = True
    client = app.test_client()

    r = client.post("/api/users/password", json={"password": "ab"})
    check("two characters is a password", r.status_code, 200)
    check("  and the account is locked with it", r.get_json()["locked"], True)

    # The shape the browser now depends on: a considered refusal says so in a
    # sentence. Without the sentence the page has nothing to show but the
    # status code, which is how "400 for /api/users/password" reached a
    # person who had only mistyped something.
    r = client.post("/api/users/password", json={"password": "later"})
    check("changing it without the old one is refused", r.status_code, 403)
    check("  in words, not just a status",
          bool((r.get_json() or {}).get("message")), True)

    r = client.post("/api/users/password", json={"password": "", "current": "ab"})
    check("an empty password takes the lock off", r.status_code, 200)
    check("  and the account is open again", r.get_json()["locked"], False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
