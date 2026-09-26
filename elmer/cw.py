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


# The most characters worth keying after DE in the opening announcement. A
# callsign is five or six; a club name can be anything, and a room listening
# to a station identify itself will wait for a callsign and not for a
# paragraph. Whole words only, so nothing is cut off mid-name.
ANNOUNCE_MOST = 14

# What a callsign or a name is made of. The code can send a full stop and a
# comma, but a name is not punctuation: "ST. PAUL ARC" reads better keyed
# without the stop than with six more elements in the middle of it, and a
# holder field that is nothing but punctuation should key nothing at all.
KEYABLE = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/")


def keyable(text, most=ANNOUNCE_MOST):
    """A name reduced to what a keyer can actually send, or ''.

    Upper case, and only the characters the code has: letters, digits, the
    slant a portable callsign carries, and single spaces between words. Words
    are kept whole and dropped from the end until the rest fits, because a
    name cut off in the middle is worse than a name left out - this is
    somebody's callsign being read out to a room.
    """
    kept = []
    for word in str(text or "").upper().split():
        clean = "".join(c for c in word if c in KEYABLE)
        if clean:
            kept.append(clean)
    out, used = [], 0
    for word in kept:
        need = len(word) + (1 if out else 0)
        if used + need > most:
            break
        out.append(word)
        used += need
    return " ".join(out)


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
# Judged over the recent past where there is one - the last thirty sends -
# rather than over everything ever sent. A rough first twenty on a character
# used to drag its lifetime ratio for a long time after the sound was known,
# and the next character waited on arithmetic rather than on the person.
# Twenty sends in the window is still the least that counts.
RECENT_WINDOW = 30

# How the drill is dealt: by weight, and the weight is how much work a
# character still needs. A character never met is the heaviest, because it
# is the one being learned. A met character that is not yet solid weighs
# more the worse its recent copy is - one copied half the time comes round
# about three times as often as one that is known. A solid character has
# the least weight, and never none: what is known has to keep being asked
# or it stops being known.
#
# This used to give the newest a third, the single worst a fifth, and deal
# the rest evenly - which meant a second and third shaky character came
# round no more often than the ones the person had cold. Reported, rightly,
# as not what was intended.
WEIGHT_NEW = 4.0
WEIGHT_KNOWN = 1.0
WEIGHT_WEAK_SPAN = 4.0        # a character copied 0% of the time weighs KNOWN + this


# A second way to be sure, and a better one.
#
# The rule above waits for twenty sends and then asks for nine in ten. A person
# who already knows the code - somebody who has come back to this after years,
# or a tester who reset their profile to see what a beginner sees - owes eight
# hundred flawless sends before the last character opens, one character at a
# time, for letters they have copied since before this program existed. That is
# the program failing to notice something it is being shown repeatedly.
#
# It is also, on the arithmetic, the weaker test. Against a flat prior, being
# right eighteen times in twenty leaves only a 35 per cent case that the
# character is really above nine in ten; a clean run of twelve, with no miss at
# all, makes a 75 per cent case. More evidence, eight fewer sends. So a clean
# run is a way through, and the only thing added to it is that the run cannot
# be one lucky minute inside a single drill: at least one of those reps has to
# have been a cold one, the first of a sitting, fetched with nothing warmed up
# in front of it. That is the rep that tells proficiency from momentum.
#
# Nothing here is one-way. is_solid reads the window every time it is asked, so
# a character promoted on a clean run goes straight back to being drilled the
# moment the misses return.
CLEAN_RUN = 12


def is_solid(stat):
    if not stat:
        return False
    recent = str(stat.get("recent") or "")
    if recent.endswith("1" * CLEAN_RUN) and "1" in str(stat.get("cold") or ""):
        return True
    if len(recent) >= SOLID_SENT:
        window = recent[-RECENT_WINDOW:]
        return window.count("1") / len(window) >= SOLID_RATE
    return stat.get("sent", 0) >= SOLID_SENT and stat["copied"] / stat["sent"] >= SOLID_RATE


def recent_rate(stat):
    """How much of a character's recent past was copied, or of its whole
    past where there is no window yet; None for a character never sent."""
    if not stat or not stat.get("sent"):
        return None
    recent = str(stat.get("recent") or "")
    if recent:
        return recent[-RECENT_WINDOW:].count("1") / len(recent[-RECENT_WINDOW:])
    return stat["copied"] / stat["sent"]


# When the drawn shape comes down.
#
# The dits and dahs drawn on screen are how a character is met, and they
# are what shows a mistaken copyist what the sound actually was. During
# the drill they are something else: the eye reads the shape off the
# screen while it is still being sounded, and the answer comes from
# reading rather than from hearing. What that trains is fluency at a
# thing nobody does on the air, and it has to be unlearned afterwards -
# the same argument Farnsworth makes about slowing a character down.
#
# So the shape comes down once a character has been heard right several
# times running, and goes back up if it stops being copied, because a
# character that has gone shaky is being met again. Four in a row, not
# three: with two characters in the lesson, three can be had by guessing
# often enough, and four is still inside a minute of the drill.
WEAN_RUN = 4
WEAN_FLOOR = 0.7


def weaned(stat):
    """Whether this character should now be heard without its shape drawn.

    Asked of the record as it stands rather than stored: a clean run of
    WEAN_RUN inside the recent window means the sound has been heard for
    itself, and recent copy below WEAN_FLOOR puts the shape back up until
    that run is earned again. Nothing here is one-way - a person who
    comes back after a month and starts missing K gets K drawn again
    without having to ask for it.

    A record from before the window was kept has no run to find, so a
    character already solid is taken at the record's word.
    """
    if not stat:
        return False
    recent = str(stat.get("recent") or "")[-RECENT_WINDOW:]
    if not recent:
        return is_solid(stat)
    if "1" * WEAN_RUN not in recent:
        return False
    rate = recent_rate(stat)
    return rate is not None and rate >= WEAN_FLOOR


