"""The first contact, as a track: the steps from a silent radio to a QSO.

Make Contact answers "what can I reach from here" for somebody who already
knows how to key up. The person it did nothing for is the one with a new
handheld and a new callsign who has never pressed the button, and does not
know what to say when they do - which is most of the people who let a
licence lapse without a single contact. What they need is not a list of
avenues but an order: listen first, program one machine, say your call,
answer somebody, keep a log. Each step says how, how you know it worked,
and what to do when it does not, with the specifics filled in - the nearest
repeater's tone and offset, the operator's own call in the words.

Which track depends on what they hold and what they have. No licence is a
track too: FRS and CB are real first contacts, and so is listening to a
net, and the last step of that track is the exam. Progress is the
operator's own, marked with a press and kept in the profile; nothing here
is graded.
"""

STEP = ("key", "title", "how", "know", "stuck", "link")


def _step(key, title, how, know, stuck="", link=None):
    return {"key": key, "title": title, "how": how, "know": know, "stuck": stuck, "link": link}


def _repeater(ways):
    for way in ways or []:
        if way.get("key") == "repeater" and way.get("rows"):
            return way["rows"][0]
    return None


def _has(gear, *keys):
    return bool(set(keys) & set(gear or []))


def _gmrs_repeater(ways):
    for way in ways or []:
        if way.get("key") == "gmrs-repeater" and way.get("rows"):
            return way["rows"][0]
    return None


