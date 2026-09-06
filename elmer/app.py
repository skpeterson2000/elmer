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
from datetime import datetime, timedelta
from pathlib import Path

from urllib.parse import urlsplit

from flask import (Flask, abort, g, jsonify, render_template, request,
                   send_from_directory)

from . import (antenna_advice, bandpdf, bandplan, callsign, cw, db, exams,
               explain, game, geocode, ionosonde, logs, propagation, ranks,
               patterns, places, regional, rfexposure, rfpdf, smith, srs,
               bugreport, gps, reachout, repeaters, terrain,
               update)
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


USER_COOKIE = "elmer_user"
COOKIE_YEARS = 5 * 365 * 24 * 3600


def _wanted_user():
    """Who this browser last said it was.  None means "whoever is first".

    The current user rides in a cookie rather than on the server, so the unit
    in the shack and a phone on the sofa can be two different people at the
    same time.  It is not a credential and is not treated as one: an unknown
    or missing value simply falls back to the first user on the unit.
    """
    try:
        return int(request.cookies.get(USER_COOKIE, ""))
    except (TypeError, ValueError):
        return None


def conn():
    if "db" not in g:
        g.db = db.connect(user_id=_wanted_user())
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
# Raised by the updater: ./elmer.py reads it on the way out and re-execs
# instead of stopping.
app.config["RESTART"] = False


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
        "SELECT COUNT(*) c FROM answer_log WHERE user_id = ? AND pool_id = ?",
        (connection.user_id, pool.pool_id)
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
    """Where the station is: the GPS if one is talking, else the saved QTH.

    A QTH entered as a bare grid square has no name to show, so the first time
    it is needed the coordinates are reverse-geocoded and the result stored.
    Failure is fine - the grid square still works on its own.

    A live fix outranks the typed square, because these Pis travel and every
    answer about reach, bearings and exposure is an answer about a place. The
    typed square is not thereby wasted: it is what the program runs on in a
    field with no GPS and no network, which is why it is asked for.
    """
    saved = _saved_qth(connection, profile)
    if not gps.enabled(connection):
        return saved
    live = gps.place(connection)
    if not live:
        return saved
    # Near home the saved QTH has a name on it and the fix does not, so keep
    # the name and take the coordinates. Away from it, a grid square is the
    # honest label: nothing here can reverse-geocode a lay-by off-grid.
    if saved.get("lat") is not None:
        km, _ = terrain.great_circle(saved["lat"], saved["lon"],
                                     live["lat"], live["lon"])
        if km <= 10 and saved.get("short"):
            live = dict(live, short=saved["short"],
                        name=saved.get("name") or saved["short"])
    return live


def _saved_qth(connection, profile):
    """The QTH somebody typed in, named once and remembered."""
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
    answered = connection.execute(
        "SELECT COUNT(*) c FROM answer_log WHERE user_id = ?",
        (connection.user_id,)).fetchone()["c"]
    today_count = connection.execute(
        "SELECT COUNT(*) c FROM answer_log WHERE user_id = ? AND day = ?",
        (connection.user_id, db.today())
    ).fetchone()["c"]
    return {"profile": prof, "standings": standings, "tracks": tracks,
            "answered": answered, "today": today_count,
            "achievements": game.earned(connection),
            "all_achievements": game.ACHIEVEMENTS,
            "rank_rules": {"current_days": ranks.CURRENT_DAYS,
                           "grace_days": ranks.GRACE_DAYS},
            "qth": qth_for(connection, prof),
            "licence": prof["settings"].get("licence") or {}}


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
    profile = db.get_profile(connection)
    answered = connection.execute(
        "SELECT COUNT(*) c FROM answer_log").fetchone()["c"]
    first_run = {
        "show": answered == 0,
        "callsign": bool(profile["callsign"]),
        "qth": bool((profile["settings"].get("location") or {}).get("lat")),
    }
    return render_template("home.html", summary=summary, greeting=greeting(),
                           first_run=first_run,
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
        licence_class=profile["settings"].get("licence_class")
                       or (profile["settings"].get("licence") or {}).get("licence_class")
                       or "Technician",
        coordinators=regional.available(),
        state=profile["settings"].get("state", ""),
        **profile_block(connection))