# How much faster counts as faster. Reaction times bounce about - a sip of
# tea is half a second - so a difference under this is not news and is not
# reported as any.
PACE_NEWS = 0.15          # 15 per cent
PACE_ENOUGH = 4           # recognitions in the recent window before we speak


def pace(stat):
    """How long this character takes now against how long it used to.

    The one thing a learner cannot see from inside is that they are getting
    faster: the percentage they can feel, but "three seconds of thinking in
    the first week, under one in the fourth" is invisible unless somebody
    keeps the clock. The record keeps it now - `first_ms` written once from
    the earliest recognitions, `times` the recent ones - and this is the
    before and after.

    None when there is not enough to say it honestly: no baseline yet, too
    few recent answers, or a difference small enough to be a sip of tea.
    """
    if not stat:
        return None
    first = stat.get("first_ms")
    times = [float(x) for x in str(stat.get("times") or "").split(",") if x]
    if not first or len(times) < PACE_ENOUGH:
        return None
    now = sum(times[-PACE_ENOUGH:]) / len(times[-PACE_ENOUGH:])
    change = (first - now) / first
    return {"first_s": round(first / 1000.0, 1), "now_s": round(now / 1000.0, 1),
            "faster": change >= PACE_NEWS, "slower": change <= -PACE_NEWS,
            "by": abs(round(change * 100))}


# ------------------------------------------------------ a cold rep and a warm one
#
# A reaction time means two different things depending on when it was taken.
# The first time a character comes round in a sitting - nothing heard yet, no
# warm-up behind it - is the rep that says whether the learning is there. The
# eighth in a row inside a ninety-second drill says the drill is still
# running. Both went into one pile, so the baseline was the mean of whichever
# few came first, warm or cold, and the two were never comparable.
#
# The cold rep is also how a character gets a baseline at all. A brand-new
# learner has none and cannot be handed one. They build one a character at a
# time, and the first cold rep that lands is the moment a character joins it.
#
# This is how a dog is judged on "sit": not the tenth in a row with a treat
# already in the air, but the first one of the walk. That rep is the marker -
# it says the expectation is achievable from cold - and it is the one that
# earns the fuss.
COLD_GAP_MS = 60000       # this long since the character was last answered
COLD_ENOUGH = 3           # cold reps past the landmark before the clock speaks


def learned(stat):
    """Whether this character has ever been named cold.

    The landmark, and a low bar on purpose: once, from a standing start, with
    nothing warmed up in front of it. Gross replication - the dog sat. What
    comes after is refinement, and refinement is not what earns the fuss;
    see :func:`wins`.
    """
    return bool(stat and "1" in str(stat.get("cold") or ""))


def cold_rate(stat):
    """How often the first rep of a sitting lands, or None with none taken.

    The question a trainer actually asks - "how is the dog doing on this?" -
    and it is asked of the cold rep because that is the only one that is not
    propped up by the eight before it.
    """
    cold = str((stat or {}).get("cold") or "")
    return cold.count("1") / len(cold) if cold else None


def cold_pace(stat):
    """The cold rep now against the cold rep that first landed.

    Slower to speak than :func:`pace` and it should be: there is at most one
    cold rep per sitting, so this is days of practice rather than minutes of
    it. The landmark itself is kept out of the recent window - it is the
    before, and averaging it into the after would flatten the very thing
    being measured.
    """
    if not stat:
        return None
    first = stat.get("cold_first_ms")
    times = [float(x) for x in str(stat.get("cold_times") or "").split(",") if x]
    if not first or len(times) <= COLD_ENOUGH:
        return None
    now = sum(times[-COLD_ENOUGH:]) / COLD_ENOUGH
    change = (first - now) / first
    return {"first_s": round(first / 1000.0, 1), "now_s": round(now / 1000.0, 1),
            "faster": change >= PACE_NEWS, "slower": change <= -PACE_NEWS,
            "by": abs(round(change * 100))}


# Sleeping on it, which is the only evidence that settles anything.
#
# A cold rep a minute after the last one and a cold rep after a night are the
# same entry in most records and they are not the same evidence. Hearing the
# whole code in an afternoon proves the ear works. Still having it tomorrow is
# the learning, and it is the one measure that serves both ends of the range:
# somebody who tore through the order in a day and somebody who has been on
# the same five letters for a week are asking it the same question, and it
# answers both without flattering either.
#
# A learner who does get through it in a day and still has it the next morning
# is rare and is not to be held back for being rare.
STUCK_DAYS = 4            # met cold on this many days and still not solid


def days_held(stat):
    """The days this character was named cold and landed, most recent last."""
    return [d for d in str((stat or {}).get("cold_days") or "").split(",") if d]


def slept_on(stat):
    """How many separate days it has survived. One is an afternoon; two is a
    night, and a night is the thing."""
    return len(days_held(stat))


def held_overnight(stat):
    """Whether it was there again on a later day. The strongest thing the
    record can say about a character, and the cheapest to earn honestly."""
    return slept_on(stat) >= 2


def stuck(stat):
    """A character that keeps coming back and will not settle, or None.

    Not a judgement and not a failure - some letters simply take longer, and
    the pair they are being confused with is usually the whole story. Said so
    that the drill can do something about it rather than dealing the same
    character again and hoping.
    """
    if not stat or is_solid(stat):
        return None
    days = slept_on(stat)
    if days < STUCK_DAYS:
        return None
    confused = stat.get("confused") or {}
    if isinstance(confused, str):
        try:
            confused = json.loads(confused)
        except ValueError:
            confused = {}
    worst = sorted(confused.items(), key=lambda kv: -kv[1])[:2]
    return {"days": days, "heard_as": [w[0] for w in worst],
            "rate": recent_rate(stat)}


def paces(progress, chars=None):
    """Every character with something to say about its pace, quickest first.

    The quickest is the one worth showing: it is the proof, and somebody
    who has just been told they copied 60 per cent needs the sentence that
    says the rest of it is arriving.
    """
    out = []
    for ch in (chars or list(progress or {})):
        got = pace((progress or {}).get(ch))
        if got and got["faster"]:
            out.append(dict(got, ch=ch))
    out.sort(key=lambda p: -p["by"])
    return out


