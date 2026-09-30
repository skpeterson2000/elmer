"""A CW contact with a virtual partner: a safe place to learn conversation.

Copying code is a skill and sending it is another, and neither is the thing
a newcomer is afraid of. That is the contact itself - somebody real at the
other end, a call to get right, a report to give, a name to catch, and the
awful moment of not knowing what to send next. This is that contact, with
nobody real at the other end: a partner who answers a CQ or calls one, gives
a report, asks a name, talks about the rig and the weather, and says 73.

What makes it more than a script is that the partner copies what your fist
actually sent - the decoder's reading of your keying, not what you meant.
A call with a character in it that would not decode gets "PSE AGN UR CALL";
a name that came through as JOM is JOM; ragged timing gets "PSE QRS" and a
readability in the report to match. It answers at the speed you send, slows
for QRS and speeds for QRQ, repeats itself for AGN, and understands the
usual abbreviations in whatever order they arrive.

The client keys each over through the CW page's own decoder and posts the
text it read, with '*' for anything that did not decode, and a quality
figure for the fist. This module keeps the contact's state and writes the
partner's next over; the page sends it in code.
"""
import logging
import random
import re
from datetime import datetime

from . import cw

log = logging.getLogger("elmer")

# What the partner is: enough of a station to talk about.
NAMES = ["JIM", "BOB", "ANN", "SUE", "TOM", "MAX", "LEE", "PAT", "RAY", "JOE", "DON", "BILL",
         "KAY", "BEV", "HAL", "ED", "AL", "DAVE", "RON", "JAN", "GARY", "MIKE", "CAROL", "WALT"]
QTHS = ["DENVER CO", "AUSTIN TX", "BOISE ID", "TULSA OK", "DAYTON OH", "SALEM OR", "OMAHA NE",
        "RENO NV", "TAMPA FL", "ALBANY NY", "FARGO ND", "MACON GA", "HELENA MT", "DOVER DE",
        "BANGOR ME", "PEORIA IL", "YAKIMA WA", "TUCSON AZ", "DULUTH MN", "ERIE PA"]
RIGS = ["IC7300", "K3", "KX2", "FT991A", "TS590", "FT710", "IC7610", "K4", "HOMEBREW"]
ANTS = ["DIPOLE", "EFHW", "VERT", "YAGI", "LOOP", "INV V", "G5RV", "HEXBEAM"]
POWERS = [5, 10, 50, 100, 100, 100, 500]
SKIES = ["SUNNY", "CLDY", "RAIN", "SNOW", "CLEAR", "WINDY", "FOG", "OVC"]

# Words that end a field in an over: the next topic, a prosign, a joining word.
STOP = {"NAME", "OP", "QTH", "RST", "UR", "RIG", "ANT", "PWR", "WX", "AGE", "HW", "HW?", "BT", "K",
        "KN", "AR", "BK", "SK", "ES", "TNX", "TU", "FB", "DE", "R", "PSE", "73", "HR", "=", "+"}
FIELDS = {"NAME": "name", "OP": "name", "QTH": "qth", "RIG": "rig", "ANT": "ant", "PWR": "pwr",
          "WX": "wx", "AGE": "age"}
OVER = {"K", "KN", "BK", "AR", "SK"}
CALLISH = re.compile(r"^(?=.*\d)[A-Z0-9*]{3,7}(?:/[A-Z0-9*]{1,4})?$")
RST_TOKEN = re.compile(r"^[1-5*][1-9N*][1-9N*]$")

# The fist, from the client: 1.0 is clean, 0 undecodable. Below these the
# partner says so - in the report and, lower still, by asking for QRS.
READABLE = ((0.9, 5), (0.75, 4), (0.55, 3), (0.0, 2))
ASK_QRS_BELOW = 0.6
WPM_MIN, WPM_MAX = 5, 35


