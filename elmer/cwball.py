"""CW Baseball: the rules. Two teams, and the machine pitches.

Batting is copying. A pitch is a transmission - its speed, its length and
what it holds rise with the level: letters, then groups, then words, then a
callsign and a report, then a full exchange - and copying it clean is a hit
sized by the pitch: a group a single, a word a double, a callsign and a
report a triple, a full exchange a home run. A near miss is a foul (a strike
until there are two), a miss is a strike, three strikes an out, three outs
the side.

Fielding is sending. A ball in play is a sending challenge for the fielding
side: key the ball back - the text of the pitch - clean and in time, on a
straight key, a paddle, or a phone's touch key. A clean send makes the out.
A botched one lets the runner on. A bad one is an error, and gives a base.

Innings, runs on the board, a diamond with the runners on it for the fanatics
who will do code to watch a fake ballgame play out, and the late innings
faster and longer. The top pitch is a contact: CQ from the pitcher, the
batter answers with their own call, reports both ways, 73.

Nothing here plays sound or reads a key. The room says who copied what and
who keyed what; this says what it was worth. The timing of a copy or a send
is the room's clock; the rules take a deadline and a now.
"""
import random
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
HIT_PCT = 90                    # copied this clean is a hit
FOUL_PCT = 60                   # this clean is a foul: a strike until there are two
OUT_PCT = 90                    # keyed this clean makes the out
ERROR_PCT = 50                  # keyed worse than this is an error, and a base
COPY_SECONDS = 2.2              # per character, to type it after it sounds
COPY_LEAST = 12.0
FIELD_SECONDS = 4.0             # per character, to key it back
FIELD_LEAST = 12.0
REVEAL_SECONDS = 9.0            # the play stands on the screens
BETWEEN_SECONDS = 12.0          # the side retires; the board is read
INNING_WPM = 1.5                # faster each inning
BOT_SWING = {"Listener": 0.4, "Learner": 0.55, "Operator": 0.72, "Elmer": 0.86}   # a practice player's copy
BOT_FIELD = {"Listener": 0.35, "Learner": 0.5, "Operator": 0.68, "Elmer": 0.82}   # and its send


def _now():
    return time.monotonic()


def accuracy(want, got):
    """Characters right, in order, as a percentage of what was asked."""
    a = "".join(str(want or "").upper().split())
    b = "".join(str(got or "").upper().split())
    if not a:
        return 0
    hits = sum(1 for i, c in enumerate(a) if i < len(b) and b[i] == c)
    return int(round(100 * hits / len(a)))


