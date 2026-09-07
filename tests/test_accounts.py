#!/usr/bin/env python3
"""Checks for account passwords on a shared unit.

    python3 tests/test_accounts.py

Runs against a temporary database, never the real one.

What is being protected here is somebody's study record. On a club Pi the
accounts are a list of names, and picking one off that list was enough to
answer questions as that person, rename them, or - at the unit itself - delete
them and everything they had done. A password makes an account theirs.

What is *not* being claimed is protection from an attacker. ELMER speaks plain
HTTP, so a password crosses the LAN in clear, and whoever holds the Pi holds
the database. These tests describe a lock on a cupboard, not a safe.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer import db
    tmp = Path(tempfile.mkdtemp(prefix="elmer-test-")) / "test.db"
    db.DB_PATH = tmp
    conn = db.connect()
    alice = db.add_user(conn, "Alice")["id"]
    bob = db.add_user(conn, "Bob")["id"]

    print("\n-- an account starts open, because most units have one operator --")
    check("no password to begin with", db.has_password(conn, alice), False)
    check("anything opens an open account",
          db.check_password(conn, alice, ""), True)
    check("so does a wrong one, because there is nothing to be wrong about",
          db.check_password(conn, alice, "anything"), True)

    print("\n-- setting one locks it --")
    db.set_password(conn, alice, "correct horse")
    check("now locked", db.has_password(conn, alice), True)
    check("the right password opens it",
          db.check_password(conn, alice, "correct horse"), True)
    check("a wrong one does not",
          db.check_password(conn, alice, "correct horst"), False)
    check("nor does an empty one", db.check_password(conn, alice, ""), False)
    check("case matters", db.check_password(conn, alice, "Correct Horse"), False)
    check("Bob is unaffected", db.has_password(conn, bob), False)

    print("\n-- the stored form gives nothing away --")
    row = conn.execute("SELECT pw_salt, pw_hash FROM profile WHERE id = ?",
                       (alice,)).fetchone()
    check("the password itself is not stored",
          "correct horse" in (row["pw_hash"] + row["pw_salt"]), False)
    check("the hash is scrypt-sized", len(row["pw_hash"]), 64)
    check("the salt is per account", len(row["pw_salt"]), 32)
    db.set_password(conn, bob, "correct horse")
    other = conn.execute("SELECT pw_hash FROM profile WHERE id = ?",
                         (bob,)).fetchone()["pw_hash"]
    check("the same password on two accounts hashes differently",
          other != row["pw_hash"], True)

    print("\n-- and nothing secret leaves the server --")
    # users() lists everyone on the unit, and the first is the profile every
    # database is born with - Alice has to be picked out by id.
    served = next(u for u in db.users(conn) if u["id"] == alice)
    check("no hash in what /api/users answers with",
          any("hash" in k or "salt" in k for k in served), False)
    check("only whether it is locked", served["locked"], True)
    check("an open account reports itself unlocked",
          next(u for u in db.users(conn) if u["id"] == 1)["locked"], False)

    print("\n-- the moderator key opens any account --")
    check("none set to begin with", db.has_moderator(conn), False)
    check("so it opens nothing",
          db.may_alter(conn, alice, "whatever"), False)
    db.set_moderator(conn, "club night")
    check("now set", db.has_moderator(conn), True)
    check("it opens a locked account", db.may_alter(conn, alice, "club night"), True)
    check("the account's own password still does too",
          db.may_alter(conn, alice, "correct horse"), True)
    check("a wrong key opens nothing", db.may_alter(conn, alice, "guess"), False)
    check("and it is not stored in the clear",
          "club night" in str(db.unit_get(conn, db.MODERATOR_KEY)), False)

    print("\n-- clearing --")
    db.set_password(conn, alice, "")
    check("the account is open again", db.has_password(conn, alice), False)
    db.set_moderator(conn, "")
    check("the moderator key is gone", db.has_moderator(conn), False)

    print("\n-- upgrading a database that predates all this --")
    old = Path(tempfile.mkdtemp(prefix="elmer-v2-")) / "old.db"
    import sqlite3
    raw = sqlite3.connect(old)
    raw.executescript("""
        CREATE TABLE profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT '', callsign TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL, xp INTEGER NOT NULL DEFAULT 0,
            streak_days INTEGER NOT NULL DEFAULT 0,
            best_streak INTEGER NOT NULL DEFAULT 0,
            last_study_day TEXT, last_seen TEXT,
            settings TEXT NOT NULL DEFAULT '{}');
        INSERT INTO profile (id, name, created, xp) VALUES (1, 'Old Timer', '2026-01-01', 4242);
        PRAGMA user_version = 2;""")
    raw.commit()
    raw.close()
    db.DB_PATH = old
    upgraded = db.connect()
    check("the schema moved to 3",
          upgraded.execute("PRAGMA user_version").fetchone()[0], 3)
    kept = upgraded.execute("SELECT name, xp FROM profile WHERE id = 1").fetchone()
    check("the existing account survived", kept["name"], "Old Timer")
    check("  with its progress", kept["xp"], 4242)
    check("and is open, not locked out", db.has_password(upgraded, 1), False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
