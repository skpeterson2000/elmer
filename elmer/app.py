"""ELMER - the program: its screens, and the API behind them.

The browser is how ELMER draws, not what ELMER is.  The program runs on the
machine in front of the operator; nothing is hosted and there is nowhere to
visit.  Pages are server-rendered; the quiz and exam screens talk to a small
JSON API so answering never reloads the page.  The correct answer is never
sent to the browser before the user commits to a choice: the server hands
out a shuffled presentation plus its permutation, and resolves the real
answer on submit.
"""
import hmac
import ipaddress
import json
import logging
import random
import re
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from markupsafe import escape
from urllib.parse import urlsplit

from flask import (Flask, Response, abort, g, jsonify, render_template,
                   request, send_from_directory, url_for)

from . import (antenna_advice, antennapdf, bandpdf, bandplan, callsign, cw,
               db, devreset, exams,
               celestial, explain, game, geocode, groundwave,
               ionosonde, logs,
               propagation, ranks,
               nanovna, patterns, places, regional, rfexposure, rfpdf, smith, srs,
               autoplay, bugreport, cohort, conductors, diagnostics,
               activations, activationspdf, discovery, fieldkit,
               gating, hall, host, library,
               netwatch, pota, references, sweeps,
               gps, netcontrol,
               party, phonegps, prints, qr,
               monitoring, personal, reachout, repeaters, units,
               calibrate, certpdf, difficulty, forecastlog, terrain, touchstone,
               tournament, trivia, update, vna, whipbuild)
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


@app.template_global()
def asset(filename):
    """A static URL that changes when the file does.

    Without this an update lands, the server restarts, and a page that has been
    open on a kiosk since before it carries on running the previous
    JavaScript - so a fixed fault stays fixed everywhere except the screen most
    likely to be looking at it. That is not a theoretical worry: the "locate me"
    fix was reported as still broken from a page that had been open since
    before it shipped, and the server log showed the request it should have
    made was never made at all.

    Stamped with the file's own modification time, the way the icon already
    was, so the browser fetches a new URL exactly when there is something new
    at it and keeps its cache the rest of the time.
    """
    url = url_for("static", filename=filename)
    try:
        stamp = int((Path(app.static_folder) / filename).stat().st_mtime)
    except OSError:
        return url
    return f"{url}?v={stamp}"


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
def _units():
    """The operator's distance units, for any page that shows a distance."""
    try:
        chosen = db.get_profile(conn())["settings"].get("units")
    except Exception:
        chosen = None
    return {"units": units.system(chosen), "unit_systems": units.SYSTEMS}


@app.context_processor
def _classes():
    """The licence classes, for the settings the gear opens.

    From bandplan rather than written out again in a template: a list that
    exists twice is a list that disagrees with itself eventually.
    """
    return {"license_classes": bandplan.CLASSES}


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
            # Handed to every page, because the offer belongs at the start of a
            # session rather than behind the account menu.
            "offer_password": db.should_offer_password(connection,
                                                       connection.user_id),
            "answered": answered, "today": today_count,
            "achievements": game.earned(connection),
            "all_achievements": game.ACHIEVEMENTS,
            "rank_rules": {"current_days": ranks.CURRENT_DAYS,
                           "grace_days": ranks.GRACE_DAYS},
            "qth": qth_for(connection, prof),
            "license": prof["settings"].get("license") or {}}


# --------------------------------------------------------------------------
# pages
# --------------------------------------------------------------------------

def greeting():
    hour = datetime.now().hour
    return "morning" if hour < 12 else "afternoon" if hour < 18 else "evening"


def warm(log_it=True):
    """Do the dashboard's expensive reading before anybody asks for it.

    On a cold Pi the first page is the slow one: a megabyte of pool JSON comes
    off the card, six tables of cards come out of SQLite, the templates are
    compiled, and only then does anything appear. Every bit of that is cached
    afterwards, which is why the second visit is instant and the first one
    feels broken.

    In kiosk mode there is a gap of a second or two between the server binding
    and the browser asking for a page, and this is work that fits in it. It is
    read-only and it is allowed to fail: a warm-up that raises must never be
    the reason the unit does not start.
    """
    started = time.perf_counter()
    try:
        pools = load_pools()
        for name in ("base.html", "home.html"):
            app.jinja_env.get_template(name)
        connection = db.connect()
        try:
            for pool_id, pool in pools.items():
                cards = db.cards_for_pool(connection, pool_id)
                # One pool's worth of the readiness simulation, to bring the
                # code and the card rows into memory. The other five are the
                # same work on warm caches by the time anybody looks.
                pool_stats(pool, cards, trials=60)
        finally:
            connection.close()
    except Exception as exc:                          # pragma: no cover
        log.debug("warm-up skipped: %s", exc)
        return
    if log_it:
        log.info("warmed up in %.1fs", time.perf_counter() - started)


def prefetch_sky(log_it=True):
    """Fetch the sky once at start, so the first page that asks has it.

    The ionosonde network and the space-weather feed are the two things a
    fresh unit knows nothing about until somebody opens a page that asks,
    and the Lab used to open on a textbook layer - 300 km, foF2 of 8 - with a
    button to fetch the real one. The measurement is the honest starting
    point, so it is fetched at start, in the background, and cached where
    every page reads it. Network is allowed to be absent; a prefetch that
    fails is a debug line, not a fault, and the pages fall back as before.
    """
    started = time.perf_counter()
    try:
        connection = db.connect()
        try:
            loc = (db.get_profile(connection)["settings"].get("location") or {})
        finally:
            connection.close()
        found = ionosonde.stations()
        snap = propagation.snapshot(lat=loc.get("lat"), lon=loc.get("lon"))
        if log_it:
            near = ionosonde.nearest(loc["lat"], loc["lon"]) if found and loc.get("lat") is not None else None
            log.info("sky at start: %s sondes reporting%s; %s in %.1fs",
                     len(found) if found else "no",
                     (f", nearest {near['name']} {near['distance_km']} km - hmF2 {near['hmf2']} km, "
                      f"foF2 {near['fof2']} MHz" if near else ""),
                     (f"MUF {snap.get('muf')} ({snap.get('muf_source')})" if snap.get("ok")
                      else "space weather not reachable"),
                     time.perf_counter() - started)
    except Exception as exc:                          # pragma: no cover
        log.debug("sky prefetch skipped: %s", exc)


