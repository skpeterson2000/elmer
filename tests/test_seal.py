#!/usr/bin/env python3
"""Private data sealed with the password: the cipher, and the account.

    python3 tests/test_seal.py

The cipher round-trips, refuses a wrong key and a touched blob, and never
repeats itself. An account that takes a password has its token and its
notes sealed in the database file - readable with the key, named and
nothing more without it - carried through a password change, given back
plain when the password comes off, and opened by the recovery code when
the password is gone. Runs against a throwaway database.

The QTH is deliberately not among them. It was, for two days, and the cost
was out of all proportion to the secret: the data key dies with the process,
so every restart left the station unable to say where it stood, and every
answer built on the QTH went quiet at once. A grid square is on every card
that ever left the shack. Somebody else's API token is a real credential.
That is the line, and test_qth_unsealed.py holds the other side of it.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, seal  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def raw(conn, user_id):
    return conn.execute("SELECT * FROM profile WHERE id = ?", (user_id,)).fetchone()


def main():
    print("\n-- the cipher --")
    key = seal.new_key()
    blob = seal.encrypt(key, b"EN26uo, and a token")
    check("round trip", seal.decrypt(key, blob), b"EN26uo, and a token")
    check("  nonce, text and tag", len(blob), 16 + len(b"EN26uo, and a token") + 32)
    check("  two sealings of one text differ", seal.encrypt(key, b"x") == seal.encrypt(key, b"x"), False)
    try:
        seal.decrypt(seal.new_key(), blob); check("a wrong key is refused", False, True)
    except seal.Broken:
        check("a wrong key is refused", True, True)
    touched = blob[:20] + bytes([blob[20] ^ 1]) + blob[21:]
    try:
        seal.decrypt(key, touched); check("  and so is a touched blob", False, True)
    except seal.Broken:
        check("  and so is a touched blob", True, True)
    check("empty text seals and unseals", seal.unseal_text(key, seal.seal_text(key, "")), "")
    check("a plain string passes through unseal untouched", seal.unseal_text(key, "plain"), "plain")
    salt, wrapped = seal.wrap(key, "correct horse")
    check("the key wraps under a password and comes back", seal.unwrap("correct horse", salt, wrapped), key)
    code = seal.recovery_code()
    check("a recovery code is five groups of four", (len(code), code.count("-")), (24, 4))
    check("  read any way it is typed", seal.normalise_code(code.lower().replace("-", " ")), code.replace("-", ""))

    print("\n-- an account takes a password, and is sealed --")
    tmp = Path(tempfile.mkdtemp(prefix="elmer-seal-")) / "t.db"
    db.DB_PATH = tmp
    conn = db.connect()
    alice = db.get_profile(conn)["id"]
    db.save_settings(conn, {"location": {"lat": 46.6, "lon": -94.3, "grid": "EN26uo", "short": "Pequot Lakes"},
                            "repeaterbook_token": "rbuapp_secret_token_1234", "license_class": "General"})
    db.save_note(conn, "tech2026", "T1A01", "remember the ohm's law triangle")
    got = db.change_password(conn, alice, "correct horse")
    check("the change reports a seal, a key and a recovery code",
          (got["locked"], got["sealed"], len(got["key"] or b""), bool(got["recovery"])), (True, True, 32, True))
    row = raw(conn, alice)
    check("the file holds no plain token", "rbuapp_secret" in row["settings"], False)
    check("  but the QTH stays readable - it is not a secret, and everything needs it",
          ("EN26uo" in row["settings"], "Pequot" in row["settings"]), (True, True))
    check("  the license class stays plain - the room's boards show it", json.loads(row["settings"]).get("license_class"), "General")
    note = conn.execute("SELECT body FROM user_note WHERE user_id = ?", (alice,)).fetchone()["body"]
    check("  the note is sealed", (note.startswith("sealed:"), "ohm" in note), (True, False))

    print("\n-- without the key: named, and nothing more --")
    cold = db.connect()
    prof = db.get_profile(cold)
    check("the profile says what is sealed", sorted(prof["settings"].get("sealed_fields") or []), ["repeaterbook_token"])
    check("  and does not carry it", "repeaterbook_token" in prof["settings"], False)
    check("  while the QTH is simply there, on a unit nobody has signed in to",
          prof["settings"]["location"]["grid"], "EN26uo")
    check("  the note reads as nothing", db.get_note(cold, "tech2026", "T1A01"), None)
    try:
        db.save_settings(cold, dict(prof["settings"], repeaterbook_token="new_secret"))
        check("a plain token cannot be written over a seal without the key", False, True)
    except db.Locked:
        check("a plain token cannot be written over a seal without the key", True, True)
    # The QTH is the case that used to raise, and must not: somebody who has
    # not typed a password still gets to tell ELMER where they are standing.
    db.save_settings(cold, dict(prof["settings"], location={"lat": 1.0, "lon": 2.0, "grid": "AA00"}))
    check("a QTH can, with nobody signed in", db.get_profile(db.connect())["settings"]["location"]["grid"], "AA00")
    db.save_settings(cold, dict(db.get_profile(db.connect())["settings"], license_class="Extra"))
    check("  a plain setting can, and the blobs are kept", (json.loads(raw(conn, alice)["settings"]).get("license_class"),
          sorted(json.loads(raw(conn, alice)["settings"]).get("sealed") or [])), ("Extra", ["repeaterbook_token"]))

    print("\n-- with the key: exactly as saved --")
    warm = db.connect()
    warm.data_key = db.data_key_for(warm, alice, "correct horse")
    check("the right password hands over the key", warm.data_key, got["key"])
    check("  a wrong one does not", db.data_key_for(warm, alice, "correct horst"), None)
    prof = db.get_profile(warm)
    check("the token comes back", prof["settings"]["repeaterbook_token"], "rbuapp_secret_token_1234")
    check("  and the note", db.get_note(warm, "tech2026", "T1A01"), "remember the ohm's law triangle")
    db.save_settings(warm, dict(prof["settings"], location={"lat": 44.9, "lon": -93.2, "grid": "EN34", "short": "Minneapolis"}))
    check("a new QTH goes in plain even with the key in hand", "EN34" in raw(conn, alice)["settings"], True)
    check("  and read back", db.get_profile(warm)["settings"]["location"]["grid"], "EN34")
    db.save_note(warm, "tech2026", "T1A02", "a second note")
    check("a new note is sealed too", conn.execute("SELECT body FROM user_note WHERE question_id = 'T1A02'").fetchone()["body"].startswith("sealed:"), True)
    check("  and both read", sorted(db.notes_for_pool(warm, "tech2026")), ["T1A01", "T1A02"])

    print("\n-- the password changes; nothing is lost --")
    got2 = db.change_password(conn, alice, "battery staple", current="correct horse")
    check("the key is the same key, re-wrapped", got2["key"], got["key"])
    check("  the old password no longer opens it", db.data_key_for(conn, alice, "correct horse"), None)
    check("  the new one does", db.data_key_for(conn, alice, "battery staple"), got["key"])
    check("  and the sealed data is untouched", "rbuapp_secret" in raw(conn, alice)["settings"], False)
    check("  the QTH along with it", db.get_profile(db.connect())["settings"]["location"]["grid"], "EN34")

    print("\n-- the moderator opens the account, not the seal --")
    db.set_moderator(conn, "club-night")
    got3 = db.change_password(conn, alice, "reset-by-mod", current="club-night")
    check("a moderator reset says the sealed data was left behind", (got3["lost"], got3["key"]), (True, None))
    check("  the account still counts as sealed, recoverable", (db.get_user(conn, alice)["sealed"], db.get_user(conn, alice)["recoverable"]), (True, True))
    check("  the new password does not open the seal", db.data_key_for(conn, alice, "reset-by-mod"), None)
    k = db.recover_account(conn, alice, got["recovery"].lower(), "after-recovery")
    check("the recovery code opens it and the account takes a new password", k, got["key"])
    check("  which now opens the seal", db.data_key_for(conn, alice, "after-recovery"), got["key"])
    check("  a wrong code does not", db.recover_account(conn, alice, "AAAA-BBBB-CCCC-DDDD-EEEE", "x"), None)

    print("\n-- the password comes off: back to plain --")
    got4 = db.change_password(conn, alice, "", current="after-recovery")
    check("unlocked and unsealed", (got4["locked"], got4["sealed"]), (False, False))
    row = raw(conn, alice)
    check("  the QTH is plain again", "EN34" in row["settings"], True)
    check("  the note too", conn.execute("SELECT body FROM user_note WHERE question_id = 'T1A01'").fetchone()["body"], "remember the ohm's law triangle")
    check("  the seal's columns are empty", (row["seal_wrap"], row["seal_recovery"]), ("", ""))

    print("\n-- the profile a page sees never carries a wrap --")
    for k in ("seal_wrap", "seal_salt", "seal_recovery", "seal_recovery_salt", "pw_hash", "pw_salt"):
        check(f"  no {k} in the profile", k in db.get_user(conn, alice), False)

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
