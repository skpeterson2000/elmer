"""ELMER - the web application.

Pages are server-rendered; the quiz and exam screens talk to a small JSON API so
answering never reloads the page.  The correct answer is never sent to the
browser before the user commits to a choice: the server hands out a shuffled
presentation plus its permutation, and resolves the real answer on submit.
"""
import hmac
import ipaddress
import json
import logging
import os
import random
import signal
import threading
from datetime import datetime
from pathlib import Path

from flask import (Flask, abort, g, jsonify, render_template, request,
                   send_from_directory)

from . import (bandpdf, bandplan, db, exams, explain, game, geocode, logs,
               propagation, ranks, regional, rfexposure, rfpdf, srs, terrain)
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
    """Use static/icon.* as the favicon if one has been dropped in.

    The URL carries the file's modification time, because browsers cache a
    favicon harder than they cache anything else on the page - Firefox keeps
    one until its profile is cleared.  Without this, replacing the icon leaves
    the old one in the tab and looks like the change simply did not work.
    """
    static = Path(app.static_folder)
    for name in ICON_NAMES:
        icon = static / name
        if icon.exists():
            return {"icon_file": name, "icon_v": int(icon.stat().st_mtime)}
    return {"icon_file": None, "icon_v": 0}


# Set by ./elmer.py --kiosk.  Off means /api/quit does not exist at all.
app.config["KIOSK"] = False
app.config["KIOSK_TOKEN"] = None


def _is_local(address):
    """True for a request that came from this machine itself."""
    try:
        return ipaddress.ip_address(address or "").is_loopback
    except ValueError:
        return False


@app.context_processor
def _kiosk():
    """The Exit button, and only on the screen the server is running on.

    The token is what authorises the shutdown, so it is rendered only for a
    loopback request.  A phone or laptop browsing in over the network gets a
    page with no button and no token in it, and cannot stop the server.
    """
    if not app.config["KIOSK"] or not _is_local(request.remote_addr):
        return {"kiosk_token": None}
    return {"kiosk_token": app.config["KIOSK_TOKEN"]}


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


STANDING_REFRESH_EVERY = 20     # answers, between background recomputes


def standing_for(connection, pool, stats=None):
    """Recompute one pool's rank standing and cache it."""
    if stats is None:
        stats = pool_stats(pool, db.cards_for_pool(connection, pool.pool_id),
                           trials=800)
    answered = connection.execute(
        "SELECT COUNT(*) c FROM answer_log WHERE pool_id = ?", (pool.pool_id,)
    ).fetchone()["c"]
    figures = {
        "answered": answered,
        "coverage": stats["seen"] / max(1, len(pool.questions)),
        "mastery": stats["mastery"],
        "pass_probability": stats["readiness"]["pass_probability"],
    }
    standing = ranks.standing(
        pool, figures,
        exams.history(connection, pool.pool_id, limit=ranks.ELMER_RECENT),
        window=db.maintenance_window(connection, pool.pool_id,
                                     ranks.MAINTENANCE_WINDOW))
    cache = db.kv_get(connection, "standings", {}) or {}
    previous = cache.get(pool.pool_id, {}).get("step_name")
    cache[pool.pool_id] = standing
    db.kv_set(connection, "standings", cache)
    if previous and previous != standing["step_name"]:
        log.info("rank change: %s %s -> %s", pool.pool_id, previous,
                 standing["step_name"])
    return standing


def all_standings(connection, refresh=False):
    """Cached standings for every pool, in track order."""
    cache = db.kv_get(connection, "standings", {}) or {}
    out = []
    for pool_id, pool in load_pools().items():
        if refresh or pool_id not in cache:
            out.append(standing_for(connection, pool))
        else:
            out.append(cache[pool_id])
    return out


