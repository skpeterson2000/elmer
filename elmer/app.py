"""ELMER - the web application.

Pages are server-rendered; the quiz and exam screens talk to a small JSON API so
answering never reloads the page.  The correct answer is never sent to the
browser before the user commits to a choice: the server hands out a shuffled
presentation plus its permutation, and resolves the real answer on submit.
"""
import json
import logging
import random
from datetime import datetime
from pathlib import Path

from flask import (Flask, abort, g, jsonify, render_template, request,
                   send_from_directory)

from . import db, exams, explain, game, logs, propagation, srs
from .content import get_pool, load_pools, presentation

log = logging.getLogger("elmer")

app = Flask(__name__)
logs.install_request_logging(app)
app.config["JSON_SORT_KEYS"] = False
MODES = ("drill", "weak", "new", "review", "rapid", "section")
EMPTY_REASON = {
    "new": "you have seen every question in this pool at least once",
    "review": "nothing has tripped you up yet - no lapsed questions to review",
    "weak": "no questions available in this selection",
}


def conn():
    if "db" not in g:
        g.db = db.connect()
    return g.db


@app.teardown_appcontext
def _close(_exc):
    handle = g.pop("db", None)
    if handle is not None:
        handle.close()


ICON_NAMES = ("icon.png", "icon.svg", "icon.jpg", "icon.webp")


@app.context_processor
def _icon():
    """Use static/icon.* as the favicon if one has been dropped in."""
    static = Path(app.static_folder)
    for name in ICON_NAMES:
        if (static / name).exists():
            return {"icon_file": name}
    return {"icon_file": None}


# --------------------------------------------------------------------------
# shared computations
# --------------------------------------------------------------------------

def pool_stats(pool, cards, trials=1500):
    per_q, per_sec, per_sub, overall = srs.pool_skills(pool, cards)
    ready = srs.readiness(pool, per_q, per_sec, trials=trials, seed=7)
    seen = sum(1 for c in cards.values() if c["seen"])
    due = len(srs.due_queue(pool, cards, limit=None))
    now = db.utcnow()
    due_now = 0
    for q in pool.questions:
        card = cards.get(q["id"])
        if card and card["seen"] and card["due"]:
            try:
                if datetime.fromisoformat(card["due"]) <= now:
                    due_now += 1
            except ValueError:
                pass
    return {
        "pool": pool, "per_question": per_q, "per_section": per_sec,
        "per_subelement": per_sub, "mastery": overall, "readiness": ready,
        "seen": seen, "unseen": len(pool.questions) - seen,
        "due_now": due_now, "queue_len": due,
    }


def profile_block(connection):
    prof = db.get_profile(connection)
    rank = game.rank_for(prof["xp"])
    answered = connection.execute("SELECT COUNT(*) c FROM answer_log").fetchone()["c"]
    today_count = connection.execute(
        "SELECT COUNT(*) c FROM answer_log WHERE day = ?", (db.today(),)
    ).fetchone()["c"]
    return {"profile": prof, "rank": rank, "answered": answered,
            "today": today_count,
            "achievements": game.earned(connection),
            "all_achievements": game.ACHIEVEMENTS}


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------

def greeting():
    hour = datetime.now().hour
    return "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"


@app.route("/")
def home():
    connection = conn()
    pools = load_pools()
    cards = {pid: db.cards_for_pool(connection, pid) for pid in pools}
    summary = []
    for pid, pool in pools.items():
        stats = pool_stats(pool, cards[pid], trials=600)
        summary.append({
            "pool": pool, "mastery": stats["mastery"],
            "readiness": stats["readiness"], "seen": stats["seen"],
            "due_now": stats["due_now"], "total": len(pool.questions),
        })
    return render_template("home.html", summary=summary, greeting=greeting(),
                           **profile_block(connection))