def draw(chars, new, weak, progress=None):
    """How often each character in a drill should come up, as shares that
    sum to one. `new` is the character(s) not yet met, `weak` the met ones
    not yet solid, worst first, as plan() gives them; `progress` is the
    record, for how weak each one is."""
    chars = list(chars)
    if not chars:
        return {}
    progress = progress or {}
    shaky = {w["ch"] for w in weak}
    weights = {}
    for c in chars:
        if c in new:
            weights[c] = WEIGHT_NEW
        elif c in shaky:
            rate = recent_rate(progress.get(c))
            rate = 0.0 if rate is None else rate
            weights[c] = WEIGHT_KNOWN + WEIGHT_WEAK_SPAN * (1.0 - rate)
        else:
            weights[c] = WEIGHT_KNOWN
    total = sum(weights.values())
    return {c: round(w / total, 4) for c, w in weights.items()}


def plan(progress, setting=None):
    """Where a person is on the Koch order, from their record, and what to
    do next - the one decision the method rests on, made by the record
    rather than by a slider.

    The lesson is two characters plus every character in order that is
    solid; the next character in the order is the new one. A slider set
    higher is honored - a person may push on - but the plan says if the
    record does not back it. `weak` is every met character not yet solid,
    worst first, with what it was heard as."""
    progress = progress or {}
    leading = 0
    for ch in KOCH_ORDER:
        if is_solid(progress.get(ch)):
            leading += 1
        else:
            break
    # What has been met stays in the lesson. This used to be the leading
    # run of solid characters plus one, which took characters away: with
    # eight met and the third of them slipping, the lesson fell back to
    # three and five earned characters vanished - the two that were shaky
    # among them, which were the two that most needed drilling. The set is
    # every character met so far, and one more only when all of them are
    # solid. Nothing is ever taken away; not advancing is the whole of the
    # message.
    met = 0
    for ch in KOCH_ORDER:
        if (progress.get(ch) or {}).get("sent"):
            met += 1
        else:
            break
    all_solid = met > 0 and all(is_solid(progress.get(c)) for c in KOCH_ORDER[:met])
    earned = max(2, min(len(KOCH_ORDER), met + 1 if all_solid else met))
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
            "weak": weak, "words": len(words), "solid": leading, "total": len(KOCH_ORDER), "done": done,
            "draw": draw(chars, new, weak, progress),
            # The ones heard without their shape now, and the ones still
            # drawn - said plainly so the page does not have to work it
            # out twice and the day's note can say what came down.
            "weaned": [c for c in chars if weaned(progress.get(c))],
            "drawn": [c for c in chars if not weaned(progress.get(c))],
            # The characters that have been named cold at least once - the
            # baseline as it stands, built a character at a time. A learner
            # on their first day has none of these and that is the honest
            # answer; by the end of it they have one, and it is the landmark
            # everything about that character is read against afterwards.
            "learned": [c for c in chars if learned(progress.get(c))]}


# ------------------------------------------------------------------- how long
#
# Everything above decides *what* to practice. Nothing decided how long, and
# the docstring on session() used to say fifteen minutes while the code said
# nothing at all: three or four parts, and then a button offering another
# three or four. An open loop. An open loop with two characters in it is the
# same two characters for as long as a person can stand them, and what is
# learned in the eleventh minute of K and M is not K and M - it is that this
# is a thing to be endured.
#
# So the clock is set from the material there is to hold. Two characters is
# three minutes: long enough to get measurably quicker at them, short enough
# to leave somebody wanting the next go rather than relieved it is over.
# Length is earned as there is something longer to hold - more characters,
# then words, then a contact. Nothing bars a second session; what changes is
# that there is now a bottom to reach, and a top.
SESSION_LEAST = 180            # three minutes, at the two the order starts with
SESSION_MOST = 360             # six, with the whole order solid - see DAY_TARGET
SESSION_PER_CHAR = 7           # each character earned buys this much more

# A day, and why a session is only ever a piece of one.
#
# Fifteen minutes a day beats two hours on Sunday, and the arithmetic of that
# is the whole point: fifteen minutes is five passes of three, not one block
# of fifteen. What is learned is learned in the coming back - the character
# has to be fetched again from cold, after the mind has been somewhere else,
# and that fetch is the rep that counts. It is the same trick as using a new
# acquaintance's name three times in one conversation, spaced out, rather than
# fifteen times in a row.
#
# So the session grows with the material and stops growing early. A learner
# holding the whole order has more to hold and gets six minutes rather than
# three; what they do not get is a quarter of an hour in one sitting, because
# that is the shape the line above exists to argue against. The day is the
# lesson; a session is one pass through it; and the gaps between passes are
# meant to be spent somewhere else in this program - a hole of golf, which is
# exam questions wearing a better hat, or the band conditions, which is the
# argument for going and getting on the air.
DAY_TARGET = 900               # fifteen minutes, the frame the standing line sets
PASSES_FEWEST = 3
PASSES_MOST = 6


def passes(the_plan):
    """How many passes of this length a quarter of an hour comes to.

    The quotient of the day and the session, held between three and six. At
    two characters that is five passes of three minutes; holding the order it
    is three of six. Either way it is a quarter of an hour, and either way it
    is not one sitting.

    It is an illustration and not an assignment, and the page says so: the
    number is the reason the sessions are short, not a quota to be met. What
    a person's day holds is theirs to decide - somebody sitting an exam in
    three weeks and somebody learning the code for the pleasure of it are
    both using this correctly - so nothing counts down toward this figure
    and nothing is ever reported as outstanding. It survives here because
    the carry window needs a length; see :func:`set_state`.
    """
    each = budget(the_plan)
    return max(PASSES_FEWEST, min(PASSES_MOST, int(round(DAY_TARGET / float(each)))))

# What the parts cost, for fitting them to the clock.
MEET_SECONDS = 45              # hearing a new character a few times
GROUP_SECONDS = 14             # one group of five, sent and copied
WORD_SECONDS = 12              # a word sent, and the time taken to write it down
QSO_SECONDS = 120              # a short contact, copied
LAP_SECONDS = 40               # the last part, and the reason for it: see below

