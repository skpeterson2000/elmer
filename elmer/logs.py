"""Logging setup for ELMER.

Everything lands in two places: the console you started the server from, and
``data/elmer.log`` (rotated), so a problem that happened an hour ago is still
there to read.  Request lines carry the client address, which is the fastest
way to tell "my browser never reached the server" apart from "it reached it and
something broke".

Three things keep the log readable on a hall night, when twenty tables and
their phones poll this unit every second or two:

**Polls are counted, not written.** A successful, quick GET to one of the
state-polling endpoints is a heartbeat, and eighty thousand heartbeats an
hour rotate the evening's real lines out of existence - the old log held
about forty minutes of a hall. They are tallied instead, and one line every
ten minutes says how many there were, from how many clients, and how slow
the slowest was. Anything that fails or takes long is still written as
itself.

**Repeats are collapsed.** A table pointed at a net that is not running asks
every fifteen seconds and is told 404 every fifteen seconds, all night. The
first is written; the rest of the minute is one line saying how many.

**A fault gets a reference.** An unhandled exception is logged with a short
tag - ``ref e-3f9a`` - and the same tag is put on the page and in the JSON,
so "it said e-3f9a at about nine" finds the traceback in one grep.
"""
import logging
import logging.handlers
import os
import secrets
import threading
import time
import traceback

from . import db, startup
from pathlib import Path
from . import paths

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = paths.STATE / "elmer.log"

FMT = "%(asctime)s %(levelname)-7s %(name)-12s %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


class ColourFormatter(logging.Formatter):
    """Console formatter - colours only when stderr is a terminal."""

    COLOURS = {"DEBUG": "\033[36m", "INFO": "\033[32m", "WARNING": "\033[33m",
               "ERROR": "\033[31m", "CRITICAL": "\033[1;31m"}
    RESET = "\033[0m"

    def __init__(self, colour):
        super().__init__(FMT, DATEFMT)
        self.colour = colour

    def format(self, record):
        text = super().format(record)
        if not self.colour:
            return text
        return f"{self.COLOURS.get(record.levelname, '')}{text}{self.RESET}"


