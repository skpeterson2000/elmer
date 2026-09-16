"""Morse code: the alphabet, the teaching order, and practice material.

Timing follows the PARIS standard: a dit is 1200/wpm milliseconds, a dah is
three dits, the gap inside a character is one dit, between characters three,
between words seven.

Characters are introduced in Koch order and always sent at full character
speed, with the *spacing* stretched to slow things down (Farnsworth). Learning
a slowed-down character teaches the wrong sound, and it has to be unlearned
later; learning the real sound with more thinking time between does not.
"""
import random
import re

MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "/": "-..-.", "=": "-...-",
    "+": ".-.-.", "-": "-....-", ":": "---...", "(": "-.--.", ")": "-.--.-",
    '"': ".-..-.", "'": ".----.", "@": ".--.-.", "!": "-.-.--",
}
REVERSE = {code: char for char, code in MORSE.items()}

# Sent as a single character with no gap inside them.
PROSIGNS = {
    "AR": (".-.-.", "end of message"),
    "SK": ("...-.-", "end of contact"),
    "BT": ("-...-", "break, or a new paragraph"),
    "KN": ("-.--.", "go ahead, named station only"),
    "AS": (".-...", "wait"),
    "BK": ("-...-.-", "break in"),
    "VE": ("...-.", "understood"),
    "HH": ("........", "error, start that word again"),
}

# The Koch order: hardest and most distinctive first, so the ear learns to
# discriminate from the start rather than easing in on E and T.
KOCH_ORDER = list("KMRSUAPTLOWI.NJEF0Y,VG5/Q9ZH38B?427C1D6X")

Q_SIGNALS = {
    "QRL": "is this frequency busy?",
    "QRM": "interference from other stations",
    "QRN": "atmospheric noise, static",
    "QRO": "increase power",
    "QRP": "reduce power, or low power operation",
    "QRQ": "send faster",
    "QRS": "send slower",
    "QRT": "stop sending, closing down",
    "QRU": "have you anything for me?",
    "QRV": "ready",
    "QRX": "wait, stand by",
    "QRZ": "who is calling me?",
    "QSB": "fading",
    "QSL": "acknowledged, confirmed",
    "QSO": "a contact",
    "QSY": "change frequency",
    "QTH": "location",
    "QTR": "time",
}

ABBREVIATIONS = {
    "CQ": "calling any station", "DE": "from", "K": "over, go ahead",
    "R": "received", "RST": "signal report", "TU": "thank you",
    "73": "best regards", "88": "love and kisses", "OM": "old man",
    "YL": "young lady", "ES": "and", "HI": "laughter", "PSE": "please",
    "TNX": "thanks", "UR": "your", "WX": "weather", "AGN": "again",
    "ANT": "antenna", "RIG": "station equipment", "FB": "fine business",
}

CALL_PREFIXES = ["W", "K", "N", "AA", "KB", "KC", "KD", "KE", "KI", "KJ",
                 "AB", "AC", "AD", "AE", "AF", "AG", "AI", "AJ", "AK"]
DX_PREFIXES = ["G", "M", "DL", "F", "I", "EA", "JA", "VE", "VK", "ZL", "PY",
               "LU", "OH", "SM", "LA", "OZ", "PA", "ON", "HB9", "SP", "OK",
               "YU", "SV", "UA", "JH", "BY", "HL", "9A", "S5", "OE"]


def timing(wpm, effective_wpm=None):
    """PARIS timing in milliseconds, with optional Farnsworth spacing.

    Characters are always sent at ``wpm``. When ``effective_wpm`` is lower, the
    extra time is added to the gaps between characters and words, never inside
    a character.
    """
    wpm = max(1.0, float(wpm))
    dit = 1200.0 / wpm
    effective = min(float(effective_wpm or wpm), wpm)
    if effective >= wpm:
        return {"dit": dit, "dah": 3 * dit, "symbol_gap": dit,
                "char_gap": 3 * dit, "word_gap": 7 * dit, "wpm": wpm,
                "effective_wpm": wpm, "farnsworth": False}
    # PARIS: 50 dit units per word. Total delay to spread across a word at the
    # slower effective speed, per ARRL's Farnsworth formulation.
    total = (60.0 / effective) - (37.2 / wpm)
    unit = total / 19.0 * 1000.0          # 19 units of gap in "PARIS "
    return {"dit": dit, "dah": 3 * dit, "symbol_gap": dit,
            "char_gap": 3 * unit, "word_gap": 7 * unit, "wpm": wpm,
            "effective_wpm": effective, "farnsworth": True}


