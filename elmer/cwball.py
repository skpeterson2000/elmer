"""CW Baseball: the rules. Catching is receiving, throwing is sending.

Batting is receiving too. A pitch is a transmission - its speed, its length
and what it holds rise with the level: letters, then groups, then words,
then a callsign and a report, then a full exchange - and copying it clean
is a hit sized by the pitch: a group a single, a word a double, a callsign
and a report a triple, a full exchange a home run. A near miss is a foul (a
strike until there are two), a miss is a strike, three strikes an out,
three outs the side.

The mound. The machine pitches when there are not people enough for a
pitcher; otherwise the fielding side's pitcher is handed the text on their
own phone and keys it, and the umpire - the decoder - calls the pitch as
thrown: clean, the right text, at speed, is in the zone; clean but the
wrong text, or off speed, is a *ball*; a pitch that does not decode is
*wild*, nobody can copy it, and the runners advance. A pitcher chooses the
pitch by choosing how hard a thing they are willing to send: a normal
pitch is handed plain code, a hard one cut numbers, prosigns, punctuation
and the top of the speed band - harder to throw clean, harder to copy, and
it pays the batter more when it is hit, because a hanging curve gets
crushed. At the top of the ladder the pitcher composes the text. The
machine is a competent pitcher in the little league, every pitch in the
zone, and adds variety in the majors: the odd ball on purpose.

The plate. The batter's copy is the swing, graded against what actually
went out, not what the pitcher was told to send. Swing at a pitch in the
zone and copy it clean: a hit. Swing at a ball and connect - copy exactly
what was keyed, wrong letter and all - and it is a hit one base bigger,
because the batter hit a pitch never meant to be hittable; swing at a ball
and miss and it is only a ball. The batter may *take* the pitch, sending
nothing, and bet on the umpire: take a ball and it is a ball, four and a
walk; take a strike and in the majors it is a called strike, in the little
league it is free.

The field. Everyone copies every pitch, because a fielder who was not
listening cannot catch. Where the ball goes the machine decides from the
hit and a little chance, named by position; the catch is that fielder's
own copy of the pitch, held on their device until the play comes to them.
A fly ball copied clean is the out. A grounder copied clean still has to
be thrown: the fielder keys the text to a baseman, judged as a throw, and
the baseman's copy of that throw is the tag; bobble it and the runner is
safe on an error charged to the baseman. The clock is the runner: each
link has its seconds at the level. With a runner on first a grounder is a
force at second, and a clean tag there with time to spare offers the throw
on to first for two.

Nothing here plays sound or reads a key. The room says who copied what and
who keyed what; this says what it was worth. The timing of a copy or a
send is the room's clock; the rules take a deadline and a now. What a
device holds and when it is triggered is the state's `your_link`; the rules
accept a copy of the pitch from any fielder at any time as readiness, and
count it toward a fielding percentage.
"""
import random
import re
import time

from . import cw

# What a pitch is at each level: the kind, how many bases a clean copy is
# worth, and a name for the screens. The level climbs with the innings.
LEVELS = [
    {"kind": "letters", "bases": 1, "name": "letters"},
    {"kind": "group", "bases": 1, "name": "a group"},
    {"kind": "word", "bases": 2, "name": "a word"},
    {"kind": "call", "bases": 3, "name": "a call and a report"},
    {"kind": "exchange", "bases": 4, "name": "the exchange"},
    # the contact: the pitcher calls CQ, the batter copies the call, and the
    # fielder answers it - their own call - which is the ritual of the air
    {"kind": "contact", "bases": 4, "name": "a contact"},
]
WORDS = ["RADIO", "ANTENNA", "SIGNAL", "REPEAT", "STATION", "COPY", "TOWER", "GROUND", "TUNER", "BAND",
         "FILTER", "POWER", "METER", "NIGHT", "MORNING", "COAX", "DIPOLE", "BEACON", "QSL", "RIG"]
PREFIXES = ["W1", "W2", "K3", "N4", "W5", "K6", "N7", "K8", "W9", "K0", "VE3", "G4", "DL1", "JA1"]
NAMES = ["ANN", "BOB", "SAM", "JIM", "SUE", "TOM", "MAX", "KAY", "LEE", "PAT", "ROY", "AMY"]
GRIDS = ["EL16HQ", "EN36", "FN31PR", "CM87", "DM79", "EM12", "FM19", "CN87", "EN52", "DN40"]
HIT_PCT = 90                    # copied this clean is a hit
FOUL_PCT = 60                   # this clean is a foul: a strike until there are two
OUT_PCT = 90                    # keyed this clean is a clean throw, and a clean pitch
ERROR_PCT = 50                  # keyed worse than this is an error; a pitch this bad is wild
COPY_SECONDS = 2.2              # per character, to type it after it sounds
COPY_LEAST = 12.0
FIELD_SECONDS = 4.0             # per character, to key it
FIELD_LEAST = 12.0
CATCH_SECONDS = 8.0             # to hand up the held copy when the ball comes to you
WINDUP_SECONDS = 40.0           # the pitch clock: choose and key it, or it is a ball
REVEAL_SECONDS = 9.0            # the play stands on the screens
# The little league lets the batter ask for the pitch again - "?" or AGN,
# as a contact would - this many times before the umpire says play ball.
AGAIN_MOST = 3
BETWEEN_SECONDS = 12.0          # the side retires; the board is read
INNING_WPM = 1.5                # faster each inning
HARD_WPM = 1.15                 # a hard pitch is thrown at the top of the band
SPEED_TOLERANCE = 0.10          # a tenth either side, in the majors
DOUBLE_PLAY_SPARE = 0.5         # the force turned with this much of the clock left offers the second throw
BOT_SWING = {"Listener": 0.4, "Learner": 0.55, "Operator": 0.72, "Elmer": 0.86}   # a practice player's copy
BOT_FIELD = {"Listener": 0.35, "Learner": 0.5, "Operator": 0.68, "Elmer": 0.82}   # and its send
MACHINE_BALLS = {1: 0.0, 2: 0.08, 3: 0.14, 4: 0.2, 5: 0.25}                        # the majors: the machine's balls on purpose, by inning
LEAGUES = ("little", "major")
PITCHERS = ("machine", "people")
DIFFICULTIES = ("normal", "hard", "own")
# Where a ball goes, by what was hit: a grounder to the infield or a fly to
# the outfield. Infield first so a short side has somebody there.
POSITIONS = ["P", "SS", "1B", "2B", "3B", "C", "LF", "CF", "RF"]
INFIELD = ["SS", "2B", "3B", "1B"]
OUTFIELD = ["LF", "CF", "RF"]
FLIES = {"call", "exchange", "contact"}
CUT = {"T": "0", "N": "9", "A": "1", "D": "7"}       # cut numbers the air actually uses
OWN_OK = re.compile(r"^[A-Z0-9 ?/.,<>]{1,48}$")


