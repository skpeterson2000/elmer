"""XP, daily streaks and achievements.

The game layer only ever *rewards* study that the spaced-repetition scheduler
already considers useful, so chasing points and learning the material pull in
the same direction: answering a hard, overdue card is worth far more than
re-answering something already mastered.

XP measures effort and nothing more. Titles live in :mod:`elmer.ranks`, where
they are earned inside the license class they name - a global XP ladder handed
out a "General" title to someone who had never opened a General question.
"""
from datetime import date, timedelta

from .db import today

ACHIEVEMENTS = [
    ("first_light", "First Light", "Answer your first question"),
    ("century", "Century", "Answer 100 questions"),
    ("kilo", "Kilo", "Answer 1000 questions"),
    ("run_10", "Clean Run", "10 correct answers in a row"),
    ("run_25", "Pileup", "25 correct answers in a row"),
    ("run_50", "Solid Copy", "50 correct answers in a row"),
    ("streak_3", "Warming Up", "Study 3 days running"),
    ("streak_7", "Full Week", "Study 7 days running"),
    ("streak_30", "Dedicated", "Study 30 days running"),
    ("first_exam", "Sat the Exam", "Finish a full mock exam"),
    ("pass_any", "Passed One", "Pass any mock exam"),
    ("pass_tech", "Technician Ready", "Pass a Technician mock exam"),
    ("pass_gen", "General Ready", "Pass a General mock exam"),
    ("pass_extra", "Extra Ready", "Pass an Amateur Extra mock exam"),
    ("pass_grol", "GROL Ready", "Pass an Element 3 mock exam"),
    ("pass_radar", "Radar Ready", "Pass an Element 8 mock exam"),
    ("perfect_exam", "Clean Sweep", "Score 100% on a mock exam"),
    ("section_master", "Section Master", "Take any section to 90% mastery"),
    ("pool_half", "Halfway House", "Reach 50% mastery of a whole pool"),
    ("pool_master", "Pool Master", "Reach 90% mastery of a whole pool"),
    ("propagation", "Band Watcher", "Check live propagation conditions"),
    ("night_owl", "Grey Line", "Study between 0300 and 0500 local"),
    # The code. Slow to feel progress in, so the record's milestones are
    # named: the characters copied reliably, the first copy that needed no
    # resend, the rating's rungs, and the ballgame's first hit - and the
    # first thing keyed that was answered, which is the one worth having.
    ("cw_first", "First Dit", "Copy your first character"),
    ("cw_five", "Five Solid", "Copy five characters reliably"),
    ("cw_half", "Half the Code", "Copy twenty characters reliably"),
    ("cw_whole", "The Whole Code", "Copy all forty characters reliably"),
    ("cw_first_time", "First Time Through", "Copy a block at 90% with no resend"),
    ("cw_streak_7", "Daily Code", "Practise CW 7 days running"),
    ("cw_copy_10", "Ten Words", "Rated copying at 10 wpm"),
    ("cw_copy_20", "Twenty Words", "Rated copying at 20 wpm"),
    ("cw_fist", "Clean Fist", "Rated sending at 90% accuracy"),
    ("cw_qsm", "QSM?", "Ask for a resend in code, and be answered"),
    ("cw_hit", "Base Hit", "Copy a pitch clean in CW Baseball"),
    ("cw_majors", "Big League", "Copy a pitch clean in the majors"),
]
ACHIEVEMENT_INDEX = {code: (name, desc) for code, name, desc in ACHIEVEMENTS}


def xp_for_answer(correct, ms, card, was_due):
    """Points for a single answer. Hard and overdue cards pay the most."""
    if not correct:
        return 2                                    # showing up still counts
    points = 10
    if ms is not None and ms <= 6000:
        points += 4                                 # answered from knowledge
    if was_due:
        points += 6                                 # rescued an overdue card
    if card and card["lapses"]:
        points += min(8, 2 * card["lapses"])        # a card that fought back
    if card and card["seen"] == 0:
        points += 3                                 # new ground
    return points


# One day of rest earned for every six studied, which is the oldest scheduling
# advice there is. A streak that a single missed evening destroys stops being a
# reason to study and becomes a reason to dread missing one; rest that has been
# earned is a different thing from rest that is simply given.
REST_EARNED_EVERY = 7


def rest_days(conn):
    """Rest days banked, spent, and available right now."""
    row = conn.execute("SELECT streak_days FROM profile WHERE id = ?",
                       (conn.user_id,)).fetchone()
    streak = row["streak_days"] if row else 0
    from . import db
    spent = db.kv_get(conn, "rest_spent", 0) or 0
    earned = streak // REST_EARNED_EVERY
    return {"earned": earned, "spent": spent,
            "available": max(0, earned - spent), "streak": streak}


