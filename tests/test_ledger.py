#!/usr/bin/env python3
"""Every question offered is written down, and the record outlives a reset.

    python3 tests/test_ledger.py

The only way to know how hard a question is, is to watch people meet it. The
ledger (elmer/ledger.py) is where that is kept: one row per question put in
front of a person, with the answer filled in when it comes. This holds what
it has to do to be worth anything - catch every offer, match the answer to
it, name nobody, stay silent, and survive the developer reset that clears
everything else - and the two measures read from it besides hardness: how
long a question takes to become automatic, and how fast it wears off.
"""
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, devreset, difficulty as D, ledger  # noqa: E402
from elmer.app import app, get_pool  # noqa: E402

FAILS = []
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
POOL = "tech2026"
ROOT = Path(__file__).resolve().parents[1]
client = app.test_client()


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def rows():
    led = sqlite3.connect(str(ledger.PATH))
    led.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in led.execute("SELECT * FROM offer ORDER BY id")]
    finally:
        led.close()


print("\na question served is written down before it is answered")
db.set_callsign(db.connect(), "KC9SP")
got = client.get("/api/next?pool=%s&mode=drill" % POOL, environ_base=LOCAL).get_json()
qid = got["question_id"]
led = rows()
check("one offer", len(led), 1)
check("  of that question", led[0]["question_id"], qid)
check("  from the drill", (led[0]["source"], led[0]["mode"]), ("study", "drill"))
check("  and not yet answered", led[0]["answered_ts"], None)

print("\nthe answer closes that offer rather than adding another")
key = get_pool(POOL).by_id[qid]["answer"]
client.post("/api/answer", json={
    "pool": POOL, "question_id": qid, "chosen": got["order"].index(key),
    "order": got["order"], "ms": 4200, "mode": "drill"}, environ_base=LOCAL)
led = rows()
check("still one row", len(led), 1)
check("  now right, with its time", (led[0]["correct"], led[0]["ms"]), (1, 4200.0))

print("\nan offer nobody answers stays on the record as offered")
client.get("/api/next?pool=%s&mode=drill&exclude=%s" % (POOL, qid), environ_base=LOCAL)
led = rows()
check("a second offer", len(led), 2)
check("  left open", led[1]["answered_ts"], None)

print("\na mock exam offers its whole paper, and marks it on submission")
start = client.post("/api/exam/start", json={"pool": POOL}, environ_base=LOCAL).get_json()
items = json.loads(db.connect().execute("SELECT detail FROM exam WHERE id = ?",
                                        (start["exam_id"],)).fetchone()["detail"])["exam"]["items"]
exam_rows = [r for r in rows() if r["source"] == "exam"]
check("every question on the paper is an offer", len(exam_rows), len(items))
client.post("/api/exam/%d/submit" % start["exam_id"],
            json={"responses": {"0": items[0]["answer"]}, "seconds": 600}, environ_base=LOCAL)
exam_rows = [r for r in rows() if r["source"] == "exam"]
check("  each one answered once submitted", all(r["answered_ts"] for r in exam_rows), True)
check("  a blank marked as a miss", sum(1 for r in exam_rows if r["correct"] == 0), len(items) - 1)
check("  and no second row for any of them", len(exam_rows), len(items))

print("\nit names nobody")
raw = ledger.PATH.read_bytes()
check("no callsign in the file", b"KC9SP" in raw or b"kc9sp" in raw, False)
tags = {r["person"] for r in rows()}
check("one person throughout", len(tags), 1)
# The same operator after a reset: a new profile, the same callsign, the same
# person - which is what lets the ledger keep counting first exposures right.
fresh = db.connect()
fresh.execute("UPDATE profile SET created = '2099-01-01T00:00:00+00:00' WHERE id = ?",
              (fresh.user_id,))
fresh.commit()
ledger.answered(fresh, POOL, "T1A01", "T1A", True, 3000, "study", "drill")
check("  the same callsign is the same person after a reset",
      rows()[-1]["person"] in tags, True)

print("\nand says nothing about itself on any page")
said = [p.name for p in list((ROOT / "elmer" / "templates").glob("*.html"))
        + list((ROOT / "elmer" / "static").glob("*.js"))
        if "question ledger" in p.read_text(encoding="utf-8", errors="replace").lower()]
check("no template or script mentions it", said, [])

print("\nthe difficulty measure reads it")
measured = D.load(db.connect(), POOL)
check("every answered offer is a row", len(measured), sum(1 for r in rows() if r["answered_ts"]))

print("\na developer reset leaves it where it is")
if shutil.which("git"):
    repo = Path(tempfile.mkdtemp(prefix="elmer-reset-"))
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "data" / "ledger").mkdir(parents=True)
    # data/ has to hold something tracked, as the real one holds the pools:
    # a directory with nothing tracked in it is removed by git clean whole,
    # exclusions and all.
    (repo / "data" / "pool.json").write_text("{}")
    subprocess.run(["git", "-C", str(repo), "add", "data/pool.json"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "pools"], check=True)
    (repo / "data" / "ledger" / "ledger.db").write_bytes(b"x")
    (repo / "data" / "elmer.db").write_bytes(b"x")
    real = devreset.ROOT
    devreset.ROOT = repo
    try:
        listed = devreset._clean(dry_run=True).stdout
    finally:
        devreset.ROOT = real
    check("the database goes", "data/elmer.db" in listed, True)
    check("  the ledger does not", "ledger" in listed, False)
    shutil.rmtree(repo, ignore_errors=True)
else:
    print("  (no git here - skipped)")

print("\nhow long it takes to become automatic")
T = "2026-09-%02dT12:00:00+00:00"
synthetic = []
for person in ("a", "b", "c"):
    # Three sightings: wrong, right but slow, right and quick.
    for day, ok, ms in ((1, 0, 9000), (2, 1, 12000), (5, 1, 3000)):
        synthetic.append({"user_id": person, "question_id": "Q1", "ts": T % day,
                          "correct": ok, "ms": ms})
auto = D.automaticity(synthetic)["Q1"]
check("three sightings to automatic", auto["sightings"], 3)
check("  four days from first sight", auto["days"], 4.0)
check("  measured, with three people there", auto["measured"], True)

print("\nand how fast it wears off")
wear = []
for person, second in (("a", 1), ("b", 1), ("c", 0), ("d", 0)):
    wear += [{"user_id": person, "question_id": "Q2", "ts": T % 1, "correct": 1, "ms": 3000},
             {"user_id": person, "question_id": "Q2", "ts": T % 11, "correct": second, "ms": 3000}]
# Inside one sitting is not forgetting.
wear += [{"user_id": "e", "question_id": "Q2", "ts": "2026-09-01T12:00:00+00:00", "correct": 1, "ms": 3000},
         {"user_id": "e", "question_id": "Q2", "ts": "2026-09-01T12:05:00+00:00", "correct": 0, "ms": 3000}]
per, pool_wide = D.forgetting(wear)
check("four trials over a gap, the same-sitting pair left out", per["Q2"]["pairs"], 4)
check("  two lost over forty days is one in twenty a day", per["Q2"]["per_day"], 0.05)
check("  a half-life of about two weeks", per["Q2"]["half_life_days"], 13.9)
check("  and the pool-wide figure is the same sum", pool_wide["per_day"], 0.05)

print("\n" + ("FAILED: " + ", ".join(FAILS) if FAILS else "all ok"))
sys.exit(1 if FAILS else 0)
