"""Spoken words, pieced together: the golf narrator from recorded snippets.

The way an ATIS says the weather - "wind, two, seven, zero, at, one, five" -
from a shelf of recorded words, the narrator says the round from a shelf of
recorded snippets: numbers that are reused, and phrases that are fixed. The
game composes a line as a list of *tokens*; each token is the stem of a
sound file in static/golf/voice/ (three.mp3, hundred.mp3, addresses-the-
ball.mp3); the screen plays them in order and is silent for any that is not
recorded yet. So the voice can be built up one snippet at a time, and a
unit with no recordings says nothing and works exactly as before.

Nothing here plays sound. It says which words, in which order, so a person
recording them and a page playing them agree - and so the composition can
be tested without a speaker in the room.

The script to record is VOCABULARY, one line a snippet: `python3
tools/voice_script.py` prints it, and docs/narration/voice-script.md is
that printout.
"""
import random
import re

# ------------------------------------------------------------- the words
# Every snippet the narrator can say, by the file stem it is recorded under,
# with the words to record. Names are the one open set: a regular's name is
# recorded as name-<slug>.mp3 (name-scott.mp3), and a name that is not on
# the shelf is said as "the player".

NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
    8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen",
    15: "fifteen", 16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
    30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy", 80: "eighty", 90: "ninety",
}
ORDINALS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth",
            "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth",
            "seventeenth", "eighteenth"]

# The phonetic alphabet, for a callsign nobody recorded a name for: KC9SP
# is Kilo Charlie nine Sierra Papa, which is how the operator says it too.
from . import cw as _cw

PHONETIC = {"a": "Alpha", "b": "Bravo", "c": "Charlie", "d": "Delta", "e": "Echo", "f": "Foxtrot",
            "g": "Golf", "h": "Hotel", "i": "India", "j": "Juliett", "k": "Kilo", "l": "Lima",
            "m": "Mike", "n": "November", "o": "Oscar", "p": "Papa", "q": "Quebec", "r": "Romeo",
            "s": "Sierra", "t": "Tango", "u": "Uniform", "v": "Victor", "w": "Whiskey", "x": "X-ray",
            "y": "Yankee", "z": "Zulu"}

