"""Shootout - the game where choosing the question is the move.

A tournament asks everybody the same questions in the examination's own
proportions, and the skill is knowing the material. Shootout asks a different
question: what do you know that the person across the table does not? One
player holds the pick, chooses the subject, and everybody answers it - the
picker included.

That last part is the whole game. It is taken from HORSE, where the shooter
has to make the shot before anybody has to match it. Without it the winning
move is to pick the most obscure corner of the pool every time and wait for
the room to fail, which is a test of who owns the strangest question rather
than of who knows the most - and is no fun to play against. Making the picker
answer their own pick turns it back into "something I know and you do not",
which is the game that was asked for.

**The pick is a subject, not a question.** You cannot read four hundred
questions on a phone with a clock running, and the judgement being made is a
subject-level one anyway: I am good at feed lines, they went blank on feed
lines during the last net. So the picker chooses a section of the pool and a
question is drawn from it.

**A subject can only be spent once.** Otherwise the strongest player picks
their best section until everybody else is out, which takes four questions and
teaches nothing. Spending it means the run has a natural end: a player who
holds the pick for a long time is working through their good subjects, and
when they are gone they start missing.

**Letters.** Miss a question the picker got right and you take a letter.
E, L, M, E, R - five of them, and you are out. Miss a question the picker also
missed and you take nothing: the shot was not made.

**The pick passes when the picker misses**, and it passes to whoever answered
that question fastest among those who got it right. If nobody got it right it
goes round the table in order, because somebody has to have it. A picker who
keeps answering their own picks keeps picking, which is the reward for having
picked well.

**Last one standing wins.** With everybody else out there is nothing left to
decide, so the game ends the moment one player is left rather than playing out
a fixed length.

**Practice players never keep the pick.** The rule above is right for people
and wrong for furniture: a practice player that makes ninety percent of its
shots would hold the pick for ten questions while the table watched. So a
practice player's shot counts like anybody's - miss what it made and you take
a letter - but the pick moves on afterwards whatever happened, to the quickest
correct answer or round the table. The pick is the fun part, and it is for
the people.

**Somebody arriving late sits at the end** of the order with the same number
of letters as the best-placed player still in - so nobody is punished for
turning up, and nobody arrives ahead of the person who has been winning.

**Or the subjects run out.** Thirty-five subjects is thirty-five questions,
and a table of careful players can get through all of them with several still
standing. Then the game is over too, and whoever has the fewest letters wins
it - or nobody does, if they are level, which is a draw and is said to be one.
Without this ending a game where nobody ever made a shot went round the table
for ever, which is what happened on the bench with a round too short for
anybody to answer in.
"""

WORD = "ELMER"
OUT_AT = len(WORD)          # five letters and you are done


def letters(count):
    """The letters somebody has taken, as a word in progress."""
    return WORD[:max(0, min(int(count), OUT_AT))]


def is_out(count):
    return int(count) >= OUT_AT


