"""Run a match on its own, once somebody has started it.

A table screen that waits for a person to press a button between every question
is fine when that person is running a club night, and tiresome when they are
the one trying to play. This drives the round loop instead: put a question up,
let the answers come in, close it when everybody is in or the clock runs out,
show the result for a moment, and go again.

It also ticks the practice opponents. They decide what they will do when the
round opens and this hands their answers in as their moments arrive, so they
arrive spread across the round the way a room of people does rather than all
in the same instant.

Nothing here decides anything about the game. It picks no questions and scores
nothing - it is handed a way to ask for the next question and calls it. The
rules stay in party.py where they can be tested without a clock.
"""
import logging
import threading
import time

log = logging.getLogger("elmer")

TICK = 0.25                # how often bots and the round clock are checked
REVEAL_SECONDS = 8.0       # how long the result stands before the next question
BETWEEN_MIN = 1.5          # a breath after the reveal, so it does not snap


class Director:
    """Drives one room's rounds until told to stop."""

    def __init__(self, room, ask, rounds=None, reveal=REVEAL_SECONDS):
        self.room = room
        self.ask = ask                 # callable() -> starts the next round
        self.rounds = rounds           # None means keep going
        self.reveal = reveal
        self.stop = threading.Event()
        self.thread = None
        self.played = 0
        self.state = "starting"
        self.next_at = 0.0
        self.error = None

    def _tick(self):
        room = self.room
        room.run_bots()
        rnd = room.round

        if rnd and not rnd.closed:
            self.state = "asking"
            # A round is over when everyone present has answered, or the clock
            # has run out. Waiting for a player who has wandered off is what
            # the clock is for.
            if room.everyone_answered() or rnd.expired():
                room.close_round()
                self.played += 1
                self.next_at = time.monotonic() + self.reveal
                self.state = "revealing"
            return

        if rnd and rnd.closed:
            if time.monotonic() < self.next_at:
                self.state = "revealing"
                return

        if self.rounds is not None and self.played >= self.rounds:
            self.state = "finished"
            self.stop.set()
            return

        # Time for the next question.
        self.state = "asking"
        self.ask()
        self.next_at = time.monotonic() + BETWEEN_MIN

    def run(self):
        while not self.stop.is_set():
            try:
                self._tick()
            except Exception as exc:            # pragma: no cover
                self.error = repr(exc)
                self.state = "faulted"
                log.exception("autoplay: %s", exc)
                self.stop.set()
                break
            self.stop.wait(TICK)
        if self.state != "faulted":
            self.state = "finished" if self.stop.is_set() else "stopped"

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="autoplay")
        self.thread.start()
        return self

    def as_dict(self):
        return {"running": bool(self.thread and self.thread.is_alive()),
                "state": self.state, "played": self.played,
                "rounds": self.rounds, "error": self.error}


_director = None
_lock = threading.Lock()


def director():
    with _lock:
        return _director


def start(room, ask, rounds=None, reveal=REVEAL_SECONDS):
    global _director
    with _lock:
        if _director is not None:
            _director.stop.set()
        _director = Director(room, ask, rounds, reveal).start()
        log.info("autoplay: match started (%s rounds)", rounds or "open-ended")
        return _director


def stop():
    global _director
    with _lock:
        if _director is not None:
            _director.stop.set()
        _director = None
