"""Where a position came from, what it can vouch for, and whether two agree.

ELMER uses where the station is for nearly everything it says - reach,
bearings, the band plan's coordinator, the sky overhead - and it hears a
position from several places that are not equally good. A receiver on this
unit with a fix is one thing. TowerWitch's broadcast, which carries no word
on whether its receiver has a lock, is another: its default when it has none
is Minneapolis, and a station in Pequot Lakes was being put there. A browser
asked for a position on a desktop answers from the network - an IP address
or the nearest Wi-Fi - and can be a county out. So every position carries
its class, its stated accuracy and a label in words, and they are ranked by
what they can vouch for:

  fix        a receiver's own fix: gpsd with a fix, a phone better than
             about 100 m, TowerWitch when its packet says it has a fix,
             another ELMER relaying one of these, a sextant fix
  typed      the QTH the operator set
  unvouched  a position nobody vouches for: TowerWitch without a fix
             quality, TowerWitch's last known or fallback position, a coarse
             browser guess, another ELMER relaying one of these

A fix beats the typed QTH - a mobile station's typed QTH is the stale one -
and the typed QTH beats anything unvouched. Two positions farther apart than
max(5 km, three times the larger of their stated accuracies) disagree, and
that is said rather than silently resolved.

Labels carry where and how sure, never where: no coordinates and no town
names go into a label, so one can travel in a report as it stands.
"""
from . import geo

FIX, TYPED, UNVOUCHED = "fix", "typed", "unvouched"
RANK = {FIX: 0, TYPED: 1, UNVOUCHED: 2}

PHONE_FIX_M = 100.0          # a phone better than this is a fix
UERE_M = 5.0                 # metres of position error per unit of HDOP
MODE_M = {3: 10.0, 2: 30.0}  # a receiver's error when it states none
DISAGREE_MIN_M = 5000.0
DISAGREE_TIMES = 3.0
# A typed QTH is as sure as the way it was typed. A four-character grid is
# about 150 by 110 km at these latitudes, a six-character one about 7 by
# 5, a place name the size of the town it names; coordinates are exact.
GRID_M = {4: 75000.0, 6: 4000.0, 8: 400.0}
PLACE_M = 3000.0