@app.route("/")
def home():
    connection = conn()
    pools = load_pools()
    cards = {pid: db.cards_for_pool(connection, pid) for pid in pools}
    allowed, gate_state = _open_pools(connection)
    summary = []
    for pid, pool in pools.items():
        stats = pool_stats(pool, cards[pid], trials=600)
        standing_for(connection, pool, stats)
        summary.append({
            "pool": pool, "open": pid in allowed,
            # Only the amateur ladder has a tournament difficulty; the
            # commercial pools are not part of the class-versus-class game.
            "tournament": POOL_DIFFICULTY.get(pid),
            "closed_why": gating.why_closed(pid, gate_state),
            "mastery": stats["mastery"],
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
    pool = _studyable_or_403(conn(), pool_id)
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
        license_class=profile["settings"].get("license_class")
                       or (profile["settings"].get("license") or {}).get("license_class")
                       or "Technician",
        coordinators=regional.states(),
        # Chosen from the QTH when nobody has picked one. The reverse-geocoded
        # place name already carries the state and it was being thrown away,
        # so a Wisconsin operator got a silent "none" rather than the name of
        # whoever actually coordinates them.
        state=(profile["settings"].get("state")
               or regional.state_of(profile["settings"].get("location") or {})
               or ""),
        # Whether there is a QTH at all, which decides what the empty option in
        # the coordinator list should say. With a location and no match - a
        # station outside the US, say - "none" is the true answer and telling
        # somebody to set a location they have already set would be nonsense.
        # With no location, "none" is a dead end that explains nothing.
        has_location=bool((profile["settings"].get("location") or {}).get("lat")
                          is not None),
        **profile_block(connection))


def _usable(low, high, kind, band_name, license):
    """What this class may do with one activity segment, and why."""
    return bandplan.usable_answer(band_name, license, low, high, kind)


@app.route("/api/bandplan")
def api_bandplan():
    """Privileges and activity for every band, for one license class."""
    license = request.args.get("class", "Technician")
    if license not in bandplan.CLASSES:
        abort(400, "unknown license class")
    # Which class is being read, and which one this station actually holds.
    # The page is free to show any of them - that is how somebody decides
    # whether the upgrade is worth sitting for - but it should say plainly
    # when the two differ, before anything with a callsign on it is printed.
    own = _own_class()
    return jsonify({
        "class": license, "kinds": bandplan.KINDS,
        "own_class": own or "",
        "yours": bool(own) and license.lower() == own.lower(),
        # Only the upward direction is a claim worth a word. An Extra reading
        # the Technician plan is looking at a subset of what they hold; a
        # Technician reading Extra is looking at what they do not, and that is
        # the sheet that must never be mistaken for a licence.
        "above_yours": bool(
            own and bandplan.CLASS_RANK.get(license, 0)
            > bandplan.CLASS_RANK.get(own, 0)),
        "bands": [{
            **band,
            "privileges": bandplan.privileges_for(band["name"], license),
            "gaps": bandplan.gaps_for(band["name"], license),
            "activity": [
                {"low": a, "high": b, "kind": k, "label": l,
                 "you": _usable(a, b, k, band["name"], license)}
                for a, b, k, l in bandplan.activity_for(band["name"])],
        } for band in bandplan.BANDS],
        "channels_60m": bandplan.CHANNELS_60M,
    })


@app.route("/api/difficulty")
def api_difficulty():
    """Where the people on this unit get lost, question by question.

    For the Elmer running a class: the questions this unit's students found
    hardest, each with how many met it, how many missed, and how long it took
    them against their own pace. Honest from small numbers because it is
    this room's numbers, not a national claim - and it says how much of the
    pool it has measured at all.
    """
    pool_id = request.args.get("pool") or "tech2026"
    pool = _pool_or_404(pool_id)
    rows = difficulty.load(conn(), pool_id)
    measured = difficulty.measure(rows)
    try:
        limit = max(1, min(50, int(request.args.get("limit") or 12)))
    except ValueError:
        limit = 12
    hardest_rows = []
    for h in difficulty.hardest(measured, limit):
        q = pool.by_id.get(h["question_id"]) or {}
        hardest_rows.append({**h, "section": q.get("section"),
                             "text": (q.get("text") or "")[:160]})
    return jsonify({
        "pool": pool_id, "pool_name": pool.long_name,
        "questions": len(pool.by_id),
        "met": sum(1 for q in pool.by_id if q in measured),
        "measured": sum(1 for q in pool.by_id if measured.get(q, {}).get("measured")),
        "coverage": round(difficulty.coverage(measured, pool.by_id), 3),
        "min_n": difficulty.MIN_N,
        "sources": difficulty.sources(rows),
        "classes": difficulty.by_license(rows),
        "hardest": hardest_rows,
    })


@app.route("/api/bands")
def api_bands():
    """Every amateur band, its edges, where it opens, and what is in it.

    For the Lab, which has five places to type a frequency and until now no
    way of saying whether the number typed was in a band at all - a slider
    running 1.8 to 30 MHz spends most of its travel between bands, and the
    hop simulator would cheerfully model 12.0 MHz as if anybody could use it.
    Compact on purpose: edges, a calling frequency to open on, and the
    activity segments so the meter can name what is at a frequency ("CW QRP
    calling") rather than only which band it is in. Privileges are not here;
    the band plan page answers that properly, with a class, and the meter
    links to it.
    """
    out = []
    for band in bandplan.BANDS:
        call = bandplan.calling_frequency(band["name"])
        out.append({
            "name": band["name"], "key": band["name"].replace(" ", ""),
            "low": band["low"], "high": band["high"],
            "group": band.get("group"),
            "channelised": bool(band.get("channelised")),
            "calling": call[0] if call else None,
            "calling_label": call[1] if call else None,
            "activity": [[lo, hi, kind, label] for lo, hi, kind, label
                         in bandplan.activity_for(band["name"])],
        })
    return jsonify({"bands": out})


@app.route("/out")
def reachout_page():
    """What to try, from here, with what is on hand."""
    connection = conn()
    profile = db.get_profile(connection)
    settings = profile["settings"]
    shelf = library.shelf_gear(connection)
    return render_template(
        "reachout.html", gear=reachout.GEAR, classes=bandplan.CLASSES,
        license_class=settings.get("license_class")
                      or (settings.get("license") or {}).get("license_class")
                      or "Technician",
        # The gear list is radios. These are the other two thirds of the
        # inventory - what an antenna can be made of, and what it takes to
        # work that material - and both are deliberately samples rather than
        # catalogues. `conductors.improvised` and `fieldkit` say why.
        made_of=conductors.improvised(), tools=fieldkit.ladder(),
        arc=fieldkit.ARC,
        # What the shelf says this person has: the radios their manuals are
        # for, ticked, and said so they can be unticked. A shelf with no
        # radios on it leaves the old assumption - a handheld - in place.
        assumed=shelf["gear"] or ["ht"], shelf=shelf, **profile_block(connection))


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
    license = request.args.get("license") or \
        profile["settings"].get("license_class") or "Technician"
    answer = reachout.summary(place["lat"], place["lon"], gear, license,
                              conn=connection)
    answer["qth"] = place.get("short") or place.get("grid") or ""
    answer["qth_source"] = place.get("source") or "saved"
    answer["located"] = True
    # What the law says about listening, beside the frequencies rather than
    # on a page of its own - this is where somebody is looking at what they
    # could tune. Driven off the fix, because the statutes that matter are
    # about vehicles and a saved QTH is right until somebody drives.
    try:
        where = monitoring.where_am_i(place["lat"], place["lon"])
        answer["monitoring"] = monitoring.advice(
            where.get("state"),
            # Either is evidence enough. Somebody who has said which class
            # they hold but not typed a callsign is still a licensee, and the
            # condition they need to know about is the licensee's one.
            licensed=bool(profile.get("licensed") or profile.get("callsign")
                          or profile["settings"].get("license_class")))
        answer["monitoring"]["where"] = where
    except Exception:            # never worth losing the page over
        log.exception("could not work out the monitoring advice")
        answer["monitoring"] = None
    return jsonify(answer)


@app.route("/activations")
def activations_page():
    """Parks and summits: what is near, what counts, and what you have.

    The two programmes are the reason most people carry a radio somewhere, and
    almost every wasted trip is a planning failure rather than a radio one -
    the wrong kit, or the wrong side of a contour. That is fixable at a table
    days early, which is what this page is for.
    """
    connection = conn()
    settings = db.get_profile(connection)["settings"]
    # The same shelf Make Contact reads: the manuals name the radios. A wire
    # HF station is the classic activation and stays the assumption when the
    # shelf names nothing.
    shelf = library.shelf_gear(connection)
    return render_template("activations.html", gear=reachout.GEAR,
                           assumed=shelf["gear"] or ["hf_wire"], shelf=shelf,
                           # None means nobody has been asked yet, which is a
                           # different state from having said no.
                           pota_asked=settings.get("pota"),
                           **profile_block(connection))


@app.route("/api/activations")
def api_activations():
    """Everything the page needs, without touching the network.

    Held references only. Fetching is a press, because it is thirty-odd
    requests and the better part of a minute, and because a page that reaches
    out the moment it is opened is a page nobody can open quietly.
    """
    connection = conn()
    profile = db.get_profile(connection)
    place = qth_for(connection, profile)
    lat, lon = place.get("lat"), place.get("lon")
    # Each kind counted and listed on its own. Taking the nearest forty of
    # everything and sorting them afterwards reported "no summits" whenever
    # forty parks were closer than the first hill, which is most places -
    # the wrong answer to "is there anything up there", and it looked
    # authoritative.
    parks, summits = [], []
    cover = {"known": False, "reason": "nowhere", "areas": 0}
    if lat is not None:
        parks = references.nearby(lat, lon, kind="park", limit=None)
        summits = references.nearby(lat, lon, kind="summit", limit=None)
        cover = references.coverage(lat, lon)
    return jsonify({
        "qth": place.get("short") or place.get("grid") or "",
        "located": lat is not None,
        "coverage": cover,
        "radius_km": references.DEFAULT_RADIUS_KM,
        "parks": parks[:12], "summits": summits[:12],
        "held": {"parks": len(parks), "summits": len(summits)},
        "programs": [activations.POTA, activations.SOTA],
        "gear": activations.GEAR_VERDICTS,
        "land": {"read": activations.LAND_READ, "source": activations.LAND_SOURCE,
                 "rules": activations.LAND},
    })


# As far as anybody sensibly drives to a park, in whatever they count in.
MAX_BAND = 400.0


def _print_band(body, system):
    """The inner and outer edge of the search, in kilometres.

    Typed in the operator's own units and converted once, here, rather than in
    the four places that would otherwise each have to agree about it.
    """
    def asked(key, fallback):
        try:
            value = float(body.get(key, fallback))
        except (TypeError, ValueError):
            abort(400, "%s must be a number of %s"
                       % (key, units.long_name(system)))
        return max(0.0, min(MAX_BAND, value))

    inner = asked("inner", 0)
    outer = asked("outer", 50)
    if outer <= inner:
        abort(400, "the outer distance has to be past the inner one")
    return units.to_km(inner, system), units.to_km(outer, system)


def _in_band(rows, inner_km, outer_km):
    """Only what falls between the two edges, nearest first."""
    return [r for r in rows
            if inner_km <= (r.get("km") or 0) <= outer_km]


@app.route("/api/activations/print", methods=["POST"])
def api_activations_print():
    """The nearest parks, summits, or both, on a sheet for the vehicle.

    Held references only, like the page. This prints what is already on the
    disk rather than reaching out, because the press that fetches is a
    separate press for a reason - a minute of requests is not something to
    start by accident from a button labelled print.
    """
    body = request.get_json(silent=True) or {}
    want = str(body.get("want") or "both").lower()
    if want not in ("parks", "summits", "both"):
        abort(400, "want must be parks, summits or both")
    connection = conn()
    profile = db.get_profile(connection)
    system = units.system(profile["settings"].get("units"))["key"]
    inner_km, outer_km = _print_band(body, system)

    # From here, or from where you are going. A band around the destination is
    # the question somebody actually has the night before a trip, and the QTH
    # is the wrong centre for it.
    asked = str(body.get("from") or "").strip()
    if asked:
        place = geocode.resolve(asked)
        if not place or place.get("lat") is None:
            # Quoted the same way whatever is in it. Python's %r picks its
            # own quotes by content, so Coeur d'Alene and O'Brien - both
            # places somebody would type - come back in double quotes while
            # everything else comes back in single.
            abort(400, "could not find \u201c%s\u201d - try a town, a grid "
                       "square, or coordinates" % asked[:60])
    else:
        place = qth_for(connection, profile)
    lat, lon = place.get("lat"), place.get("lon")
    if lat is None:
        abort(400, "ELMER does not know where you are yet")

    parks = _in_band(references.nearby(lat, lon, kind="park", limit=None),
                     inner_km, outer_km)
    summits = _in_band(references.nearby(lat, lon, kind="summit", limit=None),
                       inner_km, outer_km)
    wanted = {"parks": parks, "summits": summits,
              "both": parks + summits}[want]
    if not wanted:
        # Three different nothings, and saying the wrong one sends somebody
        # to fetch data they already have, or to widen a band that was never
        # the problem.
        cover = references.coverage(lat, lon)
        where = place.get("short") or place.get("grid") or "there"
        if not cover.get("known"):
            abort(400, "nothing has been fetched for %s yet - fetch what is "
                       "near first, from a position there" % where)
        abort(400, "nothing is held between those distances of %s - widen the "
                   "band" % where)

    # How old the list behind this sheet is. It matters more on paper than on
    # screen: a printout is read days later, in a valley, by somebody with no
    # way to check it.
    cover = references.coverage(lat, lon)
    pdf = activationspdf.build(
        parks, summits, want=want, radius_km=references.DEFAULT_RADIUS_KM,
        inner_km=inner_km, outer_km=outer_km, system=system,
        age_days=cover.get("oldest_days"), stale=cover.get("stale", False),
        station={"grid": place.get("grid") or "",
                 "place": place.get("short") or place.get("name") or "",
                 "callsign": profile_callsign() or ""})
    named = {"parks": "parks", "summits": "summits",
             "both": "parks-and-summits"}[want]
    name = f"{named}-near-{place.get('grid') or 'here'}.pdf"
    shown = min(activationspdf.DEFAULT_LIMIT,
                max(len(parks) if want != "summits" else 0,
                    len(summits) if want != "parks" else 0))
    log.info("activations sheet: %s near %s (%d parks, %d summits held)",
             want, place.get("grid"), len(parks), len(summits))
    row = prints.keep(pdf, name, "activations",
                      "%s near %s" % (named.replace("-", " ").capitalize(),
                                      place.get("grid") or "here"),
                      {"want": want, "parks": len(parks),
                       "summits": len(summits), "shown": shown})
    return _print_reply(row, _wants_raw(body))


@app.route("/api/activations/prepare", methods=["POST"])
def api_activations_prepare():
    """Fetch the parks and summits within a day's drive, and hold them.

    Local only, and a press rather than a page load: this is the one thing
    here that costs somebody else's bandwidth, and it is the operator's
    decision when to spend it.
    """
    _local_json_or_403()
    connection = conn()
    profile = db.get_profile(connection)
    place = qth_for(connection, profile)
    if place.get("lat") is None:
        return jsonify({"ok": False,
                        "error": "ELMER does not know where you are yet - "
                                 "set a QTH on the propagation page"}), 409
    area = references.fetch(place["lat"], place["lon"],
                            label=place.get("short") or "here")
    return jsonify({"ok": True, "area": {
        "label": area["label"], "radius_km": area["radius_km"],
        "parks": len(area["parks"] or []),
        "summits": len(area["summits"] or []),
        "missing": area["missing"]}})


@app.route("/api/pota/<call>")
def api_pota(call):
    """One operator's POTA record, once somebody has asked for it.

    A callsign leaving this unit for somebody else's server is the operator's
    decision and not a detail of how a page is built, so the panel says what
    it would send before it sends anything and this only answers when asked.
    """
    settings = db.get_profile(conn())["settings"]
    if settings.get("pota") is not True:
        return jsonify({"ok": False, "asked": False,
                        "error": "not asked for"}), 403
    return jsonify(pota.lookup(call, refresh=bool(request.args.get("refresh"))))


@app.route("/api/conductors")
def api_conductors():
    """What an element can be made of, and what each choice costs or buys."""
    try:
        mhz = float(request.args.get("mhz", "14.2"))
    except ValueError:
        abort(400)
    if not 0.1 <= mhz <= 3000:
        abort(400)
    kind = request.args.get("kind") or None
    return jsonify({"mhz": mhz, "conductors": conductors.options(mhz, kind),
                    "reference": conductors.REFERENCE["key"]})


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
    # A fatter element is a lower-Q element and a lower-Q element holds its
    # SWR across more of the band. The bowtie is left alone: its Q already
    # comes from the width of the triangle, and scaling that by the gauge of
    # the wire round the edge would count the same thing twice.
    conductor = request.args.get("conductor") or conductors.REFERENCE["key"]
    made_of = conductors.describe(conductor, mhz)
    if kind != "bowtie" and made_of["q_scale"] != 1.0:
        spec = dict(spec, q=spec["q"] * made_of["q_scale"])

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
    # Three states where the operator is, then the one bit the hop geometry
    # actually wants. The F2 peak has a day height and a night height and no
    # third one, and by the grey line it is already rising - so grey counts as
    # night here. That is the only consumer left that a boolean genuinely fits.
    sun = (reachout.sun_state(place["lat"], place["lon"])
           if place.get("lat") is not None and place.get("lon") is not None
           else "lit")
    day = sun == "lit"

    # Near-vertical incidence lives or dies on whether the frequency is under
    # the critical frequency, so it gets the measured one rather than a rule of
    # thumb. Both lookups are cheap and neither is allowed to break the antenna
    # tool: the snapshot is cached for fifteen minutes and the sonde is read
    # from cache only, and if either is missing the model says so and falls
    # back to the 300-mile average.
    fof2 = hmf2 = None
    if nvis or use == "regional":
        try:
            snap = propagation.snapshot(lat=place.get("lat"), lon=place.get("lon"))
            if snap.get("ok"):
                fof2 = snap.get("fof2")
        except Exception:
            log.info("no space weather for the NVIS footprint", exc_info=False)
        try:
            if place.get("lat") is not None:
                near = ionosonde.nearest(place["lat"], place["lon"], offline=True)
                if near and near["distance_km"] <= propagation.CALIBRATION_KM:
                    hmf2 = near["hmf2"]
        except Exception:
            pass

    span = patterns.qualify(
        patterns.reach(kind, use, mhz, height_ft, nvis, slope, day, fof2, hmf2),
        mhz)

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
        # The antenna's Q at this frequency, which for a screwdriver is not
        # the table's figure - see patterns.Q_SCALES_WITH_BAND.
        "shape": spec["shape"], "q": round(patterns.base_q(kind, mhz), 1),
        "fed": spec["fed"],
        "elevation": patterns.elevation(kind, height_wl, slope_deg=slope),
        "azimuth": patterns.azimuth(kind, heading),
        "main_lobe_deg": patterns.main_lobe(kind, height_wl, slope),
        "slope": slope,
        "swr": patterns.swr_curve(kind, mhz, q=patterns.base_q(kind, mhz)),
        "bandwidth": patterns.usable_bandwidth(
            kind, mhz, q=patterns.base_q(kind, mhz)),
        "conductor": made_of,
        "dx": dx, "qth": place.get("grid") or place.get("short") or "",
        "qth_source": place.get("source") or "saved",
        "qth_age_s": place.get("age_s"),
        "reach": span, "use": use,
        "daytime": day, "sun": sun,
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


@app.route("/api/vna/sweep")
def api_vna_sweep():
    """What an instrument would show, for an antenna nobody has built yet."""
    try:
        f0 = float(request.args.get("f0", "14.2"))
        centre = float(request.args.get("centre") or f0)
        span = float(request.args.get("span", "0.14"))
        feet = float(request.args.get("feet", "0"))
        points = int(request.args.get("points", vna.DEFAULT_POINTS))
        q = request.args.get("q")
        q = float(q) if q else None
    except ValueError:
        abort(400)
    kind = request.args.get("kind", "dipole")
    line = request.args.get("line", "rg8x")
    if line not in smith.LINES or not (0.1 <= f0 <= 3000 and 0.1 <= centre <= 3000):
        abort(400)
    return jsonify(vna.sweep(kind, f0, line, feet, centre, span, points, q))


@app.route("/api/vna/ports")
def api_vna_ports():
    """Anything on the USB bus that might be an instrument."""
    found, error = nanovna.candidates()
    return jsonify({"ports": found, "error": error})


@app.route("/api/vna/identify")
def api_vna_identify():
    """Open one port and ask it what it is."""
    device = request.args.get("device") or ""
    if not host.is_serial_device(device):
        abort(400)
    info, error = nanovna.identify(device)
    return jsonify({"ok": info is not None, "info": info, "error": error})


@app.route("/api/vna/controls")
def api_vna_controls():
    """What may be asked of an instrument, and what each one costs."""
    return jsonify({"controls": nanovna.offered(),
                    "standards": nanovna.CAL_STANDARDS,
                    "slots": nanovna.MAX_SLOT})


@app.route("/api/vna/control", methods=["POST"])
def api_vna_control():
    """Change one thing on the instrument.

    Local only, and for the same reason the update controls are: reading an
    instrument from a phone across the room is harmless, and wiping its
    calibration from one is a decision that belongs to somebody standing in
    front of the bench it is on.
    """
    _local_json_or_403()
    body = request.get_json(silent=True) or {}
    device = body.get("device") or ""
    if not host.is_serial_device(device):
        abort(400)
    result, error = nanovna.control(device, body.get("action") or "",
                                    body.get("value"),
                                    confirmed=bool(body.get("confirmed")))
    return jsonify({"ok": result is not None, "result": result,
                    "error": error})


@app.route("/api/vna/measure")
def api_vna_measure():
    """One real sweep off the instrument. Slow, so it is asked for explicitly."""
    device = request.args.get("device") or ""
    if not host.is_serial_device(device):
        abort(400)
    try:
        start = float(request.args.get("start", "14.0"))
        stop = float(request.args.get("stop", "14.35"))
        points = int(request.args.get("points", "101"))
    except ValueError:
        abort(400)
    got, error = nanovna.measure(device, start, stop, points)
    if error:
        log.info("vna sweep failed: %s", error)
    # Held where another page can find it. The Smith chart is no longer a tab
    # of the same document as the instrument, and a measurement that lived in
    # the page that took it could not cross that.
    if got is not None:
        sweeps.keep(got)
    return jsonify({"ok": got is not None, "sweep": got, "error": error})


@app.route("/api/vna/last")
def api_vna_last():
    """The last sweep the instrument gave this station, if there is one.

    Read by the Smith chart, which lives on a different page from the VNA now
    and so cannot be handed the trace directly. Anyone on the network may look
    at what the antenna measured; only a browser on the machine itself can
    make the instrument do anything, which is the split the control endpoint
    already draws.
    """
    return jsonify({"sweep": sweeps.last()})


@app.route("/api/vna/s1p", methods=["POST"])
def api_vna_s1p():
    """A measured sweep as Touchstone, for every other program that reads it.

    The rows come from the browser, which is the opposite of how the antenna
    sheet works and is right here for the same reason it is wrong there: a
    sheet is computed and can always be recomputed, where a sweep is a
    measurement and exists only where it was taken. Recomputing it would mean
    sweeping the instrument again, which would be a different measurement.
    """
    body = request.get_json(force=True) or {}
    rows = body.get("rows") or []
    if not isinstance(rows, list) or not rows:
        abort(400, "no sweep to export")
    if len(rows) > 5000:
        abort(400, "that is not a sweep")
    try:
        text = touchstone.s1p(rows, z0=float(body.get("z0") or 50.0),
                              device=body.get("device") or None,
                              note=body.get("note") or None)
    except (TypeError, ValueError) as exc:
        abort(400, str(exc))
    low = min(float(r["mhz"]) for r in rows if r.get("mhz") is not None)
    high = max(float(r["mhz"]) for r in rows if r.get("mhz") is not None)
    name = touchstone.filename(low, high)
    log.info("touchstone export: %d points, %.3f-%.3f MHz", len(rows), low, high)
    return Response(text, mimetype="application/octet-stream", headers={
        "Content-Disposition": f'attachment; filename="{name}"'})


# Two eight-foot loaded whips end to end, no ground path between them: the
# measured 10 dB on 40 m (Virginia RACES, 2001-02) works back to about 24 ohms
# of loss in the pair, and the Lab's calculator starts from the same figure.
PAIR_COIL_OHMS = 24.0


@app.route("/api/antenna-advice")
def api_antenna_advice():
    """What to put up here, and why - for a licensee who has not built one yet."""
    try:
        mhz = float(request.args.get("mhz", ""))
    except ValueError:
        abort(400)
    if not 0.1 <= mhz <= 300000:
        abort(400)
    out = antenna_advice.recommend(
        mhz, use=request.args.get("use"), kind=request.args.get("kind"),
        site=request.args.get("site") or None)
    # Where the feed matches, for a horizontal wire: the heights the curve
    # does something at, marked reachable or not by what the site allows.
    if out.get("type") in ("dipole", "invertedv", "bowtie", "loop"):
        site = request.args.get("site") or ""
        reach = (antenna_advice.SITES.get(site) or {}).get("max_ft")
        out["heights"] = antenna_advice.matching_heights(
            mhz, reach if reach not in (None, 0) else None)
    # What the power asks of the parts. The conductor's diameter and material
    # come along so the heat in the wire is this wire's, not the default's.
    try:
        watts = float(request.args.get("watts") or 0)
    except ValueError:
        watts = 0.0
    if watts > 0:
        spec = next((c for c in conductors.CONDUCTORS
                     if c["key"] == request.args.get("conductor")), None)
        od = spec["od_mm"] if spec else 1.63
        sigma = spec.get("sigma", 1.0) if spec else 1.0
        coil, rrad = None, None
        if out.get("type") in ("whip", "screwdriver", "whipdipole"):
            try:
                # A pair is two of these in series, and the dipole's
                # radiation resistance is twice the monopole's; the ground
                # loss the single whip carries is not in the pair at all.
                if out["type"] == "whipdipole":
                    plan = whipbuild.plan(mhz, 8.0, loss_ohms=PAIR_COIL_OHMS)
                    coil, rrad = plan["loss_ohms"], 2 * plan["radiation_ohms"]
                else:
                    plan = whipbuild.plan(mhz, float(out.get("height_ft") or 8))
                    coil, rrad = plan.get("loss_ohms"), plan.get("radiation_ohms")
            except Exception:                    # a whip that cannot be planned
                coil = rrad = None
        out["power"] = antenna_advice.power_notes(
            out.get("type"), mhz, watts, od, sigma, coil, rrad)
    return jsonify(out)


@app.route("/api/antenna/pdf", methods=["POST"])
def api_antenna_pdf():
    """The antenna sheet: what to cut, how high, and what to expect.

    The browser sends the choices and nothing else - the sheet recomputes every
    figure from the same modules the page drew from, so a printout can never
    quietly disagree with the screen it was made from.
    """
    body = request.get_json(force=True) or {}
    try:
        mhz = float(body.get("mhz", ""))
        height_ft = float(body.get("height", 35))
    except (TypeError, ValueError):
        abort(400, "a frequency and a height are needed")
    kind = body.get("kind") or "dipole"
    if kind not in patterns.ANTENNA_Q:
        abort(400, "unknown antenna")
    if not 0.1 <= mhz <= 300000:
        abort(400, "frequency out of range")
    if not 0.0 <= height_ft <= 2000.0:
        abort(400, "height out of range")
    conductor = body.get("conductor") or "wire14"
    if conductor not in conductors.INDEX:
        conductor = "wire14"
    site = body.get("site") or "house"
    if site not in antenna_advice.SITES:
        site = "house"
    # The licence decides what is hatched over on the band bar at the top of
    # the sheet. Taking it from the profile rather than the request keeps the
    # sheet's answer to "may I transmit here" the same one every other page
    # gives, rather than one the browser could ask for.
    settings = db.get_profile(conn())["settings"]
    license_class = (settings.get("license_class")
                     or (settings.get("license") or {}).get("license_class")
                     or "Technician")
    pdf = antennapdf.build(kind, mhz, height_ft, conductor, site,
                           use=body.get("use") or None,
                           callsign=profile_callsign() or "",
                           license_class=license_class)
    title = (antenna_advice.TYPES.get(kind) or {}).get("title", kind)
    name = f"antenna-{kind}-{mhz:.3f}mhz.pdf".replace(" ", "-")
    log.info("antenna sheet PDF: %s at %.3f MHz, %.0f ft, %s",
             kind, mhz, height_ft, conductor)
    row = prints.keep(pdf, name, "antenna",
                      f"{title} - {mhz:.3f} MHz, {height_ft:.0f} ft",
                      {"kind": kind, "mhz": mhz, "height": height_ft,
                       "conductor": conductor, "site": site})
    return _print_reply(row, _wants_raw(body))


@app.route("/api/personal")
def api_personal():
    """FRS, GMRS, MURS and CB: channels, law and conventions, for the band
    plan page and anything else that meets a frequency it does not own."""
    return jsonify(personal.for_bandplan())


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
    license_class = (request.args.get("class")
                     or settings.get("license_class") or "")
    result = bandplan.privilege_at(mhz, license_class)

    # What this class may use on this band, whether or not it may use *here*.
    # Saying no without saying what instead leaves somebody to go and look it
    # up, and the thing they came for was the answer. The suggestion is the
    # middle of the widest segment they do have, which is where a calculator
    # can be pointed with one press.
    segments, suggest = [], None
    if result["band"] and license_class:
        for low, high, terms in bandplan.privileges_for(result["band"],
                                                        license_class):
            segments.append({"low": low, "high": high, "terms": terms})
        if segments and not result["allowed"]:
            widest = max(segments, key=lambda seg: seg["high"] - seg["low"])
            suggest = round((widest["low"] + widest["high"]) / 2.0, 3)
    result["band_segments"] = segments
    result["suggest_mhz"] = suggest
    result["classes"] = list(bandplan.CLASSES)
    # Outside the amateur bands the honest answer is still an answer: the
    # frequency is very often somebody else's channel, and saying whose is
    # what stops "not in a US amateur band" reading as "not a frequency".
    result["service"] = (None if result["in_band"]
                         else personal.service_at(mhz))
    # What the profile holds, as well as what this answer was worked out for.
    # A page that has been handed a class - from the band plan, or by somebody
    # choosing one - should be able to say so rather than implying the profile
    # said it.
    result["profile_class"] = settings.get("license_class") or ""
    result["asked_class"] = request.args.get("class") or ""


    modes = []
    for key, (label, _duty) in rfexposure.MODE_DUTY.items():
        emission = rfexposure.MODE_EMISSION.get(key)
        if not result["in_band"] or not license_class:
            permitted, why = None, None          # nothing claimed either way
        elif not result["allowed"]:
            permitted, why = False, "not in this class's part of the band"
        elif emission is None:
            permitted, why = True, None          # tuning, wherever you may talk
        elif (emission == "phone" and result["phone_modes"] == ["usb"]
                and key not in ("ssb", "ssb_proc")):
            permitted = False
            why = ("only upper sideband is permitted here - 60 m carries USB "
                   "voice, CW and data and nothing else (47 CFR 97.305(c))")
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
    result["known_class"] = license_class in bandplan.CLASSES
    result["classes"] = bandplan.CLASSES
    return jsonify(result)


@app.route("/api/bandplan/regional/<state>")
def api_bandplan_regional(state):
    """The local coordinator's plan. 503 when it cannot be reached."""
    data = regional.plan(state, refresh=request.args.get("refresh") == "1")
    if not data:
        # Not an error, and it used to read like one. Only a handful of the
        # forty-odd coordinators publish a plan this can read, so for the rest
        # the useful answer is who to ask rather than a 503 - the operator
        # wanted their coordinator, and naming them is most of that.
        who = regional.for_state(state)
        return jsonify({
            "ok": False, "state": state.upper(),
            "coordinators": who,
            "error": ("no plan here yet for %s" % state.upper() if who
                      else "no coordinator listed for %s" % state.upper()),
        }), 200
    return jsonify({"ok": True, **data})


# ------------------------------------------------------------- printouts
# A PDF built here used to go straight into the browser's downloads folder,
# which on a Pi running full screen with no tabs and no address bar meant
# leaving ELMER to find a file manager. So the unit keeps what it prints and
# hands back where to look at it, and the looking happens inside the app.

def _print_reply(row, raw=False):
    """Where to find a freshly built PDF - or, if asked, the PDF itself.

    The pages want the address, because they show it in the application rather
    than handing it to the desktop. Anything driving ELMER from a script wants
    the bytes, and asking for them with raw=1 still leaves a copy on the shelf.
    """
    if raw:
        pdf = prints.read(row["id"])
        return Response(pdf, mimetype="application/pdf", headers={
            "Content-Disposition": f'attachment; filename="{row["name"]}"',
            "Content-Length": str(len(pdf))})
    return jsonify({"ok": True, "id": row["id"], "name": row["name"],
                    "title": row["title"], "bytes": row["bytes"],
                    "view": url_for("print_view", print_id=row["id"]),
                    "file": url_for("print_file", print_id=row["id"])})


def _wants_raw(body):
    return (request.args.get("raw") == "1"
            or str(body.get("raw", "")).lower() in ("1", "true"))


@app.route("/prints")
def prints_page():
    """Everything this unit has printed, and a way to print it again."""
    return render_template("prints.html", shelf=prints.shelf(),
                           keep=prints.KEEP, **profile_block(conn()))


# --------------------------------------------------------------------------
# the library: the operator's own manuals, indexed
# --------------------------------------------------------------------------

@app.route("/library")
def library_page():
    """The shelf of manuals this operator owns, searchable to the page."""
    return render_template("library.html", shelf_path=str(library.SHELF),
                           topics=library.TOPICS, **profile_block(conn()))


@app.route("/api/library")
def api_library():
    """What is on the shelf and how current each index is. Reading only:
    indexing a thousand-page manual takes a while and is asked for."""
    tools = library.tools_present()
    return jsonify({"path": str(library.SHELF), "tools": tools,
                    "tools_note": None if tools["pdftotext"] else library.missing_tools_note(),
                    "shelf": library.catalogue(), "topics": library.topic_map(),
                    "mine": library.mine(conn()),
                    "reindex_days": library.REINDEX_DAYS})


@app.route("/api/library/index", methods=["POST"])
def api_library_index():
    """Index what is new or changed - or everything, or one book, if asked.

    Synchronous on purpose: the page that asked shows "indexing" until the
    answer comes, and the answer says what was read, what was kept and what
    could not be read, by name.
    """
    body = request.get_json(silent=True) or {}
    report = library.refresh(force=bool(body.get("force")),
                             only=body.get("only") or None)
    # The same shape as /api/library, tools included: the page repaints the
    # shelf from this answer, and an answer without the tools in it had the
    # page announce "nothing can be read" over three books it had just read.
    tools = library.tools_present()
    return jsonify({"report": report, "shelf": library.catalogue(),
                    "topics": library.topic_map(), "tools": tools,
                    "tools_note": None if tools["pdftotext"] else library.missing_tools_note()})


@app.route("/api/library/search")
def api_library_search():
    q = (request.args.get("q") or "").strip()[:200]
    try:
        limit = max(1, min(100, int(request.args.get("limit") or 30)))
    except ValueError:
        limit = 30
    return jsonify(library.search(q, limit))


@app.route("/api/library/outline")
def api_library_outline():
    """The publisher's bookmarks for one book, as they are in the file."""
    name = request.args.get("name") or ""
    if library.book(name) is None:
        abort(404, "no such book")
    return jsonify({"name": name, "outline": library.outline(name)})


@app.route("/api/library/pointers")
def api_library_pointers():
    """Where a topic of ELMER's is in the operator's own books."""
    topic = request.args.get("topic") or ""
    if topic not in library.TOPICS:
        abort(400, "unknown topic")
    return jsonify({"topic": topic, "label": library.TOPICS[topic]["label"],
                    "pointers": library.pointers(topic)})


@app.route("/api/library/add", methods=["POST"])
def api_library_add():
    """Put a PDF on the shelf from the browser - a phone on the LAN can hand
    the Pi a manual without anybody finding a USB stick. The name is kept,
    made safe; the file is not read until it is indexed."""
    from werkzeug.utils import secure_filename
    up = request.files.get("file")
    if up is None or not up.filename:
        abort(400, "no file")
    name = secure_filename(up.filename)
    if not name.lower().endswith(".pdf"):
        abort(400, "only PDF manuals go on the shelf")
    head = up.stream.read(5)
    up.stream.seek(0)
    if head != b"%PDF-":
        abort(400, "that is not a PDF")
    library.SHELF.mkdir(parents=True, exist_ok=True)
    target = library.SHELF / name
    up.save(target)
    if target.stat().st_size > library.MAX_PDF_MB * 1024 * 1024:
        target.unlink()
        abort(400, f"larger than {library.MAX_PDF_MB} MB - not a manual")
    log.info("library: %s added to the shelf", name)
    report = library.refresh(only=name)
    # Whoever brought the manual has the radio, until they say otherwise.
    library.set_mine(conn(), name, True)
    return jsonify({"added": name, "report": report,
                    "shelf": library.catalogue(), "mine": library.mine(conn())})


@app.route("/api/library/mine", methods=["POST"])
def api_library_mine():
    """Mark a book as this person's, or not. The shelf stays shared."""
    body = request.get_json(silent=True) or {}
    pdf = library.book(body.get("name"))
    if pdf is None:
        abort(404, "no such book")
    have = library.set_mine(conn(), pdf.name, bool(body.get("mine", True)))
    return jsonify({"mine": have})


@app.route("/api/library/gear")
def api_library_gear():
    """What the shelf says this person has, for Make Contact."""
    return jsonify(library.shelf_gear(conn()))


@app.route("/api/library/remove", methods=["POST"])
def api_library_remove():
    """Take a book off the shelf. Its index goes with it."""
    body = request.get_json(silent=True) or {}
    pdf = library.book(body.get("name"))
    if pdf is None:
        abort(404, "no such book")
    pdf.unlink()
    library.refresh()                    # drops the orphaned index
    log.info("library: %s removed from the shelf", pdf.name)
    return jsonify({"removed": pdf.name, "shelf": library.catalogue()})


@app.route("/library/read/<path:name>")
def library_read(name):
    """A manual, inside ELMER: the way back, the chapters, and the page.

    The kiosk's browser has no tab bar, so a PDF opened on its own is a wall
    with no door. This page keeps ELMER's bar above the browser's viewer,
    with Back and Escape, the publisher's chapters down the side, and - when
    it was reached from a search - the hits in this book, each a tap away.
    """
    pdf = library.book(name)
    if pdf is None:
        abort(404, "no such book")
    meta = next((b for b in library.catalogue() if b["name"] == pdf.name), {})
    try:
        page = max(1, int(request.args.get("page") or 1))
    except ValueError:
        page = 1
    query = (request.args.get("q") or "").strip()[:200]
    hits = []
    if query:
        hits = [h for h in library.search(query, limit=200)["hits"] if h["book"] == pdf.name][:40]
    # Where Back goes: the Library unless the caller said otherwise, and
    # only ever a page of this program's own.
    back = request.args.get("back") or "/library"
    if not back.startswith("/") or back.startswith("//"):
        back = "/library"
    return render_template("library_read.html", name=pdf.name,
                           title=meta.get("title") or pdf.stem, pages=meta.get("pages") or 0,
                           page=page, query=query, hits=hits,
                           outline=library.outline(pdf.name), back=back)


@app.route("/library/book/<path:name>")
def library_book(name):
    """The PDF itself, for the browser's own viewer - `#page=N` on the end
    opens it at the page the search found."""
    pdf = library.book(name)
    if pdf is None:
        abort(404, "no such book")
    return send_from_directory(str(library.SHELF), pdf.name,
                               mimetype="application/pdf", max_age=0)


@app.route("/prints/<print_id>")
def print_view(print_id):
    """One printout, shown in the page rather than handed to the desktop."""
    row = prints.one(print_id)
    if row is None:
        abort(404, "no such printout")
    return render_template("print_view.html", row=row,
                           **profile_block(conn()))


@app.route("/prints/<print_id>.pdf")
def print_file(print_id):
    """The bytes, inline: this is what the viewer and the print dialog read."""
    pdf = prints.read(print_id)
    if pdf is None:
        abort(404, "no such printout")
    row = prints.one(print_id) or {"name": "printout.pdf"}
    how = "attachment" if request.args.get("save") == "1" else "inline"
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'{how}; filename="{row["name"]}"',
        "Content-Length": str(len(pdf))})