# How the middle of a session is split once the fixed parts are paid for.
SHARE_FLASH = 0.5
SHARE_GROUPS = 0.3             # the rest goes to words, where there are words


def budget(the_plan):
    """How many seconds today's session runs for, from what there is to do.

    Short at the start and longer later, which is the whole of it: a learner
    with two characters has three minutes of material and a learner holding
    the order has a quarter of an hour of it.
    """
    the_plan = the_plan or {}
    if the_plan.get("done"):
        return SESSION_MOST
    earned = max(2, int(the_plan.get("earned") or 2))
    return int(max(SESSION_LEAST,
                   min(SESSION_MOST, SESSION_LEAST + SESSION_PER_CHAR * (earned - 2))))


# When to stop, and who says so.
#
# A learner whose answers are getting slower has stopped learning and
# started grinding, and the session after this one is the one that does not
# happen. Dog training and bedside teaching say the same thing about this
# moment and say it plainly: it is a signal to come back at a better time,
# not a wall to push through. The clock is already kept per answer, so the
# program can see it from the inside and say so first, rather than waiting
# to be told by somebody who has already decided the whole thing is a slog.
FLAG_SLOWER = 0.30             # this much slower than the session's own best
FLAG_WINDOW = 5                # answers to a stretch
FLAG_ENOUGH = 15               # answers before the question may be asked


def flagging(times):
    """Whether this session has gone past its useful end.

    `times` is this session's reaction times in order, in milliseconds. The
    reading compares the last stretch against the best stretch earlier in
    the same session - the person's own best today, not anybody else's - so
    a slow day is not read as a decline and a good day is not cut short.

    None while there is not enough to say it honestly.
    """
    times = [float(t) for t in (times or []) if t]
    if len(times) < FLAG_ENOUGH:
        return None
    now = sum(times[-FLAG_WINDOW:]) / FLAG_WINDOW
    earlier = times[:-FLAG_WINDOW]
    stretches = [sum(earlier[i:i + FLAG_WINDOW]) / FLAG_WINDOW
                 for i in range(len(earlier) - FLAG_WINDOW + 1)]
    if not stretches:
        return None
    best = min(stretches)
    slower = (now - best) / best if best else 0.0
    return {"best_s": round(best / 1000.0, 1), "now_s": round(now / 1000.0, 1),
            "by": abs(round(slower * 100)), "stop": slower >= FLAG_SLOWER}


def wins(progress, the_plan, was=None):
    """What moved, in words, loudest first - the card at the end of a sitting.

    The order is the point, and it is not the order a scoreboard would pick.
    The biggest noise is made over gross replication: a character named cold
    for the first time, from a standing start, however roughly. That is the
    rep that says the expectation is achievable, and it is the one that sends
    somebody back for more. Reliability comes second, quieter. The refined
    state - a character already learned getting a little quicker - comes last
    and stays small, and only two of them are ever shown.

    Weighting it this way round looks upside down next to a leaderboard, and
    it is deliberate: a reward that keeps arriving for the polished thing
    teaches somebody to perform for the reward, and then the reward is the
    subject. Make the fuss when the thing is first done, and taper.

    `was` is the plan as it stood before the sitting, for the things that can
    only be seen as a change. An empty list is a real answer and is not
    padded.
    """
    the_plan, was = the_plan or {}, was or {}
    loud, middle, quiet = [], [], []

    # Loudest: learned cold for the first time. Once per character, ever.
    fresh = [c for c in (the_plan.get("learned") or []) if c not in (was.get("learned") or [])]
    for ch in fresh[:3]:
        got = cold_rate(progress.get(ch))
        loud.append(f"<b>{ch} is yours</b> - you named it cold, first time it came "
                    f"round, with nothing warmed up in front of it"
                    + (". That is the one that counts" if got is None or got >= 0.99 else ""))

    # Still loud, because it is an event and not a polish: the order moving
    # on. It only happens when everything behind it is solid, so it is the
    # record saying the earlier characters are genuinely held.
    if was.get("earned") and the_plan.get("earned", 0) > was["earned"]:
        loud.append("a new character opened up, which is the order saying the "
                    "ones behind it are yours")

    # Then the scaffolding coming away: heard by ear, with nothing drawn. An
    # event too, once per character, and quieter than first naming it because
    # by now the character is known - this is the refinement of how it is
    # known, not whether.
    # Only for characters that are actually holding. A letter met on five
    # separate days and still missed half the time has survived nothing, and
    # congratulating it in the same breath as saying it will not settle is the
    # program talking over itself.
    def holding(ch):
        return (held_overnight(progress.get(ch))
                and not stuck(progress.get(ch))
                and (recent_rate(progress.get(ch)) or 0) >= WEAN_FLOOR)

    kept = [c for c in (the_plan.get("chars") or [])
            if holding(c) and not held_overnight((was.get("progress") or {}).get(c))]
    if not kept:
        # Without a before to compare, say it for anything that has just
        # earned its second day - the record carries the days, so this is a
        # fact about the character and not a guess about the session.
        kept = [c for c in (the_plan.get("chars") or [])
                if slept_on(progress.get(c)) == 2 and holding(c)][:3]
    if kept:
        loud.append("<b>" + ", ".join(kept[:3]) + "</b> "
                    + ("were" if len(kept[:3]) > 1 else "was")
                    + " still there after a night's sleep. That is the part that "
                    + "sticks - hearing it today proves the ear works, having it "
                    + "tomorrow is the learning")

    fresh_ear = [c for c in (the_plan.get("weaned") or []) if c not in (was.get("weaned") or [])]
    if fresh_ear:
        middle.append("<b>" + ", ".join(fresh_ear) + "</b> "
                      + ("are" if len(fresh_ear) > 1 else "is")
                      + " heard without the shape drawn now - by ear, not by counting")

    # Then reliability: the first rep of a sitting landing, not just landing
    # eventually. Said as a count rather than a percentage - four of the last
    # five is a thing somebody can picture.
    for ch in (the_plan.get("learned") or []):
        if ch in fresh:
            continue
        cold = str((progress.get(ch) or {}).get("cold") or "")
        if len(cold) >= 4 and cold[-5:].count("1") >= 4 and "0" in cold[:-5]:
            middle.append(f"<b>{ch}</b> lands cold now - {cold[-5:].count('1')} of the "
                          f"last {len(cold[-5:])} first-of-the-day tries, where it "
                          f"used to be hit and miss")

    # Quietest, and rationed: the refined state. Read off the cold rep, so it
    # is days of practice speaking and not the tail of one warm drill.
    for ch in (the_plan.get("chars") or []):
        got = cold_pace(progress.get(ch))
        if got and got["faster"]:
            quiet.append((got["by"], f"{ch} cold: {got['first_s']} s when you learned it, "
                                     f"{got['now_s']} s now"))
    quiet.sort(reverse=True)
    out = loud + middle + [line for _, line in quiet[:2]]
    for ch in (the_plan.get("chars") or []):
        got = stuck(progress.get(ch))
        if got:
            heard = got["heard_as"]
            out.append(
                f"<b>{ch}</b> has been coming round for {got['days']} days and has not "
                + ("settled yet" if not heard else
                   "settled yet - it is being heard as " + " or ".join(heard))
                + ". That is normal and it is not a verdict on you: some characters "
                  "take a week. What shifts it is hearing the pair against each "
                  "other rather than more of the same one")
            break
    return out


