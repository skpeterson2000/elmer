"""Running a net without somebody standing over it.

:mod:`elmer.netcontrol` holds what a hall is - which units are in it, what
question they are on, who is winning.  This drives it, and it is the same
split as :mod:`elmer.party` and :mod:`elmer.autoplay`: the rules stay where
they can be tested without a clock, and the clock lives here.

What starts a round is a table saying it has people at it.  That is a report
rather than a guess - check-in already carries the count, so the host knows
who is seated without asking - and it is better than a timer for the reason
any measurement beats any estimate: a timer that fires into an empty hall
starts a game nobody is playing, and one that has not fired yet holds up a
room that is ready.  A table that fills up late joins the round in progress
the same way, because the hall is asked again every tick rather than once at
the beginning.

Simulated tables are ticked from here too.  They exist so a hall can be seen
working before there is a hall - an instructor setting up an evening, a
demonstration on a bench, a screen at a club meeting with two Pis on it - and
they stand down as real units arrive, one for one.  They are flagged the whole
way to the board and nothing here hides them.
"""
import logging
import threading
import time

log = logging.getLogger("elmer")

TICK = 0.25                # how often the hall is looked at
REVEAL_SECONDS = 10.0      # how long a closed round stands before the next
BETWEEN_MIN = 2.0          # a breath after the reveal, so it does not snap

# A hall with nobody in it is not waiting, it is empty.  One table with one
# person at it is a game, which is the answer to somebody sitting alone in
# front of a screen that says "waiting to join".
READY_TABLES = 1


class Conductor:
    """Starts the hall when it is ready, and keeps it going."""

    def __init__(self, net, ask, ready_tables=READY_TABLES, rounds=None,
                 reveal=REVEAL_SECONDS):
        self.net = net
        self.ask = ask                 # callable() -> puts the next question up
        self.ready_tables = ready_tables
        self.rounds = rounds           # None means keep going
        self.reveal = reveal
        self.stop = threading.Event()
        self.thread = None
        self.played = 0
        self.state = "waiting"
        self.next_at = 0.0
        self.error = None

    def waiting_for(self):
        """What the hall is short of, in words a screen can use."""
        ready = len(self.net.ready_units())
        if ready >= self.ready_tables:
            return None
        short = self.ready_tables - ready
        return ("waiting for a table with somebody at it" if short == 1
                else f"waiting for {short} more tables")

    def _tick(self):
        net = self.net
        net.tick_simulated()

        if net.round:                       # closing a round clears it
            self.state = "asking"
            # A round is over when every table present has handed in, or the
            # grace has run out.  Waiting on a table that went off the air is
            # what the grace is for.
            if net.everyone_reported() or net.overdue():
                net.close_round()
                self.played += 1
                self.next_at = time.monotonic() + self.reveal
                self.state = "revealing"
            return

        if self.state == "revealing" and time.monotonic() < self.next_at:
            return

        if self.rounds is not None and self.played >= self.rounds:
            self.state = "finished"
            self.stop.set()
            return

        short = self.waiting_for()
        if short:
            # Not an error and not a failure - just nobody here yet.  The
            # hall is asked again every tick, so a table that fills up in a
            # minute's time starts it without anybody pressing anything.
            self.state = "waiting"
            return

        # A tournament that has run out of questions is finished, and the net
        # is the thing that knows. This asks the net rather than reading what
        # ask() returned: None is what any function returns when it simply did
        # its job and had nothing to say, so treating it as "played out" would
        # stop the hall for every caller that did not think to return
        # something - which is how it was written first, and what the tests
        # caught.
        plan = self.net.plan_state()
        if plan and plan.get("done"):
            log.info("hall: tournament played out after %d rounds", self.played)
            self.state = "finished"
            self.stop.set()
            return

        # A shootout has no fixed length: it ends when one table is left or
        # the subjects run out, and between questions it waits on whichever
        # table holds the pick - a state of its own, so the screens can say
        # whose it is rather than "asking".
        if net.shootout is not None:
            if net.shootout_over():
                log.info("hall: shootout over after %d questions", self.played)
                self.state = "finished"
                self.stop.set()
                return
            net.choose_for_simulated()
            if net.waiting_for_pick():
                if net.pick_overdue():
                    net.pass_pick()
                    return
                self.state = "picking"
                return

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
                log.exception("hall: %s", exc)
                self.stop.set()
                break
            self.stop.wait(TICK)
        if self.state != "faulted":
            self.state = "finished" if self.stop.is_set() else "stopped"

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="hall")
        self.thread.start()
        return self

    def as_dict(self):
        return {"running": bool(self.thread and self.thread.is_alive()),
                "state": self.state, "played": self.played,
                "rounds": self.rounds, "waiting_for": self.waiting_for(),
                "error": self.error}


_conductor = None
_lock = threading.Lock()


def conductor():
    with _lock:
        return _conductor


def start(net, ask, ready_tables=READY_TABLES, rounds=None,
          reveal=REVEAL_SECONDS):
    global _conductor
    with _lock:
        if _conductor is not None:
            _conductor.stop.set()
        _conductor = Conductor(net, ask, ready_tables, rounds, reveal).start()
        log.info("hall: conducting (%s rounds, %d table(s) wanted)",
                 rounds or "open-ended", ready_tables)
        return _conductor


def halt():
    global _conductor
    with _lock:
        if _conductor is not None:
            _conductor.stop.set()
            _conductor = None
            log.info("hall: stopped conducting")
            return True
        return False