@app.route("/study/<pool_id>")
def study(pool_id):
    pool = _pool_or_404(pool_id)
    mode = request.args.get("mode", "drill")
    if mode not in MODES:
        mode = "drill"
    section = request.args.get("section")
    return render_template("study.html", pool=pool, mode=mode, section=section,
                           section_title=pool.section_title(section) if section else None,
                           **profile_block(conn()))


@app.route("/exam/<pool_id>")
def exam_page(pool_id):
    pool = _pool_or_404(pool_id)
    return render_template("exam.html", pool=pool,
                           pace=exams.PACE_MINUTES.get(pool_id, 60),
                           **profile_block(conn()))


@app.route("/progress/<pool_id>")
def progress(pool_id):
    pool = _pool_or_404(pool_id)
    connection = conn()
    cards = db.cards_for_pool(connection, pool_id)
    stats = pool_stats(pool, cards, trials=4000)

    subs = []
    for sub in pool.subelements:
        code = sub["code"]
        sections = [s for s in pool.sections if s["subelement"] == code]
        subs.append({
            "code": code, "title": sub["title"],
            "exam_questions": sub["exam_questions"],
            "mastery": stats["per_subelement"].get(code, 0.0),
            "sections": [{
                "code": s["code"], "title": s["title"],
                "mastery": stats["per_section"].get(s["code"], 0.0),
                "count": len(pool.by_section.get(s["code"], [])),
                "seen": sum(1 for q in pool.by_section.get(s["code"], [])
                            if cards.get(q["id"], {}).get("seen")),
            } for s in sections],
        })
    weakest = sorted(
        ({"code": s["code"], "title": s["title"],
          "mastery": stats["per_section"].get(s["code"], 0.0),
          "subelement": s["subelement"]} for s in pool.sections),
        key=lambda s: s["mastery"],
    )[:8]

    daily = connection.execute(
        "SELECT day, COUNT(*) n, SUM(correct) AS n_right FROM answer_log "
        "WHERE pool_id = ? GROUP BY day ORDER BY day DESC LIMIT 30", (pool_id,)
    ).fetchall()
    return render_template(
        "progress.html", pool=pool, stats=stats, subs=subs, weakest=weakest,
        exams=exams.history(connection, pool_id),
        daily=[dict(r) for r in reversed(daily)], **profile_block(connection))


@app.route("/browse/<pool_id>")
def browse(pool_id):
    pool = _pool_or_404(pool_id)
    connection = conn()
    cards = db.cards_for_pool(connection, pool_id)
    section = request.args.get("section") or pool.section_order[0]
    questions = []
    for q in pool.by_section.get(section, []):
        card = cards.get(q["id"])
        questions.append({
            "q": q, "card": card,
            "skill": srs.skill(card) if card else None,
            "figure": pool.figure_url(q),
        })
    per_q, per_sec, _, _ = srs.pool_skills(pool, cards)
    return render_template("browse.html", pool=pool, section=section,
                           questions=questions, per_section=per_sec,
                           **profile_block(connection))


@app.route("/propagation")
def propagation_page():
    connection = conn()
    prof = db.get_profile(connection)
    loc = prof["settings"].get("location") or {}
    game.award(connection, ["propagation"])
    connection.commit()
    return render_template("propagation.html", location=loc,
                           indicators=propagation.INDICATORS,
                           **profile_block(connection))


@app.route("/lab")
def lab():
    return render_template("lab.html", **profile_block(conn()))


@app.route("/figure/<pool_id>/<path:name>")
def figure(pool_id, name):
    directory = (db.ROOT / "data" / "figures" / pool_id).resolve()
    if not directory.is_dir() or "/" in name or ".." in name:
        abort(404)
    return send_from_directory(directory, name, max_age=86400)


def _pool_or_404(pool_id):
    try:
        return get_pool(pool_id)
    except KeyError:
        abort(404)


# --------------------------------------------------------------------------
# study API
# --------------------------------------------------------------------------