def persona(rng):
    """The station at the other end."""
    return {"call": cw._callsign(rng), "name": rng.choice(NAMES), "qth": rng.choice(QTHS),
            "rig": rng.choice(RIGS), "ant": rng.choice(ANTS), "pwr": rng.choice(POWERS),
            "wx": rng.choice(SKIES), "temp": rng.randint(18, 88),
            "age": rng.randint(24, 84), "strength": rng.randint(5, 9)}


def _greeting(hour=None):
    hour = datetime.now().hour if hour is None else hour
    return "GM" if hour < 12 else "GA" if hour < 18 else "GE"


def _clean(token):
    return token.strip(".,;:!")


def parse(text):
    """What an over says, read the way an operator would: calls, a report,
    the fields a ragchew trades, questions asked, and how it hands back."""
    # A prosign keyed run-together decodes as its punctuation twin - AR is
    # "+", BT "=", KN "(" - so they are read back as the prosigns they were.
    text = str(text or "").upper()
    for twin, name in (("(", " KN "), ("+", " AR "), ("=", " BT ")):
        text = text.replace(twin, name)
    words = [_clean(w) for w in text.split()]
    words = [w for w in words if w]
    out = {"words": words, "cq": "CQ" in words, "de": None, "to": None, "rst": None,
           "fields": {}, "asks": set(), "agn": False, "qrs": False, "qrq": False,
           "closing": False, "over": words[-1] if words and words[-1] in OVER else None,
           "garbled": sum(1 for w in words if "*" in w)}
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else ""
        if w == "DE" and nxt and CALLISH.match(nxt):
            out["de"] = nxt
        elif CALLISH.match(w) and out["to"] is None and nxt == "DE":
            out["to"] = w
        if w in ("RST", "UR", "RPT") or (w == "IS" and i and words[i - 1] in ("RST", "RPT")):
            for cand in words[i + 1:i + 4]:
                if RST_TOKEN.match(cand):
                    out["rst"] = cand.replace("N", "9")
                    break
        if w in FIELDS and not nxt.endswith("?"):
            j = i + 1
            while j < len(words) and words[j] in ("IS", "HR", "="):
                j += 1
            got = []
            while j < len(words) and words[j] not in STOP and len(got) < 3 and not words[j].endswith("?"):
                if FIELDS[w] == "name" and got:
                    break                       # a name is one word; repeats follow
                got.append(words[j])
                j += 1
            # "NAME JIM JIM": the repeat is emphasis, not a surname.
            if len(got) >= 2 and got[-1] == got[-2]:
                got = got[:-1]
            if got:
                out["fields"].setdefault(FIELDS[w], " ".join(got))
        # Questions: "HW?", "NAME?", "UR QTH?", or the word then a lone "?".
        q = w[:-1] if w.endswith("?") else (w if nxt == "?" else None)
        if q in ("HW", "NAME", "QTH", "RIG", "ANT", "WX", "AGE", "PWR", "OP"):
            out["asks"].add("name" if q == "OP" else q.lower())
        if w in ("AGN", "AGN?", "QSM", "QSM?") or (w == "?" and len(words) <= 3):
            out["agn"] = True
        if w in ("QRS", "QRS?"):
            out["qrs"] = True
        if w in ("QRQ", "QRQ?"):
            out["qrq"] = True
        if w in ("73", "SK", "CUL", "GB"):
            out["closing"] = True
    return out


def _rst(p, quality):
    """The report the partner gives: readability from the fist, strength from
    the path, and a tone of 9 - every rig keys a clean note now."""
    return f"{readability(quality)}{p['strength']}9"


def readability(quality):
    q = 1.0 if quality is None else float(quality)
    return next(r for bar, r in READABLE if q >= bar)


