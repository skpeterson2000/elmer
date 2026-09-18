"""A supporter's key, the thanks it earns, and the coffee card for everyone else.

ELMER is a gift to the amateur radio community and free for everyone. Some
people will want to thank the developer with a cup of coffee, and the
program should notice that: a person who has should be thanked, and a
person who has not should hear the offer once, lightly, and then be left
alone. Both are this module's business, and nothing here changes what
ELMER does - a key opens no feature and its absence closes none.

**The key.** A supporter sends their callsign in the sponsorship note and a
key comes back: ``ELMER-KC9SP-XXXXXX``, the callsign and six letters cut
from it. The letters are a keyed hash with the salt in this file, which
means the key is a check against typos and casual passing-around, not
cryptography - anybody who reads the source can cut one. That is a fair
trade for a gift: the only thing a forged key earns is being thanked for
a coffee that was never bought, and the key carries the callsign it was
cut for, so a key passed around thanks its original owner on somebody
else's screen. There is no register of keys to keep: the same callsign
always cuts the same key, so a lost one is cut again, and SUPPORTERS.md is
the roster of who chose to be named.

**The meter.** The coffee card waits until a person has actually used the
program - :func:`active_hours` is the time spent answering questions, each
answer capped so a walk-away does not clock an afternoon - and it is asked
once at ten hours, then not again for a hundred more. It is the person's
meter, not the machine's: on a shared unit each account has its own.

**The thanks.** With a key, the dashboard says thank you once a day, and
says what the coffee meant: how many times ELMER has changed since it was
bought, read off the changelog, with the latest three lines. In a hall the
unit's table carries the supporter to net control, which puts their name
on the card between rounds - see :mod:`elmer.show`.
"""
import hashlib
import re
import time
from datetime import date, datetime

from . import db, paths

# The salt is in the source on purpose - see the module docstring.
KEY_SALT = b"elmer-supporter-2026"
KEY_RE = re.compile(r"^ELMER-([A-Z0-9]{3,12})-([A-Z2-9]{6})$")
# No 0/O or 1/I, so a key read over the air or off a phone cannot be
# mistyped into a different key.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CALL_RE = re.compile(r"^[A-Z0-9]{3,12}$")

ASK_AFTER_HOURS = 10.0          # the first coffee card
ASK_AGAIN_HOURS = 100.0         # and the next, that many hours of use later
ANSWER_CAP_MS = 5 * 60 * 1000   # an answer that took longer was a walk-away

SETTING = "supporter"           # in the profile's settings: {key, callsign, named, since}
ASKED = "supporter.asked"       # kv: {"at", "hours"} when the coffee card was last shown
THANKED = "supporter.thanked"   # kv: the day the thanks card was last shown

GAME_WORD = {"tournament": "tournament", "shootout": "shootout",
             "cutthroat": "round of CutThroat", "golf": "round of golf"}

SPONSORS_URL = "https://github.com/sponsors/skpeterson2000"


# ------------------------------------------------------------------ the key

def normalise(callsign):
    """A callsign as the key carries it: upper case, the base call only -
    KC9SP/M and VE3/KC9SP are both KC9SP's key, so the same person's key
    is the same wherever they signed from."""
    parts = [re.sub(r"[^A-Z0-9]", "", p) for p in str(callsign or "").upper().split("/")]
    return max(parts, key=len) if parts else ""


def _code(callsign):
    digest = hashlib.sha256(KEY_SALT + callsign.encode("ascii")).digest()
    return "".join(ALPHABET[b % len(ALPHABET)] for b in digest[:6])


def make_key(callsign):
    """The key for a callsign, or None when there is no callsign in it."""
    call = normalise(callsign)
    if not CALL_RE.match(call):
        return None
    return f"ELMER-{call}-{_code(call)}"


def check_key(key):
    """(callsign, None) for a key that is one; (None, reason) otherwise."""
    text = re.sub(r"\s+", "", str(key or "").upper())
    if not text:
        return None, "no key"
    m = KEY_RE.match(text)
    if not m:
        return None, "a key looks like ELMER-CALLSIGN-XXXXXX"
    call, code = m.group(1), m.group(2)
    if code != _code(call):
        return None, f"that is not the key for {call} - check it against the note it came in"
    return call, None


# ------------------------------------------------------------ the record

def record(conn):
    """This account's supporter record, or None. A record whose key no
    longer checks - the file edited by hand, say - is None too."""
    rec = (db.get_profile(conn)["settings"] or {}).get(SETTING)
    if not isinstance(rec, dict):
        return None
    call, why = check_key(rec.get("key"))
    if call is None:
        return None
    return {"key": rec["key"], "callsign": call, "named": bool(rec.get("named")),
            "since": str(rec.get("since") or "")}


def apply(settings, key=None, named=None, today=None):
    """Put a key, or the naming choice, into a settings dict. None for a
    field leaves it; an empty key clears the record. Returns a reason when
    the key is not one, else None. Pure - the caller saves."""
    if key is not None:
        text = str(key or "").strip()
        if not text:
            settings.pop(SETTING, None)
        else:
            call, why = check_key(text)
            if call is None:
                return why
            old = settings.get(SETTING) if isinstance(settings.get(SETTING), dict) else {}
            settings[SETTING] = {
                "key": f"ELMER-{call}-{_code(call)}", "callsign": call,
                "named": bool(old.get("named")),
                # The month the coffee was bought is the month the key went
                # in; the same key entered again keeps its first date.
                "since": (old.get("since") if old.get("callsign") == call and old.get("since")
                          else (today or date.today()).isoformat())}
    if named is not None and isinstance(settings.get(SETTING), dict):
        settings[SETTING]["named"] = bool(named)
    return None


