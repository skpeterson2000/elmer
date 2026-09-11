"""What the law says about listening, for the operator who is about to.

ELMER shows repeaters and, where TowerWitch is alongside, public safety
frequencies. Somewhere behind that is a question nobody asks until it matters:
am I allowed to listen to this, here.

Three rules govern what is written here, because this is the one subject in
the program where being confidently wrong does real harm.

**The statute is the answer; this module is a pointer to it.** Every entry
carries the citation and the official link, and the plain-language line is
marked as ELMER's reading rather than passed off as the law. An operator who
wants to know what the law says can read what the law says, which is the only
version that is authoritative and the only one that is current.

**What has not been checked says so.** `checked` records whether an entry was
read against the primary source or taken from somewhere else. Nothing here is
written from memory - the popular summaries of this subject are wrong often
enough that two of the five states everybody lists as banning mobile scanners
turn out not to, and one of the two whose exemption everybody repeats does not
exempt what they think it exempts.

**Silence is stated, not implied.** A state ELMER has not looked at says so.
An empty entry must never read as "no law here", because the operator cannot
tell those apart and one of them can get them arrested.
"""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from . import paths

log = logging.getLogger("elmer")

ROOT = Path(__file__).resolve().parents[1]
CACHE = paths.STATE / "statutes"
USER_AGENT = "ELMER/1.0 (personal amateur radio study tool)"

# Statutes are amended, not live-updated. A month old is current enough, and a
# unit in a field should show what it fetched rather than nothing at all.
MAX_AGE_SECONDS = 30 * 24 * 3600

# How an entry was arrived at. Anything but PRIMARY is shown with that said.
PRIMARY = "primary"          # read against the official text
SECONDARY = "secondary"      # from a code aggregator, not the legislature


# ---------------------------------------------------------------- federal

# True in every state, and the part most worth knowing. Listening to
# unencrypted public safety is ordinary; the bright lines are decryption and
# what you do with what you heard.
FEDERAL = [
    {
        "point": "Listening to an unencrypted transmission is not the offence.",
        "why": "Receiving is passive and generally lawful. What the federal "
               "statutes reach is decrypting, divulging, and using what you "
               "heard - not the act of tuning.",
        "cite": "18 U.S.C. 2511",
        "url": "https://www.law.cornell.edu/uscode/text/18/2511",
    },
    {
        "point": "Decrypting encrypted traffic is prohibited.",
        "why": "This is the line that matters on a modern trunked system, "
               "because more of them are encrypted every year. Without "
               "authorisation - a written agreement, or a role that carries "
               "it - defeating the encryption is not a grey area. A scanner "
               "that cannot decrypt it is not the point; obtaining the means "
               "is.",
        "cite": "18 U.S.C. 2511",
        "url": "https://www.law.cornell.edu/uscode/text/18/2511",
    },
    {
        "point": "Divulging what you heard, or profiting from it, is separate "
                 "from hearing it.",
        "why": "Repeating an intercepted communication for gain is its own "
               "offence, and it is the one that catches people who were "
               "lawfully listening right up until they posted it.",
        "cite": "47 U.S.C. 605",
        "url": "https://www.law.cornell.edu/uscode/text/47/605",
    },
    {
        "point": "Cellular is off the table, and has been since 1993.",
        "why": "Receivers sold in the United States are required to be "
               "incapable of tuning the cellular bands, and modifying one to "
               "restore them is prohibited.",
        "cite": "47 CFR 15.121",
        "url": "https://www.ecfr.gov/current/title-47/section-15.121",
    },
]


# ------------------------------------------------------------------ states

