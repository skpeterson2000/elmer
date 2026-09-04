"""Spaced repetition, mastery estimates and exam-readiness simulation.

Scheduling is SM-2 with the grade inferred from correctness and how long the
answer took, so the user never has to self-rate a card.

Mastery is deliberately *not* "percent of questions seen".  Each card carries an
estimated probability of answering it correctly right now: a Laplace-smoothed
accuracy discounted by a forgetting curve, floored at the 25% you would get by
guessing between four choices.  Questions never seen inherit the estimate from
their section, which is what lets the readiness number mean something before
the whole pool has been drilled.
"""
import math
import random
from datetime import timedelta

from .db import utcnow

GUESS = 0.25            # four-choice multiple guess floor
TARGET_RETENTION = 0.90  # interval is chosen to land here at review time
DECAY = -math.log(TARGET_RETENTION)
MAX_INTERVAL = 180.0
MIN_EASE, MAX_EASE = 1.3, 2.8
FAST_MS, SLOW_MS = 6000, 25000
RECOGNITION_FLOOR = 0.60   # multiple choice survives forgetting better than recall
EVIDENCE_HALF = 30         # answers before inference about unseen questions is half-trusted


def grade(correct, ms):
    """Map an answer onto SM-2's 0-5 quality scale."""
    if not correct:
        return 2 if ms and ms < SLOW_MS else 1
    if ms is None:
        return 4
    if ms <= FAST_MS:
        return 5
    if ms <= SLOW_MS:
        return 4
    return 3


def schedule(card, quality, now=None):
    """Return the updated scheduling fields for a card after one answer."""
    now = now or utcnow()
    ease = card["ease"] if card else 2.5
    interval = card["interval"] if card else 0.0
    reps = card["reps"] if card else 0
    lapses = card["lapses"] if card else 0

    ease += 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    ease = min(MAX_EASE, max(MIN_EASE, ease))

    if quality < 3:
        reps, lapses = 0, lapses + 1
        interval = 0.0                      # relearn: due again immediately
    else:
        if reps == 0:
            interval = 1.0
        elif reps == 1:
            interval = 4.0
        else:
            interval = min(MAX_INTERVAL, interval * ease)
        reps += 1

    due = now + timedelta(days=interval)
    return {"ease": round(ease, 4), "interval": round(interval, 4),
            "reps": reps, "lapses": lapses, "due": due.isoformat(),
            "last_seen": now.isoformat()}


def _elapsed_days(card, now):
    if not card or not card["last_seen"]:
        return 0.0
    try:
        from datetime import datetime
        last = datetime.fromisoformat(card["last_seen"])
    except ValueError:
        return 0.0
    return max(0.0, (now - last).total_seconds() / 86400.0)


PRIOR_WEIGHT = 1.5


def skill(card, now=None, prior=0.5):
    """0..1 estimate of genuine knowledge of one card, decayed by time.

    ``prior`` is the accuracy a card is shrunk toward when there is little
    evidence about it. Callers that know the learner's overall accuracy should
    pass it: shrinking a strong learner's thin cards toward 0.5 understates
    them badly, because well-known cards earn long intervals and so accumulate
    the fewest observations.
    """
    if not card or not card["seen"]:
        return None
    now = now or utcnow()
    accuracy = ((card["correct"] + PRIOR_WEIGHT * prior)
                / (card["seen"] + PRIOR_WEIGHT))
    base = max(0.0, (accuracy - GUESS) / (1 - GUESS))
    if card["interval"] > 0:
        retention = math.exp(-DECAY * _elapsed_days(card, now) / card["interval"])
    else:
        retention = 0.55 if card["reps"] == 0 else 1.0
    # Recognising the right answer among four choices decays more slowly than
    # free recall does, so forgetting erodes the estimate rather than erasing
    # it. Without this the readiness number sits several questions below what
    # the same learner actually scores on a mock exam.
    return max(0.0, min(1.0, base * (RECOGNITION_FLOOR + (1 - RECOGNITION_FLOOR) * retention)))


def p_correct(skill_value):
    return GUESS + (1 - GUESS) * (skill_value or 0.0)