def _usable(low, high, kind, band_name, licence):
    """What this class may do with one activity segment, and why."""
    return bandplan.usable_answer(band_name, licence, low, high, kind)


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
            "activity": [
                {"low": a, "high": b, "kind": k, "label": l,
                 "you": _usable(a, b, k, band["name"], licence)}
                for a, b, k, l in bandplan.activity_for(band["name"])],
        } for band in bandplan.BANDS],
        "channels_60m": bandplan.CHANNELS_60M,
    })


@app.route("/out")
def reachout_page():
    """What to try, from here, with what is in the vehicle."""
    connection = conn()
    profile = db.get_profile(connection)
    settings = profile["settings"]
    return render_template(
        "reachout.html", gear=reachout.GEAR, classes=bandplan.CLASSES,
        licence_class=settings.get("licence_class")
                      or (settings.get("licence") or {}).get("licence_class")
                      or "Technician",
        assumed=["ht"], **profile_block(connection))


@app.route("/api/ways-out")
def api_ways_out():
    """Every avenue worth trying from where the station is now."""
    connection = conn()
    profile = db.get_profile(connection)
    place = qth_for(connection, profile)
    if place.get("lat") is None:
        return jsonify({"ways": [], "coverage": None, "qth": "",
                        "located": False,
                        "note": "ELMER does not know where you are yet, and "
                                "every answer on this page is an answer about "
                                "a place. Set a QTH on the propagation page - "
                                "a grid square is enough - or let a GPS "
                                "answer."})
    gear = [g for g in (request.args.get("gear") or "").split(",")
            if g in reachout.GEAR]
    licence = request.args.get("licence") or \
        profile["settings"].get("licence_class") or "Technician"
    answer = reachout.summary(place["lat"], place["lon"], gear, licence,
                              conn=connection)
    answer["qth"] = place.get("short") or place.get("grid") or ""
    answer["qth_source"] = place.get("source") or "saved"
    answer["located"] = True
    return jsonify(answer)


@app.route("/api/pattern")
def api_pattern():
    """Where the energy goes, and how much band you get - for one antenna."""
    kind = request.args.get("type", "dipole")
    try:
        mhz = float(request.args.get("mhz", "14.2"))
        height_ft = float(request.args.get("height", "35"))
    except ValueError:
        abort(400)
    if kind not in patterns.ANTENNA_Q or not 0.1 <= mhz <= 3000:
        abort(400)
    lam_ft = 983.571 / mhz
    height_wl = max(0.0, height_ft / lam_ft)
    try:
        heading = float(request.args.get("heading", "0")) % 360
    except ValueError:
        heading = 0.0
    try:
        slope = max(0.0, min(89.0, float(request.args.get("slope", "0"))))
    except ValueError:
        slope = 0.0
    spec = patterns.ANTENNA_Q[kind]

    # What this antenna can actually work decides who its neighbours are. An
    # NVIS wire does not reach Europe, so putting Europe on its compass would
    # invite somebody to turn an antenna to chase a contact it cannot make.
    nvis = request.args.get("nvis") in ("1", "true", "yes")
    use = request.args.get("use") or antenna_advice.default_use(mhz)

    connection = conn()
    place = qth_for(connection, db.get_profile(connection))
    # The F2 layer sits lower by day than by night, and that changes how far
    # one hop reaches - so the answer depends on the hour where the station
    # is, not on the server's idea of noon.
    day = reachout.daytime(place["lon"]) if place.get("lon") is not None else True
    span = patterns.qualify(
        patterns.reach(kind, use, mhz, height_ft, nvis, slope, day))

    dx = []
    if place.get("lat") is not None and place.get("lon") is not None:
        dx = patterns.targets(place["lat"], place["lon"], kind, heading, span)
        # Ask OpenStreetMap what is really around this QTH, once, for next
        # time. In the background: a pattern is not worth waiting on a web
        # service for, and the bundled list answers well enough meanwhile.
        if span.get("radius_km"):
            places.refresh_in_background(place["lat"], place["lon"],
                                         span["radius_km"])

    # On FM above 50 MHz the repeater is what does the reaching, and saying so
    # without naming one was the least useful true sentence in the program.
    reps, reps_from, coverage = [], None, None
    if use in ("local", "digital") and place.get("lat") is not None:
        reps, reps_from = repeaters.nearby(place["lat"], place["lon"], mhz,
                                           height_ft=height_ft, conn=connection)
        coverage = repeaters.coverage(place["lat"], place["lon"])
        for row in reps:
            field = patterns.field_at(kind, row["bearing"], heading)
            row["field"] = round(field, 4)
            row["db"] = patterns.db(field)

    return jsonify({
        "type": kind, "mhz": mhz, "height_ft": height_ft,
        "height_wl": round(height_wl, 3), "heading": heading,
        "shape": spec["shape"], "q": spec["q"], "fed": spec["fed"],
        "elevation": patterns.elevation(kind, height_wl, slope_deg=slope),
        "azimuth": patterns.azimuth(kind, heading),
        "main_lobe_deg": patterns.main_lobe(kind, height_wl, slope),
        "slope": slope,
        "swr": patterns.swr_curve(kind, mhz),
        "bandwidth": patterns.usable_bandwidth(kind, mhz),
        "dx": dx, "qth": place.get("grid") or place.get("short") or "",
        "qth_source": place.get("source") or "saved",
        "qth_age_s": place.get("age_s"),
        "reach": span, "use": use,
        "daytime": day,
        # When the compass comes back empty, an empty compass is not the whole
        # answer - what to do instead is.
        "instead": (patterns.advise_empty(span, mhz, kind, height_ft, use,
                                          bundled=span.get("places_from") == "bundled")
                    if not dx and not reps and span["kind"] != "satellite"
                    else []),
        "repeaters": reps, "repeaters_from": reps_from,
        "repeater_coverage": coverage,
        "repeater_radius_km": round(repeaters.horizon_km(height_ft)),
    })