# A prosign written out: <AR>, <SK>, <BT>. Two or three letters run together
# with no gap inside them, which is the whole difference between the prosign AR
# and the letters A R - and it is audible. The brackets are how every logging
# program and bulletin writes them, so they are what ELMER reads.
#
# Bare "AR" is deliberately *not* treated as a prosign: "AS" and "BK" are also
# ordinary words, and somebody typing a sentence into the sender means the
# letters. Anything generated here that means the prosign says so in brackets.
PROSIGN_ANY = re.compile(r"<([A-Z]{2,3})>")


def encode(text):
    """Text to a list of words, each a list of {char, code}.

    Unknown characters are dropped. <AR> and friends become one symbol with no
    gap inside, which is what makes a prosign a prosign, and they are found
    wherever they sit rather than only when they are a whole word - "<AR>" at
    the end of a line usually has something after it.
    """
    out = []
    for word in str(text).upper().split():
        symbols, pos = [], 0

        def letters(run):
            for char in run:
                if char in MORSE:
                    symbols.append({"char": char, "code": MORSE[char]})

        for found in PROSIGN_ANY.finditer(word):
            letters(word[pos:found.start()])
            name = found.group(1)
            if name in PROSIGNS:
                code, meaning = PROSIGNS[name]
                symbols.append({"char": name, "code": code,
                                "meaning": meaning, "prosign": True})
            else:
                letters(name)              # <XY> that is not a prosign we know
            pos = found.end()
        letters(word[pos:])
        if symbols:
            out.append(symbols)
    return out


def plain(text):
    """The same text as it should be typed back - <AR> reads as AR.

    What is sent and what a student writes down are not spelled the same way,
    and marking somebody wrong for the angle brackets they cannot hear would be
    nonsense.
    """
    return PROSIGN_ANY.sub(lambda m: m.group(1), str(text).upper())


def encode_prosign(name):
    code, meaning = PROSIGNS[name]
    return {"char": name, "code": code, "meaning": meaning, "prosign": True}


def decode_code(code):
    return REVERSE.get(code) or next(
        (name for name, (c, _) in PROSIGNS.items() if c == code), None)


def koch_set(lesson):
    """The characters available at a lesson number, 2 upward."""
    return KOCH_ORDER[:max(2, min(len(KOCH_ORDER), int(lesson)))]


def _callsign(rng, dx=False):
    prefix = rng.choice(DX_PREFIXES if dx else CALL_PREFIXES)
    digit = str(rng.randint(0, 9)) if not prefix[-1].isdigit() else ""
    suffix = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                     for _ in range(rng.randint(1, 3)))
    return f"{prefix}{digit}{suffix}"


QSO_TEMPLATES = [
    "CQ CQ DE {me} {me} K",
    "{you} DE {me} GE OM UR RST {rst} {rst} QTH {qth} <BT> HW? <AR>",
    "{you} DE {me} R R TNX FER CALL UR RST {rst} <BT> NAME {name} ES QTH {qth} K",
    "{you} DE {me} R FB {name} TNX FER QSO 73 ES GL <SK>",
    "{you} DE {me} QRZ? QSB ES QRM HR PSE AGN K",
    "{you} DE {me} R TU FER RPRT WX HR {wx} <BT> RIG {watts}W ANT DIPOLE <AR>",
]
NAMES = ["JIM", "BOB", "ANN", "SUE", "TOM", "MAX", "LEE", "PAT", "RAY", "JOE"]
QTHS = ["MN", "OH", "TX", "CA", "NY", "FL", "WA", "ME", "AZ", "CO"]
WX = ["SUNNY", "RAIN", "SNOW", "CLOUDY", "COLD", "WARM", "FOG", "WINDY"]


