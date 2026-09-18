"""A supporter's key, the thanks it earns, and the coffee card for everyone else.

ELMER is a gift to the amateur radio community and free for everyone. Some
people will want to thank the developer with a cup of coffee, and the
program should notice that: a person who has should be thanked, and a
person who has not should hear the offer once, lightly, and then be left
alone. Both are this module's business, and nothing here changes what
ELMER does - a key opens no feature and its absence closes none.

**The key.** Eight characters, shown as ``XXXX-XXXX``, from an alphabet
with no 0, O, 1 or I so a key read over the air or off a phone cannot be
mistyped into a different key. The first four are the *registration*
part, a tier letter and three characters drawn at random when the key is
cut; the second four are the *validation* part, a keyed hash of the first
four and the holder's name, so a typo or a key typed under somebody
else's name is caught on the unit before anything is looked up. The
holder is whatever the sponsor wants printed - a callsign, a name, a club
- given in the sponsorship note, and the key is bound to it.

What makes a key real is the roster. Only the developer cuts keys, by
hand, on their own machine, and every key cut goes onto a signed list of
hashes that ships with ELMER - see :mod:`elmer.roster`. The private key
that signs it never leaves the developer; the public key is in the
program; a unit accepts a typed key only when it is on a roster whose
signature checks. Nobody can cut a key for a friend by reading the
source, because reading the source gives them the typo check and not the
signature; and a key that was issued can be taken off the roster again.
The eight characters are what a person types; the signature lives in the
file, which is how a short key and a real check go together. A lost key
is looked up on the roster and reissued.

``ELMER_KEY_SECRET`` keys the typo check and ships in the source by
default; a deployment that wants its own sets it alike on the issuer's
machine and every unit. The tier letter tells kinds of key apart, for a
program with more than one kind.

**The meter.** The coffee card waits until a person has actually used the
program - :func:`active_hours` is the time spent answering questions, each
answer capped so a walk-away does not clock an afternoon - and it is asked
once at ten hours, then not again for a hundred more. It is the person's
meter, not the machine's: on a shared unit each account has its own.

**The thanks.** With a key, the dashboard says thank you once a day, and
says what the coffee meant: how many times ELMER has changed since it was
bought, read off the changelog, with the latest three lines. In a hall the
unit's table carries the holder's name to net control, which puts it on
the card between rounds - see :mod:`elmer.show`.
"""
import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import date, datetime

from . import db, paths, roster

# The secret the validation part is keyed with. In the source by default -
# see the module docstring - and taken from the environment when set.
KEY_SECRET = os.environ.get("ELMER_KEY_SECRET", "elmer-supporter-2026").encode("utf-8")
PRODUCT = b"elmer-supporter"
# No 0/O or 1/I. Thirty-two symbols, five bits a character.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TIER = "S"                      # a supporter's key; the letter is there for other kinds
KEY_LENGTH = 8
KEY_RE = re.compile(r"^([A-Z2-9]{4})-?([A-Z2-9]{4})$")
MAX_HOLDER = 40

ASK_AFTER_HOURS = 10.0          # the first coffee card
ASK_AGAIN_HOURS = 100.0         # and the next, that many hours of use later
ANSWER_CAP_MS = 5 * 60 * 1000   # an answer that took longer was a walk-away

SETTING = "supporter"           # in the profile's settings: {key, holder, named, since}
ASKED = "supporter.asked"       # kv: {"at", "hours"} when the coffee card was last shown
THANKED = "supporter.thanked"   # kv: the day the thanks card was last shown

GAME_WORD = {"tournament": "tournament", "shootout": "shootout",
             "cutthroat": "round of CutThroat", "golf": "round of golf"}

SPONSORS_URL = "https://github.com/sponsors/skpeterson2000"


# ------------------------------------------------------------------ the key

def normalise(holder):
    """A holder's name as the key binds it: upper case, letters and digits
    only, so "John Doe", "john doe" and "JOHN-DOE" are one holder."""
    return re.sub(r"[^A-Z0-9]", "", str(holder or "").upper())


def _symbols(digest, count):
    return "".join(ALPHABET[b % len(ALPHABET)] for b in digest[:count])


def _registration():
    """The first half: the tier letter and three characters drawn at random."""
    return TIER + "".join(secrets.choice(ALPHABET) for _ in range(3))


def _validation(registration, holder):
    """The second half: the keyed hash of the first half and the name."""
    mac = hmac.new(KEY_SECRET, PRODUCT + b":" + registration.encode("ascii") + b":" + holder.encode("utf-8"),
                   hashlib.sha256).digest()
    return _symbols(mac, 4)


def make_key(holder):
    """A new key for a holder, shown as XXXX-XXXX; None when there is no
    name in it. Cutting is the developer's half - the key is not real until
    :func:`roster.issue` has put it on the signed roster."""
    bound = normalise(holder)
    if len(bound) < 2 or len(str(holder or "").strip()) > MAX_HOLDER:
        return None
    reg = _registration()
    return f"{reg}-{_validation(reg, bound)}"