@app.route("/api/smith")
def api_smith():
    """One antenna on one feedline, as the chart sees it."""
    try:
        r = float(request.args.get("r", "50"))
        x = float(request.args.get("x", "0"))
        mhz = float(request.args.get("mhz", "14.2"))
        feet = float(request.args.get("feet", "100"))
        watts = float(request.args.get("watts", "100"))
    except ValueError:
        abort(400)
    line = request.args.get("line", "rg213")
    if line not in smith.LINES:
        abort(400)
    if not (0.1 <= mhz <= 3000 and 0 <= feet <= 5000 and r >= 0 and watts > 0):
        abort(400)
    return jsonify(smith.analyse(r, x, line, mhz, feet, watts))


@app.route("/api/antenna-advice")
def api_antenna_advice():
    """What to put up here, and why - for a licensee who has not built one yet."""
    try:
        mhz = float(request.args.get("mhz", ""))
    except ValueError:
        abort(400)
    if not 0.1 <= mhz <= 300000:
        abort(400)
    return jsonify(antenna_advice.recommend(
        mhz, use=request.args.get("use"), kind=request.args.get("kind")))


@app.route("/api/nifog")
def api_nifog():
    """The cached interoperability channels. Never fetches on a page load."""
    from elmer import nifog
    record = nifog.load()
    if not record:
        return jsonify({"have": False, "page": nifog.SAFECOM_PAGE})
    return jsonify({"have": True, "version": record.get("version"),
                    "dated": record.get("dated"), "fetched": record.get("fetched"),
                    "url": record.get("url"), "count": record.get("count"),
                    "bands": nifog.by_band(record), "page": nifog.SAFECOM_PAGE})


