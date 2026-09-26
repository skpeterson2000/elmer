"""The question ledger: every question this unit puts in front of a person.

Nothing in ELMER knows how hard a question is except by watching people meet
it. Guessing from length or from whether it has a formula in it is a guess
wearing the clothes of data. If eight people in ten miss a question the first
time they see it, that question is hard, and the only way to know that is to
have written down the eight and the ten. The ledger writes them down.

It keeps one row per offer - the drill serving a question, a mock exam
putting one on a paper, a table in a hall answering one - and fills in the
answer when it comes: right or not, how long it took. From that record three
things can be measured over the whole pool, and they get better with every
answer given on this unit:

- **How hard a question is**, from how it went the first time each person
  met it (difficulty.py).
- **How long it takes to become automatic**: how many sightings, and over how
  many days, before a person answers it right without having to think.
- **How fast it is forgotten**: after a right answer, how often the next one
  is wrong, against the time between them.

**It survives a developer reset.** The database a reset clears belongs to the
people studying on this unit - their cards, their streaks, their notes. The
ledger belongs to the pool: what has been learned about the questions
themselves. Throwing it away would restart the measure from nothing every
time the program is reset to see its first run again. devreset.py leaves this
directory alone.

**It is silent.** Nothing on any page mentions it and nothing reads it back
to the person answering. A measure people know is running changes how they
answer, and then it measures that instead.

**It names nobody.** A person is a keyed hash: of the callsign when there is
one, so the same operator is the same person across a reset, and otherwise
of the profile. The key is made on this unit, kept in the ledger, and never
leaves it - the tag cannot be turned back into a callsign by anybody holding
only the file. Hall rows arrive already hashed under the net's own key.

A failure to write the ledger never costs anybody an answer. It is logged
once, and the study goes on.
"""
import hashlib
import hmac
import logging
import secrets
import sqlite3
from datetime import date, datetime, timezone

from . import paths

log = logging.getLogger("elmer")

DIR = paths.STATE / "ledger"
PATH = DIR / "ledger.db"
# What devreset.py must leave alone, relative to the checkout. The reset
# cleans the checkout's own data/, whatever ELMER_STATE says.
RESET_KEEPS = "data/ledger"

# How long an offer waits for its answer. Past this, an answer is a new
# sighting rather than the reply to an offer left open on a page overnight.
ANSWER_WINDOW_S = 6 * 3600

