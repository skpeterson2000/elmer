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
import secrets
import threading
import time
from collections import deque

from . import show as showmod, tournament
from .party import callsign_of as party_callsign
from .shootout import Shootout

# The games a hall can be playing. A tournament asks the blueprint's questions
# and every table answers the same ones; a shootout hands one table the choice
# of subject, and the rest of the hall has to keep up.
TOURNAMENT = "tournament"
SHOOTOUT = "shootout"

# How long the picking table gets. Longer than a table on its own, because a
# table at a hamfest is several people conferring over a screen.
HALL_PICK_SECONDS = 60.0

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
        # What the unit called itself, before net control disambiguated it.
        # A fleet imaged from one SD card shares a hostname and a machine-id,
        # so every unit computes the *same* id - and net control keys tables
        # by id, so the second to check in used to overwrite the first and a
        # hall silently collapsed to one table. So the claimed id is kept
        # apart from the slot id, and two units that claim the same one are
        # told apart by the instance token each running unit sends.
        self.claimed_id = unit_id
        self.instance = ""
        self.address = ""
        self.cloned = False       # true when its id had to be disambiguated
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
        # What its table screen said it was showing at the last check-in -
        # "question", "result", "card:trivia", "attention" - so the host's
        # page can show the room rather than a list of names.
        self.showing = ""
        self.names = []          # who is seated, by display name, for the host
        # Whether somebody at the table has said it is ready. Check-in is
        # automatic - a table rejoins its net at 04:00 with nobody near it -
        # so being checked in says the machine is up, not that the people
        # are. This is the operator's word, pressed on the table screen and
        # carried up with every check-in after; the host's panel shows the
        # two apart. Rounds still start on people actually seated: a table
        # that said ready with nobody at it has nobody to answer.
        self.ready = False
        # The round-trip time this table measured to net control over the
        # network, and whether it was measured with a round open ("game") or
        # not ("waiting"). This is the wire, not the master's processing -
        # the p95 in health() is what this machine did after a request
        # arrived; this is how long the request took to get here and back.
        # A hall stays smooth on the master's numbers and still feels slow if
        # the wifi to one table is bad, and only this catches that.
        self.rtt_ms = None
        self.rtt_room = ""

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
                "simulated": self.simulated, "showing": self.showing,
                "ready": self.ready, "cloned": self.cloned,
                "rtt_ms": self.rtt_ms, "rtt_room": self.rtt_room}


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
        # What this net *is*, as against what it is called. The name changes
        # - it follows the material when the hall drifts from Technician to
        # General, and the host can type over it - so nothing keys on it. A
        # table keys on this: it is announced over the air and sent back with
        # every check-in, so a table can tell the net it is in has been
        # renamed from the net at this address being a new one, and can find
        # a net again that came back on a different address.
        self.token = secrets.token_urlsafe(9)
        # The key under which tonight's people are written into the hall
        # log - see db.hall_who(). Made here, held here, never stored: the
        # log can tell one evening's people apart and nobody can name them.
        self.log_key = secrets.token_bytes(32)
        # When this net opened: tonight's answers in the hall log are the
        # ones since, and that is what the host's weak-sections list reads.
        self.since = _now()
        self._service = deque(maxlen=HEALTH_WINDOW)
        self.units = {}
        self.round_number = 0
        self.round = None          # dict: the question every unit is showing
        self.opened_at = 0.0
        # The run-up to a question after a pause: "Get ready" and three, two,
        # one on every screen before the first question of a game or the
        # first after an intermission. Held here rather than in the conductor
        # because the screens read the net, and a table screen, a phone and
        # the board must all be counting the same seconds. See hall.LEAD_IN.
        self.lead_in_until = 0.0
        self.lead_in_at = 0.0
        self.lead_in_seconds = 0.0
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
        # A shootout across the hall. The rules object is the same one a
        # single table uses; here the players are the tables. A table makes
        # its shot if any person at it got the question right, and a table
        # that had nobody right when the picker made it takes a letter.
        self.mode = TOURNAMENT
        self.shootout = None
        self.pick = None            # the subject chosen, waiting to be asked
        self.pick_seconds = HALL_PICK_SECONDS
        self._pick_since = None
        self.titles = {}
        self.groups = {}
        # Told when a round closes, with its summary - the app writes the
        # round to the hall's log from here. This module has no database in
        # it and should not; it is handed a function instead.
        self.on_round_closed = []
        # What every screen shows when it is not showing a question - the
        # host's announcements, the deck between rounds, the hall's mode. Its
        # sponsors and notices are loaded from this unit's state, so an
        # evening set up in advance is still set up when the net opens.
        self.show = showmod.Show.load()

    # ------------------------------------------------------------- lead-in

    def begin_lead_in(self, seconds):
        """Start the run-up: the next question comes when it has run out."""
        with self.lock:
            now = _now()
            self.lead_in_at = now
            self.lead_in_seconds = float(seconds)
            self.lead_in_until = now + float(seconds)

    def cancel_lead_in(self):
        with self.lock:
            self.lead_in_until = 0.0

    def lead_in_remaining(self):
        """Seconds still to run, 0.0 when it has run out, None when none is on."""
        with self.lock:
            if not self.lead_in_until:
                return None
            return max(0.0, self.lead_in_until - _now())

    def lead_in_view(self):
        """The run-up as a screen counts it: what is left, of how much, and
        which run-up this is - a screen that gets a stale reading a second
        late needs to know a fresh one is the same countdown, not a new one."""
        remaining = self.lead_in_remaining()
        if remaining is None:
            return None
        with self.lock:
            return {"remaining": round(remaining, 2),
                    "seconds": self.lead_in_seconds,
                    "at": round(self.lead_in_at, 2)}

    # ---------------------------------------------------------------- show

    def show_for(self, unit_id):
        """The hall's show as one unit should see it, for its check-in reply."""
        with self.lock:
            standings = [{"name": r["name"], "score": r["score"],
                          "gained": r["gained"]} for r in self.standings(6)]
        view = self.show.for_unit(unit_id, standings=standings, join=True)
        view["lead_in"] = self.lead_in_view()
        return view

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
                    # Tables whose operator pressed the button, as against
                    # tables that merely have people at them.
                    "said_ready": sum(1 for u in self.units.values()
                                      if u.present and u.ready),
                    "simulated": sum(1 for u in self.units.values()
                                     if u.simulated)}

    def _slot_for(self, claimed, instance, address, create):
        """The key in self.units for the unit checking in.

        Normally the claimed id itself. But a fleet imaged from one card
        shares hostname and machine-id, so several units claim the same id;
        they are told apart by the instance token a running unit sends (and,
        failing that, by the address the request came from). A newcomer that
        collides with a *different* running unit gets its own slot,
        ``id#2``, ``id#3``, and keeps it for as long as it keeps checking in.

        Called inside self.lock.
        """
        # A unit already seated under this exact origin keeps its slot.
        # Simulated tables count: their reports come through here as well, and
        # their ids never collide with a real unit's (they are "sim-*").
        for uid, u in self.units.items():
            if u.claimed_id != claimed:
                continue
            if instance and u.instance:
                if u.instance == instance:
                    return uid, False
            elif address and u.address == address:
                return uid, False
            elif not instance and not u.instance and not address:
                return uid, False           # nothing to tell them apart by
        if not create:
            return None, False
        if claimed not in self.units:
            return claimed, False           # the id is free; take it
        # Held by a different running unit: mint a fresh slot beside it.
        n = 2
        while f"{claimed}#{n}" in self.units:
            n += 1
        return f"{claimed}#{n}", True

    def check_in(self, unit_id, name=None, players=0, ready=None,
                 instance=None, address=None, rtt=None, room=None):
        """A unit says it is here, and how many people are sitting at it.

        Returns (unit, None) or (None, reason). A unit already known is always
        readmitted - the cap is about how large the hall grows, not about
        throwing out a table that briefly lost the network.

        `ready` is the table's own word, when it gives one - see Unit.ready.
        None leaves what the unit last said, so a caller that does not carry
        the word does not take it away.
        """
        instance = str(instance or "")[:24]
        address = str(address or "")[:64]
        with self.lock:
            slot, minted = self._slot_for(unit_id, instance, address, create=True)
            unit = self.units.get(slot)
            if unit is None:
                # A person arriving takes a machine's place rather than being
                # turned away by one, and rather than making the hall bigger
                # than the room it is in.
                self.retire_simulated()
                slot, minted = self._slot_for(unit_id, instance, address, create=True)
                state = self.health()
                if state["seats"] <= 0:
                    if state["cap"] < state["hard_cap"]:
                        return None, ("net control is busy and has stopped "
                                      "taking units - start a second net")
                    return None, (f"this net is full at {state['cap']} units "
                                  f"({state['cap'] * 8} seats) - start a "
                                  f"second net")
                display = name or unit_id
                if minted:
                    # Two units of one name is a board nobody can read, so the
                    # copy is marked - and the operator is told, because the
                    # real fix is to give the units their own hostnames.
                    seen = sum(1 for u in self.units.values()
                               if not u.simulated and u.claimed_id == unit_id) + 1
                    display = f"{display} ({seen})"
                    log.warning("net: a second unit is calling itself %r - two "
                                "machines imaged from one card share an identity. "
                                "Seating it as %s; give the units their own "
                                "hostnames to tell them apart on the board.",
                                unit_id, slot)
                unit = Unit(slot, display, players)
                unit.claimed_id = unit_id
                unit.cloned = minted
                self.units[slot] = unit
                log.info("net: table %s (%s) checked in with %d player%s - %d table%s now",
                         unit.name, slot, players, "" if players == 1 else "s",
                         len(self.units), "" if len(self.units) == 1 else "s")
                if self.shootout is not None and not self.shootout.over():
                    self.shootout.admit(slot)
            unit.last_seen = _now()
            unit.instance = instance or unit.instance
            unit.address = address or unit.address
            if name and not unit.cloned:
                unit.name = name
            unit.players = int(players or 0)
            if ready is not None and bool(ready) != unit.ready:
                unit.ready = bool(ready)
                log.info("net: table %s (%s) says it is %s", unit.name, unit_id,
                         "ready" if unit.ready else "not ready")
            if rtt is not None:
                try:
                    unit.rtt_ms = round(float(rtt), 1)
                    unit.rtt_room = str(room or "")[:8]
                except (TypeError, ValueError):
                    pass
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
                if self.shootout is not None and not self.shootout.over():
                    # Seated, and never allowed to keep the pick.
                    self.shootout.admit(unit_id)
                    self.shootout.passers.add(unit_id)
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
            self._forget_unit(going.id)
            log.info("net: simulated table %s stood down", going.name)
            return going

    def _forget_unit(self, uid):
        """A table leaves the hall, and every game it was in.

        A shootout still seating a table that has gone would hand it the pick
        and wait for a choice that never comes. Found by a test in which a
        real table checking in stood a practice table down, mid-game.
        """
        self.units.pop(uid, None)
        self._sim_plan.pop(uid, None)
        self.results.pop(uid, None)
        if self.shootout is not None:
            self.shootout.withdraw(uid)
            if self.shootout.picker is None and not self.shootout.over():
                self.shootout.picker = self.shootout.next_picker(uid)
            self._pick_since = None

    def present_units(self):
        with self.lock:
            return [u for u in self.units.values() if u.present]

    def prune(self):
        """Forget units that have been gone long enough to be gone."""
        with self.lock:
            dead = [uid for uid, u in self.units.items()
                    if u.quiet_for > DROP_AFTER]
            for uid in dead:
                log.info("net: table %s (%s) has been silent %d s - forgotten",
                         self.units[uid].name, uid, int(self.units[uid].quiet_for))
                self._forget_unit(uid)
            return len(dead)

    # --------------------------------------------------------------- rounds

    def start_round(self, pool_id, question_id, answer_index, payload,
                    seconds=45.0):
        """Put one question to every unit in the hall."""
        with self.lock:
            self.round_number += 1
            self.opened_at = _now()
            self.results = {}
            self.lead_in_until = 0.0        # the question is the end of it
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

    def report(self, unit_id, round_number, players, instance=None, address=None):
        """A unit hands in its cohort's answers for the round.

        `players` is a list of {name, correct, ms}. Scoring happened on the
        unit; the net ranks the hall. The instance and address resolve the
        same slot the unit checked in under, so a disambiguated clone reports
        to its own table rather than the first that took the shared id.
        """
        instance = str(instance or "")[:24]
        address = str(address or "")[:64]
        with self.lock:
            if not self.round or round_number != self.round_number:
                return None, "that round is not the one in progress"
            slot, _ = self._slot_for(unit_id, instance, address, create=False)
            unit = self.units.get(slot) if slot else None
            if unit is None:
                return None, "check in first"
            if unit.id in self.results:
                return None, "already reported this round"
            rows = []
            for p in players or []:
                try:
                    rows.append({
                        "unit": unit.id, "unit_name": unit.name,
                        "name": str(p.get("name", ""))[:32],
                        "correct": bool(p.get("correct")),
                        "ms": float(p.get("ms", 0)) or 0.0,
                        # Carried, not inferred: a table knows which of its
                        # players were practice and the hall does not.
                        "bot": p.get("bot") or None,
                        # What they want on a certificate; never on a board.
                        "cert_name": (str(p.get("cert_name") or "")[:48]
                                      or None),
                        # The class they said they hold, for the log alone.
                        "license": str(p.get("license") or "")[:12]})
                except (TypeError, ValueError):
                    continue
            self.results[unit.id] = rows
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
                # A callsign is one person wherever they sat; a name is one
                # person per table. KC9SP at Poldhu and KC9SP at Clifden are
                # one row; Bob at Poldhu and Bob at Clifden are two.
                call = None if row.get("bot") else party_callsign(row["name"])
                who = self.people.setdefault(
                    ("*", call) if call else (row["unit"], row["name"]),
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
                    ("*", call) if call else (row["unit"], row["name"]),
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
                "closed_at": _now(),
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
                # The placings, without what the placed carry for the log:
                # a board polls this, and neither a certificate name nor a
                # license class is the board's to hand out.
                "top": [{k: v for k, v in r.items()
                         if k not in ("cert_name", "license")}
                        for r in right[:10]],
            }
            # In a shootout the round is also a shot, table by table: a table
            # made it if any person at it was right, and its time is its
            # quickest right answer. Practice players do not make a table's
            # shot - a table full of bots that "made it" would be the program
            # handing itself the pick.
            if self.shootout is not None:
                section = (self.round.get("question") or {}).get("section")
                if section:
                    by_unit = {}
                    for row in everyone:
                        if row.get("bot"):
                            continue
                        slot = by_unit.setdefault(row["unit"], {"correct": False, "ms": None})
                        if row["correct"]:
                            slot["correct"] = True
                            slot["ms"] = (row["ms"] if slot["ms"] is None
                                          else min(slot["ms"], row["ms"]))
                    # A practice table's shot is its own simulated answers.
                    for row in everyone:
                        uid = row["unit"]
                        if uid in self.units and self.units[uid].simulated:
                            slot = by_unit.setdefault(uid, {"correct": False, "ms": None})
                            if row["correct"]:
                                slot["correct"] = True
                                slot["ms"] = (row["ms"] if slot["ms"] is None
                                              else min(slot["ms"], row["ms"]))
                    shot = self.shootout.play(section, by_unit)
                    # Names for the screens: the rules speak in unit ids.
                    shot["took_names"] = [self.units[u].name for u in shot.get("took", [])
                                          if u in self.units]
                    shot["picker_name"] = (self.units[shot["picker"]].name
                                           if shot.get("picker") in self.units else None)
                    summary["shootout"] = shot

            # A block closes on the twelfth question, the twenty-fourth and so
            # on, and the summary carries the declaration so the screen that
            # is already showing the round result shows the block result with
            # it rather than needing a second poll to find out.
            if self.plan and tournament.ends_a_block(self.round_number):
                summary["block_won"] = self._declare_block(
                    tournament.block_of(self.round_number))
            summary["section"] = (self.round.get("question") or {}).get("section") or ""
            self.history.append(summary)
            # The evening's record, one line a round: what the organiser
            # asks for afterwards and the only place it is written in words.
            people = [r for r in everyone if not r.get("bot")]
            log.info("net round %d closed: %s, %d of %d tables reported, %d people "
                     "answered, %d right, first %s%s%s",
                     summary["number"], self.round.get("question_id"),
                     summary.get("units_reported", len(self.results)),
                     len(self.present_units()), len(people),
                     sum(1 for r in people if r["correct"]),
                     (right[0]["name"] + " at " + right[0].get("unit_name", "?")) if right else "nobody",
                     (", table win " + summary["winner_name"]) if summary.get("winner_name") else "",
                     (", block %d to %s" % (summary["block_won"]["block"],
                                            summary["block_won"].get("name") or "a tie"))
                     if summary.get("block_won") else "")
            # What the listeners get is the summary plus every answer, not
            # only the ones that placed: the log wants the misses too, and
            # so does the difficulty measure. It is a separate dict because
            # the summary goes to every board that polls, and these rows
            # carry what a board must never be handed - the certificate
            # names and the license classes.
            given = dict(summary)
            given["given"] = everyone
            self.round = None
        # Outside the lock: a listener that writes to a database should not
        # hold the hall still while it does.
        for listener in list(self.on_round_closed):
            try:
                listener(given)
            except Exception as exc:                  # pragma: no cover
                log.warning("net: a round listener failed: %r", exc)
        return summary

    # ------------------------------------------------------------ shootout

    def begin_shootout(self, sections, titles=None, groups=None,
                       pick_seconds=None):
        """A shootout across the tables checked in, real tables first.

        Real tables seat first in the order they arrived and the practice
        tables after, so the opening pick is a room's, not the program's; and
        the practice tables never keep the pick, for the same reason a
        practice player never does.
        """
        with self.lock:
            real = [uid for uid, u in self.units.items() if not u.simulated]
            fake = [uid for uid, u in self.units.items() if u.simulated]
            if len(real) + len(fake) < 2:
                return None, "a shootout needs two tables"
            self.shootout = Shootout(real + fake, sections, passers=fake)
            self.titles = dict(titles or {})
            self.groups = dict(groups or {})
            self.mode = SHOOTOUT
            self.pick = None
            self.pick_seconds = float(pick_seconds or HALL_PICK_SECONDS)
            self._pick_since = None
            self.plan = None
            return self.shootout, None

    def end_shootout(self):
        with self.lock:
            self.shootout = None
            self.mode = TOURNAMENT
            self.pick = None
            self._pick_since = None

    def choose(self, unit_id, section):
        """The picking table names the subject. Refused in words otherwise."""
        with self.lock:
            s = self.shootout
            if s is None:
                return None, "this net is not running a shootout"
            if s.over():
                return None, "the shootout is over"
            if self.round is not None:
                return None, "a question is still open"
            if s.picker != unit_id:
                holder = self.units.get(s.picker)
                return None, ("it is not your table's pick" +
                              (f" - it is {holder.name}'s" if holder else ""))
            ok, why = s.may_pick(section)
            if not ok:
                return None, why
            self.pick = section
            return section, None

    def choose_for_simulated(self):
        """A practice table holding the pick chooses at random from what is left."""
        with self.lock:
            s = self.shootout
            if s is None or s.over() or self.pick is not None or self.round is not None:
                return None
            holder = self.units.get(s.picker)
            if holder is None or not holder.simulated:
                return None
            left = s.available()
            if not left:
                return None
            self.pick = random.choice(left)
            return self.pick

    def waiting_for_pick(self):
        """True while the next question is a real table's to choose."""
        with self.lock:
            s = self.shootout
            waiting = False
            if s is not None and not s.over() and self.pick is None and self.round is None:
                holder = self.units.get(s.picker)
                waiting = holder is not None and not holder.simulated
            if not waiting:
                self._pick_since = None
            elif self._pick_since is None or self._pick_since[1] != s.picker:
                self._pick_since = (_now(), s.picker)
            return waiting

    def pick_remaining(self):
        with self.lock:
            if not self.waiting_for_pick():
                return None
            return max(0.0, self.pick_seconds - (_now() - self._pick_since[0]))

    def pick_overdue(self):
        with self.lock:
            left = self.pick_remaining()
            return left is not None and left <= 0.0

    def pass_pick(self):
        """The picking table did not choose in time: round the hall, no letter."""
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

    def take_pick(self):
        with self.lock:
            section, self.pick = self.pick, None
            return section

    def shootout_over(self):
        with self.lock:
            return self.shootout is not None and self.shootout.over()

    def shootout_view(self, unit_id=None):
        """The hall's shootout with table names on it, for screens."""
        with self.lock:
            s = self.shootout
            if s is None:
                return None
            standing = []
            for row in s.standing():
                unit = self.units.get(row["player"])
                standing.append({**row,
                                 "name": unit.name if unit else "(gone)",
                                 "simulated": bool(unit.simulated) if unit else False,
                                 "present": bool(unit.present) if unit else False})
            holder = self.units.get(s.picker) if s.picker else None
            winner = self.units.get(s.winner()) if s.winner() else None
            left = self.pick_remaining()
            return {
                "on": True, "word": "ELMER",
                "standing": standing,
                "picker": s.picker, "pick_reason": s.pick_reason,
                "picker_name": holder.name if holder else None,
                "picker_is_simulated": bool(holder.simulated) if holder else False,
                "your_pick": bool(unit_id is not None and s.picker == unit_id
                                  and self.pick is None and self.round is None
                                  and not s.over()),
                "pick": self.pick,
                "pick_title": self.titles.get(self.pick, self.pick),
                "pick_remaining": None if left is None else round(left, 1),
                "available": [{"section": c, "title": self.titles.get(c, c),
                               "group": self.groups.get(c, ("", ""))[0],
                               "group_title": self.groups.get(c, ("", ""))[1]}
                              for c in s.available()],
                "spent": list(s.spent),
                "over": s.over(), "drawn": s.drawn(),
                "winner": s.winner(),
                "winner_name": winner.name if winner else None,
                "played": len(s.history),
                "last": s.history[-1] if s.history else None,
                "last_shot": next((h for h in reversed(s.history)
                                   if h.get("section")), None),
            }

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
        lead_in = self.lead_in_view()
        with self.lock:
            units = sorted((u.as_dict() for u in self.units.values()),
                           key=lambda u: (-u["score"], u["name"]))
            present = [u for u in units if u["present"]]
            return {
                "name": self.name,
                "token": self.token,
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
                # How long the last result has stood, so the board can let the
                # deck have the screen once the room has read it.
                "last_closed_for": (round(_now() - self.history[-1]["closed_at"], 1)
                                    if self.history and self.history[-1].get("closed_at")
                                    else None),
                "people": self.people_board(),
                "plan": self.plan_state(),
                "blocks": list(self.blocks),
                "mode": self.mode,
                "shootout": self.shootout_view(),
                # The board is a screen in the hall like any other: it shows
                # the deck and the announcements, addressed to nobody's seat.
                "show": dict(self.show.for_unit(None, standings=[
                    {"name": r["name"], "score": r["score"], "gained": r["gained"]}
                    for r in self.standings(6)], join=True), lead_in=lead_in),
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