def start(cq="them", wpm=18, seed=None, hour=None):
    """A new contact. `cq` says who calls: "them" and the partner calls CQ
    for you to answer; "me" and you call, and the partner answers."""
    rng = random.Random(seed)
    p = persona(rng)
    state = {"partner": p, "cq": cq, "phase": "cq_them" if cq == "them" else "cq_me",
             "wpm": int(max(WPM_MIN, min(WPM_MAX, round(float(wpm or 18))))), "adjust": 0,
             "heard": {}, "told": [], "turns": 0, "qualities": [], "last": "", "seed": seed,
             "hour": hour}
    if cq == "them":
        state["last"] = f"CQ CQ CQ DE {p['call']} {p['call']} K"
    return state, state["last"]


def _topics(state):
    return [t for t in ("rig", "wx", "age") if t not in state["told"]]


def _tell(p, topic):
    if topic == "rig":
        return f"RIG HR {p['rig']} {p['pwr']}W ES ANT {p['ant']}"
    if topic == "wx":
        return f"WX HR {p['wx']} ES {p['temp']}F"
    if topic == "age":
        return f"AGE HR {p['age']} ES HAM {max(1, p['age'] - 20 - (p['age'] % 17))} YRS"
    if topic == "name":
        return f"NAME {p['name']} {p['name']}"
    if topic == "qth":
        return f"QTH {p['qth']} {p['qth']}"
    if topic == "pwr":
        return f"PWR {p['pwr']}W"
    if topic == "ant":
        return f"ANT {p['ant']}"
    return ""


ACK = {"name": "FB {v}", "qth": "{v} FB QTH", "rig": "FB RIG", "ant": "FB ANT",
       "wx": "WX {v} SOUNDS OK", "age": "FB", "pwr": "FB"}


