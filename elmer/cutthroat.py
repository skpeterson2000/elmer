"""CutThroat - musical chairs with questions.

KC9SP: players don't get the grace of a shootout's misses. Miss the question
and you didn't get to a chair in time - you're out of the round. Every
correct answer keeps its seat. When two remain they get fifteen questions
to sort it out themselves; then the bar goes up, time comes into it, and it
is decided briefly. The seated still see every question that goes by.

**One game, three parts.**

*The field.* Everybody answers the same drawn question. Anyone still in
who did not get it right - a wrong answer, or no answer at all, which is
the same thing when the music stops - is out. One exception, because a
question nobody got is a question and not a chair: a round where *nobody*
still in was right eliminates nobody. A field of three can end in one
round if two miss; the one left is the winner and there is no final.

*The final.* Two left. Fifteen questions, and a miss no longer removes
anybody: the better count of correct answers over the fifteen wins. Both
level after fifteen, and the game goes to the last part.

*Sudden death.* One question at a time. One right and one wrong: the right
one wins. Both right: the faster wins. Both wrong: another question.

**The seated stay.** A player who is out keeps their phone on the game:
the questions arrive, the reveal arrives, they see who is left. They just
cannot answer - or can, and it counts for nothing, which is the same thing
said more gently. Their place is the order they went out in, last out
placing highest.

**Practice players are in it like anybody**, and out like anybody: a bot
that misses has missed. What they cannot do is arrive late. A person who
sits down while the field is still playing takes a chair; one who sits
down during the final or after is seated with the others, watching.

**Leaving is losing.** Somebody who walks away is out from that moment,
and if that leaves one, that one has won - a game does not wait for a
player who has gone to the coffee urn.

Nothing here has a clock or a question in it. The room feeds it every
round's answers; it says who is out, what part of the game it is in, and
who has won.
"""
FINAL_LENGTH = 15


class CutThroat:

    def __init__(self, order, passers=()):
        self.order = list(order)              # seating order, for places
        self.passers = set(passers)           # practice players
        self.out_at = {}                      # player -> round they went out
        self.left = set()                     # walked away
        self.rounds = 0
        self.final = None                     # {"round": n, "correct": {pid: n}} once two remain
        self.sudden = False
        self._winner = None
        self.history = []
        self._settle()                        # a table of two starts in the final

    # ---------------------------------------------------------------- state

    def alive(self):
        return [p for p in self.order if p not in self.out_at]

    def phase(self):
        if self._winner is not None:
            return "over"
        if self.sudden:
            return "sudden"
        if self.final is not None:
            return "final"
        return "field"

    def over(self):
        return self._winner is not None

    def winner(self):
        return self._winner

    def seat(self, player_id):
        """Somebody sat down. In the field they take a chair; later, a seat
        among the watching."""
        if player_id in self.order:
            return
        self.order.append(player_id)
        if self.phase() != "field":
            self.out_at[player_id] = self.rounds

    def withdraw(self, player_id):
        """Somebody walked away: out from now, and if that leaves one, done."""
        if player_id not in self.order or player_id in self.out_at:
            return
        self.left.add(player_id)
        self.out_at[player_id] = self.rounds
        self._settle()

    def _settle(self):
        """What the count of the living means for the parts of the game."""
        alive = self.alive()
        if len(alive) == 1 and self._winner is None:
            self._winner = alive[0]
        elif len(alive) == 2 and self.final is None and self._winner is None:
            self.final = {"round": 0, "correct": {p: 0 for p in alive}}

    # ----------------------------------------------------------------- play

    def play(self, answers):
        """One round's answers, keyed by player: {"correct": bool, "ms": n}.
        Returns what happened, for the screens."""
        self.rounds += 1
        alive = self.alive()
        got = {p: answers.get(p, {"correct": False, "ms": None}) for p in alive}
        right = [p for p in alive if got[p]["correct"]]
        out, note = [], ""
        phase = self.phase()

        if phase == "field":
            if right:
                out = [p for p in alive if p not in right]
                for p in out:
                    self.out_at[p] = self.rounds
            else:
                note = "nobody had it - nobody is out"
            self._settle()

        elif phase == "final":
            self.final["round"] += 1
            for p in right:
                self.final["correct"][p] += 1
            if self.final["round"] >= FINAL_LENGTH:
                a, b = alive
                ca, cb = self.final["correct"][a], self.final["correct"][b]
                if ca != cb:
                    self._winner = a if ca > cb else b
                    self.out_at[b if ca > cb else a] = self.rounds
                else:
                    self.sudden = True
                    note = f"level after {FINAL_LENGTH} - sudden death"

        elif phase == "sudden":
            if len(right) == 1:
                self._winner = right[0]
            elif len(right) == 2:
                a, b = right
                ma, mb = got[a]["ms"], got[b]["ms"]
                if ma is not None and mb is not None and ma != mb:
                    self._winner = a if ma < mb else b
            if self._winner is not None:
                for p in alive:
                    if p != self._winner:
                        self.out_at[p] = self.rounds
            else:
                note = "still level - another question"

        row = {
            "round": self.rounds, "phase": phase, "right": right, "out": out,
            "remaining": self.alive(), "note": note,
            "final_round": self.final["round"] if self.final else None,
            "winner": self._winner, "over": self.over(),
        }
        self.history.append(row)
        return row

    # ---------------------------------------------------------------- views

    def standing(self):
        """Everybody, best first: the living by seating, then the out in
        reverse order of going out - last out placing highest."""
        alive = self.alive()
        gone = sorted((p for p in self.order if p in self.out_at),
                      key=lambda p: (-self.out_at[p], self.order.index(p)))
        rows = []
        for place, p in enumerate(alive + gone, start=1):
            rows.append({
                "player": p,
                "place": (1 if p == self._winner else place),
                "in": p not in self.out_at,
                "out_round": self.out_at.get(p),
                "left": p in self.left,
                "bot": p in self.passers,
                "final_correct": (self.final or {}).get("correct", {}).get(p),
            })
        return rows

    def as_dict(self):
        return {
            "phase": self.phase(), "rounds": self.rounds,
            "remaining": len(self.alive()), "players": len(self.order),
            "final_round": self.final["round"] if self.final else None,
            "final_length": FINAL_LENGTH,
            "winner": self._winner, "over": self.over(),
            "standing": self.standing(),
        }