@app.route("/api/next")
def api_next():
    pool = _pool_or_404(request.args.get("pool", ""))
    mode = request.args.get("mode", "drill")
    section = request.args.get("section")
    exclude = set(filter(None, request.args.get("exclude", "").split(",")))
    connection = conn()
    cards = db.cards_for_pool(connection, pool.pool_id)

    sections = {section} if section else None
    queue = srs.due_queue(pool, cards, limit=None, sections=sections)

    if mode == "new":
        queue = [q for q in queue if not cards.get(q, {}).get("seen")]
    elif mode == "review":
        queue = [q for q in queue if cards.get(q, {}).get("lapses")]
    elif mode == "weak":
        per_q, _, _, _ = srs.pool_skills(pool, cards)
        queue = sorted(queue, key=lambda q: per_q.get(q, 0.0))[:200]
    elif mode == "rapid":
        random.shuffle(queue)

    if not queue:
        return jsonify({"done": True, "reason": EMPTY_REASON.get(
            mode, "there are no questions in this selection")})
    # `exclude` only suppresses repeats within a session; once it has consumed
    # the whole queue the session has wrapped around, so start it again.
    queue = [q for q in queue if q not in exclude] or queue

    pick = queue[0] if mode != "rapid" else random.choice(queue[:60])
    question = pool.by_id[pick]
    shown = presentation(question)
    card = cards.get(pick)
    return jsonify({
        "done": False,
        "question_id": pick,
        "section": question["section"],
        "section_title": pool.section_title(question["section"]),
        "subelement": question["subelement"],
        "text": question["text"],
        "choices": shown["choices"],
        "order": shown["order"],
        "figure": pool.figure_url(question),
        "refs": question.get("refs"),
        "remaining": len(queue),
        "card": {"seen": card["seen"], "correct": card["correct"],
                 "lapses": card["lapses"], "interval": card["interval"]}
        if card else None,
    })


@app.route("/api/answer", methods=["POST"])
def api_answer():
    body = request.get_json(force=True)
    pool = _pool_or_404(body.get("pool", ""))
    question = pool.by_id.get(body.get("question_id"))
    if not question:
        abort(400, "unknown question")

    order = body.get("order") or list(range(4))
    shown_index = body.get("chosen")
    chosen_original = order[shown_index] if shown_index is not None and \
        0 <= shown_index < len(order) else None
    correct = chosen_original == question["answer"]
    ms = body.get("ms")
    mode = body.get("mode", "drill")

    connection = conn()
    card = db.get_card(connection, pool.pool_id, question["id"])
    now = db.utcnow()
    was_due = bool(card and card["due"] and card["due"] <= now.isoformat())

    quality = srs.grade(correct, ms)
    fields = srs.schedule(card, quality, now)
    fields.update({
        "seen": (card["seen"] if card else 0) + 1,
        "correct": (card["correct"] if card else 0) + int(correct),
        "run": ((card["run"] if card else 0) + 1) if correct else 0,
        "last_ms": ms,
    })
    db.upsert_card(connection, pool.pool_id, question["id"], **fields)
    db.log_answer(connection, pool.pool_id, question["id"], question["section"],
                  correct, chosen_original, ms, mode)

    points = game.xp_for_answer(correct, ms, card, was_due)
    game.add_xp(connection, points)
    streak_days = game.touch_streak(connection)
    run, best_run = game.bump_run(connection, correct)
    total = connection.execute("SELECT COUNT(*) c FROM answer_log").fetchone()["c"]
    fresh = game.check_answer_achievements(
        connection, best_run, total, streak_days, datetime.now().hour)
    connection.commit()

    prof = db.get_profile(connection)
    return jsonify({
        "correct": correct,
        "answer_shown": order.index(question["answer"]),
        "explain": _explain(pool, question),
        "explanation": explain.for_question(
            pool, question, db.get_note(connection, pool.pool_id, question["id"])),
        "xp": points, "total_xp": prof["xp"], "rank": game.rank_for(prof["xp"]),
        "streak_days": streak_days, "run": run,
        "interval_days": fields["interval"],
        "achievements": fresh,
    })


