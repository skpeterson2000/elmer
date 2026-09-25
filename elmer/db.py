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
from . import paths

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = paths.STATE / "elmer.db"

SCHEMA_VERSION = 10

# How many recognitions to keep the clock for, and how many of the earliest
# make the baseline. Thirty is a session's worth; five is enough to average
# out the one where somebody was reaching for their tea.
TIMES_KEEP = 30
BASELINE_SAMPLES = 5

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
    settings        TEXT    NOT NULL DEFAULT '{}',
    pw_salt         TEXT    NOT NULL DEFAULT '',
    pw_hash         TEXT    NOT NULL DEFAULT '',
    seal_salt       TEXT    NOT NULL DEFAULT '',
    seal_wrap       TEXT    NOT NULL DEFAULT '',
    seal_recovery_salt TEXT NOT NULL DEFAULT '',
    seal_recovery   TEXT    NOT NULL DEFAULT ''
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

-- Every answer the hall saw, when this unit ran a net. The answer_log above
-- is one person studying on this unit. This is a room full of people at
-- tables, each answer with its question, whether it was right and how long
-- it took - which is the difficulty measure's raw material, twenty tables'
-- worth in an evening. Practice players are never written here: a bot's
-- answer says nothing about how hard a question is for a person.
--
-- Nobody is named in it. `who` is a keyed hash of the person, with a key
-- the net made up when it opened and never wrote down, so the rows from one
-- evening can be told apart by person - which is all the measure needs, it
-- normalises each person against their own sitting - and nothing can be
-- turned back into a callsign afterwards, not by this program and not by
-- whoever ends up with the file. `license` is the class they said they
-- hold, or '' when they did not say: the one demographic worth keeping,
-- because how a General does on Technician questions ten years on is how
-- fast the knowledge wears. (No semicolons in this comment - the schema is
-- split on them.)
CREATE TABLE IF NOT EXISTS hall_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    day         TEXT NOT NULL,
    pool_id     TEXT NOT NULL,
    question_id TEXT NOT NULL,
    section     TEXT NOT NULL DEFAULT '',
    unit        TEXT NOT NULL,
    who         TEXT NOT NULL,
    license     TEXT NOT NULL DEFAULT '',
    correct     INTEGER NOT NULL,
    ms          REAL,
    mode        TEXT NOT NULL DEFAULT 'hall'
);
CREATE INDEX IF NOT EXISTS hall_pool ON hall_log (pool_id, ts);

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
    repeats  INTEGER NOT NULL DEFAULT 0,
    recent   TEXT    NOT NULL DEFAULT '',
    times    TEXT    NOT NULL DEFAULT '',
    first_ms REAL,
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
    # The signed-in person's data key, handed over by the request that knows
    # them, or None: whatever is sealed stays sealed for this connection.
    data_key = None


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
    import logging
    log = logging.getLogger("elmer")
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

    log.info("migrating the database from version %s to %s - "
             "existing progress becomes the first user",
             version, SCHEMA_VERSION)

    if version == 2:
        # Version 3 is optional account passwords. Two columns, both empty,
        # so every existing account carries on exactly as it was - open, until
        # somebody chooses otherwise.
        for column in ("pw_salt", "pw_hash"):
            if column not in _columns(conn, "profile"):
                conn.execute(f"ALTER TABLE profile ADD COLUMN {column} "
                             f"TEXT NOT NULL DEFAULT ''")
        version = 3
        log.info("database upgraded to version 3 - accounts may now carry "
                 "a password")

    if version == 3:
        # Version 4 adds the hall's log. A new table, nothing rebuilt: the
        # statements are CREATE IF NOT EXISTS and add what is missing.
        for statement in _statements():
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        log.info("database upgraded to version 5 - the hall keeps a log, "
                 "with nobody's name in it")
        version = 4

    if version == 4:
        # Version 5: the hall's log says which game a round was - a hall's,
        # or a table's own tournament, shootout, CutThroat or round of golf
        # - so the field report can say which parts of the program are in
        # use and the difficulty measure can read every game alike.
        if "mode" not in _columns(conn, "hall_log"):
            conn.execute("ALTER TABLE hall_log ADD COLUMN mode TEXT NOT NULL DEFAULT 'hall'")
        conn.commit()
        log.info("database upgraded to version 5 - the log says which game")
        version = 5

    if version == 5:
        # Version 6 is the seal: an account with a password may have its
        # private data sealed under a key the password wraps. Four columns,
        # all empty, so every account carries on exactly as it was - open,
        # and plain - until its owner sets a password.
        for column in ("seal_salt", "seal_wrap", "seal_recovery_salt", "seal_recovery"):
            if column not in _columns(conn, "profile"):
                conn.execute(f"ALTER TABLE profile ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        conn.commit()
        log.info("database upgraded to version 6 - private data may be sealed with a password")
        version = 6

    if version == 6:
        # Version 7: the CW record counts the resends - how many times a
        # character had to be sent again before it was copied, which is
        # the measure a contact would give you: "please repeat".
        if "repeats" not in _columns(conn, "cw_char"):
            conn.execute("ALTER TABLE cw_char ADD COLUMN repeats INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        log.info("database upgraded to version 7 - the CW record counts resends")
        version = 7

    if version == 7:
        # Version 8 undoes a silent write.
        #
        # The band plan's licence-class picker used to save the class being
        # *read* into the profile, and the profile's class is the one thing
        # the pool gate reads. So anybody who ever looked at Amateur Extra
        # on that page had every study pool opened to them, on the dashboard
        # and at the table, and was never told. The picker was fixed; the
        # values it left behind were not.
        #
        # A value it left cannot be told from one somebody typed on purpose,
        # except by what is missing: no mark saying whose word it is - see
        # callsign.SOURCE, written by every save from here on - and no FCC
        # record behind it. Those are cleared, so the station is asked once
        # rather than quietly believed. Nothing else is touched: a class the
        # FCC record answers for stays, and so does one marked as the
        # operator's own, which is how a licence from outside the US or an
        # upgrade the published file has not caught up with survives this.
        cleared = 0
        for row in conn.execute("SELECT id, settings FROM profile").fetchall():
            try:
                settings = json.loads(row["settings"] or "{}")
            except ValueError:
                continue
            if not isinstance(settings, dict) or not settings.get("license_class"):
                continue
            if settings.get("license_class_source"):
                continue                     # somebody's own word, deliberately
            if (settings.get("license") or {}).get("found"):
                continue                     # the FCC answers for this one
            # Say what was taken. Clearing a class on an upgrade and saying
            # nothing is how a licensed operator opens ELMER the next morning
            # and finds it treating them as though they hold nothing - no
            # HF on Make Contact, the pools shut - with no way to know why.
            # The program is not entitled to delete somebody's statement
            # about themselves in silence; it leaves this behind and the
            # Station panel says so until the class is set again.
            settings["license_class_cleared"] = str(settings["license_class"])
            settings.pop("license_class", None)
            conn.execute("UPDATE profile SET settings = ? WHERE id = ?",
                         (json.dumps(settings), row["id"]))
            cleared += 1
        conn.execute("PRAGMA user_version = 8")
        conn.commit()
        log.info("database upgraded to version 8 - %d unverified licence class(es) "
                 "cleared, which the band plan used to set without asking", cleared)
        version = 8

    if version == 8:
        # Version 9: the CW record remembers its recent sends, not only the
        # totals. "Solid" was nine in ten over everything ever sent, so a
        # rough first twenty on a character dragged its ratio for a long
        # time after the sound was known, and the next character waited on
        # arithmetic rather than on the person. A window of the last thirty
        # is what a Koch trainer actually judges. The totals stay; they are
        # the record, and this is the recent past.
        if "recent" not in _columns(conn, "cw_char"):
            conn.execute("ALTER TABLE cw_char ADD COLUMN recent TEXT NOT NULL DEFAULT ''")
        conn.commit()
        log.info("database upgraded to version 9 - the CW record keeps its recent sends")
        version = 9
    if version == 9:
        # Version 10: how long it took, not only whether it was right.
        #
        # The thing a learner cannot see from inside is that they are
        # getting faster. The record knew the percentage and threw the
        # clock away, so the one measure that says "it is working" -
        # three seconds of thinking in the first week, under one in the
        # fourth - was gone the moment the session ended.
        #
        # `times` is the recent reaction times in milliseconds, and
        # `first_ms` is what it took at the start, kept once and never
        # written again: it is the before in before-and-after.
        for column, spec in (("times", "TEXT NOT NULL DEFAULT ''"),
                             ("first_ms", "REAL")):
            if column not in _columns(conn, "cw_char"):
                conn.execute(f"ALTER TABLE cw_char ADD COLUMN {column} {spec}")
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
        log.info("database upgraded to version %s - the CW record keeps how long it took",
                 SCHEMA_VERSION)
        return SCHEMA_VERSION

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
    is theirs and needs no license.
    """
    if not profile:
        return "Operator"
    return (profile.get("callsign") or "").strip().upper() \
        or (profile.get("name") or "").strip() or "Operator"


# ELMER is a program about American radio licenses written, for a while, in
# British English. "License" is the American spelling for both the noun and the
# verb, and this is a program about FCC and NCVEC licenses, so that is the
# spelling. The settings key was renamed with it - but a key is not prose, and
# every install that has already saved one has it under the old name.
# The old names are spelled out of one piece so that a search-and-replace over
# the spelling cannot quietly turn this map into a no-op - which is exactly
# what happened the first time, and it silently cost a saved Extra ticket.
_OLD = "lic" + "ence"
LEGACY_SETTINGS = {_OLD + "_class": "license_class", _OLD: "license"}


def _modernise(settings):
    """Read a settings blob saved under the older key names.

    Nobody should lose the license class they typed in because the project
    learned to spell. The old name is read where the new one is absent, and
    left in place: rewriting somebody's saved settings on read is a change to
    their data made for the program's convenience, not theirs.
    """
    for was, now in LEGACY_SETTINGS.items():
        if was in settings and now not in settings:
            settings[now] = settings[was]
    return settings


def standing(callsign, settings):
    """Where the licence behind an account stands, from the FCC record kept
    with it and today's date - never from the callsign field alone.

    The account menu used to pin a "licensed" pill on anybody with anything
    typed in the callsign box: type XYZZY and you were licensed. It was
    reported from a real one - KA7EVD, once Donny Osmond's, lapsed decades
    ago and gone from the FCC's file - which came up "licensed" for the
    same reason. What the record says is what is shown:

      None        no callsign on the account
      unchecked   a callsign, and no record looked up yet
      unfound     looked up, and the FCC has no record of it - lapsed long
                  enough to have been dropped from the file, or foreign,
                  or a slip; the file cannot tell these apart
      cancelled   the FCC still lists it, as cancelled or terminated
      current     in force
      grace       expired, in the two-year window to renew without retesting;
                  may not be used on the air
      expired     past that, gone

    Computed now, not when the record was fetched: a record's own status
    was worked out on the day of the lookup and frozen, so a licence that
    was current then would read current years after it ran out.
    """
    if not (callsign or "").strip():
        return None
    record = (settings or {}).get("license")
    if not isinstance(record, dict):
        return "unchecked"
    if not record.get("found"):
        if record.get("fcc_status") in ("cancelled", "terminated"):
            return "cancelled"
        return "unfound"
    from . import callsign as _callsign
    state = _callsign.status_for(_callsign._parse_date(record.get("expires"))).get("state")
    return state if state in ("current", "grace", "expired") else "current"


def _row_to_profile(row):
    prof = dict(row)
    prof["settings"] = _modernise(json.loads(prof["settings"] or "{}"))
    prof["display_name"] = display_name(prof)
    prof["standing"] = standing(prof.get("callsign"), prof["settings"])
    # "Licensed" is a claim the FCC has to back. In force, today.
    prof["licensed"] = prof["standing"] == "current"
    # The salt and the hash never leave here. This dict is what /api/users
    # answers with, and a stored hash served to the network is a stored hash
    # somebody can work on at their leisure. What a caller legitimately needs
    # to know is only whether the account is locked.
    prof["locked"] = bool(prof.pop("pw_hash", ""))
    prof.pop("pw_salt", None)
    # The seal's columns are wrapped keys and never useful to a page; what a
    # page needs is whether the seal is on, and whether a recovery code can
    # still open it after a moderator reset took the password wrap away.
    prof["sealed"] = bool(prof.pop("seal_wrap", "")) or bool(prof.get("seal_recovery"))
    prof["recoverable"] = bool(prof.pop("seal_recovery", ""))
    prof.pop("seal_salt", None)
    prof.pop("seal_recovery_salt", None)
    sealed = (prof["settings"].get("sealed") or {}) if isinstance(prof["settings"].get("sealed"), dict) else {}
    prof["settings"].pop("sealed", None)
    if sealed:
        prof["settings"]["sealed_fields"] = sorted(sealed)
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
    prof = _row_to_profile(row)
    # With the key in hand the sealed fields come back as plain settings,
    # exactly as they were saved; without it they are named and nothing more.
    if conn.data_key and prof["sealed"]:
        from . import seal
        stored = json.loads(row["settings"] or "{}")
        blobs = (stored.get("sealed") or {})
        freed = {}
        for key, blob in blobs.items():
            try:
                value = json.loads(seal.unseal_text(conn.data_key, blob))
            except (seal.Broken, ValueError):
                pass                       # the wrong key: stays sealed, and named
            else:
                prof["settings"][key] = value
                if key in RETIRED_SEALED_KEYS:
                    freed[key] = value
                prof["settings"].get("sealed_fields", []).remove(key) if key in prof["settings"].get("sealed_fields", []) else None
        if not prof["settings"].get("sealed_fields"):
            prof["settings"].pop("sealed_fields", None)
        # The key is in hand, which is the only time this can be done at all.
        if freed:
            _free_retired(conn, stored, freed)
    return prof


def _free_retired(conn, stored, freed):
    """Write a no-longer-sealed field back in the clear, once.

    Called from the read path, which is not where writes belong, but the
    data key exists only while its owner is signed in and this is the one
    moment it is certain to be here. It happens once per account: the blob
    goes, the plain value stays, and every later start can read it.
    """
    blobs = dict(stored.get("sealed") or {})
    for key, value in freed.items():
        blobs.pop(key, None)
        stored[key] = value
    if blobs:
        stored["sealed"] = blobs
    else:
        stored.pop("sealed", None)
    stored.pop("sealed_fields", None)
    conn.execute("UPDATE profile SET settings = ? WHERE id = ?",
                 (json.dumps(stored), conn.user_id))
    conn.commit()


# The settings a password seals: secrets, and nothing else. The name, the
# callsign and the licence stay plain - the room's boards show them and the
# callsign is a public record.
#
# The QTH used to be on this list and it should not have been. A grid square
# is not a credential: it is the one input almost every answer in ELMER is
# built on. The data key lives in this process and dies with it, so sealing
# the QTH meant that every restart left the station with no idea where it
# was until somebody typed a password - and it said so by answering "located:
# false" with a cheerful 200, which is not an error anybody can act on. What
# that cost: no path to anywhere, no sky above the station, HF missing from
# Make Contact entirely, "Locate me" refused outright. A secret earns a seal
# by being a secret. Where the antenna is standing is on every QSL card that
# ever left the shack.
SEALED_KEYS = ("repeaterbook_token",)

# What used to be sealed and is not any more. A blob under one of these is
# opened and written back in the clear the next time its owner signs in -
# there is no other moment, because there is no other moment the key exists.
RETIRED_SEALED_KEYS = ("location",)


class Locked(ValueError):
    """The account's private data is sealed and this connection has no key."""


def _sealed_row(conn, user_id=None):
    return conn.execute("SELECT seal_wrap, seal_recovery, settings FROM profile WHERE id = ?",
                        (user_id or conn.user_id,)).fetchone()


def save_settings(conn, settings):
    """Write the settings, sealing what the account seals.

    On a sealed account the private fields go into the blob under the
    data key when the connection has it. Without the key the stored blobs
    are kept exactly as they are and a plain private field is refused,
    since it could be neither sealed nor honestly left in the clear.
    """
    settings = dict(settings)
    settings.pop("sealed_fields", None)
    row = _sealed_row(conn)
    if row and (row["seal_wrap"] or row["seal_recovery"]):
        stored = (json.loads(row["settings"] or "{}").get("sealed") or {})
        if conn.data_key:
            from . import seal
            blobs = {}
            for key in SEALED_KEYS:
                value = settings.pop(key, None)
                if value not in (None, "", {}, []):
                    blobs[key] = seal.seal_text(conn.data_key, json.dumps(value))
            # a field the key could not open earlier is carried, not dropped -
            # unless it is one the seal has let go of and it is already here in
            # the clear, in which case carrying it would put it back under lock
            for key, blob in stored.items():
                if key in blobs or key in SEALED_KEYS:
                    continue
                if key in RETIRED_SEALED_KEYS and settings.get(key) not in (None, "", {}, []):
                    continue
                blobs[key] = blob
        else:
            if any(settings.get(k) not in (None, "", {}, []) for k in SEALED_KEYS):
                raise Locked("this account's private data is sealed - sign in to change it")
            for key in SEALED_KEYS:
                settings.pop(key, None)
            blobs = dict(stored)
        if blobs:
            settings["sealed"] = blobs
        else:
            settings.pop("sealed", None)
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


# What a person can say they hold. Novice and Advanced are no longer issued
# but are still held, and somebody who has one is exactly the person whose
# answers say how knowledge wears. "none" is somebody with no license yet -
# they play, and their answers are the other end of the same measurement.
LICENSE_CLASSES = ("none", "Novice", "Technician", "General", "Advanced",
                   "Extra")


def license_of(value):
    """A stated license class, normalised, or '' for not said."""
    v = str(value or "").strip()
    if not v:
        return ""
    low = v.lower()
    if low in ("none", "no", "no license", "no license", "unlicensed"):
        return "none"
    for name in LICENSE_CLASSES:
        if name.lower() == low or (low == "tech" and name == "Technician"):
            return name
    return ""


def hall_who(key, unit, name):
    """The opaque person for a hall row: same person, same evening, same tag.

    A callsign is the person wherever they sit, so KC9SP at two tables is one
    tag; anybody else is the table and the name together. The tag is an HMAC
    under a key the net made when it opened and holds only in memory - so it
    can be made again tonight for the same person, and by nobody tomorrow.
    """
    import hashlib
    import hmac
    from .party import callsign_of
    call = callsign_of(name)
    ident = call if call else f"{unit}/{str(name or '').strip().lower()}"
    return hmac.new(key, ident.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def log_hall_round(conn, pool_id, question_id, section, rows, key, mode="hall"):
    """Write a round's answers down: one row per person, no bots.

    `key` is the net's own - or the table's, for a table's own game - see
    hall_who(). No name and no callsign goes into the table: the class they
    said they hold, whether they were right, how long they took, and which
    game it was.
    """
    now, day = utcnow().isoformat(), today()
    for r in rows:
        if r.get("bot"):
            continue
        conn.execute(
            "INSERT INTO hall_log (ts, day, pool_id, question_id, section, unit, "
            "who, license, correct, ms, mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now, day, pool_id, question_id, section or "", str(r.get("unit")),
             hall_who(key, r.get("unit"), r.get("name")),
             license_of(r.get("license")), int(bool(r.get("correct"))),
             float(r["ms"]) if r.get("ms") else None, str(mode or "hall")[:20]))


def seen_questions(conn, pool_id):
    """Every question of a pool anybody on this unit has met - in study, in
    a hall, or at this table - so a draw can put the new ones first."""
    seen = {r[0] for r in conn.execute(
        "SELECT DISTINCT question_id FROM answer_log WHERE pool_id = ?", (pool_id,))}
    try:
        seen |= {r[0] for r in conn.execute(
            "SELECT DISTINCT question_id FROM hall_log WHERE pool_id = ?", (pool_id,))}
    except Exception:                        # a database from before the hall log
        pass
    return seen


def rounds_by_mode(conn, since_ts_iso):
    """How much of each game there was: rounds, answers and right answers,
    by mode, since a moment - for the field report's week in counts."""
    out = {}
    try:
        for r in conn.execute(
                "SELECT mode, COUNT(DISTINCT ts || '/' || question_id) c, COUNT(*) a, "
                "SUM(CASE WHEN correct THEN 1 ELSE 0 END) r "
                "FROM hall_log WHERE ts >= ? GROUP BY mode", (since_ts_iso,)):
            out[r["mode"] or "hall"] = {"rounds": r["c"] or 0, "answers": r["a"] or 0,
                                        "right": r["r"] or 0}
    except Exception:
        pass
    return out


def log_answer(conn, pool_id, question_id, section, correct, chosen, ms, mode):
    conn.execute(
        "INSERT INTO answer_log (user_id, ts, day, pool_id, question_id, "
        "section, correct, chosen, ms, mode) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (conn.user_id, utcnow().isoformat(), today(), pool_id, question_id,
         section, int(correct), chosen, ms, mode),
    )


def _note_out(conn, body):
    """A stored note as its owner reads it: unsealed with the key, or None
    while it is sealed and the key is not here."""
    from . import seal
    if not seal.is_sealed(body):
        return body
    if not conn.data_key:
        return None
    try:
        return seal.unseal_text(conn.data_key, body)
    except seal.Broken:
        return None


def get_note(conn, pool_id, question_id):
    row = conn.execute(
        "SELECT body FROM user_note "
        "WHERE user_id = ? AND pool_id = ? AND question_id = ?",
        (conn.user_id, pool_id, question_id),
    ).fetchone()
    return _note_out(conn, row["body"]) if row else None


def notes_for_pool(conn, pool_id):
    out = {}
    for r in conn.execute(
            "SELECT question_id, body FROM user_note WHERE user_id = ? AND pool_id = ?",
            (conn.user_id, pool_id)):
        body = _note_out(conn, r["body"])
        if body is not None:
            out[r["question_id"]] = body
    return out


def is_sealed_account(conn, user_id=None):
    row = _sealed_row(conn, user_id)
    return bool(row and (row["seal_wrap"] or row["seal_recovery"]))


def save_note(conn, pool_id, question_id, body):
    """Empty body deletes the note, so clearing the box removes it. On a
    sealed account the note is stored sealed, and refused without the key."""
    body = (body or "").strip()
    stored = body[:4000]
    if body and is_sealed_account(conn):
        if not conn.data_key:
            raise Locked("this account's notes are sealed - sign in to write one")
        from . import seal
        stored = seal.seal_text(conn.data_key, stored)
    if not body:
        conn.execute("DELETE FROM user_note "
                     "WHERE user_id = ? AND pool_id = ? AND question_id = ?",
                     (conn.user_id, pool_id, question_id))
    else:
        conn.execute(
            "INSERT INTO user_note (user_id, pool_id, question_id, body, updated) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT (user_id, pool_id, question_id) "
            "DO UPDATE SET body = excluded.body, updated = excluded.updated",
            (conn.user_id, pool_id, question_id, stored,
             utcnow().isoformat()))
    conn.commit()
    return body or None


def cw_progress(conn):
    return {r["ch"]: dict(r) for r in conn.execute(
        "SELECT * FROM cw_char WHERE user_id = ?", (conn.user_id,))}


# How much of the recent past the record keeps per character: enough for
# the window "solid" is judged over (cw.RECENT_WINDOW) with room to spare.
RECENT_KEEP = 40


def cw_record(conn, per_char):
    """Fold one copy session into the per-character record.

    ``per_char`` maps a sent character to {"sent": n, "copied": n,
    "confused": {typed: n}, "repeats": n} - what was actually heard as
    what, which is the thing that tells you which pairs still need
    separating, and how many times it had to be sent again first, which
    is what a contact would measure: "please repeat".

    ``outcomes``, if given, is the same session in order - a string of 1
    for copied and 0 for missed, one per send - and it is what the recent
    window is built from. A session that sends only totals still feeds the
    window, as its copies followed by its misses, which is the right shape
    when the order is not known and exactly right when there is one send.
    """
    import json as _json
    for ch, stats in per_char.items():
        row = conn.execute("SELECT * FROM cw_char WHERE user_id = ? AND ch = ?",
                           (conn.user_id, ch)).fetchone()
        confused = _json.loads(row["confused"]) if row else {}
        for typed, n in (stats.get("confused") or {}).items():
            confused[typed] = confused.get(typed, 0) + int(n)
        sent, copied = int(stats.get("sent", 0)), int(stats.get("copied", 0))
        outcomes = str(stats.get("outcomes") or "")
        if not outcomes or set(outcomes) - {"0", "1"} or len(outcomes) != sent:
            outcomes = "1" * copied + "0" * max(0, sent - copied)
        recent = ((row["recent"] if row and "recent" in row.keys() else "") or "") + outcomes
        recent = recent[-RECENT_KEEP:]
        # How long it took, for the answers that were right. A miss has a
        # time too and it means nothing - it is how long somebody waited
        # before guessing - so only the recognitions are kept.
        had = ((row["times"] if row and "times" in row.keys() else "") or "")
        fresh = [str(int(round(float(ms)))) for ms in (stats.get("ms") or [])
                 if 0 < float(ms) < 20000]
        times = [x for x in (had.split(",") + fresh) if x][-TIMES_KEEP:]
        # The before, written once. It is the mean of the first few
        # recognitions and then it is never touched again: a baseline that
        # moved with the record would have nothing to say.
        first_ms = row["first_ms"] if row and "first_ms" in row.keys() else None
        if first_ms is None and len(times) >= BASELINE_SAMPLES:
            early = [float(x) for x in times[:BASELINE_SAMPLES]]
            first_ms = round(sum(early) / len(early), 1)
        conn.execute(
            "INSERT INTO cw_char (user_id, ch, sent, copied, confused, repeats, recent, "
            "times, first_ms, updated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (user_id, ch) DO UPDATE SET "
            "sent = sent + excluded.sent, copied = copied + excluded.copied, "
            "confused = excluded.confused, repeats = repeats + excluded.repeats, "
            "recent = excluded.recent, times = excluded.times, "
            "first_ms = COALESCE(cw_char.first_ms, excluded.first_ms), "
            "updated = excluded.updated",
            (conn.user_id, ch, sent, copied, _json.dumps(confused),
             int(stats.get("repeats", 0) or 0), recent, ",".join(times), first_ms,
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


# --- account passwords ------------------------------------------------------
# What this is and is not. It stops a clubmate deleting somebody's progress or
# answering questions as them by picking their name off a list - which on a
# shared unit is the whole of the problem. It is not protection against
# somebody on the network who means harm: ELMER speaks plain HTTP, so a
# password crosses the wire in clear, and anybody with the Pi in their hands
# owns the database anyway. Saying so is better than implying otherwise.
#
# scrypt with a per-account salt, at the standard 16 MiB cost - about 45 ms on
# a Pi 5, which is slow enough to make guessing tedious and fast enough that
# nobody notices signing in.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1


def _hash_password(password, salt):
    import hashlib
    return hashlib.scrypt(password.encode("utf-8"), salt=salt,
                          n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                          dklen=32).hex()


def set_password(conn, user_id, password):
    """Give an account a password, or take it away with an empty one."""
    import os
    if not password:
        conn.execute("UPDATE profile SET pw_salt = '', pw_hash = '' "
                     "WHERE id = ?", (user_id,))
        conn.commit()
        return False
    salt = os.urandom(16)
    conn.execute("UPDATE profile SET pw_salt = ?, pw_hash = ? WHERE id = ?",
                 (salt.hex(), _hash_password(password, salt), user_id))
    conn.commit()
    return True


def has_password(conn, user_id):
    row = conn.execute("SELECT pw_hash FROM profile WHERE id = ?",
                       (user_id,)).fetchone()
    return bool(row and row["pw_hash"])


# ------------------------------------------------------------------ the seal
# An account with a password may have its private data sealed under a data
# key the password wraps - see seal.py for the shape and the reasoning. The
# functions here move an account between plain and sealed, hand the key to
# a request that has proved the password, and re-wrap it when the password
# changes. Nothing here keeps a key: it is returned to the caller, who holds
# it in memory for the session and no longer.

def data_key_for(conn, user_id, password):
    """The account's data key, for the right password; None otherwise, and
    None for an account that is not sealed."""
    from . import seal
    row = conn.execute("SELECT seal_salt, seal_wrap FROM profile WHERE id = ?",
                       (user_id,)).fetchone()
    if not row or not row["seal_wrap"] or not password:
        return None
    try:
        return seal.unwrap(password, bytes.fromhex(row["seal_salt"]), bytes.fromhex(row["seal_wrap"]))
    except (seal.Broken, ValueError):
        return None


def recover_key(conn, user_id, code):
    """The data key, for the right recovery code; None otherwise."""
    from . import seal
    row = conn.execute("SELECT seal_recovery_salt, seal_recovery FROM profile WHERE id = ?",
                       (user_id,)).fetchone()
    if not row or not row["seal_recovery"]:
        return None
    try:
        return seal.unwrap(seal.normalise_code(code), bytes.fromhex(row["seal_recovery_salt"]),
                           bytes.fromhex(row["seal_recovery"]))
    except (seal.Broken, ValueError):
        return None


def _write_wraps(conn, user_id, key, password=None, code=None):
    from . import seal
    sets, vals = [], []
    if password is not None:
        salt, wrapped = seal.wrap(key, password)
        sets += ["seal_salt = ?", "seal_wrap = ?"]
        vals += [salt.hex(), wrapped.hex()]
    if code is not None:
        salt, wrapped = seal.wrap(key, seal.normalise_code(code))
        sets += ["seal_recovery_salt = ?", "seal_recovery = ?"]
        vals += [salt.hex(), wrapped.hex()]
    if sets:
        conn.execute(f"UPDATE profile SET {', '.join(sets)} WHERE id = ?", vals + [user_id])


def seal_account(conn, user_id, password):
    """Seal an account that has just taken a password: a new data key,
    wrapped under the password and under a recovery code; every private
    field and every note sealed under it. Returns (key, recovery code)."""
    from . import seal
    key = seal.new_key()
    code = seal.recovery_code()
    _write_wraps(conn, user_id, key, password=password, code=code)
    # the settings, private fields into the blob
    row = conn.execute("SELECT settings FROM profile WHERE id = ?", (user_id,)).fetchone()
    settings = json.loads(row["settings"] or "{}")
    blobs = {}
    for k in SEALED_KEYS:
        value = settings.pop(k, None)
        if value not in (None, "", {}, []):
            blobs[k] = seal.seal_text(key, json.dumps(value))
    if blobs:
        settings["sealed"] = blobs
    conn.execute("UPDATE profile SET settings = ? WHERE id = ?", (json.dumps(settings), user_id))
    # the notes, each under the key
    for r in conn.execute("SELECT pool_id, question_id, body FROM user_note WHERE user_id = ?",
                          (user_id,)).fetchall():
        if not seal.is_sealed(r["body"]):
            conn.execute("UPDATE user_note SET body = ? WHERE user_id = ? AND pool_id = ? AND question_id = ?",
                         (seal.seal_text(key, r["body"]), user_id, r["pool_id"], r["question_id"]))
    conn.commit()
    return key, code


def unseal_account(conn, user_id, key):
    """Everything back to plain: the password is being taken off."""
    from . import seal
    row = conn.execute("SELECT settings FROM profile WHERE id = ?", (user_id,)).fetchone()
    settings = json.loads(row["settings"] or "{}")
    blobs = settings.pop("sealed", None) or {}
    for k, blob in blobs.items():
        try:
            settings[k] = json.loads(seal.unseal_text(key, blob))
        except (seal.Broken, ValueError):
            pass
    conn.execute("UPDATE profile SET settings = ?, seal_salt = '', seal_wrap = '', "
                 "seal_recovery_salt = '', seal_recovery = '' WHERE id = ?",
                 (json.dumps(settings), user_id))
    for r in conn.execute("SELECT pool_id, question_id, body FROM user_note WHERE user_id = ?",
                          (user_id,)).fetchall():
        if seal.is_sealed(r["body"]):
            try:
                plain = seal.unseal_text(key, r["body"])
            except seal.Broken:
                continue
            conn.execute("UPDATE user_note SET body = ? WHERE user_id = ? AND pool_id = ? AND question_id = ?",
                         (plain, user_id, r["pool_id"], r["question_id"]))
    conn.commit()


def drop_seal(conn, user_id):
    """A moderator reset with no key: the password wrap goes, the recovery
    wrap and the sealed data stay, for the day the code turns up."""
    conn.execute("UPDATE profile SET seal_salt = '', seal_wrap = '' WHERE id = ?", (user_id,))
    conn.commit()


def change_password(conn, user_id, new, current="", data_key=None):
    """Set, change or clear an account's password, carrying the seal with it.

    Returns {"locked", "sealed", "key", "recovery", "lost"}: the key for the
    session that made the change, the recovery code when a seal was just
    made (shown once), and "lost" when a moderator reset had to leave the
    sealed data behind the recovery code alone.
    """
    out = {"locked": bool(new), "sealed": False, "key": None, "recovery": None, "lost": False}
    key = data_key or data_key_for(conn, user_id, current)
    was_sealed = is_sealed_account(conn, user_id)
    if not new:
        if was_sealed:
            if key:
                unseal_account(conn, user_id, key)
            else:
                # the moderator opened it: the data stays behind the code
                drop_seal(conn, user_id)
                out["lost"] = True
                out["sealed"] = True
        set_password(conn, user_id, "")
        return out
    set_password(conn, user_id, new)
    if was_sealed and key:
        _write_wraps(conn, user_id, key, password=new)
        conn.commit()
        out.update(sealed=True, key=key)
    elif was_sealed:
        drop_seal(conn, user_id)              # the recovery code is the way back
        out.update(sealed=True, lost=True)
    else:
        key, code = seal_account(conn, user_id, new)
        out.update(sealed=True, key=key, recovery=code)
    return out


def recover_account(conn, user_id, code, new_password):
    """The recovery code opens the seal and the account takes a new
    password, with the key wrapped under it again. Returns the key, or
    None for a code that does not open it."""
    key = recover_key(conn, user_id, code)
    if key is None:
        return None
    set_password(conn, user_id, new_password)
    _write_wraps(conn, user_id, key, password=new_password)
    conn.commit()
    return key


def check_password(conn, user_id, password):
    """Whether this password opens that account.

    An account with no password is open, which is the state every account
    starts in: somebody studying alone on their own Pi should not have to
    invent a password before they can answer a question.
    """
    import hmac
    row = conn.execute("SELECT pw_salt, pw_hash FROM profile WHERE id = ?",
                       (user_id,)).fetchone()
    if not row or not row["pw_hash"]:
        return True
    if not password:
        return False
    try:
        salt = bytes.fromhex(row["pw_salt"])
    except ValueError:
        return False
    # Constant time, so a wrong password cannot be narrowed down by how long
    # it took to be told so.
    return hmac.compare_digest(_hash_password(password, salt), row["pw_hash"])


# Offering a password when the unit stops being one person's.
#
# A password is optional and starts unset, which is right: somebody studying
# alone on their own Pi should not have to invent one before answering a
# question. But nothing used to change when a second person appeared, and that
# is exactly when it starts to matter - so the protection sat in a menu nobody
# opened until after they had been bitten.
#
# The offer is made from three facts and no others: how many accounts are on
# the unit, whether *this* account has a password, and whether this account has
# been asked before. It never consults another account's state, so the second
# person to arrive sees the same words whether the first has a password or not.
# Telling somebody that a clubmate is unprotected would be its own small
# betrayal, and would make the honest answer to "should I bother" a matter of
# who else had bothered.
OFFERED_KEY = "password_offered"

# Whether this unit is one person's or shared. Not asked until a second
# account is about to be made; answered once, and kept as the unit's own
# setting. On a shared unit the person at the controls is asked to lock
# their account *before* the second account exists - the one moment they
# are certainly the one holding the controls - and a secret saved on an
# account needs the account to have a password.
SHARED_KEY = "shared_unit"


def shared(conn):
    """True, False, or None for not yet asked."""
    return unit_get(conn, SHARED_KEY, None)


def set_shared(conn, flag):
    unit_set(conn, SHARED_KEY, None if flag is None else bool(flag))
    conn.commit()


def password_offered(conn, user_id):
    """Whether this account has been asked about a password, either answer."""
    row = conn.execute("SELECT v FROM kv WHERE user_id = ? AND k = ?",
                       (user_id, OFFERED_KEY)).fetchone()
    return bool(row and json.loads(row["v"]))


# Settings that are secrets: kept, used, and never sent back to a page. A
# page is told that one is saved, and nothing more.
SECRET_KEYS = ("repeaterbook_token",)


def public_profile(profile):
    """The profile as a page may see it: every secret replaced by whether
    it is there."""
    out = dict(profile)
    settings = dict(out.get("settings") or {})
    for key in SECRET_KEYS:
        settings["has_" + key] = bool(settings.pop(key, None))
    out["settings"] = settings
    return out


def should_offer_password(conn, user_id):
    """Whether to offer this account a password, once."""
    shared = conn.execute("SELECT COUNT(*) c FROM profile").fetchone()["c"] > 1
    if not shared or has_password(conn, user_id):
        return False
    row = conn.execute("SELECT v FROM kv WHERE user_id = ? AND k = ?",
                       (user_id, OFFERED_KEY)).fetchone()
    return not (row and json.loads(row["v"]))


def mark_password_offered(conn, user_id):
    """Remember that this account was asked, whichever way it answered."""
    conn.execute(
        "INSERT INTO kv (user_id, k, v) VALUES (?, ?, ?) "
        "ON CONFLICT (user_id, k) DO UPDATE SET v = excluded.v",
        (user_id, OFFERED_KEY, json.dumps(True)))
    conn.commit()


MODERATOR_KEY = "moderator_pw"


def set_moderator(conn, password):
    """The key the person whose Pi this is holds, for when somebody forgets.

    Without one, a forgotten password means the account can only be freed from
    the machine itself. With one, whoever runs the club night can clear it.
    """
    import os
    if not password:
        unit_set(conn, MODERATOR_KEY, "")
        return False
    salt = os.urandom(16)
    unit_set(conn, MODERATOR_KEY,
             {"salt": salt.hex(), "hash": _hash_password(password, salt)})
    return True


def has_moderator(conn):
    return bool(unit_get(conn, MODERATOR_KEY))


def check_moderator(conn, password):
    import hmac
    stored = unit_get(conn, MODERATOR_KEY)
    if not stored or not password:
        return False
    try:
        salt = bytes.fromhex(stored["salt"])
    except (ValueError, TypeError, KeyError):
        return False
    return hmac.compare_digest(_hash_password(password, salt), stored["hash"])


def may_alter(conn, user_id, password):
    """Whether this request may rename, remove or become that account.

    The account's own password opens it; the moderator key opens any of them,
    because somebody has to be able to sort out a forgotten password at a club
    night without a keyboard and a database editor.
    """
    if check_password(conn, user_id, password):
        return True
    return check_moderator(conn, password)


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