def practice(kind, count=5, lesson=10, seed=None, callsign=None):
    """Generate a practice item: a list of groups of text to send."""
    rng = random.Random(seed)
    kind = kind or "koch"

    if kind == "koch":
        chars = koch_set(lesson)
        return [" ".join("".join(rng.choice(chars) for _ in range(5))
                         for _ in range(count))]
    if kind == "letters":
        return [" ".join("".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
                                 for _ in range(5)) for _ in range(count))]
    if kind == "numbers":
        return [" ".join("".join(rng.choice("0123456789") for _ in range(5))
                         for _ in range(count))]
    if kind == "mixed":
        pool = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/.,?="
        return [" ".join("".join(rng.choice(pool) for _ in range(5))
                         for _ in range(count))]
    if kind == "callsigns":
        return [" ".join(_callsign(rng, dx=rng.random() < 0.4)
                         for _ in range(count))]
    if kind == "qsignals":
        keys = rng.sample(sorted(Q_SIGNALS), min(count, len(Q_SIGNALS)))
        return [" ".join(keys)]
    if kind == "abbreviations":
        keys = rng.sample(sorted(ABBREVIATIONS), min(count, len(ABBREVIATIONS)))
        return [" ".join(keys)]
    if kind == "prosigns":
        keys = rng.sample(sorted(PROSIGNS), min(count, len(PROSIGNS)))
        return [" ".join(f"<{k}>" for k in keys)]
    if kind == "words":
        words = words_for(koch_set(lesson), count, seed)
        return [" ".join(words) if words else " ".join("".join(rng.choice(koch_set(lesson)) for _ in range(5))
                                                       for _ in range(count))]
    if kind == "qso":
        me = callsign or _callsign(rng)
        return [rng.choice(QSO_TEMPLATES).format(
            me=me, you=_callsign(rng, dx=rng.random() < 0.3),
            rst=f"5{rng.randint(5, 9)}{rng.randint(5, 9)}",
            name=rng.choice(NAMES), qth=rng.choice(QTHS),
            wx=rng.choice(WX), watts=rng.choice([5, 10, 50, 100]))]
    return practice("koch", count, lesson, seed, callsign)


# Real words, for the day the lesson's characters can spell some: the
# commonest English words and the words a CW contact is made of. A word is
# offered only when every character in it has been met, so the first words
# come at about lesson eight and the list grows with the lesson.
WORDS = (
    "THE AND FOR ARE BUT NOT YOU ALL ANY CAN HAD HER WAS ONE OUR OUT DAY GET HAS HIM HIS HOW MAN NEW NOW OLD SEE "
    "TWO WAY WHO BOY DID ITS LET PUT SAY SHE TOO USE THAT WITH HAVE THIS WILL YOUR FROM THEY KNOW WANT BEEN GOOD "
    "MUCH SOME TIME VERY WHEN COME HERE JUST LIKE LONG MAKE MANY MORE ONLY OVER SUCH TAKE THAN THEM WELL WERE "
    "WORK YEAR BACK CALL CAME EACH EVEN FIND GIVE HAND HIGH KEEP LAST LEFT LIFE LIVE LOOK MOST NAME NEXT OPEN "
    "PART PLAY SAME SEEM SHOW SIDE TELL TURN WEEK WENT WORD ABOUT AFTER AGAIN COULD EVERY FIRST GREAT HOUSE LARGE "
    "NEVER OTHER PLACE RIGHT SMALL SOUND STILL THEIR THERE THESE THING THINK THREE UNDER WATER WHERE WHICH WHILE "
    "WORLD WOULD WRITE YEARS YOUNG "
    "RAIN SNOW SUN WIND COLD WARM HOT FOG NICE FINE OK SO IS IT AT ON IN TO UP AN AS BE BY DO GO IF MY NO OF OR "
    "AM PM AGE JOB GUY GAL TOWN CITY LAKE HILL FARM ROAD MILE WIRE POLE MAST TOWER RADIO POWER WATTS "
    "CQ DE K R RST TU TNX ES OM YL PSE AGN ANT RIG WX QTH QSL QSO QRM QRN QSB QRP QRO QRT QRZ QSY FB HI GL GE GM GN GA "
    "SK AR BT KN NAME HR UR VY BEST DX NET TEST HW CPY CUL 73 88 599 579 559 "
).split()