def _num(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def accuracy_m(pos, saved=False):
    """The position's error in metres, stated or fairly derived; None if
    nothing is known about it (a typed coordinate pair is taken as exact)."""
    for key in ("accuracy_m", "eph"):
        got = _num(pos.get(key))
        if got is not None:
            return got
    hdop = _num(pos.get("hdop"))
    if hdop is not None:
        return hdop * UERE_M
    if saved:
        kind = pos.get("kind")
        if kind == "grid":
            return GRID_M.get(len(str(pos.get("grid") or pos.get("short") or "")), GRID_M[6])
        if kind in ("coordinates", "coords", "celestial"):
            return None
        if pos.get("source") in (None, "") and kind not in ("fix", "gps"):
            return PLACE_M
        return None
    # A receiver that states its mode and no error is given the usual error
    # for that mode. Only a receiver: a phone that states no accuracy has
    # not stated one, and is not a fix on the strength of a guess.
    src = pos.get("source")
    if src not in ("gps", "towerwitch-net"):
        return None
    mode = pos.get("fix_mode") if src == "towerwitch-net" else pos.get("mode")
    return MODE_M.get(int(mode)) if isinstance(mode, (int, float)) and int(mode) in MODE_M else None


def _plus(m):
    if m is None:
        return ""
    return f", ±{m:.0f} m" if m < 1000 else f", ±{m / 1000:.1f} km"


def vouch(pos, saved=False):
    """{"class", "accuracy_m", "label"} for one position. `saved` is the
    operator's QTH as stored, not a live report."""
    if not pos:
        return None
    acc = accuracy_m(pos, saved)
    src = pos.get("source")
    if saved:
        kind = pos.get("kind")
        if src == "browser" or pos.get("browser"):
            if acc is not None and acc <= PHONE_FIX_M:
                return {"class": FIX, "accuracy_m": acc, "label": f"the browser's position, saved{_plus(acc)}"}
            return {"class": UNVOUCHED, "accuracy_m": acc,
                    "label": "the browser's position, saved - may be an IP or Wi-Fi guess" + _plus(acc)}
        if kind == "celestial":
            return {"class": FIX, "accuracy_m": acc, "label": "a sextant fix, saved"}
        if src:
            # A live position somebody saved as the QTH: it was a fix then,
            # and it is the typed QTH now - saved, not live.
            inner = vouch({k: v for k, v in pos.items() if k != "kind"})
            return {"class": TYPED, "accuracy_m": acc,
                    "label": f"saved from {inner['label'] if inner else src}"}
        if kind in ("fix", "gps"):
            # Saved by "Locate me" before the source was kept with it: a
            # position the operator accepted, from where no longer known.
            return {"class": TYPED, "accuracy_m": acc,
                    "label": "a located position, saved before its source was kept"}
        what = {"grid": "a typed grid square", "coordinates": "typed coordinates",
                "coords": "typed coordinates"}.get(kind, "a typed place name")
        return {"class": TYPED, "accuracy_m": acc, "label": what + _plus(acc)}
    if src == "gps":
        mode = pos.get("mode")
        sats = pos.get("sats")
        return {"class": FIX if (mode or 0) >= 2 else UNVOUCHED, "accuracy_m": acc,
                "label": f"gpsd, {mode}D fix" + (f", {sats} satellites" if sats is not None else "") + _plus(acc)}
    if src == "phone":
        mode = pos.get("mode") or 0
        if acc is not None and acc <= PHONE_FIX_M and mode >= 2:
            return {"class": FIX, "accuracy_m": acc, "label": f"a phone, {mode}D fix{_plus(acc)}"}
        return {"class": UNVOUCHED, "accuracy_m": acc,
                "label": "a phone" + (f", too coarse to vouch for{_plus(acc)}" if acc is not None
                                      else ", with no accuracy to vouch for it")}
    if src == "towerwitch-net":
        if pos.get("fallback"):
            return {"class": UNVOUCHED, "accuracy_m": acc,
                    "label": "TowerWitch's fallback position - it says it has no fix"}
        mode = pos.get("fix_mode")
        if mode is None:
            return {"class": UNVOUCHED, "accuracy_m": acc, "label": "TowerWitch - no fix quality given"}
        if mode >= 2:
            sats = pos.get("sats")
            return {"class": FIX, "accuracy_m": acc,
                    "label": f"TowerWitch's receiver, {int(mode)}D fix"
                             + (f", {sats} satellites" if sats is not None else "") + _plus(acc)}
        return {"class": UNVOUCHED, "accuracy_m": acc, "label": "TowerWitch - its receiver has no fix"}
    if src == "towerwitch":
        was = (" - its fallback, not a fix" if pos.get("fallback")
               else " - a fix when it was written" if pos.get("fallback") is False and (pos.get("fix_mode") or 0) >= 2
               else "")
        return {"class": UNVOUCHED, "accuracy_m": acc, "label": "TowerWitch's last known position" + was}
    if src == "elmer-peer":
        via = pos.get("via") or {}
        said = via.get("label") or "a source it did not name"
        cls = FIX if via.get("class") == FIX else UNVOUCHED
        return {"class": cls, "accuracy_m": _num(via.get("accuracy_m")),
                "label": f"another ELMER, relaying {said}"}
    if src == "browser":
        if acc is not None and acc <= PHONE_FIX_M:
            return {"class": FIX, "accuracy_m": acc, "label": f"the browser's position{_plus(acc)}"}
        return {"class": UNVOUCHED, "accuracy_m": acc,
                "label": "the browser's position - may be an IP or Wi-Fi guess" + _plus(acc)}
    return {"class": UNVOUCHED, "accuracy_m": acc, "label": f"{src or 'an unnamed source'}"}


def disagreement(a, b, va=None, vb=None):
    """{"km", "limit_km"} when two positions are farther apart than
    max(5 km, 3 x the larger of their stated accuracies), else None."""
    if not a or not b or a.get("lat") is None or b.get("lat") is None:
        return None
    km, _ = geo.great_circle(float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"]))
    accs = [x for x in ((va or {}).get("accuracy_m"), (vb or {}).get("accuracy_m")) if x is not None]
    limit_m = max(DISAGREE_MIN_M, DISAGREE_TIMES * max(accs)) if accs else DISAGREE_MIN_M
    if km * 1000.0 <= limit_m:
        return None
    return {"km": round(km, 1), "limit_km": round(limit_m / 1000.0, 1)}


def best(live):
    """The live position to use from several, by class and then in the
    order given (which is the order they are trusted in)."""
    live = [p for p in live if p]
    if not live:
        return None
    return min(live, key=lambda p: RANK[vouch(p)["class"]])


def choose(saved, live, others=()):
    """The position to work from, with the account of it.

    `saved` is the operator's QTH (may be empty), `live` the best live
    position (may be None), `others` every other live position heard. A
    fix beats the typed QTH, the typed QTH beats anything unvouched, and
    an unvouched position is used only when there is nothing else. Returns
    (chosen, account); account is {"class", "label", "accuracy_m", "source",
    "disagree": [{"with", "km", "limit_km"}]}.
    """
    have_saved = bool(saved) and saved.get("lat") is not None
    vs = vouch(saved, saved=True) if have_saved else None
    vl = vouch(live) if live else None
    if vl and vl["class"] == FIX:
        chosen, vc = live, vl
    elif have_saved:
        # Typed, or itself unvouched - either way no worse than a live
        # position that is not a fix, and it is the one the operator chose.
        chosen, vc = saved, vs
    elif live:
        chosen, vc = live, vl
    else:
        return saved, None
    disagree = []
    rivals = ([(saved, vs)] if have_saved and chosen is not saved else []) \
        + ([(live, vl)] if live and chosen is not live else []) \
        + [(p, vouch(p)) for p in others if p and p is not live and p is not chosen]
    for other, vo in rivals:
        gap = disagreement(chosen, other, vc, vo)
        if gap:
            disagree.append({"with": vo["label"], "class": vo["class"], **gap})
    return chosen, {"class": vc["class"], "label": vc["label"], "accuracy_m": vc["accuracy_m"],
                    "source": chosen.get("source") or ("typed" if chosen is saved else None),
                    "disagree": disagree}


def words(account):
    """The account as one sentence for the self-check and the pages."""
    if not account:
        return "no position from anywhere"
    out = f"from {account['label']}"
    for d in account.get("disagree") or []:
        out += (f"; {d['with']} is {d['km']:.0f} km from it"
                f" (more than the {d['limit_km']:.0f} km their accuracies allow)")
    return out