@app.route("/api/privileges")
def api_privileges():
    """What may actually be transmitted here, by this class, on this frequency.

    ELMER already holds 97.301 and 97.305 in full; this is what lets the rest
    of the program act on them rather than merely display them. A tool that
    knows a General may not use 14.200 and lets one be entered anyway is not
    neutral - it has quietly endorsed the operation.
    """
    try:
        mhz = float(request.args.get("mhz", ""))
    except ValueError:
        abort(400)
    connection = conn()
    settings = db.get_profile(connection)["settings"]
    licence_class = (request.args.get("class")
                     or settings.get("licence_class") or "")
    result = bandplan.privilege_at(mhz, licence_class)

    modes = []
    for key, (label, _duty) in rfexposure.MODE_DUTY.items():
        emission = rfexposure.MODE_EMISSION.get(key)
        if not result["in_band"] or not licence_class:
            permitted, why = None, None          # nothing claimed either way
        elif not result["allowed"]:
            permitted, why = False, "not in this class's part of the band"
        elif emission is None:
            permitted, why = True, None          # tuning, wherever you may talk
        elif emission in result["emissions"]:
            permitted, why = True, None
        else:
            permitted = False
            why = (bandplan.EMISSION_LABELS.get(emission, emission)
                   + " is not permitted in this segment")
        caution = None
        # Legal by emission category is not the same as legal by bandwidth.
        if key == "fm" and result["in_band"] and mhz < 29.0:
            caution = ("FM below 29 MHz is outside normal practice and the "
                       "bandwidth rules - check before relying on it")
        modes.append({"key": key, "label": label, "emission": emission,
                      "permitted": permitted, "why": why, "caution": caution})

    result["modes"] = modes
    result["known_class"] = licence_class in bandplan.CLASSES
    result["classes"] = bandplan.CLASSES
    return jsonify(result)


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
    if body.get("layout") == "card":
        pdf = bandpdf.build_card(licence, {"callsign": profile_callsign()})
    else:
        pdf = bandpdf.build(bands, licence, plan,
                            interop=bool(body.get("interop")))
    name = f"band-plan-{licence.lower()}{'-' + state.lower() if state else ''}.pdf"
    log.info("band chart PDF: %s, %d bands, regional=%s", licence, len(bands), state or "none")
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Content-Length": str(len(pdf))})


@app.route("/cw")
def cw_page():
    connection = conn()
    profile = db.get_profile(connection)
    settings = profile["settings"].get("cw") or {}
    return render_template(
        "cw.html", kinds=cw.KINDS, koch_order=cw.KOCH_ORDER,
        cw_settings=settings, progress=db.cw_progress(connection),
        meanings=cw.MEANINGS, **profile_block(connection))


@app.route("/api/cw/practice")
def api_cw_practice():
    """A block of practice text, plus the timing to send it with."""
    kind = request.args.get("kind", "koch")
    try:
        count = max(1, min(60, int(request.args.get("count", 5))))
        lesson = max(2, min(len(cw.KOCH_ORDER), int(request.args.get("lesson", 10))))
        wpm = max(3.0, min(60.0, float(request.args.get("wpm", 20))))
        effective = max(3.0, min(wpm, float(request.args.get("effective", wpm))))
    except ValueError:
        abort(400, "check the numbers")
    call = db.get_profile(conn())["callsign"] or None
    text = cw.practice(kind, count, lesson, seed=None, callsign=call)[0]
    return jsonify({
        "kind": kind, "text": text, "groups": cw.encode(text),
        "timing": cw.timing(wpm, effective),
        "lesson_chars": cw.koch_set(lesson) if kind == "koch" else None,
        "meanings": {w: cw.MEANINGS[w] for w in set(text.split())
                     if w in cw.MEANINGS},
    })


@app.route("/api/cw/encode")
def api_cw_encode():
    text = request.args.get("text", "")
    try:
        wpm = max(3.0, min(60.0, float(request.args.get("wpm", 20))))
        effective = max(3.0, min(wpm, float(request.args.get("effective", wpm))))
    except ValueError:
        abort(400, "check the numbers")
    return jsonify({"text": text.upper(), "groups": cw.encode(text),
                    "timing": cw.timing(wpm, effective)})


