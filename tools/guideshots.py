#!/usr/bin/env python3
"""Figures for the User's Guide, taken from the running program.

    python3 tools/guideshots.py             # every figure
    python3 tools/guideshots.py cw          # one chapter's
    python3 tools/guideshots.py --list      # what there is

The guide has eighteen pictures across eighteen thousand words, and the
chapters a newcomer needs most are the thinnest of all: CW is fourteen
hundred words with no subheadings and one screenshot at the very bottom,
which is the same thing as none.

Part of the reason is that every one of those pictures was taken by hand.
A figure that costs an afternoon is a figure nobody adds, and one taken once
goes quietly out of date as the program moves under it. So they are taken
from the program instead, by this, and can be taken again after any change.

Two things matter about the result. A figure is cropped to the thing being
explained rather than being a picture of a whole window with the thing
somewhere inside it - that is what `where` is for. And the state is set up
first, so the figure shows a session in progress or a record with some
history on it, rather than an empty page on a unit nobody has used.
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

SHOTS = ROOT / "docs" / "screenshots" / "guide"

# Which profile the figures are taken as. The first one, unless told
# otherwise: a unit with several sends an unidentified browser to /who.
USER = int(os.environ.get("GUIDESHOT_USER") or 1)


# Each figure: where it goes, which page, what to crop to, and what to do to
# the page first. `setup` is JavaScript run before the shot, for the state a
# picture needs - a lesson opened, a panel unfolded, an answer typed.
FIGURES = [
    # -- CW: the chapter with the most words and the fewest pictures.
    # The CW page keeps each mode in a pane and hides the rest, so the figure
    # presses the button first - the same press a person makes, rather than
    # reaching for a function that the page does not put in global scope. A hidden panel measures zero and this
    # tool reports it missing rather than writing out a blank picture.
    {"name": "cw-today", "chapter": "cw", "url": "/cw",
     "where": "#cw-today", "settle": 3.0,
     "setup": "document.querySelector('#cw-modes [data-mode=today]').click()",
     "why": "The session the record has decided on, with its clock and its parts."},
    {"name": "cw-chart", "chapter": "cw", "url": "/cw",
     "where": "#cw-chart", "settle": 3.0,
     "setup": "document.querySelector('#cw-modes [data-mode=chart]').click()",
     "why": "The whole code as a wall chart, which is what a learner looks at."},
    {"name": "cw-learn", "chapter": "cw", "url": "/cw",
     "where": "#cw-learn", "settle": 3.0,
     "setup": "document.querySelector('#cw-modes [data-mode=learn]').click()",
     "why": "Meeting a character: the shape drawn as it sounds, then its name."},
    {"name": "cw-qualify", "chapter": "cw", "url": "/cw",
     "where": "#cw-qualify", "settle": 3.0,
     "setup": "document.querySelector('#cw-modes [data-mode=qualify]').click();"
              " document.getElementById('cw-q-wpm').value = 25;"
              " document.getElementById('cw-q-wpm').dispatchEvent(new Event('input'))",
     "why": "The qualifying run, and what the speed you name actually means."},
    {"name": "cw-rating", "chapter": "cw", "url": "/cw",
     "where": "#cw-rating", "settle": 3.0,
     "setup": "document.querySelector('#cw-modes [data-mode=rating]').click()",
     "why": "The two numbers that move - the speed copied and the speed sent."},
    # -- The band plan: privileges, which is the other wall of prose.
    {"name": "bandplan-strip", "chapter": "bandplan", "url": "/bandplan",
     "where": ".bp-band", "settle": 3.0,
     "why": "One band's strip: the segments, the modes, and where this class may go."},
    # -- Studying: the drill, and what an explanation looks like.
    {"name": "study-explain", "chapter": "study", "url": "/study/tech2026",
     "where": ".panel", "settle": 3.0,
     "why": "A question with its explanation open, which is the whole of the drill."},
]


def serve(port):
    """ELMER, on a port of its own, with the operator's own state."""
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\n"
         "from elmer.app import app\n"
         "app.run(host='127.0.0.1', port=%d, threaded=True, use_reloader=False)"
         % (str(ROOT), port)],
        env=dict(os.environ), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(150):
        try:
            urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port, timeout=1).close()
            return proc
        except Exception:
            time.sleep(0.2)
    proc.terminate()
    raise SystemExit("ELMER did not come up on port %d" % port)


def take(figure, port, browser):
    """One figure. Returns what happened, for the caller to print."""
    out = SHOTS / (figure["name"] + ".png")
    url = "http://127.0.0.1:%d%s" % (port, figure["url"])
    setup = figure.get("setup") or ""
    # The setup runs, then the page is given a moment to settle into it before
    # the shutter. Returning the selector's own size tells us whether there was
    # anything there to photograph.
    # Where it actually landed is reported too: a unit with more than one
    # profile sends a browser with no cookie to /who, and every figure then
    # quietly photographs the wrong page. Better to say so.
    js = ("(async () => { if (location.pathname.indexOf('/who') === 0)"
          " return 'AT /who - this unit has more than one profile';"
          " %s; await new Promise(r => setTimeout(r, 900));"
          " const el = document.querySelector(%r);"
          " return el ? Math.round(el.getBoundingClientRect().width) : 0; })()"
          % (setup, figure["where"]))
    try:
        width = browser.evaluate(url, js, width=1280, height=900,
                                 settle=figure.get("settle", 2.5),
                                 out=str(out), clip=figure["where"],
                                 # Say who we are, or a unit with two profiles
                                 # answers /who and the figure is of that.
                                 cookies={"elmer_user": str(USER)})
    except Exception as exc:
        return "failed  %-18s %s" % (figure["name"], exc)
    if isinstance(width, str):
        # The setup threw. Said in full, because the usual cause is that the
        # page moved and the figure is now asking for something that is gone.
        out.unlink(missing_ok=True)
        return "ERROR   %-18s %s" % (figure["name"], width[:120])
    if not width:
        # The shot was taken before the crop could be worked out, so there is a
        # picture of the whole window sitting there under a name that promises
        # a panel. Left behind, it goes in the guide and nobody notices until a
        # reader does. Take it away and say what happened.
        out.unlink(missing_ok=True)
        return ("MISSING %-18s nothing matched %s on %s - hidden, or the page "
                "has moved (no file written)"
                % (figure["name"], figure["where"], figure["url"]))
    size = out.stat().st_size if out.is_file() else 0
    return "ok      %-18s %s  (%d px wide, %d KB)" % (
        figure["name"], figure["url"], width, size // 1024)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("chapter", nargs="?", help="only this chapter's figures")
    ap.add_argument("--list", action="store_true", help="what there is, and why")
    args = ap.parse_args()

    wanted = [f for f in FIGURES if not args.chapter or f["chapter"] == args.chapter]
    if args.list:
        for f in FIGURES:
            print("%-10s %-18s %-22s %s" % (f["chapter"], f["name"], f["url"], f["why"]))
        return 0
    if not wanted:
        print("no figures for %r - try --list" % args.chapter)
        return 1

    import _browser
    if not _browser.available():
        print("this needs chromium")
        return 1
    SHOTS.mkdir(parents=True, exist_ok=True)
    port = _browser._free_port()
    server = serve(port)
    try:
        for figure in wanted:
            print(take(figure, port, _browser), flush=True)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