@app.route("/api/prints")
def api_prints():
    return jsonify({"prints": prints.shelf(), "keep": prints.KEEP})


@app.route("/api/prints/<print_id>", methods=["DELETE"])
def api_prints_delete(print_id):
    return jsonify({"deleted": prints.forget(print_id)})


def _own_class():
    """The class this station actually holds, from the FCC record where there
    is one.

    Deliberately not the class being *looked at*. The band plan lets anybody
    read any class's privileges, which is worth having and is how somebody
    decides whether the upgrade is worth sitting for - but a printed sheet
    with a callsign on it is read as a claim about that station, and those two
    questions must not be allowed to produce the same document.
    """
    settings = db.get_profile(conn())["settings"]
    record = settings.get("license") or {}
    if record.get("found"):
        return str(record.get("licence_class")
                   or record.get("license_class") or "")
    return str(settings.get("license_class") or "")


@app.route("/api/bandplan/pdf", methods=["POST"])
def api_bandplan_pdf():
    body = request.get_json(force=True) or {}
    license = body.get("class", "Technician")
    if license not in bandplan.CLASSES:
        abort(400, "unknown license class")
    bands = body.get("bands") or [b["name"] for b in bandplan.BANDS]
    state = (body.get("state") or "").upper()
    plan = regional.plan(state) if state else None
    # A callsign goes on a chart only when the chart is of that station's own
    # privileges. Anything else is a study sheet, and a study sheet with a
    # callsign on it is a document somebody can wave - which is not what this
    # program is for and reflects on more people than the one waving it.
    own = _own_class()
    mine = bool(own) and license.lower() == own.lower()
    if body.get("layout") == "card":
        pdf = bandpdf.build_card(
            license, {"callsign": profile_callsign()} if mine else None,
            own=mine)
    else:
        pdf = bandpdf.build(bands, license, plan,
                            interop=bool(body.get("interop")), own=mine)
    card = body.get("layout") == "card"
    name = f"band-plan-{license.lower()}{'-' + state.lower() if state else ''}.pdf"
    if card:
        name = f"band-card-{license.lower()}.pdf"
    log.info("band chart PDF: %s, %d bands, regional=%s", license, len(bands), state or "none")
    row = prints.keep(pdf, name, "band-card" if card else "band-chart",
                      f"{'One-page chart' if card else 'Full band chart'} "
                      f"- {license}" + (f", {state}" if state else ""),
                      {"class": license, "state": state})
    return _print_reply(row, _wants_raw(body))


@app.route("/cw")
def cw_page():
    connection = conn()
    profile = db.get_profile(connection)
    settings = profile["settings"].get("cw") or {}
    return render_template(
        "cw.html", kinds=cw.KINDS, koch_order=cw.KOCH_ORDER,
        cw_settings=settings, progress=db.cw_progress(connection),
        meanings=cw.MEANINGS, chart=cw.chart(), **profile_block(connection))


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
        # What is sent is written <AR>; what a student writes down is AR.
        "plain": cw.plain(text),
        "timing": cw.timing(wpm, effective),
        "lesson_chars": cw.koch_set(lesson) if kind == "koch" else None,
        "meanings": {w: cw.MEANINGS[w] for w in set(cw.plain(text).split())
                     if w in cw.MEANINGS},
    })


@app.route("/api/cw/encode")
def api_cw_encode():
    """Any text as sendable code - what the type-and-hear box posts to.

    Characters with no Morse equivalent are reported rather than dropped in
    silence, because somebody who typed a semicolon and heard nothing has been
    told the tool is broken when in fact the code has no semicolon.
    """
    text = request.args.get("text", "")[:2000]
    try:
        wpm = max(3.0, min(60.0, float(request.args.get("wpm", 20))))
        effective = max(3.0, min(wpm, float(request.args.get("effective", wpm))))
    except ValueError:
        abort(400, "check the numbers")
    groups = cw.encode(text)
    sendable = set(cw.MORSE) | {"<", ">"}
    skipped = sorted({c for c in text.upper()
                      if not c.isspace() and c not in sendable})
    return jsonify({"text": text.upper(), "plain": cw.plain(text),
                    "groups": groups, "skipped": skipped,
                    "characters": sum(len(w) for w in groups),
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


@app.route("/tools")
def tools():
    """The bench, as opposed to the syllabus.

    Split out of the Lab because the Lab is the material the exams ask about
    and these are not: no element has ever asked how to drive a NanoVNA or
    take a sun sight. They are worth having and they were worth moving.
    """
    return render_template("tools.html", **profile_block(conn()))


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


def _open_pools(connection):
    """Which pools this user may study, and the gate state behind that."""
    settings = db.get_profile(connection)["settings"]
    standings = all_standings(connection)
    return gating.open_pools(settings, standings, list(load_pools()))


# How long a wall stands before it takes itself down. Long enough to read the
# sentence on it twice, short enough that nobody is stuck looking at it.
FORBIDDEN_SECONDS = 8


@app.errorhandler(400)
def _bad_request(exc):
    """An API refusal reaches the page that asked, in the language it asked in.

    A 400 carrying a sentence worth reading - "nothing is held for here yet,
    fetch what is near first" - is no use as an HTML error page to something
    that called fetch() and will try to parse it. The pages then report their
    own vaguer guess instead of the reason they were given.
    """
    why = getattr(exc, "description", "") or "That request was not understood."
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"ok": False, "error": why}), 400
    return exc


@app.errorhandler(409)
def _conflict(exc):
    """The same courtesy for a refusal about state - "no round is open",
    "no net is running on this unit". A 409 is always the server declining
    on purpose with a reason, and the reason is the whole point of it.
    """
    why = getattr(exc, "description", "") or "That cannot be done right now."
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"ok": False, "error": why}), 409
    return exc


@app.errorhandler(403)
def _forbidden(exc):
    """A closed door with the way out written on it.

    The framework's own 403 is the word Forbidden and nothing else, which on a
    kiosk is a dead end: a full-screen browser has no back button and nobody
    is standing there to type a URL. So a page, with the reason the gate gave,
    Escape bound to leave, and a clock that leaves on its own.

    An API keeps its JSON. Something fetching /api and handed a page back
    would report a parse error instead of the refusal, which is a worse
    message about a working refusal.
    """
    why = getattr(exc, "description", "") or "That is not open yet."
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"ok": False, "error": why}), 403
    referrer = request.referrer or ""
    here = request.host_url.rstrip("/")
    back = referrer if referrer.startswith(here) and referrer != request.url \
        else url_for("home")
    # The top bar is part of the way out, so this page is a page like any
    # other and needs what every page is given.  A handler that cannot build
    # that - no database, no user yet - must still answer, because the one
    # thing a dead end must not do is become a second dead end.
    try:
        block = profile_block(conn())
    except Exception:
        log.exception("could not build the page around a 403")
        return (f"<h1>Not open yet</h1><p>{escape(why)}</p>"
                f"<p><a href=\"{escape(back)}\">Back</a></p>"), 403
    return render_template("forbidden.html", why=why, back=back,
                           seconds=FORBIDDEN_SECONDS, **block), 403