@app.route("/api/cw/result", methods=["POST"])
def api_cw_result():
    """Record a copy session, per character."""
    body = request.get_json(force=True) or {}
    per_char = body.get("per_char") or {}
    if not isinstance(per_char, dict):
        abort(400, "per_char must be an object")
    connection = conn()
    db.cw_record(connection, per_char)
    settings = db.get_profile(connection)["settings"]
    if body.get("settings"):
        settings["cw"] = body["settings"]
        db.save_settings(connection, settings)
    total = sum(v.get("sent", 0) for v in per_char.values())
    hit = sum(v.get("copied", 0) for v in per_char.values())
    log.info("CW copy session: %d characters, %d%% copied", total,
             round(100 * hit / total) if total else 0)
    return jsonify({"ok": True, "progress": db.cw_progress(connection)})


@app.route("/lab")
def lab():
    return render_template("lab.html", **profile_block(conn()))


# --------------------------------------------------------------------------
# leaving ELMER
# --------------------------------------------------------------------------

def _external_url(raw):
    """An off-site http(s) URL, or None if it is not one we will send anyone to."""
    parts = urlsplit((raw or "").strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return parts.geturl()


def _internal_path(raw):
    """A path back into ELMER, or "/" if it is anything else.

    Only a single leading slash will do.  "//host" and "/\\host" are both read
    by browsers as a protocol-relative address, which would turn the Back
    button into a way off the machine - the exact thing this page exists to
    prevent.
    """
    path = (raw or "").strip()
    if not path.startswith("/") or path[:2] in ("//", "/\\"):
        return "/"
    return path


@app.route("/away")
def away():
    """The step between ELMER and an off-site link.

    In kiosk mode the browser has no back button, so following a link straight
    out to the FCC would strand the operator there with no way back and no way
    to stop the program.  This page stays inside ELMER - Exit button and all -
    says where the link goes, and opens it in a window that can be closed.
    """
    url = _external_url(request.args.get("url"))
    if not url:
        abort(400)
    return render_template("away.html", url=url,
                           host=urlsplit(url).netloc,
                           back=_internal_path(request.args.get("from")),
                           **profile_block(conn()))


@app.route("/api/open-external", methods=["POST"])
def api_open_external():
    """Open an off-site link in an ordinary window beside the kiosk.

    Guarded exactly as /api/quit is: kiosk mode, this machine, and the token
    minted at startup.  Otherwise a page fetched over the LAN could make the
    machine in the shack open arbitrary windows.
    """
    if not app.config["KIOSK"]:
        abort(404)
    if not _is_local(request.remote_addr):
        log.warning("open-external refused: request from %s", request.remote_addr)
        abort(403)
    body = request.get_json(silent=True) or {}
    expected = app.config["KIOSK_TOKEN"] or ""
    if not expected or not hmac.compare_digest(str(body.get("token", "")), expected):
        log.warning("open-external refused: bad token")
        abort(403)
    url = _external_url(body.get("url"))
    if not url:
        abort(400)

    from . import kiosk
    return jsonify({"ok": True, "opened": kiosk.open_window(url)})


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
    total = connection.execute(
        "SELECT COUNT(*) c FROM answer_log WHERE user_id = ?",
        (connection.user_id,)).fetchone()["c"]
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
    row = connection.execute("SELECT * FROM exam WHERE id = ? AND user_id = ?",
                             (exam_id, connection.user_id)).fetchone()
    if not row or not row["detail"]:
        abort(404)
    stored = json.loads(row["detail"])
    if "exam" not in stored:
        # Scored by an earlier build that overwrote the questions. The result is
        # on record, so hand that back rather than failing on a resubmit.
        if row["finished"] and row["score"] is not None:
            log.info("exam %s already scored; returning the recorded result", exam_id)
            return jsonify({
                "score": row["score"], "total": row["total"],
                "pass_mark": get_pool(row["pool_id"]).pass_mark,
                "passed": bool(row["passed"]), "seconds": row["seconds"] or 0,
                "percent": round(100 * row["score"] / row["total"], 1),
                "breakdown": stored.get("breakdown", []),
                "results": stored.get("results", []),
                "perfect": row["score"] == row["total"],
                "already_scored": True, "xp": 0, "achievements": [],
                "total_xp": db.get_profile(connection)["xp"],
            })
        abort(404)
    exam = stored["exam"]
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
    else:
        # Earned by actually seeing conditions, not by the page rendering.
        if game.award(connection, ["propagation"]):
            connection.commit()
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


def profile_callsign():
    return db.get_profile(conn())["callsign"] or ""


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
    # The licence class comes from the profile, so the evaluation can say when
    # the operation it is evaluating would not be permitted in the first place.
    station.setdefault("licence_class",
                       profile["settings"].get("licence_class") or "")
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
    except rfexposure.InvalidCase as exc:
        log.info("RF exposure input refused: %s", exc)
        return jsonify({"error": str(exc), "cases": []}), 400
    except (TypeError, ValueError) as exc:
        log.warning("RF exposure evaluation rejected: %s", exc)
        return jsonify({"error": "check the numbers entered", "cases": []}), 400


@app.route("/api/rf-exposure/pdf", methods=["POST"])
def api_rf_exposure_pdf():
    """The same evaluation as a station record to print and post."""
    from flask import Response
    station, cases = _rf_payload(request.get_json(force=True) or {})
    if not cases:
        abort(400, "no bands to evaluate")
    try:
        evaluation = rfexposure.evaluate(station, cases)
    except rfexposure.InvalidCase as exc:
        log.info("RF exposure PDF refused: %s", exc)
        abort(400, str(exc))
    pdf = rfpdf.build(evaluation, station)
    call = (station.get("callsign") or "station").replace("/", "-")
    name = f"RF-exposure-{call}-{station['date']}.pdf"
    log.info("RF exposure PDF generated for %s: %d bands, compliant=%s",
             call, len(cases), evaluation["compliant"])
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Content-Length": str(len(pdf)),
    })


