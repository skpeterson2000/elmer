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

# Measured on a Raspberry Pi 5: 30 players answering simultaneously were all
# served in 642 ms, 60 took 5068 ms. The knee is between the two, and 24 keeps
# a margin under it rather than sitting on it.
CAP_PER_UNIT = 24
COHORT_SIZE = 8
MAX_COHORTS = 4

# A round is scored on the players who answered. Somebody who wandered off to
# the coffee urn should not hold the room up for ever - but the clock is the
# only thing that ends a round early, so it has to be long enough to read a
# question and four choices without hurrying. A minute, and adjustable up to
# three, because the people this is for are not all in a hurry.
DEFAULT_ROUND_SECONDS = 60.0
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
# each other: a marine permit, a radiotelephone licence and a radar
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
# They are never disguised. Every one is flagged as a bot the whole way out to
# the screen, because a leaderboard that quietly counts software among the
# operators is a leaderboard that cannot be trusted at a club night.
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

    def __init__(self, player_id, name, cohort_id, bot=None):
        self.id = player_id
        self.name = name
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

    @property
    def remaining(self):
        return max(0.0, self.seconds - (_now() - self.opened_at))

    def expired(self):
        return self.remaining <= 0.0


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

    def join(self, name, cohort=None, bot=None):
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
                            or f"Player {self._next_id}", cid, bot=bot)
            self.players[player.id] = player
            self._next_id += 1
            if not bot:
                self.rebalance_bots()
            return player, None

    def leave(self, player_id):
        with self.lock:
            gone = self.players.pop(player_id, None)
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
            self.history.append(summary)
            return summary

    def picker(self):
        """Which cohort chooses the next question, and what it may choose."""
        with self.lock:
            last = self.history[-1] if self.history else None
            return {"cohort": last["winner_cohort"] if last else None,
                    "difficulties": sorted(DIFFICULTIES)}

    def state(self, player_id=None):
        """Everything a connected device needs to draw the screen."""
        with self.lock:
            rnd = self.round
            board = sorted((c.as_dict(list(self.players.values()))
                            for c in self.cohorts.values()),
                           key=lambda c: -c["score"])
            out = {
                "open": self.open,
                "bots": sum(1 for p in self.players.values() if p.bot),
                "people": sum(1 for p in self.players.values() if not p.bot),
                "bots_on": self.bots_wanted,
                "health": self.health(),
                "cohorts": board,
                "round": None,
                "picker": self.picker(),
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
                }
                if rnd.closed:
                    out["round"]["results"] = sorted(
                        rnd.answers.values(),
                        key=lambda a: (not a["correct"], a["ms"]))
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