def set_key(conn, key, named=None):
    """Enter a key, or clear it with an empty one. (record, None) or (None, reason)."""
    settings = db.get_profile(conn)["settings"]
    why = apply(settings, key, named)
    if why:
        return None, why
    db.save_settings(conn, settings)
    conn.commit()
    return record(conn), None


def words(names, most=6):
    """A list of names as a sentence reads them: the first few, and how many more."""
    names = [n for n in names if n]
    if not names:
        return ""
    shown = names[:most]
    rest = len(names) - len(shown)
    line = shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " and " + shown[-1]
    return line + (f" and {rest} more" if rest else "")


def named_callsign(conn):
    """The callsign to put on a hall's card for this unit, or '' - a
    supporter who would rather not be named is not, anywhere."""
    rec = record(conn)
    return rec["callsign"] if rec and rec["named"] else ""


# ------------------------------------------------------------- the meter

def active_hours(conn):
    """Hours this account has spent answering questions, each answer capped."""
    row = conn.execute(
        "SELECT COALESCE(SUM(MIN(COALESCE(ms, 0), ?)), 0) FROM answer_log WHERE user_id = ?",
        (ANSWER_CAP_MS, conn.user_id)).fetchone()
    return float(row[0] or 0) / 3_600_000.0


# ---------------------------------------------------------- the changelog

_HEAD = re.compile(r"^## (\d{4}-\d{2}-\d{2})\s*$")


def changes_since(since, text=None, most=3):
    """What the coffee has meant: the changelog's entries since a day.

    Returns {"count", "since", "lines"}: how many one-line entries fall on
    or after `since`, and the latest few, first sentence only, for a card.
    """
    if text is None:
        try:
            text = (paths.ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        except OSError:
            text = ""
    since = str(since or "")[:10]
    count, lines, day = 0, [], None
    for raw in text.splitlines():
        m = _HEAD.match(raw)
        if m:
            day = m.group(1)
            continue
        if day is None or (since and day < since) or not raw.startswith("- "):
            continue
        count += 1
        if len(lines) < most:
            entry = raw[2:].strip()
            # The subject up to its first colon or full stop: the changelog
            # writes a sentence and then explains it, and a card wants the
            # sentence.
            cut = re.split(r"[:.](?:\s|$)", entry, maxsplit=1)[0].strip()
            lines.append(cut[:120] or entry[:120])
    return {"count": count, "since": since, "lines": lines}


# --------------------------------------------------------------- the card

def _month_words(day):
    try:
        d = datetime.strptime(str(day)[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return f"{d:%B %Y}"


def card(conn, now=None, supporters=None, changelog=None):
    """What the dashboard shows this account today, if anything.

    {"kind": "none"}; or "thanks" with the callsign, what has changed since
    and how many others are on the list; or "coffee" with the hours. Pure:
    :func:`shown` records that a card was shown.
    """
    now = time.time() if now is None else now
    today = date.fromtimestamp(now).isoformat()
    rec = record(conn)
    if rec:
        if db.kv_get(conn, THANKED) == today:
            return {"kind": "none"}
        changes = changes_since(rec["since"], changelog)
        if supporters is None:
            from . import credits
            supporters = credits.supporters()
        others = sum(1 for s in supporters if normalise(s.get("who")) != rec["callsign"])
        return {
            "kind": "thanks", "callsign": rec["callsign"], "named": rec["named"],
            "since": rec["since"], "since_words": _month_words(rec["since"]),
            "changes": changes["count"], "lines": changes["lines"], "others": others,
            "title": f"Thank you, {rec['callsign']}, for your generous support of this project.",
            "line": (f"Since your coffee in {_month_words(rec['since'])}, ELMER has changed "
                     f"{changes['count']} time{'s' if changes['count'] != 1 else ''}."
                     if changes["count"] else
                     f"Your coffee arrived in {_month_words(rec['since'])}; the next release "
                     "is being brewed on it."),
            "others_line": (f"You and {others} other{'s' if others != 1 else ''} are on the list."
                            if others else ""),
        }
    hours = active_hours(conn)
    if hours < ASK_AFTER_HOURS:
        return {"kind": "none"}
    asked = db.kv_get(conn, ASKED) or {}
    if asked and hours - float(asked.get("hours") or 0) < ASK_AGAIN_HOURS:
        return {"kind": "none"}
    whole = int(hours)
    return {
        "kind": "coffee", "hours": whole, "url": SPONSORS_URL,
        "title": f"ELMER has your {whole} hours.",
        "line": ("The developer has several hobbies competing for their evenings; "
                 "a cup of coffee is how this one wins a few more of them."),
        "foot": "It stays free for everyone, coffee or no coffee.",
    }


def shown(conn, kind, now=None):
    """The card was shown: the coffee card waits a hundred hours, the thanks
    card waits for tomorrow."""
    now = time.time() if now is None else now
    if kind == "coffee":
        db.kv_set(conn, ASKED, {"at": now, "hours": active_hours(conn)})
    elif kind == "thanks":
        db.kv_set(conn, THANKED, date.fromtimestamp(now).isoformat())


def honour_line(callsign, game=None):
    """The hall's card for a table whose unit is a supporter's."""
    what = GAME_WORD.get(str(game or "").lower(), "session")
    return f"This {what} is brought to you by the generous contribution of {callsign}."


if __name__ == "__main__":       # python -m elmer.supporter KC9SP
    import sys
    for arg in sys.argv[1:] or [""]:
        key = make_key(arg)
        print(key if key else f"{arg!r} is not a callsign")
