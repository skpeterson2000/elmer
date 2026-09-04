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


def encode(text):
    """Text to a list of {char, code} , keeping unknown characters out."""
    out = []
    for word in str(text).upper().split():
        symbols = []
        for char in word:
            if char in MORSE:
                symbols.append({"char": char, "code": MORSE[char]})
        if symbols:
            out.append(symbols)
    return out


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
    "{you} DE {me} GE OM UR RST {rst} {rst} QTH {qth} BT HW? AR",
    "{you} DE {me} R R TNX FER CALL UR RST {rst} BT NAME {name} ES QTH {qth} K",
    "{you} DE {me} R FB {name} TNX FER QSO 73 ES GL SK",
    "{you} DE {me} QRZ? QSB ES QRM HR PSE AGN K",
    "{you} DE {me} R TU FER RPRT WX HR {wx} BT RIG {watts}W ANT DIPOLE AR",
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
        return [" ".join(keys)]
    if kind == "qso":
        me = callsign or _callsign(rng)
        return [rng.choice(QSO_TEMPLATES).format(
            me=me, you=_callsign(rng, dx=rng.random() < 0.3),
            rst=f"5{rng.randint(5, 9)}{rng.randint(5, 9)}",
            name=rng.choice(NAMES), qth=rng.choice(QTHS),
            wx=rng.choice(WX), watts=rng.choice([5, 10, 50, 100]))]
    return practice("koch", count, lesson, seed, callsign)


MEANINGS = {}
MEANINGS.update(Q_SIGNALS)
MEANINGS.update(ABBREVIATIONS)
MEANINGS.update({k: v[1] for k, v in PROSIGNS.items()})

KINDS = [
    ("koch", "Koch lesson"), ("letters", "Letters"), ("numbers", "Numbers"),
    ("mixed", "Mixed characters"), ("callsigns", "Callsigns"),
    ("qsignals", "Q signals"), ("abbreviations", "Abbreviations"),
    ("prosigns", "Prosigns"), ("qso", "QSO fragments"),
]