# Only what has been read. A state missing from here is a state ELMER has not
# looked at, and `advice()` says exactly that rather than implying anything.
STATES = {
    "MN": {
        "name": "Minnesota",
        "reading": "A licensed amateur may have police-frequency receive gear "
                   "in a vehicle - but the exemption has conditions, and one "
                   "of them is that the licence travels with you.",
        "carry_licence": True,
        "statutes": [
            {
                "cite": "Minn. Stat. 299C.37",
                "title": "Radios capable of receiving police frequencies",
                "url": "https://www.revisor.mn.gov/statutes/cite/299C.37",
                "checked": PRIMARY,
                "quote": "No person other than peace officers within the "
                         "state, the members of the State Patrol, and persons "
                         "who hold an amateur radio license issued by the "
                         "Federal Communications Commission, shall equip any "
                         "motor vehicle with any radio equipment or "
                         "combination of equipment, capable of receiving any "
                         "radio signal, message, or information from any "
                         "police emergency frequency.",
                "reading": "The amateur exemption carries three conditions: no "
                           "conviction for a crime of violence, the equipment "
                           "under the licence holder's direct control whenever "
                           "it is used, and the licence carried in the vehicle "
                           "at all times and produced to a peace officer on "
                           "request.",
            },
            {
                "cite": "Minn. Stat. 609.856",
                "title": "Use of police radios during commission of crime",
                "url": "https://www.revisor.mn.gov/statutes/cite/609.856",
                "checked": PRIMARY,
                "quote": "Whoever has in possession or uses a radio or device "
                         "capable of receiving or transmitting a police radio "
                         "signal, message, or transmission of information used "
                         "for law enforcement purposes, while in the "
                         "commission of a felony...",
                "reading": "Not a scanner law. It has no amateur exemption "
                           "because it does not need one - the offence is the "
                           "felony, and the receiver is what raises the "
                           "penalty for it.",
            },
        ],
    },
    "FL": {
        "name": "Florida",
        "reading": "Not a possession law. What is prohibited is intercepting "
                   "police radio in order to commit a crime or get away from "
                   "one.",
        "statutes": [
            {
                "cite": "Fla. Stat. 843.167",
                "title": "Unlawful use of police communications; enhanced "
                         "penalties",
                "url": "https://www.flsenate.gov/Laws/Statutes/2023/843.167",
                "checked": PRIMARY,
                "quote": "Intercept any police radio communication by use of a "
                         "scanner or any other means for the purpose of using "
                         "that communication to assist in committing a crime "
                         "or to escape from or avoid detection, arrest, trial, "
                         "conviction, or punishment",
                "reading": "It lists no amateur exemption and needs none. "
                           "Owning or using a scanner is not what it reaches.",
            },
        ],
    },
    "NY": {
        "name": "New York",
        "reading": "A vehicle restriction with a permit system - and the "
                   "amateur exemption is narrower than it is usually "
                   "reported. Read it before relying on it.",
        "statutes": [
            {
                "cite": "N.Y. Veh. & Traf. Law 397",
                "title": "Equipping motor vehicles with radio receiving sets "
                         "capable of receiving signals on police frequencies",
                "url": "https://www.nysenate.gov/legislation/laws/VAT/397",
                "checked": PRIMARY,
                "quote": "Nothing in this section contained shall be construed "
                         "to apply to any person who holds a valid amateur "
                         "radio operator's license issued by the federal "
                         "communications commission and who operates a duly "
                         "licensed portable mobile transmitter and in "
                         "connection therewith a receiver or receiving set on "
                         "frequencies exclusively allocated by the federal "
                         "communications commission to duly licensed radio "
                         "amateurs.",
                "reading": "Read what that exempts: a receiver used with your "
                           "amateur station, on amateur frequencies. It is not "
                           "obviously a licence to carry a police scanner, "
                           "which is how it is usually summarised. Permits are "
                           "issued by the local governing body, and that is "
                           "the route this section actually provides.",
            },
        ],
    },
    "IN": {
        "name": "Indiana",
        "reading": "A use restriction with a list of exemptions, one of which "
                   "is an amateur licence.",
        "statutes": [
            {
                "cite": "Ind. Code 35-44.1-2-7",
                "title": "Unlawful use of a police radio",
                "url": "https://law.justia.com/codes/indiana/title-35/"
                       "article-44-1/chapter-2/section-35-44-1-2-7/",
                "checked": SECONDARY,
                "quote": "",
                "reading": "Exemptions reported include an amateur licensee "
                           "not transmitting on police emergency frequencies, "
                           "written permission from a law enforcement agency's "
                           "chief executive, use confined to a dwelling or "
                           "place of business, journalists, and dealers. Read "
                           "the section itself before relying on any of them.",
            },
        ],
    },
    "KY": {
        "name": "Kentucky",
        "reading": "A possession and use restriction with a long exemption "
                   "list, including an amateur licence.",
        "statutes": [
            {
                "cite": "KRS 432.570",
                "title": "Restrictions on possession or use of radio capable "
                         "of sending or receiving police messages",
                "url": "https://law.justia.com/codes/kentucky/"
                       "chapter-432/section-432-570/",
                "checked": SECONDARY,
                "quote": "",
                "reading": "Exemptions reported include a valid FCC amateur "
                           "licence, journalists, retailers and wholesalers, "
                           "licensed broadcast stations at their premises, a "
                           "receive-only set at a residence, licensed tow "
                           "trucks, and emergency management personnel "
                           "authorised in writing. Read the section itself "
                           "before relying on any of them.",
            },
        ],
    },
}


def known(state):
    """Whether ELMER has looked at this state at all."""
    return _code(state) in STATES


def _code(state):
    """A two letter code from whatever the profile happens to hold."""
    text = str(state or "").strip()
    if len(text) == 2:
        return text.upper()
    for code, entry in STATES.items():
        if entry["name"].lower() == text.lower():
            return code
    return text.upper()[:2]


def search_url(state):
    """Where to go looking, for a state nobody has written down yet.

    Offered rather than guessed at. A link to a search is honest about being
    a starting point; a sentence invented about a statute nobody read is not.
    """
    where = str(state or "").strip() or "your state"
    query = f"{where} statute police radio scanner motor vehicle amateur radio"
    return "https://www.google.com/search?q=" + urllib.parse.quote(query)


