"""SQLite storage for study progress.

One row per (pool, question) in ``card`` holds the spaced-repetition state;
``answer_log`` keeps the full history so mastery, accuracy trends and the
readiness estimate can be recomputed at any time.
"""
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "elmer.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    callsign        TEXT    NOT NULL DEFAULT '',
    created         TEXT    NOT NULL,
    xp              INTEGER NOT NULL DEFAULT 0,
    streak_days     INTEGER NOT NULL DEFAULT 0,
    best_streak     INTEGER NOT NULL DEFAULT 0,
    last_study_day  TEXT,
    settings        TEXT    NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS card (
    pool_id     TEXT NOT NULL,
    question_id TEXT NOT NULL,
    ease        REAL NOT NULL DEFAULT 2.5,
    interval    REAL NOT NULL DEFAULT 0,
    due         TEXT,
    reps        INTEGER NOT NULL DEFAULT 0,
    lapses      INTEGER NOT NULL DEFAULT 0,
    seen        INTEGER NOT NULL DEFAULT 0,
    correct     INTEGER NOT NULL DEFAULT 0,
    run         INTEGER NOT NULL DEFAULT 0,
    last_seen   TEXT,
    last_ms     INTEGER,
    PRIMARY KEY (pool_id, question_id)
);
CREATE INDEX IF NOT EXISTS card_due ON card (pool_id, due);

CREATE TABLE IF NOT EXISTS answer_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    day         TEXT NOT NULL,
    pool_id     TEXT NOT NULL,
    question_id TEXT NOT NULL,
    section     TEXT NOT NULL,
    correct     INTEGER NOT NULL,
    chosen      INTEGER,
    ms          INTEGER,
    mode        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS log_day ON answer_log (day);
CREATE INDEX IF NOT EXISTS log_pool ON answer_log (pool_id, ts);

CREATE TABLE IF NOT EXISTS exam (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id  TEXT NOT NULL,
    started  TEXT NOT NULL,
    finished TEXT,
    score    INTEGER,
    total    INTEGER,
    passed   INTEGER,
    seconds  INTEGER,
    detail   TEXT
);

CREATE TABLE IF NOT EXISTS achievement (
    code   TEXT PRIMARY KEY,
    earned TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_note (
    pool_id     TEXT NOT NULL,
    question_id TEXT NOT NULL,
    body        TEXT NOT NULL,
    updated     TEXT NOT NULL,
    PRIMARY KEY (pool_id, question_id)
);

CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
"""


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def today():
    return date.today().isoformat()


def connect(path=DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO profile (id, created) VALUES (1, ?)", (today(),)
    )
    conn.commit()
    return conn


def get_profile(conn):
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    prof = dict(row)
    prof["settings"] = json.loads(prof["settings"] or "{}")
    return prof


def save_settings(conn, settings):
    conn.execute("UPDATE profile SET settings = ? WHERE id = 1",
                 (json.dumps(settings),))
    conn.commit()


def set_callsign(conn, callsign):
    conn.execute("UPDATE profile SET callsign = ? WHERE id = 1",
                 (callsign.upper().strip(),))
    conn.commit()


def get_card(conn, pool_id, question_id):
    row = conn.execute(
        "SELECT * FROM card WHERE pool_id = ? AND question_id = ?",
        (pool_id, question_id),
    ).fetchone()
    return dict(row) if row else None


def cards_for_pool(conn, pool_id):
    rows = conn.execute("SELECT * FROM card WHERE pool_id = ?", (pool_id,))
    return {r["question_id"]: dict(r) for r in rows}


def upsert_card(conn, pool_id, question_id, **fields):
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values())
    conn.execute(
        f"INSERT INTO card (pool_id, question_id) VALUES (?, ?) "
        f"ON CONFLICT (pool_id, question_id) DO NOTHING",
        (pool_id, question_id),
    )
    conn.execute(
        f"UPDATE card SET {cols} WHERE pool_id = ? AND question_id = ?",
        vals + [pool_id, question_id],
    )


def log_answer(conn, pool_id, question_id, section, correct, chosen, ms, mode):
    conn.execute(
        "INSERT INTO answer_log (ts, day, pool_id, question_id, section, "
        "correct, chosen, ms, mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (utcnow().isoformat(), today(), pool_id, question_id, section,
         int(correct), chosen, ms, mode),
    )


def get_note(conn, pool_id, question_id):
    row = conn.execute(
        "SELECT body FROM user_note WHERE pool_id = ? AND question_id = ?",
        (pool_id, question_id),
    ).fetchone()
    return row["body"] if row else None


def notes_for_pool(conn, pool_id):
    return {r["question_id"]: r["body"] for r in conn.execute(
        "SELECT question_id, body FROM user_note WHERE pool_id = ?", (pool_id,))}


def save_note(conn, pool_id, question_id, body):
    """Empty body deletes the note, so clearing the box removes it."""
    body = (body or "").strip()
    if not body:
        conn.execute("DELETE FROM user_note WHERE pool_id = ? AND question_id = ?",
                     (pool_id, question_id))
    else:
        conn.execute(
            "INSERT INTO user_note (pool_id, question_id, body, updated) "
            "VALUES (?, ?, ?, ?) ON CONFLICT (pool_id, question_id) "
            "DO UPDATE SET body = excluded.body, updated = excluded.updated",
            (pool_id, question_id, body[:4000], utcnow().isoformat()))
    conn.commit()
    return body or None


def kv_get(conn, key, default=None):
    row = conn.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
    return json.loads(row["v"]) if row else default


def kv_set(conn, key, value):
    conn.execute(
        "INSERT INTO kv (k, v) VALUES (?, ?) "
        "ON CONFLICT (k) DO UPDATE SET v = excluded.v",
        (key, json.dumps(value)),
    )
    conn.commit()