def baseline_words(the_plan, was=None):
    """What a learner has a baseline on, for the card when nothing else moved.

    A first session has no before and cannot have one, and saying "too early
    to show you anything" is both true and the wrong thing to say to somebody
    who has just done the work. What they have is the start of the mark: the
    characters they can name cold. That is worth naming, because it is the
    thing the rest will be measured against.
    """
    the_plan = the_plan or {}
    got = the_plan.get("learned") or []
    met = the_plan.get("chars") or []
    if not got:
        return ("No mark to measure against yet - it gets set the first time you "
                "name a character cold, before any warming up. That is what the "
                "next sitting is for.")
    return ("You can name <b>" + ", ".join(got) + "</b> cold"
            + (f", which is {len(got)} of the {len(met)} in front of you" if len(met) > len(got) else "")
            + ". That is the mark everything else gets read against.")


# A set of passes does not expire at midnight.
#
# Five passes is what a day comes to, not a quota to be met before a clock
# runs out. Somebody who got three of them in before the evening went sideways
# has done three passes of a five-pass set, and the honest thing tomorrow is
# to offer them the last two - not to wipe it and start again, which would be
# the program punishing them for having a life. The whole argument for this
# shape is that it fits into the gaps in a day; a version of it that only
# works on a clear day is not the same claim.
#
# So a set carries. It stays open for CARRY_DAYS after the day it was opened,
# and a pass finished inside that window goes on the same set. Past that it is
# a new set, because a set that never closes is not a set either.
CARRY_DAYS = 1


def _as_date(text):
    from datetime import date as _date
    try:
        y, m, d = (int(x) for x in str(text).split("-"))
        return _date(y, m, d)
    except (TypeError, ValueError):
        return None


def set_state(saved, today, target):
    """The set of passes in progress: what is done, and what is left.

    `saved` is what was last written down - {"opened", "last", "passes",
    "target"} - and `today` is the date now. Returns the set as it stands,
    with `carried` true when it was opened on an earlier day and is still
    being worked through.

    Both dates are kept, and both are needed: `opened` says how long the set
    has been open, and `last` says when it was last touched. Without `last`, a
    set finished on the carry day read as a brand-new empty one the moment it
    was completed, because the only question being asked was whether it had
    opened today.
    """
    target = max(1, int(target or 1))
    fresh = {"opened": today.isoformat(), "passes": 0, "target": target,
             "left": target, "carried": False, "complete": False}
    saved = saved or {}
    opened = _as_date(saved.get("opened"))
    last = _as_date(saved.get("last")) or opened
    done = int(saved.get("passes") or 0)
    if opened is None or done <= 0:
        return fresh
    want = int(saved.get("target") or target)
    state = {"opened": saved.get("opened"), "last": saved.get("last"),
             "passes": done, "target": want, "left": max(0, want - done),
             "carried": opened != today, "complete": done >= want}
    if done >= want:
        # Finished. It stands for the rest of the day it was finished on, and
        # after that the next pass opens a new one.
        return state if last == today else fresh
    if (today - opened).days > CARRY_DAYS:
        return fresh                       # too long ago to still be the same set
    return state


def add_pass(saved, today, target):
    """One finished pass folded into the set, and the set that comes of it."""
    state = set_state(saved, today, target)
    if state["complete"]:
        # Complete already, and somebody has gone again: a new set opens,
        # because more is welcome and none of it is required.
        state = {"opened": today.isoformat(), "passes": 0,
                 "target": max(1, int(target or 1))}
    return {"opened": state["opened"], "last": today.isoformat(),
            "passes": int(state["passes"]) + 1,
            "target": int(state.get("target") or target)}


