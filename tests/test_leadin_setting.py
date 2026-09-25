#!/usr/bin/env python3
"""The run-up the host can set: "Playing in 30 s", counted on every screen.

    python3 tests/test_leadin_setting.py

The hall always had five seconds of "Get ready" before the first question.
Now the host chooses how many, on the Playing press, and the unit
remembers; the program's own hand-over from an intermission uses the
same number; and the run-up says which it is - the first question of the
evening or the next one - so a screen can put words on the clock.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import app as appmod, db, hall, netcontrol  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def run():
    print("\n-- the hall's default run-up --")
    check("five seconds, as it always was", hall.default_lead_in(), 5.0)
    check("set to thirty", hall.set_default_lead_in(30), 30.0)
    check("  kept within reason: not under three", hall.set_default_lead_in(0.5), 3.0)
    check("  nor over ten minutes", hall.set_default_lead_in(9999), 600.0)
    hall.set_default_lead_in(5)

    print("\n-- which run-up it is --")
    net = netcontrol.Net(name="t")
    net.begin_lead_in(20)
    v = net.lead_in_view()
    check("to the first question, with nothing played", v["first"], True)
    check("  of twenty seconds", v["seconds"], 20.0)
    net.cancel_lead_in()

    print("\n-- the host's press carries it, and the unit remembers --")
    client = appmod.app.test_client()
    local = {"REMOTE_ADDR": "127.0.0.1"}
    client.post("/api/net/open", json={"difficulty": "technician"}, environ_base=local)
    r = client.post("/api/net/show/mode", json={"mode": "play", "lead_in": 45}, environ_base=local)
    check("taken", r.status_code, 200)
    check("  the hall's default is now forty-five", hall.default_lead_in(), 45.0)
    check("  and the host's view says so",
          client.get("/api/net/show", environ_base=local).get_json()["lead_in_setting"], 45.0)
    conn = db.connect()
    check("  remembered on the unit", db.unit_get(conn, appmod.LEAD_IN_KEY, ""), "45.0")
    r = client.post("/api/net/show/mode", json={"mode": "play", "lead_in": "soon"}, environ_base=local)
    check("nonsense is refused", r.status_code, 400)
    client.post("/api/net/show/mode", json={"mode": "intermission"}, environ_base=local)
    r = client.post("/api/net/show/mode", json={"mode": "play"}, environ_base=local)
    check("a press with no number keeps the remembered one",
          (r.status_code, hall.default_lead_in()), (200, 45.0))
    live = hall.conductor()
    check("  and the conductor has it", live.lead_in if live else None, 45.0)
    client.post("/api/net/end", json={}, environ_base=local)

    print("\n-- and it comes back at the next net --")
    hall.set_default_lead_in(5)
    client.post("/api/net/open", json={"difficulty": "technician"}, environ_base=local)
    check("restored from the unit at open", hall.default_lead_in(), 45.0)
    client.post("/api/net/end", json={}, environ_base=local)
    conn.close()

    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    finally:
        hall.halt()
        netcontrol.close_net()
        time.sleep(0.1)
