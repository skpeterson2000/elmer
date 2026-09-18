#!/usr/bin/env python3
"""The Gaming Center keeps the pool gate: a fresh Operator gets Technician
and nothing else at the table, the same rule as the dashboard's cards.

    python3 tests/test_table_gate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401
from elmer import party  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    from elmer.app import app
    c = app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}

    print("\n-- a fresh Operator at the table --")
    r = c.get("/party/1", environ_base=local)
    page = r.data.decode("utf-8")
    check("the table opens", r.status_code, 200)
    check("  Technician is offered", '<option value="technician" selected>Technician</option>' in page, True)
    check("  General is on the list but not open", 'value="general" disabled title=' in page and "not open yet" in page, True)
    check("  nor Amateur Extra", 'value="extra" disabled title=' in page, True)
    check("  asked for General by address, the page opens on Technician", '<option value="technician" selected>' in
          c.get("/party/1?difficulty=general", environ_base=local).data.decode("utf-8"), True)
    r = c.post("/api/party/mode", json={"mode": "golf", "difficulty": "general", "holes": "front"}, environ_base=local)
    check("a round of golf on General is refused", r.status_code, 403)
    check("  with the gate's own sentence", "General opens when" in r.data.decode("utf-8"), True)
    r = c.post("/api/party/round", json={"difficulty": "extra"}, environ_base=local)
    check("a question from Amateur Extra is refused", r.status_code, 403)
    r = c.post("/api/party/round", json={"difficulty": "technician"}, environ_base=local)
    check("  one from Technician is put to the table", r.status_code, 200)

    print("\n-- the gate opens the way it does on the dashboard --")
    c.post("/api/settings", json={"license_class": "General"}, environ_base=local)
    page = c.get("/party/1", environ_base=local).data.decode("utf-8")
    check("a General licensee is offered General and Amateur Extra, the next thing to work toward",
          ('value="general" disabled' in page, 'value="extra" disabled' in page), (False, False))
    r = c.post("/api/party/round", json={"difficulty": "extra"}, environ_base=local)
    check("  and may run the table on it", r.status_code, 200)
    c.post("/api/settings", json={"license_class": "none"}, environ_base=local)
    from elmer import db, gating
    conn = db.connect()
    settings = db.get_profile(conn)["settings"]
    settings[gating.SETTING] = "off"
    db.save_settings(conn, settings)
    conn.commit()
    page = c.get("/party/1", environ_base=local).data.decode("utf-8")
    check("with the gate switched off, every class is open at the table too", "disabled title=" in page, False)
    party.close_room()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