SCHEMA = """
CREATE TABLE IF NOT EXISTS offer (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    day         TEXT NOT NULL,
    pool_id     TEXT NOT NULL,
    question_id TEXT NOT NULL,
    section     TEXT NOT NULL DEFAULT '',
    person      TEXT NOT NULL,
    source      TEXT NOT NULL,
    mode        TEXT NOT NULL DEFAULT '',
    license     TEXT NOT NULL DEFAULT '',
    answered_ts TEXT,
    correct     INTEGER,
    ms          REAL
);
CREATE INDEX IF NOT EXISTS offer_person ON offer (person, pool_id, question_id, id);
CREATE INDEX IF NOT EXISTS offer_pool ON offer (pool_id, id);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_warned = False


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _open():
    DIR.mkdir(parents=True, exist_ok=True)
    led = sqlite3.connect(str(PATH), timeout=5)
    led.row_factory = sqlite3.Row
    led.executescript(SCHEMA)
    if not led.execute("SELECT 1 FROM meta WHERE key = 'secret'").fetchone():
        led.execute("INSERT INTO meta (key, value) VALUES ('secret', ?), ('created', ?)",
                    (secrets.token_hex(32), _now().isoformat()))
        led.commit()
    return led


def _write(what, fn):
    """Run one write, and never let it reach the answer that caused it."""
    global _warned
    led = None
    try:
        led = _open()
        out = fn(led)
        led.commit()
        if _warned:
            log.info("question ledger writable again at %s", PATH)
            _warned = False
        return out
    except (OSError, sqlite3.Error) as exc:
        # Once per failure, not once per answer: an evening of study against
        # a read-only card would otherwise be an evening of this line.
        if not _warned:
            log.warning("question ledger: could not record %s at %s: %s", what, PATH, exc)
            _warned = True
        return None
    finally:
        if led is not None:
            led.close()


def _secret(led):
    return led.execute("SELECT value FROM meta WHERE key = 'secret'").fetchone()["value"]


def _person(led, conn):
    """The opaque tag for whoever is signed in on this connection."""
    row = conn.execute("SELECT id, created, callsign, settings FROM profile WHERE id = ?",
                       (conn.user_id,)).fetchone()
    if row is None:
        ident = f"profile:{conn.user_id}"
    elif (row["callsign"] or "").strip():
        ident = "call:" + row["callsign"].strip().upper()
    else:
        ident = f"profile:{row['id']}:{row['created']}"
    return hmac.new(bytes.fromhex(_secret(led)), ident.encode("utf-8"),
                    hashlib.sha256).hexdigest()[:20]


def _license(conn):
    from .db import _modernise, license_of
    import json
    row = conn.execute("SELECT settings FROM profile WHERE id = ?",
                       (conn.user_id,)).fetchone()
    if row is None:
        return ""
    try:
        s = _modernise(json.loads(row["settings"] or "{}"))
    except ValueError:
        return ""
    return license_of(s.get("license_class")
                      or (s.get("license") or {}).get("license_class"))


def offered(conn, pool_id, question_id, section, source, mode=""):
    """A question has been put in front of the person on `conn`."""
    def go(led):
        now = _now()
        led.execute(
            "INSERT INTO offer (ts, day, pool_id, question_id, section, person, "
            "source, mode, license) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now.isoformat(), date.today().isoformat(), pool_id, question_id,
             section or "", _person(led, conn), source, mode or "", _license(conn)))
    _write("an offer", go)


def answered(conn, pool_id, question_id, section, correct, ms, source, mode=""):
    """The person on `conn` answered. Closes the offer that asked it, if one
    is open; otherwise the offer and the answer are one row - a table's
    question, say, which was offered somewhere the ledger was not watching."""
    def go(led):
        now = _now()
        person = _person(led, conn)
        cutoff = datetime.fromtimestamp(now.timestamp() - ANSWER_WINDOW_S,
                                        timezone.utc).isoformat()
        open_offer = led.execute(
            "SELECT id FROM offer WHERE person = ? AND pool_id = ? AND question_id = ? "
            "AND answered_ts IS NULL AND ts >= ? ORDER BY id DESC LIMIT 1",
            (person, pool_id, question_id, cutoff)).fetchone()
        if open_offer:
            led.execute("UPDATE offer SET answered_ts = ?, correct = ?, ms = ? WHERE id = ?",
                        (now.isoformat(), int(bool(correct)), ms, open_offer["id"]))
            return
        led.execute(
            "INSERT INTO offer (ts, day, pool_id, question_id, section, person, source, "
            "mode, license, answered_ts, correct, ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now.isoformat(), date.today().isoformat(), pool_id, question_id,
             section or "", person, source, mode or "", _license(conn),
             now.isoformat(), int(bool(correct)), ms))
    _write("an answer", go)


def hall_answers(pool_id, question_id, section, rows, mode="hall"):
    """A round at the tables: one row per person, already hashed by the net."""
    def go(led):
        now = _now().isoformat()
        for r in rows:
            led.execute(
                "INSERT INTO offer (ts, day, pool_id, question_id, section, person, "
                "source, mode, license, answered_ts, correct, ms) "
                "VALUES (?, ?, ?, ?, ?, ?, 'hall', ?, ?, ?, ?, ?)",
                (now, date.today().isoformat(), pool_id, question_id, section or "",
                 "hall:" + r["who"], mode or "hall", r["license"], now,
                 int(bool(r["correct"])), r["ms"]))
    _write("a hall round", go)


def backfill(conn):
    """Bring in what this unit's database recorded before the ledger existed.

    Once, and only the rows older than the ledger itself - anything after that
    was written here as it happened. Study rows are keyed by the profile they
    belong to now; hall rows keep the tag the net gave them.
    """
    def go(led):
        if led.execute("SELECT 1 FROM meta WHERE key = 'backfilled'").fetchone():
            return 0
        created = led.execute("SELECT value FROM meta WHERE key = 'created'").fetchone()["value"]
        n = 0
        people = {}
        rows = conn.execute(
            "SELECT user_id, ts, day, pool_id, question_id, section, correct, ms, mode "
            "FROM answer_log WHERE ts < ? ORDER BY id", (created,)).fetchall()
        real_user = conn.user_id
        try:
            for r in rows:
                if r["user_id"] not in people:
                    conn.user_id = r["user_id"]
                    people[r["user_id"]] = (_person(led, conn), _license(conn))
                person, lic = people[r["user_id"]]
                led.execute(
                    "INSERT INTO offer (ts, day, pool_id, question_id, section, person, "
                    "source, mode, license, answered_ts, correct, ms) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (r["ts"], r["day"], r["pool_id"], r["question_id"], r["section"],
                     person, "exam" if r["mode"] == "exam" else "study", r["mode"],
                     lic, r["ts"], r["correct"], r["ms"]))
                n += 1
        finally:
            conn.user_id = real_user
        try:
            hall = conn.execute(
                "SELECT ts, day, pool_id, question_id, section, who, license, correct, "
                "ms, mode FROM hall_log WHERE ts < ? ORDER BY id", (created,)).fetchall()
        except sqlite3.OperationalError:     # a database from before the hall log
            hall = []
        for h in hall:
            led.execute(
                "INSERT INTO offer (ts, day, pool_id, question_id, section, person, "
                "source, mode, license, answered_ts, correct, ms) "
                "VALUES (?, ?, ?, ?, ?, ?, 'hall', ?, ?, ?, ?, ?)",
                (h["ts"], h["day"], h["pool_id"], h["question_id"], h["section"],
                 "hall:" + h["who"], h["mode"], h["license"], h["ts"], h["correct"], h["ms"]))
            n += 1
        led.execute("INSERT INTO meta (key, value) VALUES ('backfilled', ?)",
                    (_now().isoformat(),))
        if n:
            log.info("question ledger: brought in %d earlier answer(s)", n)
        return n
    return _write("the earlier answers", go) or 0


def answers(pool_id):
    """Every answered offer for a pool, oldest first, as plain dicts."""
    try:
        led = _open()
    except (OSError, sqlite3.Error) as exc:
        log.warning("question ledger: could not read %s: %s", PATH, exc)
        return []
    try:
        return [dict(r) for r in led.execute(
            "SELECT person, ts, day, question_id, section, source, license, "
            "correct, ms, answered_ts FROM offer "
            "WHERE pool_id = ? AND answered_ts IS NOT NULL ORDER BY id", (pool_id,))]
    except sqlite3.Error as exc:
        log.warning("question ledger: could not read %s: %s", PATH, exc)
        return []
    finally:
        led.close()
