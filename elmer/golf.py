"""Golf - a round on a real course, a question a stroke.

KC9SP's game, modelled on the real one. The course is a real one - Pebble
Beach, the Old Course, Augusta - from its card: each hole's par and yards,
the hazards along the line, the wind it usually has. A stroke is a
question. Answer it right and the ball flies; answer it wrong and it is a
foul ball - into the rough, the sand, the water, over the cliff for a
drop and a stroke.

**One at a time.** Golf is not a race. The player who is away - farthest
from the hole; on the tee, the honour, which is the best score on the
last hole - plays, and the rest of the group watches. Nothing in a round
of golf is timed: a golfer rushed at the tee is not playing golf, so the
clock has no say in the shot and no screen shows one. The room waits on
the player who is away for as long as they take.

**The shot.** With the question the player chooses a club - driver,
wood, iron, wedge; on the green it is the putter and nothing else - and
the club sets how far the ball goes. A club that can reach the pin is
hit at it and lands within a few yards of it, either side; one that
cannot is a full swing and goes its length. The wind adds or takes
yards, and the lie the ball was in takes some too: rough costs a fifth,
sand allows only a wedge and costs more. Where the ball lands is checked
against the course. A correct driver that carries into Rae's Creek is
golf, and the player chose the driver.

**Foul balls.** A wrong answer finds the nearest trouble the club could
have reached: water most often means a drop where you were and a penalty
stroke; sand means you are in it; rough means a short one that did go
forward. Trouble that was not in reach of the club is not in reach of the
foul ball either - a wedge from the fairway cannot find a bunker two
hundred yards on.

**The green.** On it, the game is putting, and putting is about being
right, not fast: a correct answer holes it, a wrong one is a missed putt
and another stroke. A player who has not holed after par plus three
picks up and takes that, the way casual golfers do, so a hole has a
bounded number of questions and the table moves on together.

**What is asked.** Golf is the slow game: the one for sitting and
reasoning an answer through, talking radio with friends between strokes,
nobody missing a shot to a clock. So the questions have a thread. Each
hole takes one test area - a section of the pool, drawn from those not
yet played this round - and stays on it until its questions run out,
then takes another. Once every question in the pool has been asked
once, the ones missed come round again first; after those, the order is
by how hard the questions have measured on this unit, matched to the
shot at hand: a ball on the tee or the fairway gets an easier one, a
ball in the rough or the sand a harder one. A bad lie has its say.

**Scoring** is real golf: strokes against the card - eagle, birdie, par,
bogey and the rest - lowest total over the round wins. A handicap, if the
table switched it on, is strokes given, taken off at the end: a poor
player and a fair one can play the same card. A tie for the lead at the
end is a playoff, hole by hole, sudden death.

**The wind is drawn each round** around the hole's typical, so no two
rounds play the same; the 12th at Augusta swirls, which means it is drawn
for every shot.

Nothing here has a clock or a question in it. The room says who is away,
which club they chose and whether they were right; this says where the
ball went, in yards and in words - the playback - and who is winning.
"""
import json
import random
from pathlib import Path

COURSES_DIR = Path(__file__).resolve().parents[1] / "data" / "golf"

# The most a club can carry, in yards, from a good lie with a fast answer.
CLUBS = {"driver": 250, "wood": 210, "iron": 165, "wedge": 105}
CLUB_ORDER = ("driver", "wood", "iron", "wedge")
# What the lie costs: a factor on the carry, and the longest club allowed.
LIES = {
    "tee": (1.0, "driver"), "fairway": (1.0, "driver"),
    "rough": (0.8, "wood"), "sand": (0.6, "wedge"),
}
# A shot the club can reach the pin with is aimed at it, and lands within
# this many yards of it, either side. Full swings are for when the club
# cannot reach, and go the club's length. Both within the club's spread.
AIM = 12
# The club's say in where a fair ball lands. A right answer flies the ball,
# but a driver is longer and wilder than an iron: the spread is how far
# long or short of the mark it can land, and the leak is the chance it
# drifts off the line into the first cut or whatever is out there - a
# bunker, the rough - never the water and never out of bounds, which are a
# wrong answer's to find. "Less bad luck." It is what puts variety in the
# lies after a good tee shot, and so in who is away next.
# Where within the spread, and whether it leaks, is the swing's timing: the
# milliseconds the answer took seed the draw for that stroke. Not a clock -
# a quick answer is no straighter than a slow one - but the same swing
# twice lands the same way, and every stroke lands a little differently,
# which is what a golfer means by luck.
CLUB_SPREAD = {"driver": 18, "wood": 14, "iron": 9, "wedge": 5}
CLUB_LEAK = {"driver": 0.18, "wood": 0.12, "iron": 0.06, "wedge": 0.02}
# The hole has a width. A ball is so many yards along the line and so many
# off it - left negative, right positive. Inside FAIRWAY_HALF either side
# is the fairway (or whatever band crosses it); beyond it are the sides,
# where the card's left and right hazards live, and the first cut where
# nothing does. A green is GREEN_HALF wide either side of the pin. The
# mark a golfer aims at is a point in the same yards, and the leak is a
# push of LEAK_PUSH yards off to one side.
FAIRWAY_HALF = 18
GREEN_HALF = 14
OFF_MOST = 45
LEAK_PUSH = 10
# A ball does not stick where it lands. Carry, then roll: the club sets
# how much life the ball has when it comes down - a driver's low, running
# ball has a lot, a wedge's high, spinning one almost none - the surface it
# lands on sets how much of that it keeps, and the wind pushes the roll
# along or holds it up. A crosswind drifts the ball in flight, from the
# side the course says it blows off. What is left after all of that is
# where the ball lies, and where the hazards are read. The mark is where
# the ball comes down; a golfer who wants it to stop short of the creek
# lands it shorter still, as on a course.
# The green. Everyone wants the cup, and the green decides: a putt is
# rolled the distance to the mark, give or take a pace that grows with the
# length, and the slope has its say - downhill runs long, uphill comes up
# short, and a cross-slope breaks the line toward the fall. A ball that
# passes over the cup with pace to spare drops; too much pace and it lips
# out and runs on. Inside TAP_IN feet of the cup is good - a stroke, no
# question. A wrong answer is a bad stroke: never up, or raced past.
CUP_CAPTURE = 0.7               # feet either side of the cup a putt with pace drops in
CUP_OVERRUN = 4.0               # feet past the cup a putt may still have and drop
TAP_IN = 2.0                    # feet: that's good
PUTT_PACE = (0.08, 300.0)       # the pace's spread: eight percent, plus a foot in three hundred
SLOPE_PACE = 0.06               # per percent of grade, on a putt straight up or down it
SLOPE_BREAK = 0.035             # feet of break per foot rolled, per percent of grade
PUTT_LINE = 4.0                 # degrees either side of the line a right answer's putt may start on
DEFAULT_SLOPE = {"falls": "front", "grade": 1.5}
FALLS = {"front": (-1.0, 0.0), "back": (1.0, 0.0), "left": (0.0, -1.0), "right": (0.0, 1.0)}
ROLL = {"driver": 24, "wood": 18, "iron": 9, "wedge": 3}
SURFACE_ROLL = {"fairway": 1.0, "green": 0.45, "rough": 0.3, "sand": 0.0, "tee": 1.0}
WIND_ROLL = {"with": 1.4, "into": 0.6, "across": 1.0}
WIND_DRIFT = 0.35               # yards of sideways drift per mile an hour, across
ROLL_NOISE = (0.6, 1.4)         # the bounce: the roll, times somewhere in here
SIDE_BANDS = {"": ("across", "front", "centre", "around", "beyond", ""),
              "left": ("left", "around"), "right": ("right", "around")}


