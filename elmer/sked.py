"""Frequencies on the unit: two operators, each on their own device, in CW.

The Contact simulator gives somebody a partner who is never nervous and
never in a hurry. The next step is a person - a friend across the room, a
student and an Elmer at the club - and the unit is already the radio they
both reach. So it keeps a handful of frequencies. Tune to one, and what you
key goes out on it, word by word, as your own fist: the decoded text, and
the element timings that make it sound like you rather than like a machine
re-sending your letters. Everybody tuned there hears it, which is two
operators working each other - or, with a third, QRM, as on the air.

Nothing here is kept: a frequency is memory, and a word older than a few
minutes is gone. Who is tuned is whoever has polled lately.
"""
import logging
import threading
import time

log = logging.getLogger("elmer")

# A few frequencies, named as they would be on 40 m and 20 m CW.
FREQS = ("7.030", "7.040", "7.055", "14.050", "14.060")
KEEP = 300               # words kept on a frequency
KEEP_S = 600.0           # and for no longer than this
GONE_S = 20.0            # not polled for this long: no longer tuned
MOST_ELEMENTS = 400      # in one word, from any one device
MOST_TEXT = 120

_lock = threading.Lock()
_freqs = {f: {"seq": 0, "words": [], "tuned": {}} for f in FREQS}


def _now():
    return time.monotonic()


def _prune(f, now):
    f["words"] = [w for w in f["words"] if now - w["at"] < KEEP_S][-KEEP:]
    f["tuned"] = {u: t for u, t in f["tuned"].items() if now - t["seen"] < GONE_S}


def _who(f):
    return [{"call": t["call"], "name": t["name"], "me": False} for t in f["tuned"].values()]


def tune(freq, user, call, name):
    """Tune this operator to a frequency, off any other. Returns the latest
    word number, so the first poll hears only what comes next."""
    if freq not in _freqs:
        raise KeyError(freq)
    now = _now()
    with _lock:
        for other in _freqs.values():
            other["tuned"].pop(user, None)
        f = _freqs[freq]
        _prune(f, now)
        f["tuned"][user] = {"call": call or "", "name": name or "", "seen": now}
        log.info("sked: %s tuned to %s, %d there", call or user, freq, len(f["tuned"]))
        return {"freq": freq, "seq": f["seq"], "tuned": _who(f)}


def leave(user):
    with _lock:
        for f in _freqs.values():
            f["tuned"].pop(user, None)


def keyed(text, wpm):
    """Element timings for typed text, as a clean fist would key it: a word
    typed rather than keyed still goes out as code."""
    from . import cw
    t = cw.timing(max(5.0, min(50.0, float(wpm or 18))))
    els = [["s", t["word_gap"]]]
    for w, word in enumerate(cw.encode(text)):
        if w:
            els.append(["s", t["word_gap"]])
        for i, sym in enumerate(word):
            if i:
                els.append(["s", t["char_gap"]])
            for j, el in enumerate(sym["code"]):
                if j:
                    els.append(["s", t["symbol_gap"]])
                els.append(["m", t["dah"] if el == "-" else t["dit"]])
    return els[:MOST_ELEMENTS]


def send(freq, user, text, elements, wpm):
    """A word keyed by this operator: its text, and its fist as
    [["m", ms], ["s", ms], ...]."""
    if freq not in _freqs:
        raise KeyError(freq)
    els = []
    for kind, ms in (elements or [])[:MOST_ELEMENTS]:
        if kind in ("m", "s"):
            els.append([kind, max(1.0, min(5000.0, float(ms)))])
    if not els and text:
        els = keyed(text, wpm)
    now = _now()
    with _lock:
        f = _freqs[freq]
        _prune(f, now)
        me = f["tuned"].get(user)
        if me is None:
            raise LookupError("not tuned here")
        me["seen"] = now
        f["seq"] += 1
        f["words"].append({"seq": f["seq"], "from": user, "call": me["call"], "at": now,
                           "text": str(text or "")[:MOST_TEXT].upper(), "elements": els,
                           "wpm": max(5.0, min(50.0, float(wpm or 18)))})
        return f["seq"]


def poll(freq, user, after):
    """Words on the frequency since `after`, not this operator's own, and
    who is tuned. Polling is what keeps an operator tuned."""
    if freq not in _freqs:
        raise KeyError(freq)
    now = _now()
    with _lock:
        f = _freqs[freq]
        _prune(f, now)
        if user in f["tuned"]:
            f["tuned"][user]["seen"] = now
        words = [{k: w[k] for k in ("seq", "call", "text", "elements", "wpm")}
                 for w in f["words"] if w["seq"] > after and w["from"] != user]
        tuned = [dict(t, me=(u == user)) for u, t in f["tuned"].items()]
        return {"freq": freq, "seq": f["seq"], "words": words,
                "tuned": [{"call": t["call"], "name": t["name"], "me": t["me"]} for t in tuned]}