def qth_for(connection, profile):
    """The saved QTH, with a friendly name filled in once and remembered.

    A QTH entered as a bare grid square has no name to show, so the first time
    it is needed the coordinates are reverse-geocoded and the result stored.
    Failure is fine - the grid square still works on its own.
    """
    place = dict(profile["settings"].get("location") or {})
    if not place.get("lat") or place.get("short"):
        return place
    try:
        named = geocode.reverse(place["lat"], place["lon"])
    except Exception:
        named = None
    if not named:
        return place
    place["short"] = named["short"]
    place["name"] = named["name"]
    place.setdefault("kind", named.get("kind"))
    place.setdefault("grid", named["grid"])
    settings = profile["settings"]
    settings["location"] = place
    db.save_settings(connection, settings)
    log.info("named the saved QTH %s as %s", place.get("grid"), place["short"])
    return place


def profile_block(connection):
    prof = db.get_profile(connection)
    standings = all_standings(connection)
    tracks = ranks.overall(standings)
    answered = connection.execute("SELECT COUNT(*) c FROM answer_log").fetchone()["c"]
    today_count = connection.execute(
        "SELECT COUNT(*) c FROM answer_log WHERE day = ?", (db.today(),)
    ).fetchone()["c"]
    return {"profile": prof, "standings": standings, "tracks": tracks,
            "answered": answered, "today": today_count,
            "achievements": game.earned(connection),
            "all_achievements": game.ACHIEVEMENTS,
            "rank_rules": {"current_days": ranks.CURRENT_DAYS,
                           "grace_days": ranks.GRACE_DAYS},
            "qth": qth_for(connection, prof)}


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
        standing_for(connection, pool, stats)
        summary.append({
            "pool": pool, "mastery": stats["mastery"],
            "readiness": stats["readiness"], "seen": stats["seen"],
            "due_now": stats["due_now"], "total": len(pool.questions),
        })
    connection.commit()
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
    standing = standing_for(connection, pool, stats)
    connection.commit()

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
        exams=exams.history(connection, pool_id), standing=standing,
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


@app.route("/bandplan")
def bandplan_page():
    connection = conn()
    profile = db.get_profile(connection)
    return render_template(
        "bandplan.html", bands=bandplan.BANDS, kinds=bandplan.KINDS,
        classes=bandplan.CLASSES,
        licence_class=profile["settings"].get("licence_class", "Technician"),
        coordinators=regional.available(),
        state=profile["settings"].get("state", ""),
        **profile_block(connection))


@app.route("/api/bandplan")
def api_bandplan():
    """Privileges and activity for every band, for one licence class."""
    licence = request.args.get("class", "Technician")
    if licence not in bandplan.CLASSES:
        abort(400, "unknown licence class")
    return jsonify({
        "class": licence, "kinds": bandplan.KINDS,
        "bands": [{
            **band,
            "privileges": bandplan.privileges_for(band["name"], licence),
            "gaps": bandplan.gaps_for(band["name"], licence),
            "activity": [{"low": a, "high": b, "kind": k, "label": l}
                         for a, b, k, l in bandplan.activity_for(band["name"])],
        } for band in bandplan.BANDS],
        "channels_60m": bandplan.CHANNELS_60M,
    })


@app.route("/api/bandplan/regional/<state>")
def api_bandplan_regional(state):
    """The local coordinator's plan. 503 when it cannot be reached."""
    data = regional.plan(state, refresh=request.args.get("refresh") == "1")
    if not data:
        return jsonify({"ok": False,
                        "error": f"no coordinator plan available for {state}"}), 503
    return jsonify({"ok": True, **data})


