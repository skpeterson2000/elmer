"""SQLite storage for study progress.

One row per (user, pool, question) in ``card`` holds the spaced-repetition
state; ``answer_log`` keeps the full history so mastery, accuracy trends and
the readiness estimate can be recomputed at any time.

Everything personal is scoped to a user, because one ELMER in a house is shared
the way a radio is: whoever sits down should get their own progress, their own
titles and their own streak, without anyone having to log out of anything.  The
current user is carried by the browser rather than by the server, so the unit
in the shack and a phone on the sofa can be two different people at once.

Rather than thread a user id through eighty call sites, the connection carries
it: :class:`Connection` holds ``user_id`` and the queries here read it.  A
caller that wants somebody else's data sets ``conn.user_id`` and asks the same
question.

There are no passwords.  Switching user is a choice, not an authentication -
anyone who can reach ELMER can be anyone on it.  That is a deliberate trade for
a family appliance holding nothing but how many radio questions somebody got
right, and it is worth knowing before putting one on a network with people you
would not hand the radio to.
"""
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "elmer.db"

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL DEFAULT '',
    callsign        TEXT    NOT NULL DEFAULT '',
    created         TEXT    NOT NULL,
    xp              INTEGER NOT NULL DEFAULT 0,
    streak_days     INTEGER NOT NULL DEFAULT 0,
    best_streak     INTEGER NOT NULL DEFAULT 0,
    last_study_day  TEXT,
    last_seen       TEXT,
    settings        TEXT    NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS card (
    user_id     INTEGER NOT NULL DEFAULT 1,
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
    PRIMARY KEY (user_id, pool_id, question_id)
);
CREATE INDEX IF NOT EXISTS card_due ON card (user_id, pool_id, due);

CREATE TABLE IF NOT EXISTS answer_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL DEFAULT 1,
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
CREATE INDEX IF NOT EXISTS log_day ON answer_log (user_id, day);
CREATE INDEX IF NOT EXISTS log_pool ON answer_log (user_id, pool_id, ts);

CREATE TABLE IF NOT EXISTS exam (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL DEFAULT 1,
    pool_id  TEXT NOT NULL,
    started  TEXT NOT NULL,
    finished TEXT,
    score    INTEGER,
    total    INTEGER,
    passed   INTEGER,
    seconds  INTEGER,
    detail   TEXT
);
CREATE INDEX IF NOT EXISTS exam_user ON exam (user_id, pool_id, finished);

CREATE TABLE IF NOT EXISTS achievement (
    user_id INTEGER NOT NULL DEFAULT 1,
    code    TEXT NOT NULL,
    earned  TEXT NOT NULL,
    PRIMARY KEY (user_id, code)
);

CREATE TABLE IF NOT EXISTS user_note (
    user_id     INTEGER NOT NULL DEFAULT 1,
    pool_id     TEXT NOT NULL,
    question_id TEXT NOT NULL,
    body        TEXT NOT NULL,
    updated     TEXT NOT NULL,
    PRIMARY KEY (user_id, pool_id, question_id)
);

CREATE TABLE IF NOT EXISTS cw_char (
    user_id  INTEGER NOT NULL DEFAULT 1,
    ch       TEXT NOT NULL,
    sent     INTEGER NOT NULL DEFAULT 0,
    copied   INTEGER NOT NULL DEFAULT 0,
    confused TEXT    NOT NULL DEFAULT '{}',
    updated  TEXT,
    PRIMARY KEY (user_id, ch)
);

CREATE TABLE IF NOT EXISTS kv (
    user_id INTEGER NOT NULL DEFAULT 1,
    k       TEXT NOT NULL,
    v       TEXT NOT NULL,
    PRIMARY KEY (user_id, k)
);