def _studyable_or_403(connection, pool_id):
    """A pool the user may actually study. Closed is not the same as missing.

    404 would be a lie - the pool is there and its questions ship with every
    copy. It is closed, which is a different thing, and the reply says which
    pool would open it.
    """
    pool = _pool_or_404(pool_id)
    allowed, state = _open_pools(connection)
    if pool_id not in allowed:
        abort(403, gating.why_closed(pool_id, state) or "not open yet")
    return pool


# --------------------------------------------------------------------------
# study API
# --------------------------------------------------------------------------

@app.route("/api/next")
def api_next():
    pool = _studyable_or_403(conn(), request.args.get("pool", ""))
    mode = request.args.get("mode", "drill")
    section = request.args.get("section")
    exclude = set(filter(None, request.args.get("exclude", "").split(",")))
    connection = conn()
    cards = db.cards_for_pool(connection, pool.pool_id)

    sections = {section} if section else None
    # Drill is the mode with a day that can be finished; the others are
    # deliberate choices to work on something specific and are not rationed.
    plan = srs.day_plan(connection, pool.pool_id) if mode == "drill" else None
    queue = srs.due_queue(
        pool, cards, limit=None, sections=sections,
        new_left=plan["new_left"] if plan else None,
        review_left=plan["review_left"] if plan else None)
    if plan and not queue:
        return jsonify({
            "done": True, "finished_today": True, "plan": plan,
            "reason": (f"That is today's study done - {plan['new_done']} new "
                       f"and {plan['review_done']} reviewed. More tomorrow, "
                       f"when it will do the most good.")})

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
    pool = _studyable_or_403(conn(), body.get("pool", ""))
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
        # Forgetting something you had learned is a different event from
        # missing something new, and only the first is worth remarking on.
        # srs counts a lapse on any miss - a card seen for the first time and
        # got wrong lands there too - so the test is what the card was worth
        # before it slipped: it had graduated past the same-session relearn
        # and was being held at a real spacing.
        "lapsed": bool(not correct and card and card["reps"] > 0
                       and (card["interval"] or 0) >= srs.LEARNED_DAYS),
        "was_interval": round(card["interval"], 1) if card else 0.0,
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
        # A measured MUF is worth writing down whenever one comes in, not only
        # when somebody opens the band plan: the skill record is built from
        # these, and the dashboard is the page that is always open.
        try:
            if loc.get("lat") is not None:
                forecastlog.measured(snap)
        except Exception:                          # never at the page's expense
            log.exception("forecast ledger")
    return jsonify(snap)


@app.route("/api/path-bands")
def api_path_bands():
    """Which band could carry a contact this far, when line of sight cannot.

    The path tool answers whether two antennas can see each other, and past
    about fifty miles they never can. That is not the end of the contact - it
    has moved to the ionosphere - so this is the other half of the answer,
    over the same distance the path tool just measured.
    """
    try:
        km = float(request.args.get("km", "0"))
    except (TypeError, ValueError):
        abort(400, "km must be a number")
    if not 0 < km <= 20100:
        abort(400, "that is not a distance on this planet")
    connection = conn()
    profile = db.get_profile(connection)
    place = qth_for(connection, profile)
    snap = propagation.snapshot(lat=place.get("lat"), lon=place.get("lon"))
    try:
        watts = max(1.0, min(1500.0, float(request.args.get("watts", "100"))))
    except (TypeError, ValueError):
        watts = 100.0
    # The height comes off the snapshot with everything else. It used to be
    # looked up separately here, which is a second fetch and a second chance
    # for this page to disagree with the band conditions page about what the
    # ionosphere is doing.
    out = propagation.path_bands(
        km, fof2=snap.get("fof2"),
        hmf2=snap.get("hmf2") or propagation.HMF2_DEFAULT,
        elevation=snap.get("elevation") or 0.0,
        k_index=snap.get("k_index") or 2.0, muf=snap.get("muf"), watts=watts)
    out["ok"] = True
    out["muf"] = snap.get("muf")
    out["hmf2_measured"] = bool(snap.get("hmf2_measured"))
    return jsonify(out)


def _calibration_summary(table):
    """The table as one sentence's worth of facts: when, on what, and this
    month's factors - for the strip under the band, not the whole table."""
    if not table:
        return None
    month = datetime.now(timezone.utc).strftime("%m")
    entry = (table.get("months") or {}).get(month) or {}
    cells = forecastlog.month_cells(entry)
    return {"made": entry.get("_made") or table.get("made"), "days": entry.get("_days") or table.get("days"),
            "stations": entry.get("_stations") or table.get("stations") or [],
            "months_known": len(table.get("months") or {}),
            "coverage": forecastlog.coverage(table),
            "this_month": {k: {"factor": v["factor"], "n": v["n"], "applied": v["applied"]}
                           for k, v in cells.items()}}


# --------------------------------------------------------------------------
# calibrate my forecast
# --------------------------------------------------------------------------

@app.route("/api/calibrate", methods=["POST"])
def api_calibrate_start():
    """Begin the year-long blind run for this unit's QTH - about five
    minutes on a Pi. Local screen only: it is this unit's CPU for five
    minutes and this unit's table at the end of it."""
    if not _is_local(request.remote_addr):
        abort(403)
    settings = db.get_profile(conn())["settings"]
    loc = settings.get("location") or {}
    if loc.get("lat") is None:
        abort(400, "set a QTH first - the forecast is about a place, and so is its calibration")
    body = request.get_json(silent=True) or {}
    try:
        days = max(30, min(400, int(body.get("days") or 365)))
    except ValueError:
        days = 365
    log.info("calibration: started for %s, %d days", loc.get("short") or loc.get("grid"), days)
    return jsonify(calibrate.start(loc["lat"], loc["lon"], days=days,
                                   build=bugreport.build_stamp().get("commit") or "",
                                   place=loc.get("short") or loc.get("grid") or ""))


@app.route("/api/calibrate/status")
def api_calibrate_status():
    return jsonify(calibrate.status())


@app.route("/api/cards")
def api_cards():
    """A card for a screen that is waiting: the history deck, the quotes,
    or the hams people have heard of. `avoid` is the last one shown."""
    deck = request.args.get("deck") or "history"
    return jsonify(trivia.draw(avoid=request.args.get("avoid"), deck=deck))


@app.route("/api/calibrate/stop", methods=["POST"])
def api_calibrate_stop():
    if not _is_local(request.remote_addr):
        abort(403)
    return jsonify({"stopped": calibrate.stop()})


@app.route("/api/propagation/outlook")
def api_propagation_outlook():
    """Band by band: how good it is now, and how the next day looks.

    The wall-chart rating says Poor, Fair or Good for a group of bands twice a
    day. This is the same question asked hour by hour for one band, which is
    the form the answer is needed in when the decision is whether to call CQ on
    SSB now or come back at eight and use CW.

    Nothing here fetches: it works from the space-weather snapshot the
    dashboard already caches and from the ionosonde reading if one happens to
    be in hand, so opening the band plan costs no network at all.
    """
    connection = conn()
    settings = db.get_profile(connection)["settings"]
    loc = settings.get("location") or {}
    lat, lon = loc.get("lat"), loc.get("lon")
    snap = propagation.snapshot(lat=lat, lon=lon)
    if not snap.get("ok"):
        return jsonify({"ok": False, "error": snap.get("error", "no space weather")})

    # The snapshot has already been anchored to the ionosonde network, so there
    # is nothing to redo here. It used to be redone - a second anchor with a
    # second radius and a different secant factor - and those two answers are
    # what had the band plan and the propagation page quoting different MUFs
    # for the same sky at the same moment.
    cal = snap.get("calibration")
    muf = snap["muf"]
    anchor = cal["factor"] if cal else 1.0
    m3000 = cal["m3000"] if cal else propagation.M3000_DEFAULT
    station = {"name": cal["nearest"], "km": cal["nearest_km"],
               "age_minutes": cal["age_minutes"],
               "measured": cal["measured_fof2"],
               "stations": cal["stations"]} if cal else None

    # What this unit's own record says the model runs over or under the sondes
    # by, by sky - applied where the anchor has let go, and said on the page.
    adj = forecastlog.adjustment()
    bias = forecastlog.applied_bias(adj)
    table = forecastlog.calibration()
    # The record's own forecast for each of the next 25 hours: the measured
    # MUF at that hour of day over the last few days, where the ledger has
    # it. Computed once for every band, since it is about the sky, not the band.
    start_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    record_hours = [(start_hour + timedelta(hours=i)).isoformat() for i in range(25)]
    persist = forecastlog.persistence(record_hours) if lat is not None else None
    persist_days = max((p["days"] for p in (persist or []) if p), default=0)

    # With no QTH there is no sun angle, so the snapshot's assumed one is used
    # - the same one it computed its own MUF from, so the two cannot drift.
    elevation = snap["elevation_used"]
    k_index = snap.get("k_index") or 0
    # Where this station sits relative to the auroral oval, and where the feed
    # says the oval's edge is tonight. Without these the K index costs the same
    # in Miami as at Fairbanks, which it does not.
    geomag = (propagation.geomagnetic_latitude(lat, lon)
              if lat is not None and lon is not None else None)
    aurora_lat = snap.get("aurora_lat") or None
    rated = {row["band"]: row for row in snap.get("bands", [])}

    bands = []
    for name, mhz, _group in propagation.BANDS:
        # The snapshot's height, which is the measured one where a sonde is in
        # reach. This used to read cal["hmf2"] - a key calibration has never
        # had - so it fell through to a textbook 300 km every time while
        # looking for all the world as though it were using the network.
        now = propagation.band_score(mhz, muf, elevation, k_index,
                                     snap.get("fof2"),
                                     snap.get("hmf2") or propagation.HMF2_DEFAULT,
                                     geomag_lat=geomag, aurora_lat=aurora_lat)
        # When there is a hole in the middle, say what covers it. Ground wave
        # is the only thing that reaches into a skip zone, and it is the one
        # kind of propagation the antenna really does decide.
        if now.get("skip_km"):
            now["ground_wave"] = groundwave.describe(mhz, watts=100.0)
        hours, when = [], []
        if lat is not None:
            when = propagation.outlook(mhz, lat, lon, snap["sfi"], k_index,
                                       anchor=anchor, m3000=m3000,
                                       aurora_lat=aurora_lat,
                                       # The sky the anchor was measured under.
                                       # Without it a night calibration is
                                       # carried through the following noon.
                                       anchor_sun=(cal or {}).get("sun_deg"),
                                       # Measured where a sonde is in reach, so
                                       # the 24 hours and the hour agree about
                                       # how high the layer is.
                                       hmf2=snap.get("hmf2")
                                       or propagation.HMF2_DEFAULT,
                                       bias=bias, calibration=table,
                                       persist=persist)
            hours = [{"at": row["at"], "score": row["score"], "muf": row["muf"],
                      "regime": row["regime"], "day": row["day"]}
                     for row in when]
        # Ours against the wall chart's, with the disagreement said out loud
        # rather than left for the reader to spot. Neither is corrected toward
        # the other; see propagation.reconcile.
        now["wall"] = propagation.reconcile(
            now.get("score"), (rated.get(name) or {}).get("rating", ""),
            snap.get("muf_source"))
        bands.append({"band": name, "mhz": mhz, "now": now,
                      "rating": (rated.get(name) or {}).get("rating", ""),
                      "note": (rated.get(name) or {}).get("note", ""),
                      "hours": hours,
                      "windows": propagation.windows(when) if when else []})
    # The clock times behind the hourly strip. Nothing is fetched for these and
    # nothing is cached: `celestial` already computes the sun's altitude for an
    # instant in order to reduce a sextant sight, and a rise time is that same
    # arithmetic solved the other way round - for the moment rather than for the
    # height. A unit with the network unplugged answers this for any date.
    #
    # Two heights, because they are two different events and the difference is
    # the whole grey-line argument: the sun leaves the ground at -0.833 (upper
    # limb, refraction and semidiameter included, which is what an almanac
    # prints) and leaves the D layer 80 km up at D_LAYER_DIP below that. The
    # gap between them is the window where the absorber is collapsing and the
    # reflector is still lit.
    sun_times = None
    if lat is not None and lon is not None:
        now_utc = datetime.now(timezone.utc)

        def _iso(t):
            return t.isoformat() if t else None

        ground = celestial.rise_set(lat, lon, now_utc)
        d_layer = celestial.rise_set(lat, lon, now_utc,
                                     altitude=-propagation.D_LAYER_DIP)
        sun_times = {
            "rise": _iso(ground["rise"]), "set": _iso(ground["set"]),
            "up_all_day": ground["up_all_window"],
            "down_all_day": ground["down_all_window"],
            # Where the sun stands for the D layer: it rises there first and
            # sets there last, so these bracket the ground times.
            "d_layer_rise": _iso(d_layer["rise"]),
            "d_layer_set": _iso(d_layer["set"]),
            "d_layer_dip": round(propagation.D_LAYER_DIP, 2),
        }

    # The ledger: this hour's outlook written down with what it was drawn
    # from, the measured MUF written down if there is one, and the verdict
    # on whether the outlook moved more than the sky did since last time.
    record = None
    if lat is not None:
        try:
            forecastlog.measured(snap)
            verdict = forecastlog.record(
                bands, {"sfi": snap["sfi"], "k_index": k_index, "muf_now": muf,
                        "muf_source": snap["muf_source"], "fof2": snap.get("fof2"),
                        "hmf2": snap.get("hmf2"), "hmf2_measured": snap.get("hmf2_measured"),
                        "m3000": m3000, "anchor": anchor, "lat": lat, "lon": lon,
                        "adjustment": bias},
                bugreport.build_stamp().get("commit"))
            record = {"adjustment": adj, "skill": forecastlog.skill(),
                      "drift": verdict if (verdict and verdict["moved"]) else forecastlog.latest_drift(),
                      "calibration": _calibration_summary(table),
                      "persistence": {"days": persist_days,
                                      "hours": sum(1 for p in (persist or []) if p)}}
        except Exception:                          # the ledger must never cost the page
            log.exception("forecast ledger")

    return jsonify({"ok": True, "located": lat is not None,
                    "record": record,
                    "muf": muf, "muf_source": snap["muf_source"],
                    "fof2": snap["fof2"], "station": station,
                    "sfi": snap["sfi"], "k_index": k_index,
                    "a_index": snap.get("a_index"),
                    "is_day": snap.get("is_day"),
                    "regime": snap.get("regime"),
                    "elevation": snap.get("elevation"),
                    "verdict": snap.get("verdict", ""),
                    # Above about 30 MHz the model has nothing to say, so what
                    # the network is reporting is passed through instead.
                    "vhf": snap.get("vhf") or {},
                    "aurora": snap.get("aurora"),
                    "geomag_lat": round(geomag, 1) if geomag is not None else None,
                    "aurora_lat": aurora_lat,
                    "sun": sun_times,
                    "fetched": snap.get("fetched"), "bands": bands})


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
    # The license class comes from the profile, so the evaluation can say when
    # the operation it is evaluating would not be permitted in the first place.
    station.setdefault("license_class",
                       profile["settings"].get("license_class") or "")
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
    row = prints.keep(pdf, name, "rf-exposure",
                      f"Station RF exposure record - {call}",
                      {"callsign": call, "date": station["date"],
                       "compliant": evaluation["compliant"]})
    return _print_reply(row, _wants_raw(request.get_json(silent=True) or {}))