class Shootout:
    """One game, as a rules object: no questions, no network, no clock.

    `players` is a list of ids in seating order. Everything here is decided
    from what has been played, so a table and a hall can both run it and get
    the same answer.
    """

    def __init__(self, players, sections=(), passers=()):
        self.order = list(players)
        self.letters = {p: 0 for p in self.order}
        self.sections = list(sections)
        self.spent = []                  # subjects already played, in order
        self.passers = set(passers)      # who never keeps the pick
        self.picker = self.order[0] if self.order else None
        # Why the current picker has it: first, kept, quickest, round,
        # timeout, or admitted. A screen greets a pick that was earned
        # differently from one that came round because nobody got it.
        self.pick_reason = "first" if self.picker is not None else None
        self.history = []                # one entry per question played

    def admit(self, player):
        """Somebody sat down mid-game. Seated last, level with the leader."""
        if player in self.letters:
            return False
        standing = self.live()
        self.order.append(player)
        self.letters[player] = (min(self.letters[p] for p in standing)
                                if standing else 0)
        if self.picker is None and not self.over():
            self.picker, self.pick_reason = player, "admitted"
        return True

    # ------------------------------------------------------------- standing

    def live(self):
        """Everybody still in, in seating order."""
        return [p for p in self.order if not is_out(self.letters.get(p, 0))]

    def over(self):
        if len(self.order) <= 1:
            return False                 # one player is not a game
        if len(self.live()) <= 1:
            return True
        return bool(self.sections) and not self.available()

    def winner(self):
        """Who won, or None while the game is on - or when it is drawn."""
        if not self.over():
            return None
        standing = self.live()
        if len(standing) == 1:
            return standing[0]
        # Out of subjects with several still in: fewest letters takes it, and
        # level on that is a draw rather than a coin toss nobody asked for.
        if not standing:
            return None
        fewest = min(self.letters[p] for p in standing)
        best = [p for p in standing if self.letters[p] == fewest]
        return best[0] if len(best) == 1 else None

    def drawn(self):
        """Over with nobody able to be called the winner."""
        return self.over() and self.winner() is None and len(self.live()) > 1

    def standing(self):
        return [{"player": p, "letters": self.letters.get(p, 0),
                 "word": letters(self.letters.get(p, 0)),
                 "out": is_out(self.letters.get(p, 0)),
                 "picking": p == self.picker} for p in self.order]

    # ---------------------------------------------------------- the picking

    def available(self):
        """The subjects still to be spent."""
        spent = set(self.spent)
        return [s for s in self.sections if s not in spent]

    def may_pick(self, section):
        """Whether this subject can be played, and why not if it cannot."""
        if section not in self.sections:
            return False, "that is not a subject in this pool"
        if section in self.spent:
            return False, "that subject has already been played"
        return True, None

    def next_picker(self, after):
        """Whose turn it is when the pick has to move on.

        Round the table from whoever had it, skipping anybody already out.
        Used when a question nobody answered correctly leaves no obvious
        claimant - somebody has to hold it, and going round in order is the
        one rule nobody can argue was unfair to them.
        """
        standing = self.live()
        if not standing:
            return None
        if after not in self.order:
            return standing[0]
        start = self.order.index(after)
        for step in range(1, len(self.order) + 1):
            candidate = self.order[(start + step) % len(self.order)]
            if candidate in standing:
                return candidate
        return None

    # ---------------------------------------------------------- the scoring

    def play(self, section, answers):
        """Score one question. `answers` is {player: {correct, ms}}.

        Returns what happened, in the terms a screen says it in.
        """
        ok, why = self.may_pick(section)
        if not ok:
            return {"error": why}

        picker = self.picker
        said = dict(answers or {})
        made = bool((said.get(picker) or {}).get("correct"))

        took = []
        if made:
            # Only a made shot costs anybody anything, and only the players
            # still in can take a letter - somebody already out is out.
            for player in self.live():
                if player == picker:
                    continue
                if not (said.get(player) or {}).get("correct"):
                    self.letters[player] = self.letters.get(player, 0) + 1
                    took.append(player)

        self.spent.append(section)

        # Who picks next. The picker keeps it while they keep making them -
        # unless they are furniture; a miss hands it to the quickest correct
        # answer, and a question nobody got goes round the table.
        if (made and not is_out(self.letters.get(picker, 0))
                and picker not in self.passers):
            following, why = picker, "kept"
        else:
            right = [(a.get("ms") or 0, p) for p, a in said.items()
                     if a.get("correct") and p in self.live() and p != picker]
            if right:
                following, why = sorted(right)[0][1], "quickest"
            else:
                following, why = self.next_picker(picker), "round"
        self.picker = None if self.over() else following
        self.pick_reason = None if self.over() else why

        played = {"section": section, "picker": picker, "made": made,
                  "took": took, "next_picker": self.picker,
                  "out": [p for p in self.order if is_out(self.letters[p])],
                  "winner": self.winner(), "over": self.over()}
        self.history.append(played)
        return played

    def withdraw(self, player):
        """Somebody left the table. Treat it as being out.

        Not removed from the order, because the order is how the pick goes
        round and rewriting it mid-game would move everybody's turn. Out is
        out, and the pick moves on if they were holding it.
        """
        if player not in self.letters:
            return False
        self.letters[player] = OUT_AT
        if self.picker == player:
            self.picker = None if self.over() else self.next_picker(player)
            self.pick_reason = None if self.over() else "round"
        return True

    def as_dict(self):
        return {"word": WORD, "picker": self.picker,
                "pick_reason": self.pick_reason,
                "standing": self.standing(), "available": self.available(),
                "spent": list(self.spent), "over": self.over(),
                "winner": self.winner(), "drawn": self.drawn(),
                "played": len(self.history)}
