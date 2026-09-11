"""Tournament mode: cohorts of players racing the same question.

An instructor with a room full of people has a different problem from a lone
operator with a Pi on the bench. The material is the same; the shape of the
evening is not. This is the room layer - who is here, which cohort they are on,
what question is on the screen, and who got there first.

A tournament never shows an explanation. Everywhere else in ELMER the reason an
answer is right appears the moment somebody commits to one, because that is
where the learning is - but a tournament is a race, and stopping a hall of
people mid-round to read a paragraph is neither. The payload a round carries is
deliberately the question, its choices and its figure and nothing else; the
explanations are a keystroke away in the pool browser afterwards, which is when
somebody actually wants to argue about them.

Three things decide the design, and all three came from measuring this Pi
rather than guessing at it:

Round state is held in memory and written once when the round closes. The
answer path in ordinary study performs about seven separate commits, and SQLite
takes the write lock for each, which caps the unit near forty-six answers a
second. A race is precisely the case that would hit that ceiling - everybody
answers within the same second or two - so the hot path here does no database
work at all. What survives the evening is written at the end of the round.

Admission is capped and the cap moves. Sixty players answering at once took
five seconds to serve on a Pi 5; thirty took 642 ms. A party that quietly
degrades into a five-second lag is worse than one that says "this unit is
full" - so the room stops admitting before it gets there, and says so.

The race is timed by the player's own clock. Server arrival order measures
network jitter, which at thirty players spread across 300-600 ms - longer than
the difference in thinking that the race is meant to be about. The browser
knows when it painted the question and when the button was pressed, and that
interval is the only honest answer. It is bounded against the server's own
elapsed time, because a number the client supplies is a number the client can
invent, and somebody in a room full of radio amateurs will try.
"""
import random
import threading
import time
from collections import deque

from . import trivia
from .shootout import Shootout

# Measured on a Raspberry Pi 5: 30 players answering simultaneously were all
# served in 642 ms, 60 took 5068 ms. The knee is between the two, and 24 keeps
# a margin under it rather than sitting on it.
CAP_PER_UNIT = 24
COHORT_SIZE = 8
MAX_COHORTS = 4

# A round is scored on the players who answered. Somebody who wandered off to
# the coffee urn should not hold the room up for ever - but the clock is the
# only thing that ends a round early, so it has to be long enough to read a
# question and four choices without hurrying.
#
# Half a minute. A minute was generous to the point of being slack: the room
# spends most of it watching a question everybody has already answered, and a
# hall of tables moves at the speed of its slowest clock, not its slowest
# reader. Adjustable, because a room of first-timers reads slower than a club
# night, but not up to three minutes any more - nothing was using that except
# the wait.
DEFAULT_ROUND_SECONDS = 30.0

# The games a table can be playing.
TOURNAMENT = "tournament"
SHOOTOUT = "shootout"
MODES = (TOURNAMENT, SHOOTOUT)

# How long the picker gets to choose a subject before it goes round the
# table. A question has a clock and so must the pick, or a phone put down on
# the table with the pick on it holds everybody else there indefinitely.
# Longer than a question because there are thirty subjects to read, not four
# answers. Passing costs no letter: nobody shot, so nobody missed.
PICK_SECONDS = 45.0
REVEAL_SECONDS = 8.0

# Admission stops before the room is unpleasant, not after. These are the
# service times the unit is actually delivering, not a guess at its capacity.
SLOW_MS = 900.0          # a round-serving time that is starting to be felt
HEALTH_WINDOW = 40       # how many recent services the judgement is made on

# Devices poll rather than hold a socket open, so a player can first see the
# question up to one poll interval after the round opened, plus the network.
# This is how far under the round clock a reported time can honestly be, and
# therefore the most a made-up number can gain.
POLL_SECONDS = 1.0
DELIVERY_SLACK_MS = POLL_SECONDS * 1000.0 + 1500.0

# What a tournament can be run on. The amateur ladder is a difficulty in the
# ordinary sense - Technician then General then Extra, each harder than the
# last. The commercial elements are not a ladder and are not harder versions of
# each other: a marine permit, a radiotelephone license and a radar
# endorsement are three different jobs. They are here because a club that
# studies them should be able to hold a night on them too, and the game does
# not care which pool the questions came from.
DIFFICULTIES = {
    "technician": "tech2026", "general": "gen2023", "extra": "extra2024",
    "mrop": "element1", "grol": "element3", "radar": "element8",
}

