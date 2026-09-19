#!/usr/bin/env python3
"""Where the station stands is not a secret, and a restart does not lose it.

    python3 tests/test_qth_unsealed.py

The QTH spent two days on the sealed list. That looked like caution and was
not: the data key lives in the running process and dies with it, so every
start left the station with no idea where it was until somebody typed a
password. Everything downstream is built on the QTH, so everything downstream
went quiet at once - no path to anywhere, no sky overhead, HF missing from
Make Contact, "Locate me" refused - and it went quiet politely, answering
"located: false" with a 200, which is not an error anybody can act on.

A secret earns a seal by being a secret. A grid square is on every card that
ever left the shack. The token for somebody else's API is a real credential
and stays sealed, which is the line this test draws.

An account that was already sealed keeps its QTH: the blob is opened and
written back in the clear the first time its owner signs in, which is the
only moment the key exists at all.
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer

FAILS = []
HOME = {"lat": 43.07, "lon": -89.4, "grid": "EN53"}


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def raw_settings(path, user_id):
    """The settings as they sit on disk, with no key anywhere near them."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT settings FROM profile WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return json.loads(row["settings"] or "{}")


def main():
    from elmer import db

    print("\n-- the list itself --")
    check("a token for somebody else's service is still sealed",
          "repeaterbook_token" in db.SEALED_KEYS, True)
    check("where the antenna stands is not",
          "location" in db.SEALED_KEYS, False)
    check("  and it is remembered as something that used to be",
          "location" in db.RETIRED_SEALED_KEYS, True)

    print("\n-- a sealed account can still save its QTH without the key --")
    conn = db.connect()
    db.set_password(conn, conn.user_id, "hunter2")
    # A password alone is a name check. Sealing is the separate step that
    # makes a data key and wraps it under that password.
    db.seal_account(conn, conn.user_id, "hunter2")
    cold = db.connect()                      # a fresh start: no key anywhere
    check("the account is sealed", db.has_password(cold, cold.user_id), True)
    check("  and it has no key in hand", bool(cold.data_key), False)
    db.save_settings(cold, {"location": dict(HOME)})
    check("  the QTH saves anyway - no password asked for", True, True)

    print("\n-- and a later start reads it back, with nobody signed in --")
    later = db.connect()
    check("the station knows where it is",
          db.get_profile(later)["settings"].get("location"), HOME)
    check("  and it is in the clear on disk, not in a blob",
          raw_settings(db.DB_PATH, later.user_id).get("location"), HOME)

    print("\n-- a real secret is still refused without the key --")
    try:
        db.save_settings(db.connect(), {"repeaterbook_token": "abc123"})
    except db.Locked:
        check("the token will not be written in the clear", True, True)
    else:
        check("the token will not be written in the clear", False, True)

    print("\n-- an account sealed under the old rules is carried over --")
    # Put a QTH back under lock exactly as the retired scheme left it, so
    # what is tested is the account somebody already has, not a fresh one.
    from elmer import seal
    who = db.connect().user_id
    key = db.data_key_for(db.connect(), who, "hunter2")
    check("the password opens the account", bool(key), True)
    stored = raw_settings(db.DB_PATH, who)
    stored.pop("location", None)
    stored["sealed"] = {"location": seal.seal_text(key, json.dumps(HOME))}
    disk = sqlite3.connect(db.DB_PATH)
    disk.execute("UPDATE profile SET settings = ? WHERE id = ?", (json.dumps(stored), who))
    disk.commit()
    disk.close()

    shut = db.connect()
    check("with no key the old QTH cannot be read",
          db.get_profile(shut)["settings"].get("location"), None)
    check("  and the panel is told it is a lock, not an empty field",
          "location" in (db.get_profile(shut)["settings"].get("sealed_fields") or []), True)

    signed_in = db.connect()
    signed_in.data_key = db.data_key_for(signed_in, who, "hunter2")
    check("signing in gives the QTH back",
          db.get_profile(signed_in)["settings"].get("location"), HOME)
    check("  and frees it on disk, once, so no later start needs the password",
          raw_settings(db.DB_PATH, who).get("location"), HOME)
    check("  the blob is gone rather than kept alongside",
          "location" in (raw_settings(db.DB_PATH, who).get("sealed") or {}), False)

    cold_again = db.connect()
    check("and the next cold start knows where it is",
          db.get_profile(cold_again)["settings"].get("location"), HOME)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
