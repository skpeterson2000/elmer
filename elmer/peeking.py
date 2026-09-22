"""Answering the drill from the network tab, and what ELMER says about it.

Every question the drill sends carries `order`, the shuffle its choices were
dealt in. The pool's own answer index is printed on the Browse page for
anybody to read, so `order.index()` of it is the answer to the question on
screen, and anyone who opens the network tab can have it.

That is closed on the mock exam, because the exam is the measurement and a
measurement somebody can reach into is not one. Here it is left open, on
purpose, and this module is what happens instead.

**Why leaving it open is the right answer.** The drill is about to give them
the answer. Not eventually - in about a second, for free, with an
explanation, the FCC rule and a link to the Lab. There is nothing here to
steal. And the question is coming back: the scheduler's whole job is to keep
returning a card until it is answered right on a Tuesday three weeks from
now, and it cannot be got rid of by being right once. So a person decoding
the payload has done strictly more work than pressing a key, to learn
strictly less, in a place that was about to hand it over anyway. Closing the
hole would mean server-side state on every question to defend a thing that
is not worth defending. Saying something is funnier and more useful.

**What actually happens to them.** Nothing punitive, and the joke is better
for it. The answer counts as correct, the scheduler believes it, and it
spaces the card out accordingly - so it comes back in nine days to somebody
who has never read it. The system corrects itself without any help, which is
worth telling them, because it is the part they have not thought about.

**How it is spotted.** Not by looking for a devtools window, which is both
unreliable and creepy. By arithmetic: an answer that is correct, on a
question this account has never seen before, given faster than anybody can
read a question and four choices. One of those is a lucky stab at four
options; three is a decoder. So it is counted and nothing is said until the
third, which puts a false positive at about one in sixty-four - and a false
positive costs nothing anyway, since all that happens is an owl and a badge.

**And yes, it is beatable.** The timing comes from the browser, so anybody
who reads this far can send a plausible `ms` and never be seen. The point at
which somebody is forging timings to avoid being teased by an owl about a
study tool that was going to give them the answer is a point well past
anything this module needs to worry about.
"""
import logging

from . import db

log = logging.getLogger("elmer")

KEY = "read_the_wire"

# Faster than a person can read a question and four choices they have never
# seen. A known card answered on reflex lands around 700 ms; this is set well
# under that, and the unseen-card test below does most of the work anyway.
FLOOR_MS = 450

# How many before ELMER says anything. One is a lucky stab at four choices.
TRIP = 3

BADGE = "peeked"


def impossible(correct, ms, card):
    """Whether this answer cannot have been read off the screen.

    Correct, on a card never seen before, faster than it can be read. Each
    of the three on its own is ordinary; together they are arithmetic.
    """
    if not correct or ms is None:
        return False
    try:
        ms = float(ms)
    except (TypeError, ValueError):
        return False
    if ms < 0 or ms >= FLOOR_MS:
        return False
    return not (card and card["seen"])


# What is said, the first time it trips. Long, because it is the one chance
# to make the actual point - which is not "stop", it is "you have taken the
# long way round to a thing that was free".
FIRST = [
    "Yes. That is the shuffle, in the payload, on every question. It is not "
    "an oversight and it is not going anywhere.",

    "Consider what you have bought. The drill was going to give you that "
    "answer in about a second, for nothing, with an explanation under it, "
    "the FCC rule it comes from and a link to try it in the Lab. You have "
    "done more work than pressing a key, to get less.",

    "And the card is coming back. That is the entire design - a question "
    "returns until you get it right on a Tuesday three weeks from now, and "
    "there is no answering it hard enough to make it stop. What you have "
    "actually done is tell the scheduler you know this one, which it "
    "believes, so it will space the card out and hand it to you again in "
    "nine days, to someone who has still never read it.",

    "The mock exam is sealed, because that one is a measurement. This is "
    "practice, and there is no beating practice - there is only doing it or "
    "not doing it. Have the badge.",
]

# And afterwards. Short, occasional, and never a scolding.
AGAIN = [
    "Still reading the wire. The answer is directly below, as usual.",
    "The payload again. Nine days, and it will be back, and you will not "
    "know it then either.",
    "You are aware this is the part of the program that gives you the "
    "answer for free.",
    "Noted. The scheduler believes you every time, which is the problem.",
]


def seen(conn):
    """How many impossible answers this account has given."""
    kept = db.kv_get(conn, KEY, {}) or {}
    return int(kept.get("count", 0)) if isinstance(kept, dict) else 0


def note(conn, correct, ms, card):
    """Record an impossible answer and return what to say, or None.

    Nothing is said before ``TRIP`` of them. After that the first one says
    the whole thing; later ones get a line, chosen by the count so it moves
    through the list rather than repeating.
    """
    if not impossible(correct, ms, card):
        return None

    kept = db.kv_get(conn, KEY, {}) or {}
    if not isinstance(kept, dict):
        kept = {}
    count = int(kept.get("count", 0)) + 1
    kept["count"] = count
    db.kv_set(conn, KEY, kept)

    if count < TRIP:
        return None
    if count == TRIP:
        log.info("someone is answering %s from the network tab - told, and "
                 "badged for it", "the drill")
        return {"first": True, "count": count, "lines": list(FIRST)}
    return {"first": False, "count": count,
            "lines": [AGAIN[(count - TRIP - 1) % len(AGAIN)]]}
