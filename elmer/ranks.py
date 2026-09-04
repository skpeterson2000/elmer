"""Rank progression: a five-step ladder nested inside every licence class.

The point of the nesting is that a title can only be earned with the material
it names.  There is no route to a General title that does not run through
General questions, which is what a single global XP ladder got wrong.

Within a class the steps are::

    <Class> Listener -> Learner -> Operator -> <Class> -> <Class> Elmer

The first two are earned by coverage and estimated mastery.  The upper three
require mock exam evidence, and that evidence goes stale, modelled on the FCC's
own pathway for an expired licence:

* **current** - a passing exam within CURRENT_DAYS.
* **grace**   - past that but within GRACE_DAYS. The tier is retained but shown
  as lapsed, and a single passing exam renews it, exactly as a licence in its
  grace period is renewed without re-testing.
* **expired** - past GRACE_DAYS. The exam-proven tiers are lost and must be
  earned again in full, as an amateur past the grace period must re-test.

Thresholds are deliberately gathered here as named constants so they can be
tuned without hunting through the logic.
"""
from datetime import datetime, timedelta, timezone

# --- step requirements ------------------------------------------------------
LISTENER_ANSWERS = 25          # questions answered from this pool
LEARNER_COVERAGE = 0.40
LEARNER_MASTERY = 0.40
OPERATOR_COVERAGE = 0.70
OPERATOR_MASTERY = 0.60
OPERATOR_EXAMS = 1             # at least one mock exam passed
CLASS_COVERAGE = 0.90
CLASS_PASS_ODDS = 0.85
CLASS_RECENT = 3               # 2 of the last 3 exams passed
CLASS_RECENT_PASSES = 2
ELMER_COVERAGE = 1.0
ELMER_PASS_ODDS = 0.95
ELMER_RECENT = 5               # last 5 exams, all passed
ELMER_MEAN_PERCENT = 90.0

# --- currency of exam evidence ---------------------------------------------
CURRENT_DAYS = 90
GRACE_DAYS = 180

# --- staying current by practice -------------------------------------------
# Regular practice keeps a tier alive without re-sitting an exam, which is how
# proficiency actually works. The bar rises with the tier: holding an Elmer
# title by practice takes Elmer-standard practice. Counted over distinct
# questions, so repeating one easy card cannot maintain a whole pool.
MAINTENANCE_WINDOW = 30
MAINTENANCE_BAR = {}          # filled in below, once the step numbers exist

LISTENER, LEARNER, OPERATOR, CLASS, ELMER = 1, 2, 3, 4, 5
EXAM_PROVEN = OPERATOR         # steps at or above this need live exam evidence

MAINTENANCE_BAR = {            # step -> (distinct questions, accuracy)
    OPERATOR: (30, 0.75),
    CLASS: (40, 0.85),
    ELMER: (50, 0.90),
}

TRACKS = {
    "amateur": ["tech2026", "gen2023", "extra2024"],
    "commercial": ["element1", "element3", "element8"],
}
TRACK_TITLES = {"amateur": "Amateur", "commercial": "Commercial"}


def step_name(rank_name, step):
    if step <= 0:
        return "not started"
    if step == CLASS:
        return rank_name
    if step == ELMER:
        return f"{rank_name} Elmer"
    return f"{rank_name} {['Listener', 'Learner', 'Operator'][step - 1]}"


def _req(label, value, target, fmt="{:.0%}"):
    return {"label": label, "value": value, "target": target,
            "met": value >= target,
            "shown": fmt.format(value), "needed": fmt.format(target)}


def _aware(when):
    """Coerce a datetime to UTC-aware.

    Timestamps are stored aware, but callers pass whatever they have. Mixing
    the two raises only once there is a passed exam on record, which is exactly
    when the dashboard is most wanted - so both sides are normalised here.
    """
    if when is None:
        return None
    return when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when


def _exam_summary(exams, now):
    """Condense a pool's exam history into the figures the ladder needs."""
    now = _aware(now)
    finished = [e for e in exams if e.get("finished")]
    finished.sort(key=lambda e: e["finished"], reverse=True)
    passed = [e for e in finished if e["passed"]]
    last_pass = None
    if passed:
        try:
            last_pass = _aware(datetime.fromisoformat(
                passed[0]["finished"].replace("Z", "+00:00")))
        except ValueError:
            last_pass = None
    recent = finished[:ELMER_RECENT]
    percents = [100.0 * e["score"] / e["total"] for e in recent if e["total"]]
    return {
        "taken": len(finished),
        "passed": len(passed),
        "last_three": finished[:CLASS_RECENT],
        "last_three_passes": sum(1 for e in finished[:CLASS_RECENT] if e["passed"]),
        "last_five": recent,
        "last_five_all_passed": len(recent) >= ELMER_RECENT
                                and all(e["passed"] for e in recent),
        "last_five_mean": sum(percents) / len(percents) if percents else 0.0,
        "days_since_pass": (now - last_pass).days if last_pass else None,
    }


def currency(days_since_pass):
    """Where the exam evidence sits on the current / grace / expired scale."""
    if days_since_pass is None:
        return "none"
    if days_since_pass <= CURRENT_DAYS:
        return "current"
    if days_since_pass <= GRACE_DAYS:
        return "grace"
    return "expired"


