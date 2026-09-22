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
import logging
import math
import random
from pathlib import Path

# The one logger, as every module here takes it. Golf had none until the
# landing model arrived, having never had anything to say; now a surface
# nobody has heard of, a club that is not on the list, a run that works
# out absurd and a ball that skips off the water all have somewhere to be
# said, and the operator can read afterwards what the round actually did.
log = logging.getLogger("elmer")

COURSES_DIR = Path(__file__).resolve().parents[1] / "data" / "golf"

# The most a club can carry, in yards, from a good lie with a fast answer.
CLUBS = {"driver": 250, "wood": 210, "iron": 165, "wedge": 105}
CLUB_ORDER = ("driver", "wood", "iron", "wedge")
# What the lie costs: a factor on the carry, and the longest club allowed.
LIES = {
    "tee": (1.0, "driver"), "fairway": (1.0, "driver"),
    "rough": (0.8, "wood"), "sand": (0.6, "wedge"), "fringe": (1.0, "wedge"),
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
# The fringe: the collar of longer grass round the green, FRINGE yards
# wide, and bordered by rough on every side but the front, where the
# fairway runs up to it. A green is clipped to nothing and does not absorb
# a landing the way a fairway's grass does - a ball that comes down on it
# releases, and can run to the far side and off; the fringe is the middle
# ground, which is why a golfer chips into it on purpose, to take the pace
# off a ball that would otherwise run across the green. A ball that stops
# on the collar can be putted - the putter through it - or chipped.
FRINGE = 3
FRINGE_DRAG = 0.12              # of a putt's roll, lost to the collar when the golfer did not allow for it
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
# The ground's say. A ball lands with the speed it was hit at, and the roll
# is that speed on that surface on that day: a full driver on a running
# fairway goes forty yards more; a three-quarter iron into a soft green
# releases a few and stops. ROLL is a full swing on a fairway of ordinary
# firmness; the speed of a lesser swing scales it, the surface it came down
# on scales it, the wind, and the day.
# How the ball arrives, and how the ground answers - which used to be one
# number each and could not be asked the interesting question.
#
# ROLL was a yard figure per club that quietly bundled three different
# things: how fast the ball was going when it landed, how steeply it came
# down, and how much it was spinning. SURFACE_ROLL was a multiplier rather
# than a friction. Between them there was no way to ask "what if it arrives
# shallow and fast" - so a thinned iron and a flushed one landed the same
# way, and a ball could not skip off water because nothing knew the angle
# it hit at.
#
# Now: the arrival is the club's (speed, descent, spin), the ground's answer
# is a friction, and the run falls out of the two.
#
#     run = BASE · v² · cos(descent) · spin_check / friction · firmness
#
# DESCENT and SPIN are the physical figures - a driver comes in shallow and
# barely turning, a wedge steep and spinning hard. V_LAND is then *solved*
# so that a full swing on a fairway reproduces the 24 / 19 / 11 / 6 this
# replaced, exactly: the same discipline as the wind becoming a bearing,
# where the four cardinal hours came out unchanged. The feel is kept and
# the knobs now mean something. tools/golf_roll.py prints the table these
# produce, which is how they get retuned from play rather than from memory.
DESCENT = {"driver": 38.0, "wood": 43.0, "iron": 48.0, "wedge": 55.0}   # degrees
V_LAND = {"driver": 1.000, "wood": 0.930, "iron": 0.756, "wedge": 0.620}
SPIN_RATE = {"driver": 0.05, "wood": 0.12, "iron": 0.34, "wedge": 0.62}
SPIN_CHECK = 0.186              # how much of the spin figure actually checks it
ROLL_BASE = 9.838               # solved; see the derivation above
STINGER_DESCENT = 0.35          # a punched ball comes in this much flatter

# What the ground does about it. A friction, so a bigger number is a
# surface that stops the ball sooner, and the run goes as one over it.
# Every one of these is set to reproduce the multiplier it had, so this
# stage changes the *shape* of the model and none of its behaviour:
# x1.33 on the green, x1.00 on the fairway, x0.70 on the fringe, x0.36 in
# the rough, and a ball landing in sand stopping where it pitched.
#
# The fringe is under argument and is deliberately NOT changed here.
# KC9SP reads a collar as intermediate between fairway and green; this
# table has it braking harder than the fairway, which is a deliberate and
# tested ordering (test_golf.py pins green > fairway > fringe > rough).
# Installing a contested number while re-shaping the model would mean two
# changes riding on one commit and no way to tell which moved the game.
# tools/golf_roll.py prints the table under either value; the argument is
# settled there. See docs/golf-plan.md.
FRICTION = {"green": 0.24, "fringe": 0.457, "fairway": 0.32, "tee": 0.32,
            "rough": 0.90, "sand": 40.0}
# What the fringe would be if a collar ran a touch faster than the fairway,
# which is the other reading. Not used; here so the tool can show both.
FRINGE_IF_FAST = 0.30
FRICTION_DEFAULT = "fairway"    # what an unknown surface is charged

# The skip. Not a special case and not a shot anybody is offered: once the
# descent angle is a real quantity, a ball that arrives at water shallow
# enough and fast enough skips off it, the way a flat stone does. Every
# ordinary shot comes down between 38 and 55 degrees and never qualifies. A
# stinger - which is an *earned* flair, punched under the wind - comes in
# at about a third of that, and can. So the trick shot is reachable only
# through a shot somebody earned, and is never promised.
SKIP_ANGLE = 20.0               # degrees; steeper than this and it goes in
SKIP_SPEED = 0.70               # and slower than this it has not the pace
SKIP_ODDS = 0.45                # at the flattest and fastest; less as it steepens
SKIP_RUN = (18, 34)             # yards it carries on across the water
# The wind, by the clock. A caddie says where it is out of the way a pilot
# does - "out of eight o'clock" - twelve being straight down the hole and
# three off the right, and that is one fact with a head component and a
# cross component in it rather than four categories that cannot be mixed.
# The card still says with, into or across; the hour is drawn inside that
# arc, seeded by the hole, so a hole plays the same way every round.
#
# theta is measured clockwise from twelve, so the tail component is
# -cos(theta) - full headwind out of twelve, full tail out of six - and the
# cross component is sin(theta), positive off the right. At the four
# cardinal hours these reproduce the old numbers exactly; in between they
# give what the hour actually implies, which is the point of saying it.
WIND_ARC = {"into": (11, 12, 1), "with": (5, 6, 7),
            "across-left": (8, 9, 10), "across-right": (2, 3, 4)}
WIND_ROLL_TAIL = 0.25           # roll multiplier added downwind, at full tail
WIND_ROLL_HEAD = 0.30           # and taken off into it, so 0.70 out of twelve
WIND_CARRY_TAIL = 0.6           # yards a mile an hour, running before it
WIND_CARRY_HEAD = 0.8           # and against it, which costs more than it gives
WIND_CARRY_CROSS = 0.2          # what a pure crosswind costs in carry anyway
# Sideways drift is a matter of how long the ball is up there. A crosswind
# does not push a ball a fixed distance - it accelerates it sideways for as
# long as the ball is in the air, so a driver that hangs six seconds is
# moved several yards and a pitching wedge laid up forty yards is barely
# touched. Drifting both the same, which is what a flat yards-per-mile-an-
# hour did, is the thing that surprises a golfer: they know the wedge holds
# its line and the game did not.
#
# Flight time is the club's full-swing hang, scaled by how much of its
# length this particular shot was - roughly the square root, a half-length
# iron being up about seven tenths as long, which is near enough for a game.
# The wind at which a day gusts its full spread. Ten, not twenty: eight
# miles an hour gusting to eleven is an ordinary afternoon, and damping
# that made a breeze sit far stiller than one does. What is being caught
# here is the light air below it - three or four miles an hour, which
# genuinely just sits there - not a moderate wind.
GUST_FULL = 10
WIND_DRIFT_PER_SECOND = 0.06    # yards a mile an hour, for each second aloft
FLIGHT_SECONDS = {"driver": 6.0, "wood": 5.4, "iron": 4.6, "wedge": 3.6, "putter": 0.0}
STINGER_HANG = 0.4              # a punched ball is under it and down early
# A full driver in a fifteen mile an hour crosswind moves about five yards,
# which is what it does; the old flat figure was 0.35 a mile an hour for
# everything, and this reproduces it for a driver and nothing else.
ROLL_NOISE = (0.7, 1.3)         # the bounce: the roll, times somewhere in here
ROLL_SPEED = 1.2                # the roll goes as the landing speed to this power
RUN_MOST = 80                   # yards; past this the arithmetic has gone wrong, not the ball
# The day - see Day. The ground's firmness comes from how wet it is, and
# how wet it is comes from the sky, hole by hole.
GROUND_WORDS = ((0.25, "firm and running"), (0.55, ""), (0.8, "soft underfoot"), (1.01, "wet - nothing runs"))
SKY_WORDS = {"sun": "sun out", "cloud": "overcast", "shower": "a shower coming through"}
# A green that falls toward the player checks an approach; one that falls
# away releases it; one that falls across nudges the roll toward the fall.
SLOPE_RELEASE = 0.1             # per percent of grade, on the roll
SLOPE_DRIFT = 0.15              # of the roll, per percent of grade, across
# Spin: a wedge into a green can bite and come back; an iron now and then.
SPIN_ODDS = {"wedge": 0.35, "iron": 0.15}
SPIN_BACK = {"wedge": (1, 4), "iron": (0, 2)}
# The bounce that kicks: ground is not flat, and one landing in eight goes
# sideways a few yards off what it hit.
KICK_ODDS = 0.12
KICK_YARDS = (2, 6)
SIDE_BANDS = {"": ("across", "front", "centre", "around", "beyond", ""),
              "left": ("left", "around"), "right": ("right", "around")}


def green_edge(h):
    """The green's half-depth in yards, either side of the pin."""
    return h["green"] / 2 + 5


def green_half(h):
    """The green's half-width in yards: the card's, where it was measured
    (the greenside sand says where the green stops), else GREEN_HALF."""
    try:
        return max(6.0, min(float(GREEN_HALF), float(h.get("green_half") or GREEN_HALF)))
    except (TypeError, ValueError):
        return float(GREEN_HALF)


def hazard_off(h, hz):
    """Where a hazard sits across the hole, in yards off the line, right
    positive: as measured where the card has it, else where its side
    puts it - beside the fairway for left and right, on the line for the
    rest. "around" is two: this returns the right one; the caller mirrors."""
    half = fairway_half(h)
    side = hz.get("side", "")
    if hz.get("off") is not None:
        off = float(hz["off"])
        if side in ("left", "right"):
            # A side hazard's stated offset is measured from the fairway's
            # edge, not from the line of play: nought is at the edge and the
            # rest is out into the rough. Read as centre-line yards instead,
            # fifty-three of the ninety side hazards on the shipped courses
            # would sit *inside* their own fairway, which is not how a course
            # is built - and the card drew them there, which is what made a
            # drive down the middle come to rest in a bunker.
            return (-1 if off < 0 or side == "left" else 1) * (half + abs(off))
        return off
    # No stated offset: twelve yards into the rough, which is the same
    # reading the stated ones get and sits it where the ones beside it sit.
    if side == "left":
        return -(half + 12)
    if side == "right":
        return half + 12
    if side == "around":
        return green_half(h) + 8
    return 0.0


def hazard_spans(h, hz):
    """Where a hazard lies across the hole: a list of (centre, half-width)
    in yards off the line, right positive. Usually one; "around" is two,
    one either side of the green.

    This is the whole of a hazard's shape across the line, and it is what
    the map draws and what a ball is tested against. It used to be drawn
    from these numbers and decided from the side label alone, so the two
    could disagree and did: a ball down the middle of the fairway was
    called into a bunker that is drawn beside it, and a ball forty yards
    right was called into a bunker drawn at thirty. What is drawn is what
    the ball obeys, and this is the one place that says so.
    """
    side = hz.get("side", "")
    half = fairway_half(h)
    if hz.get("off") is None:
        if side in ("across", "front", "centre"):
            # Straight across the line of play: the fairway's width, and a
            # little narrower for one sitting in the middle of it.
            return [(0.0, half * (0.75 if side == "centre" else 1.0))]
        if side == "beyond":
            return [(0.0, green_half(h) + 6)]
        if side == "around":
            return [(-(green_half(h) + 8), 7.0), (green_half(h) + 8, 7.0)]
    off = hazard_off(h, hz)
    if hz["kind"] == "water" and side in ("left", "right") and (hz["to"] - hz["from"]) > 80:
        # Water down the length of one side: a band running out to the edge.
        return [(off + (18 if off > 0 else -18), 24.0)]
    if hz["kind"] == "water" and side in ("across", "front"):
        return [(off, half)]
    return [(off, 8.0 if hz["kind"] == "bunker" else 12.0)]


def hazard_covers(h, hz, off):
    """Whether a ball this far off the line is across the hazard at all."""
    across = float(off or 0)
    return any(abs(across - centre) <= width for centre, width in hazard_spans(h, hz))


def on_the_green(h, at, off):
    """What a ball at these yards is on, of the green and its collar:
    "green", "fringe", or None for neither."""
    edge = green_edge(h)
    along, across = abs(h["yards"] - float(at)), abs(float(off or 0))
    half = green_half(h)
    if along <= edge and across <= half:
        return "green"
    if along <= edge + FRINGE and across <= half + FRINGE:
        return "fringe"
    return None


def fairway_half(h=None):
    """The fairway's half-width on this hole, yards: the card's, or the
    usual eighteen. Every hole its own - the 7th's a lane, the 2nd's a
    field."""
    try:
        return float((h or {}).get("width") or FAIRWAY_HALF)
    except (TypeError, ValueError):
        return float(FAIRWAY_HALF)


def side_of(off, half=None):
    """Which side of the hole a ball this far off the line is on: '' for
    the fairway's width, 'left' or 'right' beyond it."""
    half = FAIRWAY_HALF if half is None else half
    if off < -half:
        return "left"
    if off > half:
        return "right"
    return ""
LEAK_CALLS = ["Leaked it.", "Pushed it a touch.", "Pulled it a hair.", "That got away from him."]
def wind_parts(hour):
    """A clock hour as (tail, cross): how much of the wind is behind you,
    and how much is across you. ``None`` is no wind at all, which is what a
    stinger is played to earn.

    Twelve is dead ahead, so out of twelve is a full headwind and tail is
    -1; out of six it is +1. Cross is positive when the wind is off the
    right, which pushes the ball left. Both are cosine and sine of the same
    angle, which is why a quartering wind is most of a headwind and a bit
    of a crosswind rather than having to be called one or the other.
    """
    if hour is None:
        return 0.0, 0.0
    theta = math.radians((int(hour) % 12) * 30.0)
    return -math.cos(theta), math.sin(theta)


def wind_carry(hour):
    """Yards a mile an hour, by where the wind is out of.

    A headwind costs more than the same tailwind gives, which is the oldest
    complaint in the game, and a crosswind costs a little whatever else it
    is doing. At twelve, three, six and nine this is -0.8, -0.2, +0.6 and
    -0.2, the four numbers this replaced.
    """
    tail, cross = wind_parts(hour)
    gain = WIND_CARRY_TAIL if tail >= 0 else WIND_CARRY_HEAD
    return tail * gain - WIND_CARRY_CROSS * abs(cross)


def wind_roll(hour):
    """The roll multiplier: a ball run on downwind, held up into it."""
    tail, _ = wind_parts(hour)
    return 1.0 + tail * (WIND_ROLL_TAIL if tail >= 0 else WIND_ROLL_HEAD)


def descent_angle(club, flair=None):
    """The angle the ball comes down at, in degrees.

    The club's, flattened by a stinger. This is the quantity the skip turns
    on, and the reason the skip needs no special case of its own.
    """
    angle = DESCENT.get(club)
    if angle is None:
        if club:                            # a putter has no flight; anything else is a bug
            log.warning("golf: no descent angle for club %r - using the "
                        "iron's %.0f degrees", club, DESCENT["iron"])
        angle = DESCENT["iron"]
    return angle * (STINGER_DESCENT if flair == "stinger" else 1.0)


def landing_speed(club, carry=None, most=None):
    """How fast the ball is going when it lands, 0..1 against a flushed
    driver. A part swing arrives slower, which is most of why it runs less."""
    speed = V_LAND.get(club, V_LAND["iron"])
    if carry and most:
        speed *= max(0.3, min(1.15, (abs(carry) / float(most)) ** (ROLL_SPEED / 2)))
    return speed


def friction_of(lie):
    """What the surface charges the ball. Bigger stops it sooner."""
    known = FRICTION.get(lie)
    if known is None:
        log.warning("golf: no friction for a ball on %r - charging it the "
                    "%s's %.2f", lie, FRICTION_DEFAULT, FRICTION[FRICTION_DEFAULT])
        return FRICTION[FRICTION_DEFAULT]
    return known


def run_yards(club, lie, hour=None, carry=None, most=None, flair=None, firmness=1.0):
    """How far the ball runs on after it pitches.

    The arrival against the ground: speed squared, flattened by how steeply
    it came in, checked by its spin, divided by what the surface charges,
    and scaled by how firm the day has left it.
    """
    speed = landing_speed(club, carry, most)
    angle = descent_angle(club, flair)
    check = 1.0 - SPIN_CHECK * SPIN_RATE.get(club, SPIN_RATE["iron"])
    run = (ROLL_BASE * speed * speed * math.cos(math.radians(angle)) * check
           / friction_of(lie) * float(firmness) * wind_roll(hour))
    if run < 0 or run > RUN_MOST:
        log.warning("golf: a %s on the %s worked out at %.1f yards of run "
                    "(speed %.2f, descent %.0f deg, firmness %.2f) - "
                    "holding it to %d", club, lie, run, speed, angle,
                    firmness, 0 if run < 0 else RUN_MOST)
        run = 0.0 if run < 0 else float(RUN_MOST)
    return run


def skips(angle, speed, rng):
    """Whether a ball arriving at water at this angle and pace skips off it.

    Flat and fast, or it goes in. The odds fall away as it steepens, so a
    ball just under the angle usually still gets wet.
    """
    if angle >= SKIP_ANGLE or speed < SKIP_SPEED:
        return False
    odds = SKIP_ODDS * (1.0 - angle / SKIP_ANGLE)
    return rng.random() < odds


def flight_seconds(club, carry=None, most=None, flair=None):
    """How long this shot is in the air, near enough for a game.

    The club's full-swing hang, scaled by the root of how much of its
    length the shot actually was - a wedge dropped forty yards is up about
    two seconds, a driver flushed is up six. A stinger is punched under the
    wind and is down early, which is the whole reason anybody hits one.
    """
    hang = FLIGHT_SECONDS.get(club, 4.6)
    if carry and most:
        hang *= max(0.25, min(1.15, (abs(carry) / float(most)) ** 0.5))
    if flair == "stinger":
        hang *= STINGER_HANG
    return hang


def wind_drift(hour, mph, club=None, carry=None, most=None, flair=None):
    """Yards the wind carries the ball sideways, off the side it blows from.

    Positive is to the right of the line. A wind out of nine o'clock - off
    the left - pushes the ball right, which is the sign the crosswind case
    has always used. How far depends on how long the ball is up: see
    :func:`flight_seconds` and the note on WIND_DRIFT_PER_SECOND.
    """
    _, cross = wind_parts(hour)
    if not cross:
        return 0.0
    seconds = flight_seconds(club, carry, most, flair) if club else FLIGHT_SECONDS["driver"]
    return -WIND_DRIFT_PER_SECOND * float(mph or 0) * cross * seconds
# Where a hole ends: picked up at par plus this many.
PICK_UP_OVER = 3
# The shots worth making. Golf is about the shots - good, bad and regular -
# and some are shaped on purpose: a hook worked around the trees, a stinger
# punched under the wind, a flop over the sand to a tap-in, the approach
# that goes in. Here they are earned by an adept answer: a right answer on
# a question this unit has measured as hard, or the third right answer in a
# row. Which shot depends on where the ball is; the ball still obeys the
# course, it just gets the shot a good golfer would have played from there.
# How far from the lie's wanted hardness a question may be and still be
# likely: the draw's bell, in the pool's 0..1 measure. A quarter means a
# question half a scale away is a fifth as likely as one dead on.
CHOOSE_WIDTH = 0.25
ADEPT_HARDNESS = 0.6            # of the unit's own 0..1 measure; see difficulty.py
ADEPT_STREAK = 3                # right answers in a row, when nothing is measured
HOLE_OUT_ODDS = 1 / 6           # an adept approach from inside HOLE_OUT_FROM yards
HOLE_OUT_FROM = 120
# From inside this the map is the green and its approaches, whatever the
# club - a wedge's length; see Golf.approaching and golfmap.approach_svg.
APPROACH_FROM = 105
FLAIR_CALLS = {
    "worked": ["Worked it around the trees.", "Shaped it out of there.", "Hooked it on purpose, and it came back."],
    "stinger": ["A stinger, under the wind.", "Punched it. The wind never saw it.", "Kept it low. That's the shot."],
    "flop": ["Flopped it to a tap-in.", "Straight up, straight down. Kick-in.", "That's a touch shot."],
    "holed-out": ["Holed it from the fairway!", "It's IN. From out there.", "Walked it in from the fairway."],
    "launched": ["Launched it.", "That one's still going.", "Nuked it."],
    "pure": ["Pured it. Stiff.", "All over the flag.", "Pin high, and close."],
    # The one nobody is offered. It is never chosen by the game the way the
    # others are - it falls out of arriving at water flat and fast - so it
    # is said loudly, or a ball coming out of the water reads as a fault.
    "skipped": ["Skipped it! That's still dry.", "It BOUNCED. Off the water, and out.",
                "Three skips and dry land. Nobody meant that."],
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
    "fringe": ["On the collar.", "Just on the fringe.", "The fringe took the pace off it.", "Putt it from there."],
    "long": ["Flew the green.", "Too much club.", "Airmailed it."],
    "holed": ["In the hole!", "Drained it.", "Bottom of the cup.", "It's in the cup!", "In the cup!",
              "THAT, ladies and gentlemen, is how it is done."],
    "rough": ["Topped it.", "Fat. Chunked it.", "Skied that one.", "In the rough.",
              "OOOPS! That's going to need patching.", "Are you new at this?"],
    "sand": ["Sliced it into the sand.", "Pulled it into the bunker.", "Beach.", "Found the bunker.", "That ball is on the beach."],
    "water": ["Hooked it into the water.", "Wet.", "That's a splash - what was the wind?",
              "That's swimming.", "Are you going after that?", "We all have bad days."],
    "missed": ["Lipped out.", "Left it short.", "Burned the edge."],
}
# How hard a question the lie asks for, as a place in the pool's measured
# hardness - nought the easiest, one the hardest. The tee is a fresh start;
# the sand is not.
LIE_HARDNESS = {"tee": 0.25, "fairway": 0.35, "green": 0.5, "fringe": 0.5, "rough": 0.7, "sand": 0.85}
NAMES = {-3: "albatross", -2: "eagle", -1: "birdie", 0: "par", 1: "bogey",
         2: "double bogey", 3: "triple bogey"}


def courses():
    """Every course shipped, by id, friendliest first."""
    out = {}
    for path in sorted(COURSES_DIR.glob("*.json")):
        if path.name.endswith(".map.json"):
            continue                      # a course's routing (coursemap.py), not a card
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


class Day:
    """The weather a round is played in, and how it moves.

    A round is four hours, and in four hours the wind gets up and backs
    round, a shower comes through and the sun follows it, and the ground
    that was running at the first is holding at the ninth. So the day is
    a small model rather than a number: the wind walks around the day's
    mean from hole to hole and gusts from shot to shot; the sky steps
    between sun, cloud and shower; the ground's moisture rises under a
    shower and dries in sun and wind, and its firmness - what the roll
    is multiplied by - follows the moisture. It starts from the real
    forecast at the course when the unit had a network (weather.py), and
    from the card's typical wind when it did not.
    """
    WALK = 3.0                  # mph the wind may drift between holes
    PULL = 0.3                  # of the way back to the day's mean, each hole
    GUST = (0.7, 1.4)           # a shot's wind, as a factor on the hole's
    DRY = {"sun": 0.02, "cloud": 0.01, "shower": -0.15}     # moisture per hole
    WIND_DRY = 0.001            # more, per mile an hour
    STEP = {"sun": (("cloud", 0.15),), "cloud": (("sun", 0.25), ("shower", 0.2)), "shower": (("cloud", 0.5),)}

    def __init__(self, rng, typical_mph=10, forecast=None):
        self.rng = rng
        self.forecast = forecast or None
        if forecast:
            # The day's wind, not the minute's. The forecast's current hour
            # is a single sample, and somebody teeing off in a lull on a
            # blowy day was handed a dead round - the course's whole
            # character gone because of when they happened to sit down. The
            # round starts from the highest wind of the day instead, which
            # is what "playing Pebble Beach in the afternoon" means. See
            # weather.PEAK_HOURS. A forecast from an older build has no
            # peak in it and falls back to the hour, as it always did.
            self.mean = float(forecast.get("peak_mph")
                              or forecast.get("wind_mph") or typical_mph)
            self.sky = forecast.get("sky") or "sun"
            self.rain_chance = float(forecast.get("rain_chance") or 0.0)
            self.moisture = 0.7 if forecast.get("raining") else 0.3 + 0.3 * self.rain_chance
        else:
            self.mean = float(typical_mph)
            self.sky = rng.choices(("sun", "cloud", "shower"), weights=(5, 3, 1))[0]
            self.rain_chance = {"sun": 0.05, "cloud": 0.25, "shower": 0.6}[self.sky]
            self.moisture = rng.uniform(0.15, 0.6) + (0.3 if self.sky == "shower" else 0.0)
        self.moisture = max(0.0, min(1.0, self.moisture))
        self.wind_mph = max(0, round(self.mean * rng.uniform(0.7, 1.3)))
        self.holes = 0

    def next_hole(self):
        """The day moves on: the wind walks, the sky steps, the ground
        dries or soaks."""
        self.holes += 1
        drift = self.rng.uniform(-self.WALK, self.WALK) + self.PULL * (self.mean - self.wind_mph)
        self.wind_mph = max(0, min(40, round(self.wind_mph + drift)))
        r = self.rng.random()
        for to, odds in self.STEP[self.sky]:
            # the forecast's rain chance leans the step toward a shower
            if to == "shower":
                odds *= 0.5 + 2.0 * self.rain_chance
            if r < odds:
                self.sky = to
                break
            r -= odds
        self.moisture -= self.DRY[self.sky] + (self.WIND_DRY * self.wind_mph if self.sky != "shower" else 0.0)
        self.moisture = max(0.0, min(1.0, self.moisture))

    def gust(self):
        """This shot's wind: the hole's, gusting or lulling.

        Two things a flat draw between the bounds got wrong. Light air is
        steady - four miles an hour does not gust to six and drop to three,
        it just sits there - so the spread opens as the wind gets up and is
        nearly nothing below a breeze. And a gust is not as likely as the
        lull between gusts: most shots are played in about the wind that is
        blowing, and now and then one is caught. So the draw is triangular
        with its mode at the hole's own wind rather than uniform across the
        range, which is the shape of the thing rather than a box.

        Bounds equal - GUST set to (1.0, 1.0) - is the wind held still, and
        is how the shot tests take the day's life out of a swing.
        """
        low, high = self.GUST
        if low == high:
            return self.wind_mph * low
        share = min(1.0, self.wind_mph / GUST_FULL)
        low = 1.0 - (1.0 - low) * share
        high = 1.0 + (high - 1.0) * share
        return self.wind_mph * self.rng.triangular(low, high, 1.0)

    @property
    def firmness(self):
        """What the roll is multiplied by: bone dry runs a third more,
        soaked runs a third less."""
        return round(1.35 - 0.7 * self.moisture, 3)

    @property
    def ground_words(self):
        return next(w for edge, w in GROUND_WORDS if self.moisture < edge)

    def state(self):
        return {"wind_mph": self.wind_mph, "sky": self.sky, "sky_words": SKY_WORDS.get(self.sky, ""),
                "moisture": round(self.moisture, 2), "firmness": self.firmness,
                "ground_words": self.ground_words,
                "forecast": bool(self.forecast), "where": (self.forecast or {}).get("where", "")}


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

    def __init__(self, players, course, holes=None, handicaps=None, seed=None, seconds=30.0, forecast=None):
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
        self.before = {}                 # player -> the ball before their last stroke, for a mulligan
        # Luck, earned: a player who answered along with somebody else's
        # stroke and got it right has a little on their side for their next
        # one - the near half of the club's spread, no leak, no bad kick,
        # a kind bounce; on a foul ball, out of the water. One stroke, then
        # it is spent. Ignoring the question or missing it costs nothing.
        self.luck = set()
        self.mulligans = {}              # player -> the hole they took one on
        self._who = None               # whose stroke is being played
        # Not every golfer hits it the same. Power is a factor on every
        # club's length; wildness a factor on the leak. People are 1.0 and
        # 1.0 - the question is their swing. Practice players are given a
        # spread by the room, so a foursome is four different golfers.
        self.power = {p: 1.0 for p in self.players}
        self.wild = {p: 1.0 for p in self.players}
        self.balls = {}
        self.day = Day(self.rng, (course.get("wind") or {}).get("typical_mph", 10), forecast)
        self.playoff = []          # players still in a playoff, if one
        self.playoff_holes = 0
        self._winner = None
        self.history = []
        self.logs = {p: {} for p in self.players}       # player -> hole n -> every stroke's words
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

    # The day's wind, as the round has always been asked for it - and set,
    # which the tests do to read the wind's yards exactly.
    @property
    def wind_mph(self):
        return self.day.wind_mph

    @wind_mph.setter
    def wind_mph(self, mph):
        self.day.wind_mph = mph
        self.day.mean = mph

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
        if self.hole_index > 0:
            self.day.next_hole()
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

    def wind_clock(self, h, kind=None):
        """Which hour of the clock this hole's wind is out of.

        The card gives the arc - with, into or across, and across off the
        side the course plays it - and the hour is drawn inside that arc
        from the hole's own number rather than from the round's generator,
        so the same hole is the same wind every round while the eighteen
        are not all quartering the same way. `kind` is the wind as it was
        resolved for this shot, which matters on a swirling hole where it
        is drawn afresh each time.
        """
        kind = kind or h.get("wind", "across")
        if kind == "across":
            kind = f"across-{self.wind_from(h)}"
        arc = WIND_ARC.get(kind)
        if not arc:
            return None
        # Seeded by the hole's own number - "n" on the card - and the arc,
        # not by self.rng: the generator is the round's, and advancing it
        # here would move every later draw in the round.
        seed = (int(h.get("n") or 0) * 31 + sum(ord(c) for c in kind)) % len(arc)
        return arc[seed]

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
        if ball.lie == "fringe":
            return ["wedge", "putter"]
        longest = LIES[ball.lie][1]
        return list(CLUB_ORDER[CLUB_ORDER.index(longest):])

    def ahead(self, player, club=None):
        """What lies in the line of this player's next shot, as a caddie
        would say it at address: the hazards down the line from the ball
        toward the mark, each with its yards from the ball, its side, and
        whether it is in play with the club in hand - within the club's
        reach and run, foreground - or beyond, where a shot at the mark
        that gets away goes, background. A hazard off to the other side
        of the line from the ball and the mark is not in the line."""
        h = self.hole()
        ball = self.balls.get(player)
        if h is None or ball is None or ball.done() or ball.lie in ("green", "fringe"):
            return []
        club = club or self.default_club(player)
        if not club or club == "putter":
            return []
        mark = self.aim(player) or {"at": h["yards"], "off": 0}
        reach = self.reach(player, club) + self.expected_roll(club, "fairway", self.wind_clock(h)) * ROLL_NOISE[1]
        half = fairway_half(h)
        # the sides the line runs through: the ball's, the mark's, and the
        # middle when either is near it
        mark_off = int(mark.get("off") or 0)
        sides = {side_of(ball.off, half), side_of(mark_off, half)}
        if any(abs(o) <= half for o in (ball.off, mark_off)):
            sides |= {"", "across", "front", "centre", "around", "beyond"}
        # a bunker to one side is in the line of a club that can spray that
        # far: the driver's, on most holes; not the wedge's
        if CLUB_SPREAD.get(club, AIM) >= half - abs(mark_off) - 2:
            sides |= {"left", "right"}
        out = []
        for hz in h.get("hazards", []):
            if hz["to"] <= ball.at or hz.get("side", "") not in sides:
                continue
            at = int(hz["from"] - ball.at)
            if hz.get("side") == "beyond" and at < 0:
                at = 0
            out.append({"kind": hz["kind"], "name": hz.get("name") or hz["kind"], "at": max(0, at),
                        "to": int(hz["to"] - ball.at), "side": hz.get("side", ""),
                        "where": "in-play" if hz["from"] <= ball.at + reach else "beyond"})
        out.sort(key=lambda z: z["at"])
        return out[:2]

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
        if ball.lie == "fringe":
            return "putter"                 # through the collar: the Texas wedge; the wedge is there to choose
        left = abs(h["yards"] - ball.at)
        for club in reversed(allowed):
            if self.reach(player, club) >= left:
                return club
        # None reaches: the longest - unless a full swing with it, and the
        # run after, would find water lying across the fairway. Then the
        # longest that stops short of it: the lay-up every golfer knows.
        for club in allowed:
            # with room for the club's spread and a lively bounce
            far = (ball.at + self.reach(player, club) + CLUB_SPREAD.get(club, AIM)
                   + self.expected_roll(club, "fairway", self.wind_clock(h)) * ROLL_NOISE[1])
            water = self._in_band(h, int(far), kinds=("water",))
            crossing = [hz for hz in h.get("hazards", []) if hz["kind"] == "water"
                        and hz.get("side", "") in SIDE_BANDS[""] and ball.at < hz["from"] <= far]
            if not water and not crossing:
                return club
        return allowed[-1]

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
        if ball.lie in ("green", "fringe"):
            # On the green the mark is anywhere on it, in feet if need be:
            # the cup, or the spot above it the break wants.
            half = h["green"] / 2 + 2
            at = max(h["yards"] - half, min(h["yards"] + half, at))
            off = max(-(green_half(h) + 2), min(green_half(h) + 2, off))
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

    def approaching(self, player):
        """Whether this golfer's next stroke is at the green: the club in
        hand reaches the pin, or the ball is inside a wedge of it. The
        screens zoom the map to the green then, so the mark can be put on
        the fringe or the front edge rather than somewhere near the flag."""
        h = self.hole()
        ball = self.balls.get(player)
        if h is None or ball is None or ball.done() or ball.lie in ("green", "fringe"):
            return False
        left = h["yards"] - ball.at
        if left <= APPROACH_FROM:
            return True
        club = self.default_club(player)
        return bool(club and club != "putter" and self.reach(player, club) >= left)

    def expected_roll(self, club, lie="fairway", hour=None, carry=None, most=None, flair=None):
        """How far a ball with this club is expected to run on after it
        lands there: what a golfer allows for when landing it short. A
        full swing unless the carry is given against the club's most.

        ``hour`` is the clock the wind is out of; downwind the ball runs on
        and into it the ball sits down, which is the tail component of it.
        """
        return run_yards(club, lie, hour, carry, most, flair, self.day.firmness)

    def _carry(self, ball, club, hour, left, mph=None):
        """How far the ball goes. A club that can reach the mark is hit at
        it and lands near it; one that cannot is a full swing and goes its
        length. The wind has its say on both. Nothing about the answer but
        that it was right reaches here: the swing is not timed.

        ``mph`` is this stroke's wind - one gust, drawn once by the caller
        and handed to the carry, the roll and the drift alike, because a
        ball cannot be carried by one wind and blown sideways by another.
        """
        most = CLUBS[club] * LIES[ball.lie][0] * self.power.get(self._who, 1.0)
        wind_yards = wind_carry(hour) * (self.day.gust() if mph is None else mph)
        spread = CLUB_SPREAD.get(club, AIM) * (0.5 if getattr(self, "_lucky", False) else 1.0)
        if most + wind_yards >= abs(left):
            # Aimed - at the pin, from either side of it, within the club's spread.
            return round(left + self.swing.uniform(-spread, spread) + wind_yards * 0.25)
        # A full swing: the club's length, give or take its spread.
        return max(10, round(most + wind_yards + self.swing.uniform(-spread, spread)))

    def _in_band(self, h, at, off=None, kinds=("water", "bunker", "rough")):
        """The hazard a ball at these yards is in, if any, of these kinds.

        Along the hole and across it both. `off` is the ball's yards off the
        line; None asks only "is there one at this distance", which is what
        the caddie's look-ahead wants.

        This used to take a set of side labels instead of the ball's actual
        line, which is how the picture and the play came apart: every ball
        whose label matched was in the hazard however far from it it was,
        and every ball whose label did not could sit in the middle of one.
        """
        for hz in h.get("hazards", []):
            if hz["kind"] not in kinds:
                continue
            if not (hz["from"] <= at <= hz["to"]):
                continue
            if off is not None and not hazard_covers(h, hz, off):
                continue
            return hz
        return None

    def _fair(self, h, ball, club, adept=False):
        """A correct answer: the ball flies, and the course has its say. An
        adept answer gets the shot a good golfer would have played from
        there - see FLAIR_CALLS."""
        wind = self.wind_on(h)
        # One wind, for everything this stroke does. The carry used to draw
        # its own gust while the drift read the hole's steady wind, so a
        # ball could be held up by twenty-five and blown sideways by
        # fifteen on the same swing. The hour it is out of, and the mph it
        # is blowing at this instant, are settled here and handed on.
        hour = self.wind_clock(h, wind)
        mph = self.day.gust()
        if club == "putter" or ball.lie == "green":
            return self._putt(h, ball, right=True, adept=adept)
        if ball.lie == "fringe":
            # A putt leaves the ball at fractional yards; a chip from the
            # collar is read in whole ones like every other shot.
            ball.at, ball.off = int(round(ball.at)), int(round(ball.off))
        left_before = h["yards"] - ball.at
        # The mark: the pin down the line unless the golfer set one. The
        # shot is played at the mark; the pin is what is left after it.
        mark = self.aim(self._who) or {"at": h["yards"], "off": 0, "set": False}
        to_mark = mark["at"] - ball.at
        if not mark.get("set") and club != "putter":
            # Nobody aims at the pin with a club that runs: the ball is
            # landed short by what it is expected to release on the green,
            # and the run does the rest. A golfer who set a mark gets it.
            most = CLUBS[club] * LIES[ball.lie][0] * self.power.get(self._who, 1.0)
            if most >= to_mark:
                to_mark -= int(round(self.expected_roll(club, "green", hour, to_mark, most) * 0.8))
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
            carry = self._carry(ball, club, hour, to_mark, mph)
            ball.lie = lie_was
        elif flair == "stinger":
            carry = self._carry(ball, club, None, to_mark, mph)  # the wind's say, taken away
        elif flair == "launched":
            carry = round(self._carry(ball, club, hour, to_mark, mph) * 1.12)
        elif adept and self.reach(self._who, club) >= to_mark:
            flair = "pure"                    # the club reaches: stiff, all over the mark
            carry = round(to_mark + self.rng.uniform(-4, 4))
        elif adept:
            flair = "launched"                # a full swing with everything in it
            carry = round(self._carry(ball, club, hour, to_mark, mph) * 1.12)
        else:
            carry = self._carry(ball, club, hour, to_mark, mph)
        landed = ball.at + carry
        # Across the line: at the mark's side of it, within the club's
        # spread - and, for a plain shot, the leak: a push off to one side.
        lucky = getattr(self, "_lucky", False)
        spread = CLUB_SPREAD.get(club, AIM) * 0.6 * (0.5 if lucky else 1.0)
        off = mark["off"] + (self.swing.uniform(-4, 4) if flair == "pure" else self.swing.uniform(-spread, spread))
        leaked = None
        if not adept and not lucky and self.swing.random() < CLUB_LEAK.get(club, 0.0) * self.wild.get(self._who, 1.0):
            leaked = "left" if (off < 0 if off else self.swing.random() < 0.5) else "right"
            off += -LEAK_PUSH if leaked == "left" else LEAK_PUSH
            if abs(off) <= fairway_half(h):           # a leak goes off the fairway, by definition
                off = (-1 if leaked == "left" else 1) * (fairway_half(h) + 3)
        # A crosswind drifts the ball in flight, off the side it blows from,
        # by as much as the ball is up there to be pushed - this stroke's
        # gust, this club, this much of a swing. Any hour with a sideways
        # component in it drifts, not only a dead crosswind: a wind out of
        # ten o'clock is mostly in your face and still moves the ball.
        if hour is not None and mph:
            most = CLUBS[club] * LIES[ball.lie][0] * self.power.get(self._who, 1.0)
            off += wind_drift(hour, mph, club, carry, most, flair)
        off = int(round(max(-OFF_MOST, min(OFF_MOST, off))))
        from_the_tee = ball.strokes == 0
        ball.strokes += 1
        edge = green_edge(h)                     # the green's depth either side of the pin
        # Then the roll: the club's life, on the surface it came down on,
        # with the wind. A pure shot is stiff - it lands and stops; a flop
        # has already been dealt with. The ball is read where it comes to
        # rest, and a roll across a creek is a ball in the creek. The
        # fringe brakes a ball that comes down on it and lets the rest
        # trickle on - the chip through the collar every golfer plays.
        half = fairway_half(h)
        came_down = on_the_green(h, landed, off) or \
            ("sand" if (self._in_band(h, landed, off, kinds=("bunker",))) else
             "rough" if (side_of(off, half) or self._in_band(h, landed, off, kinds=("rough",))) else "fairway")
        roll, spun, kicked = 0, False, None
        if flair != "pure":
            most = CLUBS[club] * LIES[ball.lie][0] * self.power.get(self._who, 1.0)
            roll = self.expected_roll(club, came_down, hour, abs(carry), most, flair) * (
                self.swing.uniform(1.0, ROLL_NOISE[1]) if lucky and came_down != "green" else self.swing.uniform(*ROLL_NOISE))
            if came_down == "green":
                # The green's fall: toward the player checks the ball, away
                # releases it, across nudges the roll toward the fall.
                s = self.slope(h)
                if s["falls"] == "front":
                    roll *= max(0.4, 1 - SLOPE_RELEASE * s["grade"])
                elif s["falls"] == "back":
                    roll *= 1 + SLOPE_RELEASE * s["grade"]
                else:
                    off += (-1 if s["falls"] == "left" else 1) * SLOPE_DRIFT * s["grade"] * roll
                if club in SPIN_ODDS and not adept and self.swing.random() < SPIN_ODDS[club]:
                    lo, hi = SPIN_BACK[club]
                    roll, spun = -self.swing.uniform(lo, hi), True
            elif came_down in ("fairway", "rough") and not lucky and self.swing.random() < KICK_ODDS:
                kicked = "left" if self.swing.random() < 0.5 else "right"
                off += (-1 if kicked == "left" else 1) * self.swing.uniform(*KICK_YARDS)
            off = int(round(max(-OFF_MOST, min(OFF_MOST, off))))
        roll = int(round(roll))
        ran_through = None
        if roll > 0:
            for y in range(landed + 1, landed + roll + 1):
                hz_on_the_way = self._in_band(h, y, off, kinds=("water", "bunker"))
                # The card puts the water beyond a green at the pin's own
                # yardage; the green runs on past the pin, and a ball still
                # on it has not gone in.
                if hz_on_the_way and hz_on_the_way.get("side") == "beyond" and y <= h["yards"] + edge \
                        and abs(off) <= green_half(h):
                    continue
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
        side = side_of(off, half)
        rests_on = on_the_green(h, rest, off)
        on_green = rests_on == "green"
        # Beside the green, off its collar, is rough: the fairway ends at
        # the front of the fringe.
        beside_green = rests_on is None and abs(left) <= edge + FRINGE
        if beside_green and not side:
            side = "left" if off < 0 else "right"
        # On the green is on the green, whatever bunkers ring it. Off it,
        # what is where the ball came to rest: down the middle, a creek
        # across the fairway, a bunker in front of the green, the ocean
        # beyond it; off to a side, that side's trouble - or the first cut,
        # when the card has nothing there.
        hz = ran_through or (None if rests_on or flair == "worked" else self._in_band(h, rest, off))
        landed = rest
        ran = (f", spun back {-roll * 3} feet" if spun and roll < 0
               else f", released {roll}" if (came_down == "green" and roll >= 3)
               else f", took the fringe and trickled {roll * 3} feet" if (came_down == "fringe" and 1 <= roll <= 3)
               else f", ran {roll} more" if roll >= 4
               else ", checked up" if (came_down == "green" and roll <= 1 and club in ("iron", "wedge"))
               else ", the fringe checked it" if (came_down == "fringe" and roll < 1) else "")
        if kicked:
            ran = f", kicked {kicked}" + ran
        wide = f" {side}" if side else ""
        # A ball that arrives at water flat and fast skips off it, the way
        # a stone does. Never offered and never aimable - see SKIP_ANGLE -
        # and loud when it happens, because a ball that goes in the water
        # and comes out reads as a fault unless the game says otherwise.
        if hz and hz["kind"] == "water" and not side:
            angle = descent_angle(club, flair)
            pace = landing_speed(club, abs(carry), most if flair != "pure" else None)
            if skips(angle, pace, self.swing):
                wet_name = hz["name"] or "the water"
                skipped = self.swing.randint(*SKIP_RUN)
                landed = min(landed + skipped, h["yards"] + edge)
                log.info("golf: skipped one off %s - %s in at %.0f degrees, "
                         "%d yards on", wet_name, club, angle, skipped)
                hz = self._in_band(h, landed, off)
                if not (hz and hz["kind"] == "water"):
                    ball.at, ball.off = landed, off
                    rests_on = on_the_green(h, landed, off)
                    ball.lie = rests_on or (hz["kind"] if hz else "fairway")
                    left = int(round(h["yards"] - landed))
                    return {"kind": ball.lie, "flair": "skipped",
                            "words": f"{club}, {carry} yards - skipped off "
                                     f"{wet_name} and came out "
                                     f"{skipped} on, {left} to go",
                            "carry": carry, "wind": wind, "skipped": skipped,
                            "left": left, "off": off}
                log.debug("golf: the skip came down in %s again - wet after all", wet_name)
        if hz and hz["kind"] == "water":
            if side:
                # A right answer that drifted stops on the bank: no penalty,
                # a bad lie. The water is a wrong answer's to find.
                ball.at, ball.off, ball.lie = landed, off, "rough"
                return {"kind": "rough", "words": f"{club}, {carry} yards - out to the {side}, stopped on the bank of "
                                                  f"{hz['name'] or 'the water'} - {left} to go, from the rough",
                        "carry": carry, "wind": wind, "leak": leaked, "left": left, "off": off}
            how = "ran into" if ran_through else "into"
            at_before = ball.at
            ball.at, ball.off = landed, off
            dropped = self._drop(h, ball, hz, side)
            ball.at = max(ball.at, at_before)
            left = int(round(h["yards"] - ball.at))
            return {"kind": "water", "words": f"{club}, {carry} yards - {how} {hz['name'] or 'the water'}; "
                                              f"{dropped}, and a penalty stroke - {left} to go",
                    "carry": carry, "roll": roll, "wind": wind, "hazard": hz["name"], "left": left, "off": ball.off}
        if on_green:
            ball.at, ball.off = landed, off
            ball.lie = "green"
            feet = max(3, int(round((abs(left) ** 2 + off ** 2) ** 0.5 * 3)))
            onto = (" - through the fringe and onto the green" if came_down == "fringe"
                    else " - ran onto the green" if came_down != "green" and roll >= 4 else f"{ran} - on the green")
            if came_down == "green" and left < 0 and not spun and roll >= 3:
                onto = f", released {roll} past the pin - on the green"
            return {"kind": "green", "words": f"{club}, {abs(carry)} yards{onto}, {feet} feet",
                    "carry": carry, "roll": roll, "wind": wind, "feet": feet, "flair": flair, "off": off,
                    "via": "fringe" if came_down == "fringe" else None}
        if rests_on == "fringe":
            # Stopped on the collar: putt it from there, or chip it.
            ball.at, ball.off = landed, off
            ball.lie = "fringe"
            feet = max(3, int(round((abs(left) ** 2 + off ** 2) ** 0.5 * 3)))
            where = ("short" if left > 0 and abs(off) <= green_half(h) else "long" if left < 0 and abs(off) <= green_half(h)
                     else "left" if off < 0 else "right")
            return {"kind": "fringe", "words": f"{club}, {abs(carry)} yards{ran} - on the fringe, {where}, {feet} feet",
                    "carry": carry, "roll": roll, "wind": wind, "feet": feet, "flair": flair, "off": off}
        if beside_green and not hz:
            # Off the collar, beside the green: the rough that borders it.
            ball.at, ball.off, ball.lie = landed, off, "rough"
            feet = int(round((abs(left) ** 2 + off ** 2) ** 0.5 * 3))
            return {"kind": "rough", "words": f"{club}, {abs(carry)} yards{ran} - {side} of the green, in the rough beside it, {feet} feet",
                    "carry": carry, "roll": roll, "wind": wind, "leak": leaked, "left": left, "off": off}
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
        where = "fairway" if abs(off) <= half / 2 else f"{side_of(off, half) or ('left' if off < 0 else 'right')} side of the fairway"
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
        from_fringe = ball.lie == "fringe"
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
            if from_fringe:
                rolled *= 1 - FRINGE_DRAG            # the collar takes some of it
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
        head = (f"putt from the fringe, {feet} feet" if from_fringe else f"putt, {feet} feet") + (f", {words_slope}" if words_slope else "")
        if holed:
            ball.at, ball.off, ball.holed = h["yards"], 0, True
            return {"kind": "holed", "putt": True, "feet": feet, "words": f"{head} - holed", "carry": 0, "left_feet": 0}
        left = (rx * rx + ry * ry) ** 0.5
        if right and left <= TAP_IN:
            ball.strokes += 1                       # the tap-in: a stroke, no question
            ball.at, ball.off, ball.holed = h["yards"], 0, True
            return {"kind": "holed", "putt": True, "feet": feet, "tap_in": True,
                    "words": f"{head} - to {'a foot' if left < 1.5 else str(int(round(left))) + ' feet'}, that's good - and the tap-in is a stroke",
                    "carry": 0, "left_feet": 0}
        ball.at, ball.off = h["yards"] + rx / 3.0, ry / 3.0
        left_ft = max(1, int(round(left)))
        stopped_on = on_the_green(h, ball.at, ball.off)
        if stopped_on is None:
            ball.lie = "rough"                      # raced it off the green
            ball.at, ball.off = round(ball.at), round(ball.off)
            return {"kind": "missed", "putt": True, "feet": feet, "words": f"{head} - raced it off the green",
                    "carry": 0, "left_feet": left_ft}
        ball.lie = stopped_on
        how = ("holed" if holed else (f"{left_ft} feet past" if (rx * ux + ry * uy) > (bx * ux + by * uy) + length else
                                     f"{left_ft} feet short" if left_ft and rolled < length * 0.9 else f"to {left_ft} feet"))
        if not right:
            how = f"left it short, {left_ft} feet" if rolled < length else f"raced it past, {left_ft} feet"
        if stopped_on == "fringe":
            how += ", onto the fringe"
        return {"kind": "green" if right else "missed", "putt": True, "feet": feet, "words": f"{head} - {how}",
                "carry": 0, "left_feet": left_ft}

    def _drop(self, h, ball, hz, side=""):
        """The ball is in the water: a penalty stroke, and a drop where it
        went in - short of water across the hole, on the bank beside water
        down a side, behind the green when it flew into the sea beyond.
        Not stroke and distance, which is the harsh option and the slow
        one; this is what a golfer does. Returns where, in words."""
        ball.strokes += 1                            # the penalty
        half = fairway_half(h)
        where = hz.get("side", "")
        if where == "beyond":
            ball.at = int(round(h["yards"] + green_edge(h) + 2))
            ball.off = int(round(max(-half, min(half, ball.off))))
            ball.lie = "rough"
            return "dropped behind the green, in the rough"
        if where in ("left", "right") or side in ("left", "right"):
            s = where if where in ("left", "right") else side
            ball.at = int(round(max(ball.at, min(hz["to"], max(hz["from"], ball.at)))))
            ball.off = (-1 if s == "left" else 1) * (half + 3)
            ball.lie = "rough"
            return f"dropped on the bank, {s}"
        ball.at = int(round(hz["from"] - 3))
        ball.off = int(round(max(-half, min(half, ball.off))))
        ball.lie = "fairway" if abs(ball.off) <= half else "rough"
        return f"dropped short of {hz.get('name') or 'the water'}"

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
            # short, and off to one side - the rough is beside the fairway,
            # not down the middle of it, and the strip shows it there
            ball.at += max(20, round(CLUBS[club] * 0.4))
            ball.lie = "rough"
            side = -1 if ball.off < 0 else 1 if ball.off > 0 else self.swing.choice((-1, 1))
            ball.off = side * int(round(fairway_half(h) + self.swing.uniform(4, 12)))
            return {"kind": "rough", "words": f"{club}, a foul ball - short and into the rough on the {'left' if side < 0 else 'right'}",
                    "carry": 0, "off": ball.off}
        weights = {"water": 2, "bunker": 3, "rough": 3}
        if getattr(self, "_lucky", False) and any(x["kind"] != "water" for x in ahead):
            ahead = [x for x in ahead if x["kind"] != "water"]     # luck keeps it dry
        hz = self.rng.choices(ahead, weights=[weights[x["kind"]] for x in ahead])[0]
        name = hz["name"] or hz["kind"]
        if hz["kind"] == "water":
            at_before = ball.at
            ball.at = max(ball.at + 10, hz["from"])
            dropped = self._drop(h, ball, hz)
            ball.at = max(ball.at, at_before)
            left = int(round(h["yards"] - ball.at))
            return {"kind": "water", "words": f"{club}, a foul ball - into {name}; {dropped}, and a penalty stroke - {left} to go",
                    "carry": 0, "hazard": name, "left": left, "off": ball.off}
        # In the hazard it just named, and in the part of it the card draws.
        # This used to push the ball ten yards on whatever that overran, and
        # set it beside the fairway whatever side of the hole the hazard was
        # actually on - so a ball "in the bunker" could come to rest past the
        # end of it, or thirty yards away from it across the hole.
        ball.at = int(min(max(ball.at + 10, hz["from"]), hz["to"]))
        ball.lie = "sand" if hz["kind"] == "bunker" else "rough"
        spans = hazard_spans(h, hz)
        centre, width = min(spans, key=lambda s: abs(s[0] - ball.off))
        ball.off = int(round(centre + self.swing.uniform(-width / 2, width / 2)))
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
        # Farthest from the hole - as the crow flies, along and across
        # both. Along alone had a ball pin-high on the collar, fifteen
        # yards to the side, counted as nearer than one three yards short
        # on the green, and its owner watching the other putt.
        def from_hole(p):
            b = self.balls[p]
            return ((h["yards"] - b.at) ** 2 + (b.off or 0) ** 2) ** 0.5
        return max(playing, key=lambda p: (from_hole(p), -order[p]))

    def _stroke(self, h, p, ball, answer):
        """One player's stroke with one answer: where the ball went, in
        words, and the ball moved."""
        a = answer or {}
        self._who = p
        played_from = ball.lie
        # Where the ball was, kept for a mulligan: the stroke undone, a
        # fresh ball from the same spot.
        self.before[p] = {"hole": h["n"], "at": ball.at, "off": ball.off, "lie": ball.lie, "strokes": ball.strokes,
                          "holed": ball.holed, "picked_up": ball.picked_up, "log": len(ball.log),
                          "aim": self.aims.get(p)}
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
        self._lucky = p in self.luck
        self.luck.discard(p)              # spent on this stroke, whichever way it goes
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
        if self._lucky:
            shot["luck"] = True
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
        elif ball.holed and shot.get("tap_in"):
            # The tap-in is a stroke - a conceded putt counts, on any card -
            # and it is written as a line of its own so the strokes on the
            # card and the lines in the history are the same number. It
            # used to be folded into the putt's line, and a golfer who
            # counted the lines was one short and called it cheating.
            shot["also"] = f"tap-in - holed, {ball.strokes} for {score_name(ball.strokes, h['par'])}"
            shot["score"] = score_name(ball.strokes, h["par"])
        elif ball.holed:
            shot["words"] += f" - {ball.strokes} for {score_name(ball.strokes, h['par'])}"
            shot["score"] = score_name(ball.strokes, h["par"])
        shot.update(strokes=ball.strokes, at=ball.at, off=ball.off, lie=ball.lie, club=club,
                    done=ball.done(), holed=ball.holed, aim=ball.last_aim, **{"from": played_from})
        self.aims.pop(p, None)            # a mark is for one stroke
        self.before[p]["foul"] = not bool(a.get("correct"))
        ball.log.append(shot["words"])
        if shot.get("also"):
            ball.log.append(shot["also"])
        self.logs.setdefault(p, {})[h["n"]] = list(ball.log)
        return shot

    def grant_luck(self, player):
        """A little luck for this player's next stroke - see self.luck."""
        if player in self.balls:
            self.luck.add(player)

    def can_mulligan(self, player):
        """Whether this golfer may take a mulligan now: their last stroke
        was on this hole and was a foul ball, the hole is still being
        played, and they have not had one on this hole. Once a hole, the
        way a friendly game gives it."""
        h = self.hole()
        b = self.before.get(player)
        ball = self.balls.get(player)
        if h is None or b is None or ball is None or b.get("hole") != h["n"] or not b.get("foul"):
            return False
        if self.mulligans.get(player) == h["n"] or ball.done():
            return False
        return True

    def mulligan(self, player):
        """The foul ball taken back: the ball, the strokes and the mark as
        they were before it; the words say so on the card; the next
        stroke is a fresh question from the same spot. Returns the words,
        or None when there is no mulligan to be had."""
        if not self.can_mulligan(player):
            return None
        h = self.hole()
        b = self.before[player]
        ball = self.balls[player]
        ball.at, ball.off, ball.lie = b["at"], b["off"], b["lie"]
        ball.strokes, ball.holed, ball.picked_up = b["strokes"], b["holed"], b["picked_up"]
        del ball.log[b["log"]:]
        if b.get("aim"):
            self.aims[player] = dict(b["aim"])
        self.mulligans[player] = h["n"]
        b["foul"] = False
        where = "the tee" if ball.strokes == 0 else f"{int(round(h['yards'] - ball.at))} out"
        words = f"mulligan - a fresh ball from {where}"
        ball.log.append(words)
        self.logs.setdefault(player, {})[h["n"]] = list(ball.log)
        # the history keeps the foul ball's row, with the mulligan written on it
        for row in reversed(self.history):
            if row.get("hole") == h["n"] and player in (row.get("shots") or {}):
                row["shots"][player]["mulligan"] = words
                break
        return words

    def _after(self, h, shots):
        """The hole's state after some strokes; the next hole if it is done."""
        hole_done = all(b.done() for b in self.balls.values())
        row = {"hole": h["n"], "par": h["par"], "shots": shots, "hole_done": hole_done,
               "wind_mph": self.day.wind_mph}
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

    def choose(self, candidates, player, seen=None):
        """One of `candidates` for this player's stroke.

        Questions nobody on this unit has met come first, the way the
        tournament draws - a group that plays every Thursday should not
        meet the same forty questions every Thursday. Then, where the pool
        has measured hardness, the draw leans toward what the lie calls
        for: nearer the wanted hardness is likelier, but every question can
        come. It used to take the three nearest and pick one of those,
        which put the same three up on every first fairway stroke of every
        round and never showed a section's easy or hard questions at all."""
        ids = list(candidates)
        if not ids:
            return None
        if seen:
            fresh = [q for q in ids if q not in seen]
            if fresh:
                ids = fresh
        ranked = [q for q in ids if q in self.hardness]
        if len(ranked) < 3:
            return self.rng.choice(ids)
        ball = self.balls.get(player)
        want = LIE_HARDNESS.get(ball.lie if ball else "fairway", 0.5)
        lo, hi = min(self.hardness[q] for q in ranked), max(self.hardness[q] for q in ranked)
        span = (hi - lo) or 1.0
        weights = [math.exp(-(((self.hardness[q] - lo) / span - want) / CHOOSE_WIDTH) ** 2 / 2) for q in ranked]
        return self.rng.choices(ranked, weights=weights)[0]

    def draw(self, by_section, all_ids, player, seen=None):
        """The question for this stroke, from the pool as the room presents
        it: `by_section` every question by section, `all_ids` every
        question, `seen` the questions anybody on this unit has met. One
        area per hole until it runs dry; every question once, the unmet
        first; then the misses, once more each - on purpose, since a
        question missed is one to meet again; then by hardness against
        the lie."""
        left = {sec: [q for q in ids if q not in self.asked] for sec, ids in by_section.items()}
        section = self.pick_section(left)
        if section is not None:
            return self.choose(left[section], player, seen), section
        again = [q for q in self.missed if self.asked.get(q, 0) < 2]
        if again:
            return again[0], None
        fewest = min(self.asked.get(q, 0) for q in all_ids) if all_ids else 0
        return self.choose([q for q in all_ids if self.asked.get(q, 0) == fewest], player, seen), None

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
            "hole_wind": h.get("wind") if h else None, "wind_mph": self.day.wind_mph,
            "day": self.day.state(), "ground_words": self.day.ground_words,
            "holes_played": self.hole_index, "holes": len(self.holes),
            "slope": self.slope(h) if h else None,
            "balls": {p: {"at": b.at, "off": b.off, "lie": b.lie, "strokes": b.strokes, "holed": b.holed,
                          "picked_up": b.picked_up, "left": int(round(h["yards"] - b.at)) if h else 0,
                          "feet": (int(round(((b.at - h["yards"]) ** 2 + b.off ** 2) ** 0.5 * 3)) if h and b.lie in ("green", "fringe") else None),
                          "approaching": self.approaching(p),
                          "aim": self.aim(p), "last_aim": b.last_aim,
                          "clubs": self.clubs_for(p), "default_club": self.default_club(p),
                          "can_mulligan": self.can_mulligan(p),
                          "luck": p in self.luck,
                          "log": list(b.log), "ahead": self.ahead(p)}
                      for p, b in self.balls.items()},
            # every stroke of every hole, in words, by player: the history a
            # name on the card opens, so a score can always be counted
            "logs": {p: {str(n): lines for n, lines in holes.items()} for p, holes in self.logs.items()},
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
