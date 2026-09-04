"""Logging setup for ELMER.

Everything lands in two places: the console you started the server from, and
``data/elmer.log`` (rotated), so a problem that happened an hour ago is still
there to read.  Request lines carry the client address, which is the fastest
way to tell "my browser never reached the server" apart from "it reached it and
something broke".
"""
import logging
import logging.handlers
import os
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "data" / "elmer.log"

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
    rotating = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    rotating.setLevel(logging.DEBUG)          # the file always keeps everything
    rotating.setFormatter(logging.Formatter(FMT, DATEFMT))
    root.addHandler(rotating)

    # Werkzeug logs its own request lines; ours carry more, so silence its
    # duplicates but keep its warnings.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    return LOG_PATH


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
        level = logging.WARNING if response.status_code >= 400 else logging.INFO
        log.log(level, "%s %s %s -> %s in %.0fms  [%s]",
                request.remote_addr, request.method, request.full_path.rstrip("?"),
                response.status_code, elapsed,
                (request.user_agent.string or "-")[:60])
        return response

    @app.errorhandler(Exception)
    def _log_exception(exc):
        from flask import request
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return exc                      # 404s and friends are already logged
        log.error("UNHANDLED %s on %s %s\n%s", type(exc).__name__,
                  request.method, request.path, traceback.format_exc())
        return ("<h1>ELMER hit an error</h1><p>The details are in "
                "<code>data/elmer.log</code>.</p>", 500)