@app.route("/api/callsign/<call>")
def api_callsign(call):
    """Look up a US amateur licence. 503 when the lookup cannot be reached."""
    found = callsign.lookup(call, refresh=request.args.get("refresh") == "1")
    if found is None:
        return jsonify({"ok": False,
                        "error": "licence lookup unavailable - check the "
                                 "callsign, or the network"}), 503
    return jsonify({"ok": True, **found})


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


@app.route("/api/ionosonde")
def api_ionosonde():
    """What the ionosonde network is measuring, and the closest one to you.

    This is the honest answer to where the F2 layer is: somebody points a radar
    straight up and times the echo. 503 when the network cannot be reached, so
    the tools fall back to a typical height and say they are doing so.
    """
    connection = conn()
    qth = qth_for(connection, db.get_profile(connection))
    force = request.args.get("refresh") == "1"
    try:
        lat = float(request.args.get("lat", qth.get("lat")))
        lon = float(request.args.get("lon", qth.get("lon")))
    except (TypeError, ValueError):
        lat = lon = None

    overview = ionosonde.spread(force)
    if overview is None:
        log.warning("ionosonde network unreachable")
        return jsonify({"ok": False, "typical": ionosonde.TYPICAL,
                        "error": "no ionosonde data reachable"}), 503
    closest = ionosonde.nearest(lat, lon) if lat is not None else None
    return jsonify({"ok": True, "spread": overview, "nearest": closest,
                    "typical": ionosonde.TYPICAL,
                    "have_qth": lat is not None})


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


def _adopt_licence(connection, call, settings=None):
    """Record a callsign on the current user and read its licence.

    A callsign is enough to know the licence class and when it expires, so
    there is no reason to make the operator tell us separately - and from here
    on it is also what ELMER calls them.
    """
    save = settings is None
    db.set_callsign(connection, call or "")
    settings = db.get_profile(connection)["settings"] if save else settings
    found = callsign.lookup(call) if call else None
    if found and found.get("found"):
        settings["licence"] = found
        if found.get("licence_class"):
            settings["licence_class"] = found["licence_class"]
        log.info("licence for %s: %s, expires %s (%s)", found["callsign"],
                 found.get("licence_class") or found.get("type"),
                 found.get("expires"), found["status"]["state"])
    elif found is not None:
        settings["licence"] = found
    elif call:
        log.warning("licence lookup unavailable for %s", call)
    if save:
        db.save_settings(connection, settings)
    return settings


