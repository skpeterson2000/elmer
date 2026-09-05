"""XP, daily streaks and achievements.

The game layer only ever *rewards* study that the spaced-repetition scheduler
already considers useful, so chasing points and learning the material pull in
the same direction: answering a hard, overdue card is worth far more than
re-answering something already mastered.

XP measures effort and nothing more. Titles live in :mod:`elmer.ranks`, where
they are earned inside the licence class they name - a global XP ladder handed
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


def touch_streak(conn):
    """Roll the daily streak forward. Returns the streak length after today."""
    row = conn.execute(
        "SELECT streak_days, best_streak, last_study_day FROM profile WHERE id = ?",
        (conn.user_id,)
    ).fetchone()
    now, last = today(), row["last_study_day"]
    streak = row["streak_days"]
    if last == now:
        return streak
    if last and date.fromisoformat(last) == date.fromisoformat(now) - timedelta(days=1):
        streak += 1
    else:
        streak = 1
    best = max(streak, row["best_streak"])
    conn.execute(
        "UPDATE profile SET streak_days = ?, best_streak = ?, last_study_day = ? "
        "WHERE id = ?", (streak, best, now, conn.user_id),
    )
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


def check_mastery_achievements(conn, per_section, overall):
    codes = []
    if any(v >= 0.90 for v in per_section.values()):
        codes.append("section_master")
    if overall >= 0.50:
        codes.append("pool_half")
    if overall >= 0.90:
        codes.append("pool_master")
    return award(conn, codes)