CREATE TABLE IF NOT EXISTS setting (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
"""

# Tables that hold somebody's own work, and so gained a user_id when ELMER
# learned to be shared.  Each entry is the table and the primary key it should
# end up with; the migration rebuilds any that still have the old shape.
PER_USER = (
    ("card", "PRIMARY KEY (user_id, pool_id, question_id)"),
    ("answer_log", None),
    ("exam", None),
    ("achievement", "PRIMARY KEY (user_id, code)"),
    ("user_note", "PRIMARY KEY (user_id, pool_id, question_id)"),
    ("cw_char", "PRIMARY KEY (user_id, ch)"),
    ("kv", "PRIMARY KEY (user_id, k)"),
)


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def today():
    return date.today().isoformat()


class Connection(sqlite3.Connection):
    """A connection that knows whose data it is looking at.

    Every query below is scoped to ``user_id``.  Keeping it on the connection
    rather than in each signature is what let ELMER become multi-user without
    rewriting every call site - and it means a query that forgets to scope
    itself stands out, rather than quietly returning the whole household.
    """

    user_id = 1


def _columns(conn, table):
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def _statements():
    """SCHEMA as separate statements, so it can be run inside a transaction.

    ``executescript`` commits whatever is open before it runs, which would take
    the migration's own transaction apart underneath it.
    """
    return [line.strip() for line in SCHEMA.split(";") if line.strip()]


def _ddl(table):
    """Just the CREATE TABLE for one table, in its current shape."""
    wanted = f"CREATE TABLE IF NOT EXISTS {table} ("
    for statement in _statements():
        if statement.startswith(wanted):
            return statement
    raise KeyError(table)


def _rebuild(conn, table, as_user=None):
    """Recreate one table in its current shape, carrying its rows over.

    SQLite cannot add a column to a primary key or drop a CHECK constraint, so
    a table that needs either is rebuilt beside itself and swapped.  Its
    indexes go first: an index keeps its name when its table is renamed, and
    the name would then collide with the one the new table wants.
    """
    carried = _columns(conn, table)
    for index in conn.execute(f"PRAGMA index_list({table})").fetchall():
        if not index["name"].startswith("sqlite_autoindex"):
            conn.execute(f"DROP INDEX IF EXISTS {index['name']}")
    conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
    conn.execute(_ddl(table))
    shared = [c for c in carried if c in _columns(conn, table)]
    columns = ", ".join(shared)
    if as_user is None:
        conn.execute(f"INSERT INTO {table} ({columns}) "
                     f"SELECT {columns} FROM {table}_old")
    else:
        conn.execute(f"INSERT INTO {table} (user_id, {columns}) "
                     f"SELECT {int(as_user)}, {columns} FROM {table}_old")
    conn.execute(f"DROP TABLE {table}_old")


def migrate(conn):
    """Bring an existing database up to SCHEMA_VERSION.

    Version 2 is when ELMER learned to be shared.  Everything personal gained a
    user_id, which for tables like ``card`` means a new primary key - so those
    tables are rebuilt beside themselves and swapped, with every existing row
    becoming user 1.  Whoever was using ELMER before keeps every card, every
    answer and every title, and simply becomes the first user on the unit.

    The whole thing runs in one transaction: an interruption, a power cut or a
    failure part way through leaves the database exactly as it was.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= SCHEMA_VERSION:
        return version

    if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'profile'"
    ).fetchone():
        for statement in _statements():      # a new database is born current
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        return SCHEMA_VERSION

    import logging
    log = logging.getLogger("elmer")
    log.info("migrating the database from version %s to %s - "
             "existing progress becomes the first user",
             version, SCHEMA_VERSION)

    was = conn.isolation_level
    conn.isolation_level = None              # this transaction is managed here
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("BEGIN")
        if "name" not in _columns(conn, "profile"):
            # Rebuilt for its CHECK (id = 1), which is what limited ELMER to
            # one person in the first place.
            _rebuild(conn, "profile")
        for table, _pk in PER_USER:
            if "user_id" not in _columns(conn, table):
                _rebuild(conn, table, as_user=1)
                log.info("  %s carried over", table)
        for statement in _statements():      # indexes, and anything missing
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.isolation_level = was
        conn.execute("PRAGMA foreign_keys=ON")
    log.info("database migrated")
    return SCHEMA_VERSION


def connect(path=None, user_id=None):
    # Read DB_PATH now rather than binding it as a default when this module is
    # imported: a default is fixed at import time, so pointing DB_PATH at
    # another file - a test, a second database - silently had no effect.
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, factory=Connection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    migrate(conn)
    # Every time, not only on a migration: a table added by a later release
    # appears here on its own, which is what CREATE TABLE IF NOT EXISTS is for.
    # Anything that changes an existing table still needs migrate().
    for statement in _statements():
        conn.execute(statement)
    # There is always somebody: an ELMER with no users has no dashboard to show
    # and nowhere to put the first answered question.
    if not conn.execute("SELECT 1 FROM profile LIMIT 1").fetchone():
        conn.execute("INSERT INTO profile (id, name, created) VALUES (1, ?, ?)",
                     ("Operator", today()))
        conn.commit()
    # An id that names nobody - a stale cookie, a user since removed - is not
    # an error worth showing anyone; it just means the first user on the unit.
    conn.user_id = (user_id if user_id and user_exists(conn, user_id)
                    else first_user_id(conn))
    return conn


def first_user_id(conn):
    row = conn.execute("SELECT id FROM profile ORDER BY id LIMIT 1").fetchone()
    return row["id"] if row else 1


# --------------------------------------------------------------------------
# who is playing
# --------------------------------------------------------------------------