@app.route("/api/settings", methods=["POST"])
def api_settings():
    body = request.get_json(force=True)
    connection = conn()
    settings = db.get_profile(connection)["settings"]
    if "callsign" in body:
        settings = _adopt_licence(connection, body["callsign"] or "", settings)
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


# --------------------------------------------------------------------------
# who is playing
# --------------------------------------------------------------------------
# Switching user is a choice, not a sign-in: there is nothing here worth
# protecting and a password on a family appliance is a barrier to the eight
# year old, not to anyone else.  Removing somebody is the exception - that
# destroys their work, so it has to be done at the unit itself.

def _user_block(connection):
    current = db.get_profile(connection)
    return {"users": [{"id": u["id"], "name": u["name"],
                       "callsign": u["callsign"], "licensed": u["licensed"],
                       "display_name": u["display_name"],
                       "last_seen": u["last_seen"]}
                      for u in db.users(connection)],
            "current": current["id"],
            "display_name": current["display_name"],
            "local": _is_local(request.remote_addr)}


def _with_user_cookie(payload, user_id):
    """Answer, and remember on this browser who that was."""
    response = jsonify(payload)
    response.set_cookie(USER_COOKIE, str(user_id), max_age=COOKIE_YEARS,
                        samesite="Lax")
    return response


@app.route("/api/users")
def api_users():
    return jsonify(_user_block(conn()))


@app.route("/api/users/switch", methods=["POST"])
def api_users_switch():
    connection = conn()
    body = request.get_json(silent=True) or {}
    try:
        wanted = int(body.get("id"))
    except (TypeError, ValueError):
        abort(400)
    if not db.user_exists(connection, wanted):
        abort(404)
    connection.user_id = wanted
    db.touch_user(connection)
    log.info("now playing: %s", db.get_profile(connection)["display_name"])
    return _with_user_cookie(_user_block(connection), wanted)


@app.route("/api/users/add", methods=["POST"])
def api_users_add():
    connection = conn()
    body = request.get_json(silent=True) or {}
    try:
        profile = db.add_user(connection, body.get("name", ""),
                              body.get("callsign", ""))
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    connection.user_id = profile["id"]
    # A callsign given up front is worth resolving straight away: it is what
    # decides whether ELMER calls them by it.
    if profile["callsign"]:
        _adopt_licence(connection, profile["callsign"])
    log.info("new user on the unit: %s", profile["display_name"])
    return _with_user_cookie(_user_block(connection), profile["id"])


@app.route("/api/users/rename", methods=["POST"])
def api_users_rename():
    connection = conn()
    body = request.get_json(silent=True) or {}
    try:
        db.rename_user(connection, connection.user_id, body.get("name", ""))
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    return jsonify(_user_block(connection))


@app.route("/api/users/remove", methods=["POST"])
def api_users_remove():
    connection = conn()
    if not _is_local(request.remote_addr):
        log.warning("remove user refused: request from %s", request.remote_addr)
        return jsonify({"ok": False, "message":
                        "removing somebody has to be done at the unit itself"}), 403
    body = request.get_json(silent=True) or {}
    try:
        wanted = int(body.get("id"))
    except (TypeError, ValueError):
        abort(400)
    if not db.user_exists(connection, wanted):
        abort(404)
    name = db.get_user(connection, wanted)["display_name"]
    try:
        db.remove_user(connection, wanted)
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 409
    log.info("removed %s and everything of theirs", name)
    if connection.user_id == wanted:
        connection.user_id = db.first_user_id(connection)
    return _with_user_cookie(_user_block(connection), connection.user_id)