def session(the_plan, seconds=None):
    """Today's session, in order and to a clock: meet what is new, drill one
    character at a time, copy groups, then words once there are any - and
    finish on something already known.

    The length comes from :func:`budget` unless a caller names one, and the
    parts are cut to fit it rather than being a fixed list that runs for as
    long as it runs.
    """
    total = int(seconds if seconds is not None else budget(the_plan))
    steps = []
    if the_plan["done"]:
        # With the order held, the session is mostly listening, and it ends
        # on a contact rather than on a drill: at this point the reward for
        # knowing the code is using it.
        contacts = max(1, min(4, int(total * 0.55 / QSO_SECONDS)))
        count = max(6, int(round((total - contacts * QSO_SECONDS) / WORD_SECONDS)))
        steps.append({"kind": "words", "count": count, "seconds": count * WORD_SECONDS,
                      "why": "every character is solid - the rest is speed, and words are how it comes"})
        steps.append({"kind": "qso", "count": contacts, "seconds": contacts * QSO_SECONDS,
                      "why": ("contacts, as they would be sent" if contacts > 1
                              else "a contact, as it would be sent")})
        return steps
    left = total
    # The last part is paid for first: a session ends on something that goes
    # right. A trainer finishes on a command the animal has cold, and a
    # teacher finishes on the thing the student can already do, for the same
    # reason - the last minute is the one that is remembered, and what it
    # should say is "I can do this", not "I could not do that".
    known = [c for c in the_plan["chars"]
             if c not in the_plan["new"] and c not in [w["ch"] for w in the_plan["weak"]]]
    if known:
        left -= LAP_SECONDS
    if the_plan["new"]:
        steps.append({"kind": "meet", "chars": the_plan["new"], "seconds": MEET_SECONDS,
                      "why": "new: hear it, see it drawn, hear it again - the sound first, the name second"})
        left -= MEET_SECONDS
    # The shape coming down is said out loud. A screen that quietly stops
    # drawing the dits looks broken to the person it is helping, and the
    # reason is worth hearing anyway: it is the point of the whole drill.
    weak = [w["ch"] for w in the_plan["weak"][:3]]
    down = (the_plan.get("weaned") or [])[:6]
    why = "one character at a time, answer as it comes - the reflex, not the recall"
    if weak:
        why += "; " + ", ".join(weak) + (" come" if len(weak) > 1 else " comes") + " round more often"
    if down:
        why += ("; " + ", ".join(down)
                + (" are heard without the shape drawn now - you have them by ear"
                   if len(down) > 1 else
                   " is heard without the shape drawn now - you have it by ear"))
    # The middle, cut to whatever the clock has left. With words in it the
    # shares are flash, groups and words; without, the two share it out.
    left = max(GROUP_SECONDS * 2, left)
    has_words = the_plan["words"] >= 8
    flash_share = SHARE_FLASH if has_words else SHARE_FLASH / (SHARE_FLASH + SHARE_GROUPS)
    group_share = SHARE_GROUPS if has_words else 1.0 - flash_share
    steps.append({"kind": "flash", "seconds": max(30, int(round(left * flash_share))), "why": why})
    groups = max(2, int(round(left * group_share / GROUP_SECONDS)))
    steps.append({"kind": "koch", "count": groups, "seconds": groups * GROUP_SECONDS,
                  "why": f"{groups} groups of five at speed - copy behind, write what you heard"})
    if has_words:
        count = max(3, int(round(left * (1.0 - flash_share - group_share) / WORD_SECONDS)))
        steps.append({"kind": "words", "count": count, "seconds": count * WORD_SECONDS,
                      "why": "words from the characters you have - the sound of the code as it is used"})
    if known:
        # Only what is already known, and said so: the point is that it goes
        # right, not that it is tested.
        steps.append({"kind": "flash", "seconds": LAP_SECONDS, "only": known, "lap": True,
                      "why": "a lap on the ones you already have - this part is not a test, "
                             "it is where the session ends because it goes right"})
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
    being learned and a full stop and a hyphen are a poor way to show a sound.
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


# ------------------------------------------------------- the qualifying run
#
# The old code tests sent five minutes of plain language and asked for one
# minute of it perfectly - and that is still the right shape, because it is
# honest about how copying actually goes. Nobody copies a hundred per cent for
# five minutes. What a proficient operator does is settle: the first half
# minute is a scramble, then the ear catches the rhythm and a clean stretch
# comes out of it. Asking for one contiguous minute out of five measures that
# settling rather than punishing the scramble.
#
# What is different here is that the operator names the speed. The program
# does not decide what they can do; it gives them the run they asked for and
# then tells them the truth about it, which is a different relationship.
#
# It ends the moment the clean minute lands. Making somebody sit through four
# more minutes after they have already proved the thing is the program
# collecting evidence for its own sake.
QUALIFY_SECONDS = 300          # five minutes of sending, at most
QUALIFY_CLEAN = 60             # one contiguous minute of it, without a miss
# Not a shape invented here. Chuck Adams, K7QO - whose own 140.9 words a minute
# is the figure everybody quotes - describes the standard for code tests and
# world records as "copying one minute without error out of five minutes of
# plain text". He also says the 140.9 is misleading when it is repeated as a
# plain-text speed, because it came from RufzXP, which sends single callsigns
# and nothing else. Both are worth having right: see QUALIFY_SOURCE.
QUALIFY_SOURCE = "https://www.arrl.org/news/morse-code-at-140-wpm"
QUALIFY_SOURCE_NAME = "ARRL: Morse Code at 140 WPM"
QUALIFY_LEAST_WPM = 5
QUALIFY_MOST_WPM = 40