@app.route("/api/callsign/<call>")
def api_callsign(call):
    """Look up a US amateur license. 503 when the lookup cannot be reached."""
    found = callsign.lookup(call, refresh=request.args.get("refresh") == "1")
    if found is None:
        return jsonify({"ok": False,
                        "error": "license lookup unavailable - check the "
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


# ------------------------------------------------------------------- party
# A study party is a room on one unit: cohorts of players racing the same
# question, timed by their own clocks. None of it touches the database while a
# round is running - see elmer/party.py for why.

POOL_DIFFICULTY = {v: k for k, v in party.DIFFICULTIES.items()}


def _tournament_choices():
    """What a tournament can be run on, grouped by track for the pickers."""
    order = list(party.DIFFICULTIES)
    return ([(k, party.LABELS[k]) for k in order
             if party.TRACK_OF.get(k) == "amateur"],
            [(k, party.LABELS[k]) for k in order
             if party.TRACK_OF.get(k) == "commercial"])


def _net_name_for(difficulty):
    """What to call a net, so several on one network tell themselves apart.

    A hamfest can easily hold three at once - Technician in one corner,
    General in another, Extra in the next room - and "ELMER Net" three times
    over tells a unit deciding where to report exactly nothing. The material is
    the thing that distinguishes them, so it is the name.
    """
    label = party.LABELS.get(difficulty, "").split("\u2014")[0].strip()
    return f"{label} net" if label else "ELMER Net"


def _party_or_404():
    room = party.room()
    if room is None:
        abort(404, "no party is running on this unit")
    return room


@app.route("/api/party/open", methods=["POST"])
def api_party_open():
    """Start a party on this unit. The host's screen calls this once."""
    body = request.get_json(silent=True) or {}
    party.close_room()
    room = party.room(create=True, cohorts=int(body.get("cohorts", 2) or 2))
    log.info("party opened: %d cohorts, cap %d",
             len(room.cohorts), room.health()["cap"])
    return jsonify(room.state())


@app.route("/api/party/join", methods=["POST"])
def api_party_join():
    """Take a seat, if there is one.

    A refusal is a normal answer here, not an error to be swallowed: the whole
    point of the cap is that somebody is told to use the next unit rather than
    being let in to make the round slow for everybody.
    """
    room = _party_or_404()
    body = request.get_json(silent=True) or {}
    cohort = body.get("cohort")
    player, why = room.join(body.get("name"), int(cohort) if cohort else None,
                            cert_name=body.get("cert_name"),
                            device=body.get("device"),
                            previous=body.get("previous"),
                            license=body.get("license"))
    if player is None:
        return jsonify({"joined": False, "reason": why,
                        "health": room.health()}), 409
    # Somebody is here now, so the table stops waiting to be told. A person
    # who scanned the code and got a screen that says "waiting" with nothing
    # behind it has been handed a broken program, whatever the code does.
    _party_arm_start(room)
    return jsonify({"joined": True, "player": player.as_dict(),
                    "state": room.state(player.id)})


def _with_hall(state):
    """The hall's shootout, as this table sees it, on the table's own state.

    The pick in a hall shootout is the table's, and the subjects went up on
    the table's screen alone - which is not what anybody at the table was
    looking at. Reported from the second Pi: "the driver said it was my turn
    to choose, and nothing appeared." So every phone at the picking table
    gets the subjects too, and any of them may tap.
    """
    link = cohort.bridge()
    if link is not None and getattr(link, "hall_shootout", None):
        state["hall"] = {"shootout": link.hall_shootout,
                         "table": link.name, "mode": link.net_mode}
    return state


@app.route("/api/party/state")
def api_party_state():
    """What every device polls. Cheap on purpose: no database, no exam maths."""
    room = _party_or_404()
    started = time.perf_counter()
    try:
        who = int(request.args.get("player", "")) or None
    except ValueError:
        who = None
    state = _with_hall(room.state(who))
    # Whether the device polling this may start the game itself. One person
    # alone on an idle table gets the press; in a hall with others already in,
    # the table screen keeps it, so one phone cannot start a round while the
    # instructor is still talking.
    state["may_start"] = bool(room.people_here() == 1
                              and _party_may_begin(room))
    # Feed the moving cap with what this unit is really delivering.
    room.note_service((time.perf_counter() - started) * 1000.0)
    return jsonify(state)


@app.route("/api/party/round", methods=["POST"])
def api_party_round():
    """Put a question to the room.

    The difficulty is the license class, which is the pool. One shuffle is
    drawn here and shown to everybody, because two people looking at the same
    question in different orders are not racing the same question.
    """
    room = _party_or_404()
    body = request.get_json(silent=True) or {}
    try:
        rnd = _ask_party(body.get("difficulty", "technician"),
                         body.get("section"), body.get("seconds"))
    except ValueError as exc:
        abort(400, str(exc))
    log.info("party round %d: %s %s", rnd.number, rnd.pool_id, rnd.question_id)
    return jsonify(room.state())


@app.route("/api/party/answer", methods=["POST"])
def api_party_answer():
    """One answer, timed by the player's own clock."""
    room = _party_or_404()
    started = time.perf_counter()
    body = request.get_json(silent=True) or {}
    try:
        who = int(body.get("player"))
    except (TypeError, ValueError):
        abort(400, "need a player id")
    chosen = body.get("chosen")
    rnd = room.round
    server_ms = (time.monotonic() - rnd.opened_at) * 1000.0 if rnd else None
    entry, why = room.submit(who, chosen, body.get("ms"), server_ms)
    room.note_service((time.perf_counter() - started) * 1000.0)
    if entry is None:
        return jsonify({"accepted": False, "reason": why}), 409
    # Correctness is deliberately not returned yet: it is revealed when the
    # round closes, so nobody learns the answer by watching a neighbour.
    return jsonify({"accepted": True, "ms": entry["ms"],
                    "everyone_in": room.everyone_answered()})


# How long a table waits after somebody arrives before it starts by itself.
# Long enough for a second and a third person to get in behind the first,
# short enough that one operator with a phone is not left reading a countdown.
AUTO_START_SECONDS = 15.0


def _party_under_net():
    """Whether this table takes its rounds from somebody else.

    A table in a hall answers the question net control put up. One that
    started its own would have its players answering something nobody else in
    the room was looking at, so nothing here fires while a net has it.
    """
    return cohort.bridge() is not None


def _party_playing(room):
    """Whether a game is already under way, by whatever route.

    A round whose clock has run out and that nothing is driving is not a game
    in progress, it is the wreckage of one - and counting it as live is how a
    table stopped mid-question stays unstartable for ever, which is the same
    dead end this exists to remove, one step further in.
    """
    director = autoplay.director()
    if director and (director.as_dict() or {}).get("running"):
        return True
    rnd = room.round
    return rnd is not None and not rnd.closed and not rnd.expired()


def _party_may_begin(room):
    """Whether this table is free to start a game on its own account."""
    return (not _party_under_net() and not _party_playing(room)
            and room.people_here() > 0)


def _party_class():
    """What to ask when nobody has said: the class the operator is studying.

    Needs a request to read the profile, so it is worked out while one is in
    hand and carried into the timer rather than looked up from inside it.
    """
    settings = db.get_profile(conn())["settings"]
    named = (settings.get("license_class")
             or (settings.get("license") or {}).get("license_class") or "")
    named = str(named).strip().lower()
    return named if named in party.DIFFICULTIES else "technician"


def _party_begin(room, difficulty, armed_only=False):
    """Put the first question up and let the director carry it from there."""
    if armed_only and not room.waiting_to_start():
        return False                     # somebody started it, or all left
    room.disarm_start()
    if not _party_may_begin(room):
        return False
    room.end_shootout()               # what starts on its own is a tournament
    room.fill_bots(None)
    seconds = party.DEFAULT_ROUND_SECONDS
    autoplay.start(room, lambda: _ask_party(difficulty, None, seconds))
    log.info("party: started on its own (%s)", difficulty)
    return True


def _party_pick_net(nets, mine):
    """Which of the nets out there this table should report to.

    The table chooses, not the player.  A General sitting down at a table in a
    Technician net answers Technician questions, which is material they have
    already passed and are therefore being asked to recall at speed - which is
    practice, and cheap practice at that.  Splitting a table's players onto
    different material would mean four people at one table racing four
    different questions, and that is not a race.

    So: the net studying what this unit studies, if there is one, and the
    busiest net otherwise.  `nets` arrives sorted with the fullest first.
    """
    for net in nets:
        if (net.get("difficulty") or "").lower() == mine:
            return net
    return nets[0] if nets else None


def _party_auto_join(room):
    """Attach this table to a net it can hear, before it starts one of its own.

    This is the difference between a room of Pis playing together and a room
    of Pis each running its own quiz.  Everything needed for the first has
    been here all along - net control serves one question to every table, the
    tables run their own rounds and time on the player's own clock - but the
    only way to wire a table in was for somebody to type an address into it,
    and the auto-start then committed the unit to playing alone fifteen
    seconds after anybody sat down.

    Returns True if this table is now somebody's table.
    """
    if cohort.bridge() is not None:
        return True                       # already reporting to somebody
    if netcontrol.net() is not None:
        # Hosting.  Its own table belongs in its own hall, and never in
        # somebody else's: a host that wandered off into a neighbour's net
        # would be serving one room and answering another.
        return False
    connection = conn()
    if not cohort.auto_join_wanted(connection):
        return False
    live = discovery.neighbourhood()
    if live is None:
        return False
    try:
        heard = live.nets()
    except Exception:                     # a roster is never worth a 500
        return False
    chosen = _party_pick_net(heard, _party_class())
    if not chosen:
        return False
    party.room(create=True, cohorts=1)
    link = cohort.connect(chosen["url"], None, None, conn=connection)
    log.info("cohort: heard %s at %s and joined it", chosen["name"], link.url)
    return True


def _party_arm_start(room):
    """Join a net if one can be heard, and otherwise start on our own account."""
    if _party_auto_join(room):
        return                            # the hall's rounds arrive by wire
    if room.waiting_to_start() or not _party_may_begin(room):
        return
    difficulty = _party_class()
    room.arm_start(AUTO_START_SECONDS)
    threading.Timer(AUTO_START_SECONDS + 0.25,
                    lambda: _party_begin(room, difficulty, True)).start()


def _ask_party(difficulty="technician", section=None, seconds=None):
    """Put one question to the table. Shared by the button and the director."""
    pool_id = party.DIFFICULTIES.get(str(difficulty).lower())
    if not pool_id:
        raise ValueError(f"difficulty must be one of {sorted(party.DIFFICULTIES)}")
    pool = _pool_or_404(pool_id)
    room = _party_or_404()
    if room.mode == party.SHOOTOUT and not section:
        # In a shootout the subject is the picker's, not the button's. A
        # practice player holding the pick chooses now; a person's choice is
        # waited for, and pressing the button before they have made it is
        # told so rather than handed a question from nowhere.
        if room.shootout_over():
            raise ValueError("the shootout is over")
        room.choose_for_bot()
        section = room.take_pick()
        if not section:
            who = (room.shootout_view() or {}).get("picker_name") or "the picker"
            raise ValueError(f"waiting for {who} to choose the subject")
    ids = [q["id"] for q in pool.by_id.values()
           if not section or q["section"] == section]
    if not ids:
        raise ValueError("no questions in that section")
    question = pool.by_id[random.choice(ids)]
    shown = presentation(question)
    return room.start_round(
        pool_id, question["id"], shown["answer"],
        seconds=float(seconds or party.DEFAULT_ROUND_SECONDS),
        payload={"text": question["text"], "choices": shown["choices"],
                 "section": question["section"],
                 "section_title": pool.section_title(question["section"]),
                 "figure": pool.figure_url(question),
                 "difficulty": str(difficulty).lower()})


def _headline(shouted):
    """COMMISSION'S RULES, as a heading: str.title() gives Commission'S."""
    return " ".join(w[:1].upper() + w[1:].lower() for w in str(shouted).split())


def _subject_name(long_title, limit=48):
    """The first clause of a section title, which is what the section is."""
    head = re.split(r"[;:]", str(long_title or ""), 1)[0].strip()
    if len(head) > limit:
        cut = head[:limit].rsplit(" ", 1)[0].rstrip(" ,")
        return cut + "\u2026"
    return head


@app.route("/api/party/mode", methods=["POST"])
def api_party_mode():
    """Which game this table is playing: a tournament, or a shootout.

    A shootout needs the subjects of the pool being played, with their titles,
    because "T5C" is a filing reference and "Electrical principles" is a thing
    somebody can decide they are good at. The class comes from the body or
    from what this operator is studying, the same way the tournament's does.
    """
    room = _party_or_404()
    body = request.get_json(silent=True) or {}
    wanted = str(body.get("mode") or party.TOURNAMENT).lower()
    if wanted not in party.MODES:
        abort(400, f"mode must be one of {list(party.MODES)}")
    if room.round is not None and not room.round.closed:
        abort(409, "a question is still open")
    if wanted == party.SHOOTOUT:
        difficulty = str(body.get("difficulty") or _party_class()).lower()
        pool_id = party.DIFFICULTIES.get(difficulty)
        if not pool_id:
            abort(400, f"difficulty must be one of {sorted(party.DIFFICULTIES)}")
        pool = _pool_or_404(pool_id)
        # The pool's section titles are whole sentences - "Current and
        # voltage: terminology and units, conductors and insulators,
        # alternating and direct current" - and thirty-three of them on a
        # phone with a clock running is a wall. The first clause is the
        # subject; the subelement it sits in is the heading.
        titles = {code: _subject_name(pool.section_title(code))
                  for code in pool.section_order}
        groups = {}
        for code in pool.section_order:
            sub = pool.subelement_of(code)
            meta = pool.subelement_meta.get(sub) or {}
            groups[code] = (sub, _headline(meta.get("title") or sub))
        # Practice players sit down first, because the shootout fixes its
        # seating order the moment it starts: a bot that arrived afterwards
        # would answer every question and never be able to take a letter.
        room.fill_bots(body.get("level"))
        started, why = room.begin_shootout(list(pool.section_order), titles,
                                           groups, body.get("pick_seconds"))
        if started is None:
            abort(409, why)
        # The director carries it from here, waiting on the pick between
        # questions.
        seconds = float(body.get("seconds") or party.DEFAULT_ROUND_SECONDS)
        autoplay.start(room, lambda: _ask_party(difficulty, None, seconds))
        log.info("party: shootout started (%s, %d players)", difficulty,
                 len(room.players))
    else:
        room.end_shootout()
        log.info("party: back to a tournament")
    return jsonify(room.state())


@app.route("/api/party/pick", methods=["POST"])
def api_party_pick():
    """The picker names the subject of the next question."""
    room = _party_or_404()
    body = request.get_json(silent=True) or {}
    try:
        who = int(body.get("player"))
    except (TypeError, ValueError):
        abort(400, "need a player id")
    section = str(body.get("section") or "").strip()
    chosen, why = room.choose(who, section)
    if chosen is None:
        # Refused in words, because "it is not your pick" is the thing the
        # person who pressed the button needs to be told.
        return jsonify({"ok": False, "message": why}), 409
    log.info("party: %s picked %s", who, chosen)
    return jsonify({"ok": True, "section": chosen,
                    "shootout": room.shootout_view(who)})


@app.route("/api/party/bots", methods=["POST"])
def api_party_bots():
    """Switch practice opponents on or off for this table."""
    room = _party_or_404()
    body = request.get_json(silent=True) or {}
    if body.get("on", True):
        room.fill_bots(body.get("level"))
    else:
        room.clear_bots()
    return jsonify(room.state())


@app.route("/api/party/auto", methods=["POST"])
def api_party_auto():
    """Start or stop a match that runs itself.

    Once started, questions follow one another: the round closes when everyone
    has answered or the clock runs out, the result stands for a moment, and the
    next question goes up. The game master starts it and can stop it; nothing
    in between needs a button.
    """
    room = _party_or_404()
    body = request.get_json(silent=True) or {}
    if not body.get("on", True):
        autoplay.stop()
        return jsonify({"auto": autoplay.director().as_dict()
                        if autoplay.director() else None, "running": False})
    room.disarm_start()          # a press beats a countdown
    difficulty = str(body.get("difficulty", "technician")).lower()
    seconds = float(body.get("seconds") or party.DEFAULT_ROUND_SECONDS)
    section = body.get("section")
    rounds = body.get("rounds")
    # A tournament is not a shootout. Left in shootout mode after one had
    # finished, the table would take the draw as "the shootout is over" and
    # the tournament button would start a director that stopped at once.
    room.end_shootout()
    if body.get("bots", True):
        room.fill_bots(body.get("level"))
    driver = autoplay.start(
        room, lambda: _ask_party(difficulty, section, seconds),
        rounds=int(rounds) if rounds else None,
        reveal=float(body.get("reveal") or autoplay.REVEAL_SECONDS))
    return jsonify({"running": True, "auto": driver.as_dict(),
                    "state": room.state()})


@app.route("/api/party/end", methods=["POST"])
def api_party_end():
    """Pack the table up: stop the match, dismiss the practice players, close
    the room. Leaving the screen is not the same as finishing, and somebody who
    is done should be able to say so rather than leaving a tournament running
    on a Pi nobody is looking at."""
    autoplay.stop()
    room = party.room()
    if room is not None:
        room.clear_bots()
    party.close_room()
    log.info("party: table closed")
    return jsonify({"open": False})


@app.route("/api/net/end", methods=["POST"])
def api_net_end():
    """Close the net. Tables will find it gone and carry on by themselves."""
    # Whatever was conducting it stops with it - a conductor ticking a net
    # that is gone would keep asking questions into an empty room - and the
    # host's own table is let go with it, or it would sit reporting to a net
    # that has closed instead of playing for the people in front of it.
    hall.halt()
    cohort.disconnect(conn())
    netcontrol.close_net()
    log.info("net control: closed")
    return jsonify({"open": False})


@app.route("/api/party/auto-state")
def api_party_auto_state():
    """Whether a tournament is running on this table."""
    driver = autoplay.director()
    return jsonify({"auto": driver.as_dict() if driver else None})


@app.route("/api/party/close", methods=["POST"])
def api_party_close():
    """Score the round and say who picks next."""
    room = _party_or_404()
    summary = room.close_round()
    if summary is None:
        abort(409, "no round is open")
    return jsonify({"summary": summary, "state": room.state()})


@app.route("/api/party/start-now", methods=["POST"])
def api_party_start_now():
    """Begin, at the request of the one person sitting here.

    The rule is checked here rather than trusted from the screen that offered
    it: a phone may start a game it is alone in, and may not start one in a
    room that has other people in it or that is taking its rounds from a net.
    """
    room = _party_or_404()
    if room.people_here() != 1 or not _party_may_begin(room):
        return jsonify({"started": False,
                        "reason": "this table is not yours to start"}), 409
    started = _party_begin(room, _party_class())
    return jsonify({"started": started, "state": room.state()})


@app.route("/api/party/leave", methods=["POST"])
def api_party_leave():
    room = _party_or_404()
    body = request.get_json(silent=True) or {}
    try:
        room.leave(int(body.get("player")))
    except (TypeError, ValueError):
        abort(400, "need a player id")
    # A countdown for an empty room is a Pi talking to itself.
    if room.people_here() == 0:
        room.disarm_start()
    return jsonify(room.state())


def _join_url(table):
    """The address a phone should be sent to, as seen from the hall.

    Not request.host_url: the table screen is very often the kiosk browser on
    the Pi itself, which would bake in "localhost" and hand every phone in the
    room an address that means their own handset.
    """
    return f"{_here()}/j/{table}"


@app.route("/party")
@app.route("/party/<table>")
def party_table(table="1"):
    """The screen that sits on the table: the join code, and round control."""
    running = party.room()
    if running is None:
        running = party.room(create=True, cohorts=1)
    url = _join_url(table)
    wanted = str(request.args.get("difficulty", "")).lower()
    if wanted not in party.DIFFICULTIES:
        wanted = "technician"
    amateur, commercial = _tournament_choices()
    return render_template(
        "party_table.html", table=table, name=f"Table {table}",
        difficulty=wanted, join_url=url, amateur=amateur, commercial=commercial,
        qr_svg=qr.as_svg(url, module=7, quiet=3))


@app.route("/j/<table>")
def party_join(table):
    """Where the QR code lands: a phone, at one table."""
    if party.room() is None:
        abort(404, "no party is running on this unit")
    return render_template("party_player.html", table=table,
                           name=f"Table {table}")


# --------------------------------------------------------------- net control
# One master unit running a competition across many cohort units. The traffic
# here is one conversation per unit, not one per player - see netcontrol.py.

def _net_or_404():
    running = netcontrol.net()
    if running is None:
        abort(404, "no net is running on this unit")
    return running


def _open_net(wanted, name=None, section=None, seconds=None):
    """Open a net here, whichever way somebody asked for one.

    There are two ways in - the button, and simply arriving at the host screen
    - and they used to build different nets.  Arriving at /net made one
    straight out of netcontrol with no conductor, no table for the people at
    this machine, and nothing said in the log, so a hall opened that way sat
    at nought tables until somebody pressed for every question by hand.  A
    second way of doing a thing is a second thing to keep working; there is
    one now.
    """
    connection = conn()
    hall.halt()                       # the old net's conductor goes with it
    netcontrol.close_net()
    # A unit cannot be its own net and somebody else's table at once - it
    # would be taking questions from one hall while serving another.  Opening
    # a net says which of the two this machine is.
    cohort.disconnect(connection)
    running = netcontrol.net(create=True, difficulty=wanted,
                             name=str(name or _net_name_for(wanted))[:60])
    log.info("net control opened: %s", running.name)
    # Every round the hall closes is written to this unit's hall log: each
    # person's answer with its question and its time, which is the difficulty
    # measure's raw material - twenty tables' worth in an evening, where one
    # person studying alone contributes one line at a time. Opened here
    # rather than borrowed from a request, because the conductor closes rounds
    # from its own thread.
    def _write_round(summary):
        rows = summary.get("given") or []
        if not rows:
            return
        connection = db.connect()
        try:
            db.log_hall_round(connection, summary.get("pool") or "",
                              summary.get("question_id") or "",
                              summary.get("section") or "", rows,
                              running.log_key)
            connection.commit()
        finally:
            connection.close()
    if not running.on_round_closed:
        running.on_round_closed.append(_write_round)

    # The people sitting at the host are in the hall like anybody else.  It
    # goes through the same bridge every other table uses rather than a short
    # cut, because a host that runs its own players down a private path is a
    # host whose own table is the one case never exercised - and it is the
    # table the instructor is sitting at.
    cohort.set_auto_join(connection, True)
    party.room(create=True, cohorts=1)
    link = cohort.connect(f"http://127.0.0.1:{app.config.get('PORT', 5000)}",
                          None, None, conn=connection)
    log.info("cohort: the host takes a table in its own net as %s", link.unit_id)

    # And it conducts.  A net that needs a second press before it will do
    # anything is a net that sits at nought tables all evening, which is what
    # was on the board.  Rounds still wait for somebody to be seated - see
    # hall.py - so opening one early costs nothing.
    hall.start(running, lambda: _ask_net(running, wanted, section, seconds))
    return running


@app.route("/api/net/open", methods=["POST"])
def api_net_open():
    body = request.get_json(silent=True) or {}
    wanted = str(body.get("difficulty", "technician")).lower()
    if wanted not in party.DIFFICULTIES:
        wanted = "technician"
    running = _open_net(wanted, body.get("name"), body.get("section"),
                        body.get("seconds"))
    return jsonify(running.board())


@app.route("/api/net/checkin", methods=["POST"])
def api_net_checkin():
    """A cohort unit reports for duty, and learns what to put on its screens."""
    running = _net_or_404()
    body = request.get_json(silent=True) or {}
    unit_id = str(body.get("unit", "")).strip()[:40]
    if not unit_id:
        abort(400, "need a unit id")
    started = time.perf_counter()
    unit, why = running.check_in(unit_id, body.get("name"),
                                 body.get("players", 0))
    running.note_service((time.perf_counter() - started) * 1000.0)
    if unit is None:
        return jsonify({"checked_in": False, "reason": why,
                        "health": running.health()}), 409
    # The key travels to the unit: it scores its own cohort locally, which is
    # what keeps eight players' worth of traffic off this machine.
    return jsonify({"checked_in": True, "unit": unit.as_dict(),
                    "net": {"name": running.name,
                            "difficulty": running.difficulty,
                            "mode": running.mode},
                    "round": running.current(include_key=True),
                    # The hall's shootout as this table sees it - whether the
                    # pick is this table's, what is left to pick, the clock.
                    "shootout": (running.shootout_view(unit.id)
                                 if running.shootout is not None else None)})


def _ask_net(running, level="technician", section=None, seconds=None):
    """Put one question to the whole hall.  Shared by the button and the hall.

    Lifted out of the route it used to live in so that something other than a
    person pressing a key can call it - see :mod:`elmer.hall`.  It raises the
    way a route does, because that is what the route still wants; the
    conductor calls it from a thread where an exception is caught, logged and
    turned into a fault the board can show.
    """
    # `level`, not `difficulty`: the parameter used to be called that and
    # shadowed the difficulty module, so the first tournament round of a net
    # on a fresh plan died with "'str' object has no attribute 'measure'".
    wanted = str(level or "technician").lower()
    pool_id = party.DIFFICULTIES.get(wanted)
    if not pool_id:
        abort(400, f"difficulty must be one of {sorted(party.DIFFICULTIES)}")
    pool = _pool_or_404(pool_id)

    if not section and running.mode == netcontrol.SHOOTOUT:
        # In a shootout the subject is the picking table's. A practice table
        # holding the pick chooses now; a real table's choice is waited for.
        if running.shootout_over():
            return None
        running.choose_for_simulated()
        section = running.take_pick()
        if not section:
            return None
    if section:
        # A section asked for by name is somebody drilling one subject on
        # purpose - an instructor working a room through antennas - and it is
        # not a tournament, so it does not spend the tournament's draw.
        ids = [q["id"] for q in pool.by_id.values()
               if q["section"] == section]
        if not ids:
            abort(400, "no questions in that section")
        question = pool.by_id[random.choice(ids)]
    else:
        # The tournament is drawn once, in the proportions of the examination
        # for this licence class, and walked one question at a time. It used
        # to be random.choice over the whole pool every round: every section
        # equally likely whatever its weight on the paper, the same question
        # possible twice in an evening, and no end to it.
        state = running.plan_state()
        if state is None or state.get("difficulty") != wanted:
            # Easiest first, where this unit has measured enough to say so;
            # blueprint order, said plainly, where it has not. The conductor
            # calls this from its own thread, so the database is opened here
            # rather than taken from the request that is not there.
            measured = difficulty.measure(difficulty.load(db.connect(), pool_id))
            running.set_plan(tournament.plan(
                pool_id, wanted, difficulty_of=difficulty.ranker(measured)))
            log.info("net: tournament drawn, %d%% of the pool measured, %s",
                     round(100 * difficulty.coverage(measured, pool.by_id)),
                     "easiest first" if running.plan_state().get("ramped")
                     else "blueprint order")
        question = running.next_question()
        if question is None:
            # Played out. The caller decides what that means: a route says so
            # to whoever pressed the button, the conductor stops the hall.
            log.info("net: tournament played out after %d rounds",
                     running.round_number)
            return None
    shown = presentation(question)
    # A net that moves from Technician to General is a General net now, and
    # the hall's screens say so - unless somebody named it by hand, in which
    # case the name they chose is theirs and stays.
    if running.name == _net_name_for(running.difficulty):
        running.name = _net_name_for(wanted)
    running.start_round(
        pool_id, question["id"], shown["answer"],
        {"text": question["text"], "choices": shown["choices"],
         "section": question["section"],
         "section_title": pool.section_title(question["section"]),
         "figure": pool.figure_url(question), "difficulty": wanted},
        seconds=float(seconds or party.DEFAULT_ROUND_SECONDS))
    log.info("net round %d: %s %s across %d units",
             running.round_number, pool_id, question["id"],
             len(running.present_units()))
    return running


@app.route("/api/net/round", methods=["POST"])
def api_net_round():
    """Put one question to the whole hall."""
    running = _net_or_404()
    body = request.get_json(silent=True) or {}
    asked = _ask_net(running, body.get("difficulty", "technician"),
                     body.get("section"), body.get("seconds"))
    if asked is None:
        # A finished tournament is an answer, not a fault, and it is said in
        # a sentence so the screen shows the reason rather than a number.
        return jsonify({"ok": False,
                        "message": "this tournament is played out - "
                                   "start another to keep going",
                        "board": running.board()}), 409
    return jsonify(running.board())


@app.route("/api/net/simulate", methods=["POST"])
def api_net_simulate():
    """Fill the hall with tables that are not there, or send them home.

    For an instructor setting an evening up, a demonstration on a bench, or a
    club screen with two Pis in front of it.  They play, they are flagged
    simulated the whole way to the board, and a real unit checking in takes
    one of their places - see netcontrol.add_simulated.
    """
    running = _net_or_404()
    body = request.get_json(silent=True) or {}
    try:
        count = int(body.get("count", 4))
    except (TypeError, ValueError):
        abort(400, "count must be a number")
    if count > 0:
        made = running.add_simulated(min(count, len(netcontrol.SIMULATED_NAMES)))
        added = [u.name for u in made]
    else:
        added = []
        for _ in range(-count):
            gone = running.retire_simulated()
            if gone is None:
                break
            added.append(gone.name)
    return jsonify({"added" if count > 0 else "retired": added,
                    "simulated": len(running.simulated_units()),
                    "board": running.board()})


@app.route("/api/net/conduct", methods=["POST"])
def api_net_conduct():
    """Let the hall run itself: start when a table reports it has people.

    The trigger is a report rather than a clock.  A table says how many are
    sitting at it every time it checks in, so the host knows when there is a
    game to start without guessing at it, and a table that fills up late
    joins the next round rather than being waited for.
    """
    running = _net_or_404()
    body = request.get_json(silent=True) or {}
    if str(body.get("run", True)).lower() in ("false", "0"):
        return jsonify({"conducting": False, "stopped": hall.halt()})
    wanted = str(body.get("difficulty") or running.difficulty).lower()
    if wanted not in party.DIFFICULTIES:
        abort(400, f"difficulty must be one of {sorted(party.DIFFICULTIES)}")
    section = body.get("section")
    seconds = body.get("seconds")
    rounds = body.get("rounds")
    conductor = hall.start(
        running,
        lambda: _ask_net(running, wanted, section, seconds),
        ready_tables=max(1, int(body.get("tables", hall.READY_TABLES))),
        # Left unsaid, a hall runs the tournament's own length - three blocks
        # of twelve, or four for Extra - rather than until somebody stops it.
        rounds=int(rounds) if rounds else tournament.length_for(wanted))
    return jsonify({"conducting": True, "hall": conductor.as_dict(),
                    "board": running.board()})


@app.route("/api/net/mode", methods=["POST"])
def api_net_mode():
    """Which game the hall is playing: a tournament, or a shootout.

    A shootout across a hall is a shootout between tables: the picking table
    chooses the subject on its own screen, everybody's phones answer, and a
    table takes a letter when nobody at it got what the picker's table made.
    Starting one starts the hall conducting, waiting on the first pick.
    """
    running = _net_or_404()
    body = request.get_json(silent=True) or {}
    wanted = str(body.get("mode") or netcontrol.TOURNAMENT).lower()
    if wanted not in (netcontrol.TOURNAMENT, netcontrol.SHOOTOUT):
        abort(400, "mode must be tournament or shootout")
    if running.round is not None:
        abort(409, "a question is still open")
    if wanted == netcontrol.SHOOTOUT:
        difficulty = str(body.get("difficulty") or running.difficulty).lower()
        pool_id = party.DIFFICULTIES.get(difficulty)
        if not pool_id:
            abort(400, f"difficulty must be one of {sorted(party.DIFFICULTIES)}")
        pool = _pool_or_404(pool_id)
        titles = {code: _subject_name(pool.section_title(code))
                  for code in pool.section_order}
        groups = {}
        for code in pool.section_order:
            sub = pool.subelement_of(code)
            meta = pool.subelement_meta.get(sub) or {}
            groups[code] = (sub, _headline(meta.get("title") or sub))
        hall.halt()
        started, why = running.begin_shootout(list(pool.section_order), titles,
                                              groups, body.get("pick_seconds"))
        if started is None:
            abort(409, why)
        seconds = body.get("seconds")
        hall.start(running, lambda: _ask_net(running, difficulty, None, seconds),
                   ready_tables=max(1, int(body.get("tables", hall.READY_TABLES))),
                   rounds=None)
        log.info("net: shootout started (%s, %d tables)", difficulty,
                 len(running.units))
    else:
        hall.halt()
        running.end_shootout()
        log.info("net: back to a tournament")
    return jsonify(running.board())


@app.route("/api/net/pick", methods=["POST"])
def api_net_pick():
    """The picking table names the subject of the next question."""
    running = _net_or_404()
    body = request.get_json(silent=True) or {}
    unit_id = str(body.get("unit") or "").strip()
    section = str(body.get("section") or "").strip()
    chosen, why = running.choose(unit_id, section)
    if chosen is None:
        return jsonify({"ok": False, "message": why}), 409
    log.info("net: %s picked %s", unit_id, chosen)
    return jsonify({"ok": True, "section": chosen,
                    "shootout": running.shootout_view(unit_id)})


@app.route("/api/net/report", methods=["POST"])
def api_net_report():
    """A unit hands in its cohort's results for the round."""
    running = _net_or_404()
    body = request.get_json(silent=True) or {}
    got, why = running.report(str(body.get("unit", "")),
                              int(body.get("round", 0) or 0),
                              body.get("players") or [])
    if got is None:
        return jsonify({"accepted": False, "reason": why}), 409
    return jsonify({"accepted": True, "counted": got["accepted"],
                    "everyone_in": running.everyone_reported()})


@app.route("/api/net/close", methods=["POST"])
def api_net_close():
    running = _net_or_404()
    summary = running.close_round()
    if summary is None:
        abort(409, "no round is open")
    running.prune()
    return jsonify({"summary": summary, "board": running.board()})


@app.route("/api/party/net", methods=["POST"])
def api_party_net():
    """Point this table at a net control, or cut it loose."""
    body = request.get_json(silent=True) or {}
    url = str(body.get("url", "")).strip()
    connection = conn()
    if not url or str(body.get("join", True)).lower() in ("false", "0"):
        # By hand, so it stays that way: a table that walks straight back into
        # the net it was just taken out of has not offered a choice.
        cohort.set_auto_join(connection, False)
        cohort.disconnect(connection)
        return jsonify({"connected": False, "auto_join": False})
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    party.room(create=True, cohorts=1)
    cohort.set_auto_join(connection, True)
    link = cohort.connect(url, body.get("unit"), body.get("name"),
                          conn=connection)
    log.info("cohort: reporting to net control at %s as %s", link.url, link.unit_id)
    return jsonify({"connected": True, "auto_join": True,
                    "bridge": link.as_dict()})


@app.route("/api/party/net/pick", methods=["POST"])
def api_party_net_pick():
    """This table's choice of subject, relayed to the hall it reports to.

    The table screen cannot reach the hall itself - another origin - so its
    own server carries the choice across, under this table's unit id.
    """
    link = cohort.bridge()
    if link is None:
        return jsonify({"ok": False, "message": "this table is not in a net"}), 409
    body = request.get_json(silent=True) or {}
    reply = link.pick(str(body.get("section") or "").strip())
    if not reply.get("ok"):
        return jsonify({"ok": False,
                        "message": reply.get("message") or reply.get("error")
                        or "the hall did not take the pick"}), 409
    return jsonify(reply)


@app.route("/api/party/net")
def api_party_net_state():
    link = cohort.bridge()
    return jsonify({"connected": link is not None,
                    "bridge": link.as_dict() if link else None})


def _here():
    """This machine's address as the rest of the hall sees it."""
    host = request.host.split(":")[0]
    if host in ("localhost", "127.0.0.1", "::1"):
        found = diagnostics.local_addresses()
        host = found[0][1] if found else host
    port = urlsplit(request.host_url).port or 5000
    return f"http://{host}:{port}"


@app.route("/net")
def net_host():
    """The screen net control runs the hall from.

    The difficulty asked for here names the net, because a network can hold
    more than one at a time and the name is how a table tells them apart. An
    already-running net keeps the name it has: arriving at this screen is not
    a reason to rename the tournament underneath it.
    """
    wanted = str(request.args.get("difficulty", "")).lower()
    if wanted not in party.DIFFICULTIES:
        wanted = "technician"
    running = netcontrol.net()
    if running is None:
        running = _open_net(wanted)
    where = _here()
    # The code goes where a phone is useful, which is into the game.  It used
    # to carry this machine's bare address, so somebody holding a phone up to
    # a screen with a round on it landed on the dashboard and had to go
    # looking - and the address it carried was for other Pis to point
    # themselves at, which is a thing nobody points a phone at and which
    # tables now find on their own anyway.  The address stays in writing
    # beside it for whoever still wants to type it.
    join_url = _join_url("1")
    amateur, commercial = _tournament_choices()
    return render_template("net_host.html", where=where, join_url=join_url,
                           net_name=running.name,
                           difficulty=running.difficulty,
                           amateur=amateur, commercial=commercial,
                           qr_svg=qr.as_svg(join_url, module=6, quiet=3))


@app.route("/net/board")
@app.route("/board")
def net_board():
    """The big board: what the room looks at between rounds.

    This used to refuse with a 404 when no net was running, which on a screen
    at the front of a room is a blank white page and no way to tell whether
    anything is wrong. A board that people are watching should always say what
    is happening, including that nothing is - so it never refuses, and it shows
    a hall, a single table, or an invitation to start one, whichever is true.
    """
    return render_template("net_board.html")


@app.route("/api/board")
def api_board():
    """Whatever this unit is running, shaped for the screen at the front.

    A hall if there are tables checked in, otherwise the table on this machine,
    otherwise nothing - said plainly rather than as an error.
    """
    running = netcontrol.net()
    if running is not None and running.units:
        board = running.board()
        board["kind"] = "hall"
        return jsonify(board)
    room = party.room()
    if room is not None and (room.players or room.round):
        state = room.state()
        state["kind"] = "table"
        state["name"] = "Tournament"
        driver = autoplay.director()
        state["auto"] = driver.as_dict() if driver else None
        return jsonify(state)
    return jsonify({"kind": "idle",
                    "net": running is not None,
                    "where": _here()})


def _certificate_awards(scope, places):
    """Who placed, with the facts about it, from the game this unit ran.

    Never a practice player: a bot on a certificate would be the program
    awarding itself. The facts are counted from the game's own history rather
    than carried as running totals, so a certificate can be printed for a game
    that finished an hour ago and still be right.
    """
    places = max(1, min(int(places or 3), 3))
    if scope == "hall":
        running = netcontrol.net()
        if running is None:
            abort(409, "no net is running on this unit")
        people = [p for p in running.people_for_awards() if not p.get("bot")]
        # Fastest-correct counts per person, from the rounds themselves.
        fastest = {}
        for summary in running.history:
            top = (summary.get("top") or [None])[0]
            if top:
                who = (top["unit"], top["name"])
                fastest[who] = fastest.get(who, 0) + 1
        state = running.plan_state() or {}
        game = {"label": party.LABELS.get(running.difficulty, running.difficulty.title()),
                "length": state.get("length"), "blocks": state.get("blocks"),
                "mode": "shootout" if running.mode == netcontrol.SHOOTOUT else "tournament"}
        awards = []
        for i, p in enumerate(people[:places], start=1):
            entry = dict(p)
            entry["fastest"] = fastest.get((p["unit"], p["name"]), 0)
            entry["blocks_won"] = [b["block"] for b in running.blocks
                                   if (b.get("player") or {}).get("name") == p["name"]
                                   and (b.get("player") or {}).get("unit_name") == p.get("unit_name")]
            awards.append({"place": i, "name": p.get("cert_name") or p["name"],
                           # Whether they said what they wanted on the wall.
                           # A name they chose is theirs; only a play name
                           # standing in for one may be corrected.
                           "chosen": bool(p.get("cert_name")),
                           "lines": certpdf.lines_for(entry, game)})
        return awards, game, running.name
    room = party.room()
    if room is None:
        abort(409, "no table is running on this unit")
    diff = (room.round.payload.get("difficulty") if room.round and room.round.payload
            else None) or _party_class()
    label = party.LABELS.get(diff, str(diff).title())
    if room.mode == party.SHOOTOUT and room.shootout is not None:
        view = room.shootout_view()
        standing = [r for r in view["standing"] if not r["bot"] and not r["gone"]]
        # Fewest letters first; the winner, if there is one, leads.
        standing.sort(key=lambda r: (r["player"] != view.get("winner"), r["letters"], r["name"]))
        game = {"label": label, "mode": "shootout"}
        awards = [{"place": i,
                   "name": room.cert_name_of(r["player"]) or r["name"],
                   "chosen": bool(room.cert_name_of(r["player"])),
                   "lines": certpdf.lines_for({"letters": r["letters"]}, game)}
                  for i, r in enumerate(standing[:places], start=1)]
        return awards, game, "Shootout"
    players = sorted((pl for pl in room.players.values() if not pl.bot),
                     key=lambda pl: (-pl.score, pl.name))
    fastest = {}
    for summary in room.history:
        answers = summary.get("answers") or []
        first = next((a for a in answers if a.get("place") == 1), None)
        if first:
            fastest[first["player_id"]] = fastest.get(first["player_id"], 0) + 1
    game = {"label": label, "length": len(room.history), "mode": "tournament"}
    awards = []
    for i, pl in enumerate(players[:places], start=1):
        entry = {"answered": pl.answered, "correct": pl.correct, "score": pl.score,
                 "fastest": fastest.get(pl.id, 0)}
        awards.append({"place": i, "name": pl.cert_name or pl.name,
                       "chosen": bool(pl.cert_name),
                       "lines": certpdf.lines_for(entry, game)})
    return awards, game, "Tournament"


CERT_SETTING = "certificates.event"


def _certificate_details(connection, body=None):
    """The event as the host described it, saved on the unit between prints.

    A club sets these once for the day - the event, who is hosting, the date
    as it should read, where, who signs - and every certificate that evening
    uses them. Defaults come from the station: the QTH for the place, the
    profile's callsign for net control, today for the date.
    """
    saved = db.unit_get(connection, CERT_SETTING) or {}
    if not isinstance(saved, dict):
        saved = {}
    profile = db.get_profile(connection)
    place = qth_for(connection, profile) or {}
    licence = profile["settings"].get("license") or {}
    # A grid square is where the station is, not a place for a certificate:
    # "EN26uo" on the wall says nothing to anybody. A named town is used;
    # a bare grid is left blank for the host to fill in.
    where = str(place.get("short") or "")
    if re.fullmatch(r"[A-Ra-r]{2}\d{2}([A-Xa-x]{2})?", where.strip()):
        where = ""
    defaults = {
        "event": "", "club": "",
        "when": date.today().strftime("%-d %B %Y"),
        "where": where,
        "net_control": licence.get("callsign") or "",
        "club_signer": "", "places": 3,
    }
    out = dict(defaults)
    out.update({k: v for k, v in saved.items() if k in defaults})
    if body:
        for k in defaults:
            if k in body:
                out[k] = body[k]
    out["places"] = max(1, min(3, int(out.get("places") or 3)))
    for k in ("event", "club", "when", "where", "net_control", "club_signer"):
        out[k] = str(out.get(k) or "").strip()[:80]
    return out


@app.route("/api/tournament/certificates/preview")
def api_tournament_certificates_preview():
    """Who would be awarded, and what the certificate would say - to edit
    before printing. The names come back as the players asked for them, and
    a host who can see a misspelling fixes it here rather than on the wall.
    """
    scope = "hall" if request.args.get("scope") == "hall" else "table"
    try:
        awards, game, default_event = _certificate_awards(scope, 3)
    except Exception:
        awards, game, default_event = [], {}, "tournament"
    details = _certificate_details(conn())
    if not details["event"]:
        details["event"] = f"ELMER {default_event}"
    return jsonify({"awards": awards, "game": game, "details": details})


@app.route("/api/tournament/certificates", methods=["POST"])
def api_tournament_certificates():
    """Certificates for the wall: one page per placing, on the print shelf.

    The event is as the host described it and is remembered on the unit.
    Names may be corrected on the way through - `names` maps a placing to
    what should be printed - because a player who typed "dana" on a phone
    should not have that in 44 point type. What the certificate says about
    the game is what the game recorded; what it says about licences is
    nothing, in so many words.
    """
    body = request.get_json(silent=True) or {}
    scope = "hall" if str(body.get("scope", "")).lower() == "hall" else "table"
    connection = conn()
    details = _certificate_details(connection, body)
    awards, game, default_event = _certificate_awards(scope, details["places"])
    if not awards:
        return jsonify({"ok": False, "message": "nobody to award yet - no person "
                        "has played a round"}), 409
    # A name the player chose for the wall is theirs and is not corrected,
    # whatever the form sent: nobody turns a Richard into a Dick but Richard.
    # Only a play name standing in for a certificate name may be fixed.
    fixes = body.get("names") or {}
    for a in awards:
        if a.get("chosen"):
            continue
        fixed = str(fixes.get(str(a["place"])) or "").strip()[:48]
        if fixed:
            a["name"] = fixed
    event = details["event"] or f"ELMER {default_event}"
    # Remembered for the next print tonight - not the name fixes, which
    # belong to these people and this print.
    db.unit_set(connection, CERT_SETTING, {k: details[k] for k in
                ("event", "club", "when", "where", "net_control",
                 "club_signer", "places")})
    connection.commit()
    pdf = certpdf.build(
        awards, event=event, when=details["when"] or None,
        where=details["where"], club=details["club"],
        signers={"net_control": details["net_control"],
                 "club": details["club_signer"]},
        mode=game.get("mode"))
    name = "certificates-" + re.sub(r"[^a-z0-9]+", "-", event.lower()).strip("-") + ".pdf"
    row = prints.keep(pdf, name, "certificates", f"Certificates - {event}",
                      {"scope": scope, "awarded": [a["name"] for a in awards],
                       "game": game.get("label")})
    log.info("certificates: %d for %s (%s)", len(awards), event, scope)
    return _print_reply(row, _wants_raw(body))


@app.route("/api/net/board")
def api_net_board():
    """The hall's big screen, and what a late unit polls to catch up."""
    running = _net_or_404()
    out = running.board()
    # What the hall is doing between questions, so a screen can say "waiting
    # for a table" rather than sitting on a stale leaderboard looking broken.
    conductor = hall.conductor()
    out["hall"] = conductor.as_dict() if conductor else None
    return jsonify(out)


def _board_here():
    """This unit's own game, in the shape the board draws.

    The same answer /api/board gives, minus the fetch: the board asks this unit
    for every game on the network, and the one running here is not worth a
    round trip to itself.
    """
    running = netcontrol.net()
    if running is not None and running.units:
        return dict(running.board(), kind="hall")
    room = party.room()
    if room is not None and (room.players or room.round):
        driver = autoplay.director()
        return dict(room.state(), kind="table", name="Tournament",
                    auto=driver.as_dict() if driver else None)
    if running is not None:
        return dict(running.board(), kind="hall")
    return None


@app.route("/api/boards")
def api_boards():
    """Every tournament on the network, for one screen at the front.

    A hall can hold several at once and the board should show the hall, not
    whichever one happens to be running on the Pi the screen is plugged into.
    The neighbours' boards are fetched here rather than from the browser: they
    are on other origins, a board polls every second, and several screens on
    one unit should not each cost the hall a round of requests.
    """
    mine = _board_here()
    out = []
    running = netcontrol.net()
    if mine is not None:
        out.append({"url": "", "here": True, "kind": mine.get("kind"),
                    "name": (running.name if running is not None
                             else "Tournament"),
                    "difficulty": (running.difficulty if running is not None
                                   else ""),
                    "board": mine, "stale": False, "error": None})
    away = [g for g in discovery.games() if g.get("url")]
    # The net this unit reports to, whether or not it was heard announcing
    # itself. A board on a table needs the hall's standings above all, and the
    # master may be on another subnet or on the end of a wire.
    link = cohort.bridge()
    if link is not None and not any(g["url"] == link.url for g in away):
        away.append({"url": link.url, "name": link.net_name or "the net",
                     "difficulty": link.net_difficulty, "units": 0,
                     "kind": "hall", "path": "/api/net/board"})
    for got in netwatch.look(away):
        board = got.get("board")
        if board is not None and got.get("kind") == "hall":
            board = dict(board, kind="hall")
        out.append({"url": got["url"], "here": False,
                    "kind": got.get("kind"), "name": got.get("name") or "",
                    "difficulty": got.get("difficulty") or "",
                    "board": board, "stale": got.get("stale"),
                    "age_s": got.get("age_s"), "error": got.get("error")})
    netwatch.forget(keep=[g["url"] for g in away])
    party_now = _party_standings(out, link, running)
    if link is not None:
        # The net this unit is a table in is not a second tournament to watch
        # alongside its own board - it is the same one, seen from the master.
        # It belongs in the strip at the foot as context, and listing it as a
        # rival to the table's own screen would count these players twice.
        out = [g for g in out if g["url"] != link.url]
    return jsonify({"games": out, "count": len(out), "where": _here(),
                    "local": _local_standings(), "party": party_now})


def _local_standings():
    """Who is ahead at this table. None when nobody is playing here.

    This is the half of the foot of the board that belongs to the people in
    the room: their own names, their own scores. On a unit that is only net
    control there is nobody at it, and the strip says so by not being there.
    """
    room = party.room()
    if room is None:
        return None
    rows = room.standings()
    if not rows:
        return None
    state = room.state()
    return {"name": "This table", "standings": rows,
            "people": state.get("people", 0), "bots": state.get("bots", 0)}


def _party_standings(games, link, running):
    """Where the tables stand in the hall this unit belongs to.

    Only for a table. Net control's own screen is the hall standings already,
    and repeating them along the foot of it would be the same list twice; the
    unit that needs this is the one whose board can otherwise show nothing but
    its own eight players.
    """
    if link is None:
        return None
    for entry in games:            # not `game`: that is a module here
        if entry.get("url") == link.url and entry.get("board"):
            board = entry["board"]
            return {"name": board.get("name") or entry.get("name") or "The hall",
                    "standings": board.get("standings") or [],
                    "units": board.get("units_present", 0),
                    "players": board.get("players", 0)}
    return None


@app.route("/api/pool-gate", methods=["POST"])
def api_pool_gate():
    """Open every pool, or put the gate back.

    Offered plainly rather than buried: the gate exists so that a first
    evening is not a wall of 2,475 questions, not to tell a licensed operator
    what they may read.
    """
    connection = conn()
    body = request.get_json(silent=True) or {}
    wanted = "off" if body.get("open") else "on"
    profile = db.get_profile(connection)
    settings = dict(profile["settings"])
    settings[gating.SETTING] = wanted
    db.save_settings(connection, settings)
    allowed, state = _open_pools(connection)
    return jsonify({"gate": wanted, "open": sorted(allowed), "state": state})


@app.route("/api/users/password", methods=["POST"])
def api_users_password():
    """Set, change or clear the password on an account.

    Changing one needs the old one, so somebody who wanders off from an open
    dashboard does not come back to an account they are locked out of.
    """
    connection = conn()
    body = request.get_json(silent=True) or {}
    target = body.get("id")
    try:
        target = int(target) if target is not None else connection.user_id
    except (TypeError, ValueError):
        abort(400)
    if not db.user_exists(connection, target):
        abort(404)
    if not db.may_alter(connection, target, body.get("current") or ""):
        return jsonify({"ok": False, "locked": True,
                        "message": "that account already has a password"}), 403
    # Any length. There used to be a four character floor here, which the
    # dialog asking for the password flatly contradicted - it says "any
    # length, anything you like" and then says the password travels in clear,
    # which is the honest threat model: this is a name tag, not a vault.
    # A floor buys nothing against anybody who can already read the wire, and
    # it refuses the nine year old at a club night who wants to be "ab".
    # An empty password is not a short one - it means take the lock off.
    wanted = body.get("password") or ""
    db.set_password(connection, target, wanted)
    log.info("account %s: password %s", target, "set" if wanted else "cleared")
    return jsonify({"ok": True, "locked": bool(wanted),
                    "users": _user_block(connection)})


@app.route("/api/users/offered", methods=["POST"])
def api_users_offered():
    """Remember that this account was offered a password, either answer.

    Declining is a real answer and it sticks. Being asked twice about something
    optional is how a program teaches people to dismiss it without reading.
    """
    connection = conn()
    db.mark_password_offered(connection, connection.user_id)
    return jsonify(_user_block(connection))


@app.route("/api/users/moderator", methods=["POST"])
def api_users_moderator():
    """The key the person whose Pi this is holds.

    Set at the unit itself and nowhere else. It opens any account, which is
    what makes a forgotten password at a club night a thirty-second problem
    rather than an evening with a database editor - and is exactly why it
    should not be settable from a phone at the back of the room.
    """
    connection = conn()
    if not _is_local(request.remote_addr):
        return jsonify({"ok": False, "message":
                        "the moderator key is set at the unit itself"}), 403
    body = request.get_json(silent=True) or {}
    if db.has_moderator(connection) and not db.check_moderator(
            connection, body.get("current") or ""):
        return jsonify({"ok": False,
                        "message": "the current moderator key is needed"}), 403
    wanted = body.get("password") or ""
    if wanted and len(wanted) < 4:
        return jsonify({"ok": False, "message": "four characters at least"}), 400
    db.set_moderator(connection, wanted)
    log.info("moderator key %s", "set" if wanted else "cleared")
    return jsonify({"ok": True, "set": bool(wanted)})


@app.route("/api/doctor")
def api_doctor():
    """The same checks --doctor runs, for somebody who is not at a terminal.

    A self-check that only works from a command line is a self-check most
    operators never run, and the station Pi is frequently a kiosk with no
    terminal on it at all.

    Account names are taken out of the paths, exactly as the problem report
    does it: this answers over the network, and which folder somebody keeps
    their radio software in is nobody's business. Whether that folder is sound
    is the part with diagnostic value, and that is kept.
    """
    checks = diagnostics.collect(port=app.config.get("PORT", 5000))
    for check in checks:
        check["detail"] = bugreport.RE_HOME.sub(
            lambda m: m.group(1) + "[user]", check["detail"])
    counts = {"ok": 0, "warn": 0, "FAIL": 0}
    for check in checks:
        counts[check["state"]] = counts.get(check["state"], 0) + 1
    return jsonify({"checks": checks, "counts": counts,
                    "sound": counts.get("FAIL", 0) == 0,
                    "checked_at": time.time()})


def _describe_this_unit():
    """What this unit tells the network about itself, for discovery.

    Called from the announcing thread, so it takes no request context and
    never raises: a unit that cannot describe itself should go quiet, not
    bring a thread down.
    """
    # The id tells units apart; the name is what a person reads. They are not
    # the same string: two Pis out of the box share a hostname, so the id
    # carries a mark that makes it unique and the name stays the hostname.
    out = {"unit": cohort.default_unit_id(), "name": cohort.default_unit_name(),
           "version": "", "party": {}}
    try:
        out["version"] = (update.state() or {}).get("head") or ""
    except Exception:
        pass
    try:
        found = diagnostics.local_addresses()
        host = found[0][1] if found else "127.0.0.1"
        out["url"] = f"http://{host}:{app.config.get('PORT', 5000)}"
    except Exception:
        out.setdefault("url", "")
    try:
        connection = db.connect()
        out["share_position"] = db.unit_get(connection, "share_position",
                                            "on") != "off"
        fix = gps.fix(connection)
        # Never pass on a position that came from another unit. Two units with
        # no receiver would otherwise echo one between themselves for ever,
        # and it would never age out or be traceable to a real receiver.
        if fix and fix.get("source") != "elmer-peer":
            out["fix"] = fix
    except Exception:
        pass
    try:
        room = party.room()
        if room is not None:
            state = room.health()
            out["party"] = {"running": bool(room.round),
                            "players": state.get("players", 0),
                            "seats": state.get("seats", 0)}
    except Exception:
        pass
    out["net"] = _net_role()
    return out


def _net_role():
    """Which part this unit is playing in a hall, for the announcement.

    Three parts and no more: running the net for everyone, reporting to
    somebody else's, or on its own. A unit that is only a table still says
    which net it reports to, so a third unit arriving late can join the same
    net without having to be told where it is by hand.
    """
    role = {}
    try:
        running = netcontrol.net()
        if running is not None:
            role["hosting"] = True
            role["name"] = running.name
            role["difficulty"] = running.difficulty
            role["units"] = len(running.present_units())
            role["round"] = running.round_number
    except Exception:
        pass
    try:
        link = cohort.bridge()
        if link is not None:
            role["table_of"] = link.url
            if link.net_name:
                role["table_in"] = link.net_name
    except Exception:
        pass
    return role


@app.route("/api/peers")
def api_peers():
    """Other ELMERs on this network, and the part this one is playing.

    The roster comes back too - it is what the code works from, and a
    diagnostic wants it - but the dashboard reads only the summary. Nine units
    in a hall is nine names, nine addresses and nine versions on the screen,
    and none of it answers the question actually in front of the operator,
    which is what this unit should do about the others.
    """
    mine = _net_role()
    try:
        # Whether anything is running here at all. A unit with no tournament on
        # it is not "playing independently", it is simply idle, and a panel
        # that tells it otherwise is telling it something untrue.
        mine["playing_here"] = party.room() is not None
    except Exception:
        pass
    # The panel offers to open a net, and a net is named for what it studies,
    # so the choices travel with the answer rather than being written out a
    # second time in the browser.
    choices = [[key, party.LABELS[key]] for key in party.DIFFICULTIES]
    live = discovery.neighbourhood()
    if live is None:
        return jsonify({"running": False, "peers": [], "count": 0,
                        "summary": {"count": 0, "nets": []}, "me": mine,
                        "difficulties": choices})
    return jsonify(dict(live.as_dict(), me=mine, difficulties=choices))


@app.route("/api/gps/raw")
def api_gps_raw():
    """What gpsd actually says, for working out a disagreement about it."""
    host, port = gps.target(conn())
    return jsonify(gps.probe(host, port,
                             seconds=float(request.args.get("seconds", 4))))


@app.route("/api/gps/phone", methods=["GET", "POST"])
def api_gps_phone():
    """Listen for a phone streaming NMEA, or stop.

    The address to point the phone at is returned, because that is the only
    thing the operator has to type into whichever forwarding app they already
    have, and reading it off the screen beats working it out.
    """
    connection = conn()
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        if body.get("on", True):
            port = int(body.get("port") or phonegps.DEFAULT_PORT)
            try:
                phonegps.start(port)
            except OSError as exc:
                return jsonify({"listening": False,
                                "error": f"could not listen on {port}: {exc}"}), 409
            db.unit_set(connection, "phone_gps_port", port)
        else:
            phonegps.stop_listening()
            db.unit_set(connection, "phone_gps_port", 0)
    live = phonegps.listener()
    state = live.as_dict() if live else {"listening": False,
                                         "port": phonegps.DEFAULT_PORT}
    state["send_to"] = f"{_here().split('//')[1].split(':')[0]}:{state['port']}"
    got = phonegps.current()
    if got:
        from .geocode import to_grid
        state["fix"] = {"lat": got["lat"], "lon": got["lon"],
                        "grid": to_grid(got["lat"], got["lon"]),
                        "mode": got.get("mode"), "alt_m": got.get("alt_m")}
    return jsonify(state)


@app.route("/api/gps")
def api_gps():
    """The station's own GPS fix, named if it can be named.

    "Locate me" used to mean only the browser's geolocation, which on a Pi in
    a vehicle is the one source that cannot work: Chromium resolves position
    through a network lookup service it has no key for, and it never consults
    gpsd. Meanwhile the receiver on the desk has a 3D fix. This offers that fix
    to the page, in the shape the button already saves.
    """
    connection = conn()
    host, port = gps.target(connection)
    if not gps.enabled(connection):
        return jsonify({"located": False, "reason": "off",
                        "detail": "GPS is switched off for this unit"})
    live = gps.place(connection)
    if not live:
        # Say which of the several quite different things went wrong. "No fix"
        # covers a unit with no receiver, a receiver that has not locked yet,
        # and a gpsd on another machine that is not answering, and those are
        # not fixed the same way - so the page should not report them with one
        # sentence either.
        listening = diagnostics.port_in_use(port, host)
        phone = phonegps.listener()
        if listening:
            detail = (f"gpsd at {host}:{port} is answering but has no fix yet "
                      f"- a receiver indoors often never gets one")
        elif phone:
            detail = (f"nothing is listening at {host}:{port}, and no phone is "
                      f"streaming to udp/{phone.port} yet")
        else:
            detail = (f"nothing is listening at {host}:{port} - this unit has "
                      f"no GPS. A phone can be one: turn it on in Settings")
        return jsonify({"located": False, "reason": "no fix", "detail": detail,
                        "gpsd": f"{host}:{port}", "gpsd_listening": listening,
                        "phone_listening": bool(phone)})
    place = geocode.reverse(live["lat"], live["lon"]) or {}
    return jsonify({
        "located": True,
        "name": place.get("name") or live["grid"],
        "short": place.get("short") or live["grid"],
        "kind": "gps", "lat": live["lat"], "lon": live["lon"],
        "grid": live["grid"], "mode": live.get("mode"),
        "age_s": live.get("age_s"), "from": live.get("from"),
    })


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
    # Whether it is day where the operator is. A height means nothing on its
    # own: the F2 layer sits around 270 km by day and 330 at night, so the
    # same 245 km is ordinary at noon and distinctly low at eleven at night -
    # and the tool that reads this was calling every low layer a daytime one
    # whatever the hour.
    sun = day = None
    if lat is not None:
        try:
            sun = round(propagation.solar_elevation(lat, lon), 1)
            day = sun > 0
        except Exception:
            sun = day = None
    return jsonify({"ok": True, "spread": overview, "nearest": closest,
                    "typical": ionosonde.TYPICAL,
                    "sun_deg": sun, "day": day,
                    "typical_hmf2": {"day": patterns.TYPICAL_HMF2[True],
                                     "night": patterns.TYPICAL_HMF2[False]},
                    "have_qth": lat is not None})


@app.route("/api/celestial/fix", methods=["POST"])
def api_celestial_fix():
    """Where you are, from sextant sights of the sun and an accurate clock.

    Every step is returned, not just the answer: the point of the tool is that
    somebody can watch the arithmetic happen and come to trust it, and nobody
    trusts a black box they might one day have to rely on.
    """
    body = request.get_json(force=True) or {}
    rows = body.get("sights") or []
    if not isinstance(rows, list) or len(rows) < 2:
        return jsonify({"ok": False,
                        "error": "Two sights at least. One is a circle, not "
                                 "a place."}), 400
    if len(rows) > 8:
        return jsonify({"ok": False, "error": "eight sights is plenty"}), 400

    horizon = body.get("horizon")
    if horizon not in ("artificial", "shadow"):
        horizon = "sea"
    try:
        index_error = float(body.get("index_error_arcmin") or 0.0)
        height_ft = max(0.0, float(body.get("height_ft") or 0.0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "check the corrections"}), 400

    sights, working = [], []
    for i, row in enumerate(rows, 1):
        try:
            hs = float(row.get("hs"))
            when = datetime.fromisoformat(str(row.get("when")).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return jsonify({"ok": False,
                            "error": f"sight {i}: check the angle and the time"}), 400
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if not -1.0 <= hs <= 180.0:
            return jsonify({"ok": False,
                            "error": f"sight {i}: {hs} is not an altitude"}), 400
        limb = row.get("limb") if row.get("limb") in ("lower", "upper") else "centre"
        done = celestial.reduce_sight(hs, when, index_error, height_ft,
                                      limb, horizon)
        # Each sight carries what it is worth, so a stick reading is not
        # given a sextant's confidence when the uncertainty is worked out.
        sights.append({"ho": done["ho"], "when": when,
                       "sigma": done["sigma_arcmin"]})
        working.append({"n": i, "when": when.isoformat(), "limb": limb,
                        "ho": round(done["ho"], 4),
                        "sigma_arcmin": done["sigma_arcmin"],
                        "steps": [{"name": n, "value": round(v, 4), "why": w}
                                  for n, v, w in done["steps"]]})

    hint = None
    if body.get("use_qth"):
        place = qth_for(conn(), db.get_profile(conn()))
        if place.get("lat") is not None:
            hint = (place["lat"], place["lon"])

    found = celestial.fix(sights, hint=hint)
    if not found.get("ok"):
        return jsonify(found), 400
    found["grid"] = geocode.to_grid(found["lat"], found["lon"])
    found["working"] = working
    found["hinted"] = hint is not None

    # A position is not the answer somebody in trouble needs. "Which way do I
    # walk" is, and the two are only the same to a person who already reads
    # charts. So the fix comes back with the nearest named places and a
    # bearing to each, offline, from the list that shipped with the program.
    try:
        found["landfall"], found["landfall_from"] = places.nearest(
            found["lat"], found["lon"])
    except Exception:                                   # never lose the fix
        log.debug("no places for a celestial fix", exc_info=False)
        found["landfall"], found["landfall_from"] = [], None

    # And which way that bearing is measured from. There is no magnetic model
    # here and there does not need to be one: the same sun that gave the fix
    # gives true north directly, and a compass with an unknown declination is
    # the thing being replaced rather than the thing being relied on.
    now = datetime.now(timezone.utc)
    alt_now, az_now = celestial.altitude_azimuth(found["lat"], found["lon"], now)
    found["north"] = {"when": now.isoformat(), "sun_azimuth": round(az_now, 1),
                      "sun_altitude": round(alt_now, 1)}
    for other in found.get("alternatives", []):
        other["grid"] = geocode.to_grid(other["lat"], other["lon"])
    log.info("celestial fix from %d sights: %s, +/-%s nm (%s geometry)",
             len(sights), found["grid"], found.get("uncertainty_nm"),
             found.get("geometry"))
    return jsonify(found)


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


def _adopt_license(connection, call, settings=None):
    """Record a callsign on the current user and read its license.

    A callsign is enough to know the license class and when it expires, so
    there is no reason to make the operator tell us separately - and from here
    on it is also what ELMER calls them.
    """
    save = settings is None
    db.set_callsign(connection, call or "")
    settings = db.get_profile(connection)["settings"] if save else settings
    found = callsign.lookup(call) if call else None
    if found and found.get("found"):
        settings["license"] = found
        if found.get("license_class"):
            settings["license_class"] = found["license_class"]
        log.info("license for %s: %s, expires %s (%s)", found["callsign"],
                 found.get("license_class") or found.get("type"),
                 found.get("expires"), found["status"]["state"])
    elif found is not None:
        settings["license"] = found
    elif call:
        log.warning("license lookup unavailable for %s", call)
    if save:
        db.save_settings(connection, settings)
    return settings


@app.route("/api/settings", methods=["POST"])
def api_settings():
    body = request.get_json(force=True)
    connection = conn()
    settings = db.get_profile(connection)["settings"]
    if "callsign" in body:
        settings = _adopt_license(connection, body["callsign"] or "", settings)
    if "units" in body:
        # Narrow on purpose - see elmer/units.py. This is how far away a thing
        # is, not a request to rename the 40 m band.
        settings["units"] = units.system(body["units"])["key"]
    for key in ("license_class", "state"):
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


# --------------------------------------------------------------------------
# DEVELOPMENT ONLY. Delete this block, elmer/devreset.py, and the Developer
# panel at the foot of tools.html to take it out. Nothing else refers to it.
# --------------------------------------------------------------------------

@app.route("/api/dev/reset")
def api_dev_reset_preview():
    """What a reset would take. Asked first, always."""
    if not _is_local(request.remote_addr):
        abort(403, "a reset can only be asked for from this machine")
    return jsonify(devreset.would_remove())


@app.route("/api/dev/reset", methods=["POST"])
def api_dev_reset():
    """Put this unit back to how a fresh clone finds it.

    Told twice on purpose. The caller has to send back the number of things
    the preview said would go, so a stale page that was opened before somebody
    fetched a day's worth of parks cannot quietly take them.
    """
    _local_json_or_403()
    body = request.get_json(silent=True) or {}
    preview = devreset.would_remove()
    if not preview.get("ok"):
        return jsonify(preview), 400
    if body.get("count") != preview.get("count"):
        return jsonify({"ok": False, "stale": True, "count": preview["count"],
                        "items": preview["items"],
                        "error": "what is here has changed since you looked - "
                                 "read it again before resetting"}), 409
    log.warning("dev reset asked for from %s", request.remote_addr)
    return jsonify(devreset.reset())


# ------------------------------------------------------ end development only


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
    threading.Timer(0.3, lambda: host.stop_main_thread(
        app.config.get("PORT"))).start()
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
                       # Whether an account is locked, never anything about
                       # what it is locked with.
                       "locked": u["locked"],
                       "last_seen": u["last_seen"]}
                      for u in db.users(connection)],
            "current": current["id"],
            "display_name": current["display_name"],
            "locked": db.has_password(connection, current["id"]),
            "moderator": db.has_moderator(connection),
            # Offered once, when the unit stops being one person's. Computed
            # from this account alone, so it reveals nothing about anybody
            # else's - see the note in db.py.
            "offer_password": db.should_offer_password(connection,
                                                       current["id"]),
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
    """Become another user on this unit.

    An account with a password is not a name on a list any more: answering
    questions as somebody else quietly corrupts the one record they came here
    to build, and picking their name out of a menu should not be enough to do
    that.
    """
    connection = conn()
    body = request.get_json(silent=True) or {}
    try:
        wanted = int(body.get("id"))
    except (TypeError, ValueError):
        abort(400)
    if not db.user_exists(connection, wanted):
        abort(404)
    if not db.may_alter(connection, wanted, body.get("password") or ""):
        log.info("switch to user %s refused: wrong or missing password", wanted)
        return jsonify({"ok": False, "locked": True,
                        "message": "that account has a password"}), 403
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
        _adopt_license(connection, profile["callsign"])
    log.info("new user on the unit: %s", profile["display_name"])
    return _with_user_cookie(_user_block(connection), profile["id"])


@app.route("/api/users/rename", methods=["POST"])
def api_users_rename():
    """Rename an account. Its own password, or the moderator's, opens it."""
    connection = conn()
    body = request.get_json(silent=True) or {}
    # Renaming defaults to whoever you currently are, as it always did; an
    # explicit id is for renaming somebody else, which needs their password.
    target = body.get("id")
    try:
        target = int(target) if target is not None else connection.user_id
    except (TypeError, ValueError):
        abort(400)
    if not db.user_exists(connection, target):
        abort(404)
    if not db.may_alter(connection, target, body.get("password") or ""):
        return jsonify({"ok": False, "locked": True,
                        "message": "that account has a password"}), 403
    try:
        db.rename_user(connection, target, body.get("name", ""))
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
    if not db.may_alter(connection, wanted, body.get("password") or ""):
        log.warning("remove user %s refused: wrong or missing password", wanted)
        return jsonify({"ok": False, "locked": True,
                        "message": "that account has a password"}), 403
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


@app.route("/api/log")
def api_log():
    """The tail of this unit's log, for the screen in front of it.

    A kiosk has no terminal. When something has gone wrong the page says
    "the details are in data/elmer.log", and this is how the person at the
    screen reads them without one. Local requests only, like the report,
    because the log carries addresses and callsigns; `level` narrows it to
    the lines worth reading - warnings and errors - and `ref` finds one
    fault by its reference.
    """
    if not _is_local(request.remote_addr):
        abort(403)
    try:
        lines = max(20, min(2000, int(request.args.get("lines") or 300)))
    except ValueError:
        lines = 300
    level = (request.args.get("level") or "").upper()
    ref = (request.args.get("ref") or "").strip()[:12]
    tail = bugreport._tail(bugreport.LOG, lines)
    if ref:
        # The traceback follows its header line without a timestamp, so
        # take the header and everything up to the next stamped line.
        out, taking = [], False
        for ln in tail:
            stamped = len(ln) > 19 and ln[4] == "-" and ln[10] == " "
            if ref in ln:
                taking = True
            elif stamped and taking:
                taking = False
            if taking:
                out.append(ln)
        tail = out
    elif level in ("WARNING", "ERROR"):
        want = (" WARNING ", " ERROR ") if level == "WARNING" else (" ERROR ",)
        tail = [ln for ln in tail if any(w in ln for w in want) or "UNHANDLED" in ln]
    return jsonify({"path": str(bugreport.LOG), "lines": tail,
                    "level": level or "ALL", "ref": ref})


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
    threading.Timer(0.4, lambda: host.stop_main_thread(
        app.config.get("PORT"))).start()


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