def side_of(off):
    """Which side of the hole a ball this far off the line is on: '' for
    the fairway's width, 'left' or 'right' beyond it."""
    if off < -FAIRWAY_HALF:
        return "left"
    if off > FAIRWAY_HALF:
        return "right"
    return ""
LEAK_CALLS = ["Leaked it.", "Pushed it a touch.", "Pulled it a hair.", "That got away from him."]
# Yards per mile an hour, by how the wind sits on the line.
WIND_EFFECT = {"with": 0.6, "into": -0.8, "across": -0.2}
# Where a hole ends: picked up at par plus this many.
PICK_UP_OVER = 3
# The shots worth making. Golf is about the shots - good, bad and regular -
# and some are shaped on purpose: a hook worked around the trees, a stinger
# punched under the wind, a flop over the sand to a tap-in, the approach
# that goes in. Here they are earned by an adept answer: a right answer on
# a question this unit has measured as hard, or the third right answer in a
# row. Which shot depends on where the ball is; the ball still obeys the
# course, it just gets the shot a good golfer would have played from there.
ADEPT_HARDNESS = 0.6            # of the unit's own 0..1 measure; see difficulty.py
ADEPT_STREAK = 3                # right answers in a row, when nothing is measured
HOLE_OUT_ODDS = 1 / 6           # an adept approach from inside HOLE_OUT_FROM yards
HOLE_OUT_FROM = 120
FLAIR_CALLS = {
    "worked": ["Worked it around the trees.", "Shaped it out of there.", "Hooked it on purpose, and it came back."],
    "stinger": ["A stinger, under the wind.", "Punched it. The wind never saw it.", "Kept it low. That's the shot."],
    "flop": ["Flopped it to a tap-in.", "Straight up, straight down. Kick-in.", "That's a touch shot."],
    "holed-out": ["Holed it from the fairway!", "It's IN. From out there.", "Walked it in from the fairway."],
    "launched": ["Launched it.", "That one's still going.", "Nuked it."],
    "pure": ["Pured it. Stiff.", "All over the flag.", "Pin high, and close."],
}

# A hole in one. Real on a par 3 - about one in twelve thousand for an
# amateur, which nobody would ever see here - so a right answer from the tee
# of a par 3 drops with these odds instead: rare, and possible, which is
# what an ace is. Never on a par 4 or 5, where the real world says almost
# never and the game says never.
ACE_ODDS = 0.02
# What a golfer says at the moment of contact, by what the ball did. The
# screens show it big, so somebody knows what they hit without reading the
# coloured answer - and a clip of the swing can go with it later; the
# reveal looks for static/golf/clips/<kind>.gif and shows it if it is there.
CALLS = {
    "fairway": ["Pured it.", "Right down the middle.", "That'll play.", "Nice shot!", "On the fairway."],
    "green": ["On the dance floor.", "Stuck it.", "That's looking at it.", "Nice shot!"],
    "long": ["Flew the green.", "Too much club.", "Airmailed it."],
    "holed": ["In the hole!", "Drained it.", "Bottom of the cup."],
    "rough": ["Topped it.", "Fat. Chunked it.", "Skied that one.", "In the rough."],
    "sand": ["Sliced it into the sand.", "Pulled it into the bunker.", "Beach.", "Found the bunker."],
    "water": ["Hooked it into the water.", "Wet.", "That's a splash - what was the wind?",
              "That's swimming.", "Are you going after that?"],
    "missed": ["Lipped out.", "Left it short.", "Burned the edge."],
}
# How hard a question the lie asks for, as a place in the pool's measured
# hardness - nought the easiest, one the hardest. The tee is a fresh start;
# the sand is not.
LIE_HARDNESS = {"tee": 0.25, "fairway": 0.35, "green": 0.5, "rough": 0.7, "sand": 0.85}
NAMES = {-3: "albatross", -2: "eagle", -1: "birdie", 0: "par", 1: "bogey",
         2: "double bogey", 3: "triple bogey"}


