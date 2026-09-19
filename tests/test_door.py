#!/usr/bin/env python3
"""The door asks only when there is something to ask, and asks in place.

    python3 tests/test_door.py

Two complaints, a few minutes apart, and both were fair.

The first: being told "Not done - this account's private data is sealed,
unlock it with your password from the account menu, then save". That is a
refusal, a lecture and an errand for something the program could simply have
asked for. It asks now, where the work is, and when the password opens the
account the request that was refused is made again, so the thing the person
was doing finishes instead of having to be started over.

The second: having to sign in every morning, alone at home, on the machine
the program is being written on. A door with one person behind it and no
password on them is a door for its own sake, and asking a question with one
answer teaches people to click past questions. So it does not ask then. And
where it does ask, it offers to stay signed in, because who you are is a
convenience. What is sealed is a secret, and that key still lives only in the
running process - a remembered station is asked for its password once, when
it first needs to read something sealed.
"""
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


def user_cookie(response):
    """The Set-Cookie line for who is at the controls, if there is one."""
    return next((v for k, v in response.headers if k == "Set-Cookie" and "elmer_user" in v), "")


def main():
    from elmer.app import app

    print("\n-- one person, no password: nothing to ask --")
    check("the dashboard opens straight away",
          app.test_client().get("/", environ_base=LOCAL).status_code, 200)

    print("\n-- put a password on, and it asks --")
    me = app.test_client()
    me.post("/api/users/switch", json={"id": 1}, environ_base=LOCAL)
    check("the password is set",
          me.post("/api/users/password", json={"password": "hunter2", "confirm": "hunter2"},
                  environ_base=LOCAL).status_code, 200)
    check("  a browser that has not signed in is sent to the door",
          app.test_client().get("/", environ_base=LOCAL).status_code, 302)
    check("  and the door itself always opens",
          app.test_client().get("/who", environ_base=LOCAL).status_code, 200)
    check("  the wrong password does not open it",
          app.test_client().post("/api/users/switch", json={"id": 1, "password": "no"},
                                 environ_base=LOCAL).status_code, 403)

    print("\n-- staying signed in is the operator's choice --")
    stay = app.test_client()
    r = stay.post("/api/users/switch", json={"id": 1, "password": "hunter2", "remember": True},
                  environ_base=LOCAL)
    check("signed in", r.status_code, 200)
    check("  and remembered past the window", "Max-Age" in user_cookie(r), True)
    once = app.test_client()
    r = once.post("/api/users/switch", json={"id": 1, "password": "hunter2"}, environ_base=LOCAL)
    check("without it, the choice ends with the window", "Max-Age" in user_cookie(r), False)

    print("\n-- a locked save says who to ask, rather than where to go --")
    # The state an operator meets after a restart: known by name, sealed data
    # shut, because the key lives in the process and the process has gone.
    cold = app.test_client()
    cold.set_cookie("elmer_user", "1")
    # Where the station stands is not what this is about any more: that is
    # saved by anybody, signed in or not, because every answer is built on
    # it. What needs the key is a credential for somebody else's service.
    r = cold.post("/api/settings", json={"location": {"lat": 45.0, "lon": -93.0, "grid": "EN35"}},
                  environ_base=LOCAL)
    check("the QTH saves with no password at all", r.status_code, 200)
    r = cold.post("/api/settings", json={"repeaterbook_token": "rbuapp_secret"}, environ_base=LOCAL)
    said = r.get_json()
    check("the save is refused", r.status_code, 423)
    check("  and says it is a lock, not a fault", said.get("locked"), True)
    check("  naming whose password opens it", said.get("user"), 1)
    check("  and who that is, to put on the box", bool(said.get("name")), True)
    # No errand in the words: the page has what it needs to ask here.
    check("  without sending anybody to a menu",
          "menu" in (said.get("message") or "").lower(), False)

    print("\n-- and the password finishes the job --")
    check("it opens", cold.post("/api/users/switch", json={"id": 1, "password": "hunter2"},
                                environ_base=LOCAL).status_code, 200)
    r = cold.post("/api/settings", json={"repeaterbook_token": "rbuapp_secret"}, environ_base=LOCAL)
    check("  and the save that was refused now goes through", r.status_code, 200)
    # Read the way a page reads it: through the session that holds the key.
    # A connection without one sees the sealed blob and not the place, which
    # is the whole point of sealing it.
    check("  and the station can be asked where it is again",
          (cold.get("/api/path-to?to=EM48", environ_base=LOCAL).get_json() or {}).get("located"),
          True)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
