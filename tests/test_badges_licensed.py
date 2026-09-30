#!/usr/bin/env python3
"""The streaks and badges worth having, for the learner and the licensed.

    python3 tests/test_badges_licensed.py

A daily streak suits somebody working toward a first license, and its short
milestones - three days, a hundred answers, ten in a row - are encouragement
that matters most there. Somebody who already holds the license is better
served by longer measures: weeks running rather than days, and mock exams
that keep coming back clean. What is held here:

  - the short milestones are counted for everybody, and cheered only for
    the unlicensed: for a licensed operator they are quiet;
  - a pass on a pool the license already covers is quiet too; a pass on
    the next one up is not;
  - weeks running: a week missed ends it, a busy day does not;
  - papers in a row with no more than two missed, and perfect ones in a
    row, earn their own badges;
  - Worked All Groups is a badge per pool, once every group is worked;
  - and a quiet badge makes no toast on any page.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolate  # noqa: E402,F401  - before anything from elmer
from elmer import db, game  # noqa: E402

FAILS = []
ROOT = Path(__file__).resolve().parents[1]


def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}: {got!r}"
          + ("" if ok else f"  (wanted {want!r})"))
    if not ok:
        FAILS.append(label)


def licence(conn, cls):
    settings = db.get_profile(conn)["settings"]
    settings["license_class"] = cls
    db.save_settings(conn, settings)


def fresh_badges(conn):
    conn.execute("DELETE FROM achievement WHERE user_id = ?", (conn.user_id,))


def main():
    conn = db.connect()

    print("\n-- short milestones: cheered for a learner, counted quietly for the licensed --")
    licence(conn, "")
    got = {a["code"]: a["quiet"] for a in game.award(conn, ["first_light", "pass_tech"])}
    check("nobody licensed: both cheered", got, {"first_light": False, "pass_tech": False})
    fresh_badges(conn)
    licence(conn, "General")
    got = {a["code"]: a["quiet"] for a in game.award(conn, ["first_light", "pass_tech", "pass_extra", "streak_30"])}
    check("a General: the first answer and a Technician pass are quiet",
          (got["first_light"], got["pass_tech"]), (True, True))
    check("  an Extra pass, and a month's streak, are cheered", (got["pass_extra"], got["streak_30"]), (False, False))
    check("  and the quiet ones are still counted", {"first_light", "pass_tech"} <= set(game.earned(conn)), True)

    print("\n-- weeks running --")
    for key in ("study_week", "week_streak"):
        conn.execute("DELETE FROM kv WHERE user_id = ? AND k = ?", (conn.user_id, key))
    days = ["2026-09-01", "2026-09-03", "2026-09-09", "2026-09-15", "2026-09-22"]
    got = [game._touch_weeks(conn, d) for d in days]
    check("a day in each week, however spaced: the count climbs", got, [1, 1, 2, 3, 4])
    check("  a week with nothing in it ends it", game._touch_weeks(conn, "2026-10-06"), 1)

    print("\n-- papers that keep coming back clean --")
    for key in ("exam_clean_run", "exam_perfect_run"):
        conn.execute("DELETE FROM kv WHERE user_id = ? AND k = ?", (conn.user_id, key))
    runs = [game.exam_runs(conn, m) for m in (2, 0, 1, 3, 0)]
    check("two missed is still clean, three ends it; perfect counts on its own",
          runs, [(1, 0), (2, 1), (3, 0), (0, 0), (1, 1)])
    fresh_badges(conn)
    for key in ("exam_clean_run", "exam_perfect_run"):
        conn.execute("DELETE FROM kv WHERE user_id = ? AND k = ?", (conn.user_id, key))
    codes = []
    for _ in range(3):
        codes += [a["code"] for a in game.check_exam_achievements(conn, "extra2024", True, True, missed=0)]
    check("three perfect papers in a row: Steady Hand and Clean Sheets",
          {"clean_3", "sweep_3"} <= set(codes), True)

    print("\n-- Worked All Groups --")
    check("not until every group", game.check_group_achievements(conn, "tech2026", 34, 35), [])
    got = [a["code"] for a in game.check_group_achievements(conn, "tech2026", 35, 35)]
    check("  then the pool's own badge", got, ["wag_tech"])
    check("every pool with an exam badge has a Worked All badge", set(game.WAG_BADGE) == set(game.EXAM_BADGE), True)
    check("  and they are all on the wall", all(c in game.ACHIEVEMENT_INDEX for c in game.WAG_BADGE.values()), True)

    print("\n-- the screens --")
    js = (ROOT / "elmer" / "static" / "elmer.js").read_text(encoding="utf-8")
    check("a quiet badge makes no toast", "filter(a => !a.quiet)" in js, True)
    study = (ROOT / "elmer" / "static" / "study.js").read_text(encoding="utf-8")
    check("  the verdict notes it, and the badge chime is for the cheered ones",
          ("Counted: " in study, "some(a => !a.quiet)" in study), (True, True))
    conn.commit()


if __name__ == "__main__":
    main()
    print("\n" + ("ALL PASS" if not FAILS else f"FAILURES: {FAILS}"))
    sys.exit(1 if FAILS else 0)