def courses():
    """Every course shipped, by id, friendliest first."""
    out = {}
    for path in sorted(COURSES_DIR.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        out[c["id"]] = c
    order = {"technician": 0, "general": 1, "extra": 2}
    return dict(sorted(out.items(), key=lambda kv: order.get(kv[1].get("pool"), 9)))


def course(course_id):
    return courses()[course_id]


def course_for_pool(pool):
    """The course that goes with a pool - Pebble Beach for Technician, the
    Old Course for General, Augusta for Extra."""
    for c in courses().values():
        if c.get("pool") == pool:
            return c
    return None


def score_name(strokes, par):
    d = strokes - par
    if d in NAMES:
        return NAMES[d]
    return f"{d:+d}"


def handicap_from_accuracy(accuracy, holes=18):
    """Strokes given over `holes` holes, from a player's share of right
    answers. Nine in ten and better plays scratch; one in two gets a
    stroke a hole. A round of nine gets half."""
    if accuracy is None:
        return 0
    acc = max(0.0, min(1.0, float(accuracy)))
    full = 0 if acc >= 0.9 else round((0.9 - acc) / 0.4 * 18)
    return max(0, min(18, full)) * holes // 18


class Ball:
    """One player's ball on one hole."""

    def __init__(self):
        self.at = 0            # yards from the tee, along the line
        self.off = 0           # yards off the line: left negative, right positive
        self.last_aim = None   # where the last stroke was aimed, for the strip to show beside where it went
        self.lie = "tee"
        self.strokes = 0
        self.holed = False
        self.picked_up = False
        self.log = []          # the playback, a line per stroke

    def done(self):
        return self.holed or self.picked_up


class Golf:

    def __init__(self, players, course, holes=None, handicaps=None, seed=None, seconds=30.0):
        """`players` in seating order; `course` a course dict; `holes` the
        hole numbers to play (default the front nine); `handicaps` strokes
        given per player over the round, or None for none."""
        self.players = list(players)
        self.course = course
        # The front nine unless told otherwise - the course's first nine,
        # which on a course with fewer holes is what it has.
        self.holes = list(holes) if holes else [h["n"] for h in course["holes"]][:9]
        self.round_holes = list(self.holes)      # the card; a playoff adds holes but not to it
        self.handicaps = dict(handicaps or {})
        self.seconds = float(seconds)
        self.rng = random.Random(seed)
        self.cards = {p: {} for p in self.players}      # player -> hole n -> strokes
        self.hole_index = 0
        self.swing = self.rng          # this stroke's draw; seeded by its timing when known
        self.aims = {}                 # player -> {"at", "off"}: the mark they set, for one stroke
        self._who = None               # whose stroke is being played
        # Not every golfer hits it the same. Power is a factor on every
        # club's length; wildness a factor on the leak. People are 1.0 and
        # 1.0 - the question is their swing. Practice players are given a
        # spread by the room, so a foursome is four different golfers.
        self.power = {p: 1.0 for p in self.players}
        self.wild = {p: 1.0 for p in self.players}
        self.balls = {}
        self.wind_mph = 0
        self.playoff = []          # players still in a playoff, if one
        self.playoff_holes = 0
        self._winner = None
        self.history = []
        # The thread of questions: how often each has been asked this
        # round, which were missed, the section each hole took, and how
        # hard the pool's questions have measured (set by the room).
        self.asked = {}
        self.missed = []
        self.sections_used = []
        self.hole_section = None
        self.hardness = {}
        self.tee_times = []             # who joins at the next tee, in order
        self.streak = {}                # right answers in a row, per player
        self._tee_off()

    # ---------------------------------------------------------------- holes

    def hole(self):
        n = self.holes[self.hole_index] if self.hole_index < len(self.holes) else None
        if n is None:
            return None
        return next(h for h in self.course["holes"] if h["n"] == n)

    def _tee_off(self):
        h = self.hole()
        if h is None:
            return
        typical = self.course.get("wind", {}).get("typical_mph", 10)
        self.wind_mph = max(0, round(typical * self.rng.uniform(0.6, 1.4)))
        # The tee is where a group is joined: whoever booked a tee time
        # during the last hole is in the group from this one.
        if not self.playoff:
            for p in self.tee_times:
                if p not in self.players:
                    self.players.append(p)
                    self.cards.setdefault(p, {})
            self.tee_times = []
        playing = self.playoff or self.players
        self.balls = {p: Ball() for p in playing}
        self.hole_section = None            # a new hole takes a new area

    def wind_from(self, h):
        """Which side a crosswind blows off on this course - the card says
        ("off the left"); left unless it says right."""
        said = str((self.course.get("wind") or {}).get("from") or "").lower()
        return "right" if "right" in said and "left" not in said else "left"

    def wind_on(self, h):
        """How the wind sits on this hole for this shot: swirling is drawn
        every time, which is what swirling means."""
        w = h.get("wind", "across")
        if w == "swirling":
            w = self.rng.choice(("with", "into", "across"))
        return w

    def over(self):
        return self._winner is not None or (self.hole() is None and not self.playoff)

    def winner(self):
        return self._winner

    # ---------------------------------------------------------------- clubs

    def clubs_for(self, player):
        """What this player may choose now, longest first; the putter alone
        on the green."""
        ball = self.balls.get(player)
        if ball is None or ball.done():
            return []
        if ball.lie == "green":
            return ["putter"]
        longest = LIES[ball.lie][1]
        return list(CLUB_ORDER[CLUB_ORDER.index(longest):])

    def default_club(self, player):
        """The sensible club: the shortest allowed that can reach the pin,
        since a club that reaches is aimed; the longest if none can."""
        allowed = self.clubs_for(player)
        if not allowed:
            return None
        if allowed == ["putter"]:
            return "putter"
        h = self.hole()
        ball = self.balls[player]
        left = abs(h["yards"] - ball.at)
        for club in reversed(allowed):
            if self.reach(player, club) >= left:
                return club
        return allowed[0]

    # ---------------------------------------------------------------- shots

    def set_swing(self, player, power=1.0, wild=1.0):
        """How this golfer hits it: a factor on the clubs' length and one
        on the leak. For the practice players; a person is 1.0 and 1.0."""
        self.power[player] = max(0.6, min(1.2, float(power)))
        self.wild[player] = max(0.3, min(3.0, float(wild)))

    def reach(self, player, club, lie=None):
        """How far this golfer's club goes from this lie."""
        lie = lie or self.balls[player].lie
        return CLUBS[club] * LIES[lie][0] * self.power.get(player, 1.0)

    def set_aim(self, player, at, off=0):
        """The golfer's mark: where they mean the ball to land, in yards
        along the line and off it. Theirs to set, for their next stroke,
        anywhere ahead of the ball and within the hole's width; the
        algorithm feeds the result. Returns the mark as kept, or None."""
        h = self.hole()
        ball = self.balls.get(player)
        if h is None or ball is None or ball.done():
            return None
        try:
            at, off = float(at), float(off)
        except (TypeError, ValueError):
            return None
        if ball.lie == "green":
            # On the green the mark is anywhere on it, in feet if need be:
            # the cup, or the spot above it the break wants.
            half = h["green"] / 2 + 2
            at = max(h["yards"] - half, min(h["yards"] + half, at))
            off = max(-(GREEN_HALF + 2), min(GREEN_HALF + 2, off))
            self.aims[player] = {"at": round(at, 2), "off": round(off, 2)}
            return dict(self.aims[player])
        at, off = int(round(at)), int(round(off))
        at = max(ball.at + 10, min(h["yards"] + 20, at))
        off = max(-OFF_MOST, min(OFF_MOST, off))
        self.aims[player] = {"at": at, "off": off}
        return dict(self.aims[player])

    def clear_aim(self, player):
        self.aims.pop(player, None)

    def aim(self, player):
        """Where this player's next stroke is aimed: their mark, or the
        sensible one - the pin, down the line."""
        h = self.hole()
        if h is None:
            return None
        mark = self.aims.get(player)
        if mark:
            return {"at": mark["at"], "off": mark["off"], "set": True}
        return {"at": h["yards"], "off": 0, "set": False}

    def expected_roll(self, club, lie="fairway", wind="across"):
        """How far a ball with this club is expected to run on after it
        lands there: what a golfer allows for when landing it short."""
        return ROLL.get(club, 0) * SURFACE_ROLL.get(lie, 1.0) * WIND_ROLL.get(wind, 1.0)

    def _carry(self, ball, club, wind, left):
        """How far the ball goes. A club that can reach the mark is hit at
        it and lands near it; one that cannot is a full swing and goes its
        length. The wind has its say on both. Nothing about the answer but
        that it was right reaches here: the swing is not timed."""
        most = CLUBS[club] * LIES[ball.lie][0] * self.power.get(self._who, 1.0)
        wind_yards = WIND_EFFECT.get(wind, 0.0) * self.wind_mph
        spread = CLUB_SPREAD.get(club, AIM)
        if most + wind_yards >= abs(left):
            # Aimed - at the pin, from either side of it, within the club's spread.
            return round(left + self.swing.uniform(-spread, spread) + wind_yards * 0.25)
        # A full swing: the club's length, give or take its spread.
        return max(10, round(most + wind_yards + self.swing.uniform(-spread, spread)))

    def _in_band(self, h, at, kinds=("water", "bunker", "rough"), sides=None):
        """The hazard a ball at `at` yards is in, if any, of these kinds and
        on these sides of the line - None means any side."""
        for hz in h.get("hazards", []):
            if hz["kind"] not in kinds:
                continue
            if sides is not None and hz.get("side", "") not in sides:
                continue
            if hz["from"] <= at <= hz["to"]:
                return hz
        return None

    def _fair(self, h, ball, club, adept=False):
        """A correct answer: the ball flies, and the course has its say. An
        adept answer gets the shot a good golfer would have played from
        there - see FLAIR_CALLS."""
        wind = self.wind_on(h)
        if club == "putter" or ball.lie == "green":
            return self._putt(h, ball, right=True, adept=adept)
        left_before = h["yards"] - ball.at
        # The mark: the pin down the line unless the golfer set one. The
        # shot is played at the mark; the pin is what is left after it.
        mark = self.aim(self._who) or {"at": h["yards"], "off": 0, "set": False}
        to_mark = mark["at"] - ball.at
        flair = None
        if adept:
            if left_before <= HOLE_OUT_FROM and self.rng.random() < HOLE_OUT_ODDS:
                ball.strokes += 1
                ball.at = h["yards"]
                ball.holed = True
                return {"kind": "holed", "words": f"{club}, {left_before} yards - holed it from the fairway",
                        "carry": left_before, "wind": wind, "flair": "holed-out"}
            if club == "wedge" and left_before <= 40:
                ball.strokes += 1
                ball.at = h["yards"] - 1
                ball.lie = "green"
                return {"kind": "green", "words": f"wedge, {left_before} yards - flopped it, to a tap-in, 3 feet",
                        "carry": left_before, "wind": wind, "feet": 3, "flair": "flop"}
            if ball.lie in ("rough", "sand"):
                flair = "worked"              # the lie does not cost: shaped out of it
            elif wind == "into":
                flair = "stinger"             # the wind does not cost: punched under it
            elif ball.strokes == 0:
                flair = "launched"            # off the tee: a little more of everything
        if flair == "worked":
            lie_was = ball.lie
            ball.lie = "fairway"
            carry = self._carry(ball, club, wind, to_mark)
            ball.lie = lie_was
        elif flair == "stinger":
            carry = self._carry(ball, club, None, to_mark)       # the wind's say, taken away
        elif flair == "launched":
            carry = round(self._carry(ball, club, wind, to_mark) * 1.12)
        elif adept and self.reach(self._who, club) >= to_mark:
            flair = "pure"                    # the club reaches: stiff, all over the mark
            carry = round(to_mark + self.rng.uniform(-4, 4))
        elif adept:
            flair = "launched"                # a full swing with everything in it
            carry = round(self._carry(ball, club, wind, to_mark) * 1.12)
        else:
            carry = self._carry(ball, club, wind, to_mark)
        landed = ball.at + carry
        # Across the line: at the mark's side of it, within the club's
        # spread - and, for a plain shot, the leak: a push off to one side.
        spread = CLUB_SPREAD.get(club, AIM) * 0.6
        off = mark["off"] + (self.swing.uniform(-4, 4) if flair == "pure" else self.swing.uniform(-spread, spread))
        leaked = None
        if not adept and self.swing.random() < CLUB_LEAK.get(club, 0.0) * self.wild.get(self._who, 1.0):
            leaked = "left" if (off < 0 if off else self.swing.random() < 0.5) else "right"
            off += -LEAK_PUSH if leaked == "left" else LEAK_PUSH
            if abs(off) <= FAIRWAY_HALF:              # a leak goes off the fairway, by definition
                off = (-1 if leaked == "left" else 1) * (FAIRWAY_HALF + 3)
        # A crosswind drifts the ball in flight, off the side it blows from.
        if wind == "across" and self.wind_mph:
            drift = WIND_DRIFT * self.wind_mph * (1 if self.wind_from(h) == "left" else -1)
            off += drift * (0.4 if flair == "stinger" else 1.0)
        off = int(round(max(-OFF_MOST, min(OFF_MOST, off))))
        from_the_tee = ball.strokes == 0
        ball.strokes += 1
        edge = h["green"] / 2 + 5                # the green's depth either side of the pin
        # Then the roll: the club's life, on the surface it came down on,
        # with the wind. A pure shot is stiff - it lands and stops; a flop
        # has already been dealt with. The ball is read where it comes to
        # rest, and a roll across a creek is a ball in the creek.
        came_down = "green" if (abs(h["yards"] - landed) <= edge and abs(off) <= GREEN_HALF) else \
            ("sand" if (self._in_band(h, landed, kinds=("bunker",), sides=SIDE_BANDS[side_of(off)])) else
             "rough" if (side_of(off) or self._in_band(h, landed, kinds=("rough",), sides=SIDE_BANDS[""])) else "fairway")
        roll = 0
        if flair != "pure":
            roll = ROLL.get(club, 0) * SURFACE_ROLL.get(came_down, 1.0) * WIND_ROLL.get(wind, 1.0) \
                * self.swing.uniform(*ROLL_NOISE)
        roll = int(round(roll))
        ran_through = None
        if roll:
            for y in range(landed + 1, landed + roll + 1):
                hz_on_the_way = self._in_band(h, y, kinds=("water", "bunker"), sides=SIDE_BANDS[side_of(off)])
                if hz_on_the_way:
                    ran_through, roll = hz_on_the_way, y - landed
                    break
        rest = landed + roll
        left = h["yards"] - rest
        if from_the_tee and h["par"] == 3 and self.rng.random() < ACE_ODDS:
            ball.at = h["yards"]
            ball.holed = True
            return {"kind": "holed", "words": f"{club}, {h['yards']} yards - IN THE HOLE. An ace.",
                    "carry": h["yards"], "wind": wind, "ace": True}
        side = side_of(off)
        on_green = abs(left) <= edge and abs(off) <= GREEN_HALF
        # On the green is on the green, whatever bunkers ring it. Off it,
        # what is where the ball came to rest: down the middle, a creek
        # across the fairway, a bunker in front of the green, the ocean
        # beyond it; off to a side, that side's trouble - or the first cut,
        # when the card has nothing there.
        hz = ran_through or (None if on_green or flair == "worked" else self._in_band(h, rest, sides=SIDE_BANDS[side]))
        landed = rest
        ran = (f", ran {roll} more" if roll >= 4 else ", checked up" if (came_down == "green" and roll <= 1 and club in ("iron", "wedge")) else "")
        wide = f" {side}" if side else ""
        if hz and hz["kind"] == "water":
            if side:
                # A right answer that drifted stops on the bank: no penalty,
                # a bad lie. The water is a wrong answer's to find.
                ball.at, ball.off, ball.lie = landed, off, "rough"
                return {"kind": "rough", "words": f"{club}, {carry} yards - out to the {side}, stopped on the bank of "
                                                  f"{hz['name'] or 'the water'} - {left} to go, from the rough",
                        "carry": carry, "wind": wind, "leak": leaked, "left": left, "off": off}
            ball.strokes += 1                        # the penalty
            how = "ran into" if ran_through else "into"
            return {"kind": "water", "words": f"{club}, {carry} yards - {how} {hz['name'] or 'the water'}; "
                                              f"drop, and a penalty stroke", "carry": carry, "roll": roll, "wind": wind,
                    "hazard": hz["name"]}
        if on_green:
            ball.at, ball.off = landed, off
            ball.lie = "green"
            feet = max(3, int(round((abs(left) ** 2 + off ** 2) ** 0.5 * 3)))
            onto = " - ran onto the green" if came_down != "green" and roll >= 4 else f"{ran} - on the green"
            return {"kind": "green", "words": f"{club}, {abs(carry)} yards{onto}, {feet} feet",
                    "carry": carry, "roll": roll, "wind": wind, "feet": feet, "flair": flair, "off": off}
        if side and not hz and abs(left) > edge:
            # Off the fairway's width, into the first cut - by the golfer's
            # own mark, or the club's leak.
            ball.at, ball.off, ball.lie = landed, off, "rough"
            how = f"leaked {side}" if leaked else f"out to the {side}"
            return {"kind": "rough", "words": f"{club}, {carry} yards{ran} - {how}, into the first cut - {left} to go",
                    "carry": carry, "roll": roll, "wind": wind, "leak": leaked, "left": left, "off": off}
        if left < -edge:
            # Over the back: rough beyond, or whatever is there.
            ball.at, ball.off = h["yards"], off
            ball.lie = "rough"
            how = "ran through the green" if came_down == "green" else "through the green"
            return {"kind": "long", "words": f"{club}, {carry} yards - {how}, into the rough behind",
                    "carry": carry, "roll": roll, "wind": wind, "off": off}
        ball.at, ball.off = landed, off
        if hz and hz["kind"] == "bunker":
            ball.lie = "sand"
            how = "ran into" if ran_through else (f"leaked {side}, into" if leaked else "into")
            return {"kind": "sand", "words": f"{club}, {carry} yards - {how} {hz['name'] or 'the sand'}",
                    "carry": carry, "roll": roll, "wind": wind, "hazard": hz["name"], "leak": leaked, "off": off}
        if hz and hz["kind"] == "rough":
            ball.lie = "rough"
            how = f"leaked {side}, " if leaked else ""
            return {"kind": "rough", "words": f"{club}, {carry} yards{ran} - {how}into {hz['name'] or 'the rough'}",
                    "carry": carry, "roll": roll, "wind": wind, "hazard": hz["name"], "leak": leaked, "off": off}
        ball.lie = "fairway"
        where = "fairway" if abs(off) <= FAIRWAY_HALF / 2 else f"{side_of(off) or ('left' if off < 0 else 'right')} side of the fairway"
        return {"kind": "fairway", "words": f"{club}, {carry} yards{ran}, {where} - {left} to go",
                "carry": carry, "roll": roll, "wind": wind, "left": left, "flair": flair, "off": off}

    def slope(self, h):
        """How this green falls, and how much: {"falls", "grade"}."""
        s = dict(DEFAULT_SLOPE)
        s.update(h.get("slope") or {})
        if s.get("falls") not in FALLS:
            s["falls"] = "front"
        s["grade"] = max(0.0, min(5.0, float(s.get("grade") or 0)))
        return s

    def feet_from_cup(self, ball, h):
        """Where the ball sits on the green, in feet from the cup: along
        (short negative, past positive) and across (left negative)."""
        return (ball.at - h["yards"]) * 3.0, ball.off * 3.0

    def _putt(self, h, ball, right, adept=False):
        """The putt. Everyone wants the cup, and the green decides."""
        ball.strokes += 1
        bx, by = self.feet_from_cup(ball, h)
        mark = self.aim(self._who) or {"at": h["yards"], "off": 0}
        mx, my = (float(mark["at"]) - h["yards"]) * 3.0, float(mark["off"]) * 3.0
        vx, vy = mx - bx, my - by
        length = (vx * vx + vy * vy) ** 0.5
        have = (bx * bx + by * by) ** 0.5                 # the putt's length to the cup
        feet = int(round(have))
        s = self.slope(h)
        fx, fy = FALLS[s["falls"]]
        grade = s["grade"]
        if have < 1.5 and right:
            # a foot away: the tap-in is the stroke
            ball.at, ball.off, ball.holed = h["yards"], 0, True
            return {"kind": "holed", "putt": True, "feet": feet, "words": "tap-in - holed", "carry": 0, "left_feet": 0}
        if length < 0.5:
            vx, vy, length = -bx, -by, max(have, 0.5)     # a mark on the ball: at the cup, then
        ux, uy = vx / length, vy / length
        if right:
            pace = PUTT_PACE[0] + length / PUTT_PACE[1]
            line = PUTT_LINE
            if adept:
                pace, line = pace * 0.5, line * 0.5
            rolled = length * (1 + self.swing.uniform(-pace, pace))
            # and the line: a degree or two either side of where it was meant
            import math as _m
            ang = _m.radians(self.swing.uniform(-line, line))
            ux, uy = ux * _m.cos(ang) - uy * _m.sin(ang), ux * _m.sin(ang) + uy * _m.cos(ang)
        elif self.swing.random() < 0.5:
            rolled = length * self.swing.uniform(0.45, 0.72)          # never up
        else:
            rolled = length * self.swing.uniform(1.25, 1.6)           # raced it
        # The slope: pace on the up-and-down, break across. A golfer who set
        # no mark is taken to have allowed for the pace, as anyone who has
        # putted uphill does; one who set a mark gets the green as it is.
        along_fall = ux * fx + uy * fy
        if mark.get("set"):
            rolled *= 1 + SLOPE_PACE * grade * along_fall
        px, py = fx - along_fall * ux, fy - along_fall * uy         # the fall across the line
        brk = SLOPE_BREAK * grade * rolled
        rx, ry = bx + ux * rolled + px * brk, by + uy * rolled + py * brk
        if not right:
            # a bad stroke is off line as well as off pace
            wobble = self.swing.uniform(-0.12, 0.12) * length
            rx, ry = rx - uy * wobble, ry + ux * wobble
        # Over the cup with pace to spare, and it drops. The path is the
        # segment from the ball to where it would rest.
        holed = False
        if right:
            dx, dy = rx - bx, ry - by
            seg = (dx * dx + dy * dy) ** 0.5 or 1e-6
            t = max(0.0, min(1.0, (-bx * dx - by * dy) / (seg * seg)))
            cx, cy = bx + t * dx, by + t * dy
            miss = (cx * cx + cy * cy) ** 0.5
            overrun = seg * (1 - t)
            capture, allow = (CUP_CAPTURE * 1.4, CUP_OVERRUN * 1.5) if adept else (CUP_CAPTURE, CUP_OVERRUN)
            holed = miss <= capture and overrun <= allow and t > 0
        words_slope = ("downhill" if along_fall > 0.4 and grade >= 1 else "uphill" if along_fall < -0.4 and grade >= 1
                       else (f"breaking {s['falls']}" if s["falls"] in ("left", "right") else "across the slope")
                       if grade >= 1.5 and abs(along_fall) < 0.7 else "")
        head = f"putt, {feet} feet" + (f", {words_slope}" if words_slope else "")
        if holed:
            ball.at, ball.off, ball.holed = h["yards"], 0, True
            return {"kind": "holed", "putt": True, "feet": feet, "words": f"{head} - holed", "carry": 0, "left_feet": 0}
        left = (rx * rx + ry * ry) ** 0.5
        if right and left <= TAP_IN:
            ball.strokes += 1                       # the tap-in: a stroke, no question
            ball.at, ball.off, ball.holed = h["yards"], 0, True
            return {"kind": "holed", "putt": True, "feet": feet, "tap_in": True,
                    "words": f"{head} - to {'a foot' if left < 1.5 else str(int(round(left))) + ' feet'}, that's good",
                    "carry": 0, "left_feet": 0}
        half = h["green"] * 1.5 + 6
        ball.at, ball.off = h["yards"] + rx / 3.0, ry / 3.0
        left_ft = max(1, int(round(left)))
        if abs(rx) > half or abs(ry) > GREEN_HALF * 3 + 3:
            ball.lie = "rough"                      # raced it off the green
            ball.at, ball.off = round(ball.at), round(ball.off)
            return {"kind": "missed", "putt": True, "feet": feet, "words": f"{head} - raced it off the green",
                    "carry": 0, "left_feet": left_ft}
        ball.lie = "green"
        how = ("holed" if holed else (f"{left_ft} feet past" if (rx * ux + ry * uy) > (bx * ux + by * uy) + length else
                                     f"{left_ft} feet short" if left_ft and rolled < length * 0.9 else f"to {left_ft} feet"))
        if not right:
            how = f"left it short, {left_ft} feet" if rolled < length else f"raced it past, {left_ft} feet"
        return {"kind": "green" if right else "missed", "putt": True, "feet": feet, "words": f"{head} - {how}",
                "carry": 0, "left_feet": left_ft}

    def _foul(self, h, ball, club):
        """A wrong answer: the ball finds the nearest trouble the club could
        have reached. Nothing in reach means a short one into the rough."""
        if club == "putter" or ball.lie == "green":
            return self._putt(h, ball, right=False)
        ball.strokes += 1
        reach = ball.at + CLUBS[club] * LIES[ball.lie][0] * self.power.get(self._who, 1.0)
        ahead = [hz for hz in h.get("hazards", [])
                 if hz["to"] > ball.at and hz["from"] <= reach and hz["kind"] in ("water", "bunker", "rough")]
        if not ahead:
            ball.at += max(20, round(CLUBS[club] * 0.4))
            ball.lie = "rough"
            return {"kind": "rough", "words": f"{club}, a foul ball - short and into the rough", "carry": 0}
        weights = {"water": 2, "bunker": 3, "rough": 3}
        hz = self.rng.choices(ahead, weights=[weights[x["kind"]] for x in ahead])[0]
        name = hz["name"] or hz["kind"]
        if hz["kind"] == "water":
            ball.strokes += 1
            return {"kind": "water", "words": f"{club}, a foul ball - into {name}; drop, and a penalty stroke",
                    "carry": 0, "hazard": name}
        ball.at = max(ball.at + 10, hz["from"])
        ball.lie = "sand" if hz["kind"] == "bunker" else "rough"
        if hz.get("side") in ("left", "right"):
            ball.off = (-1 if hz["side"] == "left" else 1) * (FAIRWAY_HALF + LEAK_PUSH)
        return {"kind": ball.lie, "words": f"{club}, a foul ball - into {name}", "carry": 0, "hazard": name,
                "off": ball.off}

    def away(self):
        """Whose turn it is: the ball farthest from the hole plays first,
        as on a course. On the tee, the honour - the best score on the last
        hole plays first - and seating order settles the rest. None when
        every ball on the hole is down."""
        h = self.hole()
        if h is None:
            return None
        playing = [p for p in (self.playoff or self.players)
                   if p in self.balls and not self.balls[p].done()]
        if not playing:
            return None
        order = {p: i for i, p in enumerate(self.players)}
        if all(self.balls[p].strokes == 0 for p in playing):
            last = self.history[-1] if self.history else None
            card = (last or {}).get("card") or {}
            return min(playing, key=lambda p: (card.get(p, 99), order[p]))
        return max(playing, key=lambda p: (h["yards"] - self.balls[p].at, -order[p]))

    def _stroke(self, h, p, ball, answer):
        """One player's stroke with one answer: where the ball went, in
        words, and the ball moved."""
        a = answer or {}
        self._who = p
        # The swing's timing seeds this stroke's draw - see CLUB_SPREAD.
        try:
            ms = int(a.get("ms")) if a.get("ms") is not None else None
        except (TypeError, ValueError):
            ms = None
        self.swing = random.Random(ms) if ms is not None else self.rng
        ball.last_aim = self.aim(p)       # the mark this stroke is played at, kept beside the result
        club = a.get("club") or self.default_club(p)
        if club not in self.clubs_for(p):
            club = self.default_club(p)
        qid = a.get("question_id")
        if qid:
            if a.get("correct"):
                if qid in self.missed:
                    self.missed.remove(qid)     # learned, then
            elif qid not in self.missed:
                self.missed.append(qid)
        if a.get("correct"):
            self.streak[p] = self.streak.get(p, 0) + 1
            adept = (bool(qid) and self.hardness.get(qid, 0.0) >= ADEPT_HARDNESS) \
                or self.streak[p] >= ADEPT_STREAK or bool(a.get("adept"))
            shot = self._fair(h, ball, club, adept=adept)
        else:
            self.streak[p] = 0
            shot = self._foul(h, ball, club)
        flair = shot.get("flair")
        shot["call"] = ("A hole in one!" if shot.get("ace")
                        else self.rng.choice(FLAIR_CALLS[flair]) if flair in FLAIR_CALLS
                        else self.rng.choice(LEAK_CALLS) if shot.get("leak")
                        else self.rng.choice(CALLS.get(shot["kind"], ["That's a shot."])))
        if not ball.holed and ball.strokes >= h["par"] + PICK_UP_OVER:
            ball.picked_up = True
            ball.strokes = h["par"] + PICK_UP_OVER
            shot["words"] += f" - picked up, {score_name(ball.strokes, h['par'])}"
            shot["score"] = score_name(ball.strokes, h["par"])
        elif ball.holed:
            shot["words"] += f" - {ball.strokes} for {score_name(ball.strokes, h['par'])}"
            shot["score"] = score_name(ball.strokes, h["par"])
        shot.update(strokes=ball.strokes, at=ball.at, off=ball.off, lie=ball.lie, club=club,
                    done=ball.done(), holed=ball.holed, aim=ball.last_aim)
        self.aims.pop(p, None)            # a mark is for one stroke
        ball.log.append(shot["words"])
        return shot

    def _after(self, h, shots):
        """The hole's state after some strokes; the next hole if it is done."""
        hole_done = all(b.done() for b in self.balls.values())
        row = {"hole": h["n"], "par": h["par"], "shots": shots, "hole_done": hole_done,
               "wind_mph": self.wind_mph}
        if hole_done:
            for p, b in self.balls.items():
                self.cards[p][h["n"]] = b.strokes
            row["card"] = {p: b.strokes for p, b in self.balls.items()}
            self._next_hole()
            row["round_over"] = self.over()
            row["winner"] = self._winner
        self.history.append(row)
        return row

    def play_one(self, player, answer):
        """One stroke, by the player who is away: `answer` is
        {"correct", "club"}, or None for a player who never played the
        shot - a foul ball. Returns the shot in words, and the hole's state
        after it. The way a round is played."""
        h = self.hole()
        if h is None or self.over():
            return {"error": "the round is over"}
        ball = self.balls.get(player)
        if ball is None or ball.done():
            return {"error": "not on this hole"}
        shot = self._stroke(h, player, ball, answer)
        return self._after(h, {player: shot})

    def play(self, answers):
        """Everybody's strokes at once: `answers` is {player: {"correct",
        "club"}}, a player not in it plays a foul ball. Returns every shot
        in words, and the hole's state after them. The rules tests use it;
        the room plays one at a time, see play_one."""
        h = self.hole()
        if h is None or self.over():
            return {"error": "the round is over"}
        shots = {}
        for p, ball in self.balls.items():
            if ball.done():
                continue
            shots[p] = self._stroke(h, p, ball, answers.get(p))
        return self._after(h, shots)

    def add_player(self, player):
        """Somebody arriving mid-round arranges a tee time: if the group is
        still on the tee they join it now; otherwise they join at the next
        tee, and watch this hole with the group. No card for the holes
        before. In a playoff they watch."""
        if player in self.players or player in self.tee_times:
            return
        h = self.hole()
        on_the_tee = (h is not None and not self.playoff
                      and all(b.strokes == 0 for b in self.balls.values()))
        if on_the_tee:
            self.players.append(player)
            self.cards[player] = {}
            self.balls[player] = Ball()
            return
        if self.playoff or h is None:
            self.players.append(player)      # watching; there is no tee to join at
            self.cards[player] = {}
            return
        self.tee_times.append(player)

    def has_tee_time(self, player):
        return player in self.tee_times

    def drop(self, player):
        """Somebody left: their ball is picked up, the round goes on without
        them, and the hole moves on if theirs was the last ball on it."""
        if player in self.tee_times:
            self.tee_times.remove(player)
            return None
        if player not in self.players:
            return None
        self.players.remove(player)
        self.cards.pop(player, None)
        self.playoff = [p for p in self.playoff if p != player]
        self.balls.pop(player, None)
        h = self.hole()
        if h is not None and self.balls and all(b.done() for b in self.balls.values()):
            return self._after(h, {})
        if self.playoff and len(self.playoff) == 1:
            self._winner = self.playoff[0]
            self.playoff = []
        return None

    def _next_hole(self):
        if self.playoff:
            # Sudden death: a hole that separates them ends it.
            scores = {p: self.balls[p].strokes for p in self.playoff}
            best = min(scores.values())
            still = [p for p in self.playoff if scores[p] == best]
            self.playoff_holes += 1
            if len(still) == 1:
                self._winner = still[0]
                self.playoff = []
                return
            self.playoff = still
            self._tee_off_playoff()
            return
        self.hole_index += 1
        if self.hole() is None:
            board = self.leaderboard()
            if not board:
                return
            top = board[0]["net"]
            tied = [r["player"] for r in board if r["net"] == top]
            if len(tied) == 1:
                self._winner = tied[0]
            else:
                self.playoff = tied
                self._tee_off_playoff()
        else:
            self._tee_off()

    def _tee_off_playoff(self):
        """A playoff plays on from the next hole of the course, round again."""
        played = set(self.holes)
        candidates = [h["n"] for h in self.course["holes"] if h["n"] not in played] or \
                     [h["n"] for h in self.course["holes"]]
        n = candidates[(self.playoff_holes) % len(candidates)]
        self.holes.append(n)
        self.hole_index = len(self.holes) - 1
        self._tee_off()

    # ------------------------------------------------------------ questions
    # Which question the room asks is the room's business - it has the pool
    # and the unit's log. This keeps the thread: the area a hole is on, what
    # has been asked, what was missed, and what the lie calls for.

    def note_asked(self, question_id):
        self.asked[question_id] = self.asked.get(question_id, 0) + 1

    def pick_section(self, by_section):
        """`by_section` is {section: [question ids not yet asked this
        round]}. This hole's section while it has any left; else one not
        yet played this round, at random; else any with some left; else
        None - every question has been asked once."""
        live = {sec: ids for sec, ids in by_section.items() if ids}
        if self.hole_section in live:
            return self.hole_section
        fresh = [sec for sec in live if sec not in self.sections_used]
        pick = (self.rng.choice(sorted(fresh)) if fresh
                else self.rng.choice(sorted(live)) if live else None)
        if pick is not None:
            self.hole_section = pick
            self.sections_used.append(pick)
        return pick

    def choose(self, candidates, player):
        """One of `candidates` for this player's stroke: where the pool has
        measured hardness, the one nearest what the lie calls for, from the
        three nearest so it is not the same one every round; otherwise any."""
        ids = list(candidates)
        if not ids:
            return None
        ranked = [q for q in ids if q in self.hardness]
        if len(ranked) < 3:
            return self.rng.choice(ids)
        ball = self.balls.get(player)
        want = LIE_HARDNESS.get(ball.lie if ball else "fairway", 0.5)
        lo, hi = min(self.hardness[q] for q in ranked), max(self.hardness[q] for q in ranked)
        span = (hi - lo) or 1.0
        place = lambda q: (self.hardness[q] - lo) / span      # noqa: E731
        ranked.sort(key=lambda q: abs(place(q) - want))
        return self.rng.choice(ranked[:3])

    def draw(self, by_section, all_ids, player):
        """The question for this stroke, from the pool as the room presents
        it: `by_section` every question by section, `all_ids` every
        question. One area per hole until it runs dry; every question once;
        then the misses; then by hardness against the lie."""
        left = {sec: [q for q in ids if q not in self.asked] for sec, ids in by_section.items()}
        section = self.pick_section(left)
        if section is not None:
            return self.choose(left[section], player), section
        again = [q for q in self.missed if self.asked.get(q, 0) < 2]
        if again:
            return again[0], None
        fewest = min(self.asked.get(q, 0) for q in all_ids) if all_ids else 0
        return self.choose([q for q in all_ids if self.asked.get(q, 0) == fewest], player), None

    # ---------------------------------------------------------------- views

    def par_so_far(self, player):
        return sum(next(h["par"] for h in self.course["holes"] if h["n"] == n)
                   for n in self.cards[player] if n in self.round_holes)

    def leaderboard(self):
        """Everybody, best first: gross, strokes given, net, and to par -
        over the round's holes; a playoff decides, it does not count."""
        rows = []
        for p in self.players:
            on_card = {n: s for n, s in self.cards[p].items() if n in self.round_holes}
            gross = sum(on_card.values())
            given = int(self.handicaps.get(p, 0))
            played = len(on_card)
            rows.append({"player": p, "gross": gross, "given": given, "net": gross - given,
                         "holes": played, "to_par": gross - given - self.par_so_far(p),
                         # the card itself: strokes by hole, for a scorecard
                         "card": {str(n): s for n, s in on_card.items()}})
        rows.sort(key=lambda r: (r["net"], r["gross"]))
        for i, r in enumerate(rows, start=1):
            r["place"] = i
        return rows

    def as_dict(self):
        h = self.hole()
        return {
            "course": self.course["id"], "course_name": self.course["name"],
            "hole": h["n"] if h else None, "par": h["par"] if h else None,
            "yards": h["yards"] if h else None, "hole_name": (h.get("name") or "") if h else "",
            "hole_wind": h.get("wind") if h else None, "wind_mph": self.wind_mph,
            "holes_played": self.hole_index, "holes": len(self.holes),
            "slope": self.slope(h) if h else None,
            "balls": {p: {"at": b.at, "off": b.off, "lie": b.lie, "strokes": b.strokes, "holed": b.holed,
                          "picked_up": b.picked_up, "left": int(round(h["yards"] - b.at)) if h else 0,
                          "feet": (int(round(((b.at - h["yards"]) ** 2 + b.off ** 2) ** 0.5 * 3)) if h and b.lie == "green" else None),
                          "aim": self.aim(p), "last_aim": b.last_aim,
                          "clubs": self.clubs_for(p), "default_club": self.default_club(p),
                          "log": list(b.log)}
                      for p, b in self.balls.items()},
            "leaderboard": self.leaderboard(),
            # the round's holes with their pars, in order: the scorecard's top rows
            "round_holes": [{"n": n, "par": next(x["par"] for x in self.course["holes"] if x["n"] == n)}
                            for n in self.round_holes],
            "playoff": list(self.playoff), "handicaps": bool(self.handicaps),
            "away": self.away(), "hole_section": self.hole_section,
            "tee_times": list(self.tee_times),
            "asked": sum(self.asked.values()), "missed": len(self.missed),
            "winner": self._winner, "over": self.over(),
        }