def check_key(key, holder):
    """(holder as given, None) for the holder's key; (None, reason) otherwise."""
    text = re.sub(r"[\s-]+", "", str(key or "").upper())
    name = str(holder or "").strip()[:MAX_HOLDER]
    if not text:
        return None, "no key"
    if len(text) != KEY_LENGTH or not KEY_RE.match(text[:4] + "-" + text[4:]):
        return None, "a key is eight letters and digits, shown as XXXX-XXXX"
    bound = normalise(name)
    if len(bound) < 2:
        return None, "the key needs the name it was cut for - the one given in the note"
    reg, val = text[:4], text[4:]
    if not hmac.compare_digest(val, _validation(reg, bound)):
        return None, f"that is not the key for {name} - check both against the note they came in"
    return name, None


NOT_ON_ROSTER = ("the key reads right but is not on the signed roster this unit has - "
                 "a new key needs a network for a moment, or ELMER updated, before it is accepted")


def verify(key, holder, fetch=False):
    """The whole check: the key reads right for the name, and it is on the
    signed roster - fetching the current one when asked and the key is not
    here. (holder as given, None) or (None, reason)."""
    name, why = check_key(key, holder)
    if name is None:
        return None, why
    if not roster.contains(key, name, fetch=fetch):
        return None, NOT_ON_ROSTER
    return name, None


# ------------------------------------------------------------ the record

def record(conn):
    """This account's supporter record, or None. A record whose key no
    longer checks - the file edited by hand, say - is None too."""
    rec = (db.get_profile(conn)["settings"] or {}).get(SETTING)
    if not isinstance(rec, dict):
        return None
    holder, why = verify(rec.get("key"), rec.get("holder"))
    if holder is None:
        return None
    return {"key": rec["key"], "holder": holder, "named": bool(rec.get("named")),
            "since": str(rec.get("since") or "")}


def apply(settings, key=None, holder=None, named=None, today=None, check=None):
    """Put a key and its holder, or the naming choice, into a settings dict.
    None for a field leaves it; an empty key clears the record. Returns a
    reason when the key is not the holder's, else None. `check` is the
    checker to use - :func:`check_key` by default, the typo check alone;
    the settings endpoint passes :func:`verify` with a fetch, so a key is
    on the roster before it is kept. Pure - the caller saves."""
    check = check or check_key
    old = settings.get(SETTING) if isinstance(settings.get(SETTING), dict) else {}
    if key is not None or holder is not None:
        text = str((old.get("key") if key is None else key) or "").strip()
        name = str((old.get("holder") if holder is None else holder) or "").strip()
        if not text:
            settings.pop(SETTING, None)
        else:
            name, why = check(text, name)
            if name is None:
                return why
            clean = re.sub(r"[\s-]+", "", text.upper())
            settings[SETTING] = {
                "key": clean[:4] + "-" + clean[4:], "holder": name,
                "named": bool(old.get("named")),
                # The month the coffee was bought is the month the key went
                # in; the same key entered again keeps its first date.
                "since": (old.get("since") if normalise(old.get("holder")) == normalise(name)
                          and old.get("since") else (today or date.today()).isoformat())}
    if named is not None and isinstance(settings.get(SETTING), dict):
        settings[SETTING]["named"] = bool(named)
    return None


def set_key(conn, key, holder=None, named=None, fetch=False):
    """Enter a key, or clear it with an empty one. (record, None) or (None, reason)."""
    settings = db.get_profile(conn)["settings"]
    why = apply(settings, key, holder, named,
                check=lambda k, h: verify(k, h, fetch=fetch))
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


def named_holder(conn):
    """The name to put on a hall's card for this unit, or '' - a supporter
    who would rather not be named is not, anywhere."""
    rec = record(conn)
    return rec["holder"] if rec and rec["named"] else ""


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

    {"kind": "none"}; or "thanks" with the holder, what has changed since
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
        mine = normalise(rec["holder"])
        others = sum(1 for s in supporters if normalise(s.get("who")) != mine)
        return {
            "kind": "thanks", "holder": rec["holder"], "named": rec["named"],
            "since": rec["since"], "since_words": _month_words(rec["since"]),
            "changes": changes["count"], "lines": changes["lines"], "others": others,
            "title": f"Thank you, {rec['holder']}, for your generous support of this project.",
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


def honour_line(holder, game=None):
    """The hall's card for a table whose unit is a supporter's."""
    what = GAME_WORD.get(str(game or "").lower(), "session")
    return f"This {what} is brought to you by the generous contribution of {holder}."


def issue(holder, seed_path=None, path=None):
    """The developer's whole step: cut a key for a name and put it on the
    roster. Returns (key, count) or raises with a reason."""
    key = make_key(holder)
    if key is None:
        raise ValueError(f"{holder!r} is not a name to cut a key for")
    count = roster.issue(key, holder, seed_path=seed_path, path=path)
    return key, count
