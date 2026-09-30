#!/usr/bin/env python3
"""The phone's map zooms to the green whenever the green is the target.

    python3 tests/test_golf_zoom.py

It zoomed only when the club ELMER would hand over reached the pin - and
that club is the one that reaches the golfer's own mark, so a mark set
short of the green, or going for a par five in two with more club than
suggested, stayed on the whole hole, where a mark can only be put roughly.
What is held here:

  - the map zooms when any club in the bag reaches the green from the lie;
  - not when none does;
  - the golfer can switch either way for this stroke, and the next stroke
    starts from ELMER's own choice again;
  - a ball on the green has its own view, whatever was chosen.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import golf as G  # noqa: E402

FAILS = []


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}" + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def main():
    g = G.Golf([1], G.course("pebble-beach"), seed=3)
    h = g.hole()
    ball = g.balls[1]
    longest = max(g.reach(1, c) for c in g.clubs_for(1) if c != "putter")
    print(f"\n-- the {h['n']}, {h['yards']} yards; the longest club in the bag goes {longest:.0f} --")
    ball.at, ball.lie = h["yards"] - (longest - 5), "fairway"
    check("in reach of the longest club: zoomed to the green", g.zoomed(1), True)
    g.set_aim(1, ball.at + 60, 0)
    check("  and still zoomed with a mark set short of the green", g.zoomed(1), True)
    g.clear_aim(1)
    ball.at = h["yards"] - (longest + 40)
    check("out of reach of every club: the whole hole", g.zoomed(1), False)

    print("\n-- the golfer's switch --")
    check("switched to the green, it zooms", g.set_view(1, "green"), True)
    ball.at = h["yards"] - (longest - 5)
    check("switched back to the whole hole, it is the whole hole", g.set_view(1, "hole"), False)
    ball.strokes += 1
    check("  for that stroke only: the next starts from ELMER's own", g.zoomed(1), True)
    ball.lie, ball.at = "green", h["yards"] - 3
    g.set_view(1, "green")
    check("a ball on the green has its own view, whatever was chosen", g.zoomed(1), False)
    check("a view that is not one is ignored", g.set_view(1, "sideways"), False)

    print("\n-- the phone --")
    page = (ROOT / "elmer" / "templates" / "party_player.html").read_text(encoding="utf-8")
    check("offers the switch, and sends it", ('id="aim-view"' in page, "/api/party/golf/view" in page), (True, True))
    from elmer.app import app
    check("the route is there", "/api/party/golf/view" in {r.rule for r in app.url_map.iter_rules()}, True)


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
