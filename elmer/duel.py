"""The duel: two operators, code that gets longer and faster, first to
miss is out.

A close play at a base - the baseman took the throw clean and the runner
copied it clean, the slide and the tag arriving together - is decided
the way the rest of CW Baseball is decided, by the code, and not by a
coin. The two go head to head. Round one, both copy the same short group
the machine sends; round two, both key it back; then a character longer
and two words a minute faster, copy again, send again, until one of them
misses. A round both miss goes to the runner, because a tie at the bag
goes to the runner. Time contracts the way attention does: each round is
a few seconds, and the rest of the room watches the exchange on the board
with the round, the length and the speed, and nothing of the text.

It is its own small game and could stand alone - a shootout for the CW
page - so it lives here rather than in :mod:`elmer.cwball`, which starts
it and reads the winner.
"""
import random
import time

from . import cw

CLEAN = 90                      # copied or keyed this clean and the round is held
START_LENGTH = 2                # characters in round one
LENGTH_EVERY = 2                # rounds between a character longer (copy, then send, then longer)
WPM_STEP = 2.0                  # faster each time it gets longer
COPY_SECONDS = 2.0              # per character, to type it after it sounds
SEND_SECONDS = 3.0              # per character, to key it
LEAST_SECONDS = 6.0
BOT_COPY = {"Listener": 0.4, "Learner": 0.55, "Operator": 0.72, "Elmer": 0.86}
BOT_SEND = {"Listener": 0.35, "Learner": 0.5, "Operator": 0.68, "Elmer": 0.82}
BOT_FADE = 0.06                 # a practice player's odds fall this much a round
LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ2345679"


def _now():
    return time.time()


def _squash(text):
    return "".join(str(text or "").upper().split())


def accuracy(want, got):
    """Characters right in place, as a percentage of the longer."""
    a, b = _squash(want), _squash(got)
    if not a:
        return 100 if not b else 0
    hits = sum(1 for i, ch in enumerate(a) if i < len(b) and b[i] == ch)
    return round(100 * hits / max(len(a), len(b)))


class Duel:
    """`a` is the runner, `b` the baseman; a round both miss is the runner's."""

    def __init__(self, a, b, names=None, base_wpm=10.0, seed=None, bots=None):
        self.a, self.b = a, b
        self.names = dict(names or {})
        self.base_wpm = float(base_wpm)
        self.rng = random.Random(seed)
        self.bots = dict(bots or {})
        self.round = 0
        self.kind = None                  # "copy" | "send"
        self.text = ""
        self.wpm = self.base_wpm
        self.groups = []
        self.timing = None
        self.deadline = _now()
        self.done = {}                    # player -> pct, this round
        self.winner = None
        self.log = []                     # [{"round", "kind", "length", "wpm", "a", "b"}]
        self._bot_at = {}
        self._new_round()

    # ------------------------------------------------------------ rounds
    def name(self, p):
        return self.names.get(p, str(p))

    def length(self):
        return START_LENGTH + (self.round - 1) // LENGTH_EVERY

    def _new_round(self):
        self.round += 1
        self.kind = "copy" if self.round % 2 == 1 else "send"
        step = (self.round - 1) // LENGTH_EVERY
        self.wpm = round(self.base_wpm + WPM_STEP * step, 1)
        if self.kind == "copy" or not self.text:
            self.text = "".join(self.rng.choice(LETTERS) for _ in range(self.length()))
        # a send round keys back what the copy round sent, so the pair is
        # one exchange: hear it, then say it
        self.groups = cw.encode(self.text)
        self.timing = cw.timing(self.wpm, self.wpm)
        n = len(self.text)
        if self.kind == "copy":
            sounds = sum(len(cw.MORSE.get(c, "")) for c in self.text) * 2.5 * self.timing["dit"] / 1000.0
            window = sounds + n * COPY_SECONDS
        else:
            window = n * SEND_SECONDS
        self.deadline = _now() + max(LEAST_SECONDS, window)
        self.done = {}
        self._bot_at = {}
        for p in (self.a, self.b):
            if p in self.bots:
                self._bot_at[p] = _now() + (self.deadline - _now()) * self.rng.uniform(0.3, 0.8)

    def over(self):
        return self.winner is not None

    # --------------------------------------------------------------- acts
    def act(self, player, answer, wpm=None):
        """A copy typed or a text keyed, from one of the two. Returns
        {"ok", "pct", "clean"} and, when the round has both, moves on."""
        if self.over():
            return {"error": "the duel is decided"}
        if player not in (self.a, self.b):
            return {"error": "not your duel"}
        if player in self.done:
            return {"error": "you have answered this round"}
        pct = accuracy(self.text, answer)
        self.done[player] = pct
        out = {"ok": True, "pct": pct, "clean": pct >= CLEAN, "round": self.round}
        self._settle()
        return out

    def _settle(self):
        if len(self.done) < 2 or self.over():
            return
        a_ok = self.done.get(self.a, 0) >= CLEAN
        b_ok = self.done.get(self.b, 0) >= CLEAN
        self.log.append({"round": self.round, "kind": self.kind, "length": len(self.text),
                         "wpm": self.wpm, "a": self.done.get(self.a, 0), "b": self.done.get(self.b, 0)})
        if a_ok and b_ok:
            self._new_round()
        elif a_ok:
            self.winner = self.a
        elif b_ok:
            self.winner = self.b
        else:
            self.winner = self.a          # a tie at the bag goes to the runner

    def tick(self, now=None):
        """Practice players act when their moment comes; the clock ends a
        round for anybody who never answered, as a miss."""
        now = _now() if now is None else now
        if self.over():
            return
        for p, at in list(self._bot_at.items()):
            if now >= at and p not in self.done:
                level = self.bots.get(p)
                odds = (BOT_COPY if self.kind == "copy" else BOT_SEND).get(level, 0.5) - BOT_FADE * (self.round - 1)
                clean = self.rng.random() < max(0.05, odds)
                self.act(p, self.text if clean else self.text[:-1] + "?")
                if self.over():
                    return
        if now >= self.deadline and not self.over():
            for p in (self.a, self.b):
                self.done.setdefault(p, 0)
            self._settle()

    # --------------------------------------------------------------- view
    def words(self):
        who = f"{self.name(self.a)} and {self.name(self.b)}"
        if self.over():
            return (f"{self.name(self.winner)} wins the duel in {len(self.log)} round"
                    f"{'s' if len(self.log) != 1 else ''}")
        what = "copy" if self.kind == "copy" else "send"
        return f"Duel, round {self.round}: {who} {what} {len(self.text)} characters at {self.wpm:g} wpm"

    def as_dict(self, player_id=None):
        you = player_id in (self.a, self.b)
        return {
            "round": self.round, "kind": self.kind, "length": len(self.text), "wpm": self.wpm,
            "a": self.a, "b": self.b, "a_name": self.name(self.a), "b_name": self.name(self.b),
            "you": you, "role": "runner" if player_id == self.a else "baseman" if player_id == self.b else None,
            # the text goes to the two only, and only to key it back: a copy
            # round is heard, never read
            "text": self.text if you and self.kind == "send" else None,
            "groups": self.groups if self.kind == "copy" else None,
            "timing": self.timing if self.kind == "copy" else None,
            "done": {str(p): (p in self.done) for p in (self.a, self.b)},
            "answered": player_id in self.done,
            "deadline_in": max(0.0, round(self.deadline - _now(), 1)),
            "winner": self.winner, "winner_name": self.name(self.winner) if self.winner is not None else None,
            "log": list(self.log), "words": self.words(),
        }
