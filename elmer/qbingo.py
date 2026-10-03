"""Q-code bingo: the table keys a Q signal, the phones mark what it meant.

A club-night game for the Q signals. Each player's phone holds a card of
meanings - four by four, sixteen of the Q signals ELMER knows - and the
table screen keys a code by sound alone, with nothing written. Somebody who
hears QRS marks "send slower". A line of four - a row, a column or a
diagonal - and they call it, and the call is checked against what was
actually keyed: every square on the line marked, and every one of them
called. A square marked for a code that was never called does not count,
and a call that does not stand is said, not punished; the game goes on.

The code just called is written on the table only once the next one has
been keyed, with its meaning - so the room listens first and learns after.
Everything here is the game's arithmetic; the room, the screens and the
routes are party.py's and app.py's.
"""
import random

from . import cw

SIZE = 4                                   # four by four: sixteen of the Q signals
LINES = ([[r * SIZE + c for c in range(SIZE)] for r in range(SIZE)] +          # rows
         [[r * SIZE + c for r in range(SIZE)] for c in range(SIZE)] +          # columns
         [[i * SIZE + i for i in range(SIZE)], [i * SIZE + SIZE - 1 - i for i in range(SIZE)]])
DEFAULT_WPM = 15
DEFAULT_EVERY_S = 20                       # seconds between calls, when the table calls on its own


class QBingo:
    """One game: cards for the players, the calls in order, the marks, the winner."""

    def __init__(self, players, rng=None, wpm=DEFAULT_WPM, every_s=DEFAULT_EVERY_S):
        self.rng = rng or random.Random()
        self.wpm = max(5, min(30, int(wpm)))
        self.every_s = max(8, min(90, int(every_s)))
        codes = list(cw.Q_SIGNALS)
        self.order = self.rng.sample(codes, len(codes))      # the calls, decided at the start
        self.called = []
        self.cards = {}                                      # player id -> sixteen codes
        self.marks = {}                                      # player id -> set of squares
        self.names = {}
        self.winner = None
        self.claims = []                                     # every call of "bingo", stood or not
        for pid, name in players:
            self.seat(pid, name)

    def seat(self, pid, name):
        """A card for a player - for one who sits down mid-game too."""
        if pid in self.cards:
            return
        self.cards[pid] = self.rng.sample(list(cw.Q_SIGNALS), SIZE * SIZE)
        self.marks[pid] = set()
        self.names[pid] = name

    def withdraw(self, pid):
        self.cards.pop(pid, None)
        self.marks.pop(pid, None)

    def over(self):
        """Over when somebody has won. Every code having been keyed is not the
        end: the calls stop, and the last line can still be called."""
        return self.winner is not None

    def all_called(self):
        return len(self.called) >= len(self.order)

    def call(self):
        """Key the next code. Returns it, or None when there are none left or
        the game is won."""
        if self.over() or self.all_called():
            return None
        code = self.order[len(self.called)]
        self.called.append(code)
        return code

    def mark(self, pid, square, on=True):
        """Mark or unmark a square on a player's card. Returns (ok, why)."""
        if pid not in self.cards:
            return False, "you have no card in this game"
        if self.winner is not None:
            return False, "the game is over"
        try:
            square = int(square)
        except (TypeError, ValueError):
            return False, "not a square"
        if not 0 <= square < SIZE * SIZE:
            return False, "not a square"
        (self.marks[pid].add if on else self.marks[pid].discard)(square)
        return True, None

    def line_for(self, pid):
        """The first line on a player's card that is marked and all called."""
        card, marked, called = self.cards.get(pid), self.marks.get(pid, set()), set(self.called)
        if not card:
            return None
        for line in LINES:
            if all(sq in marked and card[sq] in called for sq in line):
                return line
        return None

    def claim(self, pid):
        """A player calls bingo. Returns (won, words)."""
        if pid not in self.cards:
            return False, "you have no card in this game"
        if self.winner is not None:
            return False, "%s has already won" % self.names.get(self.winner, "somebody")
        line = self.line_for(pid)
        if line is None:
            # Which marked squares were never called - the useful thing to know.
            card, called = self.cards[pid], set(self.called)
            wrong = [card[sq] for sq in sorted(self.marks[pid]) if card[sq] not in called]
            self.claims.append({"player": pid, "stood": False})
            if wrong:
                return False, ("not yet - %s %s not been called" %
                               (", ".join(cw.Q_SIGNALS[c] for c in wrong), "has" if len(wrong) == 1 else "have"))
            return False, "not yet - no line of four is marked"
        self.winner = pid
        self.claims.append({"player": pid, "stood": True, "line": line})
        return True, "bingo - %s" % ", ".join(self.cards[pid][sq] for sq in line)

    def sound(self):
        """What the table keys for the latest call: the groups and timing
        morse.js plays, Farnsworth-free at the game's speed."""
        if not self.called:
            return None
        return {"n": len(self.called), "groups": cw.encode(self.called[-1]), "timing": cw.timing(self.wpm, self.wpm)}

    def view(self, pid=None):
        """For the screens. The table never sees the code being keyed now -
        only the ones before it, with their meanings. A phone sees its own
        card, as meanings, and its marks."""
        out = {"on": True, "calls": len(self.called), "of": len(self.order), "wpm": self.wpm,
               "every_s": self.every_s, "over": self.over(), "all_called": self.all_called(),
               "earlier": [{"code": c, "meaning": cw.Q_SIGNALS[c]} for c in self.called[:-1]],
               "sound": self.sound(),
               "winner": self.winner, "winner_name": self.names.get(self.winner) if self.winner is not None else None,
               "players": len(self.cards)}
        if (self.over() or self.all_called()) and self.called:
            out["last"] = {"code": self.called[-1], "meaning": cw.Q_SIGNALS[self.called[-1]]}
        if self.winner is not None:
            line = self.line_for(self.winner) or []
            out["winning"] = [{"code": self.cards[self.winner][sq], "meaning": cw.Q_SIGNALS[self.cards[self.winner][sq]]}
                              for sq in line]
        if pid is not None and pid in self.cards:
            out["card"] = [cw.Q_SIGNALS[c] for c in self.cards[pid]]
            out["marked"] = sorted(self.marks[pid])
            if self.over():
                out["card_codes"] = list(self.cards[pid])
        return out