VOCABULARY = {
    # numbers, reused everywhere: yards, feet, strokes, miles an hour
    **{w: w for w in NUMBER_WORDS.values()},
    "hundred": "hundred", "and": "and",
    # the letters, phonetic - a callsign spelled out when there is no name file
    **{f"phon-{k}": v for k, v in PHONETIC.items()},
    # the CW page says back what a key pressed: a prosign or a Q signal by
    # its meaning, so the sound of the code is coupled to what it means
    **{f"pro-{k.lower()}": f"{k} - {v[1]}" for k, v in _cw.PROSIGNS.items()},
    **{f"q-{k.lower()}": f"{k} - {v}" for k, v in _cw.Q_SIGNALS.items()},
    # the slots on the sheet: the narrator calls the golfer by their place
    # in the group rather than by name - "Player 2 is away" - which is what
    # a starter does, and needs no file per person. Honors on the tee.
    **{f"player-{n}-is-away": f"Player {n} is away" for n in (1, 2, 3, 4)},
    **{f"player-{n}-has-honors": f"Player {n} has honors" for n in (1, 2, 3, 4)},
    # single words, the pieces a phrase falls back to when the phrase is
    # not recorded: "hole, one, is, par, four" for "the first, par, four";
    # "rough", "bunker", "green" for "into the rough", "into the sand",
    # "on the green". Terse, the way an ATIS is, and better than silence.
    "hole": "hole", "is": "is", "rough": "rough", "bunker": "bunker", "green": "green",
    # What lies in the line at address, as a caddie says it: "Ahead, a
    # bunker at two hundred forty yards, on the right, in play." "Ahead,
    # the water beyond the green."
    "ahead": "Ahead,", "a-bunker": "a bunker", "the-water": "the water", "the-rough": "the rough",
    "at": "at", "on-the-left": "on the left", "on-the-right": "on the right",
    "across-the-fairway": "across the fairway", "beyond-the-green": "beyond the green",
    "in-play": "in play.", "out-of-reach": "out of reach.",
    # the holes
    **{f"the-{o}": f"the {o}" for o in ORDINALS},
    "par": "par", "yards": "yards", "feet": "feet", "to-go": "to go",
    "yards-to-go": "yards left to go",
    # the courses
    "pebble-beach": "Pebble Beach", "the-old-course": "the Old Course at Saint Andrews",
    "augusta-national": "Augusta National",
    # the wind
    "the-breeze-is-behind-you": "the breeze is behind you",
    "into-the-breeze": "into the breeze", "a-crosswind": "a crosswind",
    "the-wind-swirls-here": "the wind swirls here", "miles-an-hour": "miles an hour",
    # The wind, said the better way when these are recorded: "The wind is,
    # twelve miles per hour, from behind you." The pieces above are the
    # older reading and stand in until they are.
    "the-wind-is": "The wind is,", "from-behind-you": "from behind you.", "in-your-face": "in your face.",
    "across-the-hole": "across the hole.", "and-swirling": "and swirling.",
    # The wind by the clock, which is how a caddie and a pilot both say it:
    # twelve is straight down the hole, three off the right. Better than the
    # four phrases above because it is the fact the game now models - see
    # golf.wind_parts - rather than a bucket it was sorted into, and a
    # quartering wind has somewhere to be said.
    **{f"out-of-{w}-oclock": f"Out of {w} o'clock."
       for w in ("one", "two", "three", "four", "five", "six",
                 "seven", "eight", "nine", "ten", "eleven", "twelve")},
    # the address
    "the-player": "the player", "addresses-the-ball": "addresses the ball",
    "in-hand": "in hand",
    "the-driver": "the driver", "the-wood": "the wood", "the-iron": "the iron",
    "the-wedge": "the wedge", "the-putter": "the putter",
    "from-the-tee": "from the tee", "from-the-fairway": "from the fairway",
    "from-the-rough": "from the rough", "from-the-sand": "from the sand",
    "on-the-green": "on the green",
    "your-shot": "your shot",
    # the stroke in words
    "a-foul-ball": "a foul ball", "fairway": "fairway",
    "into-the-sand": "into the sand", "into-the-water": "into the water",
    "into-the-rough": "into the rough", "short-and-into-the-rough": "short, and into the rough",
    "through-the-green": "through the green, into the rough behind",
    "drop-and-a-penalty-stroke": "drop, and a penalty stroke",
    "putt-holed": "putt holed", "putt-missed": "putt missed",
    "in-the-hole": "in the hole", "an-ace": "an ace",
    "picked-up": "picked up",
    # the scores
    "for-an-albatross": "for an albatross", "for-an-eagle": "for an eagle",
    "for-a-birdie": "for a birdie", "for-par": "for par", "for-a-bogey": "for a bogey",
    "for-a-double-bogey": "for a double bogey", "for-a-triple-bogey": "for a triple bogey",
    "over-par": "over par",
    # the calls - one file each, the golfer's word at contact
    "call-fairway-1": "Pured it.", "call-fairway-2": "Right down the middle.", "call-fairway-3": "That'll play.",
    "call-fairway-4": "Nice shot!", "call-fairway-5": "On the fairway.",
    "call-rough-4": "In the rough.", "call-sand-4": "Found the bunker.",
    "call-water-4": "That's swimming.", "call-water-5": "Are you going after that?",
    "call-rough-5": "OOOPS! That's going to need patching.", "call-rough-6": "Are you new at this?",
    "call-water-6": "We all have bad days.", "call-holed-4": "It's in the cup!", "call-holed-5": "In the cup!",
    "call-holed-6": "THAT, ladies and gentlemen, is how it is done.",
    "call-sand-5": "That ball is on the beach.",
    "call-green-1": "On the dance floor.", "call-green-2": "Stuck it.", "call-green-3": "That's looking at it.",
    "call-fringe-1": "On the collar.", "call-fringe-2": "Just on the fringe.",
    "call-fringe-3": "The fringe took the pace off it.", "call-fringe-4": "Putt it from there.",
    "on-the-fringe": "on the fringe",
    "call-long-1": "Flew the green.", "call-long-2": "Too much club.", "call-long-3": "Airmailed it.",
    "call-holed-1": "In the hole!", "call-holed-2": "Drained it.", "call-holed-3": "Bottom of the cup.",
    "call-rough-1": "Topped it.", "call-rough-2": "Fat. Chunked it.", "call-rough-3": "Skied that one.",
    "call-sand-1": "Sliced it into the sand.", "call-sand-2": "Pulled it into the bunker.", "call-sand-3": "Beach.",
    "call-water-1": "Hooked it into the water.", "call-water-2": "Wet.", "call-water-3": "That's a splash - what was the wind?",
    "call-missed-1": "Lipped out.", "call-missed-2": "Left it short.", "call-missed-3": "Burned the edge.",
    "call-ace": "A hole in one!",
    # the shots worth making - earned by an adept answer
    "call-worked-1": "Worked it around the trees.", "call-worked-2": "Shaped it out of there.",
    "call-worked-3": "Hooked it on purpose, and it came back.",
    "call-stinger-1": "A stinger, under the wind.", "call-stinger-2": "Punched it. The wind never saw it.",
    "call-stinger-3": "Kept it low. That's the shot.",
    "call-flop-1": "Flopped it to a tap-in.", "call-flop-2": "Straight up, straight down. Kick-in.",
    "call-flop-3": "That's a touch shot.",
    # The skip. Nobody is offered this shot and the game never chooses it -
    # it falls out of arriving at water flat and fast - so it is said
    # loudly, or a ball coming out of the water reads as a fault. See
    # golf.SKIP_ANGLE.
    "call-skip-1": "Skipped it! That's still dry.",
    "call-skip-2": "It BOUNCED. Off the water, and out.",
    "call-skip-3": "Three skips and dry land. Nobody meant that.",
    "call-holed-out-1": "Holed it from the fairway!", "call-holed-out-2": "It's IN. From out there.",
    "call-holed-out-3": "Walked it in from the fairway.",
    "call-launched-1": "Launched it.", "call-launched-2": "That one's still going.", "call-launched-3": "Nuked it.",
    "call-pure-1": "Pured it. Stiff.", "call-pure-2": "All over the flag.", "call-pure-3": "Pin high, and close.",
    "holed-it-from-the-fairway": "holed it from the fairway", "flopped-it-to-a-tap-in": "flopped it, to a tap-in",
    # the card, and the round
    "thats-the-hole": "that's the hole", "on-to-the-next": "on to the next",
    "wins-the-round": "wins the round", "a-playoff": "a playoff, sudden death",
    "tee-time": "a tee time",
}

