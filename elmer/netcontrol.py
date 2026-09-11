"""Net control: one master unit running a competition across many cohort units.

A club evening fits on one Pi. A hamfest does not, and the reason is not
processing power - it is that twenty-four people answering at once is the point
where a single unit stops feeling instant. The answer is not a bigger machine.
It is more machines, each with a cohort of eight on it, and one unit running
the net.

The load on net control scales with the number of *units*, not the number of
players, and that is the whole trick. Eight players poll the Pi in front of
them several times a second between them; net control never sees any of it. It
sees one check-in per unit per poll, and one report per unit per round. Two
hundred players on twenty-five units is twenty-five conversations, not two
hundred - which is why a hall full of people is a smaller problem for the
master than a single crowded room is for one Pi.

Net control is authoritative for two things only: which question the room is
on, and what the standings are. Everything about actually running a round -
showing the question, taking the answers, timing them on the player's own
clock - stays on the cohort unit, close to the people it serves. A unit that
loses the network mid-round finishes its round locally and reports late; the
net notices it is quiet and carries on without it, rather than stopping the
hall because one Pi in the corner went off the air.
"""
import logging
import random
import threading
import time
from collections import deque

from . import tournament

log = logging.getLogger("elmer")

# Measured on a Raspberry Pi 5 acting as net control: 100 units checked in at
# 1 Hz with a p95 of 46 ms, 200 at 100 ms, and 400 was the knee at 1067 ms.
# One hundred units - eight hundred seats - keeps roughly a four-fold margin
# under the knee, which is the right side of a benchmark to stand on: the
# figures above were taken on a quiet bench, and a hall is not a quiet bench.
#
# It is also well under the limit that actually binds at a public event, which
# is not this machine but the wireless. Eight hundred phones is a serious
# access-point deployment; the master is the one part of the evening that will
# not be what breaks.
MAX_UNITS = 100

# A unit that has not been heard from in this long is assumed to have gone off
# the air. It is not removed - it may come back - but it stops holding up a
# round and stops being counted as present.
QUIET_AFTER = 25.0
DROP_AFTER = 300.0

# Net control degrades the same way a cohort unit does: it stops taking units
# before the hall is unpleasant, rather than after.
SLOW_MS = 400.0
HEALTH_WINDOW = 60

# A round closes when every present unit has reported, or this long after the
# clock the tables are showing has run out. A hall does not wait indefinitely
# for one table.
#
# Measured from the round's own length rather than fixed, because the two have
# to stay in step in both directions: a fixed grace shorter than the round
# would close it under the people still answering, and one much longer leaves
# a hall of thirty-second rounds stalled for three of them because one table
# went off the air.
GRACE_AFTER_TIME = 20.0


# Tables that are not there.  A net with nothing checked in shows an empty
# board, which is the least useful thing a screen at the front of a room can
# do, and an instructor setting an evening up cannot tell whether any of it
# works until eight people have arrived and sat down.  So a hall can be filled
# with tables that play, and a real unit arriving takes one of their places.
#
# Named for wireless stations rather than for people, because a table on a
# board is a place with an operator at it - and because nobody reading Poldhu
# off a screen will take it for the Pi in front of them.
SIMULATED_NAMES = ["Poldhu", "Clifden", "Glace Bay", "Signal Hill", "Nauen",
                   "Arlington", "Sayville", "Tuckerton", "Rugby", "Malabar",
                   "Bolinas", "Kahuku", "Marion", "Cape Cod"]

# A simulated table is consistently as good as it is, rather than rolling
# fresh every round: a board is worth watching because one table is having a
# good evening and another is not, and randomness with no memory gives neither.
SIM_SKILL = (0.45, 0.9)

# Where a simulated table's answers land inside the round.  Never at the
# instant it opens - a hall where the machines all answer in the first second
# looks like a fault, not a game.
SIM_EARLIEST = 2.5
SIM_LATEST_SHARE = 0.85


def _now():
    return time.monotonic()