# What "solid" means: nine in ten, over enough sends that a lucky run is
# not solid. Twenty is a session's worth of a character.
SOLID_RATE = 0.9
SOLID_SENT = 20


def is_solid(stat):
    return bool(stat) and stat.get("sent", 0) >= SOLID_SENT and stat["copied"] / stat["sent"] >= SOLID_RATE


def plan(progress, setting=None):
    """Where a person is on the Koch order, from their record, and what to
    do next - the one decision the method rests on, made by the record
    rather than by a slider.

    The lesson is two characters plus every character in order that is
    solid; the next character in the order is the new one. A slider set
    higher is honoured - a person may push on - but the plan says if the
    record does not back it. `weak` is every met character not yet solid,
    worst first, with what it was heard as."""
    progress = progress or {}
    leading = 0
    for ch in KOCH_ORDER:
        if is_solid(progress.get(ch)):
            leading += 1
        else:
            break
    earned = max(2, min(len(KOCH_ORDER), leading + 1))
    lesson = earned
    ahead = False
    if setting:
        try:
            wanted = max(2, min(len(KOCH_ORDER), int(setting)))
        except (TypeError, ValueError):
            wanted = earned
        if wanted > earned:
            lesson, ahead = wanted, True
    chars = KOCH_ORDER[:lesson]
    met = [c for c in chars if (progress.get(c) or {}).get("sent")]
    new = [c for c in chars if c not in met] or ([chars[-1]] if lesson > 2 and not is_solid(progress.get(chars[-1])) else [])
    weak = []
    for c in met:
        st = progress[c]
        rate = st["copied"] / st["sent"] if st["sent"] else 0.0
        if not is_solid(st):
            confused = st.get("confused") or {}
            if isinstance(confused, str):
                import json as _json
                try:
                    confused = _json.loads(confused)
                except ValueError:
                    confused = {}
            worst = sorted(confused.items(), key=lambda kv: -kv[1])[:2]
            weak.append({"ch": c, "rate": round(rate, 2), "sent": st["sent"],
                         "heard_as": [w[0] for w in worst]})
    weak.sort(key=lambda w: (w["rate"], -w["sent"]))
    words = [w for w in WORDS if set(w) <= set(chars)]
    done = leading >= len(KOCH_ORDER)
    return {"lesson": lesson, "earned": earned, "ahead": ahead, "chars": chars, "new": new,
            "weak": weak, "words": len(words), "solid": leading, "total": len(KOCH_ORDER), "done": done}


def session(the_plan):
    """Today's session, in order: meet what is new, drill one character at
    a time against the clock, copy groups, then words once there are any.
    Fifteen minutes, and the record decides tomorrow's."""
    steps = []
    if the_plan["done"]:
        steps.append({"kind": "words", "count": 8, "why": "every character is solid - the rest is speed, and words are how it comes"})
        steps.append({"kind": "qso", "count": 1, "why": "a contact, as it would be sent"})
        return steps
    if the_plan["new"]:
        steps.append({"kind": "meet", "chars": the_plan["new"],
                      "why": "new: hear it, see it drawn, hear it again - the sound first, the name second"})
    steps.append({"kind": "flash", "seconds": 90,
                  "why": ("one character at a time, answer as it comes - the reflex, not the recall"
                          + (f"; {', '.join(w['ch'] for w in the_plan['weak'][:3])} come round more often" if the_plan["weak"] else ""))})
    steps.append({"kind": "koch", "count": 5, "why": "five groups of five at speed - copy behind, write what you heard"})
    if the_plan["words"] >= 8:
        steps.append({"kind": "words", "count": 6, "why": "words from the characters you have - the sound of the code as it is used"})
    return steps