def _now():
    return time.monotonic()


def _squash(text):
    return "".join(str(text or "").upper().split())


def accuracy(want, got):
    """Characters right, in order, as a percentage of what was asked."""
    a = _squash(want)
    b = _squash(got)
    if not a:
        return 0
    hits = sum(1 for i, c in enumerate(a) if i < len(b) and b[i] == c)
    return int(round(100 * hits / len(a)))


def uncut(text):
    """5NN read as 599, T as 0: the cut numbers written out, where they sit
    among digits. A word of letters is left alone."""
    out = []
    for word in str(text or "").upper().split():
        if any(ch.isdigit() for ch in word) and all(ch.isdigit() or ch in CUT for ch in word):
            word = "".join(CUT.get(ch, ch) for ch in word)
        out.append(word)
    return " ".join(out)


def accuracy_any(want, got):
    """The better of the copy read as written and read with the cut numbers
    expanded, both ways: 5NN copied as 599 is right, and so is 599 as 5NN."""
    return max(accuracy(want, got), accuracy(uncut(want), uncut(got)))


class Baseball:

    def __init__(self, lineups, names=None, innings=3, base_wpm=10.0, seed=None, bots=None,
                 league="little", pitcher="machine"):
        """`lineups` {"A": [player ids], "B": [...]} in batting order; A bats
        first. `names` player -> name. `bots` player -> level for practice
        players, who copy and key by their level's odds. `league` little or
        major; `pitcher` machine, or people - the fielding side's pitcher keys
        the pitch."""
        self.rng = random.Random(seed)
        self.lineups = {"A": list(lineups.get("A") or []), "B": list(lineups.get("B") or [])}
        self.names = dict(names or {})
        self.bots = dict(bots or {})
        self.innings = max(1, int(innings))
        self.base_wpm = max(5.0, float(base_wpm))
        self.league = league if league in LEAGUES else "little"
        self.pitcher_mode = pitcher if pitcher in PITCHERS else "machine"
        self.inning = 1
        self.half = "top"                 # A bats in the top, B in the bottom
        self.outs = 0
        self.strikes = 0
        self.balls = 0
        self.bases = [None, None, None]   # first, second, third: the player on it
        self.runs = {"A": 0, "B": 0}
        self.line = {"A": [], "B": []}    # runs an inning
        self.hits = {"A": 0, "B": 0}
        self.errors = {"A": 0, "B": 0}
        self.next_up = {"A": 0, "B": 0}
        self.phase = "between"            # windup | pitch | field | reveal | between | over
        self.deadline = _now() + 3.0
        self.pitch = None
        self.batter = None
        self.pitcher = None               # the person on the mound, when people pitch
        self.fielder = None               # whose link is live in the field
        self.link = None                  # pick | throw_pitch | catch | throw | tag
        self.chain = []                   # the links still to come in this play
        self.last = None                  # the last play, for the screens
        self.plays = []
        self.winner = None
        self.stats = {}                   # player -> {"copies", "clean", "catches", "caught", "throws", "clean_throws"}
        self._counted = set()             # (player, pitch n) whose copy is already in the record
        self._bot_at = None

    # ----------------------------------------------------------- who is who
    def batting(self):
        return "A" if self.half == "top" else "B"

    def fielding(self):
        return "B" if self.half == "top" else "A"

    def name(self, p):
        return self.names.get(p, str(p))

    def over(self):
        return self.phase == "over"

    def people_pitch(self):
        return self.pitcher_mode == "people" and bool(self.lineups[self.fielding()])

    def level(self):
        """The pitch's level: the inning's, capped below the top - and the
        last inning of the game, whatever number it is, pitches the contact
        every other time, so the end-game is the air itself."""
        if self.inning >= self.innings and self.inning > 1 and self.rng.random() < 0.5:
            return len(LEVELS) - 1
        return min(len(LEVELS) - 2, self.inning - 1)

    def wpm(self):
        return round(self.base_wpm + INNING_WPM * (self.inning - 1), 1)

    def positions(self, team=None):
        """Who stands where: the pitching rotation turns with the inning, the
        rest fill the positions in order, infield first. A short side leaves
        positions empty and fielder_at() covers them."""
        team = team or self.fielding()
        order = self.lineups[team]
        if not order:
            return {}
        n = len(order)
        pitcher = order[(self.inning - 1) % n]
        rest = [p for p in order if p != pitcher]
        out = {"P": pitcher}
        for pos, p in zip(POSITIONS[1:], rest):
            out[pos] = p
        return out

    def fielder_at(self, position, team=None, not_these=()):
        """The player covering a position - the one standing there, else the
        nearest of their group, else anybody but the pitcher and `not_these`,
        so one person is never asked to catch, throw and catch again."""
        team = team or self.fielding()
        posn = self.positions(team)
        if posn.get(position) is not None and posn[position] not in not_these:
            return posn[position]
        group = INFIELD if position in INFIELD or position in ("C",) else OUTFIELD
        for pos in group + INFIELD + OUTFIELD:
            p = posn.get(pos)
            if p is not None and p not in not_these:
                return p
        for p in self.lineups[team]:
            if p not in not_these and p != posn.get("P"):
                return p
        return posn.get("P")

    def stat(self, p):
        return self.stats.setdefault(p, {"copies": 0, "clean": 0, "catches": 0, "caught": 0,
                                         "throws": 0, "clean_throws": 0, "pitches": 0, "strikes": 0,
                                         "agains": 0, "agains_keyed": 0})

    # --------------------------------------------------------------- pitches
    def _text(self, level, difficulty="normal"):
        kind = LEVELS[level]["kind"]
        r = self.rng
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        hard = difficulty == "hard"
        if kind == "letters":
            return "".join(r.choice(letters) for _ in range(3)) + (r.choice("0123456789") if hard else "")
        if kind == "group":
            pool = letters + "0123456789" + ("?/." if hard else "")
            return "".join(r.choice(pool) for _ in range(6 if hard else 5))
        if kind == "word":
            return r.choice(WORDS) + (f" {r.choice(GRIDS)}" if hard else "")
        if kind == "call":
            call = f"{r.choice(PREFIXES)}{''.join(r.choice(letters) for _ in range(r.choice((2, 3))))}"
            report = f"5{r.choice('789')}9"
            if hard:
                report = report.replace("9", "N")          # 5NN, the way it is sent
                return f"{call} {report} <BT>"
            return f"{call} {report}"
        call = f"{r.choice(PREFIXES)}{''.join(r.choice(letters) for _ in range(3))}"
        if kind == "contact":
            return f"CQ CQ CQ DE {call} {call} K" + (" <AR>" if hard else "")
        if hard:
            return f"CQ CQ DE {call} {call} QTH {r.choice(GRIDS)} <AR> K"
        return f"CQ CQ DE {call} {call} K"

    def _machine_call(self, text):
        """What the machine throws: in the little league a competent pitcher,
        every pitch in the zone; in the majors the odd ball on purpose - one
        letter wrong, keyed clean - rising with the inning."""
        if self.league != "major":
            return text, "zone"
        odds = MACHINE_BALLS.get(min(self.inning, 5), 0.25)
        if self.rng.random() >= odds:
            return text, "zone"
        chars = list(text)
        spots = [i for i, ch in enumerate(chars) if ch.isalnum()]
        if not spots:
            return text, "zone"
        i = self.rng.choice(spots)
        pool = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        chars[i] = self.rng.choice([c for c in pool if c != chars[i]])
        return "".join(chars), "ball"

    def new_pitch(self):
        """The next pitch, to the next batter. With people pitching, phase
        windup: the pitcher chooses and keys. Else the machine throws now."""
        team = self.batting()
        order = self.lineups[team]
        if not order:
            self.phase = "over"
            self.winner = self.fielding()
            return None
        self.batter = order[self.next_up[team] % len(order)]
        level = self.level()
        self.fielder = None
        self.link = None
        self.chain = []
        self.pitch = {"n": len(self.plays) + 1, "level": level, "kind": LEVELS[level]["kind"],
                      "name": LEVELS[level]["name"], "bases": LEVELS[level]["bases"],
                      "wpm": self.wpm(), "difficulty": None, "text": None, "sent": None, "call": None,
                      "again": 0, "again_keyed": 0}
        if self.people_pitch():
            self.pitcher = self.positions()["P"]
            self.stat(self.pitcher)["pitches"] += 1
            self.phase = "windup"
            self.link = "pick"
            self.deadline = _now() + WINDUP_SECONDS
            self._plan_bot()
            return self.pitch
        self.pitcher = None
        self.pitch["difficulty"] = "normal"
        text = self._text(level)
        self.pitch["text"] = text
        sent, call = self._machine_call(text)
        self._throw_pitch(sent, call, self.wpm())
        return self.pitch

    def choose(self, player, difficulty, text=None):
        """The pitcher's choice: how hard a thing to send. `own` is the top of
        the ladder - the pitcher composes the text - and only in the majors
        at the exchange or above."""
        if self.phase != "windup" or self.link != "pick":
            return {"error": "nothing to choose now"}
        if player != self.pitcher:
            return {"error": f"not your mound - {self.name(self.pitcher)} is pitching"}
        if difficulty not in DIFFICULTIES:
            difficulty = "normal"
        level = self.pitch["level"]
        if difficulty == "own":
            if self.league != "major" or level < 4:
                return {"error": "composing your own pitch is the majors, at the exchange and above"}
            own = str(text or "").upper().strip()
            if not OWN_OK.match(own) or not cw.encode(own):
                return {"error": "the pitch must be letters, numbers, punctuation and prosigns, up to 48"}
            self.pitch["text"] = own
        else:
            self.pitch["text"] = self._text(level, difficulty)
        self.pitch["difficulty"] = difficulty
        self.pitch["wpm"] = round(self.wpm() * (HARD_WPM if difficulty != "normal" else 1.0), 1)
        self.link = "throw_pitch"
        self._plan_bot()
        return {"ok": True, "text": self.pitch["text"], "wpm": self.pitch["wpm"]}

    def deliver(self, player, keyed, wpm=None):
        """The pitcher's throw: what the decoder read of their keying, and
        the speed it measured. The umpire calls it and the pitch is thrown
        once through the table - as keyed, wrong letter and all."""
        if self.phase != "windup":
            return {"error": "no pitch to throw"}
        if player != self.pitcher:
            return {"error": f"not your mound - {self.name(self.pitcher)} is pitching"}
        if self.link == "pick":
            self.choose(player, "normal")
        want = self.pitch["text"]
        pct = accuracy_any(cw.plain(want), keyed)
        try:
            measured = float(wpm) if wpm else None
        except (TypeError, ValueError):
            measured = None
        asked = self.pitch["wpm"]
        off_speed = (self.league == "major" and measured is not None
                     and abs(measured - asked) > asked * SPEED_TOLERANCE)
        if pct >= OUT_PCT and not off_speed:
            call = "zone"
        elif pct >= ERROR_PCT:
            call = "ball"
        else:
            call = "wild"
        self.pitch["pitch_pct"] = pct
        self.pitch["measured_wpm"] = round(measured, 1) if measured else None
        self.pitch["off_speed"] = bool(off_speed)
        if call == "zone":
            self.stat(player)["strikes"] += 1
        if call == "wild":
            return self._wild(player, keyed)
        self._throw_pitch(str(keyed or "").upper().strip() or cw.plain(want), call,
                          measured if measured and not off_speed else asked)
        return {"ok": True, "call": None}          # the call is the umpire's to reveal

    def _throw_pitch(self, sent, call, wpm):
        """The pitch is in the air: what actually went out, at the speed it
        went, for every screen to sound and every device to copy and hold."""
        p = self.pitch
        sent = cw.plain(sent) if "<" in sent else sent
        p["sent"] = sent
        p["call"] = call
        p["plain"] = cw.plain(p["text"] or sent)
        p["groups"] = cw.encode(p["text"] if call == "zone" else sent)
        p["timing"] = cw.timing(wpm, wpm)
        p["thrown_wpm"] = round(float(wpm), 1)
        chars = len(_squash(sent))
        p["sounds"] = round(sum(len(cw.MORSE.get(c, "")) for c in _squash(cw.plain(p["text"] if call == "zone" else sent))) * 2.5
                            * p["timing"]["dit"] / 1000.0 + len(sent.split()) * p["timing"]["word_gap"] / 1000.0, 1)
        p["window"] = round(max(COPY_LEAST, chars * COPY_SECONDS), 1)
        # what the batter must produce: what was sent - except in a contact,
        # the call that is calling; the fielder's answer is their own call
        called = sent.split()[3] if p["kind"] == "contact" and len(sent.split()) > 3 else None
        p["want"] = called or sent
        p["answer"] = f"{called} DE" if called else None
        self.phase = "pitch"
        self.link = "swing"
        self.deadline = _now() + p["sounds"] + p["window"]
        self._plan_bot()

    def _wild(self, player, keyed):
        """A pitch nobody could copy: a ball, and the runners move up."""
        play = self._play_base()
        play.update({"result": "wild pitch", "keyed": str(keyed or "")[:60], "pitcher": player,
                     "pitcher_name": self.name(player), "call": "wild"})
        self.balls += 1
        moved = self._advance(1)
        play["words"] = f"{self.name(player)}'s pitch got away - wild pitch, ball {self.balls}"
        if moved:
            play["words"] += f", the runners move up{' - a run scores' if play.get('scored') else ''}"
        if self.balls >= 4:
            play["words"] += f" - ball four, {self.name(self.batter)} walks"
            self._walk(play)
        else:
            self._reveal(play)
        return play

    # -------------------------------------------------------------- the play
    def _play_base(self):
        p = self.pitch or {}
        return {"n": p.get("n"), "batter": self.batter, "batter_name": self.name(self.batter),
                "kind": p.get("kind"), "bases": p.get("bases"), "difficulty": p.get("difficulty"),
                "pitch": p.get("sent"), "asked": cw.plain(p["text"]) if p.get("text") else None,
                "want": p.get("want"), "call": p.get("call"), "pitcher": self.pitcher,
                "pitcher_name": self.name(self.pitcher) if self.pitcher is not None else "the machine",
                "scored": 0}

    def hit_bases(self):
        """What a hit is worth: the level's bases, one more for a hard pitch,
        one more for a ball hit clean - capped at a home run."""
        p = self.pitch
        bases = p["bases"]
        if p.get("difficulty") in ("hard", "own"):
            bases += 1
        if p.get("call") == "ball":
            bases += 1
        return min(4, bases)

    def again(self, player, keyed=False):
        """The batter asks for the pitch again - "?" or AGN, as a contact
        would. The little league only, and only with the machine on the
        mound: a person is not asked to key it twice, and the majors pitch
        it once. The pitch sounds again on every screen, the clock restarts,
        and the ask is counted - against the pitch, so the play can say
        "after asking twice", and for the batter, in the record. `keyed`
        says it was asked in code rather than by a button, which the words
        mark: for many that will be the first thing they ever send that is
        answered, and it should feel like it."""
        if self.phase != "pitch":
            return {"error": "no pitch to ask for again"}
        if player != self.batter:
            return {"error": f"not your at-bat - {self.name(self.batter)} is up"}
        if self.league != "little":
            return {"error": "the majors pitch it once"}
        if self.pitcher is not None:
            return {"error": f"{self.name(self.pitcher)} is on the mound - a person is not asked to key it twice"}
        p = self.pitch
        if p.get("again", 0) >= AGAIN_MOST:
            return {"error": f"the umpire says play ball - {AGAIN_MOST} is the most the little league allows"}
        p["again"] = p.get("again", 0) + 1
        if keyed:
            p["again_keyed"] = p.get("again_keyed", 0) + 1
        s = self.stat(player)
        s["agains"] += 1
        if keyed:
            s["agains_keyed"] += 1
        self.deadline = _now() + p["sounds"] + p["window"]
        self._plan_bot()
        return {"ok": True, "again": p["again"], "left": AGAIN_MOST - p["again"], "keyed": bool(keyed),
                "words": (f"{self.name(player)} asked for it again"
                          + (" - in code, and the machine answered" if keyed else "")
                          + f" ({p['again']} of {AGAIN_MOST})")}

    def swing(self, player, typed):
        """The batter's copy. Returns the play, or an error."""
        p = self.pitch
        play = self._swing(player, typed)
        if isinstance(play, dict) and not play.get("error") and p and p.get("again"):
            how = "again" if p["again"] == 1 else "twice" if p["again"] == 2 else f"{p['again']} times"
            play["words"] += f" - after asking for it {how}" + (", in code" if p.get("again_keyed") else "")
        return play

    def _swing(self, player, typed):
        if self.phase != "pitch":
            return {"error": "no pitch to swing at"}
        if player != self.batter:
            return {"error": f"not your at-bat - {self.name(self.batter)} is up"}
        pct = accuracy_any(self.pitch["want"], typed)
        play = self._play_base()
        play.update({"typed": str(typed or "")[:60], "copy_pct": pct, "swung": True})
        s = self.stat(player)
        s["copies"] += 1
        self._counted.add((player, self.pitch["n"]))
        ball = self.pitch["call"] == "ball"
        if pct >= HIT_PCT:
            s["clean"] += 1
            bases = self.hit_bases()
            play["result"] = "in play"
            play["hit_bases"] = bases
            play["words"] = (f"{self.name(player)} copied {self.pitch['name']} clean"
                             + (" - and that pitch was a ball: connected with it anyway" if ball else "")
                             + f" - in play, {bases} base{'s' if bases > 1 else ''} if it drops")
            self._to_field(play)
            return play
        if ball:
            self.balls += 1
            play["result"] = "ball"
            play["words"] = f"{self.name(player)} swung and got {pct}% - but the pitch was a ball, ball {self.balls}"
            if self.balls >= 4:
                play["words"] += f" - ball four, {self.name(player)} walks"
                self._walk(play)
            else:
                self._reveal(play)
            return play
        if pct >= FOUL_PCT and self.strikes < 2:
            self.strikes += 1
            play["result"] = "foul"
            play["words"] = f"{self.name(player)} got {pct}% of it - foul ball, strike {self.strikes}"
            self._reveal(play)
            return play
        self._strike(play, f"{self.name(player)} got {pct}% of it")
        return play

    def take(self, player):
        """The batter lets it go by and bets on the umpire's call."""
        p = self.pitch
        play = self._take(player)
        if isinstance(play, dict) and not play.get("error") and p and p.get("again"):
            how = "again" if p["again"] == 1 else "twice" if p["again"] == 2 else f"{p['again']} times"
            play["words"] += f" - after asking for it {how}" + (", in code" if p.get("again_keyed") else "")
        return play

    def _take(self, player):
        if self.phase != "pitch":
            return {"error": "no pitch to take"}
        if player != self.batter:
            return {"error": f"not your at-bat - {self.name(self.batter)} is up"}
        play = self._play_base()
        play.update({"typed": "", "swung": False})
        if self.pitch["call"] == "ball":
            self.balls += 1
            play["result"] = "ball"
            play["words"] = f"{self.name(player)} takes it - ball {self.balls}, the umpire agrees"
            if self.balls >= 4:
                play["words"] += f" - ball four, {self.name(player)} walks"
                self._walk(play)
            else:
                self._reveal(play)
            return play
        if self.league == "major":
            self._strike(play, f"{self.name(player)} takes it - right down the middle", looking=True)
            return play
        play["result"] = "taken"
        play["words"] = f"{self.name(player)} takes it - it was a strike, but the little league lets that go"
        self._reveal(play)
        return play

    def _strike(self, play, words, looking=False):
        self.strikes += 1
        play["result"] = "strike"
        play["words"] = f"{words} - strike {self.strikes}{' looking' if looking else ''}"
        if self.strikes >= 3:
            play["result"] = "strikeout"
            play["words"] = f"{words} - strike three, {self.name(self.batter)} is out{' looking' if looking else ''}"
            self._out(play)
        else:
            self._reveal(play)

    def _walk(self, play):
        play["result"] = "walk"
        self._reach(play, 1, forced=True)

    # ---------------------------------------------------------- the field
    def _ball_goes(self, kind):
        """Where the ball goes: a fly to the outfield off the big pitches, a
        grounder to the infield off the small ones, a little chance in it."""
        if kind in FLIES:
            return self.rng.choice(OUTFIELD), True
        if kind == "word" and self.rng.random() < 0.5:
            return "3B", False
        return self.rng.choice(INFIELD), False

    def _to_field(self, play):
        team = self.fielding()
        if not self.lineups[team]:
            self._reach(play, play["hit_bases"])
            return
        position, fly = self._ball_goes(self.pitch["kind"])
        fielder = self.fielder_at(position)
        play["position"] = position
        play["fly"] = fly
        play["fielder"] = fielder
        play["fielder_name"] = self.name(fielder)
        # the throw: the text back - or, in a contact, the answer to the call
        if self.pitch.get("answer"):
            own = self.name(fielder).upper()
            own = own if own.replace("/", "").isalnum() and any(c.isdigit() for c in own) else "ELMER"
            self.pitch["key"] = f"{self.pitch['answer']} {own}"
        else:
            self.pitch["key"] = self.pitch["sent"]
        play["key"] = self.pitch["key"]
        force = self.bases[0] is not None and not fly
        self.chain = [("catch", fielder)]
        if not fly:
            base = "2B" if force else "1B"
            baseman = self.fielder_at(base, not_these=(fielder,))
            play["to"] = base
            self.chain += [("throw", fielder), ("tag", baseman)]
        self.last = play
        self.phase = "field"
        self._next_link()

    def _next_link(self):
        if not self.chain:
            return
        link, who = self.chain.pop(0)
        self.link = link
        self.fielder = who
        play = self.last
        if link == "catch":
            self.deadline = _now() + CATCH_SECONDS
            play["words"] = (f"{'Fly ball' if play.get('fly') else 'Ground ball'} to {play['position']} - "
                             f"{self.name(who)} has the play")
        elif link == "throw":
            chars = len(_squash(self.pitch["key"]))
            self.deadline = _now() + max(FIELD_LEAST, chars * FIELD_SECONDS)
        elif link == "tag":
            # the throw sounds for the baseman to copy: the code, never the text
            thrown = self.pitch.get("throw") or self.pitch["key"]
            wpm = self.pitch.get("throw_wpm") or self.pitch.get("thrown_wpm") or self.wpm()
            self.pitch["throw_groups"] = cw.encode(thrown)
            self.pitch["throw_timing"] = cw.timing(wpm, wpm)
            self.deadline = _now() + CATCH_SECONDS
        self._plan_bot()

    def catch(self, player, typed):
        """The fielder's held copy of the pitch, handed up now the ball has
        come to them. A fly caught clean is the out; a grounder caught clean
        still has to be thrown; a bobble and the hit stands, or worse."""
        if self.phase != "field" or self.link != "catch":
            return {"error": "no ball to catch"}
        if player != self.fielder:
            return {"error": f"not your ball - {self.name(self.fielder)} has it"}
        play = self.last
        pct = accuracy_any(self.pitch["want"], typed)
        play["catch_typed"] = str(typed or "")[:60]
        play["catch_pct"] = pct
        s = self.stat(player)
        s["copies"] += 1
        s["catches"] += 1
        self._counted.add((player, self.pitch["n"]))
        if pct >= HIT_PCT:
            s["clean"] += 1
            s["caught"] += 1
            if play.get("fly"):
                play["result"] = "out"
                play["words"] = f"{self.name(player)} had the pitch clean - fly ball caught, {self.name(play['batter'])} is out"
                self._out(play)
                return play
            play["words"] = f"{self.name(player)} fields it clean - the throw to {play['to']}"
            self._next_link()
            return play
        if pct >= ERROR_PCT:
            play["result"] = "safe"
            play["words"] = f"{self.name(player)} had {pct}% of it - it drops, {self.name(play['batter'])} is safe"
            self._reach(play, play["hit_bases"])
        else:
            play["result"] = "error"
            play["words"] = f"{self.name(player)} never had it ({pct}%) - error, an extra base"
            self.errors[self.fielding()] += 1
            self._reach(play, play["hit_bases"] + 1)
        return play

    def throw(self, player, keyed, wpm=None, late=False):
        """The fielder's send to the baseman. Clean goes on to the tag; rough
        and the runner is safe; botched is an error."""
        if self.phase != "field" or self.link != "throw":
            return {"error": "nothing to throw"}
        if player != self.fielder:
            return {"error": f"not your ball - {self.name(self.fielder)} has it"}
        play = self.last
        pct = 0 if late else accuracy_any(self.pitch["key"], keyed)
        play["keyed"] = str(keyed or "")[:60]
        play["field_pct"] = pct
        s = self.stat(player)
        s["throws"] += 1
        bases = play["hit_bases"]
        if late:
            play["result"] = "safe"
            play["words"] = f"{self.name(player)} never got the throw off - {self.name(play['batter'])} is safe"
            self._reach(play, bases)
        elif pct >= OUT_PCT:
            s["clean_throws"] += 1
            self.pitch["throw"] = str(keyed or "").upper().strip()
            try:
                self.pitch["throw_wpm"] = float(wpm) if wpm else None
            except (TypeError, ValueError):
                self.pitch["throw_wpm"] = None
            play["words"] = f"{self.name(player)} keyed it clean - the throw is on its way to {play['to']}"
            self._next_link()
        elif pct >= ERROR_PCT:
            play["result"] = "safe"
            play["words"] = f"{self.name(player)} got {pct}% of the throw - {self.name(play['batter'])} is safe"
            self._reach(play, bases)
        else:
            play["result"] = "error"
            play["words"] = f"{self.name(player)} threw it away ({pct}%) - error, an extra base"
            self.errors[self.fielding()] += 1
            self._reach(play, bases + 1)
        return play

    field = throw                           # the old name for the old route

    def tag(self, player, typed):
        """The baseman's copy of the throw. Clean is the out; a bobble and
        the runner is safe on the baseman's error. A force at second with
        time to spare turns into the throw on to first."""
        if self.phase != "field" or self.link != "tag":
            return {"error": "no throw to catch"}
        if player != self.fielder:
            return {"error": f"not your base - {self.name(self.fielder)} is covering"}
        play = self.last
        pct = accuracy_any(self.pitch.get("throw") or self.pitch["key"], typed)
        play["tag_typed"] = str(typed or "")[:60]
        play["tag_pct"] = pct
        s = self.stat(player)
        s["copies"] += 1
        s["catches"] += 1
        if pct < HIT_PCT:
            play["result"] = "error"
            play["words"] = f"{self.name(player)} bobbled the throw at {play['to']} ({pct}%) - error, {self.name(play['batter'])} is safe"
            self.errors[self.fielding()] += 1
            self._reach(play, play["hit_bases"])
            return play
        s["clean"] += 1
        s["caught"] += 1
        if play.get("to") == "2B" and self.bases[0] is not None and not play.get("forced_out"):
            # the force at second: the lead runner is out; the batter is on
            # first unless there is time to turn two
            runner = self.bases[0]
            self.bases[0] = None
            play["forced_out"] = runner
            play["forced_name"] = self.name(runner)
            spare = self.deadline - _now()
            if spare >= CATCH_SECONDS * DOUBLE_PLAY_SPARE and self.outs < 2:
                first = self.fielder_at("1B", not_these=(player, play["fielder"]))
                if first is not None and first != player:
                    self.outs += 1
                    play["outs"] = self.outs
                    play["to"] = "1B"
                    play["words"] = f"{self.name(player)} takes the throw - {self.name(runner)} forced at second, and the throw on to first"
                    self.chain = [("throw", player), ("tag", first)]
                    self._next_link()
                    return play
            play["result"] = "force out"
            play["words"] = f"{self.name(player)} takes the throw - {self.name(runner)} forced at second, {self.name(play['batter'])} on at first"
            self.outs += 1
            play["outs"] = self.outs
            if self.outs >= 3:
                play["side"] = True
                self.next_up[self.batting()] += 1
                self.strikes = self.balls = 0
                self._retire(play)
                return play
            self._reach(play, 1, forced=True, count_hit=False)
            return play
        play["result"] = "double play" if play.get("forced_out") else "out"
        play["words"] = (f"{self.name(player)} takes the throw at {play['to']} - "
                         + (f"two! {self.name(play['batter'])} is out as well" if play.get("forced_out")
                            else f"{self.name(play['batter'])} is out"))
        self._out(play)
        return play

    def readiness(self, player, n, typed):
        """A copy of a pitch from anybody whose link never came - handed up
        after the reveal if it was clean, at the inning break if it was not,
        the device having graded it first against the pitch the reveal
        showed. It is readiness and a fielding percentage, never the play;
        a pitch already counted for this player is not counted twice.
        Returns the percentage."""
        try:
            n = int(n or 0)
        except (TypeError, ValueError):
            return {"error": "not a pitch"}
        want = None
        if self.pitch and n == self.pitch["n"]:
            want = self.pitch.get("want")
        else:
            want = next((pl.get("want") for pl in reversed(self.plays) if pl.get("n") == n), None)
        if not want:
            return {"error": "not a pitch of this game"}
        if player not in self.lineups["A"] and player not in self.lineups["B"]:
            return {"error": "not in this game"}
        if (player, n) in self._counted:
            return {"ok": True, "pct": accuracy_any(want, typed), "counted": False}
        self._counted.add((player, n))
        pct = accuracy_any(want, typed)
        s = self.stat(player)
        s["copies"] += 1
        if pct >= HIT_PCT:
            s["clean"] += 1
        return {"ok": True, "pct": pct, "counted": True}

    # --------------------------------------------------------- the runners
    def _advance(self, bases):
        """Every runner moves up `bases`; runs that score are counted.
        Returns whether anybody moved."""
        team = self.batting()
        moved = False
        new = [None, None, None]
        scored = 0
        for i, r in enumerate(self.bases):
            if r is None:
                continue
            moved = True
            to = i + bases
            if to >= 3:
                scored += 1
            else:
                new[to] = r
        self.bases = new
        self.runs[team] += scored
        if self.last is not None and scored:
            self.last["scored"] = self.last.get("scored", 0) + scored
        return moved

    def _reach(self, play, bases, forced=False, count_hit=True):
        """The batter reaches; the runners move up that many - or, forced,
        only as far as they must."""
        team = self.batting()
        bases = min(4, max(1, int(bases)))
        scored = 0
        if forced:
            # a walk or a fielder's choice: a runner moves only if pushed
            new = list(self.bases)
            runner = self.batter
            i = 0
            while runner is not None and i < 3:
                runner, new[i] = new[i], runner
                i += 1
            if runner is not None:
                scored += 1
            self.bases = new
        else:
            new = [None, None, None]
            for i, r in enumerate(self.bases):
                if r is None:
                    continue
                to = i + bases
                if to >= 3:
                    scored += 1
                else:
                    new[to] = r
            if bases >= 4:
                scored += 1
            else:
                new[bases - 1] = self.batter
            self.bases = new
        self.runs[team] += scored
        if count_hit and play.get("result") not in ("walk", "error", "force out"):
            self.hits[team] += 1
        play["scored"] = play.get("scored", 0) + scored
        play["hit"] = bases
        if scored:
            play["words"] += f" - {scored} run{'s' if scored > 1 else ''} score{'' if scored > 1 else 's'}"
        self.next_up[team] += 1
        self.strikes = 0
        self.balls = 0
        self._reveal(play)

    def _out(self, play):
        team = self.batting()
        self.outs += 1
        self.next_up[team] += 1
        self.strikes = 0
        self.balls = 0
        play["outs"] = self.outs
        if self.outs >= 3:
            play["side"] = True
            self._retire(play)
        else:
            self._reveal(play)

    def _retire(self, play):
        team = self.batting()
        self.line[team].append(self.runs[team] - sum(self.line[team]))
        self.bases = [None, None, None]
        self.outs = 0
        self.strikes = 0
        self.balls = 0
        self.fielder = None
        self.link = None
        self.chain = []
        if self.half == "top":
            self.half = "bottom"
        else:
            if self.inning >= self.innings and self.runs["A"] != self.runs["B"]:
                self.phase = "over"
                self.winner = "A" if self.runs["A"] > self.runs["B"] else "B"
                play["words"] += f" - that's the game: {self.runs['A']} to {self.runs['B']}"
                self.last = play
                self.plays.append(play)
                return
            self.half = "top"
            self.inning += 1
        play["words"] += " - side retired"
        self.last = play
        self.plays.append(play)
        self.phase = "between"
        self.deadline = _now() + BETWEEN_SECONDS

    def _reveal(self, play):
        self.last = play
        self.plays.append(play)
        self.fielder = None
        self.link = None
        self.chain = []
        self.phase = "reveal"
        self.deadline = _now() + REVEAL_SECONDS

    # -------------------------------------------------------- the practice
    def _actor(self):
        if self.phase == "windup":
            return self.pitcher
        if self.phase == "pitch":
            return self.batter
        if self.phase == "field":
            return self.fielder
        return None

    def _plan_bot(self):
        """A practice player's act, planned for a moment in the window."""
        self._bot_at = None
        who = self._actor()
        if who in self.bots:
            span = max(0.5, self.deadline - _now())
            self._bot_at = _now() + span * self.rng.uniform(0.3, 0.7)

    def _bot_act(self):
        who = self._actor()
        level = self.bots.get(who)
        if level is None:
            self._bot_at = None
            return
        r = self.rng
        if self.phase == "windup":
            if self.link == "pick":
                self.choose(who, "hard" if self.league == "major" and r.random() < 0.3 else "normal")
            want = cw.plain(self.pitch["text"])
            roll = r.random()
            odds = BOT_FIELD.get(level, 0.5)
            keyed = want if roll < odds else (want[:-1] + "?" if roll < odds + 0.3 else "??")
            self.deliver(who, keyed, self.pitch["wpm"])
        elif self.phase == "pitch":
            want = self.pitch["want"]
            clean = r.random() < BOT_SWING.get(level, 0.5)
            self.swing(who, want if clean else want[:max(1, len(want) // 2)] + "?")
        elif self.phase == "field":
            if self.link == "catch":
                want = self.pitch["want"]
                clean = r.random() < BOT_SWING.get(level, 0.5)
                self.catch(who, want if clean else want[:max(1, len(want) // 2)] + "?")
            elif self.link == "throw":
                text = self.pitch.get("key") or self.pitch["sent"]
                roll = r.random()
                odds = BOT_FIELD.get(level, 0.5)
                self.throw(who, text if roll < odds else (text[:-1] + "?" if roll < odds + 0.3 else "??"))
            elif self.link == "tag":
                want = self.pitch.get("throw") or self.pitch["key"]
                clean = r.random() < BOT_SWING.get(level, 0.5)
                self.tag(who, want if clean else want[:-1] + "?")

    # ---------------------------------------------------------------- clock
    def tick(self, now=None):
        """What time does: a practice player acts when its moment comes; a
        pitcher who never throws has thrown a ball; a pitch nobody swung at
        is taken; a catch, a throw or a tag never made is the runner safe;
        a reveal ends and the next pitch comes."""
        now = _now() if now is None else now
        if self.phase == "over":
            return
        if self._bot_at is not None and now >= self._bot_at:
            self._bot_act()
            return
        if now < self.deadline:
            return
        if self.phase == "windup":
            self._wild(self.pitcher, "")
            self.last["result"] = "delay"
            self.last["words"] = f"{self.name(self.pitcher)} never threw it - the pitch clock, ball {self.balls}"
        elif self.phase == "pitch":
            self.take(self.batter)
        elif self.phase == "field":
            play = self.last
            if self.link == "throw":
                self.throw(self.fielder, "", late=True)
            else:
                play["result"] = "safe"
                play["words"] = (f"{self.name(self.fielder)} never made the "
                                 f"{'catch' if self.link == 'catch' else 'tag'} in time - "
                                 f"{self.name(play['batter'])} is safe")
                self._reach(play, play["hit_bases"])
        elif self.phase in ("reveal", "between"):
            self.new_pitch()

    # ------------------------------------------------------------ the view
    def your_link(self, player_id):
        """What this device is asked for right now, or None: pick and
        throw_pitch on the mound, swing at the plate, catch, throw or tag in
        the field. Everybody else copies the pitch and holds it."""
        if player_id is None:
            return None
        if self.phase == "windup" and player_id == self.pitcher:
            return self.link
        if self.phase == "pitch" and player_id == self.batter:
            return "swing"
        if self.phase == "field" and player_id == self.fielder:
            return self.link
        return None

    def as_dict(self, player_id=None):
        lead = "A" if self.runs["A"] > self.runs["B"] else "B" if self.runs["B"] > self.runs["A"] else None
        p = self.pitch
        hidden = ("text", "plain", "want", "answer", "key", "sent", "call", "throw", "pitch_pct", "off_speed")
        if p and self.phase == "windup":
            pitch = {k: v for k, v in p.items() if k not in hidden}
            if player_id == self.pitcher and p.get("text"):
                pitch["text"] = p["text"]              # the prompt, to the pitcher alone
        elif p and self.phase == "pitch":
            pitch = {k: v for k, v in p.items() if k not in hidden}
        elif p and self.phase == "field":
            # the fielder with the ball is told what to key; the baseman hears
            # the throw and is never shown it
            pitch = {k: v for k, v in p.items() if k not in ("text", "call", "pitch_pct", "off_speed", "throw")}
            if self.link != "tag":
                pitch.pop("throw_groups", None); pitch.pop("throw_timing", None)
        else:
            pitch = None
        link = self.your_link(player_id)
        return {
            "inning": self.inning, "half": self.half, "innings": self.innings, "outs": self.outs,
            "strikes": self.strikes, "balls": self.balls, "phase": self.phase, "over": self.over(),
            "winner": self.winner, "league": self.league, "pitcher_mode": self.pitcher_mode,
            "runs": dict(self.runs), "line": {k: list(v) for k, v in self.line.items()},
            "hits": dict(self.hits), "errors": dict(self.errors), "lead": lead,
            "bases": [{"player": r, "name": self.name(r)} if r is not None else None for r in self.bases],
            "batting": self.batting(), "fielding": self.fielding(),
            "batter": self.batter, "batter_name": self.name(self.batter) if self.batter is not None else None,
            "pitcher": self.pitcher, "pitcher_name": self.name(self.pitcher) if self.pitcher is not None else "the machine",
            "fielder": self.fielder, "fielder_name": self.name(self.fielder) if self.fielder is not None else None,
            "link": self.link if self.phase in ("windup", "field") else None,
            "positions": {pos: {"player": pl, "name": self.name(pl)} for pos, pl in self.positions().items()},
            "pitch": pitch,
            "deadline_in": max(0.0, round(self.deadline - _now(), 1)),
            "last": self.last, "level": LEVELS[self.level()]["name"], "wpm": self.wpm(),
            "lineups": {k: [{"player": pl, "name": self.name(pl)} for pl in v] for k, v in self.lineups.items()},
            "stats": {str(k): dict(v) for k, v in self.stats.items()},
            "your_link": link,
            "your_swing": link == "swing",
            # the little league's "again": offered to the batter while the
            # machine pitches, this many at most
            "again_most": AGAIN_MOST if self.league == "little" and self.pitcher is None else 0,
            "your_throw": link in ("throw",),
            "your_team": next((k for k, v in self.lineups.items() if player_id in v), None),
            # everybody copies every pitch and holds it: the token is the pitch
            # number, and the copy is handed up when your_link says catch or
            # tag, or as readiness with a poll after the play
            "hold": p["n"] if p and self.phase in ("pitch", "field") else None,
        }