@app.route("/api/scoreboard")
def api_scoreboard():
    """Everyone on the unit, side by side.

    Read from each user's cached standings rather than recomputed: the point is
    a glance at who is doing what, and it should not cost six exam simulations
    per person to draw.
    """
    connection = conn()
    was, board = connection.user_id, []
    week = (datetime.now() - timedelta(days=7)).date().isoformat()
    try:
        for user in db.users(connection):
            connection.user_id = user["id"]
            standings = list((db.kv_get(connection, "standings", {}) or {}).values())
            tracks = ranks.overall(standings) if standings else {}
            counts = connection.execute(
                "SELECT COUNT(*) AS total, "
                "COALESCE(SUM(correct), 0) AS right_ FROM answer_log "
                "WHERE user_id = ?", (user["id"],)).fetchone()
            recent = connection.execute(
                "SELECT COUNT(*) c FROM answer_log WHERE user_id = ? AND day >= ?",
                (user["id"], week)).fetchone()["c"]
            board.append({
                "id": user["id"],
                "name": user["display_name"],
                "licensed": user["licensed"],
                "titles": {k: t["title"] for k, t in tracks.items()},
                "xp": user["xp"],
                "streak": user["streak_days"],
                "best_streak": user["best_streak"],
                "answered": counts["total"] or 0,
                "accuracy": (counts["right_"] / counts["total"]) if counts["total"] else 0.0,
                "week": recent,
                "last_seen": user["last_seen"],
                "is_you": user["id"] == was,
            })
    finally:
        connection.user_id = was
    board.sort(key=lambda r: (-r["week"], -r["xp"]))
    return jsonify({"board": board})


# --------------------------------------------------------------------------
# updates
# --------------------------------------------------------------------------
# These are gated on the request coming from this machine, and on a JSON
# content type.  Loopback keeps the network out; insisting on JSON keeps a
# page on some other site out, since a cross-origin form post cannot set that
# header without a preflight the browser will refuse.  There is no token here
# because unlike /api/quit these are wanted outside kiosk mode too, where no
# token is ever minted.

def _local_json_or_403():
    if not _is_local(request.remote_addr):
        log.warning("update refused: request from %s", request.remote_addr)
        abort(403)
    if not request.is_json:
        abort(415)


def _update_payload(status):
    """What the dashboard needs, in one object."""
    connection = conn()
    return {
        "policy": update.policy(connection),
        "policies": list(update.POLICIES),
        "state": update.state(),
        "status": status,
        "blocked": update.blocked(status),
        "local": _is_local(request.remote_addr),
    }


@app.route("/api/report", methods=["POST"])
def api_report():
    """Write a problem report somebody can read, then decide to send.

    A report can carry the station's identity if asked for, so it is written
    only for a browser on this machine - a phone on the LAN can look at ELMER
    but cannot make it write one.
    """
    if not _is_local(request.remote_addr):
        log.warning("report refused: request from %s", request.remote_addr)
        abort(403)
    include = request.json.get("station") is True if request.is_json else False
    path, redacted, text = bugreport.write(conn(), include_station=include)
    log.info("problem report written to %s (%s)", path.name,
             "redacted" if redacted else "with station detail")
    return jsonify({"path": str(path), "redacted": redacted, "text": text,
                    "contact": bugreport.CONTACT})


@app.route("/api/update")
def api_update():
    """The cached answer.  Deliberately does not touch the network."""
    return jsonify(_update_payload(update.cached()))


@app.route("/api/update/check", methods=["POST"])
def api_update_check():
    _local_json_or_403()
    # An explicit press means now, but a page that reloads in a loop should
    # not become a fetch in a loop.
    return jsonify(_update_payload(update.check(max_age=20)))


@app.route("/api/update/policy", methods=["POST"])
def api_update_policy():
    _local_json_or_403()
    wanted = (request.get_json(silent=True) or {}).get("policy")
    try:
        update.set_policy(conn(), wanted)
    except ValueError:
        abort(400)
    return jsonify(_update_payload(update.cached()))


@app.route("/api/update/apply", methods=["POST"])
def api_update_apply():
    _local_json_or_403()
    ok, message, detail = update.apply()
    if not ok:
        return jsonify({"ok": False, "message": message}), 409
    restarting = bool(detail.get("to"))
    if restarting:
        request_restart()
    return jsonify({"ok": True, "message": message, "detail": detail,
                    "restarting": restarting})


def request_restart():
    """Come back on the new code, the same way the Exit button stops.

    Answering first and interrupting afterwards keeps one shutdown path rather
    than two: ./elmer.py decides on the way out whether it is stopping or
    starting again.
    """
    app.config["RESTART"] = True
    threading.Timer(0.4, lambda: os.kill(os.getpid(), signal.SIGINT)).start()


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