def maintenance_status(step, window):
    """Whether recent practice is enough to hold ``step`` without an exam."""
    bar = MAINTENANCE_BAR.get(step)
    if not bar or window is None:
        return None
    need_q, need_acc = bar
    return {
        "step": step,
        "distinct": window["distinct"], "need_distinct": need_q,
        "accuracy": window["accuracy"], "need_accuracy": need_acc,
        "window_days": window["window_days"],
        "met": window["distinct"] >= need_q and window["accuracy"] >= need_acc,
        "questions_short": max(0, need_q - window["distinct"]),
    }


def standing(pool, stats, exams, now=None, window=None):
    """Work out one pool's step, and what the next one asks for.

    ``stats`` needs ``coverage``, ``mastery`` and ``pass_probability``.
    ``window`` is recent practice, from :func:`elmer.db.maintenance_window`.
    """
    now = _aware(now) or datetime.now(timezone.utc)
    ex = _exam_summary(exams, now)
    state = currency(ex["days_since_pass"])
    coverage = stats["coverage"]
    mastery = stats["mastery"]
    odds = stats["pass_probability"]

    ladder = [
        (LISTENER, [_req("questions answered", stats["answered"],
                         LISTENER_ANSWERS, "{:.0f}")]),
        (LEARNER, [_req("pool seen", coverage, LEARNER_COVERAGE),
                   _req("mastery", mastery, LEARNER_MASTERY)]),
        (OPERATOR, [_req("pool seen", coverage, OPERATOR_COVERAGE),
                    _req("mastery", mastery, OPERATOR_MASTERY),
                    _req("mock exams passed", ex["passed"], OPERATOR_EXAMS, "{:.0f}")]),
        (CLASS, [_req("pool seen", coverage, CLASS_COVERAGE),
                 _req("pass probability", odds, CLASS_PASS_ODDS),
                 _req(f"passes in last {CLASS_RECENT} exams",
                      ex["last_three_passes"], CLASS_RECENT_PASSES, "{:.0f}")]),
        (ELMER, [_req("pool seen", coverage, ELMER_COVERAGE),
                 _req("pass probability", odds, ELMER_PASS_ODDS),
                 _req(f"last {ELMER_RECENT} exams all passed",
                      1.0 if ex["last_five_all_passed"] else 0.0, 1.0, "{:.0f}"),
                 _req(f"mean of last {ELMER_RECENT}", ex["last_five_mean"],
                      ELMER_MEAN_PERCENT, "{:.0f}%")]),
    ]

    earned = 0
    for step, reqs in ladder:
        if all(r["met"] for r in reqs):
            earned = step
        else:
            break

    # Sustained practice at the tier's own standard keeps it current without
    # re-sitting an exam - a few questions a week protects proficiency, which
    # is exactly what the decay is trying to measure.
    upkeep = maintenance_status(earned, window)
    maintained = bool(upkeep and upkeep["met"] and ex["passed"])
    if maintained and state in ("grace", "expired"):
        state = "current"

    # Exam evidence past its grace period cannot support a proven tier.
    held = earned
    if earned >= EXAM_PROVEN and state == "expired":
        held = min(earned, LEARNER)

    nxt = next((s for s, _ in ladder if s > held), None)
    next_reqs = dict(ladder).get(nxt, [])

    return {
        "pool_id": pool.pool_id,
        "rank_name": pool.rank_name,
        "class_name": pool.name,
        "track": pool.track,
        "step": held,
        "step_name": step_name(pool.rank_name, held),
        "earned_step": earned,
        "lapsed": state == "grace" and earned >= EXAM_PROVEN,
        "expired": state == "expired" and earned >= EXAM_PROVEN,
        "currency": state,
        "maintained": maintained,
        "upkeep": upkeep,
        "days_since_pass": ex["days_since_pass"],
        "renew_within": (GRACE_DAYS - ex["days_since_pass"])
                        if state == "grace" else None,
        "next_step": nxt,
        "next_name": step_name(pool.rank_name, nxt) if nxt else None,
        "next_requirements": next_reqs,
        "coverage": coverage, "mastery": mastery, "pass_probability": odds,
        "exams": {k: ex[k] for k in ("taken", "passed", "last_three_passes",
                                     "last_five_mean")},
    }


def track_standing(standings, track):
    """A track's headline title: the highest class actually qualified in.

    A fully-earned higher class outranks a lower one, so General beats
    Technician Elmer. Below the class tier nothing is qualified yet, so the
    furthest step reached is shown instead.
    """
    members = [s for s in standings if s["track"] == track]
    order = {pid: n for n, pid in enumerate(TRACKS[track])}
    members.sort(key=lambda s: order.get(s["pool_id"], 99))

    qualified = [s for s in members if s["step"] >= CLASS]
    if qualified:
        lead = qualified[-1]                      # highest class in track order
    else:
        lead = max(members, key=lambda s: (s["step"], -order.get(s["pool_id"], 99)),
                   default=None)
    return {
        "track": track,
        "label": TRACK_TITLES[track],
        "title": lead["step_name"] if lead and lead["step"] else "Unlicensed",
        "lapsed": bool(lead and lead["lapsed"]),
        "lead_pool": lead["pool_id"] if lead else None,
        "members": members,
    }


def overall(standings):
    return {track: track_standing(standings, track) for track in TRACKS}