class Unit:
    """One cohort Pi, checked in to the net."""

    def __init__(self, unit_id, name, players=0, simulated=False):
        self.id = unit_id
        self.name = name
        self.players = players
        # Carried the whole way out, because everything downstream needs it:
        # a real unit checking in displaces one of these, the host's panel
        # shows which places are held, and the board chooses not to mark them
        # - see the practice opponents in party.py for why.
        self.simulated = bool(simulated)
        self.skill = random.uniform(*SIM_SKILL) if simulated else None
        self.first_seen = _now()
        self.last_seen = self.first_seen
        self.score = 0
        self.rounds_won = 0
        self.reported_round = 0

    @property
    def quiet_for(self):
        return _now() - self.last_seen

    @property
    def present(self):
        return self.quiet_for <= QUIET_AFTER

    def as_dict(self):
        return {"id": self.id, "name": self.name, "players": self.players,
                "score": self.score, "rounds_won": self.rounds_won,
                "present": self.present, "quiet_for": round(self.quiet_for, 1),
                "reported_round": self.reported_round,
                "simulated": self.simulated}


class Net:
    """The competition: many units, one question at a time, one leaderboard."""

    def __init__(self, name="ELMER Net", cap=MAX_UNITS,
                 difficulty="technician"):
        self.lock = threading.RLock()
        self.name = name
        self.cap = cap
        # What this net is studying. One network can hold several at once -
        # Technician in one corner, General in another, Extra in the next room
        # - and a unit deciding which to report to picks by the material, not
        # by which Pi it happens to be running on. The name follows it.
        self.difficulty = difficulty
        self._service = deque(maxlen=HEALTH_WINDOW)
        self.units = {}
        self.round_number = 0
        self.round = None          # dict: the question every unit is showing
        self.opened_at = 0.0
        self.results = {}          # unit_id -> list of player results
        self.history = []
        self.picker_unit = None
        self._sim_plan = {}        # unit_id -> (when it answers, what it says)
        # Everyone who has answered anything, by (table, name), kept across
        # rounds. The tables' own totals are not the whole story: a hall
        # scores by table so that a big table cannot be beaten by arithmetic,
        # but the person sitting at one wants to find their own name, and a
        # round board only ever showed the last question. Practice players are
        # kept in with a flag rather than dropped, because a board with the
        # practice tables edited out of it is not the game that was played.
        self.people = {}           # (unit_id, name) -> running total
        # The tournament itself: its questions drawn up front in the shape of
        # the examination, and how far through them the hall has got. Drawing
        # the whole thing at the start rather than a question at a time is
        # what lets it be twelve, thirty-six or forty-eight questions of known
        # proportions instead of an unbounded string of random ones.
        self.plan = None
        self.plan_at = 0
        # A winner is declared every twelve questions rather than once at the
        # end. A table that started badly gets another chance to be the table
        # that won something, and a room gets a result while it is still
        # watching. These are the ones declared so far.
        self.blocks = []
        self._block_units = {}     # points this block, by table
        self._block_people = {}    # points this block, by (table, name)

    # ------------------------------------------------------------- check-in

    def note_service(self, ms):
        """How long a check-in actually took, for the moving cap."""
        with self.lock:
            self._service.append(float(ms))

    def health(self):
        """What the hall is costing this machine, and how many units may join.

        The cap comes down when net control is visibly slow, for the same
        reason a cohort unit's does: a hall that quietly degrades is worse
        than one that says "this net is full, start another".
        """
        with self.lock:
            recent = sorted(self._service)
            p95 = (recent[min(len(recent) - 1, int(len(recent) * 0.95))]
                   if len(recent) >= 8 else 0.0)
            cap = self.cap
            if p95 > SLOW_MS * 2:
                cap = max(1, int(self.cap * 0.5))
            elif p95 > SLOW_MS:
                cap = max(1, int(self.cap * 0.75))
            known = len(self.units)
            ready = [u for u in self.units.values() if u.present and u.players]
            return {"units": known, "cap": cap, "hard_cap": self.cap,
                    "p95_ms": round(p95, 1), "seats": max(0, cap - known),
                    "players": known * 8, "healthy": p95 <= SLOW_MS,
                    "ready": len(ready),
                    "seated": sum(u.players for u in ready),
                    "simulated": sum(1 for u in self.units.values()
                                     if u.simulated)}

    def check_in(self, unit_id, name=None, players=0):
        """A unit says it is here, and how many people are sitting at it.

        Returns (unit, None) or (None, reason). A unit already known is always
        readmitted - the cap is about how large the hall grows, not about
        throwing out a table that briefly lost the network.
        """
        with self.lock:
            unit = self.units.get(unit_id)
            if unit is None:
                # A person arriving takes a machine's place rather than being
                # turned away by one, and rather than making the hall bigger
                # than the room it is in.
                self.retire_simulated()
                state = self.health()
                if state["seats"] <= 0:
                    if state["cap"] < state["hard_cap"]:
                        return None, ("net control is busy and has stopped "
                                      "taking units - start a second net")
                    return None, (f"this net is full at {state['cap']} units "
                                  f"({state['cap'] * 8} seats) - start a "
                                  f"second net")
                unit = Unit(unit_id, name or unit_id, players)
                self.units[unit_id] = unit
            unit.last_seen = _now()
            if name:
                unit.name = name
            unit.players = int(players or 0)
            return unit, None

    def ready_units(self):
        """Tables with somebody actually sitting at them.

        A table checks in the moment it is switched on, which is not the same
        as being ready to play - an empty table in the corner should not start
        the hall, and should not hold it up either.  Check-in already carries
        the count, so readiness is a report rather than a guess: the table
        knows who is at it and says so, and the host starts when the hall has
        somebody in it.
        """
        with self.lock:
            return [u for u in self.units.values() if u.present and u.players]

    def simulated_units(self):
        with self.lock:
            return [u for u in self.units.values() if u.simulated]

    def add_simulated(self, count=1, players=None):
        """Put tables in the hall that are not there.  Returns what was added."""
        with self.lock:
            taken = {u.name for u in self.units.values()}
            free = [n for n in SIMULATED_NAMES if n not in taken]
            random.shuffle(free)
            made = []
            for name in free[:max(0, int(count))]:
                unit_id = "sim-" + name.lower().replace(" ", "-")
                seats = players if players else random.randint(3, 8)
                unit = Unit(unit_id, name, seats, simulated=True)
                self.units[unit_id] = unit
                made.append(unit)
            if made:
                log.info("net: %d simulated table(s) joined - %s",
                         len(made), ", ".join(u.name for u in made))
            return made

    def retire_simulated(self):
        """Give a simulated table's place up, weakest first.

        Weakest rather than newest, so what a real unit displaces is the
        table nobody was watching - the evening's story survives somebody
        walking in halfway through it.
        """
        with self.lock:
            sims = self.simulated_units()
            if not sims:
                return None
            going = min(sims, key=lambda u: (u.score, u.rounds_won))
            self.units.pop(going.id, None)
            self._sim_plan.pop(going.id, None)
            self.results.pop(going.id, None)
            log.info("net: simulated table %s stood down", going.name)
            return going

    def present_units(self):
        with self.lock:
            return [u for u in self.units.values() if u.present]

    def prune(self):
        """Forget units that have been gone long enough to be gone."""
        with self.lock:
            dead = [uid for uid, u in self.units.items()
                    if u.quiet_for > DROP_AFTER]
            for uid in dead:
                self.units.pop(uid, None)
            return len(dead)

    # --------------------------------------------------------------- rounds

    def start_round(self, pool_id, question_id, answer_index, payload,
                    seconds=45.0):
        """Put one question to every unit in the hall."""
        with self.lock:
            self.round_number += 1
            self.opened_at = _now()
            self.results = {}
            if payload.get("difficulty"):
                # A net that spent the evening drifting from Technician to
                # General should say so on the network; the label is what the
                # hall is doing, not what somebody typed when they opened it.
                self.difficulty = payload["difficulty"]
            self.round = {
                "number": self.round_number, "pool": pool_id,
                "question_id": question_id, "answer_index": answer_index,
                "question": payload, "seconds": seconds,
            }
            self._plan_simulated(seconds)
            return self.round

    # ------------------------------------------------------- tables that
    # ------------------------------------------------------- are not there

    def _plan_simulated(self, seconds):
        """Decide now what the simulated tables will do, and when.

        Decided at the top of the round and handed in as the moments arrive,
        the way the practice players are: a hall where every machine answers
        in the same instant reads as a fault rather than a game, and a board
        that fills gradually is the one somebody will watch.
        """
        from .party import BOT_NAMES

        self._sim_plan = {}
        latest = max(SIM_EARLIEST + 1.0, seconds * SIM_LATEST_SHARE)
        for unit in self.units.values():
            if not unit.simulated:
                continue
            names = random.sample(BOT_NAMES, min(unit.players, len(BOT_NAMES)))
            rows, slowest = [], 0.0
            for name in names:
                took = random.uniform(SIM_EARLIEST, latest)
                slowest = max(slowest, took)
                rows.append({"name": name, "bot": "practice",
                             "correct": random.random() < unit.skill,
                             "ms": round(took * 1000.0, 1)})
            # A table reports when its cohort is done, not when its first
            # player is - which is what puts the fast tables up the board
            # first and gives the thing its shape.
            self._sim_plan[unit.id] = (_now() + slowest + 0.4, rows)

    def tick_simulated(self):
        """Hand in the simulated tables' answers as their moments arrive.

        Also keeps them present.  A table that is there says so every few
        seconds; one that never spoke would go quiet after
        `QUIET_AFTER` and drop off the board it is meant to be filling.
        """
        with self.lock:
            now = _now()
            handed = 0
            for unit in self.units.values():
                if unit.simulated:
                    unit.last_seen = now
            if not self.round:
                return 0
            for unit_id, (at, rows) in list(self._sim_plan.items()):
                if unit_id not in self.units:
                    self._sim_plan.pop(unit_id, None)
                    continue
                if now < at or unit_id in self.results:
                    continue
                self._sim_plan.pop(unit_id, None)
                self.report(unit_id, self.round_number, rows)
                handed += 1
            return handed

    def current(self, include_key=False):
        """What a unit needs to run the round in front of it.

        The answer key travels to the units, because they score their own
        players locally - that is what keeps the players' traffic off the
        master. It is never served to a player device.
        """
        with self.lock:
            if not self.round:
                return None
            out = dict(self.round)
            if not include_key:
                out.pop("answer_index", None)
            out["elapsed"] = round(_now() - self.opened_at, 1)
            out["reported"] = len(self.results)
            out["awaiting"] = max(0, len(self.present_units()) - len(self.results))
            return out

    def report(self, unit_id, round_number, players):
        """A unit hands in its cohort's answers for the round.

        `players` is a list of {name, correct, ms}. Scoring happened on the
        unit; the net ranks the hall.
        """
        with self.lock:
            if not self.round or round_number != self.round_number:
                return None, "that round is not the one in progress"
            unit = self.units.get(unit_id)
            if unit is None:
                return None, "check in first"
            if unit_id in self.results:
                return None, "already reported this round"
            rows = []
            for p in players or []:
                try:
                    rows.append({
                        "unit": unit_id, "unit_name": unit.name,
                        "name": str(p.get("name", ""))[:32],
                        "correct": bool(p.get("correct")),
                        "ms": float(p.get("ms", 0)) or 0.0,
                        # Carried, not inferred: a table knows which of its
                        # players were practice and the hall does not.
                        "bot": p.get("bot") or None,
                        # What they want on a certificate; never on a board.
                        "cert_name": (str(p.get("cert_name") or "")[:48]
                                      or None)})
                except (TypeError, ValueError):
                    continue
            self.results[unit_id] = rows
            unit.last_seen = _now()
            unit.reported_round = round_number
            return {"accepted": len(rows)}, None

    def everyone_reported(self):
        with self.lock:
            return bool(self.round) and len(self.results) >= len(self.present_units())

    def overdue(self):
        with self.lock:
            if not self.round:
                return False
            showing = float(self.round.get("seconds") or 0.0)
            return (_now() - self.opened_at) > showing + GRACE_AFTER_TIME

    def close_round(self):
        """Rank the hall, award the unit score, and hand over the pick."""
        with self.lock:
            if not self.round:
                return None
            everyone = [row for rows in self.results.values() for row in rows]
            right = sorted([r for r in everyone if r["correct"]],
                           key=lambda r: r["ms"])
            per_unit = {}
            for place, row in enumerate(right, start=1):
                # The podium is separated, the tail is flattened. Flattening
                # the whole curve stops one fast table taking everything, but
                # flattening the podium too meant that a hall with three or
                # fewer correct answers - which is most club evenings - tied
                # every round and decided it on a coin toss. Being correct is
                # still most of the value: last place scores a fifth of first,
                # not a hundredth.
                row["place"] = place
                row["points"] = (7 - place if place <= 3
                                 else 3 if place <= 10 else 1)
                per_unit[row["unit"]] = per_unit.get(row["unit"], 0) + row["points"]

            for uid, points in per_unit.items():
                if uid in self.units:
                    self.units[uid].score += points
                # The block runs alongside the tournament total rather than
                # replacing it: the hall keeps a whole-evening score and also
                # declares somebody every twelve questions.
                self._block_units[uid] = self._block_units.get(uid, 0) + points

            # Every answer counts towards a person's total, not just the ones
            # that scored: "3 of 7" is the number somebody is actually playing
            # against, and a leaderboard of points alone cannot tell a player
            # who got two right from one who got two right out of twenty.
            for row in everyone:
                who = self.people.setdefault(
                    (row["unit"], row["name"]),
                    {"name": row["name"], "unit": row["unit"],
                     "unit_name": row["unit_name"], "score": 0,
                     "correct": 0, "answered": 0, "bot": bool(row.get("bot")),
                     "cert_name": row.get("cert_name")})
                who["answered"] += 1
                who["correct"] += 1 if row["correct"] else 0
                who["score"] += row.get("points", 0)
                # A table can be renamed mid-hall; the person is the same one.
                who["unit_name"] = row["unit_name"]
                if row.get("cert_name"):
                    who["cert_name"] = row["cert_name"]

                block = self._block_people.setdefault(
                    (row["unit"], row["name"]),
                    {"name": row["name"], "unit_name": row["unit_name"],
                     "points": 0, "correct": 0, "bot": bool(row.get("bot"))})
                block["points"] += row.get("points", 0)
                block["correct"] += 1 if row["correct"] else 0

            winner = None
            if per_unit:
                best = max(per_unit.values())
                tied = [u for u, p in per_unit.items() if p == best]
                # A tie hands the pick to whoever is behind overall, so a
                # runaway table does not also own the question list. Where they
                # are level on that too, it is drawn - sorting by unit id gave
                # the same table every tie all evening, which over a long hall
                # is a real advantage handed out alphabetically.
                floor = min(self.units[u].score for u in tied)
                level = [u for u in tied if self.units[u].score == floor]
                winner = random.choice(level)
                self.units[winner].rounds_won += 1
            self.picker_unit = winner

            # The question and its answer travel with the summary. A hall
            # watching a round close is a room full of people who have just
            # read a question, and telling them the answer at the moment the
            # winner goes up is the only teaching a spectator gets - the
            # explanation stays where it belongs, in the pool browser
            # afterwards, but the answer itself costs nothing and sticks.
            payload = self.round.get("question") or {}
            choices = payload.get("choices") or []
            index = self.round.get("answer_index")
            summary = {
                "number": self.round_number,
                "question_id": self.round["question_id"],
                "pool": self.round["pool"],
                "question": payload.get("text", ""),
                "answer": (choices[index] if isinstance(index, int)
                           and 0 <= index < len(choices) else None),
                "units_reported": len(self.results),
                "answers": len(everyone),
                "correct": len(right),
                "winner_unit": winner,
                # And what that unit is called. The id is a machine's handle -
                # a hostname with a mark on it, so that two Pis of the same
                # name are still two Pis - and putting it on a screen at the
                # front of a hall tells the room nothing it wants to know.
                "winner_name": (self.units[winner].name if winner in self.units
                                else None),
                "unit_points": per_unit,
                "top": right[:10],
            }
            # A block closes on the twelfth question, the twenty-fourth and so
            # on, and the summary carries the declaration so the screen that
            # is already showing the round result shows the block result with
            # it rather than needing a second poll to find out.
            if self.plan and tournament.ends_a_block(self.round_number):
                summary["block_won"] = self._declare_block(
                    tournament.block_of(self.round_number))
            self.history.append(summary)
            self.round = None
            return summary

    # ----------------------------------------------------------- the plan

    def set_plan(self, plan):
        """Lay out a whole tournament, replacing anything half played.

        Called when a hall starts, and again when net control moves it to
        another licence class: a Technician tournament that becomes a General
        one is a different examination and the draw has to be redrawn for it.
        """
        with self.lock:
            self.plan = plan
            self.plan_at = 0
            self.blocks = []
            self._block_units = {}
            self._block_people = {}

    def next_question(self):
        """The next question of the tournament, or None when it is played out.

        None is not a failure. It is the tournament finishing, which is a
        thing a tournament is supposed to do.
        """
        with self.lock:
            questions = (self.plan or {}).get("questions") or []
            if self.plan_at >= len(questions):
                return None
            question = questions[self.plan_at]
            self.plan_at += 1
            return question

    def plan_state(self):
        """How far through, in the terms a screen says it in."""
        with self.lock:
            if not self.plan:
                return None
            length = len(self.plan.get("questions") or [])
            asked = min(self.plan_at, length)
            return {
                "asked": asked,
                "length": length,
                "block": tournament.block_of(max(1, asked)),
                "blocks": self.plan.get("blocks"),
                "block_size": self.plan.get("block", tournament.BLOCK),
                "difficulty": self.plan.get("difficulty"),
                # Whether the draw was actually ordered easiest-first. False
                # means blueprint order, which is the truth on a unit with no
                # answer history to measure difficulty from - and a screen
                # should be able to say so rather than implying a warm-up.
                "ramped": bool(self.plan.get("ramped")),
                "done": asked >= length and length > 0,
            }

    def _declare_block(self, number):
        """Who won the last twelve questions - the table, and the player."""
        unit_id, unit_points = None, 0
        if self._block_units:
            best = max(self._block_units.values())
            tied = [u for u, p in self._block_units.items() if p == best]
            # Level on the block is broken by who is behind overall, for the
            # same reason the round tie is: a table already running away with
            # the hall should not also collect the consolation.
            floor = min(self.units[u].score for u in tied if u in self.units
                        ) if any(u in self.units for u in tied) else 0
            level = [u for u in tied
                     if u in self.units and self.units[u].score == floor]
            unit_id = random.choice(level or tied)
            unit_points = best
        top = sorted(self._block_people.values(),
                     key=lambda p: (-p["points"], p["name"]))
        row = {
            "block": number,
            "through": self.round_number,
            "unit": unit_id,
            "name": (self.units[unit_id].name if unit_id in self.units
                     else None),
            "points": unit_points,
            # The block's best player as well as its best table, because the
            # table result is the hall's and the player result is the one
            # somebody at a table came for.
            "player": top[0] if top else None,
        }
        self.blocks.append(row)
        self._block_units = {}
        self._block_people = {}
        return row

    def standings(self, limit=8):
        """Which tables are ahead, and which just gained.

        For the strip along the foot of a board that is not net control's own
        screen. A spectator at table three can see their own table's players
        on this unit; what they cannot see, and most want to, is where the
        table stands in the hall.
        """
        with self.lock:
            gained = (self.history[-1].get("unit_points") or {}
                      if self.history else {})
            rows = sorted(self.units.values(),
                          key=lambda u: (-u.score, u.name.lower()))
            return [{"name": u.name, "score": u.score,
                     "gained": gained.get(u.id, 0), "players": u.players,
                     "present": u.present} for u in rows[:limit]]

    # ---------------------------------------------------------------- board

    def board(self):
        """The big screen: who is winning, and how big the hall is."""
        with self.lock:
            units = sorted((u.as_dict() for u in self.units.values()),
                           key=lambda u: (-u["score"], u["name"]))
            present = [u for u in units if u["present"]]
            return {
                "name": self.name,
                "difficulty": self.difficulty,
                "health": self.health(),
                "units": units,
                # Ready-made for the strip at the foot of a board, including
                # the boards on other units that fetch this one over HTTP.
                "standings": self.standings(),
                "units_present": len(present),
                "players": sum(u["players"] for u in present),
                "round": self.current(),
                "picker_unit": self.picker_unit,
                "picker_name": (self.units[self.picker_unit].name
                                if self.picker_unit in self.units else None),
                "last": self.history[-1] if self.history else None,
                "people": self.people_board(),
                "plan": self.plan_state(),
                "blocks": list(self.blocks),
            }

    def people_board(self, limit=40):
        """Everyone in the hall by running total, best first.

        Practice players are in the list and flagged, so a screen can show the
        hall as it is and still be asked to show only the people in the room.
        Deciding that here rather than on the screen would mean two boards
        watching one net could disagree about who is winning.
        """
        with self.lock:
            rows = sorted(
                self.people.values(),
                key=lambda p: (-p["score"], -p["correct"], p["name"]))
            # The certificate name is not the board's to hand out: anything
            # polling the board would otherwise get every player's real name
            # in the JSON, whether or not a screen drew it.
            return [{k: v for k, v in p.items() if k != "cert_name"}
                    for p in rows[:limit]]

    def people_for_awards(self, limit=200):
        """The same list with the certificate names on - for the host only."""
        with self.lock:
            rows = sorted(
                self.people.values(),
                key=lambda p: (-p["score"], -p["correct"], p["name"]))
            return [dict(p) for p in rows[:limit]]


_net = None
_net_lock = threading.Lock()


def net(create=False, name="ELMER Net", cap=MAX_UNITS,
        difficulty="technician"):
    global _net
    with _net_lock:
        if _net is None and create:
            _net = Net(name, cap, difficulty)
        return _net


def close_net():
    global _net
    with _net_lock:
        _net = None
