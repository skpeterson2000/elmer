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

The first question after a pause gets a run-up.  A hall that has been in
intermission for ten minutes and then has a question on every screen in the
same instant has handed the round to whoever happened to be looking, and the
rest will say, rightly, that their time was taken from them.  So the
conductor puts five seconds on every screen first - "Get ready", then three,
two, one - and asks on nought.  The same five seconds whether the host
pressed Play or the programme's clock ran out, because the people in the
room cannot tell which it was and should not have to.

The programme keeps its own time too.  A step with minutes on it used to be
a note for the host, who pressed Next when it felt like ten minutes; with a
clock counting down in the corner of every screen it has to mean what it
says, so the timekeeper here moves the programme on when a timed step is
up, and hands over from a game step when its rounds are played.  Steps with
no natural end - an announcement, the certificates, thanks - still wait for
the host, and the host's own buttons work throughout.
"""
import logging
import threading
import time

log = logging.getLogger("elmer")

TICK = 0.25                # how often the hall is looked at
REVEAL_SECONDS = 10.0      # how long a closed round stands before the next
BETWEEN_MIN = 2.0          # a breath after the reveal, so it does not snap
# The run-up before the first question of a conducting: "Get ready" until
# three seconds are left, then three, two, one.  The screens draw the words
# from what is left; this is only how long it is.
LEAD_IN = 5.0
# What the host has set it to on this unit, if they have: "Playing in 30 s"
# is the same run-up made longer, so the room gets a clock on every screen
# instead of a question from nowhere. Set from the application, which is
# where the setting is kept; this module keeps no database of its own.
_default_lead_in = LEAD_IN


def set_default_lead_in(seconds):
    """The run-up every conducting gets unless told otherwise; 3 s to 10 min."""
    global _default_lead_in
    _default_lead_in = max(3.0, min(600.0, float(seconds)))
    return _default_lead_in


def default_lead_in():
    return _default_lead_in

# A hall with nobody in it is not waiting, it is empty.  One table with one
# person at it is a game, which is the answer to somebody sitting alone in
# front of a screen that says "waiting to join".
READY_TABLES = 1


class Conductor:
    """Starts the hall when it is ready, and keeps it going."""

    def __init__(self, net, ask, ready_tables=READY_TABLES, rounds=None,
                 reveal=REVEAL_SECONDS, lead_in=LEAD_IN):
        self.net = net
        self.ask = ask                 # callable() -> puts the next question up
        self.ready_tables = ready_tables
        self.rounds = rounds           # None means keep going
        self.reveal = reveal
        self.lead_in = float(lead_in or 0.0)
        self.stop = threading.Event()
        self.thread = None
        self.played = 0
        self.state = "waiting"
        self.next_at = 0.0
        self.error = None
        # The run-up happens once, before this conducting's first question.
        # Every Play press and every programme step makes a new conductor,
        # so "first" is the first after whatever pause there was.
        self._led_in = self.lead_in <= 0
        self._starting = False

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
        if net.cutthroat is not None or net.golf is not None:
            if net.game_over():
                log.info("hall: %s over after %d questions", net.mode, self.played)
                self.state = "finished"
                self.stop.set()
                return
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

        if not self._led_in:
            # Everything that could hold the question up has cleared - the
            # tables are seated, the pick is made - so the run-up starts now
            # and the question follows it. Started from the net so that all
            # three kinds of screen count the same seconds.
            if not self._starting:
                self._starting = True
                self.state = "starting"
                net.begin_lead_in(self.lead_in)
                return
            if (net.lead_in_remaining() or 0.0) > 0:
                return
            self._led_in = True

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
        if self._starting and not self._led_in:
            # Stopped in the run-up - the host called an intermission - so the
            # screens are not left counting down to a question that will not
            # come.
            self.net.cancel_lead_in()
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
                "lead_in": (self.net.lead_in_remaining()
                            if self.state == "starting" else None),
                "error": self.error}


class Timekeeper:
    """Walks the programme's timed steps, and hands over from finished games.

    `advance(index)` is the application's: it moves the programme on from
    step `index` and makes the new step happen - the same thing the host's
    Next button does.  Given the index so that a press and a tick landing
    together cannot skip a step between them.
    """

    def __init__(self, net, advance, lead_in=LEAD_IN, tick=0.5):
        self.net = net
        self.advance = advance
        self.lead_in = float(lead_in or 0.0)
        self.tick = tick
        self.stop = threading.Event()
        self.thread = None
        self._handed = None            # the finished conductor already handed over
        self.error = None

    def due(self, now=None):
        """The index of the step to move on from, or None."""
        show = self.net.show
        cur = show.current_step()
        if cur is None:
            return None
        index = show.step
        # A timed step - an intermission or a study spell with minutes on it
        # - is up when its clock is, less the run-up where a game follows.
        if show.step_due(now, lead=self.lead_in):
            return index
        # A game step is over when the rounds are played or the shootout is
        # won; the conductor says so and then sits there.  Once per
        # conductor: a finished one stays finished, and the same programme
        # walked twice in an evening makes a new one each time.
        if cur.get("kind") in ("rounds", "shootout"):
            live = conductor()
            if (live is not None and live.state == "finished"
                    and live is not self._handed):
                return index
        return None

    def _tick(self, now=None):
        index = self.due(now)
        if index is None:
            return False
        cur = self.net.show.current_step() or {}
        if cur.get("kind") in ("rounds", "shootout"):
            self._handed = conductor()
        log.info("programme: step %d (%s) is up - moving on", index + 1,
                 cur.get("label") or cur.get("kind") or "?")
        self.advance(index)
        return True

    def run(self):
        while not self.stop.is_set():
            try:
                self._tick()
            except Exception as exc:            # pragma: no cover
                self.error = repr(exc)
                log.exception("programme: %s", exc)
            self.stop.wait(self.tick)

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="programme")
        self.thread.start()
        return self


_conductor = None
_timekeeper = None
_lock = threading.Lock()


def conductor():
    with _lock:
        return _conductor


def start(net, ask, ready_tables=READY_TABLES, rounds=None,
          reveal=REVEAL_SECONDS, lead_in=None):
    global _conductor
    if lead_in is None:
        lead_in = _default_lead_in
    with _lock:
        if _conductor is not None:
            _conductor.stop.set()
        _conductor = Conductor(net, ask, ready_tables, rounds, reveal,
                               lead_in).start()
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


def timekeeper():
    with _lock:
        return _timekeeper


def keep_time(net, advance, lead_in=None):
    """Start walking this net's programme by the clock."""
    global _timekeeper
    with _lock:
        if _timekeeper is not None:
            _timekeeper.stop.set()
        _timekeeper = Timekeeper(net, advance, lead_in if lead_in is not None else _default_lead_in).start()
        return _timekeeper


def release_time():
    global _timekeeper
    with _lock:
        if _timekeeper is not None:
            _timekeeper.stop.set()
            _timekeeper = None
            return True
        return False
