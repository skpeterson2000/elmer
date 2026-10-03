#!/usr/bin/env python3
"""Figures for the User's Guide, taken from the running program.

    python3 tools/guideshots.py             # every figure
    python3 tools/guideshots.py cw          # one chapter's
    python3 tools/guideshots.py --list      # what there is

The guide is eighteen thousand words, and the chapters a newcomer needs most
used to be the thinnest of all: CW was fourteen hundred words with no
subheadings and one screenshot at the very bottom, which is the same thing
as none. It is sectioned and illustrated now, and it was this that made
that cheap enough to do.

Part of the reason it was bare is that every picture was taken by hand.
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
# A figure marked "qth" - the reach map, band conditions, the Lab's hop -
# shows a station that has one, and the first profile need not.
REACH_USER = int(os.environ.get("GUIDESHOT_REACH_USER") or 2)


# Each figure: where it goes, which page, what to crop to, and what to do to
# the page first. `setup` is JavaScript run before the shot, for the state a
# picture needs - a lesson opened, a panel unfolded, an answer typed.
FIGURES = [
    # -- CW: the chapter with the most words in it.
    # The CW page keeps each mode in a pane and hides the rest, so the figure
    # presses the button first - the same press a person makes, rather than
    # reaching for a function the page does not put in global scope. A hidden
    # panel measures zero, and this tool reports it missing rather than
    # writing out a blank picture.
    # The mode is still called `today` in the markup; the button it draws says
    # Next session, which is the word the guide uses.
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
    # (The band's strip is a drawn figure now - tools/guidefigures.py, band-strip.)
    # -- Studying: the drill, and what an explanation looks like.
    {"name": "study-explain", "chapter": "study", "url": "/study/tech2026",
     "where": ".panel", "settle": 3.0,
     "why": "A question with its explanation open, which is the whole of the drill."},
    # -- The Library: the card catalogue, every book on the table or the
    # shelf. Take it on a unit with at least one book on each - the
    # operator's own manuals are in this picture, so a scratch ELMER_STATE
    # is the place to take it.
    # -- Band conditions and the Lab: cropped to what the guide talks about,
    # where they used to be the whole window.
    {"name": "propagation", "chapter": "propagation", "url": "/propagation", "qth": True,
     "region": ["#p-verdict", "#p-stats", "#p-stats + .grid"], "settle": 5.0,
     "why": "The verdict, the numbers and the wall chart."},
    {"name": "lab", "chapter": "lab", "url": "/lab", "qth": True,
     "where": "#pane-skip", "settle": 4.0,
     "why": "The ionospheric hop: the layer, the rays that come back and the skip zone."},
    # -- The reach map. Needs a profile with a QTH; GUIDESHOT_REACH_USER
    # says which (the default is 2, the bench unit's). The parks on it are
    # the real POTA feed, sampled when the server starts - see serve().
    {"name": "reach", "chapter": "bandplan", "url": "/bandplan#20m", "qth": True,
     "region": ["#bp-reach > div:first-child", "#bp-reach-stage", "#bp-spots-line"], "settle": 3.0,
     "setup": "for (let i = 0; i < 90 && !(window.bpReachFor && !bpReachFor.spots_only && bpPlace); i++)"
              " await new Promise(r => setTimeout(r, 500)); await new Promise(r => setTimeout(r, 2500))",
     "why": "Where 20 m reaches from here, now, with the parks on the air."},
    {"name": "reach-6m", "chapter": "bandplan", "url": "/bandplan#6m", "qth": True,
     "region": ["#bp-reach > div:first-child", "#bp-reach-stage", "#bp-reach-spotsonly"], "settle": 3.0,
     "setup": "for (let i = 0; i < 60 && !(window.bpReachFor && bpReachFor.spots_only && bpPlace); i++)"
              " await new Promise(r => setTimeout(r, 500)); await new Promise(r => setTimeout(r, 2500))",
     "why": "6 m: the map with no forecast, the spots and why."},
    # -- Tools: the VNA's two charts, the calibration drill half done, and
    # the terminator's calculator.
    {"name": "tools-vna", "chapter": "tools", "url": "/tools", "where": "#gs-vna", "settle": 3.0,
     "setup": "for (let i = 0; i < 20 && !window.vnLast; i++) await new Promise(r => setTimeout(r, 300));"
              " document.getElementById('vn-chart').parentElement.id = 'gs-vna'",
     "why": "The SWR chart and the Smith chart of the same sweep, side by side."},
    {"name": "tools-calibrate", "chapter": "tools", "url": "/tools", "where": "#gs-cal", "settle": 2.0,
     "setup": "vnCtlEnable(true); vnCalMarks({has: false, measured: ['open', 'short']});"
              " document.querySelector('[data-vna=cal-step][data-value=open]').parentElement.id = 'gs-cal'",
     "why": "A V2 calibration in progress: OPEN and SHORT measured, LOAD and DONE to go."},
    {"name": "tools-terminator", "chapter": "tools", "url": "/tools", "where": "#gs-term", "settle": 2.0,
     "setup": "document.querySelector('[data-tab=meter]').click();"
              " document.getElementById('bt-out').closest('.bench-card').querySelector('.bench-calc').id = 'gs-term'",
     "why": "The terminator calculator: banks of identical resistors for 600 ohms at 100 W."},
    # -- Parks and summits: who is on the air now, from the real feed.
    {"name": "pota-onair", "chapter": "activations", "url": "/activations", "where": "#ac-live", "settle": 3.0,
     "setup": "for (let i = 0; i < 20 && !document.querySelector('#ac-live-bands a, #ac-live-bands span');"
              " i++) await new Promise(r => setTimeout(r, 300))",
     "why": "On the air now: the parks being activated, by band, each a way into the map."},
    {"name": "library", "chapter": "library", "url": "/library",
     "where": "#lib-catalogue", "settle": 4.0,
     "why": "The card catalogue: every book, where it is, and whether it may be taken away."},
]


def serve(port):
    """ELMER, on a port of its own, with the operator's own state."""
    proc = subprocess.Popen(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, %r)\n"
         "from elmer.app import app\n"
         # The parks in the figures are the real feed's, taken once here, as
         # the running unit takes it every twenty minutes - never made up.
         "from elmer import spotlog\n"
         "spotlog.sample()\n"
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
    where = figure.get("where")
    if figure.get("region"):
        # Several elements cropped as one: a transparent box laid over all of
        # them, and the shutter cropped to the box. Nothing on the page moves.
        setup += ("; await new Promise(r => setTimeout(r, 300));"
                  " const gsEls = %r.map(q => document.querySelector(q)).filter(Boolean);"
                  " if (gsEls.length) { const rs = gsEls.map(e => e.getBoundingClientRect());"
                  " const box = document.createElement('div'); box.id = 'gs-region';"
                  " const t = Math.min(...rs.map(r => r.top)) + scrollY, l = Math.min(...rs.map(r => r.left)) + scrollX;"
                  " box.style.cssText = 'position:absolute;pointer-events:none;top:' + t + 'px;left:' + l +"
                  " 'px;width:' + (Math.max(...rs.map(r => r.right)) + scrollX - l) + 'px;height:' +"
                  " (Math.max(...rs.map(r => r.bottom)) + scrollY - t) + 'px';"
                  " document.body.appendChild(box); }") % (figure["region"],)
        where = "#gs-region"
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
          % (setup, where))
    try:
        width = browser.evaluate(url, js, width=1280, height=900,
                                 settle=figure.get("settle", 2.5),
                                 out=str(out), clip=where,
                                 # Say who we are, or a unit with two profiles
                                 # answers /who and the figure is of that.
                                 cookies={"elmer_user": str(REACH_USER if figure.get("qth") else USER)})
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
                % (figure["name"], where, figure["url"]))
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