def build(gear, license, ways, callsign="", done=None, gmrs=None):
    """The steps for this station, in order, with what is done marked.
    `gmrs` is the GMRS licence the person operates under, if any."""
    gear = set(gear or [])
    done = done or {}
    call = (callsign or "").upper().strip()
    licensed = (license or "").lower() not in ("", "none")
    said = call or "your callsign"
    steps = []

    if not licensed:
        steps.append(_step(
            "listen", "Listen for a week before you talk",
            "Find the local repeater in the list on this page and leave a radio - a handheld, a "
            "scanner, a web receiver - on it in the evening. The Thursday-night net, the commute "
            "chatter, the way people say their calls: that is the whole etiquette, and it is "
            "learned by ear in a week.",
            "You can say who the regulars are and when the net is.",
            "Nothing heard: try the other repeaters below, and 146.520 simplex on a weekend.",
            "/bandplan"))
        if _has(gear, "gmrs", "murs", "cb"):
            steps.append(_step(
                "personal", "Make a contact you are already allowed to make",
                "FRS, MURS and CB need no licence. Channel 19 on CB has somebody on it on any "
                "highway; FRS channel 1 or 20 at a campground or a ball game; MURS on a farm. "
                "Say who you are and where, and ask if anybody copies.",
                "Somebody answered, and you said your name and where you were without reading it.",
                "Channel 9 is emergencies only; try 19. FRS needs line of sight - a hilltop.",
                "/bandplan#personal"))
        machine = _gmrs_repeater(ways)
        if gmrs and gmrs.get("found") and machine:
            # A first contact on the air this week, on a licence already
            # held - before any exam. The one step a GMRS ticket changes.
            gcall = gmrs["callsign"]
            steps.append(_step(
                "gmrs", f"Key the GMRS repeater at {machine.get('where') or machine.get('call')} - say {gcall}",
                f"Listen on {machine['output']:.3f} for a while, then transmit 5 MHz up"
                + (f" with tone {machine['tone']}" if machine.get("tone") else "")
                + f": \"{gcall}, listening.\" It is {machine['miles']} miles off, {machine.get('reach', 'within reach')}. "
                f"Say the call at the end of the exchange too - it is the licence talking, and on GMRS "
                f"that licence covers the whole family (95.1705(c)).",
                "Somebody came back to your call through the machine, and you heard yourself in the repeater's tail.",
                "Nothing back: the owner's say-so may be needed - the call on the listing is theirs. Try channel 20 "
                "simplex with the travel tone meanwhile.",
                "/bandplan#personal"))
        steps.append(_step(
            "exam", "Sit the Technician exam",
            "Thirty-five questions from a public pool of about four hundred, and the pool is in "
            "this program with the reasons behind every answer. Most people pass in three to six "
            "weeks of evenings. The exam costs about fifteen dollars and the licence lasts ten "
            "years.",
            "A callsign in the FCC database with your name on it - usually within a week.",
            "Stuck on a section: the study pages drill one section at a time.",
            "/study/tech2026"))
        return _mark(steps, done)

    rep = _repeater(ways)
    steps.append(_step(
        "listen", "Listen first - an hour, then a week",
        (f"Put the radio on {rep['call']} ({rep['output']:.3f}) and leave it there in the evening. "
         if rep else "Put the radio on the nearest repeater below and leave it there in the evening. ")
        + "Hear how people open ('W0XYZ monitoring'), how they hand over, how long they leave "
          "between overs. Nobody is graded on it; the ear does the learning.",
        "You know when the weekly net is and who runs it.",
        "Nothing heard all evening: the antenna is inside, or the machine is quiet - try the "
        "next one on the list, or 146.520 on a weekend afternoon.",
        "/bandplan"))
    if _has(gear, "ht", "mobile_vhf", "vhf_ssb"):
        steps.append(_step(
            "program", "Program one repeater - by hand, once",
            (f"{rep['call']}: receive {rep['output']:.3f}"
             + (f", transmit offset {rep['offset']:+.1f} MHz" if rep and rep.get("offset") else ", the standard offset")
             + (f", tone {rep['tone']}" if rep and rep.get("tone") else ", and find the tone - it is in the list below")
             + f". It is {rep['miles']} miles away on a bearing of {rep['bearing']}°. "
             if rep else "The nearest machine is in the list below, with its offset and tone. ")
            + "Do it from the radio's keypad the first time, not from software: the day it matters "
              "you will be doing it from the keypad.",
            "Press the key for half a second and let go: the repeater's tail - a courtesy beep or a "
            "second of carrier - comes back. That is the machine hearing you.",
            "No tail: check the tone first (nine times in ten), then the offset sign, then get "
            "twenty feet higher. At VHF, height beats power.",
            "/bandplan"))
        steps.append(_step(
            "key", "Say your callsign, once, and wait",
            f"Key, wait half a second, say '{said}, monitoring' - or '{said}, listening' - "
            "unkey, and wait a full minute. Not 'is anybody there', not a CQ: on a repeater, "
            "the call alone is the invitation.",
            "Somebody comes back with their call and yours. That is the contact - it counts.",
            "Nobody after three tries ten minutes apart: it is the hour, not you. Try the net "
            "night, when the machine is busy on purpose.",
            None))
        steps.append(_step(
            "net", "Check in to the net",
            "The weekly net is where a new call is expected. When net control asks for check-ins, "
            "say your call phonetically, your name, and where you are - three things, then unkey. "
            "Net control repeats it back; that is all a check-in is.",
            "You are on the net's log, and somebody said 'welcome' - they do.",
            "Missed the call for check-ins: wait for 'any late check-ins', which every net asks.",
            None))
        steps.append(_step(
            "simplex", "One contact with no repeater in between",
            "146.520 FM, both radios on the same frequency, no offset, no tone. Ask somebody from "
            "the net to meet you there after it closes; a mile or two with a handheld, twenty "
            "with a mobile and a good spot.",
            "You heard them directly and they heard you - the first contact that was all yours.",
            "Nothing: height again, and a vertical antenna at both ends. Move to a hilltop and try "
            "the same person.",
            "/out"))
    if _has(gear, "hf_mobile", "hf_wire"):
        steps.append(_step(
            "antenna", "Get a wire up and know it is resonant",
            "A dipole cut for 40 m from the antenna calculator, as high as a tree allows, fed "
            "with whatever coax you have. Check it with the analyser in Tools or a meter before "
            "you transmit into it.",
            "SWR under 2:1 where you mean to operate.",
            "High SWR everywhere: a joint, not the length. Low only off-band: cut or extend "
            "by the calculator's figure.",
            "/lab#ant"))
        steps.append(_step(
            "answer", "Answer a CQ - do not call one yet",
            "Tune the band the propagation page says is open, find somebody calling CQ clearly, "
            "and when they finish, say their call once and yours twice, phonetically. They come "
            "back with a signal report; you give one, your name and your state, and thank them.",
            "Both calls, both reports, a name each way. Write it down: that is a QSO.",
            "They did not hear you: somebody louder answered first. Wait for the next one; the "
            "band that is open is on the propagation page, and after dark it is 40 m.",
            "/propagation"))
    steps.append(_step(
        "log", "Write it down, every time",
        "Date and time in UTC, their call, the frequency, the mode, the report each way, and "
        "one thing they said. A notebook is fine; a logging program is fine.",
        "You can tell somebody the call of your first contact without looking it up.",
        "",
        "/prints"))
    steps.append(_step(
        "next", "Then: a park, a summit, a satellite, CW",
        "The parks page shows what has worked for others near you; the ISS digipeater is a "
        "handheld away; the CW pages teach the code from nothing. Any of them is the next "
        "track, and the first one is the one that got you here.",
        "You have a next thing.",
        "",
        "/activations"))
    return _mark(steps, done)


def _mark(steps, done):
    for n, step in enumerate(steps, 1):
        step["n"] = n
        step["done"] = done.get(step["key"]) or None
    first = next((s for s in steps if not s["done"]), None)
    for step in steps:
        step["next"] = step is first
    return steps