def display_name(profile):
    """What to call somebody.

    A callsign is a thing you earned from the FCC by sitting an exam, so if
    there is one on the profile that is the name ELMER uses - the same respect
    an operator gets on the air.  Everyone else is called by their name, which
    is theirs and needs no licence.
    """
    if not profile:
        return "Operator"
    return (profile.get("callsign") or "").strip().upper() \
        or (profile.get("name") or "").strip() or "Operator"


def _row_to_profile(row):
    prof = dict(row)
    prof["settings"] = json.loads(prof["settings"] or "{}")
    prof["display_name"] = display_name(prof)
    prof["licensed"] = bool((prof.get("callsign") or "").strip())
    return prof


def users(conn):
    """Everyone on this unit, in the order they joined."""
    return [_row_to_profile(r) for r in
            conn.execute("SELECT * FROM profile ORDER BY id")]


def get_user(conn, user_id):
    row = conn.execute("SELECT * FROM profile WHERE id = ?", (user_id,)).fetchone()
    return _row_to_profile(row) if row else None


def user_exists(conn, user_id):
    return bool(conn.execute("SELECT 1 FROM profile WHERE id = ?",
                             (user_id,)).fetchone())


def add_user(conn, name, callsign=""):
    """Put somebody new on the unit.  Returns the new profile."""
    name = (name or "").strip()[:40]
    if not name:
        raise ValueError("a user needs a name")
    cur = conn.execute(
        "INSERT INTO profile (name, callsign, created) VALUES (?, ?, ?)",
        (name, (callsign or "").strip().upper(), today()))
    conn.commit()
    return get_user(conn, cur.lastrowid)


def rename_user(conn, user_id, name):
    name = (name or "").strip()[:40]
    if not name:
        raise ValueError("a user needs a name")
    conn.execute("UPDATE profile SET name = ? WHERE id = ?", (name, user_id))
    conn.commit()
    return get_user(conn, user_id)


def remove_user(conn, user_id):
    """Take somebody off the unit, with everything of theirs.

    Refused for the last one standing: an ELMER with nobody on it has no
    dashboard to show.
    """
    if conn.execute("SELECT COUNT(*) c FROM profile").fetchone()["c"] <= 1:
        raise ValueError("this is the only user on the unit")
    for table, _pk in PER_USER:
        conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM profile WHERE id = ?", (user_id,))
    conn.commit()


def touch_user(conn, user_id=None):
    """Remember when somebody was last here, for the user picker."""
    conn.execute("UPDATE profile SET last_seen = ? WHERE id = ?",
                 (utcnow().isoformat(), user_id or conn.user_id))
    conn.commit()


def get_profile(conn):
    row = conn.execute("SELECT * FROM profile WHERE id = ?",
                       (conn.user_id,)).fetchone()
    if row is None:                     # the current user was removed under us
        conn.user_id = first_user_id(conn)
        row = conn.execute("SELECT * FROM profile WHERE id = ?",
                           (conn.user_id,)).fetchone()
    return _row_to_profile(row)


def save_settings(conn, settings):
    conn.execute("UPDATE profile SET settings = ? WHERE id = ?",
                 (json.dumps(settings), conn.user_id))
    conn.commit()


def set_callsign(conn, callsign):
    conn.execute("UPDATE profile SET callsign = ? WHERE id = ?",
                 (callsign.upper().strip(), conn.user_id))
    conn.commit()


def get_card(conn, pool_id, question_id):
    row = conn.execute(
        "SELECT * FROM card WHERE user_id = ? AND pool_id = ? AND question_id = ?",
        (conn.user_id, pool_id, question_id),
    ).fetchone()
    return dict(row) if row else None


def cards_for_pool(conn, pool_id):
    rows = conn.execute("SELECT * FROM card WHERE user_id = ? AND pool_id = ?",
                        (conn.user_id, pool_id))
    return {r["question_id"]: dict(r) for r in rows}


def upsert_card(conn, pool_id, question_id, **fields):
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values())
    conn.execute(
        "INSERT INTO card (user_id, pool_id, question_id) VALUES (?, ?, ?) "
        "ON CONFLICT (user_id, pool_id, question_id) DO NOTHING",
        (conn.user_id, pool_id, question_id),
    )
    conn.execute(
        f"UPDATE card SET {cols} "
        f"WHERE user_id = ? AND pool_id = ? AND question_id = ?",
        vals + [conn.user_id, pool_id, question_id],
    )


def log_answer(conn, pool_id, question_id, section, correct, chosen, ms, mode):
    conn.execute(
        "INSERT INTO answer_log (user_id, ts, day, pool_id, question_id, "
        "section, correct, chosen, ms, mode) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (conn.user_id, utcnow().isoformat(), today(), pool_id, question_id,
         section, int(correct), chosen, ms, mode),
    )


