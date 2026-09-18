#!/usr/bin/env python3
"""Checks that a question answered at a table is credited where a study
answer would be: to the player's own record on this unit, by their
callsign or by the name of their account, and to the name-free ledger the
difficulty estimate reads - and to nobody's record when the name at the
table is nobody's here.

    python3 tests/test_table_credit.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, party  # noqa: E402
import elmer.app as appmod  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def logged(connection):
    return [tuple(r) for r in connection.execute("SELECT user_id, question_id, correct, mode FROM answer_log ORDER BY ts")]


def main():
    from elmer import autoplay
    client = appmod.app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    client.post("/api/settings", json={"callsign": "KC9SP", "license_class": "General"}, environ_base=local)
    client.post("/api/users/rename", json={"id": 1, "name": "Scott"}, environ_base=local)
    client.post("/api/users/add", json={"name": "Grandkid", "shared": False}, environ_base=local)
    client.post("/api/users/add", json={"name": "Sue"}, environ_base=local)
    client.post("/api/users/switch", json={"id": 1}, environ_base=local)

    room = party.room(create=True, cohorts=1)
    seats = {name: room.join(name)[0].id for name in ("KC9SP", "grandkid", "Nobody Here")}
    client.post("/api/party/mode", json={"mode": "tournament"}, environ_base=local)
    autoplay.stop()
    room.round = None
    rnd = appmod._ask_party("general", None, 30)
    for name, pid in seats.items():
        room.submit(pid, rnd.answer_index if name != "grandkid" else (rnd.answer_index + 1) % 4, 3000, 3000)
    summary = room.close_round()
    connection = db.connect()
    rows = logged(connection)
    print("\n-- one tournament round, three at the table --")
    check("the callsign's answer is on the callsign's account", [r for r in rows if r[0] == 1], [(1, summary["question_id"], 1, "table:tournament")])
    check("  the grandchild's, seated by name in the wrong case, on theirs - and the miss is a miss", [r for r in rows if r[0] == 2], [(2, summary["question_id"], 0, "table:tournament")])
    check("  a name that is nobody's here is credited to nobody", len(rows), 2)
    check("  and every answer, named or not, reached the ledger the difficulty estimate reads",
          connection.execute("SELECT COUNT(*) FROM hall_log WHERE question_id = ?", (summary["question_id"],)).fetchone()[0], 3)
    card = db.get_card(connection, summary["pool"], summary["question_id"])
    connection.user_id = 2
    kid_card = db.get_card(connection, summary["pool"], summary["question_id"])
    check("  the cards were graded like a study answer: seen once each, the miss lapsed", (card["seen"], card["correct"], kid_card["seen"], kid_card["correct"]), (1, 1, 1, 0))

    print("\n-- extra credit: a watcher's answer counts in the record and the ledger, and pays in luck --")
    client.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "front", "seconds": 30, "companions": 0, "tee_in": 0}, environ_base=local)
    autoplay.stop()
    room.round = None
    g = room.golf
    away = g.away()
    watcher = next(p for p in g.players if p != away)
    rnd = appmod._ask_party("general", None, 30)
    extra, why = room.submit_extra(watcher, rnd.answer_index, 1200)
    check("a watcher answers along", (extra is not None, why), (True, None))
    check("  which does not close the round", room.everyone_answered(), False)
    room.submit(away, rnd.answer_index, 3000, 3000)
    summary = room.close_round()
    check("  both answers reached the difficulty ledger - two samples, not one",
          connection.execute("SELECT COUNT(*) FROM hall_log WHERE question_id = ?", (summary["question_id"],)).fetchone()[0], 2)
    check("  and the watcher's is in their study record too, marked as golf",
          connection.execute("SELECT COUNT(*) FROM answer_log WHERE question_id = ? AND mode LIKE 'table:%'", (summary["question_id"],)).fetchone()[0], 2)
    check("  and luck is theirs for their next stroke", watcher in g.luck, True)
    autoplay.stop(); room.end_golf(); room.clear_bots()

    print("\n-- two accounts with one name --")
    client.post("/api/users/add", json={"name": "Sue"}, environ_base=local)   # a second Sue
    twins = [p["id"] for p in db.users(connection) if (p.get("name") or "").lower() == "sue"]
    sue = room.join("Sue")[0].id
    rnd = appmod._ask_party("general", None, 30)
    room.submit(sue, rnd.answer_index, 3000, 3000)
    summary = room.close_round()
    check("neither Sue is credited by a name two accounts share", [r for r in logged(connection) if r[0] in twins], [])

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    import os
    code = main()
    os._exit(code)