def touch_streak(conn):
    """Roll the daily streak forward. Returns the streak length after today.

    A missed day does not automatically end a streak. One rest day is banked
    for every seven consecutive days studied, and missing a single day spends
    one if any is available - so a long streak carries the slack it earned,
    and a short one does not. Missing two days in a row ends it regardless:
    the bank covers a day off, not a lapse in the habit.
    """
    from . import db
    row = conn.execute(
        "SELECT streak_days, best_streak, last_study_day FROM profile WHERE id = ?",
        (conn.user_id,)
    ).fetchone()
    now, last = today(), row["last_study_day"]
    streak = row["streak_days"]
    if last == now:
        return streak

    gap = None
    if last:
        gap = (date.fromisoformat(now) - date.fromisoformat(last)).days

    rested = False
    if gap == 1:
        streak += 1
    elif gap == 2 and rest_days(conn)["available"] > 0:
        # Exactly one day missed, and there is rest in hand to cover it.
        db.kv_set(conn, "rest_spent", (db.kv_get(conn, "rest_spent", 0) or 0) + 1)
        streak += 1
        rested = True
    else:
        streak = 1
        db.kv_set(conn, "rest_spent", 0)

    best = max(streak, row["best_streak"])
    conn.execute(
        "UPDATE profile SET streak_days = ?, best_streak = ?, last_study_day = ? "
        "WHERE id = ?", (streak, best, now, conn.user_id),
    )
    if rested:
        log = __import__("logging").getLogger("elmer")
        log.info("streak: a rest day covered the gap, now %d days", streak)
    return streak


def bump_run(conn, correct):
    """Track consecutive correct answers across questions.

    The per-card ``run`` column counts repeats of one question; the streak a
    player actually feels is the run of right answers in a row, whatever they
    were about, so it lives here.
    """
    from .db import kv_get, kv_set
    run = (kv_get(conn, "answer_run", 0) + 1) if correct else 0
    best = max(run, kv_get(conn, "best_answer_run", 0))
    kv_set(conn, "answer_run", run)
    kv_set(conn, "best_answer_run", best)
    return run, best


def add_xp(conn, points):
    conn.execute("UPDATE profile SET xp = xp + ? WHERE id = ?",
                 (points, conn.user_id))


def earned(conn):
    return {r["code"]: r["earned"] for r in conn.execute(
        "SELECT code, earned FROM achievement WHERE user_id = ?", (conn.user_id,))}


def award(conn, codes):
    """Grant achievements not already held; returns the newly granted ones."""
    have = earned(conn)
    fresh = []
    for code in codes:
        if code in have or code not in ACHIEVEMENT_INDEX:
            continue
        conn.execute(
            "INSERT INTO achievement (user_id, code, earned) VALUES (?, ?, ?)",
            (conn.user_id, code, today()))
        name, desc = ACHIEVEMENT_INDEX[code]
        fresh.append({"code": code, "name": name, "description": desc})
        add_xp(conn, 50)
    return fresh


def check_answer_achievements(conn, run, total_answers, streak_days, hour):
    codes = ["first_light"]
    if total_answers >= 100:
        codes.append("century")
    if total_answers >= 1000:
        codes.append("kilo")
    for n, code in ((10, "run_10"), (25, "run_25"), (50, "run_50")):
        if run >= n:
            codes.append(code)
    for n, code in ((3, "streak_3"), (7, "streak_7"), (30, "streak_30")):
        if streak_days >= n:
            codes.append(code)
    if 3 <= hour < 5:
        codes.append("night_owl")
    return award(conn, codes)


EXAM_BADGE = {
    "tech2026": "pass_tech", "gen2023": "pass_gen", "extra2024": "pass_extra",
    "element3": "pass_grol", "element8": "pass_radar",
}


def check_exam_achievements(conn, pool_id, passed, perfect):
    codes = ["first_exam"]
    if passed:
        codes.append("pass_any")
        if pool_id in EXAM_BADGE:
            codes.append(EXAM_BADGE[pool_id])
    if perfect:
        codes.append("perfect_exam")
    return award(conn, codes)


def check_cw_achievements(conn, progress, session_pct=None, resends=None, streak=None, rating=None):
    """The code's badges, from whatever the caller has just learnt: the
    per-character record after a copy session (with that session's score
    and how many resends it took), the practice streak, or the rating."""
    from . import cw
    codes = []
    if any(int(s.get("sent") or 0) for s in (progress or {}).values()):
        codes.append("cw_first")
    solid = sum(1 for s in (progress or {}).values() if cw.is_solid(s))
    for n, code in ((5, "cw_five"), (20, "cw_half"), (40, "cw_whole")):
        if solid >= n:
            codes.append(code)
    if session_pct is not None and session_pct >= 90 and not resends:
        codes.append("cw_first_time")
    if streak is not None and streak >= 7:
        codes.append("cw_streak_7")
    rating = rating or {}
    for n, code in ((10, "cw_copy_10"), (20, "cw_copy_20")):
        if (rating.get("copy_wpm") or 0) >= n:
            codes.append(code)
    if (rating.get("send_accuracy") or 0) >= 90:
        codes.append("cw_fist")
    return award(conn, codes)


def check_ballgame_achievements(conn, hit=False, majors=False, keyed_ask=False):
    """CW Baseball's badges: a clean copy of a pitch, one in the majors,
    and a resend asked for in code that the machine answered."""
    codes = []
    if hit:
        codes.append("cw_hit")
        if majors:
            codes.append("cw_majors")
    if keyed_ask:
        codes.append("cw_qsm")
    return award(conn, codes)


def check_mastery_achievements(conn, per_section, overall):
    codes = []
    if any(v >= 0.90 for v in per_section.values()):
        codes.append("section_master")
    if overall >= 0.50:
        codes.append("pool_half")
    if overall >= 0.90:
        codes.append("pool_master")
    return award(conn, codes)
