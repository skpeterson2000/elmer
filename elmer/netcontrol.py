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
import threading
import time
from collections import deque

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

# A round closes when every present unit has reported, or when this much time
# has passed since it opened. A hall does not wait indefinitely for one table.
ROUND_GRACE = 90.0


def _now():
    return time.monotonic()


class Unit:
    """One cohort Pi, checked in to the net."""

    def __init__(self, unit_id, name, players=0):
        self.id = unit_id
        self.name = name
        self.players = players
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
                "reported_round": self.reported_round}


class Net:
    """The competition: many units, one question at a time, one leaderboard."""

    def __init__(self, name="ELMER Net", cap=MAX_UNITS):
        self.lock = threading.RLock()
        self.name = name
        self.cap = cap
        self._service = deque(maxlen=HEALTH_WINDOW)
        self.units = {}
        self.round_number = 0
        self.round = None          # dict: the question every unit is showing
        self.opened_at = 0.0
        self.results = {}          # unit_id -> list of player results
        self.history = []
        self.picker_unit = None

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
            return {"units": known, "cap": cap, "hard_cap": self.cap,
                    "p95_ms": round(p95, 1), "seats": max(0, cap - known),
                    "players": known * 8, "healthy": p95 <= SLOW_MS}

    def check_in(self, unit_id, name=None, players=0):
        """A unit says it is here, and how many people are sitting at it.

        Returns (unit, None) or (None, reason). A unit already known is always
        readmitted - the cap is about how large the hall grows, not about
        throwing out a table that briefly lost the network.
        """
        with self.lock:
            unit = self.units.get(unit_id)
            if unit is None:
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
            self.round = {
                "number": self.round_number, "pool": pool_id,
                "question_id": question_id, "answer_index": answer_index,
                "question": payload, "seconds": seconds,
            }
            return self.round

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
                        "ms": float(p.get("ms", 0)) or 0.0})
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
            return bool(self.round) and (_now() - self.opened_at) > ROUND_GRACE

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
                # Across a hall, place points flatten quickly - otherwise one
                # fast table takes everything and the rest stop trying. Being
                # correct is most of the value; being first is a bonus.
                row["place"] = place
                row["points"] = 5 if place <= 3 else (3 if place <= 10 else 1)
                per_unit[row["unit"]] = per_unit.get(row["unit"], 0) + row["points"]

            for uid, points in per_unit.items():
                if uid in self.units:
                    self.units[uid].score += points

            winner = None
            if per_unit:
                best = max(per_unit.values())
                tied = [u for u, p in per_unit.items() if p == best]
                # A tie hands the pick to whoever is behind overall, so a
                # runaway table does not also own the question list.
                winner = min(tied, key=lambda u: (self.units[u].score, u))
                self.units[winner].rounds_won += 1
            self.picker_unit = winner

            summary = {
                "number": self.round_number,
                "question_id": self.round["question_id"],
                "pool": self.round["pool"],
                "units_reported": len(self.results),
                "answers": len(everyone),
                "correct": len(right),
                "winner_unit": winner,
                "unit_points": per_unit,
                "top": right[:10],
            }
            self.history.append(summary)
            self.round = None
            return summary

    # ---------------------------------------------------------------- board

    def board(self):
        """The big screen: who is winning, and how big the hall is."""
        with self.lock:
            units = sorted((u.as_dict() for u in self.units.values()),
                           key=lambda u: (-u["score"], u["name"]))
            present = [u for u in units if u["present"]]
            return {
                "name": self.name,
                "health": self.health(),
                "units": units,
                "units_present": len(present),
                "players": sum(u["players"] for u in present),
                "round": self.current(),
                "picker_unit": self.picker_unit,
                "last": self.history[-1] if self.history else None,
            }


_net = None
_net_lock = threading.Lock()


def net(create=False, name="ELMER Net", cap=MAX_UNITS):
    global _net
    with _net_lock:
        if _net is None and create:
            _net = Net(name, cap)
        return _net


def close_net():
    global _net
    with _net_lock:
        _net = None