def qualifying_text(wpm, seconds=QUALIFY_SECONDS, seed=None):
    """Plain language to copy, enough to fill the run at this speed.

    Words rather than random groups: a qualifying run is about copying the
    language, and a word half-heard is often still recoverable, which is the
    skill. The whole character set is in play - this is the one drill that is
    not confined to the lesson, because its whole job is to find out what the
    operator already has.
    """
    rng = random.Random(seed)
    # PARIS: a word is five characters, so characters a minute is five times
    # the speed, and the run needs that many for as long as it runs.
    want = int(max(1, float(wpm)) * 5 * float(seconds) / 60.0)
    # Plain words alone leave fourteen of the forty characters unsent - every
    # digit, the punctuation, and Q, Z, X and J, which are exactly the ones
    # somebody proficient would most like credit for. A run built only of
    # common English cannot place anybody past the easy half of the order.
    # So it is sent the way real traffic is: words, callsigns, signal reports
    # and Q-signals, which between them use the whole set.
    # And weighted so the rare ones actually get an airing. A character only
    # counts toward placement if it was sent often enough to be sure of, so a
    # run made of ordinary English stalls the whole order at the first comma:
    # measured across a dozen runs, a flawless copyist landed anywhere between
    # twelve and thirty-three of the forty, on nothing but which words came up.
    # Traffic is where digits and punctuation live anyway - reports, serials,
    # portable callsigns - so leaning on it is truer to the air, not less.
    out, size = [], 0
    while size < want:
        roll = rng.random()
        if roll < 0.40:
            piece = rng.choice(WORDS)
        elif roll < 0.62:
            piece = _callsign(rng, dx=rng.random() < 0.3)
            if rng.random() < 0.22:
                # Portable and mobile, which is where the slant comes from and
                # the only place most operators ever hear one.
                piece += "/" + rng.choice(["P", "M", "QRP", "3", "7"])
        elif roll < 0.72:
            piece = rng.choice(list(Q_SIGNALS))
        elif roll < 0.88:
            # Serials and reports, which is where the digits live. All ten of
            # them, not just the five a signal report uses.
            piece = "".join(str(rng.randint(0, 9)) for _ in range(rng.randint(3, 5)))
        else:
            piece = rng.choice(["73", "88", "5NN", "OM", "UR", "TU", "AGN?",
                                "WX FB", "HW?", "RIG 100W", "ANT 40M DIPOLE",
                                # The stop and the comma get sent too: they are
                                # in the order, and a run that never sends them
                                # cannot give anybody credit for knowing them.
                                "NAME BOB, QTH OHIO.", "TNX FER CALL, 73.",
                                "SRI QRM, PSE AGN."])
        out.append(piece)
        size += len(piece) + 1
    return " ".join(out)


# How far out of step a copyist is allowed to get before the alignment stops
# looking. Somebody copying behind runs a character or two late; somebody who
# loses the thread entirely is not going to be recovered by a wider band, and
# the band is what keeps this fast.
ALIGN_BAND = 48


def _align(sent, got):
    """Line up what was typed against what was sent, character by character.

    A proper alignment, and it has to be: difflib takes the longest matching
    block it can find and recurses either side of it, which is the wrong
    instinct here. There are forty characters in the code and five hundred
    positions in a run, so identical short runs are everywhere, and it will
    happily match a "TH" near the start against a "TH" near the end and then
    throw away everything in between. On a real run that scored a copyist at
    thirteen per cent who had two thirds of it.

    So: edit distance with a traceback, banded to ALIGN_BAND either side of
    the diagonal. Banding keeps it quick and costs nothing real - a copyist
    fifty characters out of step has not mistyped, they have stopped copying.

    Returns (ok, typed_for), both the length of `sent`.
    """
    n, m = len(sent), len(got)
    if not n:
        return [], []
    if not m:
        return [False] * n, [""] * n
    big = float("inf")
    # cost[i][j] as two rolling rows, with the band clamped into range.
    prev = [big] * (m + 1)
    for j in range(0, min(m, ALIGN_BAND) + 1):
        prev[j] = j
    back = []                                # one row of moves per sent character
    for i in range(1, n + 1):
        row = [big] * (m + 1)
        lo, hi = max(0, i - ALIGN_BAND), min(m, i + ALIGN_BAND)
        moves = {}
        if lo == 0:
            row[0] = i
            moves[0] = "up"
        for j in range(max(1, lo), hi + 1):
            same = sent[i - 1] == got[j - 1]
            best, how = prev[j - 1] + (0 if same else 1), ("hit" if same else "sub")
            if prev[j] + 1 < best:
                best, how = prev[j] + 1, "up"        # sent, never typed
            if row[j - 1] + 1 < best:
                best, how = row[j - 1] + 1, "left"   # typed, never sent
            row[j], moves[j] = best, how
        back.append(moves)
        prev = row
    ok, typed_for = [False] * n, [""] * n
    i, j = n, m
    while i > 0:
        how = back[i - 1].get(j)
        if how is None:                      # outside the band: the rest is a miss
            i -= 1
            continue
        if how == "left":
            j -= 1
            continue
        if how in ("hit", "sub"):
            if how == "hit":
                ok[i - 1] = True
            typed_for[i - 1] = got[j - 1] if j > 0 else ""
            i, j = i - 1, j - 1
            continue
        i -= 1                               # "up": sent and nothing typed for it
    return ok, typed_for


def run_marks(text, typed, wpm):
    """A run scored: one mark a character sent, with when it went out.

    Two things have to be right or the clean minute is a lottery.

    The first is when each character was sent, and that is not guessed - it is
    computed from the code itself at this speed. The word PARIS is five words
    a minute because of exactly this arithmetic, so the schedule the sender
    used is the schedule the scorer uses.

    The second is lining up what was typed against what was sent. Somebody who
    drops one character and carries on is a character behind for the rest of
    the run; scored position by position that reads as everything after the
    slip being wrong, and it would take a clean minute away from an operator
    who had one. So the two are aligned as sequences - the same way a diff
    lines up two versions of a file - and only the genuinely unmatched
    characters count as missed.
    """
    beat = timing(wpm)
    sent = [c for c in str(text or "").upper()]
    got = [c for c in str(typed or "").upper()]
    # When each character finished going out, from the start of the run.
    at, when = 0.0, []
    for ch in sent:
        if ch == " ":
            at += beat["word_gap"]
            when.append(at)
            continue
        code = MORSE.get(ch, "")
        span = sum(beat["dah"] if sym == "-" else beat["dit"] for sym in code)
        span += beat["symbol_gap"] * max(0, len(code) - 1)
        at += span + beat["char_gap"]
        when.append(at)
    ok, typed_for = _align(sent, got)
    marks = []
    for i, ch in enumerate(sent):
        if ch == " ":
            continue                        # the gaps are not characters to copy
        marks.append({"ch": ch, "ok": ok[i], "at": round(when[i] / 1000.0, 2),
                      "typed": typed_for[i]})
    return marks


def clean_stretch(marks, need=QUALIFY_CLEAN):
    """The longest run of unbroken copy, in seconds, and whether it is enough.

    `marks` is the run as it happened: one entry a character, each
    {"ok": bool, "at": seconds from the start}. A stretch is measured from the
    first character after the last miss to the most recent one - so a miss
    ends a stretch and starts the next, which is what "contiguous" means.
    """
    best, start = 0.0, None
    for mark in marks or []:
        at = float(mark.get("at") or 0.0)
        if not mark.get("ok"):
            start = None
            continue
        if start is None:
            start = at
        best = max(best, at - start)
    return {"seconds": round(best, 1), "passed": best >= need, "need": need}