def setup(level="INFO", to_file=True):
    """Configure the root logger. Returns the path being written to, if any."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    console = logging.StreamHandler()
    console.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    console.setFormatter(ColourFormatter(os.isatty(2)))
    root.addHandler(console)

    if not to_file:
        return None

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Five files of five megabytes: a hamfest weekend, with the polls
    # counted rather than written, comes to a fraction of it.
    rotating = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    rotating.setLevel(logging.DEBUG)          # the file always keeps everything
    rotating.setFormatter(logging.Formatter(FMT, DATEFMT))
    root.addHandler(rotating)

    # Werkzeug logs its own request lines; ours carry more, so silence its
    # duplicates but keep its warnings.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    install_thread_hook()
    return LOG_PATH


def install_thread_hook():
    """A thread that dies takes its traceback to the log, not to stderr.

    The conductor, the hall bridge, the discovery listener and the GPS reader
    all run in threads. An exception that escapes one used to print to a
    console nobody was watching and leave the feature silently stopped; now
    it is an ERROR line naming the thread, which the problem report picks up.
    """
    def hook(args):
        if args.exc_type is SystemExit:
            return
        logging.getLogger("elmer").error(
            "THREAD %s died: %s\n%s", args.thread.name if args.thread else "?",
            args.exc_value, "".join(traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback)))
    threading.excepthook = hook


# Endpoints that screens and phones poll to stay current. A quick, successful
# GET to one of these is a heartbeat and is counted rather than written.
POLL_SUFFIXES = ("/state", "/auto-state", "/board", "/boards", "/peers",
                 "/health", "/api/update", "/api/gps", "/api/party/net",
                 "/api/net/checkin", "/api/discovery")
POLL_SLOW_MS = 300            # slower than this is worth a line of its own
SUMMARY_EVERY = 600           # seconds between poll summaries
REPEAT_WINDOW = 60            # seconds over which identical lines collapse


class _Quiet:
    """The tallies behind the two silences, and when to speak."""

    def __init__(self):
        self.lock = threading.Lock()
        self.polls = 0
        self.clients = set()
        self.slowest = 0.0
        self.slowest_path = ""
        self.since = time.time()
        self.repeats = {}          # key -> [first_at, count]

    def poll(self, addr, path, elapsed):
        """Count one heartbeat; return a summary line if it is time."""
        with self.lock:
            self.polls += 1
            self.clients.add(addr)
            if elapsed > self.slowest:
                self.slowest, self.slowest_path = elapsed, path
            if time.time() - self.since < SUMMARY_EVERY:
                return None
            line = (f"{self.polls} polls in the last {round((time.time() - self.since) / 60)} min "
                    f"from {len(self.clients)} client{'s' if len(self.clients) != 1 else ''}, "
                    f"slowest {self.slowest:.0f}ms ({self.slowest_path})")
            self.polls, self.clients, self.slowest, self.slowest_path = 0, set(), 0.0, ""
            self.since = time.time()
            return line

    def repeat(self, key):
        """0 to write the line; otherwise how many times it has been swallowed
        so far, or -N when the minute is up and N is the total to report."""
        now = time.time()
        with self.lock:
            had = self.repeats.get(key)
            if had is None or now - had[0] > REPEAT_WINDOW:
                if had and had[1] > 0:
                    self.repeats[key] = [now, 0]
                    return -had[1]
                self.repeats[key] = [now, 0]
                return 0
            had[1] += 1
            return had[1]


quiet = _Quiet()


def is_poll(path):
    base = path.split("?", 1)[0].rstrip("/")
    return any(base.endswith(sfx) for sfx in POLL_SUFFIXES)


def install_request_logging(app):
    """Log every request with client address, status and duration."""
    log = logging.getLogger("http")

    @app.before_request
    def _start_timer():
        from flask import g
        g._started = time.perf_counter()

    @app.after_request
    def _log_request(response):
        from flask import g, request
        elapsed = (time.perf_counter() - getattr(g, "_started", time.perf_counter())) * 1000
        status = response.status_code
        path = request.full_path.rstrip("?")
        agent = (request.user_agent.string or "-")[:60]
        own = agent.startswith("ELMER/")       # a table, a board, a bridge
        if status < 400 and elapsed < POLL_SLOW_MS and is_poll(path) \
                and request.method in ("GET", "POST"):
            summary = quiet.poll(request.remote_addr, path.split("?", 1)[0], elapsed)
            if summary:
                log.info("quiet traffic: %s", summary)
        else:
            # A refusal ELMER's own components asked for and handle - a bridge
            # told there is no net - is their normal, not a warning; a browser
            # being told 404 is worth a look.
            level = (logging.WARNING if status >= 400 and not (own and status < 500)
                     else logging.INFO)
            key = (request.remote_addr, request.method, path.split("?", 1)[0], status)
            seen = quiet.repeat(key) if status >= 400 else 0
            if seen < 0:
                log.log(level, "%s %s %s -> %s  (and %d more like it in the last minute)",
                        request.remote_addr, request.method, path.split("?", 1)[0],
                        status, -seen)
            if seen <= 0:
                log.log(level, "%s %s %s -> %s in %.0fms  [%s]",
                        request.remote_addr, request.method, path, status, elapsed, agent)
        # The first page out the door is when this unit became usable, and
        # this is the one place that already knows a page was served.  A
        # static file is not a page - see elmer.startup.
        if startup.waiting() and request.endpoint not in (None, "static") \
                and response.status_code < 400:
            try:
                startup.note_first_page(db.connect(), elapsed / 1000.0)
            except Exception:               # never break a response over it
                pass
        return response

    @app.errorhandler(Exception)
    def _log_exception(exc):
        from flask import jsonify, request
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return exc                      # 404s and friends are already logged
        ref = "e-" + secrets.token_hex(2)
        log.error("UNHANDLED %s on %s %s  ref %s\n%s", type(exc).__name__,
                  request.method, request.path, ref, traceback.format_exc())
        if request.path.startswith("/api/"):
            body = jsonify({"error": "ELMER hit an error", "ref": ref,
                            "where": f"{request.method} {request.path}"})
            return body, 500
        return (f"<h1>ELMER hit an error</h1><p>Reference <code>{ref}</code> - "
                f"the details are in <code>data/elmer.log</code> under that "
                f"reference.</p>", 500)