def _explain(pool, question):
    """The context ELMER can honestly give: where this sits in the syllabus."""
    section = question["section"]
    bits = [f"{section} - {pool.section_title(section)}"]
    sub = pool.subelement_meta.get(question["subelement"])
    if sub:
        bits.append(f"{sub['code']} - {sub['title']}")
    if question.get("refs"):
        bits.append(f"FCC rule {question['refs']}")
    return bits


# --------------------------------------------------------------------------
# exam API
# --------------------------------------------------------------------------

@app.route("/api/exam/start", methods=["POST"])
def api_exam_start():
    body = request.get_json(force=True)
    pool = _pool_or_404(body.get("pool", ""))
    connection = conn()
    exam = exams.start(connection, pool.pool_id)
    log.info("exam %s started: %s, %d questions",
             exam["exam_id"], pool.pool_id, exam["total"])
    connection.execute("UPDATE exam SET detail = ? WHERE id = ?",
                       (json.dumps({"exam": exam}), exam["exam_id"]))
    connection.commit()
    client = dict(exam)
    client["items"] = [{k: v for k, v in item.items() if k != "answer"}
                       for item in exam["items"]]
    return jsonify(client)


@app.route("/api/exam/<int:exam_id>/submit", methods=["POST"])
def api_exam_submit(exam_id):
    body = request.get_json(force=True)
    connection = conn()
    row = connection.execute("SELECT * FROM exam WHERE id = ?", (exam_id,)).fetchone()
    if not row or not row["detail"]:
        abort(404)
    exam = json.loads(row["detail"])["exam"]
    result = exams.score(connection, exam_id, exam, body.get("responses", {}),
                         body.get("seconds", 0))

    # An exam is also study: fold every answer into the schedule.
    pool = get_pool(exam["pool_id"])
    for item, res in zip(exam["items"], result["results"]):
        question = pool.by_id[item["question_id"]]
        card = db.get_card(connection, pool.pool_id, question["id"])
        quality = srs.grade(res["correct"], None)
        fields = srs.schedule(card, quality)
        fields.update({
            "seen": (card["seen"] if card else 0) + 1,
            "correct": (card["correct"] if card else 0) + int(res["correct"]),
            "run": ((card["run"] if card else 0) + 1) if res["correct"] else 0,
        })
        db.upsert_card(connection, pool.pool_id, question["id"], **fields)
        db.log_answer(connection, pool.pool_id, question["id"], question["section"],
                      res["correct"], res["chosen"], None, "exam")
        # show the user what the right answer was
        res["answer_text"] = item["choices"][item["answer"]]
        res["chosen_text"] = (item["choices"][res["chosen"]]
                              if res["chosen"] is not None else None)
        res["text"] = item["text"]
        res["section_title"] = item["section_title"]

    points = 40 + 3 * result["score"] + (150 if result["passed"] else 0)
    game.add_xp(connection, points)
    game.touch_streak(connection)
    fresh = game.check_exam_achievements(
        connection, exam["pool_id"], result["passed"], result["perfect"])
    connection.commit()

    log.info("exam %s finished: %s %d/%d %s in %ss", exam_id, exam["pool_id"],
             result["score"], result["total"],
             "PASS" if result["passed"] else "fail", body.get("seconds", 0))
    prof = db.get_profile(connection)
    result["xp"] = points
    result["total_xp"] = prof["xp"]
    result["rank"] = game.rank_for(prof["xp"])
    result["achievements"] = fresh
    return jsonify(result)


# --------------------------------------------------------------------------
# misc API
# --------------------------------------------------------------------------