def turn(state, text, quality=None, wpm=None):
    """One over from the operator, and the partner's answer. Returns
    (state, reply, notes): `notes` says, for the page, what the partner
    could not copy and why it asked what it asked."""
    p = state["partner"]
    got = parse(text)
    heard = state["heard"]
    notes = []
    state["turns"] += 1
    if quality is not None:
        state["qualities"].append(round(float(quality), 2))
    if wpm:
        state["wpm"] = int(max(WPM_MIN, min(WPM_MAX, round(float(wpm)) + state["adjust"])))

    if not got["words"]:
        return state, "", ["Nothing came through - key your over and end it with K."]
    if got["qrs"]:
        state["adjust"] -= 3
        state["wpm"] = max(WPM_MIN, state["wpm"] - 3)
    if got["qrq"]:
        state["adjust"] += 3
        state["wpm"] = min(WPM_MAX, state["wpm"] + 3)
    if got["agn"] and state["last"] and len(got["words"]) <= 4:
        notes.append("They sent that again, as asked.")
        return state, "OK AGN " + state["last"], notes

    # What the partner copied of you, as your fist sent it.
    you = got["de"] or heard.get("call")
    if got["de"]:
        heard["call"] = got["de"]
    for k, v in got["fields"].items():
        heard[k] = v
    if got["rst"]:
        heard["rst"] = got["rst"]
    ucall = heard.get("call") or ""
    ragged = quality is not None and float(quality) < ASK_QRS_BELOW
    qrs = "PSE QRS " if ragged else ""
    if ragged:
        notes.append("Your fist was hard to copy on that over - they asked you to send slower.")

    # Answering, or being answered.
    if state["phase"] == "cq_me":
        if not got["cq"] and not got["de"]:
            return state, "", ["No CQ heard - send CQ CQ DE and your call twice, then K."]
        if not you or "*" in you:
            notes.append("They could not copy your call - it came through as " + (you or "nothing") + ".")
            return _say(state, f"QRZ? {qrs}DE {p['call']} K"), state["last"], notes
        state["phase"] = "first_me"
        return _say(state, f"{you} DE {p['call']} {p['call']} K"), state["last"], notes

    if state["phase"] == "cq_them":
        if not you or "*" in you:
            notes.append("They could not copy your call - it came through as "
                         + (you or "nothing: send DE and your call") + ".")
            return _say(state, f"QRZ? {qrs}DE {p['call']} K"), state["last"], notes
        state["phase"] = "chat"
        report = _rst(p, quality)
        heard_rst = f"TNX FER RPT {heard['rst']} " if heard.get("rst") else ""
        return _say(state, f"{you} DE {p['call']} {_greeting(state.get('hour'))} {qrs}"
                           f"{heard_rst}TNX FER CALL <BT> UR RST {report} {report} <BT> "
                           f"NAME {p['name']} {p['name']} <BT> QTH {p['qth']} {p['qth']} <BT> "
                           f"HW? <AR> {you} DE {p['call']} KN"), state["last"], notes

    if state["phase"] == "done":
        return state, "", ["The contact is over - 73. Start a new one when you are ready."]

    # The operator's first over after being answered: reports and the rest.
    parts = []
    if got["qrs"] or got["qrq"]:
        parts.append("QRS OK" if got["qrs"] else "QRQ OK")
    if state["phase"] == "first_me":
        state["phase"] = "chat"
        report = _rst(p, quality)
        parts.append(f"R R {_greeting(state.get('hour'))}")
        if heard.get("name") and "*" not in heard["name"]:
            parts.append(f"{heard['name']}")
        if heard.get("rst"):
            parts.append(f"TNX FER {heard['rst']}")
        parts.append(f"<BT> UR RST {report} {report} <BT> NAME {p['name']} {p['name']} <BT> "
                     f"QTH {p['qth']} {p['qth']}")
    else:
        # Acknowledge what came through, in the order it was said.
        acks = []
        for k, v in got["fields"].items():
            if "*" in v:
                acks.append(f"UR {k.upper()} AGN?")
                notes.append(f"Your {k} did not decode cleanly - it came through as {v}.")
            elif k in ACK:
                acks.append(ACK[k].format(v=v))
        if got["rst"] and "*" not in got["rst"]:
            acks.insert(0, f"TNX FER {got['rst']}")
        parts.append("R R " + (" ".join(acks) if acks else "FB"))

    # Answer what was asked.
    for q in sorted(got["asks"]):
        if q == "hw":
            parts.append(f"UR SIGS {_rst(p, quality)}"
                         + (" SOLID CPY" if readability(quality) >= 5 else " QSB"))
        elif q in ("name", "qth", "rig", "ant", "wx", "age", "pwr"):
            parts.append(_tell(p, q))
            if q in ("rig", "ant", "pwr"):
                state["told"].append("rig")
            elif q in ("wx", "age"):
                state["told"].append(q)

    # Closing, from either end.
    uname = heard.get("name") if heard.get("name") and "*" not in heard.get("name", "*") else "OM"
    if got["closing"]:
        state["phase"] = "done"
        parts.append(f"TNX FER FB QSO {uname} <BT> 73 ES GUD DX {ucall} DE {p['call']} <SK> TU E E")
        return _say(state, qrs + " ".join(parts)), state["last"], notes
    left = _topics(state)
    if left:
        topic = left[0]
        state["told"].append(topic)
        parts.append("<BT> " + _tell(p, topic))
        if topic == "rig" and "rig" not in heard:
            parts.append("UR RIG?")
    else:
        state["phase"] = "closing"
        parts.append(f"<BT> WELL {uname} TNX FER FB QSO HPE CUL <BT> 73")
    parts.append(f"{ucall} DE {p['call']} " + ("<SK>" if state["phase"] == "closing" else "KN"))
    return _say(state, qrs + " ".join(parts)), state["last"], notes


def _say(state, text):
    state["last"] = re.sub(r"\s+", " ", text).strip()
    return state


def summary(state):
    """What the partner copied of the operator, and how the fist went."""
    qs = state.get("qualities") or []
    return {"heard": dict(state.get("heard") or {}), "turns": state.get("turns", 0),
            "fist": round(sum(qs) / len(qs), 2) if qs else None, "done": state.get("phase") == "done",
            "partner": {"call": state["partner"]["call"], "name": state["partner"]["name"],
                        "qth": state["partner"]["qth"]}}