def flash_sequence(the_plan, count=40, seed=None):
    """The characters for a flash drill: the lesson's, the weak ones
    weighted up and the new one in often, never three of one running."""
    rng = random.Random(seed)
    chars = list(the_plan["chars"])
    weight = {c: 1.0 for c in chars}
    for w in the_plan["weak"]:
        weight[w["ch"]] = 3.0
    for c in the_plan["new"]:
        weight[c] = 4.0
    out = []
    for _ in range(count):
        # Not three of the same running - with two characters "never twice"
        # would be K M K M, answerable without listening.
        pool = [c for c in chars if not (len(out) >= 2 and out[-1] == out[-2] == c)] or chars
        pick = rng.choices(pool, weights=[weight[c] for c in pool])[0]
        out.append(pick)
    return out


def words_for(chars, count=6, seed=None):
    """Words spelt only from `chars`, or an empty list when there are none."""
    rng = random.Random(seed)
    pool = [w for w in WORDS if set(w) <= set(chars)]
    if not pool:
        return []
    return rng.sample(pool, min(count, len(pool)))


PUNCTUATION = ".,?/=+-:()\"'@!"


def chart():
    """The whole code, grouped the way a wall chart groups it.

    Each entry carries the character and its code; the page draws the dits and
    dahs rather than printing dots and dashes, because the shape is the thing
    being learnt and a full stop and a hyphen are a poor way to show a sound.
    """
    def rows(chars):
        return [{"char": c, "code": MORSE[c], "meaning": MEANINGS.get(c, "")}
                for c in chars if c in MORSE]

    def run_together(text):
        """The code for a string of letters, with the gaps between them.

        A space here means an inter-letter gap rather than a silence of its
        own: it is what the page draws and what it sounds, and it is the whole
        difference between the Q signal QRM and a prosign, which has no gaps
        inside it at all.
        """
        return " ".join(MORSE[c] for c in text if c in MORSE)

    return [
        {"title": "Letters", "note": "in Koch order - hardest and most "
         "distinctive first, which is the order the lessons add them",
         "items": rows([c for c in KOCH_ORDER if c.isalpha()])},
        {"title": "Numbers", "note": "five elements each, dits filling in from "
         "the left as the digit rises", "items": rows("1234567890")},
        {"title": "Punctuation", "note": "the ones that actually get sent",
         "items": rows(PUNCTUATION)},
        {"title": "Q signals", "stacked": True,
         "note": "three letters sent as three letters, gaps and all - which "
         "is what tells QRM from a prosign. A question mark after one asks "
         "it: QRL? is \u201cis this frequency busy?\u201d and QRL on its own "
         "answers \u201cit is\u201d.",
         "items": [{"char": name, "code": run_together(name),
                    "meaning": meaning, "stacked": True}
                   for name, meaning in sorted(Q_SIGNALS.items())]},
        {"title": "Prosigns", "wide": True,
         "note": "run together with no gap inside - that "
         "is what makes them one sound rather than two letters",
         "items": [{"char": name, "code": code, "meaning": meaning,
                    "prosign": True}
                   for name, (code, meaning) in sorted(PROSIGNS.items())]},
    ]


MEANINGS = {}
MEANINGS.update(Q_SIGNALS)
MEANINGS.update(ABBREVIATIONS)
MEANINGS.update({k: v[1] for k, v in PROSIGNS.items()})

KINDS = [
    ("koch", "Koch lesson"), ("words", "Words you can copy"), ("letters", "Letters"), ("numbers", "Numbers"),
    ("mixed", "Mixed characters"), ("callsigns", "Callsigns"),
    ("qsignals", "Q signals"), ("abbreviations", "Abbreviations"),
    ("prosigns", "Prosigns"), ("qso", "QSO fragments"),
]