# The calls as the game phrases them (golf.CALLS), mapped to their files.
CALL_TOKENS = {
    "Pured it.": "call-fairway-1", "Right down the middle.": "call-fairway-2", "That'll play.": "call-fairway-3",
    "On the dance floor.": "call-green-1", "Stuck it.": "call-green-2", "That's looking at it.": "call-green-3",
    "On the collar.": "call-fringe-1", "Just on the fringe.": "call-fringe-2",
    "The fringe took the pace off it.": "call-fringe-3", "Putt it from there.": "call-fringe-4",
    "Flew the green.": "call-long-1", "Too much club.": "call-long-2", "Airmailed it.": "call-long-3",
    "In the hole!": "call-holed-1", "Drained it.": "call-holed-2", "Bottom of the cup.": "call-holed-3",
    "Topped it.": "call-rough-1", "Fat. Chunked it.": "call-rough-2", "Skied that one.": "call-rough-3",
    "Sliced it into the sand.": "call-sand-1", "Pulled it into the bunker.": "call-sand-2", "Beach.": "call-sand-3",
    "Hooked it into the water.": "call-water-1", "Wet.": "call-water-2",
    "That's a splash - what was the wind?": "call-water-3",
    "Nice shot!": "call-fairway-4", "On the fairway.": "call-fairway-5", "In the rough.": "call-rough-4",
    "Found the bunker.": "call-sand-4", "That's swimming.": "call-water-4", "Are you going after that?": "call-water-5",
    "OOOPS! That's going to need patching.": "call-rough-5", "Are you new at this?": "call-rough-6",
    "We all have bad days.": "call-water-6", "It's in the cup!": "call-holed-4", "In the cup!": "call-holed-5",
    "THAT, ladies and gentlemen, is how it is done.": "call-holed-6",
    "That ball is on the beach.": "call-sand-5",
    "Lipped out.": "call-missed-1", "Left it short.": "call-missed-2", "Burned the edge.": "call-missed-3",
    "A hole in one!": "call-ace",
    "Worked it around the trees.": "call-worked-1", "Shaped it out of there.": "call-worked-2",
    "Hooked it on purpose, and it came back.": "call-worked-3",
    "A stinger, under the wind.": "call-stinger-1", "Punched it. The wind never saw it.": "call-stinger-2",
    "Kept it low. That's the shot.": "call-stinger-3",
    "Flopped it to a tap-in.": "call-flop-1", "Straight up, straight down. Kick-in.": "call-flop-2",
    "That's a touch shot.": "call-flop-3",
    "Skipped it! That's still dry.": "call-skip-1",
    "It BOUNCED. Off the water, and out.": "call-skip-2",
    "Three skips and dry land. Nobody meant that.": "call-skip-3",
    "Holed it from the fairway!": "call-holed-out-1", "It's IN. From out there.": "call-holed-out-2",
    "Walked it in from the fairway.": "call-holed-out-3",
    "Launched it.": "call-launched-1", "That one's still going.": "call-launched-2", "Nuked it.": "call-launched-3",
    "Pured it. Stiff.": "call-pure-1", "All over the flag.": "call-pure-2", "Pin high, and close.": "call-pure-3",
}