def pool_skills(pool, cards, now=None):
    """Per-question skill, filling unseen questions in from their section.

    Returns ``(per_question, per_section, per_subelement, overall)``.
    """
    now = now or utcnow()

    # Empirical Bayes: shrink each card toward this learner's own accuracy.
    # This is a mean over cards, not over answers, because scheduling shows
    # failing cards far more often than mastered ones - pooling raw answers
    # would put the learner's "average" somewhere near their worst material.
    answered = [c for c in cards.values() if c["seen"]]
    prior = (_mean([(c["correct"] + 0.5) / (c["seen"] + 1.0) for c in answered])
             if answered else 0.5)

    seen_skill = {}
    for q in pool.questions:
        value = skill(cards.get(q["id"]), now, prior)
        if value is not None:
            seen_skill[q["id"]] = value

    section_seen, sub_seen = {}, {}
    for q in pool.questions:
        if q["id"] in seen_skill:
            section_seen.setdefault(q["section"], []).append(seen_skill[q["id"]])
            sub_seen.setdefault(q["subelement"], []).append(seen_skill[q["id"]])

    overall = _mean(list(seen_skill.values()))
    sub_est = {c: _mean(v) for c, v in sub_seen.items()}

    def fallback(section):
        sub = pool.subelement_of(section)
        return sub_est.get(sub, overall)

    # An unseen question is estimated from its section, discounted because
    # unseen is not proven. The more of a section you have actually answered,
    # the more the rest of it can be inferred from that evidence - and if the
    # whole pool rests on a handful of answers, almost nothing can be inferred
    # at all. Without this, one lucky answer implied competence across 400
    # unseen questions.
    evidence = len(seen_skill)
    confidence = evidence / (evidence + EVIDENCE_HALF)
    per_question = {}
    for q in pool.questions:
        if q["id"] in seen_skill:
            per_question[q["id"]] = seen_skill[q["id"]]
            continue
        est = section_seen.get(q["section"])
        base = _mean(est) if est else fallback(q["section"])
        total = len(pool.by_section.get(q["section"], [])) or 1
        coverage = len(est or []) / total
        per_question[q["id"]] = (0.75 + 0.20 * coverage) * base * confidence

    per_section = {}
    for code in pool.section_order:
        vals = [per_question[q["id"]] for q in pool.by_section.get(code, [])]
        per_section[code] = _mean(vals)
    per_subelement = {}
    for sub in pool.subelement_meta:
        vals = [per_question[q["id"]] for q in pool.questions
                if q["subelement"] == sub]
        per_subelement[sub] = _mean(vals)

    return per_question, per_section, per_subelement, _mean(list(per_question.values()))


def _mean(values):
    return sum(values) / len(values) if values else 0.0


def readiness(pool, per_question, per_section, trials=4000, seed=None):
    """Monte-Carlo the real exam: one question drawn per section, as the VEs do.

    Returns pass probability, mean score and a plain-language verdict.
    """
    rng = random.Random(seed)
    sections = [pool.by_section[c] for c in pool.section_order if pool.by_section.get(c)]
    passes, total_score, scores = 0, 0, []
    for _ in range(trials):
        score = 0
        for questions in sections:
            q = questions[rng.randrange(len(questions))]
            if rng.random() < p_correct(per_question[q["id"]]):
                score += 1
        scores.append(score)
        total_score += score
        if score >= pool.pass_mark:
            passes += 1
    scores.sort()
    return {
        "pass_probability": passes / trials,
        "mean_score": total_score / trials,
        "percent": 100.0 * total_score / trials / pool.exam_questions,
        "p10": scores[int(0.10 * trials)],
        "p90": scores[int(0.90 * trials)],
        "pass_mark": pool.pass_mark,
        "total": pool.exam_questions,
    }


def due_queue(pool, cards, now=None, limit=None, sections=None):
    """Cards to study next: overdue first, then unseen, then weakest.

    Ties break toward the question that has been wrong most recently, which is
    what actually moves an exam score.
    """
    now = now or utcnow()
    from datetime import datetime

    overdue, fresh, rest = [], [], []
    for q in pool.questions:
        if sections and q["section"] not in sections:
            continue
        card = cards.get(q["id"])
        if not card or not card["seen"]:
            fresh.append((q["id"], 0.0))
            continue
        if card["due"]:
            try:
                days_over = (now - datetime.fromisoformat(card["due"])).total_seconds() / 86400
            except ValueError:
                days_over = 0.0
        else:
            days_over = 0.0
        if days_over >= 0:
            overdue.append((q["id"], days_over / max(card["interval"], 0.5)))
        else:
            rest.append((q["id"], -(skill(card, now) or 0.0)))

    overdue.sort(key=lambda x: -x[1])
    rest.sort(key=lambda x: x[1])
    order = _interleave([i for i, _ in overdue], [i for i, _ in fresh])
    order += [i for i, _ in rest]
    return order[:limit] if limit else order


NEW_EVERY = 3


def _interleave(reviews, new, every=NEW_EVERY):
    """Weave new questions into the review queue.

    Without this, a mature deck's reviews fill every session and coverage of
    the pool stops growing - which is exactly when a learner most needs the
    material they have never met.
    """
    out, r, n = [], iter(reviews), iter(new)
    exhausted_r = exhausted_n = False
    while not (exhausted_r and exhausted_n):
        for _ in range(every - 1):
            item = next(r, None)
            if item is None:
                exhausted_r = True
                break
            out.append(item)
        item = next(n, None)
        if item is None:
            exhausted_n = True
            if exhausted_r:
                break
        else:
            out.append(item)
    out.extend(r)
    out.extend(n)
    return out