class Baseball:

    def __init__(self, lineups, names=None, innings=3, base_wpm=10.0, seed=None, bots=None):
        """`lineups` {"A": [player ids], "B": [...]} in batting order; A bats
        first. `names` player -> name. `bots` player -> level for practice
        players, who copy and key by their level's odds."""
        self.rng = random.Random(seed)
        self.lineups = {"A": list(lineups.get("A") or []), "B": list(lineups.get("B") or [])}
        self.names = dict(names or {})
        self.bots = dict(bots or {})
        self.innings = max(1, int(innings))
        self.base_wpm = max(5.0, float(base_wpm))
        self.inning = 1
        self.half = "top"                 # A bats in the top, B in the bottom
        self.outs = 0
        self.strikes = 0
        self.bases = [None, None, None]   # first, second, third: the player on it
        self.runs = {"A": 0, "B": 0}
        self.line = {"A": [], "B": []}    # runs an inning
        self.hits = {"A": 0, "B": 0}
        self.errors = {"A": 0, "B": 0}
        self.next_up = {"A": 0, "B": 0}
        self.next_fielder = {"A": 0, "B": 0}
        self.phase = "between"            # pitch | field | reveal | between | over
        self.deadline = _now() + 3.0
        self.pitch = None
        self.batter = None
        self.fielder = None
        self.last = None                  # the last play, for the screens
        self.plays = []
        self.winner = None
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

    def level(self):
        """The pitch's level: the inning's, capped below the top - and the
        last inning of the game, whatever number it is, pitches the contact
        every other time, so the end-game is the air itself."""
        if self.inning >= self.innings and self.inning > 1 and self.rng.random() < 0.5:
            return len(LEVELS) - 1
        return min(len(LEVELS) - 2, self.inning - 1)

    def wpm(self):
        return round(self.base_wpm + INNING_WPM * (self.inning - 1), 1)

    # --------------------------------------------------------------- pitches
    def _text(self, level):
        kind = LEVELS[level]["kind"]
        r = self.rng
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if kind == "letters":
            return "".join(r.choice(letters) for _ in range(3))
        if kind == "group":
            return "".join(r.choice(letters + "0123456789") for _ in range(5))
        if kind == "word":
            return r.choice(WORDS)
        if kind == "call":
            return f"{r.choice(PREFIXES)}{''.join(r.choice(letters) for _ in range(r.choice((2, 3))))} 5{r.choice('789')}9"
        call = f"{r.choice(PREFIXES)}{''.join(r.choice(letters) for _ in range(3))}"
        if kind == "contact":
            return f"CQ CQ CQ DE {call} {call} K"
        return f"CQ CQ DE {call} {call} K"

    def new_pitch(self):
        """The next pitch, to the next batter. Phase: pitch."""
        team = self.batting()
        order = self.lineups[team]
        if not order:
            self.phase = "over"
            self.winner = self.fielding()
            return None
        self.batter = order[self.next_up[team] % len(order)]
        level = self.level()
        text = self._text(level)
        wpm = self.wpm()
        chars = len(text.replace(" ", ""))
        timing = cw.timing(wpm, wpm)
        # how long the pitch sounds, then how long to type it
        sounds = sum(len(cw.MORSE.get(c, "")) for c in text.replace(" ", "")) * 2.5 * timing["dit"] / 1000.0 + \
            len(text.split()) * timing["word_gap"] / 1000.0
        kind = LEVELS[level]["kind"]
        # what each side must produce: the whole text, except in a contact -
        # the batter copies the call that was heard, the fielder answers it
        called = text.split()[3] if kind == "contact" else None
        self.pitch = {"n": len(self.plays) + 1, "kind": kind, "name": LEVELS[level]["name"],
                      "bases": LEVELS[level]["bases"], "text": text, "plain": cw.plain(text),
                      "groups": cw.encode(text), "timing": timing, "wpm": wpm,
                      "want": called or cw.plain(text),
                      "answer": (f"{called} DE" if called else None),
                      "sounds": round(sounds, 1), "window": round(max(COPY_LEAST, chars * COPY_SECONDS), 1)}
        self.phase = "pitch"
        self.deadline = _now() + self.pitch["sounds"] + self.pitch["window"]
        self.fielder = None
        self._plan_bot()
        return self.pitch

    def _plan_bot(self):
        """A practice player's swing or throw, planned for a moment in the window."""
        self._bot_at = None
        who = self.batter if self.phase == "pitch" else self.fielder
        if who in self.bots:
            span = self.deadline - _now()
            self._bot_at = _now() + span * self.rng.uniform(0.4, 0.8)

    def _bot_act(self):
        who = self.batter if self.phase == "pitch" else self.fielder
        level = self.bots.get(who)
        if level is None:
            self._bot_at = None
            return
        text = self.pitch["plain"]
        if self.phase == "pitch":
            want = self.pitch["want"]
            clean = self.rng.random() < BOT_SWING.get(level, 0.5)
            self.swing(who, want if clean else want[:max(1, len(want) // 2)] + "?")
        else:
            text = self.pitch.get("key") or text
            roll = self.rng.random()
            odds = BOT_FIELD.get(level, 0.5)
            got = text if roll < odds else (text[:-1] + "?" if roll < odds + 0.3 else "??")
            self.field(who, got)

    # -------------------------------------------------------------- the play
    def swing(self, player, typed):
        """The batter's copy. Returns the play, or an error."""
        if self.phase != "pitch":
            return {"error": "no pitch to swing at"}
        if player != self.batter:
            return {"error": f"not your at-bat - {self.name(self.batter)} is up"}
        pct = accuracy(self.pitch["want"], typed)
        play = {"n": self.pitch["n"], "batter": player, "batter_name": self.name(player), "typed": str(typed or "")[:60],
                "pitch": self.pitch["plain"], "want": self.pitch["want"], "copy_pct": pct, "kind": self.pitch["kind"],
                "bases": self.pitch["bases"]}
        if pct >= HIT_PCT:
            play["result"] = "in play"
            play["words"] = f"{self.name(player)} copied {self.pitch['name']} clean - in play, {self.pitch['bases']} base{'s' if self.pitch['bases'] > 1 else ''} if it drops"
            self._to_field(play)
            return play
        if pct >= FOUL_PCT and self.strikes < 2:
            self.strikes += 1
            play["result"] = "foul"
            play["words"] = f"{self.name(player)} got {pct}% of it - foul ball, strike {self.strikes}"
            self._reveal(play)
            return play
        self.strikes += 1
        play["result"] = "strike"
        play["words"] = f"{self.name(player)} got {pct}% of it - strike {self.strikes}"
        if self.strikes >= 3:
            play["result"] = "strikeout"
            play["words"] = f"{self.name(player)} strikes out on {pct}%"
            self._out(play)
        else:
            self._reveal(play)
        return play

    def _to_field(self, play):
        team = self.fielding()
        order = self.lineups[team]
        if not order:
            self._hit(play, self.pitch["bases"])
            return
        self.fielder = order[self.next_fielder[team] % len(order)]
        self.next_fielder[team] += 1
        play["fielder"] = self.fielder
        play["fielder_name"] = self.name(self.fielder)
        # the fielder keys the text back - or, in a contact, answers the
        # call with their own: "W1AW DE KC9SP"
        if self.pitch.get("answer"):
            own = self.name(self.fielder).upper()
            own = own if own.replace("/", "").isalnum() and any(c.isdigit() for c in own) else "ELMER"
            self.pitch["key"] = f"{self.pitch['answer']} {own}"
        else:
            self.pitch["key"] = self.pitch["plain"]
        play["key"] = self.pitch["key"]
        self.last = play
        self.phase = "field"
        chars = len(self.pitch["plain"].replace(" ", ""))
        self.deadline = _now() + max(FIELD_LEAST, chars * FIELD_SECONDS)
        self._plan_bot()

    def field(self, player, keyed, late=False):
        """The fielder's send. Returns the play."""
        if self.phase != "field":
            return {"error": "nothing in play"}
        if player != self.fielder:
            return {"error": f"not your ball - {self.name(self.fielder)} has it"}
        play = dict(self.last or {})
        pct = 0 if late else accuracy(self.pitch.get("key") or self.pitch["plain"], keyed)
        play["keyed"] = str(keyed or "")[:60]
        play["field_pct"] = pct
        bases = self.pitch["bases"]
        if late:
            play["result"] = "safe"
            play["words"] = f"{self.name(player)} never got the throw off - {self.name(play['batter'])} is safe"
            self._hit(play, bases)
        elif pct >= OUT_PCT:
            play["result"] = "out"
            play["words"] = f"{self.name(player)} keyed it clean - {self.name(play['batter'])} is out"
            self._out(play)
        elif pct >= ERROR_PCT:
            play["result"] = "safe"
            play["words"] = f"{self.name(player)} got {pct}% of the throw - {self.name(play['batter'])} is safe"
            self._hit(play, bases)
        else:
            play["result"] = "error"
            play["words"] = f"{self.name(player)} botched it ({pct}%) - error, an extra base"
            self.errors[self.fielding()] += 1
            self._hit(play, bases + 1)
        return play

    def _hit(self, play, bases):
        """The batter reaches; the runners move up that many."""
        team = self.batting()
        bases = min(4, max(1, int(bases)))
        scored = 0
        runners = [self.batter] + [r for r in self.bases if r is not None]
        new = [None, None, None]
        # everybody advances `bases`: the batter from home, the others from theirs
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
        self.hits[team] += 1
        play["scored"] = scored
        play["hit"] = bases
        if scored:
            play["words"] += f" - {scored} run{'s' if scored > 1 else ''} score{'' if scored > 1 else 's'}"
        self.next_up[team] += 1
        self.strikes = 0
        self._reveal(play)
        del runners

    def _out(self, play):
        team = self.batting()
        self.outs += 1
        self.next_up[team] += 1
        self.strikes = 0
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
        self.phase = "reveal"
        self.deadline = _now() + REVEAL_SECONDS

    # ---------------------------------------------------------------- clock
    def tick(self, now=None):
        """What time does: a practice player acts when its moment comes; a
        pitch nobody swung at is a strike looking; a throw nobody made is
        the runner safe; a reveal ends and the next pitch comes."""
        now = _now() if now is None else now
        if self.phase == "over":
            return
        if self._bot_at is not None and now >= self._bot_at:
            self._bot_act()
            return
        if now < self.deadline:
            return
        if self.phase == "pitch":
            self.swing(self.batter, "")
        elif self.phase == "field":
            self.field(self.fielder, "", late=True)
        elif self.phase in ("reveal", "between"):
            self.new_pitch()

    # ------------------------------------------------------------ the view
    def as_dict(self, player_id=None):
        lead = "A" if self.runs["A"] > self.runs["B"] else "B" if self.runs["B"] > self.runs["A"] else None
        return {
            "inning": self.inning, "half": self.half, "innings": self.innings, "outs": self.outs,
            "strikes": self.strikes, "phase": self.phase, "over": self.over(), "winner": self.winner,
            "runs": dict(self.runs), "line": {k: list(v) for k, v in self.line.items()},
            "hits": dict(self.hits), "errors": dict(self.errors), "lead": lead,
            "bases": [{"player": r, "name": self.name(r)} if r is not None else None for r in self.bases],
            "batting": self.batting(), "fielding": self.fielding(),
            "batter": self.batter, "batter_name": self.name(self.batter) if self.batter is not None else None,
            "fielder": self.fielder, "fielder_name": self.name(self.fielder) if self.fielder is not None else None,
            "pitch": ({k: v for k, v in self.pitch.items() if k not in ("text", "plain", "want", "answer", "key")}
                      if self.pitch and self.phase == "pitch" else
                      dict(self.pitch) if self.pitch and self.phase == "field" else None),
            "deadline_in": max(0.0, round(self.deadline - _now(), 1)),
            "last": self.last, "level": LEVELS[self.level()]["name"], "wpm": self.wpm(),
            "lineups": {k: [{"player": p, "name": self.name(p)} for p in v] for k, v in self.lineups.items()},
            "your_swing": bool(player_id is not None and self.phase == "pitch" and player_id == self.batter),
            "your_throw": bool(player_id is not None and self.phase == "field" and player_id == self.fielder),
            "your_team": next((k for k, v in self.lineups.items() if player_id in v), None),
        }