SCORE_TOKENS = {"albatross": "for-an-albatross", "eagle": "for-an-eagle", "birdie": "for-a-birdie",
                "par": "for-par", "bogey": "for-a-bogey", "double bogey": "for-a-double-bogey",
                "triple bogey": "for-a-triple-bogey"}
LIE_TOKENS = {"tee": "from-the-tee", "fairway": "from-the-fairway", "rough": "from-the-rough",
              "sand": "from-the-sand", "green": "on-the-green", "fringe": "on-the-fringe"}
COURSE_TOKENS = {"pebble-beach": "pebble-beach", "st-andrews-old": "the-old-course",
                 "augusta-national": "augusta-national"}
WIND_TOKENS = {"with": "the-breeze-is-behind-you", "into": "into-the-breeze",
               "across": "a-crosswind", "swirling": "the-wind-swirls-here"}
WIND_FROM = {"with": "from-behind-you", "into": "in-your-face",
             "across": "across-the-hole", "swirling": "and-swirling"}
CLOCK_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
               7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
WIND_CLOCK = {h: f"out-of-{w}-oclock" for h, w in CLOCK_WORDS.items()}


def clock(hour):
    """The token for a wind out of one hour of the clock, or None."""
    return WIND_CLOCK.get(int(hour) % 12 or 12) if hour is not None else None


def wind(kind, mph=None, hour=None):
    """The wind, read - in the best words this unit has recordings for.

    Three readings, newest first, each standing in for the one before it
    until somebody records the pieces:

    1. by the clock - "The wind is, twelve miles an hour, out of eight
       o'clock" - which is what the game actually models now, so the
       narrator and the ball agree about a quartering wind;
    2. "The wind is, twelve miles an hour, in your face";
    3. the oldest, "into the breeze, twelve miles an hour".

    A swirling hole has no one hour to be out of and is never given one:
    it is drawn afresh every shot, and saying a bearing for it would be
    claiming something the game does not mean.
    """
    if kind not in WIND_TOKENS:
        return []
    said = clock(hour) if kind != "swirling" else None
    have = _shelf is not None and "the-wind-is" in _shelf
    if said and mph and have and said in _shelf:
        return ["the-wind-is"] + number(mph) + ["miles-an-hour", said]
    if mph and have and WIND_FROM[kind] in _shelf:
        return ["the-wind-is"] + number(mph) + ["miles-an-hour", WIND_FROM[kind]]
    out = [WIND_TOKENS[kind]]
    if mph:
        out += number(mph) + ["miles-an-hour"]
    return out


# ------------------------------------------------------------ composing

# The shelf: which stems are recorded on this unit, told to us by the room
# when it reads the folder at the start of a round. Only numbers look at it -
# a whole number read in one breath (n-377.mp3, "three hundred seventy-seven")
# beats five pieces stitched, so when the shelf has the whole number that is
# what is said, and the pieces are the fallback for a number it does not
# have. Everything else is composed the same whatever is recorded, and the
# screen skips what is missing.
_shelf = None


def set_shelf(stems):
    """What is recorded: a list of stems, or None for unknown (say the pieces)."""
    global _shelf
    _shelf = set(stems) if stems is not None else None