@app.route("/api/propagation")
def api_propagation():
    connection = conn()
    settings = db.get_profile(connection)["settings"]
    loc = settings.get("location") or {}
    snap = propagation.snapshot(lat=loc.get("lat"), lon=loc.get("lon"),
                                force=request.args.get("force") == "1")
    if not snap.get("ok"):
        log.warning("space weather fetch failed: %s", snap.get("error"))
    return jsonify(snap)


@app.route("/api/stats/<pool_id>")
def api_stats(pool_id):
    pool = _pool_or_404(pool_id)
    connection = conn()
    cards = db.cards_for_pool(connection, pool_id)
    stats = pool_stats(pool, cards, trials=2500)
    fresh = game.check_mastery_achievements(
        connection, stats["per_section"], stats["mastery"])
    connection.commit()
    return jsonify({
        "mastery": stats["mastery"], "readiness": stats["readiness"],
        "seen": stats["seen"], "unseen": stats["unseen"],
        "due_now": stats["due_now"], "achievements": fresh,
        "sections": [
            {"code": s["code"], "title": s["title"],
             "mastery": stats["per_section"].get(s["code"], 0.0)}
            for s in pool.sections],
    })


@app.route("/api/explain/<pool_id>/<question_id>")
def api_explain(pool_id, question_id):
    pool = _pool_or_404(pool_id)
    question = pool.by_id.get(question_id)
    if not question:
        abort(404)
    connection = conn()
    return jsonify(explain.for_question(
        pool, question, db.get_note(connection, pool_id, question_id)))


@app.route("/api/explain/<pool_id>")
def api_explain_section(pool_id):
    """Every explanation for one section, so the browser fetches once."""
    pool = _pool_or_404(pool_id)
    section = request.args.get("section")
    questions = pool.by_section.get(section) if section else None
    if not questions:
        abort(404)
    connection = conn()
    notes = db.notes_for_pool(connection, pool_id)
    return jsonify({q["id"]: explain.for_question(pool, q, notes.get(q["id"]))
                    for q in questions})


@app.route("/api/note", methods=["POST"])
def api_note():
    body = request.get_json(force=True)
    pool = _pool_or_404(body.get("pool", ""))
    question_id = body.get("question_id")
    if question_id not in pool.by_id:
        abort(400, "unknown question")
    saved = db.save_note(conn(), pool.pool_id, question_id, body.get("body", ""))
    return jsonify({"saved": True, "body": saved})


@app.route("/api/client-error", methods=["POST"])
def api_client_error():
    """Browser-side failures, reported so they land in the same log as the rest.

    A JavaScript error would otherwise only exist in a console nobody is
    looking at, and the page would just sit there looking broken.
    """
    body = request.get_json(force=True, silent=True) or {}
    log.error("BROWSER %s | %s | line %s | page %s | %s",
              body.get("kind", "error"), body.get("message"),
              body.get("line"), body.get("page"),
              (request.user_agent.string or "-")[:80])
    if body.get("stack"):
        log.debug("BROWSER stack:\n%s", str(body["stack"])[:4000])
    return jsonify({"logged": True})


@app.route("/api/settings", methods=["POST"])
def api_settings():
    body = request.get_json(force=True)
    connection = conn()
    settings = db.get_profile(connection)["settings"]
    if "callsign" in body:
        db.set_callsign(connection, body["callsign"] or "")
    if "location" in body:
        settings["location"] = body["location"]
    db.save_settings(connection, settings)
    return jsonify({"ok": True, **db.get_profile(connection)})


@app.template_filter("pct")
def _pct(value):
    return f"{100 * (value or 0):.0f}%"


@app.template_filter("fill")
def _fill(value):
    """Meter colour band: red below 50%, amber to 80%, green above."""
    value = value or 0
    return "fill-high" if value >= 0.80 else "fill-mid" if value >= 0.50 else "fill-low"


@app.template_filter("width")
def _width(value):
    return f"{100 * max(0.0, min(1.0, value or 0)):.1f}%"