def qualify_advice(wpm, marks, passed):
    """What to say at the end, and it is never "you failed".

    Somebody who asked for twenty-five and copied two thirds of it does not
    need to be told they were wrong about themselves; they need the speed that
    would have worked, which the run has just measured. Somebody who copied
    almost none of it is not slow, they are early - and the honest and kindest
    thing is to say the code is learnable and point at where it starts.
    """
    marks = list(marks or [])
    hits = sum(1 for m in marks if m.get("ok"))
    rate = hits / len(marks) if marks else 0.0
    wpm = float(wpm)
    if passed:
        return {"rate": round(rate, 3), "suggest_wpm": None,
                "head": "That is a qualifying run.",
                "words": (f"A clean minute at {wpm:.0f} words a minute, which is the "
                          "same thing the old code tests asked for. Whatever the record "
                          "said about you before, it says this now.")}
    if not marks:
        return {"rate": 0.0, "suggest_wpm": QUALIFY_LEAST_WPM,
                "head": "Nothing came through.",
                "words": ("No characters were copied at all, so there is nothing to "
                          "measure yet. That is a fine place to be - it is where "
                          "everybody starts, and the code is learnable in about a month "
                          "of short days.")}
    if rate < 0.35:
        return {"rate": round(rate, 3), "suggest_wpm": None, "start_here": True,
                "head": "This one is not the place to start.",
                "words": (f"About {rate * 100:.0f} per cent came through, which means the "
                          "characters are not there yet rather than the speed being wrong "
                          "- and no speed fixes that. Start with the lesson: two characters "
                          "at a time, a few minutes a day, and the rest arrive on their own. "
                          "People who could not copy a single letter in January are holding "
                          "conversations by the spring.")}
    # They can copy; the speed was ambitious. What they actually held is the
    # number worth giving them, rounded down to something they can ask for.
    suggest = max(QUALIFY_LEAST_WPM, int(wpm * min(0.9, max(0.5, rate))))
    if suggest >= wpm:
        suggest = max(QUALIFY_LEAST_WPM, int(wpm) - 2)
    return {"rate": round(rate, 3), "suggest_wpm": suggest,
            "head": f"Close. {rate * 100:.0f} per cent of it came through.",
            "words": (f"That is real copying, at a speed that was reaching. Try it again "
                      f"at {suggest} and it will very likely land - and a qualifying run at "
                      f"{suggest} is worth more than a near miss at {wpm:.0f}, because the "
                      "speed comes back quickly once the copy is solid.")}


# ------------------------------------------------------------- what lives where
#
# A speed on a slider is a number. What makes it mean anything is knowing who
# is up there and what they are doing, so the ladder is written down once and
# read wherever a speed is being chosen or measured - the qualifying run's
# setup, the rating, the breaks between passes.
#
# The two records at the top are reported rather than asserted, and they are
# named so anybody can go and check: this program has no way to verify a world
# record and should not sound as though it does.
SPEED_LADDER = [
    {"from": 0, "to": 7, "name": "where everybody starts",
     "note": "Every character is sent at full speed from the first day; what is "
             "slowed is the gap between them. Nobody learns the code slowly and "
             "then speeds it up - that has to be unlearned."},
    {"from": 8, "to": 14, "name": "the old code tests",
     "note": "Five words a minute was Novice, thirteen was General, twenty was "
             "Extra. The tests are gone, and the speeds are still where most "
             "conversations live."},
    {"from": 15, "to": 24, "name": "ragchewing",
     "note": "A comfortable conversational speed for most operators on the air. "
             "Somewhere around here the ear stops assembling letters and starts "
             "hearing whole words - which is the change worth waiting for."},
    {"from": 25, "to": 39, "name": "fluid sending, and head copy",
     "note": "Characters run together and stop being separate things. "
             "Experienced operators copy a whole conversation in their heads at "
             "thirty to forty-five, writing nothing down."},
    {"from": 40, "to": 59, "name": "contest speed",
     "note": "Callsigns and reports in rapid-fire bursts, usually with a keyer "
             "driven from logging software. Human hands on paddles can burst "
             "into the fifties; holding it is another matter."},
    {"from": 60, "to": 99, "name": "high-speed telegraphy",
     "note": "Sixty to eighty and beyond, copied continuously - at rates that "
             "rival or beat ordinary typing. Sending this fast is machine work: "
             "past about seventy it is software, for spacing no hand can hold. "
             "There is a world championship for it, run by the IARU.",
     "source": "https://www.iaru-r1.org/2024/20th-iaru-hst-world-championship-tunisia-2024/",
     "source_name": "IARU: 20th HST World Championship, Tunisia 2024"},
    {"from": 100, "to": 999, "name": "the far end of it",
     "note": "The callsign record is held by Ianis Scutaru, YO8YNS, who took "
             "RufzXP to 311,192 points at 1,126 characters a minute - about 225 "
             "words a minute - at the IARU world championship in Tunisia in "
             "2024. Single callsigns, not prose, and a program that speeds up "
             "every time you are right. Worth knowing about; not a target.",
     "source": "http://www.highspeedtelegraphy.com/Telegraphy-world-records/World-record-Rufz",
     "source_name": "HST: RufzXP world records"},
]


def speed_note(wpm):
    """Where this speed sits, and what is done at it."""
    try:
        wpm = float(wpm)
    except (TypeError, ValueError):
        return SPEED_LADDER[0]
    for rung in SPEED_LADDER:
        if wpm <= rung["to"]:
            return rung
    return SPEED_LADDER[-1]


def speed_above(wpm):
    """The next rung up, for somebody who has just reached this one."""
    here = speed_note(wpm)
    for rung in SPEED_LADDER:
        if rung["from"] > here["to"]:
            return rung
    return None