def to_go(left):
    """"To go", after the yards: "yards to go" for a long way, where the
    yards are the point and the piece is on the shelf - "one hundred and
    fifty yards to go" - and the shorter "to go" inside a hundred, so the
    address does not say the same thing every stroke. Without the piece,
    "to go" throughout."""
    if left is not None and left >= 100 and (_shelf is None or "yards-to-go" in _shelf):
        return ["yards-to-go"]
    return ["to-go"]


def _say(phrase, *pieces):
    """The phrase, when the shelf has it or the shelf is unknown; the
    pieces instead when it does not and they are all recorded; the phrase
    (silent) otherwise. So a half-recorded shelf still says something."""
    if _shelf is None or phrase in _shelf or not pieces:
        return [phrase]
    flat = []
    for p in pieces:
        flat += p if isinstance(p, list) else [p]
    if all(t in _shelf for t in flat):
        return flat
    return [phrase]


def number(n):
    """A whole number as the words to say it: 377 is three, hundred, seventy,
    seven; 15 is fifteen; 0 is zero. Up to 999, which is every number on a
    course. If the unit has the whole number recorded (n-377), that alone."""
    n = int(n)
    if n < 0:
        n = -n
    if n > 999:
        n = 999
    if _shelf and f"n-{n}" in _shelf:
        return [f"n-{n}"]
    out = []
    if n >= 100:
        whole_hundred = f"n-{n // 100 * 100}"
        if _shelf and whole_hundred in _shelf:
            # "three hundred" in one breath, then the rest - no "and":
            # that is how it is said this side of the water.
            out.append(whole_hundred)
            n %= 100
            if not n:
                return out
        else:
            out += [NUMBER_WORDS[n // 100], "hundred"]
            n %= 100
            if n:
                out.append("and")
            else:
                return out
    if n in NUMBER_WORDS:
        out.append(NUMBER_WORDS[n])
    else:
        out += [NUMBER_WORDS[n - n % 10], NUMBER_WORDS[n % 10]]
    return out


def ordinal(n):
    """The hole, as the-first ... the-eighteenth."""
    n = int(n)
    if 1 <= n <= len(ORDINALS):
        return [f"the-{ORDINALS[n - 1]}"]
    return []


def name_token(name):
    """A regular's name, as recorded: name-<slug>. Whether it is on the
    shelf is the page's to know; a missing token is silent, and the
    address is said without the name."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
    return f"name-{slug}" if slug else "the-player"


def looks_like_callsign(name):
    """KC9SP, W1AW, VE3ABC: letters and digits, three to seven of them, at
    least one digit, no spaces. Not "Scott", not "Ann Lee"."""
    s = str(name or "").strip().upper()
    # a prefix, the digit, and a suffix of letters - the shape of every
    # amateur callsign, and not of "4X4" or a licence number
    return bool(re.fullmatch(r"[A-Z0-9]{1,3}[0-9][A-Z]{1,4}", s)) and any(c.isalpha() for c in s[:-1])


def name_tokens(name):
    """How the narrator says who: their recorded name when the shelf has
    it; a callsign spelled phonetically, letter by letter, when it does
    not - Kilo Charlie nine Sierra Papa - which is what the operator would
    say; and otherwise the name file, silent if unrecorded."""
    token = name_token(name)
    if _shelf is None or token in _shelf or not looks_like_callsign(name):
        return [token]
    out = []
    for c in str(name).strip().lower():
        out += [f"phon-{c}"] if c.isalpha() else number(int(c))
    return out


def hole(n, par, yards, wind=None, wind_mph=None, course=None, wind_hour=None):
    """The hole read out at the tee: the course once, the hole, par, yards,
    and the breeze."""
    out = []
    # A hole read as one recording - hole-<course>-<n>.mp3, "Hole one is a
    # par four at three hundred and seventy-seven yards" in one breath -
    # is said instead of the pieces when the shelf has it.
    # A hole may have more than one read - hole-<course>-<n>-read-<k> beside
    # the first - and the narrator takes one of them, so a regular hears
    # the hole in different words on different evenings.
    reads = ([f"hole-{course}-{n}"] if course and _shelf and f"hole-{course}-{n}" in _shelf else []) +         ([t for k in range(2, 10) for t in [f"hole-{course}-{n}-read-{k}"] if _shelf and t in _shelf] if course else [])
    whole = random.choice(reads) if reads else None
    if whole:
        out.append(whole)
        out += globals()["wind"](wind, wind_mph, wind_hour)
        # the tee's colour is not here: it comes a line at a time, one to
        # each player's address on the tee - see party._lie_notes
        return out
    if course and course in COURSE_TOKENS:
        out.append(COURSE_TOKENS[course])
    # "the first" - or, from the pieces, "hole, one, is"
    first = ordinal(n)
    if first:
        out += _say(first[0], "hole", number(n), *(["is"] if _shelf and "is" in _shelf else []))
    out += ["par"] + number(par)
    out += number(yards) + ["yards"]
    out += globals()["wind"](wind, wind_mph, wind_hour)
    return out


def notes(course, n, where):
    """The colour a hole was given, in order: hole-<course>-<n>-<where>-<k>
    files - "A four here feels like nothing" at the tee, "The putting
    surface is modest" at the first putt, and likewise the fairway's, the
    sand's, the rough's at the first stroke from each, the water's with
    the first splash - said when they are recorded."""
    if not course or _shelf is None:
        return []
    out = []
    k = 1
    while f"hole-{course}-{n}-{where}-{k}" in _shelf:
        out.append(f"hole-{course}-{n}-{where}-{k}")
        k += 1
    return out


def address(name, club=None, left=None, lie=None, slot=None, honors=False, green_notes=None):
    """Scott addresses the ball, the driver in hand, three hundred and
    seventy-seven to go, from the tee - or, by the slot on the sheet,
    "Player 2 is away" ("Player 1 has honors" first off the tee), which
    is how a starter calls it and needs no file per person. The slot line
    when it is recorded; the name and "addresses the ball" otherwise."""
    out = None
    if slot and _shelf is not None:
        if honors and f"player-{slot}-has-honors" in _shelf:
            out = [f"player-{slot}-has-honors"]
        elif f"player-{slot}-is-away" in _shelf:
            out = [f"player-{slot}-is-away"]
    if out is None:
        out = name_tokens(name) + ["addresses-the-ball"]
    if club:
        out += [f"the-{club}", "in-hand"]
    if lie == "green":
        out.append("on-the-green")
        if green_notes:
            out += green_notes
        return out
    notes_after = list(green_notes or [])      # the fairway's, the sand's, the rough's: after the lie
    if left is not None:
        out += number(left) + to_go(left)
    if lie in LIE_TOKENS:
        out.append(LIE_TOKENS[lie])
    return out + notes_after


AHEAD_KIND = {"bunker": "a-bunker", "water": "the-water", "rough": "the-rough"}
AHEAD_SIDE = {"left": "on-the-left", "right": "on-the-right", "across": "across-the-fairway",
              "front": "across-the-fairway", "beyond": "beyond-the-green"}


def ahead(hazards):
    """What lies in the line, said: each hazard the rules found ahead, its
    yards from the ball, its side, and whether the club in hand reaches
    it. Nothing when nothing is ahead, and nothing until the pieces are on
    the shelf - a phrase of eight unrecorded pieces was eight silences in
    every address, and the screen has the words meanwhile."""
    if _shelf is not None and ("ahead" not in _shelf or "in-play" not in _shelf):
        return []
    out = []
    for z in hazards or []:
        kind = AHEAD_KIND.get(z.get("kind"))
        if not kind:
            continue
        piece = ["ahead", kind] if not out else [kind]
        if z.get("side") != "beyond" and z.get("at"):
            piece += ["at"] + number(z["at"]) + ["yards"]
        side = AHEAD_SIDE.get(z.get("side") or "")
        if side:
            piece.append(side)
        piece.append("in-play" if z.get("where") == "in-play" else "out-of-reach")
        out += piece
    return out


def ahead_words(hazards):
    """The same, as a sentence for the screen."""
    parts = []
    for z in hazards or []:
        kind = {"bunker": "a bunker", "water": "the water", "rough": "the rough"}.get(z.get("kind"), z.get("kind", ""))
        name = z.get("name") or ""
        what = name if name and name != z.get("kind") else kind
        if z.get("kind") == "bunker" and "bunker" not in what.lower():
            what += " bunker"                       # "greenside" wants its noun
        where = {"left": "on the left", "right": "on the right", "across": "across the fairway",
                 "front": "across the fairway", "beyond": "beyond the green"}.get(z.get("side") or "", "")
        bit = what + (f" at {z['at']} yards" if z.get("side") != "beyond" and z.get("at") else "") + (f", {where}" if where else "")
        bit += ", in play" if z.get("where") == "in-play" else ", out of reach"
        parts.append(bit)
    return ("Ahead: " + "; ".join(parts) + ".") if parts else ""


def call(text):
    """The golfer's word at contact, as its file."""
    tok = CALL_TOKENS.get(str(text or "").strip())
    return [tok] if tok else []


def shot(s):
    """The stroke in words, from the shot the rules made: the club, the
    yards, where it went, and the score if the hole is done."""
    kind = s.get("kind")
    out = []
    club = s.get("club")
    if s.get("flair") == "holed-out":
        out += [f"the-{club}"] if club else []
        out += number(s.get("carry") or 0) + ["yards", "holed-it-from-the-fairway"]
    elif s.get("flair") == "flop":
        out += ["the-wedge"] + number(s.get("carry") or 0) + ["yards", "flopped-it-to-a-tap-in"]
    elif s.get("putt"):
        # a putt: holed, or how much is left
        if kind == "holed":
            out.append("putt-holed")
        else:
            if kind == "missed":
                out.append("putt-missed")
            if s.get("left_feet"):
                out += number(s["left_feet"]) + ["feet"]
    elif kind == "holed":
        if s.get("ace"):
            out += [f"the-{club}"] if club else []
            out += number(s.get("carry") or 0) + ["yards", "in-the-hole", "an-ace"]
        else:
            out.append("putt-holed")
    elif kind == "missed":
        out.append("putt-missed")
    else:
        if club:
            out.append(f"the-{club}")
        if s.get("carry"):
            out += number(s["carry"]) + ["yards"]
        else:
            out.append("a-foul-ball")
        if kind == "fairway":
            out.append("fairway")
            if s.get("left") is not None:
                out += number(s["left"]) + to_go(s["left"])
        elif kind == "green":
            out += _say("on-the-green", "green")
            if s.get("feet"):
                out += number(s["feet"]) + ["feet"]
        elif kind == "fringe":
            out += _say("on-the-fringe", "green")
            if s.get("feet"):
                out += number(s["feet"]) + ["feet"]
        elif kind == "long":
            out.append("through-the-green")
        elif kind == "sand":
            out += _say("into-the-sand", "bunker")
        elif kind == "water":
            out += ["into-the-water", "drop-and-a-penalty-stroke"]
        elif kind == "rough":
            out += _say("short-and-into-the-rough" if not s.get("carry") else "into-the-rough", "rough")
    if s.get("picked_up"):
        out.append("picked-up")
    score = s.get("score")
    if score in SCORE_TOKENS and (s.get("holed") or s.get("picked_up")):
        if s.get("strokes") and s.get("holed"):
            out += number(s["strokes"])
        out.append(SCORE_TOKENS[score])
    return out


def card(rows):
    """That's the hole: each name and its score."""
    out = ["thats-the-hole"]
    for r in rows or []:
        out += name_tokens(r.get("name"))
        score = r.get("score")
        if score in SCORE_TOKENS:
            out.append(SCORE_TOKENS[score])
        elif r.get("strokes"):
            out += number(r["strokes"])
    out.append("on-to-the-next")
    return out


def script_lines():
    """The recording list: one line a snippet, `stem: words`."""
    return [f"{stem}: {words}" for stem, words in VOCABULARY.items()]


def whole_number_note():
    """For the script: the optional whole-number files, and their names."""
    return ("Whole holes, optional: a hole read as one recording - hole-<course>-<n>.mp3, "
            "hole-pebble-beach-1.mp3 for the first at Pebble Beach - is said at the tee instead of "
            "the pieces, then the wind. "
            "Whole numbers, optional: a number read in one breath beats the pieces, so "
            "any file named n-<number>.mp3 (n-377.mp3: \"three hundred seventy-seven\", "
            "n-15.mp3: \"fifteen\") is said in place of the pieces whenever that number "
            "comes up, and the pieces cover every number that has no file. Zero to 999; "
            "the numbers on the first hole at Pebble Beach are the yards from each lie, "
            "so record what the card and the clubs can produce, and the pieces fill the rest.")