# Every state, so a reverse lookup's "Trenton, Mercer County, New Jersey,
# United States" can be turned into the code the table above is keyed on.
# Names only - nothing here is a claim about any of them.
STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "district of columbia": "DC", "florida": "FL",
    "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY",
    "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT",
    "nebraska": "NE", "nevada": "NV", "new hampshire": "NH",
    "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}


def _state_in(text):
    """The state named in a reverse lookup's address line, if one is."""
    low = (text or "").lower()
    # Longest first, so "west virginia" is not read as "virginia".
    for name in sorted(STATE_CODES, key=len, reverse=True):
        if name in low:
            return STATE_CODES[name]
    return None


def where_am_i(lat, lon, allow_lookup=True):
    """Which state a fix is in, and how well ELMER actually knows that.

    The fix is the driver rather than the saved QTH, because the statutes that
    matter here are about vehicles and a vehicle is the thing that crosses a
    state line. A saved QTH is right until somebody drives, which is exactly
    when it stops being right and nobody thinks to change it.

    Worked out from the places already on disk, because the moment this
    question is worth asking is the moment somebody is somewhere new with no
    signal. That is coarse - a few towns a state - so what comes back says how
    sure it is rather than only what it thinks:

    * far from anything known, it is a guess and says so;
    * where the two nearest towns are in different states, a line is somewhere
      between them and this fix is near it, which is precisely when naming one
      state confidently would be worst.
    """
    from . import geocode, places

    if allow_lookup:
        try:
            found = geocode.reverse(lat, lon)
        except Exception:
            found = None
        code = _state_in((found or {}).get("name"))
        if code:
            return {"state": code, "sure": True,
                    "town": (found or {}).get("short"),
                    "how": "looked up from your position"}

    # No lookup, or it did not name a state. What is left is the bundled town
    # list, and it is never certain enough to say so.
    #
    # It has a few towns a state, which is fine for naming what an antenna can
    # reach and not fine for naming a jurisdiction. Asked where New Jersey is
    # it answers Pennsylvania, because it holds no New Jersey town at all and
    # Philadelphia is 45 km from Trenton; near the St Croix it answers
    # Minnesota with Wisconsin on the other bank. Neither is a bug in the data
    # - it is the wrong instrument for this question, and the honest thing is
    # to offer what it says and refuse to call it settled.
    rows = places.nearest(lat, lon, limit=3)
    rows = rows[0] if isinstance(rows, tuple) else rows
    rows = [r for r in (rows or []) if r.get("region")]
    if not rows:
        return {"state": None, "sure": False,
                "how": "no position, and nowhere known nearby"}
    near = rows[0]
    return {"state": near["region"], "town": near["name"],
            "km": near.get("km"), "sure": False,
            "how": "guessed from the nearest town ELMER knows - %s, %.0f km "
                   "away. It has only a few towns a state, so a state line "
                   "nearer than that is one it cannot see."
                   % (near["name"], near.get("km", 0))}


def advice(state, licensed=True):
    """What to put in front of an operator here, and what to admit.

    `licensed` is whether this operator holds an amateur licence, because in
    three of the five states written down so far that is the whole question.
    """
    code = _code(state)
    entry = STATES.get(code)
    out = {
        "state": code,
        "name": (entry or {}).get("name") or (state or ""),
        "federal": FEDERAL,
        "known": bool(entry),
        "licensed": bool(licensed),
    }
    if not entry:
        # Said plainly. An empty panel reads as "nothing to worry about",
        # which is the one thing it must not mean.
        out["reading"] = ("ELMER has not read this state's law on receiving "
                          "police frequencies. That is not the same as there "
                          "being none.")
        out["look_here"] = search_url(state)
        out["statutes"] = []
        return out
    out["reading"] = entry["reading"]
    out["statutes"] = entry["statutes"]
    out["carry_licence"] = entry.get("carry_licence", False)
    if entry.get("carry_licence") and licensed:
        out["do_this"] = ("Carry your licence in the vehicle. The exemption "
                          "this state gives you is conditional on producing it "
                          "on request.")
    return out


# --------------------------------------------------------------- the text

def _path(cite):
    return CACHE / (cite.replace(" ", "_").replace("/", "-") + ".json")


def fetch(url, cite, refresh=False):
    """The statute itself, from the official site, kept once it is here.

    The citation and the link are in the table above and never depend on the
    network. This is the text, which does, and which is worth having on disk
    for the campsite where there is no signal and a question has just come up.
    """
    path = _path(cite)
    if path.exists() and not refresh:
        try:
            held = json.loads(path.read_text())
            if time.time() - held.get("fetched_at", 0) < MAX_AGE_SECONDS:
                held["cached"] = True
                return held
        except (OSError, ValueError):
            pass
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", "replace")
    except Exception as exc:
        if path.exists():
            try:
                held = json.loads(path.read_text())
                held.update({"cached": True, "stale": True, "error": str(exc)})
                return held
            except (OSError, ValueError):
                pass
        return {"ok": False, "cite": cite, "url": url, "error": str(exc)}
    out = {"ok": True, "cite": cite, "url": url, "html": body,
           "fetched_at": time.time()}
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out))
    except OSError:
        pass
    return out
