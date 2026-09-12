"""A hall evening, end to end through the program's own routes, and what it
leaves in the unit's log.

Nothing in this file talks to netcontrol directly. Net control is opened
the way the host page opens it, a table checks in and reports the way a
table does, a tournament round is put the way the conductor puts one - and
then the log is read back. The round route is here because nothing else
exercised it, and a parameter that shadowed the difficulty module took
every plain tournament round down for an afternoon without a test noticing.

    python3 tests/test_hall_log.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, difficulty, netcontrol  # noqa: E402

_spare = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_spare.close()
db.DB_PATH = _spare.name

from elmer.app import app  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


app.config["TESTING"] = True
client = app.test_client()


def post(path, body=None):
    r = client.post(path, json=body or {})
    return r.status_code, (r.get_json() or {})


print("\na net opens and a tournament round is put to it")
try:
    code, board = post("/api/net/open", {"difficulty": "technician", "name": "Log night"})
    check("net control opened", code, 200)
    code, _ = post("/api/net/checkin", {"unit": "table-1", "name": "Poldhu", "players": 3})
    check("a table checked in", code, 200)
    code, board = post("/api/net/round", {"difficulty": "technician", "seconds": 30})
    check("a plain tournament round is put - the plan drawn from the measure",
          code, 200)
    q = (board.get("round") or {}).get("question_id")
    check("  with a question on it", bool(q), True)
    n = (board.get("round") or {}).get("number")

    print("\nthe table reports, and the round closes into the log")
    code, got = post("/api/net/report", {
        "unit": "table-1", "round": n,
        "players": [{"name": "KC9SP", "correct": True, "ms": 2100,
                     "license": "Extra", "cert_name": "S. Peterson"},
                    {"name": "Sparks", "correct": False, "ms": 6400, "license": "none"},
                    {"name": "Ann", "correct": True, "ms": 3300},
                    {"name": "Rig", "correct": True, "ms": 300, "bot": "practice"}]})
    check("the report was taken", (code, got.get("counted")), (200, 4))
    code, closed = post("/api/net/close")
    check("the round closed", code, 200)
    summary = closed.get("summary") or {}
    check("  and the board's summary names nobody's class or certificate",
          any(k in r for r in summary.get("top", []) for k in ("license", "cert_name")),
          False)
    check("  nor carries the rows themselves", "given" in summary, False)

    conn = db.connect()
    rows = conn.execute("SELECT unit, who, license, correct, ms FROM hall_log "
                        "ORDER BY id").fetchall()
    check("three people in the log, the practice player not among them", len(rows), 3)
    check("  the table is named, the people are not",
          ([r["unit"] for r in rows], all(len(r["who"]) == 16 for r in rows)),
          (["table-1"] * 3, True))
    flat = " ".join(r["who"] for r in rows)
    check("  no callsign, name or certificate name in it",
          any(s in flat for s in ("KC9SP", "Sparks", "Ann", "Peterson")), False)
    check("  the license classes as stated - Extra, none, unsaid",
          [r["license"] for r in rows], ["Extra", "none", ""])
    check("  right and wrong, with the time", [(r["correct"], r["ms"]) for r in rows],
          [(1, 2100.0), (0, 6400.0), (1, 3300.0)])

    print("\nand the class report reads it")
    r = client.get("/api/difficulty?pool=tech2026").get_json()
    check("the hall is a source", r["sources"]["hall"], 3)
    classes = {c["license"]: c for c in r["classes"]}
    check("  by class", sorted(classes), ["", "Extra", "none"])
    check("  the unlicensed player's miss", classes["none"]["miss_rate"], 1.0)
    check("  the Extra's time, raw", classes["Extra"]["median_ms"], 2100)
    conn.close()
finally:
    netcontrol.close_net()

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all good"))
sys.exit(1 if FAILS else 0)