# The track each belongs to, so a screen can group them rather than offering
# six flat options with no hint that three of them are not amateur radio.
TRACK_OF = {
    "technician": "amateur", "general": "amateur", "extra": "amateur",
    "mrop": "commercial", "grol": "commercial", "radar": "commercial",
}

LABELS = {
    "technician": "Technician", "general": "General", "extra": "Amateur Extra",
    "mrop": "Element 1 — Marine Radio Operator Permit",
    "grol": "Element 3 — General Radiotelephone (GROL)",
    "radar": "Element 8 — Ship Radar Endorsement",
}

# --- practice opponents -----------------------------------------------------
# One person alone with a question is studying, not playing. A table tops
# itself up with practice opponents so there is a race to be in, and gives the
# seats back the moment real people want them: a human joining retires a bot,
# which is the right way round - the machine yields to the person.
#
# The flag is carried the whole way out - to the table, to the net, into the
# round summary - because everything downstream needs it: a person joining
# displaces one, the host's panel shows which places are being held, and a
# name somebody takes over has to be known to have been free.
#
# What is done with it on a screen is that screen's business, and the big
# board deliberately does not mark them. A board with a dozen names on it
# reads as an evening; the same board with eight struck out as software reads
# as an empty room being flattered, and the room is what the screen at the
# front is for. Nothing is scored differently either way - a person beats them
# or loses to them on the same terms - so what is at stake is how a hall looks
# to the people standing in it, not what the numbers mean.
BOT_FLOOR = 0.6            # keep a cohort at least this full

# Named for the ladder in ranks.py, so what a bot is meant to represent is
# legible: accuracy, and the range of seconds it takes to answer.
BOT_SKILLS = {
    "Listener": (0.45, 6.0, 18.0),
    "Learner":  (0.62, 4.5, 14.0),
    "Operator": (0.78, 3.0, 10.0),
    "Elmer":    (0.90, 2.0, 7.0),
}

BOT_NAMES = ["Sparks", "Skip", "Static", "Hertz", "Marconi", "Doppler",
             "Ionos", "Ragchew", "Beacon", "Quench", "Pileup", "Grayline",
             "Whip", "Vertical", "Dipole", "Halyard"]


def _now():
    return time.monotonic()


class Player:
    """One person in the room, on one device - or a practice opponent."""

    def __init__(self, player_id, name, cohort_id, bot=None, cert_name=None):
        self.id = player_id
        self.name = name
        # What goes on a certificate, if they win one. The play name is what
        # the room sees on every board and phone; this is what they want on
        # the wall, and nobody sees it until it is printed. Somebody can play
        # a hamfest as "Sparks" and still take home a certificate with their
        # callsign on it - one never knows who is wandering about.
        self.cert_name = (cert_name or "").strip()[:48] or None
        self.cohort_id = cohort_id
        # None for a person; the skill level's name for a practice opponent.
        self.bot = bot
        self.joined_at = _now()
        self.last_seen = self.joined_at
        self.score = 0
        self.answered = 0
        self.correct = 0

    def as_dict(self):
        return {"id": self.id, "name": self.name, "cohort": self.cohort_id,
                "score": self.score, "answered": self.answered,
                "correct": self.correct, "bot": self.bot}


class Cohort:
    """A team of up to COHORT_SIZE players, scored together."""

    def __init__(self, cohort_id, name):
        self.id = cohort_id
        self.name = name
        self.score = 0
        self.rounds_won = 0

    def as_dict(self, players):
        mine = [p for p in players if p.cohort_id == self.id]
        return {"id": self.id, "name": self.name, "score": self.score,
                "rounds_won": self.rounds_won, "players": len(mine),
                "room": COHORT_SIZE - len(mine),
                "members": [p.as_dict() for p in mine]}


class Round:
    """One question, put to the room, and the answers that came back."""

    def __init__(self, number, pool_id, question_id, answer_index, seconds,
                 payload=None, tag=None):
        self.number = number
        self.pool_id = pool_id
        self.question_id = question_id
        # The index of the right answer *in the order the room was shown*.
        # One shuffle serves the whole room: two players looking at the same
        # question in different orders are not racing the same question.
        self.answer_index = answer_index
        self.payload = payload or {}
        # Which net-control round this is, when the table is part of a larger
        # competition. None when the table is running its own evening.
        self.tag = tag
        self.opened_at = _now()
        self.seconds = seconds
        self.answers = {}          # player_id -> dict
        self.bot_plan = {}         # player_id -> what a practice player will do
        self.closed = False
        self.winner_cohort = None
        # One card for the whole table this round, drawn here so everybody
        # who has answered is reading the same thing while they wait.
        self.card = trivia.draw()

    @property
    def remaining(self):
        return max(0.0, self.seconds - (_now() - self.opened_at))

    def expired(self):
        return self.remaining <= 0.0


