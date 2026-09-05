"""Mock exam generation and scoring.

Every exam here is built the way the real one is: exactly one question drawn at
random from each section of the pool, in syllabus order.  That is the published
NCVEC and FCC blueprint, so a score in ELMER means the same thing a score at a
VE session or a COLEM would.
"""
import json
import random

from .content import get_pool, presentation
from .db import utcnow

# Self-imposed pace targets, not official limits - VE sessions and COLEM
# testing centers set their own. Shown as a target so practice stays honest.
PACE_MINUTES = {
    "tech2026": 45, "gen2023": 45, "extra2024": 75,
    "element1": 40, "element3": 150, "element8": 75,
}


def build(pool_id, seed=None):
    pool = get_pool(pool_id)
    rng = random.Random(seed)
    items = []
    for code in pool.section_order:
        pick = pool.by_section.get(code)
        if not pick:
            continue
        question = pick[rng.randrange(len(pick))]
        shown = presentation(question, rng)
        items.append({
            "question_id": question["id"], "section": code,
            "subelement": question["subelement"],
            "section_title": pool.section_title(code),
            "text": question["text"], "choices": shown["choices"],
            "answer": shown["answer"], "order": shown["order"],
            "figure": pool.figure_url(question), "refs": question.get("refs"),
        })
    return {
        "pool_id": pool_id, "pool_name": pool.long_name,
        "total": len(items), "pass_mark": pool.pass_mark,
        "pace_minutes": PACE_MINUTES.get(pool_id, 60),
        "items": items,
    }


def start(conn, pool_id, seed=None):
    exam = build(pool_id, seed)
    cur = conn.execute(
        "INSERT INTO exam (user_id, pool_id, started, total) VALUES (?, ?, ?, ?)",
        (conn.user_id, pool_id, utcnow().isoformat(), exam["total"]),
    )
    conn.commit()
    exam["exam_id"] = cur.lastrowid
    return exam


def score(conn, exam_id, exam, responses, seconds):
    """Grade a finished exam and persist a per-subelement breakdown."""
    pool = get_pool(exam["pool_id"])
    results, correct = [], 0
    by_sub = {}
    for i, item in enumerate(exam["items"]):
        chosen = responses.get(str(i), responses.get(i))
        ok = chosen is not None and int(chosen) == item["answer"]
        correct += ok
        sub = item["subelement"]
        tally = by_sub.setdefault(sub, {"right": 0, "total": 0})
        tally["total"] += 1
        tally["right"] += int(ok)
        results.append({
            "index": i, "question_id": item["question_id"],
            "section": item["section"], "subelement": sub,
            "chosen": None if chosen is None else int(chosen),
            "answer": item["answer"], "correct": bool(ok),
        })

    passed = correct >= exam["pass_mark"]
    breakdown = [
        {"code": code,
         "title": pool.subelement_meta.get(code, {}).get("title", code),
         "right": v["right"], "total": v["total"],
         "percent": round(100 * v["right"] / v["total"]) if v["total"] else 0}
        for code, v in sorted(by_sub.items())
    ]
    # Keep the exam alongside its results. Overwriting it meant that if
    # anything after scoring failed, a retry could not find the questions and
    # died with a KeyError instead of returning the score already recorded.
    detail = {"exam": exam, "results": results, "breakdown": breakdown}
    conn.execute(
        "UPDATE exam SET finished = ?, score = ?, total = ?, passed = ?, "
        "seconds = ?, detail = ? WHERE id = ? AND user_id = ?",
        (utcnow().isoformat(), correct, exam["total"], int(passed), seconds,
         json.dumps(detail), exam_id, conn.user_id),
    )
    conn.commit()
    return {
        "score": correct, "total": exam["total"], "pass_mark": exam["pass_mark"],
        "passed": passed, "percent": round(100 * correct / exam["total"], 1),
        "seconds": seconds, "breakdown": breakdown, "results": results,
        "perfect": correct == exam["total"],
    }


def history(conn, pool_id=None, limit=20):
    sql = ("SELECT id, pool_id, started, finished, score, total, passed, seconds "
           "FROM exam WHERE finished IS NOT NULL AND user_id = ?")
    args = [conn.user_id]
    if pool_id:
        sql += " AND pool_id = ?"
        args.append(pool_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in conn.execute(sql, args)]