@app.route("/api/bandplan/pdf", methods=["POST"])
def api_bandplan_pdf():
    from flask import Response
    body = request.get_json(force=True) or {}
    licence = body.get("class", "Technician")
    if licence not in bandplan.CLASSES:
        abort(400, "unknown licence class")
    bands = body.get("bands") or [b["name"] for b in bandplan.BANDS]
    state = (body.get("state") or "").upper()
    plan = regional.plan(state) if state else None
    pdf = bandpdf.build(bands, licence, plan)
    name = f"band-plan-{licence.lower()}{'-' + state.lower() if state else ''}.pdf"
    log.info("band chart PDF: %s, %d bands, regional=%s", licence, len(bands), state or "none")
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Content-Length": str(len(pdf))})


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

    # The lower rungs move with coverage and mastery, so refresh occasionally
    # rather than on every answer - the Monte Carlo is too costly per keystroke.
    cache = db.kv_get(connection, "standings", {}) or {}
    before = (cache.get(pool.pool_id) or {}).get("step_name")
    counter = db.kv_get(connection, "answers_since_standing", 0) + 1
    promoted = None
    if counter >= STANDING_REFRESH_EVERY or pool.pool_id not in cache:
        db.kv_set(connection, "answers_since_standing", 0)
        now_standing = standing_for(connection, pool)
        if before and now_standing["step_name"] != before:
            promoted = now_standing
    else:
        db.kv_set(connection, "answers_since_standing", counter)
    connection.commit()

    prof = db.get_profile(connection)
    return jsonify({
        "correct": correct,
        "answer_shown": order.index(question["answer"]),
        "explain": _explain(pool, question),
        "explanation": explain.for_question(
            pool, question, db.get_note(connection, pool.pool_id, question["id"])),
        "xp": points, "total_xp": prof["xp"], "promoted": promoted,
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
    cache = db.kv_get(connection, "standings", {}) or {}
    before = (cache.get(pool.pool_id) or {}).get("step_name")
    standing = standing_for(connection, pool)
    connection.commit()

    prof = db.get_profile(connection)
    result["xp"] = points
    result["total_xp"] = prof["xp"]
    result["standing"] = standing
    result["promoted"] = standing if before and standing["step_name"] != before else None
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
    standing = standing_for(connection, pool, stats)
    fresh = game.check_mastery_achievements(
        connection, stats["per_section"], stats["mastery"])
    connection.commit()
    return jsonify({
        "mastery": stats["mastery"], "readiness": stats["readiness"],
        "seen": stats["seen"], "unseen": stats["unseen"],
        "due_now": stats["due_now"], "achievements": fresh,
        "standing": standing,
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


def _rf_payload(body):
    """Normalise a posted evaluation request into station + cases."""
    connection = conn()
    profile = db.get_profile(connection)
    qth = qth_for(connection, profile)
    station = body.get("station") or {}
    station.setdefault("callsign", profile["callsign"] or "")
    station.setdefault("location", qth.get("short") or qth.get("name") or "")
    station.setdefault("grid", qth.get("grid") or "")
    station.setdefault("date", db.today())
    cases = [c for c in (body.get("cases") or []) if c.get("frequency_mhz")]
    return station, cases


@app.route("/api/rf-exposure", methods=["POST"])
def api_rf_exposure():
    """Evaluate a station against the MPE limits."""
    station, cases = _rf_payload(request.get_json(force=True) or {})
    if not cases:
        return jsonify({"error": "no bands to evaluate", "cases": []}), 400
    try:
        return jsonify(rfexposure.evaluate(station, cases))
    except (TypeError, ValueError) as exc:
        log.warning("RF exposure evaluation rejected: %s", exc)
        abort(400, "check the numbers entered")


@app.route("/api/rf-exposure/pdf", methods=["POST"])
def api_rf_exposure_pdf():
    """The same evaluation as a station record to print and post."""
    from flask import Response
    station, cases = _rf_payload(request.get_json(force=True) or {})
    if not cases:
        abort(400, "no bands to evaluate")
    evaluation = rfexposure.evaluate(station, cases)
    pdf = rfpdf.build(evaluation, station)
    call = (station.get("callsign") or "station").replace("/", "-")
    name = f"RF-exposure-{call}-{station['date']}.pdf"
    log.info("RF exposure PDF generated for %s: %d bands, compliant=%s",
             call, len(cases), evaluation["compliant"])
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Content-Length": str(len(pdf)),
    })


@app.route("/api/geocode")
def api_geocode():
    """Places matching a name, for the location boxes.

    Accepts a grid square or a lat,lon pair too, so one input can take whatever
    the operator happens to know.
    """
    query = request.args.get("q", "")
    if not query.strip():
        return jsonify({"results": []})
    direct = geocode.resolve(query, allow_lookup=False)
    if direct:
        return jsonify({"results": [direct]})
    try:
        results = geocode.search(query, limit=int(request.args.get("limit", 6)))
    except ValueError:
        results = geocode.search(query)
    if not results:
        log.info("geocode found nothing for %r", query[:80])
    return jsonify({"results": results})


@app.route("/api/reverse-geocode")
def api_reverse_geocode():
    """Name the place at these coordinates - used after browser geolocation."""
    try:
        lat = float(request.args["lat"]); lon = float(request.args["lon"])
    except (KeyError, ValueError):
        abort(400, "need lat and lon")
    place = geocode.reverse(lat, lon)
    if not place:
        place = {"name": f"{lat:.4f}, {lon:.4f}", "short": f"{lat:.4f}, {lon:.4f}",
                 "kind": "coordinates", "lat": lat, "lon": lon,
                 "grid": geocode.to_grid(lat, lon)}
    return jsonify(place)


@app.route("/api/terrain")
def api_terrain():
    """Ground profile between two points, for the path tool.

    Returns 503 rather than an error when terrain cannot be reached, so the
    page can fall back to the smooth-earth calculation and say so.
    """
    try:
        lat1 = float(request.args["lat1"]); lon1 = float(request.args["lon1"])
        lat2 = float(request.args["lat2"]); lon2 = float(request.args["lon2"])
        samples = int(request.args.get("samples", 80))
    except (KeyError, ValueError):
        abort(400, "need lat1, lon1, lat2, lon2")

    data = terrain.profile(lat1, lon1, lat2, lon2, samples)
    if data is None:
        log.warning("terrain lookup failed for %.4f,%.4f -> %.4f,%.4f",
                    lat1, lon1, lat2, lon2)
        return jsonify({"ok": False,
                        "error": "terrain data unavailable - showing smooth-earth "
                                 "results only"}), 503
    return jsonify({"ok": True, **data})


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
    for key in ("licence_class", "state"):
        if key in body:
            settings[key] = body[key]
    if "location" in body:
        place = body["location"] or {}
        if place.get("lat") is not None and place.get("lon") is not None:
            place.setdefault("grid", geocode.to_grid(place["lat"], place["lon"]))
        settings["location"] = place
        log.info("QTH set to %s (%s)", place.get("grid"), place.get("short") or "unnamed")
    db.save_settings(connection, settings)
    return jsonify({"ok": True, **db.get_profile(connection)})


@app.route("/api/quit", methods=["POST"])
def api_quit():
    """Stop the server, for the Exit button in kiosk mode.

    Three things have to hold: the server was started with --kiosk, the request
    came from this machine, and it carries the token minted at startup.  The
    server binds every interface by default, so without those checks anyone on
    the network could turn the study session off.
    """
    if not app.config["KIOSK"]:
        abort(404)
    if not _is_local(request.remote_addr):
        log.warning("quit refused: request from %s", request.remote_addr)
        abort(403)
    expected = app.config["KIOSK_TOKEN"] or ""
    supplied = (request.get_json(silent=True) or {}).get("token", "")
    if not expected or not hmac.compare_digest(str(supplied), expected):
        log.warning("quit refused: bad token")
        abort(403)

    log.info("quit requested from the kiosk browser")
    # Answer first, then interrupt the main thread: ./elmer.py closes the
    # browser and exits from there, so the shutdown path is the same one
    # Ctrl+C already takes.
    threading.Timer(0.3, lambda: os.kill(os.getpid(), signal.SIGINT)).start()
    return jsonify({"ok": True})


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