def _answer_text(rnd):
    """The right answer in words, or None if the payload cannot say."""
    choices = (rnd.payload or {}).get("choices") or []
    try:
        return choices[rnd.answer_index]
    except (IndexError, TypeError):
        return None


class Room:
    """The party on this unit.

    One instance per ELMER process. Every method that touches shared state
    takes the lock: the web server is threaded, and a race decided by which
    thread got scheduled first is not a race anybody wants to be in.
    """

    def __init__(self, cap=CAP_PER_UNIT, cohorts=2):
        self.lock = threading.RLock()
        self.cap = cap
        self.players = {}
        self.cohorts = {}
        self.round = None
        self.round_number = 0
        self.history = []
        self._next_id = 1
        self._service = deque(maxlen=HEALTH_WINDOW)
        self.bots_wanted = False
        self.open = True
        # When the first question goes up on its own, or None for a table
        # waiting on somebody to press something. Somebody who has just
        # scanned the code is looking at a screen that says "waiting", and a
        # screen that waits forever is the same as a broken one. Held here as
        # a time rather than as a timer: this module has no clock in it on
        # purpose, so what fires it lives where the clocks already are.
        self.start_at = None
        # Which game this table is playing. A tournament asks the blueprint's
        # questions in order and everybody answers the same ones; a shootout
        # hands one player the choice of subject and the rest have to keep up.
        self.mode = TOURNAMENT
        self.shootout = None
        self.pick = None           # the subject chosen, waiting to be asked
        self.pick_seconds = PICK_SECONDS
        self._pick_since = None    # (when the wait began, on whom)
        for i in range(max(1, min(int(cohorts), MAX_COHORTS))):
            cid = i + 1
            self.cohorts[cid] = Cohort(cid, f"Cohort {chr(64 + cid)}")

    # ---------------------------------------------------------------- health

    def note_service(self, ms):
        """Record how long a request actually took, for the moving cap."""
        with self.lock:
            self._service.append(float(ms))

    def health(self):
        """What the unit is delivering, and how much room is left.

        The cap is not a constant dressed up as one. It starts at the measured
        figure and comes down when the unit is visibly slower than it should
        be, so a party on a loaded Pi - or a Pi also running TowerWitch, the
        repeater service and a kiosk browser - admits fewer people rather than
        admitting the same number and serving them all badly.
        """
        with self.lock:
            recent = sorted(self._service)
            if len(recent) >= 8:
                p95 = recent[min(len(recent) - 1, int(len(recent) * 0.95))]
            else:
                p95 = 0.0
            cap = self.cap
            if p95 > SLOW_MS * 2:
                cap = max(COHORT_SIZE, int(self.cap * 0.5))
            elif p95 > SLOW_MS:
                cap = max(COHORT_SIZE, int(self.cap * 0.75))
            return {"players": len(self.players), "cap": cap,
                    "hard_cap": self.cap, "p95_ms": round(p95, 1),
                    "seats": max(0, cap - len(self.players)),
                    "healthy": p95 <= SLOW_MS, "open": self.open}

    # ----------------------------------------------------------------- join

    def _seat_cohort(self, wanted=None):
        """Which cohort a joiner lands in: the one asked for if it has room,
        else the emptiest, so teams fill evenly rather than first-come."""
        counts = {cid: 0 for cid in self.cohorts}
        for p in self.players.values():
            counts[p.cohort_id] = counts.get(p.cohort_id, 0) + 1
        if wanted in self.cohorts and counts.get(wanted, 0) < COHORT_SIZE:
            return wanted
        free = [(n, cid) for cid, n in counts.items() if n < COHORT_SIZE]
        return min(free)[1] if free else None

    def join(self, name, cohort=None, bot=None, cert_name=None):
        """Admit a player, or say plainly why not.

        Returns (player, None) or (None, reason). A person arriving at a full
        table takes a practice opponent's seat rather than being turned away -
        the bots are there to make a thin room playable, not to occupy it.
        """
        with self.lock:
            if not self.open:
                return None, "the room is closed"
            if not bot:
                # A person is never turned away while software holds a seat.
                while (self.health()["seats"] <= 0
                       and any(p.bot for p in self.players.values())):
                    if not self.retire_bot():
                        break
            state = self.health()
            if state["seats"] <= 0:
                if state["cap"] < state["hard_cap"]:
                    return None, ("this unit is busy and has stopped taking "
                                  "players to keep the round quick - try the "
                                  "next unit")
                return None, (f"this unit is full at {state['cap']} players - "
                              f"try the next unit")
            cid = self._seat_cohort(cohort)
            if cid is None and not bot:
                # Every cohort full of a mix of people and practice players:
                # take a seat back from the fullest one that has a bot in it.
                if self.retire_bot():
                    cid = self._seat_cohort(cohort)
            if cid is None:
                return None, "every cohort is full"
            player = Player(self._next_id, (name or "").strip()[:32]
                            or f"Player {self._next_id}", cid, bot=bot,
                            cert_name=cert_name)
            self.players[player.id] = player
            self._next_id += 1
            self._admit_late(player)
            if not bot:
                self.rebalance_bots()
            return player, None

    def _admit_late(self, player):
        """Somebody sat down during a shootout: they are in it."""
        s = self.shootout
        if s is None or s.over():
            return
        s.admit(player.id)
        if player.bot:
            s.passers.add(player.id)

    def leave(self, player_id):
        with self.lock:
            gone = self.players.pop(player_id, None)
            if gone is not None and self.shootout is not None:
                # Out is out. The order is not rewritten, so nobody else's
                # turn moves; the pick moves on if they were holding it.
                self.shootout.withdraw(player_id)
                if self.pick is not None and self.shootout.picker is None:
                    self.pick = None
            if gone is not None and not gone.bot:
                # Somebody left; top the table back up so the room does not
                # thin out under the people still playing.
                self.rebalance_bots()
            return gone is not None

    # ---------------------------------------------------------------- rounds

    def start_round(self, pool_id, question_id, answer_index,
                    seconds=DEFAULT_ROUND_SECONDS, payload=None, tag=None):
        """Put a question to the room."""
        with self.lock:
            self.round_number += 1
            self.round = Round(self.round_number, pool_id, question_id,
                               answer_index, seconds, payload, tag)
            self._plan_bots()
            return self.round

    # ------------------------------------------------------ practice players

    def _plan_bots(self):
        """Decide now what each practice opponent will do, and when.

        Deciding up front rather than at the moment of answering is what makes
        them arrive spread across the round instead of all at once, which is
        what a room of people actually looks like.
        """
        rnd = self.round
        if rnd is None:
            return
        for player in self.players.values():
            if not player.bot:
                continue
            accuracy, quick, slow = BOT_SKILLS[player.bot]
            right = random.random() < accuracy
            wrong = [i for i in range(4) if i != rnd.answer_index]
            rnd.bot_plan[player.id] = {
                "at": random.uniform(quick, min(slow, max(quick + 0.5,
                                                          rnd.seconds - 1.0))),
                "chosen": rnd.answer_index if right else random.choice(wrong),
            }

    def run_bots(self):
        """Submit any practice answers whose moment has come.

        Driven from outside on a tick, so nothing here needs a timer of its
        own. The reported time is the one that was planned, which is the same
        number a phone would have measured.
        """
        with self.lock:
            rnd = self.round
            if rnd is None or rnd.closed:
                return 0
            elapsed = _now() - rnd.opened_at
            sent = 0
            for player_id, plan in list(rnd.bot_plan.items()):
                if player_id in rnd.answers or plan["at"] > elapsed:
                    continue
                got, _ = self.submit(player_id, plan["chosen"],
                                     plan["at"] * 1000.0,
                                     plan["at"] * 1000.0)
                if got:
                    sent += 1
            return sent

    def _bot_target(self):
        """How full a cohort should be kept, counting practice opponents."""
        import math
        return max(2, math.ceil(COHORT_SIZE * BOT_FLOOR))

    def rebalance_bots(self, level=None):
        """Keep each cohort at the floor, with practice players making up only
        the difference.

        Bots fill the gap between the people present and the floor - they do
        not take seats beyond it. So a table of one person plays against four,
        a table of five people has none, and every person who arrives displaces
        exactly one machine.
        """
        with self.lock:
            if not self.bots_wanted:
                return []
            want = self._bot_target()
            changed = []
            used = {p.name for p in self.players.values()}
            for cid in self.cohorts:
                here = [p for p in self.players.values() if p.cohort_id == cid]
                humans = [p for p in here if not p.bot]
                bots = [p for p in here if p.bot]
                need = max(0, min(want, COHORT_SIZE) - len(humans))
                while len(bots) > need:
                    leaving = max(bots, key=lambda p: p.id)
                    bots.remove(leaving)
                    self.players.pop(leaving.id, None)
                    if self.round and not self.round.closed:
                        self.round.bot_plan.pop(leaving.id, None)
                    changed.append(("out", leaving))
                while len(bots) < need and len(self.players) < self.cap:
                    pool = [n for n in BOT_NAMES if n not in used]
                    if not pool:
                        break
                    name = random.choice(pool)
                    used.add(name)
                    player = Player(self._next_id, name, cid,
                                    bot=level or random.choice(list(BOT_SKILLS)))
                    self.players[player.id] = player
                    self._next_id += 1
                    bots.append(player)
                    changed.append(("in", player))
            if changed and self.round and not self.round.closed:
                self._plan_bots()
            return changed

    def fill_bots(self, level=None):
        """Switch practice opponents on and top the table up."""
        with self.lock:
            self.bots_wanted = True
            self.rebalance_bots(level)
            return [p for p in self.players.values() if p.bot]

    def retire_bot(self, cohort_id=None):
        """Give a seat back. The machine yields to the person."""
        with self.lock:
            bots = [p for p in self.players.values() if p.bot
                    and (cohort_id is None or p.cohort_id == cohort_id)]
            if not bots:
                return None
            # The newest first, so a bot that has been playing a while and is
            # on the board does not vanish out from under the scoreboard.
            leaving = max(bots, key=lambda p: p.id)
            self.players.pop(leaving.id, None)
            if self.round and not self.round.closed:
                self.round.bot_plan.pop(leaving.id, None)
            return leaving

    def clear_bots(self):
        with self.lock:
            self.bots_wanted = False
            gone = [p.id for p in self.players.values() if p.bot]
            for pid in gone:
                self.players.pop(pid, None)
                if self.round:
                    self.round.bot_plan.pop(pid, None)
            return len(gone)

    def cert_name_of(self, player_id):
        player = self.players.get(player_id)
        return (player.cert_name if player else None) or None

    def submit(self, player_id, chosen_index, client_ms, server_ms=None):
        """Take one answer, timed by the player's own clock.

        `client_ms` is what the browser measured between painting the question
        and the button going down. `server_ms` is how long the same interval
        looked from here; it is used only as a ceiling, because a client that
        reports two milliseconds is not fast, it is lying.
        """
        with self.lock:
            rnd = self.round
            if rnd is None or rnd.closed:
                return None, "no round is open"
            if rnd.expired():
                return None, "time is up on this round"
            player = self.players.get(player_id)
            if player is None:
                return None, "you are not in this room"
            if player_id in rnd.answers:
                return None, "you have already answered"

            elapsed = (_now() - rnd.opened_at) * 1000.0
            ceiling = server_ms if server_ms is not None else elapsed
            try:
                ms = float(client_ms)
            except (TypeError, ValueError):
                ms = ceiling
            # Bounded at both ends, because only the upper bound is obvious.
            #
            # Above: a stopwatch left running cannot report longer than the
            # round has been open.
            #
            # Below: the round has been open for `ceiling` ms, and the player
            # cannot have seen the question much later than it opened - at
            # worst a poll interval plus the network. So a claim far under
            # that is not a fast finger, it is a made-up number. Flooring it
            # does not make the race unspoofable, which nothing server-side
            # can; it caps what the lie is worth at the slack window, instead
            # of letting "1 ms" win every round for ever.
            floor = max(1.0, ceiling - DELIVERY_SLACK_MS)
            ms = min(max(ms, floor), max(1.0, ceiling))

            correct = (chosen_index == rnd.answer_index)
            player.last_seen = _now()
            player.answered += 1
            if correct:
                player.correct += 1
            rnd.answers[player_id] = {
                "player_id": player_id, "name": player.name,
                "cohort": player.cohort_id, "correct": correct,
                "ms": round(ms, 1), "order": len(rnd.answers) + 1}
            return rnd.answers[player_id], None

    def everyone_answered(self):
        """Whether the round may close early. Only people count.

        Practice opponents do not get a vote. They answer in two to eighteen
        seconds and they are only scenery, so letting them end a round would
        mean a table of one person racing software that always finishes first
        - and this is a game for amateur radio operators, plenty of whom read
        at their own pace, or whose eyes or recall are not what they were.
        Nobody should be hurried off a question by a machine. The clock is what
        ends a round somebody has not answered, and the clock is generous.

        Membership is tested rather than counted, because a bot that answered
        and then retired to make room for an arriving person left its answer on
        file: the count reached the number of players while the person who had
        just sat down had not answered at all, and the round closed without
        them. That is the fault this docstring is longer than the code for.
        """
        with self.lock:
            if not self.round:
                return False
            people = [p for p in self.players.values() if not p.bot]
            # With nobody real at the table - a demonstration, or a screen left
            # running - the practice players are all there is to wait for.
            who = people or list(self.players.values())
            return all(p.id in self.round.answers for p in who)

    def close_round(self):
        """Score the round: correct answers only, fastest first.

        A cohort's round score is its members' points added up, so eight
        people each answering steadily beats one person answering brilliantly
        while seven guess - which is the behaviour a study party wants.
        """
        with self.lock:
            rnd = self.round
            if rnd is None or rnd.closed:
                return None
            rnd.closed = True

            right = sorted([a for a in rnd.answers.values() if a["correct"]],
                           key=lambda a: a["ms"])
            per_cohort = {cid: 0 for cid in self.cohorts}
            for place, entry in enumerate(right, start=1):
                # Everyone correct scores; being first is worth more, but a
                # correct answer is never worth nothing.
                points = max(1, 10 - (place - 1))
                entry["place"] = place
                entry["points"] = points
                player = self.players.get(entry["player_id"])
                if player:
                    player.score += points
                per_cohort[entry["cohort"]] = per_cohort.get(entry["cohort"], 0) + points
            for a in rnd.answers.values():
                a.setdefault("place", None)
                a.setdefault("points", 0)

            for cid, points in per_cohort.items():
                self.cohorts[cid].score += points
            best = max(per_cohort.items(), key=lambda kv: kv[1]) if per_cohort else None
            if best and best[1] > 0:
                # A tie leaves the pick with the cohort that is behind overall,
                # which keeps a runaway leader from also owning the questions.
                tied = [cid for cid, pts in per_cohort.items() if pts == best[1]]
                rnd.winner_cohort = min(
                    tied, key=lambda cid: (self.cohorts[cid].score, cid))
                self.cohorts[rnd.winner_cohort].rounds_won += 1

            summary = {
                "number": rnd.number, "pool": rnd.pool_id,
                "question_id": rnd.question_id,
                "winner_cohort": rnd.winner_cohort,
                "answers": sorted(rnd.answers.values(),
                                  key=lambda a: (not a["correct"], a["ms"])),
                "cohort_points": per_cohort,
            }
            # In a shootout the round is also a shot. The rules get every
            # answer, keyed by player, and somebody who never pressed anything
            # is simply not in it - which the rules read as a miss, because
            # that is what not answering is.
            if self.shootout is not None:
                section = (rnd.payload or {}).get("section")
                if section:
                    summary["shootout"] = self.shootout.play(section, {
                        a["player_id"]: {"correct": a["correct"], "ms": a["ms"]}
                        for a in rnd.answers.values()})
            self.history.append(summary)
            return summary

    # -------------------------------------------------------------- shootout

    def begin_shootout(self, sections, titles=None, groups=None,
                       pick_seconds=None):
        """Start a shootout over everybody at the table, in seating order.

        `sections` are the subjects that can be picked - the pool's section
        codes - and `titles` what to call them on a phone, because "T5C" is a
        filing reference and "Electrical principles: capacitance" is a subject
        somebody can decide they are good at.
        """
        with self.lock:
            # People first, in the order they sat down, then the practice
            # players - so the first pick is always a person's. Seated by id
            # alone, a table that had filled with bots earlier in the evening
            # handed the opening pick to one of them.
            order = (sorted(p for p, pl in self.players.items() if not pl.bot)
                     + sorted(p for p, pl in self.players.items() if pl.bot))
            if len(order) < 2:
                return None, "a shootout needs two players"
            self.shootout = Shootout(
                order, sections,
                passers=[p for p, pl in self.players.items() if pl.bot])
            self.titles = dict(titles or {})
            self.groups = dict(groups or {})      # code -> (sub, sub title)
            self.mode = SHOOTOUT
            self.pick = None
            self.pick_seconds = float(pick_seconds or PICK_SECONDS)
            self._pick_since = None
            return self.shootout, None

    def end_shootout(self):
        with self.lock:
            self.shootout = None
            self.mode = TOURNAMENT
            self.pick = None

    def choose(self, player_id, section):
        """The picker names the subject for the next question.

        Refused in words rather than silently, because "it is not your pick"
        is the thing a player who pressed the button needs to be told.
        """
        with self.lock:
            s = self.shootout
            if s is None:
                return None, "this table is not playing a shootout"
            if s.over():
                return None, "the shootout is over"
            if self.round is not None and not self.round.closed:
                return None, "a question is still open"
            if s.picker != player_id:
                return None, "it is not your pick"
            ok, why = s.may_pick(section)
            if not ok:
                return None, why
            self.pick = section
            return section, None

    def choose_for_bot(self):
        """A practice player holding the pick chooses for itself.

        At random among what is left: a bot with a strategy would be a bot
        with an opinion about what the people at the table are bad at, and
        it has no basis for one.
        """
        with self.lock:
            s = self.shootout
            if s is None or s.over() or self.pick is not None:
                return None
            if self.round is not None and not self.round.closed:
                return None
            holder = self.players.get(s.picker)
            if holder is None or not holder.bot:
                return None
            left = s.available()
            if not left:
                return None
            self.pick = random.choice(left)
            return self.pick

    def waiting_for_pick(self):
        """True while the next question is a person's to choose.

        The director asks this rather than reading what the draw returned,
        for the reason the hall's conductor learned the hard way: a function
        that returns nothing is not a signal, it is a function that returned
        nothing.
        """
        with self.lock:
            s = self.shootout
            waiting = False
            if s is not None and not s.over() and self.pick is None:
                if self.round is None or self.round.closed:
                    holder = self.players.get(s.picker)
                    waiting = holder is not None and not holder.bot
            # The clock on the pick starts the first time the wait is seen
            # and belongs to whoever is being waited on: a new picker gets a
            # fresh one, and a pick made or a question opened stops it.
            if not waiting:
                self._pick_since = None
            elif self._pick_since is None or self._pick_since[1] != s.picker:
                self._pick_since = (_now(), s.picker)
            return waiting

    def pick_remaining(self):
        """Seconds the picker has left, or None when nobody is being waited on."""
        with self.lock:
            if not self.waiting_for_pick():
                return None
            return max(0.0, self.pick_seconds - (_now() - self._pick_since[0]))

    def pick_overdue(self):
        with self.lock:
            left = self.pick_remaining()
            return left is not None and left <= 0.0

    def pass_pick(self):
        """The picker did not choose in time: it goes round the table.

        No letter for anybody. A letter is for missing a shot the picker
        made, and nobody shot.
        """
        with self.lock:
            s = self.shootout
            if s is None or s.over():
                return None
            was = s.picker
            s.picker = s.next_picker(was)
            s.pick_reason = "timeout"
            self._pick_since = None
            s.history.append({"section": None, "picker": was, "made": False,
                              "took": [], "next_picker": s.picker,
                              "passed": True, "out": [], "winner": None,
                              "over": False})
            return s.picker

    def shootout_over(self):
        with self.lock:
            return self.shootout is not None and self.shootout.over()

    def take_pick(self):
        """The subject waiting to be asked, cleared as it is taken."""
        with self.lock:
            section, self.pick = self.pick, None
            return section

    def shootout_view(self, player_id=None):
        """What the screens need, with names on it rather than ids."""
        with self.lock:
            s = self.shootout
            if s is None:
                return None
            standing = []
            for row in s.standing():
                player = self.players.get(row["player"])
                standing.append({
                    **row,
                    "name": player.name if player else "(left)",
                    "bot": bool(player.bot) if player else False,
                    "gone": player is None,
                })
            holder = self.players.get(s.picker) if s.picker else None
            winner = self.players.get(s.winner()) if s.winner() else None
            titles = getattr(self, "titles", {}) or {}
            groups = getattr(self, "groups", {}) or {}
            return {
                "word": s.as_dict()["word"],
                "standing": standing,
                "picker": s.picker,
                "pick_reason": s.pick_reason,
                "picker_name": holder.name if holder else None,
                "picker_is_bot": bool(holder.bot) if holder else False,
                "your_pick": bool(player_id is not None
                                  and s.picker == player_id
                                  and self.pick is None
                                  and not s.over()),
                "pick": self.pick,
                "pick_title": titles.get(self.pick, self.pick),
                "pick_remaining": (None if self.pick_remaining() is None
                                   else round(self.pick_remaining(), 1)),
                "available": [{"section": code,
                               "title": titles.get(code, code),
                               "group": groups.get(code, ("", ""))[0],
                               "group_title": groups.get(code, ("", ""))[1]}
                              for code in s.available()],
                "spent": list(s.spent),
                "over": s.over(),
                "winner": s.winner(),
                "winner_name": winner.name if winner else None,
                "drawn": s.drawn(),
                "played": len(s.history),
                "last": s.history[-1] if s.history else None,
                # The last *shot*, as distinct from the last thing that
                # happened: a pick timing out is in the history too, and a
                # screen reading that as "the picker missed" beside the
                # results of a shot the picker made was telling two stories.
                "last_shot": next((h for h in reversed(s.history)
                                   if h.get("section")), None),
            }

    def picker(self):
        """Which cohort chooses the next question, and what it may choose."""
        with self.lock:
            last = self.history[-1] if self.history else None
            return {"cohort": last["winner_cohort"] if last else None,
                    "difficulties": sorted(DIFFICULTIES)}

    def standings(self, limit=8):
        """Who is ahead at this table, and who just gained.

        For the strip along the foot of the big board, where somebody standing
        at the back is following the room rather than the question. The score
        is the evening; the gain is the round that just went - which is the
        part that makes a spectator look up.
        """
        with self.lock:
            gained = {}
            if self.history:
                gained = {a["player_id"]: a.get("points") or 0
                          for a in self.history[-1].get("answers", [])}
            rows = sorted(self.players.values(),
                          key=lambda p: (-p.score, p.name.lower()))
            return [{"name": p.name, "score": p.score, "bot": p.bot,
                     "gained": gained.get(p.id, 0),
                     "correct": p.correct, "answered": p.answered}
                    for p in rows[:limit]]

    def arm_start(self, seconds):
        """Put the first question on a countdown. Returns when it will fire."""
        with self.lock:
            self.start_at = _now() + max(0.0, float(seconds))
            return self.start_at

    def disarm_start(self):
        """Take the countdown off - somebody started it, or everyone left."""
        with self.lock:
            self.start_at = None

    def waiting_to_start(self):
        """Whether a countdown is armed and has not fired yet."""
        with self.lock:
            return self.start_at is not None

    def people_here(self):
        """How many of the players are people rather than practice ones."""
        with self.lock:
            return sum(1 for p in self.players.values() if not p.bot)

    def state(self, player_id=None):
        """Everything a connected device needs to draw the screen."""
        with self.lock:
            rnd = self.round
            board = sorted((c.as_dict(list(self.players.values()))
                            for c in self.cohorts.values()),
                           key=lambda c: -c["score"])
            out = {
                "open": self.open,
                # Seconds until the first question, for both screens to count
                # down. Negative would mean it is overdue rather than close,
                # so it floors at zero.
                "starts_in": (None if self.start_at is None
                              else max(0.0, round(self.start_at - _now(), 1))),
                "bots": sum(1 for p in self.players.values() if p.bot),
                "people": sum(1 for p in self.players.values() if not p.bot),
                "bots_on": self.bots_wanted,
                "health": self.health(),
                "cohorts": board,
                "round": None,
                "picker": self.picker(),
                "mode": self.mode,
                "shootout": self.shootout_view(player_id),
            }
            if rnd:
                out["round"] = {
                    "number": rnd.number, "pool": rnd.pool_id,
                    "question_id": rnd.question_id,
                    # payload carries text, choices and figure - never the
                    # answer index, which stays on the server until the round
                    # closes. A poll response is readable in any dev console.
                    "question": rnd.payload,
                    "remaining": round(rnd.remaining, 1),
                    "closed": rnd.closed,
                    "answered": len(rnd.answers),
                    "waiting_on": sum(1 for p in self.players.values()
                                      if not p.bot and p.id not in rnd.answers),
                    "waiting_on_all": sum(1 for p in self.players.values()
                                          if p.id not in rnd.answers),
                    "winner_cohort": rnd.winner_cohort,
                    "card": rnd.card,
                }
                if rnd.closed:
                    out["round"]["results"] = sorted(
                        rnd.answers.values(),
                        key=lambda a: (not a["correct"], a["ms"]))
                    # And now the answer itself. It is held back while the
                    # round is open because a poll response is readable in any
                    # dev console; once the round is scored there is nothing
                    # left to protect, and a room full of people who have just
                    # watched a question go by should be told what the answer
                    # was. That is most of what a spectator takes home.
                    out["round"]["answer"] = _answer_text(rnd)
                if player_id is not None:
                    out["you"] = rnd.answers.get(player_id)
            return out


_room = None
_room_lock = threading.Lock()


def room(create=False, cohorts=2):
    """The party on this unit, if one is running."""
    global _room
    with _room_lock:
        if _room is None and create:
            _room = Room(cohorts=cohorts)
        return _room


def close_room():
    global _room
    with _room_lock:
        _room = None