def get_note(conn, pool_id, question_id):
    row = conn.execute(
        "SELECT body FROM user_note "
        "WHERE user_id = ? AND pool_id = ? AND question_id = ?",
        (conn.user_id, pool_id, question_id),
    ).fetchone()
    return row["body"] if row else None


def notes_for_pool(conn, pool_id):
    return {r["question_id"]: r["body"] for r in conn.execute(
        "SELECT question_id, body FROM user_note WHERE user_id = ? AND pool_id = ?",
        (conn.user_id, pool_id))}


def save_note(conn, pool_id, question_id, body):
    """Empty body deletes the note, so clearing the box removes it."""
    body = (body or "").strip()
    if not body:
        conn.execute("DELETE FROM user_note "
                     "WHERE user_id = ? AND pool_id = ? AND question_id = ?",
                     (conn.user_id, pool_id, question_id))
    else:
        conn.execute(
            "INSERT INTO user_note (user_id, pool_id, question_id, body, updated) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT (user_id, pool_id, question_id) "
            "DO UPDATE SET body = excluded.body, updated = excluded.updated",
            (conn.user_id, pool_id, question_id, body[:4000],
             utcnow().isoformat()))
    conn.commit()
    return body or None


def cw_progress(conn):
    return {r["ch"]: dict(r) for r in conn.execute(
        "SELECT * FROM cw_char WHERE user_id = ?", (conn.user_id,))}


def cw_record(conn, per_char):
    """Fold one copy session into the per-character record.

    ``per_char`` maps a sent character to {"sent": n, "copied": n,
    "confused": {typed: n}} - what was actually heard as what, which is the
    thing that tells you which pairs still need separating.
    """
    import json as _json
    for ch, stats in per_char.items():
        row = conn.execute("SELECT * FROM cw_char WHERE user_id = ? AND ch = ?",
                           (conn.user_id, ch)).fetchone()
        confused = _json.loads(row["confused"]) if row else {}
        for typed, n in (stats.get("confused") or {}).items():
            confused[typed] = confused.get(typed, 0) + int(n)
        conn.execute(
            "INSERT INTO cw_char (user_id, ch, sent, copied, confused, updated) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (user_id, ch) DO UPDATE SET "
            "sent = sent + excluded.sent, copied = copied + excluded.copied, "
            "confused = excluded.confused, updated = excluded.updated",
            (conn.user_id, ch, int(stats.get("sent", 0)),
             int(stats.get("copied", 0)), _json.dumps(confused),
             utcnow().isoformat()))
    conn.commit()


def maintenance_window(conn, pool_id, days=30):
    """Distinct questions answered and accuracy over a recent window.

    Distinct rather than total, so repeating one easy card forty times does not
    count as keeping a whole pool current.
    """
    from datetime import date as _date, timedelta as _td
    since = (_date.today() - _td(days=days)).isoformat()
    row = conn.execute(
        "SELECT COUNT(DISTINCT question_id) AS distinct_q, COUNT(*) AS attempts, "
        "COALESCE(SUM(correct), 0) AS n_right FROM answer_log "
        "WHERE user_id = ? AND pool_id = ? AND day >= ?",
        (conn.user_id, pool_id, since),
    ).fetchone()
    attempts = row["attempts"] or 0
    return {
        "distinct": row["distinct_q"] or 0,
        "attempts": attempts,
        "accuracy": (row["n_right"] / attempts) if attempts else 0.0,
        "window_days": days,
    }


def unit_get(conn, key, default=None):
    """A setting belonging to the unit rather than to whoever is playing.

    How ELMER updates itself is a property of the machine in the shack, not of
    the person sitting at it - it should not change because somebody else
    picked their name from the top bar.
    """
    row = conn.execute("SELECT v FROM setting WHERE k = ?", (key,)).fetchone()
    return json.loads(row["v"]) if row else default


def unit_set(conn, key, value):
    conn.execute(
        "INSERT INTO setting (k, v) VALUES (?, ?) "
        "ON CONFLICT (k) DO UPDATE SET v = excluded.v",
        (key, json.dumps(value)),
    )
    conn.commit()


def kv_get(conn, key, default=None):
    row = conn.execute("SELECT v FROM kv WHERE user_id = ? AND k = ?",
                       (conn.user_id, key)).fetchone()
    return json.loads(row["v"]) if row else default


def kv_set(conn, key, value):
    conn.execute(
        "INSERT INTO kv (user_id, k, v) VALUES (?, ?, ?) "
        "ON CONFLICT (user_id, k) DO UPDATE SET v = excluded.v",
        (conn.user_id, key, json.dumps(value)),
    )
    conn.commit()
